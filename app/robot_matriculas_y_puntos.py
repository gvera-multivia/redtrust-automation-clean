import logging
import shutil, time, os
from datetime import datetime
from typing import Optional, List
from dotenv import load_dotenv

# THIRD PARTY PACKAGES
from multiprocessing import Manager, Process, Queue
from uuid import uuid4

# PERSONAL PACKAGES
from database.informesDgt.database_informesDgt import InformesDgtDatabase
from app.helper.loggerV2 import LoggerV2
from app.models.database_models import HistoricoAutomatizaciones, InformesDgtAutomatizaciones
from app.redtrust.redtrust_manager import RedTrustManager 
from app.robot.handle_certificate import CertificateManager
from app.robot.matriculasypuntos.robotDgt import RobotDgt
from app.utils.utils import random_wait
import argparse

def log_listener(queue:Queue, date:str , execution_id : str):
    """Escucha logs y escribe con el logger adecuado por clase/tarea."""
    loggers = {}

    while True:
        try:
            record = queue.get()
            if record is None:
                break

            # Obtener o crear el logger basado en módulo y clase
            key = (record["module"], record["class_name"])
            if key not in loggers:
                loggers[key] = LoggerV2(
                    execution_id=execution_id,
                    module=record["module"],
                    class_name=record["class_name"],
                    filename=f"matriculasypuntos",
                    log_dir=r"logs\matriculasypuntos",
                )

            logger = loggers[key]
            level = record.get("level", logging.INFO)

            # Mapear nivel de log a método del logger
            log_method = {
                logging.ERROR: logger.error,
                logging.WARNING: logger.warning,
                logging.DEBUG: logger.debug,
                logging.INFO: logger.info
            }.get(level, logger.info)


            log_method(
                cliente=record["cliente"],
                task_id=record["task_id"],
                result=record["result"],
                message=record["message"]
            )


        except Exception as e:
            default_logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="LogListener", log_dir=r"logs\matriculasypuntos",)
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

def run_portal_robot_static(
    cliente: int | str,
    task_id: str,
    informes_dgt : InformesDgtAutomatizaciones,
    result_queue: List,
    robot: RobotDgt,
    execution_id: str,
    logger: Optional[LoggerV2] = None
) -> None:
    try:
        

        # If no logger was passed (to avoid pickling parent logger), create a local one
        if logger is None:
            logger = LoggerV2(
                execution_id=execution_id,
                module="MatriculasyPuntos",
                class_name="PortalRobot",
                filename="matriculasypuntos",
                log_dir=r"logs\matriculasypuntos",
            )

        informes_dgt, matriculas, puntos = robot.informeDgt(informes_dgt)

        if informes_dgt is None:
            result_queue.append((task_id, 'error', None))
            logger.error(cliente, task_id, "Failure", "El robot devolvió None")
            return 
        else:
            if matriculas is None and puntos is None:
                result_queue.append((task_id, 'error', None))
                logger.error(cliente, task_id, "Pending", f"Portal robot for task {cliente} failed to retrieve data. informe_dgt={informes_dgt}, matriculas={matriculas}, puntos={puntos}")
                return 
                            
            else:
                result_queue.append((task_id, 'completed', {'informe_dgt': informes_dgt, 'matriculas': matriculas, 'puntos': puntos}))
                logger.info(cliente, task_id, "Success", f"Portal robot for task {cliente} completed with results: informe_dgt={informes_dgt}")
                return  

    except Exception as e:
        logger.error(cliente, task_id, "Failure", f"Error in portal robot for task {cliente}: {e}")
        result_queue.append((cliente, 'error', None))
        return 

