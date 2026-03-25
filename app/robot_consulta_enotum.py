import logging
import os, sys, time, json
from typing import Dict, List, Any, Optional, Tuple
from uuid import uuid4
from datetime import datetime

from app.robot.descargas.robotDehu import RobotDehu

# Ensure the parent directory is in sys.path for 'app' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# THIRD PARTY PACKAGES
from dotenv import load_dotenv
from multiprocessing import Process, Manager, Queue

# PERSONAL PACKAGES - ROBOTS
from app.robot.consultas.robotEnotum import RobotEnotum

# PERSONAL PACKAGES - MANAGERS
from app.redtrust.redtrust_manager import RedTrustManager
from database.consultas.database_consultas import ConsultasDatabase
from app.robot.handle_certificate import CertificateManager
from app.models.mailExtractionModel import ExtractionResponse

# PERSONAL PACKAGES - UTILS
from app.models.database_models import HistoricoAutomatizaciones, ConsultaAutomatizaciones, DescargaConsulta
from app.utils.utils import random_wait, CONSULTA_RESULTS
from app.helper.loggerV2 import LoggerV2
from app.helper.errors.robot_consulta_enotum import ErrorRobotConsultaEnotum
from app.models.descarga_result import DescargaResult   
from app.models.notificacion import Descarga, Notificacion

def log_listener(queue:Queue, date:str,  execution_id: str):
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
                    filename=f"descargas_{date}",
                    log_dir=r"logs\descargas",
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
            default_logger = LoggerV2(execution_id = execution_id, module="ConsultaEnotum", class_name="LogListener", log_dir=r"logs\consultaenotum")
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

def run_portal_robot_static(
    cliente: str,
    sede: str,
    logger: LoggerV2,
    robot_class: RobotEnotum | None,
    task_data: Dict[str, Any],
    result_queue: Any
):
    """Función estática para ejecutar el robot del portal en un proceso separado."""
    try:
        robot = robot_class
        if robot is None:
            logger.error(cliente, f"portal-{sede}-{cliente}", "Failure", f"Robot class for sede {sede} is not initialized.")
            return

        logger.info(cliente, f"portal-{sede}-{cliente}", "Pending", f"Starting portal robot for sede {sede} and client {cliente}")

        # Ejecutar el método principal del robot con los datos de la tarea
        status, result, agencia_tributaria = robot.consultaNotifications(
            cliente_data = task_data['cliente_data'],
            notificaciones = task_data['notificaciones'],
            fecha_revision = task_data['fecha_revision'],
            descargaespecial = task_data.get('descargaespecial', None)
        )
        logger.info(cliente, f"portal-{sede}-{cliente}", "Success", f"Portal robot for sede {sede} and client {cliente} completed successfully.")

        if status == "Failure":
            if result is None or result == {}:
                logger.error(cliente, f"portal-{sede}-{cliente}", "Failure", ErrorRobotConsultaEnotum.NoResult(f"portal-{sede}-{cliente}"))
                result_queue.append((f"portal-{sede}-{cliente}", 'error', 'No result returned'))
            else:
                logger.error(cliente, f"portal-{sede}-{cliente}", "Failure", ErrorRobotConsultaEnotum.Error(f"portal-{sede}-{cliente}"))
                result_queue.append((f"portal-{sede}-{cliente}", 'error', result))
        elif status == "Success":
            if result is None or (result == {} and (agencia_tributaria == {} or agencia_tributaria is None)):
                logger.info(cliente, f"portal-{sede}-{cliente}", "Success", ErrorRobotConsultaEnotum.NoNotifications(f"portal-{sede}-{cliente}"))
                result_queue.append((f"portal-{sede}-{cliente}", 'completed', ErrorRobotConsultaEnotum.NoNotifications(f"portal-{sede}-{cliente}")))
            else:
                logger.info(cliente, f"portal-{sede}-{cliente}", "Success", f"Portal robot for sede {sede} returned results for {len(result)} tasks.")
                # Build a list of descarga_result dicts for all items returned by the robot
                descarga_results_list = []
                for _, descarga_result in result.items():
                    for descarga in descarga_result:
                        descarga_result_dict = descarga.to_dict() if hasattr(descarga, "to_dict") else dict(descarga)

                        descarga_results_list.append(descarga_result_dict)

                # Use a single task key for the batch and include agencia_tributaria returned by the robot
                result_queue.append((
                    f"portal-{sede}-{cliente}",
                    'completed',
                    {"descarga_result": descarga_results_list, "agencia_tributaria": agencia_tributaria}
                ))
        elif status == "LoginError":
            logger.error(cliente, f"portal-{sede}-{cliente}", "Failure", ErrorRobotConsultaEnotum.LoginError(sede, "Login error occurred"))
            result_queue.append((f"portal-{sede}-{cliente}", 'error', 'Login error occurred'))
 

    except Exception as e:
        logger.error(cliente, f"portal-{sede}-{cliente}", "Failure", f"An error occurred in portal robot for sede {sede} and client {cliente}: {e}")

