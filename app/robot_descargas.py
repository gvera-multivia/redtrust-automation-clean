import logging
import os, sys, time, json, argparse
from typing import Dict, List, Any, Optional
from uuid import uuid4
from datetime import datetime

from app.models.descarga_result import DescargaResult
from app.utils.parser.PDFMetadataExtractor import PDFMetadataExtractor  # Ensure this imports the class, not the module
from app.utils.validate_descargas import validate_downloads
from app.helper.errors.robot_descargas import ErrorRobotDescargas


# Ensure the parent directory is in sys.path for 'app' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# THIRD PARTY PACKAGES
from dotenv import load_dotenv
from multiprocessing import Process, Manager, Queue

# PERSONAL PACKAGES - ROBOTS
from app.robot.descargas.robotDgt import RobotDgt
from app.robot.descargas.robotDehu import RobotDehu
from app.robot.descargas.robotEnotum import RobotEnotum

# PERSONAL PACKAGES - MANAGERS
from app.redtrust.redtrust_manager import RedTrustManager
from database.descargas.database_descargas import DescargaDatabase
from app.robot.handle_certificate import CertificateManager
from app.models.mailExtractionModel import ExtractionResponse

# PERSONAL PACKAGES - UTILS
from app.models.database_models import HistoricoAutomatizaciones, DescargasAutomatizaciones
from app.utils.utils import random_wait, DESCARGA_ESPECIAL
from app.helper.loggerV2 import LoggerV2
from app.helper.errors.robot_descargas import ErrorRobotDescargas
from app.models.notificacion import Descarga, Notificacion
from collections import defaultdict

def run_portal_robot_static(cliente: str | int , sede: str, logger: LoggerV2, robot_class: RobotDehu | RobotDgt | RobotEnotum, notifications: Dict[str, Any], result_queue: List):
    """
    Ejecuta el robot de portal para un paquete de notificaciones y devuelve resultados individuales por message_key.
    """
    try:
        logger.info(cliente, sede, "Pending", f"Running portal robot for {notifications} notifications.")
        # Llama al método batch del robot para procesar todas las notificaciones
        results = robot_class.getNotifications(notifications)
        logger.info(cliente, sede, "Success", f"Results from robot_class.getNotifications: {results}")
        
        # Espera que results sea un dict: {message_key: DescargaResult}
        if not isinstance(results, dict) or not results:
            logger.error(cliente, sede, "Failure", f"El resultado del robot debe ser un dict con message_key como clave. Resultado obtenido: {results}")
            for notification in notifications.get('notificaciones', []):
                message_key = notification.get('message_key')
                result_queue.append((message_key, 'error', 'No result returned'))
            return

        for notification in notifications.get('notificaciones', []):
            message_key = notification.get('message_key')
            result_obj = results.get(str(message_key))
            result = result_obj.to_dict() if result_obj and hasattr(result_obj, 'to_dict') else None
            if result is None or result == {}:
                logger.error(notification.get('client_id'), message_key, "Failure", ErrorRobotDescargas.NoResult(message_key))
                result_queue.append((message_key, 'error', 'No result returned'))
            else:
                status = result.get('status')
                if status == DescargaResult.StatusEnum.ERROR or status == DescargaResult.StatusEnum.PENDING:
                    logger.error(notification.get('client_id'), message_key, "Failure", ErrorRobotDescargas.Error(message_key, result.get('message', 'Unknown error')))
                    result_queue.append((message_key, 'error', result))
                elif status == DescargaResult.StatusEnum.SUCCESS:
                    logger.info(notification.get('client_id'), message_key, "Success", f"Portal robot for task {message_key} completed successfully.")
                    result_queue.append((message_key, 'completed', result))
                else:
                    logger.error(notification.get('client_id'), message_key, "Failure", f"Unknown status: {status}")
                    result_queue.append((message_key, 'error', f"Unknown status: {status}"))

    except Exception as e:
        for notification in notifications:
            if isinstance(notification, dict):
                message_key = notification.get('message_key', 'unknown')
                logger.error(notification.get('client_id'), message_key, "Failure", ErrorRobotDescargas.Error(message_key, e))

            elif isinstance(notification, str):
                message_key = notification
                logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.Error(message_key, e))
            else:
                message_key = 'unknown'
            
            result_queue.append((message_key, 'error', str(e)))