def run_certificate_handler_static(
        cliente: int | str, 
        task_id: str, 
        recipient_name: str, 
        result_queue: List, 
        date : str, 
        execution_id: str,
        logger: Optional[LoggerV2] = None
    ):

    retries = 0
    max_retries = 5
    certificate_manager = CertificateManager(
        cliente=cliente,
        task_id=task_id,
        sede='dgt',
        date=date,
        module="MatriculasyPuntos",
        execution_id=execution_id,
        filename="matriculasypuntos"
    )

    # If no logger was passed (to avoid pickling parent logger), create a local one
    if logger is None:
        logger = LoggerV2(
            execution_id=execution_id,
            module="MatriculasyPuntos",
            class_name="CertificateHandler",
            filename="matriculasypuntos",
            log_dir=r"logs\matriculasypuntos",
        )

    while retries < max_retries:
        try:
            start_time = time.time()
            while time.time() - start_time < 10:  
                result = certificate_manager.handle_certificate(recipient_name)                
                if result is None:
                    logger.error(cliente, task_id, "Failure", "El manejador de certificados devolvió None")
                    return None
                else:
                    if result:
                        logger.info(cliente, task_id, "Success", f"Certificate handler for task {cliente} completed with result: {result}")
                        result_queue.append((cliente, 'certificate_handled', result))
                        return result
                    else:
                        logger.error(cliente, task_id, "Pending", f"Certificate handler for task {cliente} failed. Retrying...")

        except Exception as e:
            logger.error(cliente, task_id, "Failure", f"Error in certificate handler for task {cliente}, attempt {retries}: {e}")
            return None
        finally:
            retries += 1

    if retries == max_retries:
        logger.error(cliente, task_id, "Failure", f"Max retries reached for task {cliente}. Marking as failed.")
    
    result_queue.append((cliente, 'certificate_handled', False))
    return result


