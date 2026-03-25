import logging
import os, time, json, argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4

# THIRD PARTY PACKAGES
from dotenv import load_dotenv
from multiprocessing import Process, Manager, Queue

# PERSONAL PACKAGES - ROBOTS
from app.helper.errors.redtrust import ErrorRedtrust
from app.models.database_models import AltasAutomatizaciones, HistoricoAutomatizaciones
from app.redtrust.redtrust_manager import RedTrustManager
from database.altas.database_altas import AltasDatabase
from app.robot.altas.robotAyuntamientoMalaga import RobotAyuntamientoMalaga
from app.robot.handle_certificate import CertificateManager

# PERSONAL PACKAGES - ROBOTS ALTAS
from app.robot.altas.robotDgt import RobotDGT
from app.robot.altas.robotDehu import RobotDehu
from app.robot.altas.robotEnotum import RobotEnotum
from app.robot.altas.robotAndalucia import RobotAndalucia
from app.robot.altas.robotAsturias import RobotAsturias
from app.robot.altas.robotBurgos import RobotBurgos
from app.robot.altas.robotCastillaLaMancha import RobotCastillaLaMancha
from app.robot.altas.robotCastillaLeon import RobotCastillaLeon
from app.robot.altas.robotCeuta import RobotCeuta
from app.robot.altas.robotComunidadValenciana import RobotComunidadValenciana
from app.robot.altas.robotLaRioja import RobotLaRioja
from app.robot.altas.robotMadrid import RobotMadrid
from app.robot.altas.robotMelilla import RobotMelilla
from app.robot.altas.robotPaisVasco import RobotPaisVasco
from app.robot.altas.robotTerrassa import RobotTerrassa
from app.robot.altas.robotAtc import RobotAtc
from app.robot.altas.robotBadajoz import RobotBadajoz
from app.robot.altas.robotBaleares import RobotAtib
from app.robot.altas.robotXaloc import RobotXaloc
from app.robot.altas.robotMigjornGran import RobotMigjornGran

# PERSONAL PACKAGES - UTILS
from app.utils.utils import random_wait
from app.helper.loggerV2 import LoggerV2

date = datetime.now().strftime("%Y%m%d")

def run_portal_robot_static(logger: LoggerV2, robot_class, cliente: str, manager: str, client_name: str, direccion: dict, tipo_cliente: str, cif: str, nif: str, sede: str, result_queue: List):
    try:
        logger.info(cliente, sede, "Pending", f"Starting portal robot for task {cliente} (type: {sede})")
            
        cif = cif.upper() if cif else None
        nif = nif.upper() if nif else None
        if tipo_cliente == 'Empresa':
            id_value = cif
        else:
            id_value = nif

        subscribe_args_map = {
            'baleares':        (cliente, direccion),
            'badajoz':         (cliente, nif),
            'ceuta':           (cliente, id_value),
            'mahon':           (id_value, direccion),
            'madrid':          (id_value,),
            'oficina virtual ayuntamiento terrassa': (client_name, tipo_cliente, id_value, direccion),
            'xaloc':           (id_value, ),
            'castilla la mancha': (cliente, id_value, tipo_cliente),
            'pais vasco':      (cliente, client_name, id_value, tipo_cliente),
            'andalucía':       (client_name, nif),
            'enotum':          (cliente, id_value, client_name),
            'agencia tributaria de catalunya': (cliente, id_value, tipo_cliente),
            'migjorn gran':   (tipo_cliente, direccion, id_value),
            'ayuntamiento de málaga': (cliente, id_value, direccion),
        }
        args = subscribe_args_map.get(sede, (cliente, id_value))
        result = robot_class.subscribe(*args)

        if sede in ['agencia tributaria de catalunya', 'oficina virtual ayuntamiento terrassa', 'madrid', 'castilla la mancha', 'ayuntamiento de málaga']:
            check, action, email = result
        else:
            check, action = result

        if check: 
            result_queue.append((f"{cliente}-{sede}", 'completed', result))
        else:
            result_queue.append((f"{cliente}-{sede}", 'error', {'error': action[1]}))
            logger.error(cliente, sede, "Failure", f"⚠️ No result from portal robot for task {cliente}")
    except Exception as e:
        logger.error(cliente, sede, "Failure", f"⚠️ Error in portal robot for task {cliente} : {e}")
        result_queue.append((f"{cliente}-{sede}", 'error', {'error': str(e)}))