def run_certificate_handler_static(logger : LoggerV2, date: str, notification : Dict[str, Any], execution_id: str, result_queue: List):
    """Static method to run the certificate handler for a task"""
    cliente = notification.get('cliente', 'UnknownClient')
    sede = notification.get('sede', '').lower()
    recipient_name = notification.get('recipient_name')
    message_key = notification.get('message_key', None)

    certificate_manager = CertificateManager(
        cliente = cliente,
        task_id = message_key,
        sede = sede,
        date = date,
        module="ConsultaEnotum",
        execution_id=execution_id,
        filename=f"consultaenotum",
    )

    if (sede == 'enotum'):
        random_wait(wait_type='X_LONG', wait=True)
    else:
        random_wait(wait_type='LONG', wait=True)

    try:
        result = certificate_manager.handle_certificate(recipient_name)

        if result:
            logger.info(cliente, message_key, "Success", f"Certificate handler for task {message_key} completed successfully.")
            result_queue.append((message_key, 'certificate_handled', result))
    
        else:
            logger.error(f"Certificate handler for task {message_key} failed. Retrying...")
            result_queue.append((message_key, 'certificate_handled', False))
    except Exception as e:
        logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.CertificateHandlerError(message_key))
        result_queue.append((message_key, 'certificate_handled', False))
    