class RobotMatriculasYPuntos:
    load_dotenv(dotenv_path='.env', override=True)
    db_config = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "server": os.getenv("DB_SERVER"),
        "database": os.getenv("DB_NAME"),
        "options": {
            "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
            "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
        }
    }

    def __init__(self, date: str, execution_id : str):
        self.date = date
        self.execution_id = execution_id 
        self.database_manager = InformesDgtDatabase(
            db_config=self.db_config,
            date=self.date,
            module="MatriculasyPuntos",
            filename="matriculasypuntos",
            execution_id=self.execution_id
        )
        self.redtrust_manager = None

        self.logger = LoggerV2(
            execution_id=execution_id,
            module="MatriculasyPuntos",
            class_name=self.__class__.__name__, 
            log_dir="logs/matriculasypuntos",
            filename=f"matriculasypuntos"
        )
        self.total_tasks = 0
        self.completed_tasks = 0
        self.progress = 0.0
        self.progress_by_task = {}

    def calcular_total_tasks(self, clientes):
        self.total_tasks = len(clientes)
        self.logger.info(None, None, "Success", f"Total de tareas a ejecutar: {self.total_tasks}")

    def actualizar_progreso_fase(self, fase: str, extra: str = ""):
        fases_pesos = {
            'db_fetch': 10,
            'ejecucion_tarea': 90,
        }
        if not hasattr(self, '_progreso_fases'):
            self._progreso_fases = {k: False for k in fases_pesos}
            self._progreso_base = 0
            self._progreso_tarea_unit = 0
            self._progreso_mitad = 0.0
        if fase != 'ejecucion_tarea' and not self._progreso_fases.get(fase, False):
            self._progreso_base += fases_pesos.get(fase, 0)
            self.progress = self._progreso_base
            self._progreso_fases[fase] = True
            self.logger.info(None, None, "Success", f"Progreso: {self.progress:.2f}% - Fase completada: {fase}. {extra}")
        elif fase == 'ejecucion_tarea':
            self.completed_tasks += 0.5
            if self.total_tasks > 0:
                self._progreso_tarea_unit = fases_pesos['ejecucion_tarea'] / self.total_tasks
            else:
                self._progreso_tarea_unit = 0
            self.progress = self._progreso_base + self.completed_tasks * (self._progreso_tarea_unit / 2)
            self.logger.info(None, None, "Pending", f"Progreso: {self.progress:.2f}% - Ejecutada media tarea {self.completed_tasks} de {self.total_tasks}. {extra}")

    def _fetch_dev_clientes(self, clientes: Optional[List[int | str]] = None, limit: Optional[int] = 100):
        try:
            clientes_fetched = self.database_manager.fetch_dev_clientes(clientes=clientes, limit=limit)
            error_clients = []
            try:
                with open("error_clients.txt", "r") as error_file:
                    error_clients = [int(line.strip()) for line in error_file if line.strip().isdigit()]
            except FileNotFoundError:
                self.logger.error(None, None, "Pending", "error_clients.txt file not found. Creating a new one.")
                with open("error_clients.txt", "w") as error_file:
                    pass 
            except Exception as e:
                self.logger.error(None, None, "Failure", f"Error reading error_clients.txt: {e}")

            clientes = [
                cliente for cliente in clientes_fetched
                if cliente['customer_number'] not in error_clients
            ]
            self.logger.info(None, None, "Success", f"Clientes obtenidos de la base de datos: {len(clientes)}")
            return clientes, clientes_fetched
        except Exception as e:
            self.logger.error(None, None, "Failure", f"Error fetching clients: {e}")
            return [], [], []

    def run(self, clientes: Optional[List[int | str]] = None, limit: Optional[int] = 100):
        self.logger.info(clientes or "GLOBAL", "RUN", "Info", "Starting Robot Matriculas y Puntos Manager for execution_id: " + self.execution_id)

        self.actualizar_progreso_fase('db_fetch', 'Consultando clientes en base de datos...')
        clientes_data, clientes_fetched = self._fetch_dev_clientes(clientes, limit=limit)
        # for cliente in clientes_data:
        #     self.database_manager.insert_assignment_log(
        #         id_value=f"informedgt_{cliente['customer_number']}_dev",
        #         cliente=str(cliente['customer_number']),
        #         sede='dev',
        #         robot_name="RobotInformesDGT",
        #         assigned_by="Adrià Martínez"
        #     )

        self.calcular_total_tasks(clientes_data)
        try:
            for i in range(0, len(clientes_data), 3):
                bloque_clientes = [(cliente['customer_number'], cliente) for cliente in clientes_data[i:i+3]]        
                self.logger.info(None, None, "Pending", f"Processing block of clients: {bloque_clientes}")

                if self.redtrust_manager is None:
                    credentials = {
                            "usuario": os.getenv("USUARIO"),
                            "password": os.getenv("PASSWORD")
                        }
                    self.redtrust_manager = RedTrustManager(
                        credentials=credentials,
                        date=self.date,
                        module="MatriculasyPuntos",
                        filename="matriculasypuntos",
                        cliente=str(bloque_clientes),
                        execution_id=self.execution_id
                    )

                if not self.redtrust_manager.automate_redtrust([cliente[0] for cliente in bloque_clientes]):
                    self.logger.error(None, None, "Failure", f"RedTrust automation failed for clients: {[cliente[0] for cliente in bloque_clientes]}. Skipping this block.")
                    continue
                
                try:
                    listener = None
                    log_queue = Queue()
                    try:
                        listener = Process(target=log_listener, args=(log_queue,self.date, str(self.execution_id)))
                        listener.start()
                    except Exception as e:
                        # If the listener fails to start, log and continue; children will create their own loggers
                        self.logger.error(None, None, "Pending", f"Could not start log listener: {e}")

                    with Manager() as manager:
                        result_queue = manager.list()  
                        for index, (cliente, cliente_info) in enumerate(bloque_clientes):
                            task_id = f"informeDGT_{cliente}"
                            result_queue[:] = []  
                            processes = []                           

                            executionRecord = HistoricoAutomatizaciones(
                                execution_id=uuid4(),
                                cliente=cliente,
                                nif=cliente_info.get('nif', None),
                                cif=cliente_info.get('cif', None),
                                tipo_cliente=cliente_info.get('customer_number_type', None),
                                robot_name="RobotInformesDGT",                                
                                status="pending",
                                sede='dev',
                                updated_by_user_id=78,
                                updated_by_user_name="Adría Martínez",
                            )

                            self.database_manager.insert_historico(executionRecord)          

                            informes_dgt = InformesDgtAutomatizaciones(
                                id=uuid4(),
                                execution_id=executionRecord.execution_id,
                            )                  

                            robot = RobotDgt(
                                cliente=cliente,
                                task_id=task_id,
                                date=datetime.now().strftime('%Y-%m-%d'),
                                log_queue=log_queue,
                                module="MatriculasyPuntos",
                                execution_id=self.execution_id
                            )

                            portal_process = Process(
                                target=run_portal_robot_static,
                                args=(cliente, task_id, informes_dgt, result_queue, robot, self.execution_id, None),
                                name=f"portal-{cliente}-dgt_matriculas"
                            )
                            processes.append(portal_process)
                            portal_process.start()
                            random_wait('SHORT', wait=True)  # Esperar un poco antes de iniciar el proceso del certificado

                            cert_process = Process(
                                target=run_certificate_handler_static,
                                args=(cliente, task_id, cliente_info['recipient_name'], result_queue, self.date, self.execution_id, None),
                                name=f"cert-{cliente}-dgt_matriculas"
                            )
                            processes.append(cert_process)
                            cert_process.start()

                            # Wait for portal process with a timeout to avoid blocking indefinitely
                            portal_process.join()
                            if not portal_process.is_alive():                                
                                # Portal finished; give the certificate handler some time to finish gracefully
                                cert_process.join(timeout=5)
                                if cert_process.is_alive():
                                    try:
                                        cert_process.terminate()
                                    except Exception:
                                        pass
                                    try:
                                        cert_process.join(timeout=5)
                                    except Exception:
                                        pass

                            try:
                                for result in result_queue:
                                    result_id, result_status, result_data = result

                                    if result_status == 'error':
                                        executionRecord.status = 'error'
                                        executionRecord.result_robot = str(result)
                                        executionRecord.execution_message = f""
                                    elif result_status == 'certificate_handled':
                                        executionRecord.status = 'pending'
                                        executionRecord.result_certificate = str(result) 
                                    elif result_status == 'completed':
                                        executionRecord.status = 'completed'
                                        executionRecord.result_robot = str(result_data)
                                        executionRecord.execution_message = f"Datos de Informe de la DGT obtenidos correctamente para cliente {cliente}, \
                                            matriculas={result_data['informe_dgt'].matriculas}, puntos={result_data['informe_dgt'].puntos}."
                                        
                                        # if result_data['matriculas'] is not None:
                                        #     self.database_manager.insert_matriculas(cliente_info, result_data['matriculas'])

                                        # if result_data['puntos'] is not None:
                                        #     self.database_manager.insert_puntos(cliente_info, result_data['puntos'])                                        

                                        self.logger.info(cliente, task_id, "Success", f"Datos guardados correctamente para el cliente {cliente}.")
                                                                                
                                    else:
                                        self.logger.error(cliente, task_id, "Failure", f"Unknown result status {result_status} for client {cliente}.")

                                
                                matriculas = result_data.get('matriculas', None)
                                puntos = result_data.get('puntos', None)
                                informe_dgt = result_data.get('informe_dgt', None)

                                matriculas_records = matriculas.get('vehiculos', []) if matriculas is not None else None
                                alertas_records = matriculas.get('alertas', []) if matriculas is not None else None
                                sanciones_records = puntos.get('sanciones', []) if puntos is not None else None

                                self.database_manager.update_historico_informesDgt(
                                    record=executionRecord,
                                    informeDgt_record=informe_dgt,
                                    matriculas_records=matriculas_records,
                                    sanciones_records=sanciones_records,
                                    alertas_records=alertas_records
                                )
                                        
                                            
                            except Exception as e:
                                self.logger.error(cliente, task_id, "Failure", f"Error al guardar los datos para el cliente {cliente}: {e}")
                                continue                        
                except Exception as e:
                    self.logger.error(None, None, "Failure", f"Error in multiprocessing block for clients {bloque_clientes}: {e}")  
                finally:
                    # Ensure listener is terminated
                    try:
                        if 'log_queue' in locals() and listener is not None:
                            try:
                                log_queue.put(None)
                            except Exception:
                                pass
                            try:
                                listener.join(timeout=10)
                            except Exception:
                                pass
                    except Exception:
                        pass
                                
        except Exception as e:       
            self.logger.error(None, None, "Failure", f"Error al procesar los clientes con IDs {bloque_clientes}: {e}")
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run Robot Matriculas y Puntos")
    parser.add_argument("--cliente", "-c", help="Cliente id (int or str)", default=None)
    args = parser.parse_args()

    date = datetime.now().strftime('%Y%m%d')
    manager = RobotMatriculasYPuntos(date, execution_id=str(uuid4()))

    cliente_arg = None
    if args.cliente is not None:
        try:
            cliente_arg = int(args.cliente)
        except ValueError:
            cliente_arg = args.cliente

    manager.run(clientes=cliente_arg)