def run_certificate_handler_static(logger : LoggerV2, cliente: str, sede: str, sede_id: str, recipient:str, execution_id:str,  result_queue: List):
    certificate_manager = CertificateManager(
        cliente = cliente,
        task_id = sede,
        sede = sede,
        date = date,
        module="Altas",
        execution_id=execution_id,
        filename=f"altas"
    )
    try:
        logger.info(cliente, sede_id, "Pending", f"Starting certificate handler for task {sede_id}")
        result = certificate_manager.handle_certificate(recipient)
        if result:
            logger.info(cliente, sede_id, "Success", f"Certificate handler for task {sede_id} completed with result: {result}")
            result_queue.append((sede_id, 'certificate_handled', result))
        else:
            logger.error(cliente, sede_id, "Failure", f"Certificate handler for task {sede_id} failed. Retrying...")
            result_queue.append((sede_id, 'certificate_handled', False))
    except Exception as e:
        logger.error(cliente, sede_id, "Failure", f"⚠️ Error in certificate handler for task {sede_id}: {e}")
        result_queue.append((sede_id, 'certificate_handled', False))
    

def log_listener(queue:Queue, date:str, execution_id:str):
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
                    filename=f"altas",
                    log_dir=r"logs\altas",
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
            default_logger = LoggerV2(execution_id=execution_id, module="Altas", class_name="LogListener", log_dir=r"logs\altas",)
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")
                  