def run_certificate_handler_static(logger, date: str, notification : Dict[str, Any],  execution_id: str, result_queue: List):
    """Static method to run the certificate handler for a task"""
    cliente = notification.get('client_id', 'UnknownClient')
    sede = notification.get('sede', '').lower()
    recipient_name = notification.get('recipient_name')
    message_key = notification.get('message_key', None)

    certificate_manager = CertificateManager(
        cliente = cliente,
        task_id = message_key,
        sede = sede,
        date = date,
        module="Descargas",
        execution_id=execution_id,
        filename=f"descargas_{date}"
    )

    if (sede == 'enotum'):
        random_wait(wait_type='X_LONG', wait=True)
    else:
        random_wait(wait_type='LONG', wait=True)

    if sede in ['dev', 'dgt']:
        retry_attempts = 3
    else:
        retry_attempts = 1
    
    for attempt in range(1, retry_attempts + 1):
        try:
            result = certificate_manager.handle_certificate(recipient_name)

            if result:
                logger.info(cliente, message_key, "Success", f"Certificate handler for task {message_key} completed successfully.")
                result_queue.append((message_key, 'certificate_handled', result))
            else:
                logger.error(f"Certificate handler for task {message_key} failed. Retrying...")
                result_queue.append((message_key, 'certificate_handled', False))
        except Exception as e:
            logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.CertificateHandlerError(message_key))
            result_queue.append((message_key, 'certificate_handled', False))
                        
def extract_and_validate_service_info(logger, execution_id: str, notification: Dict[str, Any], date: str, database_manager:DescargaDatabase ,log_queue:Queue) -> Optional[dict]:
    """Extract, filter, and validate service information from a parsed email notification."""
    try:
        sede = notification['sede'].lower()
        cliente = notification.get('client_id', 'UnknownClient')
        message_key = notification.get('message_key', 'UnknownMessageID')
        if sede == 'dehù':
            robot = RobotDehu(
                cliente=cliente,
                task_id=notification.get('message_key', None),
                date=date,
                module="Descargas",
                db_manager=database_manager,
                log_queue= log_queue,
                execution_id=execution_id
            )
        elif sede == 'enotum':
            robot = RobotEnotum(
                cliente=cliente,
                task_id=notification.get('message_key', None),
                date=date,
                module="Descargas",
                db_manager=database_manager,
                log_queue= log_queue,
                execution_id=execution_id                        
            )
        elif sede in ['dev', 'dgt']:
            robot = RobotDgt(
                cliente=cliente,
                task_id=notification.get('message_key', None),
                date=date,
                module="Descargas",
                log_queue= log_queue,
                execution_id=execution_id
            )

        else:
            logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.UnknownSede(sede))
            return None

        if robot is None:
            logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.RobotNotInitialized(sede))
            return None
        
        if not notification.get('servicio'):
            logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.MissingServicio(notification.get('message_key')))
            database_manager.update_notification_status(
                cliente=cliente,
                message_key=message_key, 
                status_id=7
            ) # Actualiza estado a 'Sin servicios'
            return None
        
        # logger.debug(cliente, message_key, "Info", f"Extracting service info for notification {message_key} in sede {sede}")

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
            logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.InvalidServicio(notification=notification))
            return None

        # Extract body using the validated servicio
        body: ExtractionResponse = robot.extract_from_body(notification['body_html'], valid_services)

        if body is None or not body.to_dict():
            logger.error(cliente, message_key, "Failure", f"Error extracting body from notification {message_key} for sede {sede}")
            return None
        
        # Return parsed information
        return sede, body.to_dict(), notification['date'], valid_services
    except KeyError as e:
        logger.error(cliente, message_key, "Failure", ErrorRobotDescargas.MissingKey(e))
        return None

def log_listener(queue:Queue, date:str, execution_id: str):
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
            default_logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="LogListener", log_dir=r"logs\descargas",)
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")