class RobotConsultaEnotum:
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

    def __init__(self, execution_id: str, fecha_a_revisar: Optional[str] = None):
        if fecha_a_revisar:
            self.default_date = fecha_a_revisar.replace("-", "")
        else:
            self.default_date = datetime.now().strftime("%Y%m%d")

        self.execution_id = execution_id
        # Managers
        self.database_manager = ConsultasDatabase(
            db_config=self.db_config, 
            date = self.default_date,  
            module="ConsultaEnotum",
            filename=f"consultaenotum",
            execution_id=self.execution_id
        )
        
        self.redtrust_manager = None  

        # Inicializa el logger
        self.logger = LoggerV2(
            execution_id=self.execution_id,
            module="ConsultaEnotum",
            class_name=self.__class__.__name__,
            log_dir="logs/consultaenotum",
            filename=f"consultaenotum"
        )

        # Progreso
        self.total_tasks = 0
        self.completed_tasks = 0
        self.progress = 0.0
        self.progress_by_task = {} 
    
    def calcular_total_tasks(self, tasks):
        """Calcula el total de tareas (cliente-sede) para el progreso."""
        total = sum(
            len(notificaciones_por_sede)
            for descarga in tasks.values()
            for notificaciones_por_sede in descarga['notificaciones'].values()
        )
        self.total_tasks = total

    def actualizar_progreso_fase(self, cliente:str, task_id:str, fase: str, extra: str = ""):
        """
        Actualiza el progreso según la fase global del proceso y lo loguea.
        Fases: db_fetch, estructuracion, asignacion_certificados, carga_certificados, ejecucion_tarea
        """
        fases_pesos = {
            'db_fetch': 10,
            'estructuracion': 5,
            'asignacion_certificados': 5,
            'carga_certificados': 10,
            'ejecucion_tarea': 70, 
        }

        log_cliente = cliente if cliente is not None else "GLOBAL"
        log_task_id = task_id if task_id is not None else "PROGRESO"
        
        if not hasattr(self, '_progreso_fases'):
            self._progreso_fases = {k: False for k in fases_pesos}
            self._progreso_base = 0
            self._progreso_tarea_unit = 0
        if fase != 'ejecucion_tarea' and not self._progreso_fases[fase]:
            self._progreso_base += fases_pesos[fase]
            self.progress = self._progreso_base
            self._progreso_fases[fase] = True
            self.logger.info(log_cliente, log_task_id, "Pending", f"Progreso: {self.progress:.2f}% - Fase {fase} completada. {extra}")
        elif fase == 'ejecucion_tarea':
            # Se suma el porcentaje correspondiente a una tarea
            self.completed_tasks += 1
            if self.total_tasks > 0:
                self._progreso_tarea_unit = fases_pesos['ejecucion_tarea'] / self.total_tasks
            else:
                self._progreso_tarea_unit = 0
            self.progress = self._progreso_base + self.completed_tasks * self._progreso_tarea_unit
            
            self.logger.info(log_cliente, log_task_id, "Pending", f"Progreso: {self.progress:.2f}% - Fase de ejecución de tareas. Tarea completada: {self.completed_tasks}/{self.total_tasks}. {extra}")

    ''' Pre-procesing and filtering'''
    def structure_and_filter_notifications(self, cliente: str, fecha_revision: str, notificaciones: List[Dict[str, Any]]) -> List[Tuple[Notificacion, bool]]:
        """
        Estructura las notificaciones al modelo Notificacion y filtra según reglas:
        - Si status == 'Agencia Tributaria', comprobar que hay 9 o más días de diferencia con hoy.
        - Si no cumple, añadir campo descargar=False, si cumple o no es AT, descargar=True.
        - Devuelve lista de tuplas (Notificacion, descargar).
        """
        log_queue = Queue()
        listener = Process(target=log_listener, args=(log_queue,self.default_date, str(self.execution_id)))
        listener.start()

        structured = {}
        today = datetime.now().date()
        for notif in notificaciones:
            # Parse date
            notif_date = notif.get('date')
            message_key = notif.get('message_key')
            if isinstance(notif_date, str):
                try:
                    notif_date_dt = datetime.fromisoformat(notif_date)
                except Exception:
                    try:
                        notif_date_dt = datetime.strptime(notif_date, "%Y-%m-%d %H:%M:%S")
                    except Exception:
                        notif_date_dt = today
            elif isinstance(notif_date, datetime):
                notif_date_dt = notif_date
            else:
                notif_date_dt = today

            descargar = True
            if notif.get('status') == 'Agencia Tributaria':
                days_diff = (today - notif_date_dt.date()).days
                if days_diff < 9:
                    descargar = False
            elif notif.get('status') == 'Descargado':
                descargar = False

            if not notif.get("servicio"):
                self.logger.warning(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.MissingServicio(message_key))
                continue

            parsed_mail = self.extract_and_validate_service_info(notif, self.default_date, log_queue)
            if not parsed_mail:
                continue

            sede, body, date, services = parsed_mail 

            # Construir el modelo Notificacion usando los datos extraídos de body
            noti_obj = Notificacion(
                message_key=notif.get('message_key'),
                date=notif_date_dt,
                sede=sede,
                status=notif.get('status'),
                mail=notif.get('mail'),
                asunto=notif.get('asunto'),
                expediente=body.get('expediente'),
                org=body.get('org'),
                body_date=body.get('date'),
                identificador=body.get('identificador'),
                link=body.get('link')
            )

            # Agrupa por cliente y sede
            if cliente not in structured:
                structured[cliente] = {
                    "client_id": int(cliente),
                    "servicio": services,
                    "nif": notif.get("nif"),
                    "cif": notif.get("cif"),
                    "notificaciones": [
                        {**dict(noti_obj), 'descargar': descargar, 'sede': sede}
                    ],
                }
            else:
                new_entry = {**dict(noti_obj), 'descargar': descargar, 'sede': sede}
                ident = body.get('identificador') or new_entry.get('identificador')

                if ident:
                    STATUS_PRIORITY = {
                        "Descargado": 3,
                        "Agencia Tributaria": 2,
                        "Pendiente": 1,
                    }

                    def status_score(status):
                        return STATUS_PRIORITY.get(status, 0)

                    for idx, existing in enumerate(structured[cliente]['notificaciones']):
                        if existing.get('identificador') == ident:
                            merged = existing.copy()

                            # --- merge general (prevalece enotum / existing) ---
                            for key, value in new_entry.items():
                                if key in ("status", "descargar"):
                                    continue
                                if merged.get(key) in (None, "", []):
                                    merged[key] = value

                            # --- status: por prioridad ---
                            existing_status = existing.get("status")
                            new_status = new_entry.get("status")

                            if status_score(new_status) > status_score(existing_status):
                                merged["status"] = new_status
                            else:
                                merged["status"] = existing_status

                            # --- descargar: False > True ---
                            if existing.get("descargar") is False or new_entry.get("descargar") is False:
                                merged["descargar"] = False
                            else:
                                merged["descargar"] = True

                            structured[cliente]['notificaciones'][idx] = merged
                            break
                    else:
                        structured[cliente]['notificaciones'].append(new_entry)
                else:
                    structured[cliente]['notificaciones'].append(new_entry)

        return structured
                  
    def extract_and_validate_service_info(self, notification: Dict[str, Any], date: str, log_queue: Queue) -> Optional[dict]:
        """Extract, filter, and validate service information from a parsed email notification."""
        try:
            sede = str(notification['sede']).lower()
            cliente = notification.get('client_id', 'UnknownClient')
            message_key = notification.get('message_key', 'UnknownMessageID')

            robot_type = {
                'dehù': RobotDehu,
                'enotum': RobotEnotum,
            }[sede]

            if robot_type:
                robot = robot_type(
                    cliente=cliente,
                    task_id=message_key,
                    date=date,
                    execution_id=self.execution_id,
                    module="ConsultaEnotum",
                    log_queue= log_queue,
                    db_manager=self.database_manager,
                )
            
        
            else:
                self.logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.UnknownSede(sede))
                return None

            if robot is None:
                self.logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.RobotNotInitialized(sede))
                return None
            
            if not notification.get('servicio'):
                self.logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.MissingServicio(message_key))
                return None
            
            self.logger.debug(cliente, message_key, "Pending", f"Extracting service info for notification {message_key} in sede {sede}")

            def parse_valid_services(task):
                """Parse and return a list of valid services based on the task's date."""
                valid_services = []
                task_date = datetime.fromisoformat(str(task['date']))
                for service, expiry_date in task.items():
                    if service in ["SUSCRIPCION", "NEOCASH", "NEOESTATAL", "MULTINEO", "INFONEO", "BLINDAJE"]:
                        if expiry_date:
                            expiry_date_obj = datetime.fromisoformat(str(expiry_date))
                            if expiry_date_obj >= task_date:
                                valid_services.append(service)
                return valid_services
            
            valid_services = parse_valid_services(notification)
            # If both 'SUSCRIPCION' and 'INFONEO' are in valid_services, replace them with 'MULTINEO' if not already present
            if 'SUSCRIPCION' in valid_services and 'INFONEO' in valid_services:
                if 'MULTINEO' not in valid_services:
                    valid_services = [s for s in valid_services if s not in ('SUSCRIPCION', 'INFONEO')]
                    valid_services.append('MULTINEO')

            if not valid_services or len(valid_services) == 0:
                self.logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.InvalidServicio(message_key))
                return None

            # Extract body using the validated servicio
            body: ExtractionResponse = robot.extract_from_body(notification['body_html'], valid_services)

            if body is None or not body.to_dict():
                self.logger.error(cliente, message_key, "Failure", f"Error extracting body from notification {message_key} for sede {sede}")
                return None

            # Ensure expediente is not None or 'None'
            if sede in ['enotum', 'dehu'] and (body.expediente is None or body.expediente == 'None'):
                self.logger.warning(cliente, message_key, "Pending", ErrorRobotConsultaEnotum.MissingExpediente(message_key))
            elif sede in ['dgt', 'dev'] and (body.identificador is None or body.identificador == 'None'):
                self.logger.warning(cliente, message_key, "Pending", ErrorRobotConsultaEnotum.MissingExpediente(message_key))
            
            # Return parsed information
            return sede, body.to_dict(), notification['date'], valid_services
        except KeyError as e:
            self.logger.error(cliente, message_key, "Failure", ErrorRobotConsultaEnotum.MissingKey(e))
            return None

    ''' Related to RedTrust'''
    def _load_certificate(self, certificate_id: str) -> bool:
        """Load certificate using RedTrust."""
        try:
            # Initialize RedTrustManager if not already initialized
            if self.redtrust_manager is None:
                credentials = {
                    "usuario": os.getenv("USUARIO"),
                    "password": os.getenv("PASSWORD")
                }
                self.redtrust_manager = RedTrustManager(
                    cliente = certificate_id,
                    execution_id=self.execution_id,                    
                    credentials=credentials , 
                    date = self.default_date,  
                    module="ConsultaEnotum",
                    filename=f"consultaenotum"
                )

            success = self.redtrust_manager.automate_redtrust(str(certificate_id))
            if success:
                self.logger.info(certificate_id, "CERTIFICATE", "Success", f"Certificate {certificate_id} loaded successfully.")
            else:
                self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRobotConsultaEnotum.CertificateLoad(certificate_id))
            return success
        except Exception as e:
            self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRobotConsultaEnotum.CertificateLoad(certificate_id))
            return False

    def consultar_sede(self, idConsulta: str | int, cliente: str, cliente_data: Dict, notificaciones: List[Tuple[Notificacion, bool]], fecha_revision: str, sede: str = 'enotum', descargaespecial:str = None, ):
        """
        Procesa las notificaciones para un cliente y ejecuta el robot Enotum para aquellas marcadas para descargar.
        """       
        message_id = f'consulta_{idConsulta}'
        execution_record = HistoricoAutomatizaciones(
            execution_id=uuid4(),
            cliente=cliente,
            nif=cliente_data['nif'],
            cif=cliente_data['cif'],
            tipo_cliente=cliente_data['tipo_cliente'],
            robot_name="RobotConsulta",
            status="pending",
            sede=sede,
            result_robot=None,
            result_certificate=None,
            execution_message=f"Ejecución iniciada para cliente {cliente} notificación {message_id} en sede {sede}",
            updated_by_user_id=78,
            updated_by_user_name="Adría Martínez",            
            created_at=datetime.now(),
            updated_at=None
        )

        self.database_manager.insert_historico(execution_record)
        
        try:
            log_queue = Queue()
            listener = Process(target=log_listener, args=(log_queue,self.default_date, str(self.execution_id)))
            listener.start()
            
            with Manager() as manager:
                result_queue = manager.list()  # Shared list for inter-process communication

                robot_logger = LoggerV2(
                    execution_id=self.execution_id,
                    module="ConsultaEnotum",
                    class_name=f"Robot{sede.capitalize()}",
                    log_dir="logs/consultaenotum",
                    filename=None,
                    log_queue=log_queue
                )
                robot_class = {
                    'enotum': RobotEnotum,                    
                }[sede](
                    module="ConsultaEnotum",
                    cliente=cliente,
                    task_id=message_id,
                    execution_id=self.execution_id,
                    date=self.default_date,
                    log_queue=log_queue,
                    db_manager=self.database_manager,
                )

                # Ejecutar el portal robot en batch para todas las notificaciones de la sede
                portal_process = Process(
                    target=run_portal_robot_static,
                    args=(
                        cliente,
                        sede,
                        self.logger,
                        robot_class,
                        {
                            'cliente': cliente,
                            'cliente_data': cliente_data,
                            'fecha_revision': fecha_revision,                           
                            'notificaciones': notificaciones,
                            'descargaespecial': descargaespecial
                        },  # Paquete de notificaciones
                        result_queue
                    ),
                    name=f"portal-{sede}-{cliente}"
                )
                portal_process.start()

                # Create and start certificate handler process
                cert_process = Process(
                    target=run_certificate_handler_static,
                    args=(
                        robot_logger,
                        self.default_date,
                        {
                            'cliente': cliente,
                            'sede': sede,
                            'recipient_name': cliente_data['recipient_name'],
                            'message_id': message_id,
                        }, 
                        self.execution_id,
                        result_queue
                    ),
                    name=f"cert-{message_id}"
                )
                cert_process.start()

                portal_process.join()  # Wait for the portal robot process to complete
                cert_process.join() 

                action = None
                notes = None

                consulta_record = None
                descarga_consulta_records: List[DescargaConsulta] = []                

                # Procesar resultados
                for res in result_queue:
                    task_id, result_type, result_data = res
                    if result_type == 'completed':
                        execution_record.status = "completed"
                        execution_record.result_robot = result_data.to_dict() if hasattr(result_data, "to_dict") else str(result_data)
                        action = 0 
                        self.logger.info(cliente, task_id, "Success", f"Portal robot for sede {sede} completed with result: {result_data}")

                        # If result_data contains 'agencia_tributaria', set action accordingly
                        if isinstance(result_data, dict) and "agencia_tributaria" in result_data:
                            if isinstance(result_data["descarga_result"], list):
                                descarga_results = result_data["descarga_result"]
                            else:
                                descarga_results = [result_data["descarga_result"]]
                            
                            if result_data.get("agencia_tributaria"):
                                action = 5
                                for _, atc in result_data.get('agencia_tributaria', {}).items():
                                    # atc should be a dict with 'fecha', but guard against unexpected types
                                    fecha = atc.get('fecha') if isinstance(atc, dict) else None
                                    if fecha:
                                        if notes is None:
                                            notes = f"ATC: {fecha}"
                                        else:
                                            notes += f", {fecha}"
                            elif any(dr.get('file', None) for dr in descarga_results):
                                action = 7
                            else:
                                action = 8
                            
                            if execution_record.status == "completed":
                                if action == 5 and (not descarga_results or len(descarga_results) == 0):
                                    # Tiene agencia_tributaria pero no hay resultados de descarga -> guardar consulta con descarga_data = None
                                    id_consulta = uuid4()
                                    if execution_record.status == "completed":
                                        self.database_manager.update_consulta_enotum(
                                            idconsulta=id_consulta,
                                            cliente=cliente,
                                            nombre_cliente=cliente_data.get('name', None) or cliente_data.get('recipient_name', None),
                                            resultado=action if action is not None else 8,
                                            notas=notes,
                                            descarga_data=None,
                                            sede=sede,
                                        )
                                else:
                                    for descarga_data in descarga_results:
                                        id_consulta = uuid4()
                                        # Convert DescargaResult to dict if needed
                                        if hasattr(descarga_data, "to_dict"):
                                            descarga_data_dict = descarga_data.to_dict()
                                        else:
                                            descarga_data_dict = descarga_data

                                        self.database_manager.update_consulta_enotum(
                                            idconsulta=id_consulta,
                                            cliente=cliente,
                                            nombre_cliente=cliente_data.get('name', None),
                                            resultado=action if action is not None else 8,
                                            notas=notes,
                                            descarga_data=descarga_data_dict,
                                            sede=sede,
                                            fecha_rueda=cliente_data.get('fecha_rueda', None)
                                        )

                                        # Build a DescargaConsulta record from available fields
                                        # Ensure asunto_notificacion does not exceed model limit (50 chars)
                                        _title = descarga_data_dict.get("title")
                                        if _title is not None:
                                            _title = str(_title)
                                            if len(_title) > 50:
                                                _title = _title[:47] + "..."
                                                
                                        descarga_consulta_records.append( 
                                            DescargaConsulta(
                                                id=uuid4(),
                                                id_consulta=id_consulta,
                                                url=descarga_data_dict.get("url"),
                                                id_notificacion=descarga_data_dict.get("identificador"),
                                                asunto_notificacion=_title,
                                                organismo_notificacion=descarga_data_dict.get("org"),
                                                fecha_notificacion=str(descarga_data_dict.get("disposition_date")),
                                                descargada_notificacion=bool(descarga_data_dict.get("desc")),
                                                expediente_notificacion=descarga_data_dict.get("expediente"),
                                                descarga_status=descarga_data_dict.get("status"),
                                                created_at=datetime.now()
                                            )
                                        )
                        else:
                            id_consulta = uuid4()
                            if execution_record.status == "completed":
                                descarga_data = result_data.get('descarga_result', None) if isinstance(result_data, dict) else None
                                self.database_manager.update_consulta_enotum(
                                    idconsulta=id_consulta,
                                    cliente=cliente,
                                    nombre_cliente=cliente_data.get('name', None) or cliente_data.get('recipient_name', None),
                                    resultado=action if action is not None else 8,
                                    notas=notes,
                                    descarga_data=descarga_data,
                                    sede=sede,
                                )
                        
                        consulta_record = ConsultaAutomatizaciones(
                            id = uuid4(),
                            execution_id=execution_record.execution_id,
                            resultado=CONSULTA_RESULTS[action],
                            notas=notes,
                            descarga=True if action == 7 else False,
                            created_at=datetime.now(),
                            updated_at=None
                        )
                                        
                    elif result_type == 'certificate_handled':
                        execution_record.result_certificate = result_data
                        self.logger.info(cliente, task_id, "Success", f"Certificate handler for sede {sede} completed with result: {result_data}")
                    elif result_type == 'error':
                        execution_record.status = "error"
                        execution_record.execution_message = result_data
                        self.logger.error(cliente, task_id, "Failure", f"Error in task {task_id}: {result_data}")
                        if "Login error" in str(result_data):
                            id_consulta = uuid4()
                            self.database_manager.update_consulta_enotum(
                                idconsulta=id_consulta,
                                cliente = cliente,
                                nombre_cliente=cliente_data.get('name', None) or cliente_data.get('recipient_name', None),
                                resultado = 2, 
                                notas= notes,
                                descarga_data=None,
                                sede = sede,
                            )

                            consulta_record = ConsultaAutomatizaciones(
                                id = id_consulta,
                                execution_id=execution_record.execution_id,
                                resultado=CONSULTA_RESULTS[2],
                                notas=notes,
                                descarga=False,
                                created_at=datetime.now(),
                                updated_at=None
                            )

                # Actualizar el histórico con los resultados finales
                self.database_manager.update_historico_consulta(
                    record = execution_record,
                    consulta_record=consulta_record,
                    descarga_consulta_records=descarga_consulta_records
                )                

                self.actualizar_progreso_fase(cliente, message_id, 'ejecucion_tarea', f'Completed processing for sede {sede} and client {cliente}.')
                log_queue.put(None)
                listener.join()

        except Exception as e:
            self.logger.error(cliente, f"consulta_{sede}_{cliente}", "Failure", f"An error occurred while processing sede {sede} for client {cliente}: {e}")
            raise
        
    '''Main execution'''
    def run(self, cliente: Optional[str | int] = None, fecha_a_revisar: Optional[str] = None, limit: Optional[str | int] = 300):
        """Main method to run the robot manager"""
        self.run_absolute_start_time = time.time()  # Variable global de instancia para tiempo absoluto
        self.logger.info("GLOBAL", "RUN", "Info", "Starting Robot Consulta Enotum Manager for execution_id: " + self.execution_id)
        try:
            # 1. BASE DE DATOS: Obtener fecha de última revisión y notificaciones desde la última revisión
            clientes = self.database_manager.consulta_clientes_enotum(
                cliente=cliente,
                date=fecha_a_revisar,
                limit=limit
            )

            for cliente_data in clientes:
                self.database_manager.insert_assignment_log(
                    id_value=f"consulta_{cliente_data['cliente']}_enotum",
                    cliente=cliente_data['cliente'],
                    sede='enotum',
                    robot_name="RobotConsulta",
                )

            self.total_tasks = len(clientes)
            self.completed_tasks = 0

            for cliente_info in clientes:
                cliente = cliente_info['cliente']
                fecha_revision = cliente_info['fecha_revision']
                idConsulta = cliente_info['idConsulta']
                especial = cliente_info.get('especial', None)
                self.actualizar_progreso_fase(cliente, "RUN", "db_fetch", f"Fetched client {cliente} with last review date {fecha_revision}")
                
                # 2.1. BASE DE DATOS: Obtener notificaciones desde la última revisión
                notificaciones = self.database_manager.get_notificaciones_from_date(cliente, fecha_revision)
                self.actualizar_progreso_fase(cliente, "RUN", "db_fetch", f"Fetched {len(notificaciones)} notifications for client {cliente} since {fecha_revision}")
                
                # 2.2. Estructurar y filtrar notificaciones
                if not notificaciones:
                    self.logger.info(cliente, "RUN", "Pending", f"No new notifications for client {cliente} since last review date {fecha_revision}. Skipping.")
                    structured = []
                else:
                    structured = self.structure_and_filter_notifications(cliente, fecha_revision, notificaciones)
                
                self.actualizar_progreso_fase(cliente, "RUN", "estructuracion", f"Structured and filtered notifications for client {cliente}")
   
                self.logger.info(cliente, "RUN", "Pending", f"Processing tasks for certificate {cliente}.")

                # 3. REDTRUST: Cargar certificado
                if not self._load_certificate(cliente):
                    self.actualizar_progreso_fase(cliente, None, 'carga_certificados', f'Cargando certificado {cliente}...')
                    continue

                self.actualizar_progreso_fase(cliente, None, 'carga_certificados', f'Cargando certificado {cliente}...')
                notis = structured.get(cliente, {}).get('notificaciones', []) if structured and structured != [] else []

                # 4. EJECUTAR ROBOT PARA CADA SEDE (solo enotum)
                self.consultar_sede(
                    idConsulta = idConsulta,
                    cliente=cliente, 
                    cliente_data=cliente_info,
                    notificaciones=notis,
                    fecha_revision=fecha_revision,
                    sede='enotum',
                    descargaespecial=especial
                )

            # Final log
            self.progress = 100.0
            absolute_elapsed_time = time.time() - self.run_absolute_start_time
            self.logger.info("GLOBAL", "RUN", "Info", f"Robot Manager ha terminado el ejecucion en {absolute_elapsed_time:.2f} segundos")
        except Exception as e:
            self.logger.error("GLOBAL", "RUN", "Failure", f"An error occurred during execution: {e}")
            raise