class RobotAltas:
    """
    Main class to manage the execution of multiple robots in parallel
    """
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

    def __init__(self, execution_id: str, db_path: str = "robots.db"):
        self.db_path = db_path
        self.tasks = []
        self.results = {}
        self.lock = None  # Si usas threading, puedes inicializar un Lock
        self.default_date = date

        # Progreso 
        self.total_tasks = 0
        self.completed_tasks = 0
        self.progress = 0.0
        self.progress_by_task = {}  # (cliente, sede): porcentaje

        # Initialize logger
        self.execution_id = execution_id
        self.logger = LoggerV2(
            execution_id=self.execution_id,
            module="Altas",
            class_name=self.__class__.__name__,
            log_dir="logs/altas",
            filename=f"altas"
        )

        # Managers
        self.database_manager = AltasDatabase(
            db_config=self.db_config, 
            date = self.default_date,  
            execution_id=self.execution_id,
            module="Altas",
            filename=f"altas"
        )

        self.redtrust_manager = None  
        self.certificate_manager = None 
        self.robot = None  # Inicializar más tarde

    def calcular_total_tasks(self, tasks):
        total = 0
        for cliente, info in tasks.items():
            total += len(info["sedes"])
        self.total_tasks = total
        self.logger.info("GLOBAL", "RUN", "Info", f"Total de tareas a ejecutar: {self.total_tasks}")

    def actualizar_progreso_fase(self, fase: str, extra: str = ""):
        fases_pesos = {
            'db_fetch': 10,
            'estructuracion': 5,
            'asignacion_certificados': 5,
            'carga_certificados': 10,
            'ejecucion_tarea': 70,
            'finalizado': 0,  # <-- Add this line
        }
        if not hasattr(self, '_progreso_fases'):
            self._progreso_fases = {k: False for k in fases_pesos}
            self._progreso_base = 0
            self._progreso_tarea_unit = 0
        if fase != 'ejecucion_tarea' and not self._progreso_fases[fase]:
            self._progreso_base += fases_pesos[fase]
            # Set progress to 100% if finalizado
            if fase == 'finalizado':
                self.progress = 100.0
            else:
                self.progress = self._progreso_base
            self._progreso_fases[fase] = True
            self.logger.info("GLOBAL", "RUN", "Info", f"Progreso: {self.progress:.2f}% - Fase completada: {fase}. {extra}")
        elif fase == 'ejecucion_tarea':
            self.completed_tasks += 1
            if self.total_tasks > 0:
                self._progreso_tarea_unit = fases_pesos['ejecucion_tarea'] / self.total_tasks
            else:
                self._progreso_tarea_unit = 0
            self.progress = self._progreso_base + self.completed_tasks * self._progreso_tarea_unit
            self.logger.info("GLOBAL", "RUN", "Info", f"Progreso: {self.progress:.2f}% - Ejecutada tarea {self.completed_tasks} de {self.total_tasks}. {extra}")

    def _load_certificate(self, certificate_id: str) -> bool:
        try:
            if self.redtrust_manager is None:
                credentials = {
                    "usuario": os.getenv("USUARIO"),
                    "password": os.getenv("PASSWORD")
                }
                self.redtrust_manager = RedTrustManager(
                    cliente = certificate_id,
                    execution_id=self.execution_id,                  
                    credentials=credentials, 
                    date = self.default_date,  
                    module="Altas",
                    filename=f"altas"
                )
            success = self.redtrust_manager.automate_redtrust(certificate_id)
            if success:
                self.logger.info(certificate_id, "CERTIFICATE", "Success", f"Certificate {certificate_id} loaded successfully")
            else:
                self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRedtrust.CertificateLoad(certificate_id))
            return success
        except Exception as e:
            self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRedtrust.CertificateLoad(certificate_id))
            return False

    ''' Altas with robots'''
    def subscribe_sedes(self, cliente: Optional[str] = None, sedes: Optional[list] = None, limit: Optional[int] = 10):
        altas = self.database_manager.fetch_altas(
            sedes=sedes,
            cliente=cliente,
            limit=limit
        )
        self.actualizar_progreso_fase('db_fetch', 'Consultando tareas en base de datos...')
        if not altas:
            self.logger.info("GLOBAL", "RUN", "Info", "No pending altas found")
            return
        try:
            network_path = os.getenv("NETWORK_PATH")
            debug_dir = os.path.join(
            network_path,
                "Documents", "workspace", "redtrust-automation", "files", "altas_debug_files"
            )
            
            os.makedirs(debug_dir, exist_ok=True)
            debug_file = os.path.join(debug_dir, "structured_altas.json")
            with open(debug_file, "w", encoding="utf-8") as f:
                json.dump(altas, f, ensure_ascii=False, indent=4, default=str)

            self.actualizar_progreso_fase('estructuracion', 'Estructurando datos y generando JSON de debug...')
        except Exception as e:
            self.logger.error("GLOBAL", "RUN", "Failure", f"⚠️ Error dumping structured notifications to JSON: {e}")

        cert_ids = [info["certificate_id"] for info in altas.values() if "certificate_id" in info]
        self.database_manager.assign_certificates(cert_ids, "Adría Martínez")
        for client_id, alta in altas.items():
            cliente_name = alta.get("name") or str(client_id)
            for sede in alta.get("sedes", []):
                self.database_manager.insert_assignment_log(
                    id_value=f"alta_{client_id}_{sede.get('sede')}",
                    cliente=cliente_name,
                    sede=sede.get("sede"),
                    robot_name="RobotAltas",
                    assigned_by="Adrià Martínez"
                )
        self.actualizar_progreso_fase('asignacion_certificados', 'Asignando certificados a usuarios...')

        # Calcular total de tareas para el reparto de progreso
        self.calcular_total_tasks(altas)
        
        # Procesar cada grupo de tareas con el mismo certificado
        for client_id, cert_tasks in altas.items():
            if cliente and str(client_id) != str(cliente):
                continue
            self.logger.info(client_id, "RUN", "Info", f"Processing tasks for certificate {client_id}")
            if not self._load_certificate(str(client_id)):
                self.logger.error(client_id, "RUN", "Failure", f"⚠️ Failed to load certificate {client_id}")
                self.actualizar_progreso_fase('carga_certificados', f'Cargando certificado {client_id}...')
                continue
            self._subscribe_sedes_with_certificate(client_id, cert_tasks, cert_tasks['sedes'], sedes=sedes)

    def _subscribe_sedes_with_certificate(self, cliente: str, cliente_info: Dict[str, Any], altas: List[Dict[str, Any]], sedes: Optional[list] = None):   
        provincia = cliente_info.get("provincia", "")
        name = cliente_info.get("name", "") if cliente_info.get("name") else cliente_info.get("recipient_name", "")
        tipo_cliente = cliente_info.get("tipo_cliente", "")
        cif = cliente_info.get("CIF", "")
        nif = cliente_info.get("NIF", "")
        recipient = cliente_info.get("recipient_name", "")
        manager_name = cliente_info.get("manager", None)

        try:
            log_queue = Queue()
            listener = Process(target=log_listener, args=(log_queue,self.default_date, str(self.execution_id)))
            listener.start()

            # Start portal robot and certificate handler processes for each task
            with Manager() as manager:
                result_queue = manager.list()  # Shared list for inter-process communication
                for alta in altas:
                    sede = alta["sede"]
                    if sedes and sede not in sedes:
                        self.actualizar_progreso_fase('ejecucion_tarea', f'Cliente={cliente}, Sede={sede}')
                        continue

                    execution_record = HistoricoAutomatizaciones(
                        execution_id=uuid4(),
                        cliente=cliente,
                        nif=nif,
                        cif=cif,
                        tipo_cliente=tipo_cliente,
                        robot_name="RobotAltas",
                        status="pending",
                        sede=sede,
                        result_robot=None,
                        result_certificate=None,
                        execution_message=f"Ejecución iniciada para cliente {cliente} en sede {sede}",
                        updated_by_user_id=78,
                        updated_by_user_name="Adría Martínez",
                        created_at=datetime.now(),
                        updated_at=None,                    
                    )

                    self.database_manager.insert_historico(execution_record)

                    processes = []
                    
                    # Define the mapping of sede to robot class once
                    robot_class_map = {
                        'andalucía': RobotAndalucia,
                        'asturias': RobotAsturias,
                        'badajoz': RobotBadajoz,
                        'baleares': RobotAtib,
                        'mahon': None,
                        'burgos': RobotBurgos,
                        'castilla la mancha': RobotCastillaLaMancha,
                        'castilla y león': RobotCastillaLeon,
                        'ceuta': RobotCeuta,
                        'comunidad valenciana': RobotComunidadValenciana,
                        'la rioja': RobotLaRioja,
                        'madrid': RobotMadrid,
                        'melilla': RobotMelilla,
                        'pais vasco': RobotPaisVasco,
                        'enotum': RobotEnotum,
                        'dev': RobotDGT,
                        'dehù': RobotDehu,
                        'xaloc': RobotXaloc,
                        'oficina virtual ayuntamiento terrassa': RobotTerrassa,
                        'agencia tributaria de catalunya': RobotAtc,
                        'migjorn gran': RobotMigjornGran,
                        'ayuntamiento de málaga': RobotAyuntamientoMalaga,
                    }

                    # Define exclusion rules by provincia
                    exclude_by_provincia = {
                        'barcelona': ['baleares', 'mahon'],
                        'girona': ['baleares', 'mahon'],
                        'lleida': ['baleares', 'mahon'],
                        'tarragona': ['baleares', 'mahon'],
                        'islas baleares': ['xaloc', 'oficina virtual ayuntamiento terrassa'],
                    }
                    # Default exclusions for other provincias
                    default_exclude = ['baleares', 'mahon', 'xaloc', 'oficina virtual ayuntamiento terrassa']

                    # If provincia is falsy, skip this alta
                    if not provincia:
                        continue
                    # Get exclusions for current provincia
                    exclusions = exclude_by_provincia.get(str(provincia).lower(), default_exclude)
                    if sede in exclusions:
                        continue

                    robot_class = robot_class_map.get(sede)

                    if not robot_class:
                        self.logger.error(cliente, sede, "Failure", f"⚠️ Unknown or unsupported sede for downloads: {sede}")
                        continue

                    # Initialize the robot class
                    robot_instance = robot_class(
                        mail=alta.get("emails", ""),
                        portal_link=alta.get("link", ""),
                        sede=sede,
                        n_mails=alta.get("n_emails", 0),
                        date=date,
                        cliente=cliente,   
                        log_queue=log_queue, 
                        execution_id=self.execution_id
                    )

                    direccion = {
                        "pais": "Espanya",
                        "calle": cliente_info.get("calle", ""),
                        "poblacion": cliente_info.get("poblacion", ""),
                        "codigo_postal": cliente_info.get("codigo_postal", ""),
                        "provincia": str(provincia).lower(),
                    }

                    # Create portal robot process
                    portal_process = Process(
                        target=run_portal_robot_static,
                        args=(self.logger, robot_instance, cliente, manager_name, name, direccion, tipo_cliente, cif, nif, sede, result_queue),
                        name=f"portal-{cliente}-{sede}"
                    )
                    processes.append(portal_process)
                    portal_process.start()

                    # Create certificate handler process
                    cert_process = Process(
                        target=run_certificate_handler_static,
                        args=(self.logger, cliente, sede, alta.get("sede_id"), recipient, self.execution_id, result_queue),
                        name=f"cert-{cliente}-{sede}"
                    )
                    processes.append(cert_process)
                    cert_process.start()

                    # Wait for the portal robot process to complete
                    portal_process.join()
                    # If portal_process finished, terminate cert_process if it's still running
                    
                    if cert_process.is_alive():
                        cert_process.terminate()
                        self.logger.info(cliente, sede, "Info", f"Certificate process for {cliente}-{sede} terminated as portal process finished.")

                    cert_process.join()

                    # Only process results if result_queue is not empty
                    if not result_queue:
                        self.logger.warning(cliente, sede, "Info", f"No results found for task {cliente}-{sede}. Skipping result processing.")
                        execution_record.execution_message = f"No results found for task {cliente}-{sede}."
                        execution_record.status = 'error'
                        execution_record.result_robot = None
                        execution_record.result_certificate = None

                    alta_record = None
                    # Process results
                    for result in result_queue:   
                        self.logger.info(cliente, sede, "Info", f"Processing result for task {result}")                                             
                        alta_id, status, resultado = result
                        execution_record.result_robot = str(resultado)
                        email = alta.get("emails")

                        if status == 'completed':
                            execution_record.status = status
                            if sede in ['agencia tributaria de catalunya', 'oficina virtual ayuntamiento terrassa', 'madrid', 'castilla la mancha', 'ayuntamiento de málaga']:
                                _, action, email_found = resultado                                
                            else:
                                email_found = None
                                _, action = resultado

                            self.logger.info(cliente, sede, "Success", f"Task {alta_id} completed successfully with data: {resultado}")
                            action_id, action_message = action
                            execution_record.result_robot = None

                            # Always set a default non-None execution_message
                            execution_record.execution_message = f"Alta realizada correctamente para {cliente} en sede {sede}, action: {action_message}"

                            if action_id == 0:
                                self.logger.error(cliente, sede, "Failure", f"Error in task {alta_id}: {action_message}")
                                execution_record.execution_message = f"Error in task {alta_id}: {action_message}"
                                continue
                            elif action_id == -1:
                                self.database_manager.update_certificate_alert(cliente_info.get('certificate_id'), cliente, 5, f"Llamar al cliente para modificar el mail del cliente en sede {sede}", "Adría Martínez")
                                self.logger.error(cliente, sede, "Failure", f"Llamar al cliente: Error para {cliente} in task {alta_id}: {action_message}")
                                execution_record.execution_message = f"Llamar al cliente: Error para {cliente} in task {alta_id}: {action_message}"
                            else:
                                self.logger.info(cliente, sede, "Info", f"Action ID: {action_id}, Action Message: {action_message}")

                                alta_record = AltasAutomatizaciones(
                                    id=uuid4(),
                                    execution_id=execution_record.execution_id,
                                    action=action_message,
                                    emails=(str(email).lower() if email else None),
                                    downloads=(True if action_id and action_id > 0 else False),
                                    notes=(f"Email encontrado: {email_found}" if email_found else None),
                                    created_at=datetime.now(),
                                    updated_at=None,
                                )

                                execution_record.execution_message = f"Alta realizada correctamente para {cliente} con action_id {action_id} en sede {sede}"
                                if action_id == 8:
                                    self.database_manager.update_alta_status(cliente_info.get('certificate_id'), action_id, None, 'Adría Martínez', sede, email_found, cliente)
                                else:
                                    self.database_manager.update_alta_status(cliente_info.get('certificate_id'), action_id, str(email).lower(), 'Adría Martínez', sede, email_found, cliente)

                        elif status == 'certificate_handled':
                            self.logger.info(cliente, sede, "Success", f"Certificate handled for task {alta_id} with data: {resultado}")
                            execution_record.result_certificate=resultado
                        
                        elif status == 'error':
                            execution_record.status = status
                            self.logger.error(cliente, sede, "Failure", f"Task {alta_id} encountered an error: {resultado.get('error', '')}")
                            execution_record.execution_message=f"Error in task {alta_id}: {resultado.get('error', '')}"

                        else:
                            self.logger.error(cliente, sede, "Failure", f"Unknown status for task {alta_id}: {status}")
                            execution_record.execution_message=f"Unknown status for task {alta_id}: {status}"
                    
                    
                    self.database_manager.update_historico_alta(
                        record=execution_record,
                        alta_record=alta_record
                    )
                    result_queue[:] = []
                    self.actualizar_progreso_fase('ejecucion_tarea', f'Cliente={cliente}, Sede={sede}')
        
                self.database_manager.unassign_certificate(cliente_info.get("certificate_id"), "Adría Martínez")

            # Signal the log_listener to exit and wait for it to finish
            log_queue.put(None)
            listener.join()

        except Exception as e:
            self.logger.error(cliente, None, "Failure", f"⚠️ Error in _subscribe_sedes_with_certificate: {e}")
            raise


    '''Main execution'''
    def run(self, cliente: Optional[str] = None, sedes: Optional[list] = None, limit: Optional[int] = 10):
        """Main method to run the robot manager"""
        start_time = time.time()
        self.logger.info("GLOBAL", "RUN", "Pending", f"Starting Robot Altas Manager with args: sedes {sedes}, cliente {cliente} for execution_id: " + self.execution_id)
        try:
            self.subscribe_sedes(cliente=cliente, sedes=sedes, limit=limit)
            elapsed_time = time.time() - start_time
            self.actualizar_progreso_fase('finalizado', 'Proceso completado')
            self.logger.info("GLOBAL", "RUN", "Success", f"✅ Robot Manager execution completed in {elapsed_time:.2f} seconds")
        except Exception as e:
            self.logger.error("GLOBAL", "RUN", "Failure", f"⚠️ Error in Robot Manager: {e}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RobotAltas Manager")
    parser.add_argument('--sedes', nargs='+', default=[
        'andalucía', 
        'asturias', 
        'badajoz', 
        # 'baleares', 
        'burgos', 
        'castilla la mancha', 
        'castilla y león',
        'ceuta', 
        'comunidad valenciana', 
        'la rioja', 
        'melilla',
        'mahon', 
        'madrid',
        'pais vasco', 
        'enotum', 
        'dev', 
        'dehù',
        'xaloc', 
        # 'oficina virtual ayuntamiento terrassa', 
        'agencia tributaria de catalunya',
        'migjorn gran',
        'ayuntamiento de málaga'
    ], help='Listado de sedes a procesar (por defecto todas las soportadas)')
    parser.add_argument('--cliente', type=str, default=None, help='ID del cliente a procesar (por defecto todos los pendientes)')
    args = parser.parse_args()

    execution_id = str(uuid4())
    manager = RobotAltas(execution_id=execution_id)
    manager.run(cliente=args.cliente, sedes=args.sedes)