class RobotDescargas:
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

    def __init__(self, date: str, execution_id : str):
        # Execution parameters
        self.default_date = date.replace("-", "")  
        self.default_date_dashes = date
        self.execution_id = execution_id

        # Managers
        self.database_manager = DescargaDatabase(
            db_config=self.db_config, 
            date = self.default_date,  
            module="Descargas",
            filename=f"descargas_{self.default_date}",
            execution_id=self.execution_id
        )
        
        self.redtrust_manager = None  

        # Inicializa el logger
        self.logger = LoggerV2(
            execution_id=self.execution_id,
            module="Descargas",
            class_name=self.__class__.__name__,
            log_dir="logs/descargas",
            filename=f"descargas_{self.default_date}"
        )

        # Progreso
        self.total_tasks = 0
        self.completed_tasks = 0
        self.progress = 0.0
        self.progress_by_task = {}  # (cliente, sede): porcentaje
    
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
            self.logger.info(log_cliente, log_task_id, "Info", f"Progreso: {self.progress:.2f}% - Fase {fase} completada. {extra}")
        elif fase == 'ejecucion_tarea':
            # Se suma el porcentaje correspondiente a una tarea
            self.completed_tasks += 1
            if self.total_tasks > 0:
                self._progreso_tarea_unit = fases_pesos['ejecucion_tarea'] / self.total_tasks
            else:
                self._progreso_tarea_unit = 0
            self.progress = self._progreso_base + self.completed_tasks * self._progreso_tarea_unit
            
            self.logger.info(log_cliente, log_task_id, "Info", f"Progreso: {self.progress:.2f}% - Fase de ejecución de tareas. Tarea completada: {self.completed_tasks}/{self.total_tasks}. {extra}")


    '''Pre-procesing and filtering'''
    def _structure_notifications(self, notifications: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Filter and structure notifications by client_id without duplicating message_key"""
        structured = {}
        seen_message_keys = set()
        log_queue = Queue()
        listener = Process(target=log_listener, args=(log_queue,self.default_date, self.execution_id))
        listener.start()


        for notification in notifications:
            message_key = notification.get("message_key")
            client_id = notification.get("client_id", "UnknownClient")
            aviso_especial = notification.get("aviso_especial", None)

            if message_key in seen_message_keys:
                continue  # Skip duplicates
            seen_message_keys.add(message_key)

            if not notification.get("servicio"):
                self.logger.warning(client_id, message_key, "Failure", ErrorRobotDescargas.MissingServicio(message_key))
                self.database_manager.update_notification_status(
                    cliente=client_id,
                    message_key=message_key, 
                    status_id=7
                ) # Actualiza estado a 'Sin servicios'

                continue

            parsed_mail = extract_and_validate_service_info(
                logger=self.logger, 
                execution_id=self.execution_id,
                notification=notification, 
                date=self.default_date, 
                database_manager=self.database_manager, 
                log_queue=log_queue
            )
            
            if not parsed_mail:
                continue

            sede, body, date, services = parsed_mail
            self.logger.debug(client_id, message_key, "Pending", f"Notification {message_key} parsed with expediente: {body.get('expediente')} for sede: {sede}")

            # Check if any string in the list is present in body.get('org')
            org_strings = [
                "Tesoreria General de la Seguridad Social",
                "Subdirección General de Clasificación de Contratistas y Registro de Contratos",
                "Secretaría General para la Innovación y Calidad del Servicio Público de Justicia",
                "Dirección General de Economía Circular, Transición Energética y Cambio Climático",
                "Dirección General del Catastro",
                "Organismo Estatal Inspección de Trabajo y Seguridad Social",
                "Ministerio de Industria y Turismo"
            ]

            # Save all extracted organizations to a txt file, one per line, appending if not already present
            org_dir = os.path.join(os.getenv("NETWORK_PATH"), "Documents", "workspace", "redtrust-automation", "files", "playground")
            os.makedirs(org_dir, exist_ok=True)
            org_file_path = os.path.join(org_dir, "organizations.txt")
            try:
                org_value = body.get('org')
                if org_value:
                    # Read existing organizations if file exists
                    existing_orgs = set()
                    if os.path.exists(org_file_path):
                        with open(org_file_path, "r", encoding="utf-8") as org_file:
                            existing_orgs = set(line.strip() for line in org_file if line.strip())
                    # Append only if not already present
                    if org_value not in existing_orgs:
                        with open(org_file_path, "a", encoding="utf-8") as org_file:
                            org_file.write(org_value + '\n')
            except Exception as e:
                self.logger.error(client_id, message_key, "Failure", f"Error saving organization to file: {e}")
            
            if aviso_especial and aviso_especial.lower() == 'no descargar aeat, ni tgss' and body.get('org') is not None and ('seguridad social' in body.get('org').lower()):
                self.logger.info(client_id, message_key, "Info", ErrorRobotDescargas.ErrorAvisoEspecial(client_id, aviso_especial))
                self.database_manager.update_notification_status(
                    cliente=client_id, 
                    message_key=message_key, 
                    status_id=14  # Actualiza estado a 'No descargar nada'
                )
                continue
            elif (
                any(s in services for s in ['SUSCRIPCION', 'BLINDAJE']) and not any(s in services for s in ['NEOCASH', 'NEOESTATAL', 'MULTINEO', 'INFONEO'])
                and body.get('org') is not None
                and any(org in body.get('org') for org in org_strings)
            ):                
                self.logger.info(client_id, message_key, "Info", ErrorRobotDescargas.MissingExpediente(notification.get('message_key')))
                self.database_manager.update_notification_status(
                    cliente=client_id, 
                    message_key=message_key, 
                    status_id=11
                ) # Actualiza estado a 'Solo suscripción'
            


            notificacion = Notificacion(
                message_key=message_key,
                date=date,
                sede=sede,
                mail=notification.get("mail"),
                status=notification.get("status", "Pendiente"),
                asunto=notification.get("asunto"),
                expediente=body.get("expediente") if sede not in ['dgt', 'dev'] else body.get("identificador"),
                org=body.get("org"),
                body_date=body.get("body_date"),
                identificador=body.get("identificador"),
                link=body.get("link")
            )
        

            # Agrupa por cliente y sede
            if client_id not in structured:
                descarga = Descarga(
                    client_id=int(client_id),
                    recipient_name=notification.get("recipient_name"),
                    servicio=services,
                    nif=notification.get("nif"),
                    cif=notification.get("cif"),
                    tipo_cliente=notification.get("tipo_cliente"),
                    client_name=notification.get("client_name"),
                    aviso_especial=notification.get("aviso_especial", None),
                    notificaciones={sede: [dict(notificacion)]}
                )
                structured[client_id] = dict(descarga)
                structured[client_id]['notificaciones'][sede] = []
                structured[client_id]['notificaciones'][sede].append(dict(notificacion))
            else:
                # Append the notification to the correct sede in the existing Descarga object
                if sede not in structured[client_id]['notificaciones']:
                    structured[client_id]['notificaciones'][sede] = []
                    structured[client_id]['notificaciones'][sede].append(dict(notificacion))
                else:
                    structured[client_id]['notificaciones'][sede].append(dict(notificacion))

        # Calcula el total de notificaciones sumando la longitud de todas las listas de notificaciones por sede y cliente
        total = sum(
            len(notificaciones_por_sede)
            for descarga in structured.values()
            for notificaciones_por_sede in descarga['notificaciones'].values()
        )

        log_queue.put(None)  # Signal the listener to exit        
        listener.join()
    
        self.logger.info("GLOBAL", "RUN", "Success", f"Total de notificaciones estructuradas: {total}.")
        return structured
  

    '''Related to RedTrust'''
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
                    module="Descargas",
                    filename=f"descargas_{self.default_date}"
                )

            success = self.redtrust_manager.automate_redtrust(str(certificate_id))
            if success:
                self.logger.info(certificate_id, "CERTIFICATE", "Success", f"Certificate {certificate_id} loaded successfully.")
            else:
                self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRobotDescargas.CertificateLoad(certificate_id))
            return success
        except Exception as e:
            self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRobotDescargas.CertificateLoad(certificate_id))
            return False
    

    ''' Downloads with robots'''
    def download_notifications(self, limit: Optional[str | int], sedes: Optional[List] = None, cliente: Optional[str] = None, message_ids: Optional[str] = None, message_keys: Optional[str] = None):
        """Execute all pending tasks"""
        # Fetch tasks from database
        self.actualizar_progreso_fase(None, None, 'db_fetch', 'Consultando tareas en base de datos...')
        notifications = self.database_manager.fetch_notifications(
            date=self.default_date_dashes,
            sedes=sedes,
            cliente=cliente,
            message_ids=message_ids,
            message_keys=message_keys,
            limit=limit
        )
        if not notifications:
            self.logger.info("GLOBAL", "RUN", "Info", "No hay notificaciones pendientes en la base de datos.")
            return

        # Filter and structure notifications
        structured_notifications = self._structure_notifications(
            notifications=notifications,
        )

        self.actualizar_progreso_fase(None, None, 'estructuracion', 'Estructurando datos y generando JSON de debug...')
        if not structured_notifications:
            self.logger.debug("GLOBAL", "RUN", "Failure", "No se encontraron notificaciones válidas para procesar.")
            return

        self.calcular_total_tasks(structured_notifications)

        message_keys = [
            notificacion["message_key"]
            for descarga in structured_notifications.values()
            for notificaciones_por_sede in descarga['notificaciones'].values()
            for notificacion in notificaciones_por_sede
            if "message_key" in notificacion
        ]

        self.database_manager.assign_notifications(message_keys, "Adría Martínez")
        # for notification in structured_notifications.values():
        #     for sede, notificaciones_por_sede in notification['notificaciones'].items():
        #         for notificacion in notificaciones_por_sede:                    
        #             self.database_manager.insert_assignment_log(
        #                 id_value=str(notificacion.get("message_key") or ""),
        #                 cliente=str(notification.get("client_id")) if notification.get("client_id") is not None else None,
        #                 sede=sede,
        #                 robot_name="RobotDescargas",
        #                 assigned_by="Adrià Martínez"
        #             )

        self.actualizar_progreso_fase(None, None, 'asignacion_certificados', 'Asignando certificados a usuarios...')

            

        for cert_id, client_info in structured_notifications.items():            
            self.logger.info(cert_id, "RUN", "Info", f"Processing tasks for certificate {cert_id}.")
            # Load certificate
            if not self._load_certificate(cert_id):
                self.actualizar_progreso_fase(cert_id, None, 'carga_certificados', f'Cargando certificado {cert_id}...')
                continue

            self.actualizar_progreso_fase(cert_id, None, 'carga_certificados', f'Cargando certificado {cert_id}...')
            self._download_notifications_with_certificate(cert_id, client_info)

    def _download_notifications_with_certificate(self, cliente: str, client_info: Dict[str, Any]):
        """
        Ejecuta un paquete de notificaciones por sede, creando un executionRecord por notificación,
        ejecutando el portal robot en batch y actualizando resultados por message_key.
        """
        execution_records = {}

        try:
            aviso_especial = client_info.get('aviso_especial', None)
            if aviso_especial:
                if aviso_especial.lower() == 'no descargar nada':
                    # Actualiza el estado de todas las notificaciones del cliente a 'No descargar nada' (status_id=14)
                    for notificaciones_por_sede in client_info['notificaciones'].values():
                        for notification in notificaciones_por_sede:
                            self.database_manager.update_notification_status(
                                message_key=notification['message_key'],
                                cliente=cliente,
                                status_id=14
                            )


                    self.logger.info(cliente, "RUN", "Info", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial)) 
                    return  # Salir de la función, no se descargan notificaciones
                elif aviso_especial.lower() == 'No descargar ayt madrid':    
                    self.logger.error(cliente, "RUN", "Failure", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))       
                    return  # Salir de la función, no se descargan notificaciones          
                # Si el aviso_especial es 'Revisar dgt', crear un registro especial si alguna sede no es 'dev' o 'dgt'
                elif aviso_especial.lower() == 'revisar dgt' and any(sede_not in ['dev', 'dgt'] for sede_not in client_info['notificaciones'].keys()):
                    message_key = f'revisar_dgt_{cliente}'
                    execution_records[message_key] = HistoricoAutomatizaciones(
                        execution_id=uuid4(),
                        cliente=cliente,
                        nif=client_info['nif'],
                        cif=client_info['cif'],
                        tipo_cliente=client_info['tipo_cliente'],
                        robot_name="RobotDescargas",
                        status="pending",
                        sede='dev',                        
                        result_robot=None,
                        result_certificate=None,
                        execution_message=f"Ejecución iniciada para cliente {cliente} notificación {message_key} en sede dev - Aviso especial: {aviso_especial}",
                        updated_by_user_id=78,
                        updated_by_user_name="Adría Martínez",
                        created_at=datetime.now(),
                        updated_at=None,
                    )

                    self.database_manager.insert_historico(execution_records[message_key])
                    try:
                        log_queue = Queue()
                        listener = Process(target=log_listener, args=(log_queue,self.default_date, self.execution_id))
                        listener.start()
                        
                        with Manager() as manager:
                            result_queue = manager.list()  # Shared list for inter-process communication

                            robot_logger = LoggerV2(
                                execution_id=self.execution_id,
                                module="Descargas",
                                class_name=f"RobotDEV",
                                log_dir="logs/descargas",
                                filename=None,
                                log_queue=log_queue
                            )
                            
                            robot_class = RobotDgt(
                                module="Descargas",
                                execution_id=self.execution_id,
                                cliente=cliente,
                                task_id=notifications[0]['message_key'],
                                date=self.default_date,
                                log_queue=log_queue
                            )
                        
                            # Ejecutar el portal robot en batch para todas las notificaciones de la sede
                            portal_process = Process(
                                target=run_portal_robot_static,
                                args=(
                                    cliente,
                                    'dev',
                                    self.logger,
                                    robot_class,
                                    {
                                        'cliente': cliente,
                                        'tipo_cliente': client_info['tipo_cliente'],
                                        'cif': client_info['cif'],
                                        'nif': client_info['nif'],
                                        'aviso_especial': client_info['aviso_especial'],
                                        'servicios': client_info.get('servicio') or client_info.get('services'),                                
                                        'notificaciones': notifications,
                                    },  # Paquete de notificaciones
                                    result_queue
                                ),
                                name=f"portal-dev-{cliente}"
                            )
                            portal_process.start()

                            # Create and start certificate handler process
                            cert_process = Process(
                                target=run_certificate_handler_static,
                                args=(
                                    robot_logger,
                                    self.default_date,
                                    {
                                        'client_id': cliente,
                                        'sede': 'dev',
                                        'recipient_name': client_info['recipient_name'],
                                        'message_key': message_key,
                                    },
                                    self.execution_id,
                                    result_queue
                                ),
                                name=f"cert-{message_key}"
                            )
                            cert_process.start()

                            portal_process.join()  # Wait for the portal robot process to complete
                            cert_process.join()  # Wait for the certificate handler process to complete

                            # Procesar resultados por message_key
                            result_map = {msg_key: rec for msg_key, rec in execution_records.items()}

                            results_by_notification = defaultdict(list)
                            for notification_id, status, result in result_queue:
                                results_by_notification[str(notification_id)].append((status, result))  

                            for notification_id, results in results_by_notification.items():
                                exec_rec : HistoricoAutomatizaciones = result_map.get(notification_id)
                                # Use a normal list for collected DescargasAutomatizaciones instances
                                descargas_automatizadas: list[DescargasAutomatizaciones] = []
                                if not exec_rec:
                                    self.logger.error(cliente, notification_id, "Failure", f"Execution record not found for notification {notification_id}")
                                    continue

                                for status, result in results:
                                    if status == 'error':
                                        exec_rec.status = 'error'
                                        exec_rec.result_robot = str(result)
                                        error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else result
                                        exec_rec.execution_message = f"Error al descargar {cliente} en sede dev, message_key {notification_id}: {error_msg}"
                                    elif status == 'certificate_handled':
                                        exec_rec.result_certificate = str(result) 
                                    elif status == 'completed':
                                        exec_rec.status = 'completed'

                                        descargas_automatizadas.append(
                                            DescargasAutomatizaciones(
                                                id=uuid4(),
                                                execution_id=exec_rec.execution_id,
                                                message_key=str(notification_id),
                                                fecha_descarga=datetime.fromisoformat(self.default_date_dashes),
                                                identificador=getattr(exec_rec, "notification_id", None),
                                                expediente=result.get("expediente", None),
                                                prev_desc=result.get("desc", None),
                                                filename=result.get("file") or result.get("filename"),
                                                organismo=result.get("org") or result.get("organismo"),
                                                created_at=datetime.now(),
                                                updated_at=None,
                                            )
                                        )
                                        exec_rec.execution_message = f"Descarga realizada correctamente para {cliente} en sede dev, message_key {notification_id}"
                                        exec_rec.result_robot = str(result)

                                self.database_manager.update_historico_descarga(
                                    record=exec_rec,
                                    descarga_records=descargas_automatizadas
                                )
                                self.actualizar_progreso_fase(cliente, notification_id, 'ejecucion_tarea', f'Cliente={cliente}, Sede=dev')
                            
                            log_queue.put(None)
                            listener.join()
                    except Exception as e:
                        self.logger.error(cliente, None, "Failure", f"Error en el manager de procesos para cliente {cliente}, sede dev - Aviso especial: {aviso_especial}: {e}")
                        return
                
            for sede, notifications in client_info['notificaciones'].items():
                # Crear executionRecord por cada notificación (key: message_key)
                if aviso_especial:
                    if aviso_especial.lower() in ['no descargar dehú'] and sede == 'dehù':
                        self.logger.info(cliente, "RUN", "Info", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))
                        continue  # No descargar notificaciones de Dehú
                    elif aviso_especial not in DESCARGA_ESPECIAL:
                        self.logger.error(cliente, "RUN", "Failure", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))
                        continue  # No descargar notificaciones de esta sede

                for notification in notifications:
                    if aviso_especial:
                        message_key = notification.get('message_key')
                        aeat = aviso_especial.lower()

                        if aeat in ['no descargar aeat', 'no descargar aeat, ni tgss', 'no descargar aeat, si tráfico'] and notification.get('status', '').lower() == 'agencia tributaria':
                            self.logger.info(cliente, message_key, "Info", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))                            
                            continue  # No descargar notificaciones de AEAT
                        if aeat == 'no descargar aeat, si tráfico':
                            self.logger.info(cliente, message_key, "Info", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))
                            continue  # No descargar notificaciones de AEAT, pero sí de tráfico
                            
                        if aeat == 'no descargar aeat, ni tgss' and notification.get('org') and 'seguridad social' in notification.get('org').lower():
                            self.logger.info(cliente, message_key, "Info", ErrorRobotDescargas.ErrorAvisoEspecial(cliente, aviso_especial))
                            self.database_manager.update_notification_status(
                                cliente=cliente,
                                message_key=message_key,
                                status_id=14  # Actualiza estado a 'No descargar nada'
                            )
                            continue                
                                            
                    message_key = notification['message_key']
                    self.logger.info(cliente, "RUN", "Info", f"Processing {message_key} notifications for client {cliente} in sede {sede} and date {notification.get('date')}.")
                    execution_records[message_key] = HistoricoAutomatizaciones(
                        execution_id=uuid4(),
                        cliente=cliente,
                        nif=client_info['nif'],
                        cif=client_info['cif'],
                        tipo_cliente=client_info['tipo_cliente'],
                        robot_name="RobotDescargas",
                        status="pending",
                        sede=sede,                        
                        result_robot=None,
                        result_certificate=None,
                        execution_message=f"Ejecución iniciada para cliente {cliente} notificación {message_key} en sede {sede}",
                        updated_by_user_id=78,
                        updated_by_user_name="Adría Martínez",
                        created_at=datetime.now(),
                        updated_at=None,
                    )

                    self.database_manager.insert_historico(execution_records[message_key])
                    
                try:
                    log_queue = Queue()
                    listener = Process(target=log_listener, args=(log_queue,self.default_date, self.execution_id))
                    listener.start()
                    
                    with Manager() as manager:
                        result_queue = manager.list()  # Shared list for inter-process communication

                        robot_logger = LoggerV2(
                            execution_id=self.execution_id,
                            module="Descargas",
                            class_name=f"Robot{sede.capitalize()}",
                            log_dir="logs/descargas",
                            filename=None,
                            log_queue=log_queue
                        )
                        robot_type = {
                            'dehù': RobotDehu,
                            'enotum': RobotEnotum,
                            'dev': RobotDgt,
                            'dgt': RobotDgt
                        }[sede]
                        
                        if sede in ['dev', 'dgt']:
                            robot_class = robot_type(
                                module="Descargas",
                                cliente=cliente,
                                task_id=notifications[0]['message_key'],
                                date=self.default_date,
                                log_queue=log_queue,
                                execution_id=self.execution_id
                            )
                        else:
                            robot_class = robot_type(
                                module="Descargas",
                                cliente=cliente,
                                task_id=notifications[0]['message_key'],
                                date=self.default_date,
                                db_manager=self.database_manager,
                                log_queue=log_queue,
                                execution_id=self.execution_id
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
                                    'tipo_cliente': client_info['tipo_cliente'],
                                    'cif': client_info['cif'],
                                    'nif': client_info['nif'],
                                    'aviso_especial': client_info['aviso_especial'],
                                    'servicios': client_info.get('servicio') or client_info.get('services'),                                
                                    'notificaciones': notifications,
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
                                    'client_id': cliente,
                                    'sede': sede,
                                    'recipient_name': client_info['recipient_name'],
                                    'message_key': notifications[0].get('message_key'),
                                },
                                self.execution_id,
                                result_queue
                            ),
                            name=f"cert-{message_key}-{cliente}"
                        )
                        cert_process.start()

                        portal_process.join()  # Wait for the portal robot process to complete
                        cert_process.join()  # Wait for the certificate handler process to complete

                        # Procesar resultados por message_key
                        result_map = {msg_key: rec for msg_key, rec in execution_records.items()}

                        results_by_notification = defaultdict(list)
                        for notification_id, status, result in result_queue:
                            results_by_notification[str(notification_id)].append((status, result))

                        # print(f"Results by notification: {results_by_notification}")    
                        # time.sleep(10)  

                        for notification_id, results in results_by_notification.items():                            
                            exec_rec : HistoricoAutomatizaciones = result_map.get(notification_id)
                            # Use a normal list for collected DescargasAutomatizaciones instances
                            descargas_automatizadas: list[DescargasAutomatizaciones] = []
                            if not exec_rec:
                                self.logger.error(cliente, notification_id, "Failure", f"Execution record not found for notification {notification_id}")
                                continue

                            for status, result in results:
                                if status == 'error':
                                    exec_rec.status = 'error'
                                    exec_rec.result_robot = str(result)
                                    error_msg = result.get('error', 'Unknown error') if isinstance(result, dict) else result
                                    exec_rec.execution_message = f"Error al descargar {cliente} en sede {sede}, message_key {notification_id}: {error_msg}"
                                elif status == 'certificate_handled':
                                    exec_rec.status = 'pending'
                                    exec_rec.result_certificate = str(result) 
                                elif status == 'completed':
                                    exec_rec.status = 'completed'

                                    descargas_automatizadas.append(
                                        DescargasAutomatizaciones(
                                            id=uuid4(),
                                            execution_id=exec_rec.execution_id,
                                            message_key=str(notification_id),
                                            fecha_descarga=datetime.fromisoformat(self.default_date_dashes),
                                            identificador=result.get("identificador", None),
                                            expediente=result.get("expediente", None),
                                            prev_desc=result.get("desc", None),
                                            filename=result.get("file") or result.get("filename"),
                                        )
                                    )
                                    exec_rec.execution_message = f"Descarga realizada correctamente para {cliente} en sede {sede}, message_key {notification_id}"
                                    exec_rec.result_robot = str(result)

                                    if str(notification_id).startswith('revisar_dgt'):
                                        continue  # Skip special 'revisar_dgt' records
                                    else:
                                        self.database_manager.update_notification_status(
                                            cliente=cliente,
                                            message_key=notification_id, 
                                            status_id=2
                                        ) # Actualiza estado a 'Descargado'

                            self.database_manager.update_historico_descarga(
                                record=exec_rec,
                                descarga_records=descargas_automatizadas
                            )
                            self.actualizar_progreso_fase(cliente, notification_id, 'ejecucion_tarea', f'Cliente={cliente}, Sede={sede}')
                        
                        log_queue.put(None)
                        listener.join()
                except ErrorRobotDescargas.ErrorAvisoEspecial as e:
                    self.logger.error(cliente, None, "Failure", str(e))
                    return
                except Exception as e:
                    self.logger.error(cliente, None, "Failure", f"Error en el manager de procesos para cliente {cliente}, sede {sede}: {e}")
                    return
        except ErrorRobotDescargas.ErrorAvisoEspecial as e:
            self.logger.error(cliente, None, "Failure", str(e))
            return
        except Exception as e:
            self.logger.error(cliente, None, "Failure", f"Error en _download_notifications_with_certificate: {e}")
            raise
    
        
    '''Main execution'''
    def run(self, cliente: Optional[str] = None, sedes: Optional[str] = None, message_ids: Optional[List] = None, message_keys: Optional[List] = None, limit: Optional[str | int] = 250):
        """Main method to run the robot manager"""
        self.run_absolute_start_time = time.time()  # Variable global de instancia para tiempo absoluto
        self.logger.info(cliente or "GLOBAL", message_ids or "RUN", "Info", "Starting Robot Descargas Manager for date: " + self.default_date_dashes + " execution_id: " + self.execution_id)
        
        try:
            self.download_notifications(sedes=sedes, cliente=cliente, message_ids=message_ids, message_keys=message_keys, limit=limit)
            
            absolute_elapsed_time = time.time() - self.run_absolute_start_time
            self.logger.info(cliente or "GLOBAL", message_ids or "RUN", "Info", f"Robot Manager ha terminado el ejecucion en {absolute_elapsed_time:.2f} segundos")
        except Exception as e:
            self.logger.error(cliente or "GLOBAL", message_ids or "RUN", "Failure", f"An error occurred during execution: {e}")
            raise

if __name__ == "__main__":
    # Create and run the robot manager
    parser = argparse.ArgumentParser(description="RobotDescargas Manager")
    parser.add_argument(
        '--dates', 
        type=str, 
        nargs='+',  # permite una o más fechas
        help='Fechas en formato YYYY-MM-DD (puedes pasar varias)'
    )
    parser.add_argument(
        '--sedes',
        type=str,
        nargs='+',
        default=['dev', 'dehù', 'enotum'],
        help="Lista de sedes a procesar (por defecto: ['dev', 'dehù', 'enotum'])"
    )
     # Add arguments for cliente and message_id with None as default
    parser.add_argument(
        '--cliente',
        type=str,
        default=None,
        help="ID del cliente a procesar (opcional)"
    )
    parser.add_argument(
        '--message_id',
        type=str,
        default=None,
        help="ID del mensaje a procesar (opcional)"
    )
    parser.add_argument(
        '--message_key',
        type=str,
        default=None,
        help="Clave del mensaje a procesar (opcional)"
    )
    args = parser.parse_args()
    
    # Si no se pasan sedes, usar el default
    if not args.sedes:
        args.sedes = ['dev', 'dehù', 'enotum']

       

    # Si no se pasaron fechas por parámetro, pedirlas por input
    while not args.dates:
        fechas_input = input("Introduce una o más fechas (separadas por espacios) en formato YYYY-MM-DD: ").strip()
        args.dates = fechas_input.split()

    # Validar todas las fechas
    fechas_validas = []
    for date_str in args.dates:
        while True:
            try:
                datetime.strptime(date_str, "%Y-%m-%d")
                fechas_validas.append(date_str)
                break
            except ValueError:
                date_str = input(f"Formato inválido para '{date_str}'. Introduce de nuevo (YYYY-MM-DD): ").strip()
                
    execution_id = str(uuid4())
    try:
        def log_queue(level: str | int, task_id: str, result: str, message: str) -> None:
            try:
                logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="PDFParser", log_dir="logs", filename="pdf_parser")

                # Mapear nivel de log a método del logger
                log_method = {
                    logging.ERROR: logger.error,
                    logging.WARNING: logger.warning,
                    logging.DEBUG: logger.debug,
                    logging.INFO: logger.info
                }.get(level, logger.info)

                log_method(
                    cliente="PDFParser",
                    task_id=task_id,
                    result=result,
                    message=message
                )

            except Exception as e:
                default_logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="LogListener", log_dir=r"logs\descargas",)
                default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

        # Ejecutar el run por cada fecha
        for fecha in fechas_validas:
            print(f"\n==== Ejecutando RobotDescargas para la fecha: {fecha} ====\n")
            manager = RobotDescargas(date = fecha, execution_id=execution_id)
            manager.run(
                sedes=args.sedes,
                cliente=args.cliente,
                message_ids=args.message_id
            )

            # validate_downloads(manager.logger, fecha)

        # extractor = PDFMetadataExtractor()
        # directory_path = os.path.join(os.getenv('DOWNLOAD_DIR'), "revisar", "sin-expediente")

        # extractor.create_metadata_dict(directory_path, log_queue, save_archives=False)
    
        # directory_path = os.path.join(os.getenv('DOWNLOAD_DIR'), "revisar", "con-expediente")
        # extractor.create_metadata_dict(directory_path, log_queue, save_archives=False)
    finally:
        # Cierra todos los loggers y handlers para liberar archivos de log
        import logging
        logging.shutdown()