if __name__ == "__main__":
    try:
        execution_id = uuid4()

        def log_queue(level: str | int, task_id: str, result: str, message: str) -> None:
            try:
                logger = LoggerV2(execution_id=execution_id, module="ConsultaEnotum", class_name="RobotConsultaEnotum", log_dir="logs", filename="pdf_parser")

                # Mapear nivel de log a método del logger
                log_method = {
                    logging.ERROR: logger.error,
                    logging.WARNING: logger.warning,
                    logging.DEBUG: logger.debug,
                    logging.INFO: logger.info
                }.get(level, logger.info)

                log_method(
                    cliente="ConsultaEnotum",
                    task_id=task_id,
                    result=result,
                    message=message
                )

            except Exception as e:
                default_logger = LoggerV2(execution_id=execution_id, module="ConsultaEnotum", class_name="LogListener", log_dir=r"logs\consultaenotum",)
                default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

        import argparse

        parser = argparse.ArgumentParser(description="RobotConsultaEnotum runner")
        parser.add_argument("--cliente", type=str, help="ID del cliente a procesar", default=None)
        parser.add_argument("--date", type=str, help="Fecha a revisar (YYYY-MM-DD)", default=None)
        args = parser.parse_args()

        

        try:
            fecha_a_revisar = args.date
            if fecha_a_revisar is not None:
                try:
                    # Try to parse and reformat to YYYY-MM-DD
                    fecha_dt = datetime.strptime(fecha_a_revisar, "%Y-%m-%d")
                    fecha_a_revisar = fecha_dt.strftime("%Y-%m-%d")
                except ValueError:
                    print(f"Error: La fecha '{fecha_a_revisar}' no tiene el formato YYYY-MM-DD.")
                    sys.exit(1)

            robot_manager = RobotConsultaEnotum(fecha_a_revisar=fecha_a_revisar, execution_id=str(execution_id))
            robot_manager.run(cliente=args.cliente, fecha_a_revisar=fecha_a_revisar)
        except Exception as e:
            print(f"An error occurred while running the robot manager: {e}")            

    except Exception as e:
        print(f"An error occurred during execution: {e}")
    
    finally:
        # Cierra todos los loggers y handlers para liberar archivos de log
        import logging
        logging.shutdown()
