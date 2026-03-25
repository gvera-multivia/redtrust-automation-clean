from datetime import datetime
from queue import Queue
import time,tempfile, shutil, os, sys, re
from typing import Any, Dict, List

# THIRD PARTY PACKAGES
import logging
import uuid
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# PERSONAL PACKAGES - UTILS
from database.descargas.database_descargas import DescargaDatabase
from app.helper.errors.base import ErrorBase
from app.helper.errors.robot_descargas import ErrorRobotDescargas
from app.utils.setup import WebDriverSetup
from app.utils.utils import DESCARGA_ESPECIAL, cleanup_download_dir, delete_download_dir, process_files, random_wait, ServiciosNEO, common_rules
from app.models.mailExtractionModel import ExtractionResponse
from app.models.descarga_result import DescargaResult


class RobotEnotum:
    def __init__(self, cliente: str, task_id: str, execution_id:str,  date: str,  log_queue: Queue, db_manager: DescargaDatabase, module : str="Descargas"):
        self.rules = {
            ServiciosNEO.INFONEO: [
                "CT_Pattern", "CC_Pattern", "EE_Pattern", "ET_Pattern", "EX_Pattern",
                "OA_Pattern", "EB_Pattern", "EI_Pattern", "EJ_Pattern", "MX_Pattern",
                "MU_Pattern", "TRIBUTS_Poblacion"
            ],
            ServiciosNEO.MULTINEO: list(common_rules.keys()),  # Use all rules
            ServiciosNEO.NEOCASH: list(common_rules.keys()),  # Use all rules
            ServiciosNEO.NEOESTATAL: list(common_rules.keys()),  # Use all rules
            ServiciosNEO.SUSCRIPCION: [
                "DH_Pattern", "MULTES_Poblacion", "DENUNCIA", "REQUERIMENT_DENUNCIA", 
                "NUM_SCatTransit_Pattern"
            ],
            ServiciosNEO.BLINDAJE: [
                "DH_Pattern", "EB_Pattern", "EI_Pattern", "EJ_Pattern", "MX_Pattern",
                "MU_Pattern", "MULTES_Poblacion", "DENUNCIA", "REQUERIMENT_DENUNCIA", 
                "NUM_SCatTransit_Pattern"
            ],
        }
        self.cliente = cliente
        self.task_id = task_id
        self.date = date
        self.module = module
        self.execution_id = execution_id
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.sede = 'enotum'  
        self.notification_date = None
        self.database_manager = db_manager

        self.log_queue = log_queue
        self.download_path = None
        # self._log(logging.INFO, self.task_id, 'Pending', f"{self.__class__.__name__} initialized for client {cliente} with task ID {task_id} on date {date}")      

    def _log(self, level: int | str, task_id: str, result: str, message: str) -> None:
        self.log_queue.put({
            "level": level,
            "module": self.module,
            "class_name": self.class_name,
            "cliente": self.cliente,
            "task_id": task_id,
            "result": result,
            "message": message
        })

    def _login_enotum(self, driver):
        try: 
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="main-content"]/app-landing/div[1]/div/div/div[2]/a'))
            ).click()


            start_time = time.time()
            while time.time() - start_time < random_wait(wait_type='XX_LONG', wait=False):
                try:
                    idcat_login = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="login-form-idcatmobil"]'))
                    )
                    cert_login = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="contingutPrincipal"]/div[2]/div[2]'))
                    )

                    if cert_login and idcat_login:
                        try:
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCertCaptcha"]'))
                            ).click()
                        except Exception:
                            WebDriverWait(driver,  random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCert"]'))
                            ).click()
                    else:
                        break
                except Exception as e:
                    random_wait(wait_type='SHORT', wait=True)
                    pass

            random_wait(wait_type='MEDIUM', wait=True) 

            xpaths = {
                'profile': '//*[@id="main-content"]/app-select-profile',
                'dlink': '//*[@id="notification-content"]', 
                'dlink-no-content':'//*[@id="main-content"]/div[1]/div/div[1]/app-notification-document-viewer',
                'buzon': '//*[@id="main-content"]/app-postbox'
                # //*[@id="main-content"]/div[1]/div/div[1]/app-notification-document-viewer
            }

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:  
                for key, xpath in xpaths.items(): 
                    try:
                        element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        if element: 
                            self._log(logging.DEBUG, self.task_id, 'Success', f"Login exitoso: {xpath} encontrado - {key}.")
                            return True, key
                    except Exception as e:
                        self._log(logging.DEBUG, self.task_id, 'Failure', f"No se encontró el elemento para {xpath}")

            self._log(logging.DEBUG, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, 'No se pudo encontrar el elemento de perfil o enlace de descarga en el tiempo esperado.')))
            return False, None

        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, e)))
            return False, None

        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def handle_descarga_especial(self, descarga_especial: str, descarga_result: DescargaResult, 
                                expediente: str, title: str, org: str, notifications: List[Dict]) -> bool:
        """
        Maneja todos los avisos especiales de descarga de forma unificada para eNotum.
        
        Args:
            descarga_especial: Tipo de aviso especial
            descarga_result: Objeto con datos de la descarga
            expediente: Número de expediente
            title: Título de la notificación
            org: Organismo emisor
            notifications: Lista de notificaciones
            
        Returns:
            bool: True si debe saltarse la notificación, False en caso contrario
        """
        if not descarga_especial:
            return False
            
        aviso = descarga_especial.lower().strip()
        
        def log_and_update_status(status_id: int) -> bool:
            """Función auxiliar para logging y actualización de estado"""
            self._log(logging.WARNING, self.task_id, 'Pending', 
                     f"Aviso especial aplicado: {aviso} para cliente {self.cliente}")
            
            # Buscar la notificación actual en la lista para actualizar su estado
            if self.task_id in [notif.get('message_key') for notif in notifications]:
                self.database_manager.update_notification_status(
                    cliente=self.cliente,
                    message_key=self.task_id,
                    status_id=status_id
                )
            
            return True
        
        def is_traffic_notification() -> bool:
            """Verifica si una notificación es de tráfico basándose en patrones de eNotum"""
            try:
                service_rules = self.rules.get(ServiciosNEO.SUSCRIPCION, [])
                
                for rule_key in service_rules:
                    pattern = common_rules.get(rule_key)
                    if not pattern:
                        continue
                    
                    # Verificar expediente
                    if expediente and re.match(pattern, expediente):
                        return True
                    
                    # Verificar título y extraer expediente si coincide
                    if title:
                        match = re.match(pattern, title)
                        if match:
                            return True
                
                # Verificar palabras clave específicas de tráfico en eNotum
                if title:
                    traffic_keywords = ['multes', 'multas', 'trànsit', 'tráfico', 'transit']
                    if any(keyword in title.lower() for keyword in traffic_keywords):
                        return True
                
                return False
                
            except Exception as e:
                self._log(logging.ERROR, self.task_id, 'Failure', 
                         f"Error comprobando si la notificación es de tráfico para {self.task_id}: {e}")
                return False
        
        # Procesar cada tipo de aviso especial
        if aviso == "no descargar nada":
            return log_and_update_status(14)
        
        elif aviso == "no descargar leídas":
            if descarga_result.desc == "SI":
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat":
            if (title and "Notificació ATC" in title and 
                org and "Generalitat de Catalunya" in org):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, ni tgss":
            if (title and org and (
                ("Notificació ATC" in title and "Generalitat de Catalunya" in org) or
                ("Tesoreria General de la Seguridad Social" in org) or
                ("Organismo Estatal Inspección de Trabajo y Seguridad Social" in org))):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, si tráfico":
            # Solo aplicar si es notificación ATC de Generalitat
            if (title and "Notificació ATC" in title and 
                org and "Generalitat de Catalunya" in org):
                # Si es tráfico, no saltar (continuar procesando)
                if is_traffic_notification():
                    return False
                else:
                    return log_and_update_status(8)
            # Si no es ATC de Generalitat, no aplicar el filtro
            return False
        
        elif aviso == "solo tráfico":
            # Si es tráfico, no saltar (continuar procesando)
            if is_traffic_notification():
                return False
            else:
                return log_and_update_status(8)
        
        else:
            if descarga_especial not in DESCARGA_ESPECIAL:
                # Aviso no reconocido
                self._log(logging.ERROR, self.task_id, 'Failure', 
                        f"Aviso especial no reconocido: {descarga_especial} para {self.task_id}")
                return False
            else:
                self._log(logging.ERROR, self.task_id, 'Failure',
                        f"Aviso especial no implementado: {descarga_especial} para {self.task_id}")
                return False
        
        # Por defecto, no saltar la notificación
        return False 
   
    def getNotifications(self, notification_data :  Dict[str, Any]) -> Dict[str, DescargaResult] | None:
        notifications = notification_data['notificaciones']
        if not notification_data or not notifications :
            self._log(logging.ERROR, self.task_id, 'Failure', "No notifications provided.")
            return None

        if not isinstance(notifications, list) or len(notifications) == 0:
            self._log(logging.ERROR, self.task_id, 'Failure', "Notifications should be a list of dictionaries.")
            return None

        portalLink = notification_data['notificaciones'][0].get('link', None)
        destinatari = notification_data['cif'] if notification_data['tipo_cliente'] in ['empresa'] else notification_data['nif']
        descarga_especial = notification_data.get('aviso_especial', None)

        response = {}

        temp_profile = tempfile.mkdtemp(prefix="enotum_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=portalLink if portalLink else 'https://usuari.enotum.cat',
            module="Descargas",
            log_dir="logs/descargas",
            filename=f"descargas_{self.date}",
            cliente=self.cliente,
            task_id = self.task_id,
            execution_id=self.execution_id,
            site=self.sede
        )
        driver, self.download_path = driver_setup.setup_chrome_driver_descargas()

        try: 
            login, path = self._login_enotum(driver)

            if login:
                for index, notification in enumerate(notifications):
                    self.task_id = notification.get('message_key')
                    notification_date = notification.get('date')
                    services = notification_data.get('servicios')
                    if not services or not isinstance(services, list) or len(services) == 0:
                        try:
                            services = notification_data.get('services')
                            if not services:
                                raise KeyError("Missing 'services' in notification")
                        except Exception:
                            self._log(logging.ERROR, self.task_id, 'Failure', ErrorRobotDescargas.MissingServicio(notification.get('message_key')))
                            self.database_manager.update_notification_status(
                                cliente=self.cliente,
                                message_key=self.task_id, 
                                status_id=7
                            )
                            continue

                    if notification_date:
                        try:
                            formatted_date = notification_date
                            if isinstance(notification_date, datetime):
                                formatted_date = notification_date.strftime("%Y%m%d")
                            else:
                                try:
                                    formatted_date = datetime.strptime(notification_date, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
                                except Exception:
                                    try:
                                        formatted_date = datetime.strptime(notification_date, "%Y-%m-%d").strftime("%Y%m%d")
                                    except Exception:
                                        formatted_date = notification_date
                            self.notification_date = formatted_date
                        except Exception:
                            pass
                    
                    if index > 0:
                        try: 
                            driver.get(notification.get('link'))
                        except Exception:
                            driver.get(f"https://usuari.enotum.cat/profile?nextUrl=%2Fnotification%2F{notification['identificador']}")

                    random_wait(wait_type='LONG', wait=True)

                    cleanup_download_dir(self.download_path, self.sede, self._log)


                    descarga_result = DescargaResult(
                        org=None,
                        title=None,
                        expediente=notification.get("expediente", None),
                        disposition_date=None,
                        desc="NO",
                        file=None,
                        status=DescargaResult.StatusEnum.PENDING,
                        message=None
                    )
                    
                    if path == 'profile':
                        try:
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-notification-detail'))
                            )
                        except Exception:
                            try:
                                try: 
                                    profiles = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(                
                                        EC.presence_of_all_elements_located((By.XPATH, '//*[@id="main-content"]/app-select-profile/div/div/div/div/div[2]/div'))
                                    )

                                    found_profile = False
                                    for index, profile in enumerate(profiles):
                                        if index == 0:
                                            try:
                                                nif_cif = WebDriverWait(profile, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, './p'))
                                                ).text
                                                self._log(logging.DEBUG, self.task_id, 'Failure', str(ErrorBase.ErrorNifCliente(destinatari, nif_cif)))
                                                if destinatari in nif_cif:
                                                    WebDriverWait(profile, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.element_to_be_clickable((By.XPATH, './a'))
                                                    ).click()
                                                    found_profile = True
                                                    break

                                            except Exception as e:
                                                self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorNifCliente(destinatari, nif_cif)))
                                                continue
                                        else:
                                            list_items = WebDriverWait(profile, random_wait(wait_type='X_LONG', wait=False)).until( 
                                                EC.presence_of_all_elements_located((By.XPATH, './ul/li'))
                                            )
                                            for item in list_items:
                                                try:
                                                    nif_cif = WebDriverWait(item, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, './p'))
                                                    ).text
                                                    self._log(logging.INFO, self.task_id, 'Pending', f"NIF/CIF encontrado: {nif_cif} - {destinatari}")
                                                    if destinatari in nif_cif:
                                                        WebDriverWait(item, random_wait(wait_type='X_LONG', wait=False)).until(
                                                            EC.element_to_be_clickable((By.XPATH, './a'))
                                                        ).click()
                                                        found_profile = True
                                                        break
                                                except Exception as e:
                                                    self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorNifCliente(destinatari, nif_cif)))
                                                    continue
                                    
                                    if not found_profile:
                                        self._log(logging.ERROR, self.task_id, 'Failure', f"No se encontró el perfil para el destinatario {destinatari}.")
                                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                                        descarga_result.message = f"No se encontró el perfil para el destinatario {destinatari}."
                                        response[self.task_id ] = descarga_result
                                        continue
                                    
                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-select-profile/div/div/div/div/div[2]/div')))
                                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                                    descarga_result.message = ErrorBase.ErrorXpathElemento('//*[@id="main-content"]/app-select-profile/div/div/div/div/div[2]/div')
                                    response[self.task_id ] = descarga_result
                                    continue

                                random_wait(wait_type='MEDIUM', wait=True)

                                try:
                                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-notification-detail'))
                                    )
                                except Exception:
                                    try:
                                        notification_list = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                            EC.presence_of_all_elements_located((By.XPATH, '//*[@id="main-content"]/app-postbox/div/div[3]/app-postbox-notification-row'))
                                        )
                                        random_wait(wait_type='MEDIUM', wait=True)

                                        for index, notificacion in enumerate(notification_list):    
                                            random_wait(wait_type='MEDIUM', wait=True)

                                            notification_title = notificacion.find_element(By.XPATH, './/div/article/div[1]/h3/a')

                                            if self.task_id in notification_title.text:
                                                random_wait(wait_type='MEDIUM', wait=True)
                                                
                                                notification_title.click()
                                                self._log(logging.DEBUG, self.task_id, 'Pending', f"Notificación encontrada: {notification_title.text}")
                                                break

                                    except Exception as e:
                                        self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-postbox/div/div[3]/app-postbox-notification-row')))  
                                        pass  
                                                            

                            except Exception as e:
                                self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-select-profile/div/div/div/div/div[2]/div')))
                                descarga_result.status = DescargaResult.StatusEnum.ERROR
                                descarga_result.message = ErrorBase.ErrorXpathElemento('//*[@id="main-content"]/app-select-profile/div/div/div/div/div[2]/div')
                                response[self.task_id] = descarga_result
                                continue
                        
                    try:
                        try:
                            rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="accordion-item-1"]/app-notification-detail-data/table/tr'))
                            )
                        except Exception as e:
                            rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="notification-content"]/div[2]/app-notification-detail-data/table/tr'))
                            )
                        
                        for row in rows:
                            row_text = row.text
                            # Emitter/Emisor/Emissor
                            if (
                                'Emitter' in row_text or 'Emisor' in row_text or 'Emissor' in row_text
                            ):
                                descarga_result.org = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './/td'))
                                ).text
                            # Subject/Asunto/Assumpte
                            if (
                                'Subject' in row_text or 'Asunto' in row_text or 'Assumpte' in row_text
                            ):
                                descarga_result.title = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './/td'))
                                ).text
                            # Delivery date/Fecha de entrega/Data de lliurament
                            if (
                                'Delivery date' in row_text or 'Fecha de entrega' in row_text or 'Data de lliurament' in row_text
                            ):
                                descarga_result.disposition_date = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './/td'))
                                ).text

    
                        # Primero, comprueba si la notificación ya está abierta o no descargada
                        try:
                            notification_btn_text = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="notification-content"]/div[2]/div[3]/a'))
                            ).text
                            if notification_btn_text in ['Abrir la notificación', 'Obrir la notificació', 'Open notification']:
                                descarga_result.desc = 'NO'
                            else:
                                descarga_result.desc = 'SI'
                        except Exception:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"Error detectando si la notificación está abierta o no para {self.task_id}")
                            try:
                                status_text = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '//*[@id="notification-content"]/div[2]/app-notification-detail-status/div/p'))
                                ).text
                                if any(word in status_text for word in ['Open', 'Obert', 'Abierta', 'Abierto', 'Vencida', 'Caducada', 'Vençuda']):
                                    descarga_result.desc = 'SI'
                                elif any(word in status_text for word in ['En plazo', 'En termini', 'In term']):
                                    descarga_result.desc = 'NO'
                                else:
                                    descarga_result.desc = 'NO'
                            except Exception:
                                descarga_result.desc = 'NO'

                        # Verificar aviso especial antes de continuar
                        if descarga_especial:
                            should_skip = self.handle_descarga_especial(
                                descarga_especial=descarga_especial,
                                descarga_result=descarga_result,
                                expediente=descarga_result.expediente,
                                title=descarga_result.title,
                                org=descarga_result.org,
                                notifications=[]  # Se pasa lista vacía ya que el update se hace internamente
                            )
                            if should_skip:
                                raise ErrorRobotDescargas.ErrorAvisoEspecial(self.cliente, descarga_especial)
                            
                        expediente_valido = False
                        duda = False

                        # Solo comprobar expediente si la notificación NO está abierta/descargada
                        if any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services):
                            expediente_valido = True  # Para estos servicios, no se valida el expediente
                        elif any(service in ["BLINDAJE", "INFONEO", "SUSCRIPCION"] for service in services):
                            # Itera sobre los servicios y sus reglas regex, comprueba si el expediente cumple alguna
                            for service in services:
                                try:
                                    # Obtiene las reglas para el servicio actual
                                    service_enum = ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")]
                                    service_rules = self.rules.get(service_enum, [])
                                    for rule_key in service_rules:
                                        pattern = common_rules.get(rule_key)
                                        if not pattern:
                                            continue
                                        # Check expediente
                                        if descarga_result.expediente and re.match(pattern, descarga_result.expediente):
                                            expediente_valido = True
                                            break
                                        # Check title and extract expediente if matches
                                        if descarga_result.title:
                                            match = re.match(pattern, descarga_result.title)
                                            if match:
                                                descarga_result.expediente = match.group(0)
                                                expediente_valido = True
                                                break
                                    if expediente_valido:
                                        break
                                except Exception:
                                    continue

                            if descarga_result.desc == "NO":
                                # Lógica para definir si es duda o no
                                if not expediente_valido:
                                    if descarga_result.title and descarga_result.title.strip() in ["Notificació ATC"] and descarga_result.org and descarga_result.org.strip() in ["Generalitat de Catalunya"]:
                                        duda = True
                                    else:
                                        if any(word in descarga_result.title.lower() for word in ['multes', 'multas']):
                                            # Indica que es de tráfico
                                            duda = True
                                        else:
                                            # TODO: implementar lógica para deducir si una notificación es seguro que no es tráfico, cuando tiene los servicios BLINDAJE o SUSCRIPCION
                                            duda = False

                                if not expediente_valido and not duda:
                                    status = notification.get('status')
                                    if status in ["Agencia Tributaria", "Pendiente"]:
                                        self.database_manager.update_notification_status(
                                            cliente=self.cliente,
                                            message_key=self.task_id,
                                        )
                                    raise ErrorRobotDescargas.InvalidServicio(notification)

                        # Si la notificación no está abierta/descargada y expediente es válido, procede a abrirla
                        if descarga_result.desc == "NO" and (expediente_valido or duda or any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services)):
                            try:
                                notification_btn = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '//*[@id="notification-content"]/div[2]/div[3]/a'))
                                )
                                driver.execute_script(
                                    "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true, clientX: arguments[0].getBoundingClientRect().left + window.scrollX - 10, clientY: arguments[0].getBoundingClientRect().top + window.scrollY + 10}))",
                                    notification_btn
                                )
                                random_wait(wait_type='X_LONG', wait=True)
                                # Después de abrir, actualiza desc
                                descarga_result.desc = 'SI'
                            except Exception as e:
                                self._log(logging.ERROR, self.task_id, 'Failure', f"Error abriendo la notificación para {self.task_id}: {e}")
                                descarga_result.status = DescargaResult.StatusEnum.ERROR
                                descarga_result.message = f"Error abriendo la notificación para {self.task_id}: {e}"
                                response[self.task_id ] = descarga_result
                                continue                                
                                                        

                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="notification-content"]/div[2]/div[1]/div/button'))
                        ).click()

                        random_wait(wait_type='MEDIUM', wait=True)

                        try:
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="accordion-item-1-btn"]'))
                            ).click()
                        except Exception as e:
                            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-postbox/div/div[3]/app-postbox-notification-row')))
                            pass
                        
                        descarga_result.expediente = notification.get('expediente', None)

                        processed_file, expediente = process_files(self.download_path, self.task_id , descarga_result.to_dict(), self.cliente, self.date, self.notification_date, self._log)

                        if processed_file:
                            descarga_result.status = DescargaResult.StatusEnum.SUCCESS
                            descarga_result.expediente = expediente
                            descarga_result.message = f"Notificación procesada correctamente: {self.task_id}"
                            descarga_result.file = processed_file
                        else:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando archivo para notificacion {notification.get('identificador')}")
                            descarga_result.status = DescargaResult.StatusEnum.ERROR
                            descarga_result.message = f"Error procesando archivo para notificacion {self.task_id}"
                            response[self.task_id] = descarga_result
                            continue

                        response[self.task_id] = descarga_result
                        self._log(logging.INFO, self.task_id, 'Success', f"Notificación procesada correctamente {self.task_id}: {descarga_result.to_dict()}")
                    except RuntimeError as re:
                        self._log(logging.ERROR, self.task_id, 'Failure', str(re))
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = str(re)
                        response[self.task_id] = descarga_result
                        continue
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando notificacion {self.task_id }: {e}")
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = f"Error procesando notificacion {self.task_id}: {e}"
                        response[self.task_id] = descarga_result
                        continue
            else:
                self._log(logging.ERROR, self.task_id, 'Failure', "Error en el login")
                return None

        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorDescargaEnSede(portalLink, e)))
            return None

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
            delete_download_dir(self.download_path, self.sede, self._log)
            if response:
                return response
            
            return None
    
    def extract_from_body(self, body_html: str, services: List[str]) -> ExtractionResponse:
        """Extract specific field values from the body_html content."""
        if not body_html:
            self._log(logging.ERROR, self.task_id, "Failure", "body_html cannot be None or empty")
            raise ValueError("body_html cannot be None or empty")
        try:
            soup = BeautifulSoup(body_html, 'html.parser')

            def extract_text(th_string):
                """Helper function to extract text from a table row."""
                element = soup.find('th', string=th_string)
                return element.find_next('td').get_text(strip=True) if element else None

            # Extract fields
            link = soup.find('a', href=True, string=lambda s: s and (s.strip() in ["Identifica't per accedir-hi", "Identifícate para acceder a ella"]))
            # Soportar catalán y castellano para los campos
            destinatari = re.sub(
                r'\s*\(.*?\)', '', 
                extract_text('Destinatari') or extract_text('Destinatario') or ''
            ).strip()
            emissor = extract_text('Emissor') or extract_text('Emisor')
            concepto = extract_text('Assumpte') or extract_text('Asunto')
            data_lliurament = extract_text('Data de lliurament') or extract_text('Fecha de entrega')
            id_notificacio = extract_text('Id. Notificació') or extract_text('Id. Notificación')

            matching_rules = {}
            concepto_value = None  
            for service in services:
                # Descargar todas las notificaciones 
                if service in [ServiciosNEO.MULTINEO.name, ServiciosNEO.NEOCASH.name, ServiciosNEO.NEOESTATAL.name]:
                    try:
                        service_rules = self.rules.get(
                            ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")], []
                        )
                        for rule_key in service_rules:
                            matches = re.findall(common_rules[rule_key], concepto or "")
                            if matches:
                                matching_rules[rule_key] = matches
                                concepto_value = matches[0]
                                break
                        if concepto_value:                    
                            break
                        
                    except KeyError:
                        self._log(logging.WARNING, self.task_id, "Failure", f"No matching rules found for service: {service}. Skipping.")
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Error finding pattern expediente - {service}: {e}")
                # Descargar todas las notificaciones excepto las de tráfico
                elif service in [ServiciosNEO.INFONEO.name]:
                    try:
                        service_rules = self.rules.get(
                            ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")], []
                        )
                        for rule_key in service_rules:
                            matches = re.findall(common_rules[rule_key], concepto or "")
                            if matches:
                                matching_rules[rule_key] = matches
                                concepto_value = matches[0]
                                break
                        if concepto_value:                    
                            break
                    except KeyError:
                        self._log(logging.WARNING, self.task_id, "Failure", f"No matching rules found for service: {service}. Skipping.")
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Error finding pattern expediente - {service}: {e}")
                # Descargar solo las notificaciones de tráfico
                elif service in [ServiciosNEO.SUSCRIPCION.name, ServiciosNEO.BLINDAJE.name]:
                    try:
                        service_rules = self.rules.get(
                            ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")], []
                        )
                        for rule_key in service_rules:
                            matches = re.findall(common_rules[rule_key], concepto or "")
                            if matches:
                                matching_rules[rule_key] = matches
                                concepto_value = matches[0]
                                break
                        if concepto_value:                    
                            break
                    except KeyError:
                        self._log(logging.WARNING, self.task_id, "Failure", f"No matching rules found for service: {service}. Skipping.")
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Error finding pattern expediente - {service}: {e}")
                else:
                    self._log(logging.WARNING, self.task_id, "Failure", f"Unknown service: {service}. Skipping.")

            # Return the extracted elements in a structured response
            self._log(logging.INFO, self.task_id, "Success", f"Extracción completada para {destinatari} - {concepto_value}")
            return ExtractionResponse(
                client_name=destinatari,
                expediente=concepto_value,
                org=emissor,
                date=data_lliurament,
                identificador=id_notificacio,
                link=link['href'] if link else None
            )
        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"Error extracting fields: {e}")
            raise KeyError(f"⚠️ Error extracting fields: {e}")

