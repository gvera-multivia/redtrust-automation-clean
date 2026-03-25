import datetime
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
from app.utils.utils import cleanup_download_dir, delete_download_dir, process_files, random_wait, ServiciosNEO, common_rules, DESCARGA_ESPECIAL
from app.models.mailExtractionModel import ExtractionResponse
from app.models.descarga_result import DescargaResult


class RobotEnotum:
    def __init__(self, cliente: str, task_id: str, execution_id:str, date: str,  log_queue: Queue,  db_manager: DescargaDatabase, module : str="ConsultaEnotum",):
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
        self.execution_id = execution_id
        self.date = date
        self.module = module
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.sede = 'enotum'  
        self.notification_date = None
        self.log_queue = log_queue
        self.download_path = None
        self.database_manager = db_manager

    def _log(self, level: int | str, task_id: str, result: str, message: str) -> None:
        self.log_queue.put({
            "level": level,
            "module": self.module,
            "class_name": self.class_name.split('_')[0],
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
                'postbox': '//*[@id="main-content"]/app-postbox',
                'dlink': '//*[@id="notification-content"]', 
                'dlink-no-content':'//*[@id="main-content"]/div[1]/div/div[1]/app-notification-document-viewer'
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
   
    def consultaNotifications(self, cliente_data : Dict, notificaciones : List[Dict], fecha_revision : str, descargaespecial:str = None) -> Dict[str, DescargaResult] | None:
        portalLink = 'https://usuari.enotum.cat'
        destinatari = cliente_data['cif'] if str(cliente_data.get('tipo_cliente')).lower() in ['empresa', 'holding'] else cliente_data['nif']
        response = {}
        agencia_tributaria = {}

        if isinstance(fecha_revision, str):
            fecha_revision_date = datetime.datetime.strptime(fecha_revision, '%Y-%m-%d').date()
        elif isinstance(fecha_revision, datetime.datetime):
            fecha_revision_date = fecha_revision.date()
        elif isinstance(fecha_revision, datetime.date):
            fecha_revision_date = fecha_revision
        else:
            raise ValueError("fecha_revision must be str, datetime, or date")

        temp_profile = tempfile.mkdtemp(prefix="enotum_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=portalLink if portalLink else 'https://usuari.enotum.cat',
            module="ConsultaEnotum",
            log_dir="logs/consultaenotum",
            filename=f"consultaenotum",
            cliente=self.cliente,
            task_id = self.task_id,
            site=self.sede,
            execution_id=self.execution_id
        )
        driver, self.download_path = driver_setup.setup_chrome_driver_descargas()

        try: 
            login, path = self._login_enotum(driver)

            if login:                
                random_wait(wait_type='LONG', wait=True)
                cleanup_download_dir(self.download_path, self.sede, self._log)    

                servicio_str = cliente_data.get('servicio')
                if servicio_str:
                    services = [s.strip().replace(" ", "").replace("-", "").upper() for s in servicio_str.split(';') if s.strip()]
                else:
                    try:
                        services = cliente_data.get('services')
                        if not services:
                            raise KeyError("Missing 'services' in notification")
                    except Exception:
                        self._log(logging.ERROR, self.task_id, 'Failure', "Error obteniendo servicios del cliente")
                        return "Failure", None, None
                    
                identificadores = [noti.get('identificador') for noti in notificaciones if noti.get('identificador')]
                                                 
                if path == 'profile':
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
                        
                        if not found_profile:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"No se encontró el perfil para el destinatario {destinatari}.")
                            return "Failure", None, None
                            
                        
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-select-profile/div/div/div/div/div[2]/div')))
                        return "Failure", None, None

                try:    
                    try:
                        info_element = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="main-content"]/app-postbox/div/div[4]/div/p'))
                        )
                        info_text = info_element.text.strip()
                        # Extraer el número total de notificaciones del texto info_text
                        total_notifications = None
                        match = re.search(r'de\s+(\d+)', info_text)
                        if match:
                            total_notifications = int(match.group(1))
                            self._log(logging.INFO, self.task_id, 'Pending', f"Total de notificaciones encontradas: {total_notifications}")
                        else:
                            self._log(logging.WARNING, self.task_id, 'Pending', f"No se pudo extraer el número total de notificaciones del texto: '{info_text}'")
                    except Exception as e:
                        self._log(logging.INFO, self.task_id, 'Pending', f"No se encontró el elemento de información: {e}")
                        try:
                            div_box = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                                EC.presence_of_element_located((By.XPATH, '//*[@id="main-content"]/app-postbox/div/div[2]/div/div'))
                            )

                            if 'no-results d-flex flex-column align-items-center' in (div_box.get_attribute('class') or ''):
                                total_notifications = 0
                                self._log(logging.INFO, self.task_id, 'Pending', "Se asume que no hay ninguna notificación presente.")
                                                        
                        except Exception:
                            raise Exception("No se pudo determinar el número de notificaciones.")

                    random_wait(wait_type='MEDIUM', wait=True)                                        

                    try:
                        if total_notifications is None or total_notifications == 0:
                            self._log(logging.INFO, self.task_id, 'Pending', "No hay notificaciones para procesar.")
                            return "Success", response, agencia_tributaria
                        i=0
                        while True:
                            notification_list = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_all_elements_located((By.XPATH, '//*[@id="main-content"]/app-postbox/div/div[3]/app-postbox-notification-row'))
                            )
                            random_wait(wait_type='MEDIUM', wait=True)

                            for index in range(len(notification_list)):
                                try:
                                    self.task_id = cliente_data.get('idConsulta') 
                                    notification = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, f'//*[@id="main-content"]/app-postbox/div/div[3]/app-postbox-notification-row[{index+1}]'))
                                    )

                                    random_wait(wait_type='MEDIUM', wait=True)

                                    date_span = notification.find_element(By.XPATH, './/div/article/div[2]/p').text
                                    date_str = date_span.split('·')[0].strip()
                                    try:
                                        date = datetime.datetime.strptime(date_str, '%d/%m/%Y').date()
                                    except ValueError:
                                        try:
                                            date = datetime.datetime.strptime(date_str, '%d/%m/%y').date()
                                        except ValueError as ve:
                                            self._log(logging.ERROR, self.task_id, 'Failure', f"Formato de fecha no válido: {date_str}")
                                            continue                    
                                    
                                    yesterday = datetime.date.today() - datetime.timedelta(days=1)
                                    if fecha_revision_date >= date or date > yesterday:
                                        self._log(logging.INFO, self.task_id, 'Pending', f"Notificación {index+1}: Fecha {date} fuera del rango [{fecha_revision_date}, {yesterday}]. Saltando resto de notificaciones.")
                                        break
                                    
                                    notification_title = notification.find_element(By.XPATH, './/div/article/div[1]/h3/a')
                                    notification_url = notification_title.get_attribute('href')
                                    notification_id = notification_title.get_attribute('href').split('/')[-1]
                                    notification_org = notification.find_element(By.XPATH, './/div/article/div[1]/p').text.split('·')[0].strip()
                                    notification_title_text = notification_title.text.strip()
                                    notification_found = None

                                    # Saltar notificaciones ya procesadas por identificador o estado "Descargado"
                                    if notification_id in identificadores:
                                        # Evitar asignar un generador a `self.task_id` (no serializable por multiprocessing queues).
                                        # Obtener el primer `message_key` coincidente o mantener el valor actual de `self.task_id`.
                                        self.task_id = next(
                                            (noti.get('message_key') for noti in notificaciones if noti.get('identificador') == notification_id),
                                            self.task_id
                                        )

                                        if any(
                                            noti.get('identificador') == notification_id and noti.get('status', '').lower() in ['descargado', ]
                                            for noti in notificaciones
                                        ):
                                            self._log(logging.INFO, self.task_id, 'Pending', f"Notificación {index+1}: Identificador {notification_id} en estado 'Descargado'. Saltando.")
                                            continue
                                        elif (
                                            any(
                                                noti.get('identificador') == notification_id and noti.get('status', '').lower() in ['agencia tributaria', ]
                                                for noti in notificaciones
                                            )
                                            and notification_title_text == "Notificació ATC"
                                            and notification_org == "Generalitat de Catalunya"
                                            and date >= datetime.date.today() - datetime.timedelta(days=10)
                                        ):
                                            self._log(logging.INFO, self.task_id, 'Pending', f"Notificación {index+1}: Identificador {notification_id} en estado 'Agencia Tributaria' y por debajo de 10 días de antelación. Saltando.")
                                            agencia_tributaria[self.task_id] = {
                                                "fecha": date.strftime('%Y-%m-%d'),
                                                "id": notification_title_text,
                                                "organismo": notification_org
                                            }
                                            continue
                                        elif any(
                                            noti.get('identificador') == notification_id and noti.get('status', '').lower() in ['pendiente', ]
                                            for noti in notificaciones
                                        ):
                                            notification_found = next(
                                                (noti for noti in notificaciones if noti.get('identificador') == notification_id and noti.get('status', '').lower() in ['pendiente', ]),
                                                None
                                            )
                                            pass
                                        else: 
                                            pass                            

                                    random_wait(wait_type='MEDIUM', wait=True)                    
                                    notification_title.click()
                                    random_wait(wait_type='LONG', wait=True)

                                    try:
                                        # Verificar si hay contenido en la notificación
                                        try:
                                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, '//*[@id="main-content"]/div[1]/div/div[1]/app-notification-document-viewer'))
                                            )

                                        except Exception:
                                            self._log(logging.INFO, self.task_id, 'Failure', f"Notificación {index+1}: No hay contenido para esta notificación. Saltando.")
                                            continue
                                        
                                        # Leer detalles de la notificación
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
                                                    org = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, './/td'))
                                                    ).text
                                                # Subject/Asunto/Assumpte
                                                if (
                                                    'Subject' in row_text or 'Asunto' in row_text or 'Assumpte' in row_text
                                                ):
                                                    title = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, './/td'))
                                                    ).text
                                                # Delivery date/Fecha de entrega/Data de lliurament
                                                if (
                                                    'Delivery date' in row_text or 'Fecha de entrega' in row_text or 'Data de lliurament' in row_text
                                                ):
                                                    disposition_date = WebDriverWait(row, random_wait(wait_type='SHORT', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, './/td'))
                                                    ).text


                                            # Primero, comprueba si la notificación ya está abierta o no descargada
                                            try:
                                                notification_btn_text = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="notification-content"]/div[2]/div[3]/a'))
                                                ).text
                                                if notification_btn_text in ['Abrir la notificación', 'Obrir la notificació', 'Open notification']:
                                                    desc = 'NO'
                                                else:
                                                    desc = 'SI'
                                            except Exception:
                                                self._log(logging.ERROR, self.task_id, 'Failure', f"Error detectando si la notificación está abierta o no para {self.task_id}")
                                                try:
                                                    status_text = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, '//*[@id="notification-content"]/div[2]/app-notification-detail-status/div/p'))
                                                    ).text
                                                    if any(word in status_text for word in ['Open', 'Obert', 'Abierta', 'Abierto', 'Vencida', 'Caducada', 'Vençuda']):
                                                        desc = 'SI'
                                                    elif any(word in status_text for word in ['En plazo', 'En termini', 'In term']):
                                                        desc = 'NO'
                                                    else:
                                                        desc = 'NO'
                                                except Exception:
                                                    desc = 'NO'
                                
                                            # Comprobación expediente-servicios para determinar si abrir o no la notificación
                                            expediente_valido = False
                                            expediente = None
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
                                                            if expediente and re.match(pattern, expediente):
                                                                expediente_valido = True
                                                                break
                                                            # Check title and extract expediente if matches
                                                            if title:
                                                                match = re.match(pattern, title)
                                                                if match:
                                                                    expediente = match.group(0)
                                                                    expediente_valido = True
                                                                    break
                                                        if expediente_valido:
                                                            break
                                                    except Exception:
                                                        continue

                                                if desc == "NO":
                                                    # Lógica para definir si es duda o no
                                                    if not expediente_valido:
                                                        if title and title.strip() in ["Notificació ATC"] and org and org.strip() in ["Generalitat de Catalunya"]:
                                                            duda = True
                                                        else:
                                                            # TODO: implementar lógica para deducir si una notificación es seguro que no es tráfico, cuando tiene los servicios BLINDAJE o SUSCRIPCION
                                                            duda = False
                                                    if notification_found and isinstance(notification_found, dict):
                                                        if not expediente_valido and not duda:                                                
                                                            if notification_found.get('status') == "Agencia Tributaria":
                                                                self.database_manager.update_notification_status(self.task_id, status_id=9)
                                                            elif notification_found.get('status') == "Pendiente":
                                                                self.database_manager.update_notification_status(self.task_id, status_id=1)
                                                            raise ErrorRobotDescargas.InvalidServicio(notification_found)
                                                        
                                            # Ensure expediente is initialized
                                            expediente_value = notification_found.get("expediente") if notification_found and isinstance(notification_found, dict) else None
                                            if expediente_value is None:
                                                expediente_value = expediente

                                            # Format disposition_date as DDMMYYYY (e.g., 22/9/25 -> 22092025)
                                            try:
                                                date_obj = datetime.datetime.strptime(date_str, '%d/%m/%y')
                                                disposition_date_formatted = date_obj.strftime('%Y%m%d')
                                            except ValueError:
                                                try:
                                                    date_obj = datetime.datetime.strptime(date_str, '%d/%m/%Y')
                                                    disposition_date_formatted = date_obj.strftime('%Y%m%d')
                                                except Exception:
                                                    disposition_date_formatted = date_str.replace('/', '')

                                            descarga_result = DescargaResult(
                                                org=org,
                                                title=title,
                                                expediente=expediente_value,
                                                disposition_date=disposition_date_formatted,
                                                desc=desc,
                                                file=None,
                                                status=DescargaResult.StatusEnum.PENDING,
                                                message=None,
                                                identificador=notification_id,
                                                url=notification_url
                                            )

                                            if descargaespecial:
                                                # Procesar aviso especial de descarga
                                                should_skip = self._handle_descarga_especial(
                                                    descargaespecial, descarga_result, expediente, title, notificaciones
                                                )
                                                if should_skip:
                                                    continue

                                            # Si la notificación no está abierta/descargada y expediente es válido, procede a abrirla
                                            if desc == "NO" and (expediente_valido or duda or any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services)):
                                                try:
                                                    notification_btn = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.element_to_be_clickable((By.XPATH, '//*[@id="notification-content"]/div[2]/div[3]/a'))
                                                    )
                                                    driver.execute_script(
                                                        "arguments[0].dispatchEvent(new MouseEvent('click', {bubbles: true, clientX: arguments[0].getBoundingClientRect().left + window.scrollX - 10, clientY: arguments[0].getBoundingClientRect().top + window.scrollY + 10}))",
                                                        notification_btn
                                                    )
                                                    print("ABRIR CLICK NOTIFICATION")
                                                    random_wait(wait_type='X_LONG', wait=True)
                                                    # Después de abrir, actualiza desc
                                                    desc = 'SI'
                                                except Exception as e:
                                                    self._log(logging.ERROR, self.task_id, 'Failure', f"Error abriendo la notificación para {self.task_id}: {e}")
                                                    continue

                                            # Descargar la notificación si está abierta/descargada
                                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                EC.element_to_be_clickable((By.XPATH, '//*[@id="notification-content"]/div[2]/div[1]/div/button'))
                                            ).click()
                                            print("DESCARGAR CLICK NOTIFICATION")

                                            self._log(logging.INFO, self.task_id, 'Pending', f"Notificación {index+1}: Título: {notification_title_text}, Fecha: {date}, Emisor: {org}, Asunto: {title}, Fecha de entrega: {disposition_date}, Descargada: {desc}")
                                            random_wait(wait_type='X_LONG', wait=True)

                                            try:
                                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.element_to_be_clickable((By.XPATH, '//*[@id="accordion-item-1-btn"]'))
                                                ).click()
                                            except Exception as e:
                                                self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-postbox/div/div[3]/app-postbox-notification-row')))
                                                pass

                                            # Only call process_files if date_obj is not None
                                            processed_file, expediente = process_files(self.download_path, self.task_id, descarga_result.to_dict(), self.cliente, self.date, descarga_result.disposition_date, self._log, 'consultaenotum')

                                            if self.task_id not in response:
                                                response[self.task_id] = []

                                            if processed_file:
                                                descarga_result.status = DescargaResult.StatusEnum.SUCCESS
                                                descarga_result.expediente = expediente
                                                descarga_result.message = f"Notificación procesada correctamente: {self.task_id}"
                                                descarga_result.file = processed_file
                                                response[self.task_id].append(descarga_result)

                                            else:
                                                identificador = notification_found.get('identificador') if notification_found and isinstance(notification_found, dict) else None
                                                self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando archivo para notificacion {identificador}")
                                                descarga_result.status = DescargaResult.StatusEnum.ERROR
                                                descarga_result.message = f"Error procesando archivo para notificacion {self.task_id}"
                                                response[self.task_id].append(descarga_result)
                                                continue

                                            if self.task_id in identificadores:
                                                self.database_manager.update_notification_status(self.task_id, status_id=2)

                                            self._log(logging.INFO, self.task_id, 'Success', f"Notificación procesada correctamente {self.task_id}: {descarga_result.to_dict()}")
                                        
                                        
                                        except Exception as e:
                                            self._log(logging.ERROR, self.task_id, 'Failure', f"Error leyendo detalles de notificación {index+1}: {e}")
                                            # Ensure descarga_result is initialized before referencing
                                            if 'descarga_result' in locals():
                                                descarga_result.status = DescargaResult.StatusEnum.ERROR
                                                descarga_result.message = f"Error procesando notificación {index+1}: {e}"
                                                if self.task_id not in response:
                                                    response[self.task_id] = []
                                                response[self.task_id].append(descarga_result)
                                            continue
                                        finally:
                                            driver.back()
                                            random_wait(wait_type='MEDIUM', wait=True)
                                    
                                    except Exception as e:
                                        self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando notificación {index+1}: {e}")
                                        continue

                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"Error accediendo a notificación {index+1}: {e}")
                                    continue
                                finally:
                                    i += 1

                            if fecha_revision_date >= date or date > yesterday:
                                break   
                            else:
                                try:
                                    next_button = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                        EC.element_to_be_clickable((By.XPATH, '//*[@id="main-content"]/app-postbox/div/div[4]/div/a'))
                                    )
                                    if next_button.is_enabled() and next_button.is_displayed():
                                        next_button.click()
                                        random_wait(wait_type='MEDIUM', wait=True)
                                        
                                        continue
                                except Exception:
                                    # No hay más páginas, salir del bucle
                                    break
                                                                
                        return "Success", response, agencia_tributaria

                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"Error recorriendo las notificaciones: {e}")
                        return "Failure", None, None

                except Exception as e:
                    self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorXpathElemento('//*[@id=\"main-content\"]/app-select-profile/div/div/div/div/div[2]/div')))
                    return "Failure", None, None                                        
                
            else:
                if WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                    EC.presence_of_element_located((By.XPATH, '//*[@id="validPaginaERRORCert"]/div/div/div[1]/h1/span'))
                ).text.strip() in ['Error amb el certificat electrònic', 'Error con el certificado electrónico', 'Error with the electronic certificate']:
                    self._log(logging.ERROR, self.task_id, 'Failure', "Error en el login")
                    return "LoginError", None, None
                else:
                    self._log(logging.ERROR, self.task_id, 'Failure', "Error en el login")
                    return "Failure", None, None


        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorDescargaEnSede(portalLink, e)))
            return "Failure", None, None

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
            delete_download_dir(self.download_path, self.sede, self._log)
            
    
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
            link = soup.find('a', href=True, string="Identifica't per accedir-hi")
            destinatari = re.sub(r'\s*\(.*?\)', '', extract_text('Destinatari') or '').strip()
            emissor = extract_text('Emissor')
            concepto = extract_text('Assumpte')
            data_lliurament = extract_text('Data de lliurament')
            id_notificacio = extract_text('Id. Notificació')

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
                        else:
                            concepto_value = "N/A"
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

    def _handle_descarga_especial(self, descargaespecial: str, descarga_result: DescargaResult, 
                                  expediente: str, title: str, notificaciones: List[Dict]) -> bool:
        """
        Maneja todos los avisos especiales de descarga de forma unificada.
        
        Args:
            descargaespecial: Tipo de aviso especial
            descarga_result: Objeto con datos de la descarga
            expediente: Número de expediente
            title: Título de la notificación
            notificaciones: Lista de notificaciones
            
        Returns:
            bool: True si debe saltarse la notificación, False en caso contrario
        """
        aviso = descargaespecial.lower().strip()
        
        def log_and_update_status(status_id: int) -> bool:
            """Función auxiliar para logging y actualización de estado"""
            self._log(logging.WARNING, self.task_id, 'Pending', 
                     ErrorRobotDescargas.ErrorAvisoEspecial(cliente=self.cliente, aviso=aviso))
            
            if self.task_id in [notif.get('message_key') for notif in notificaciones]:
                self.database_manager.update_notification_status(self.task_id, status_id=status_id)
            
            return True
        
        def is_traffic_notification() -> bool:
            """Verifica si una notificación es de tráfico basándose en patrones"""
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
                
                return False
                
            except Exception as e:
                self._log(logging.ERROR, self.task_id, 'Failure', 
                         f"Error comprobando si la notificación es de tráfico para {self.task_id}: {e}")
                raise ErrorRobotDescargas.ErrorAvisoEspecial(cliente=self.cliente, aviso="Error verificando tráfico")
        
        # Procesar cada tipo de aviso especial
        if aviso == "no descargar nada":
            return log_and_update_status(14)
        
        elif aviso == "no descargar leídas":
            if descarga_result.desc == "SI":
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat":
            if (descarga_result.title in ["Notificació ATC"] and 
                descarga_result.org.strip() in ["Generalitat de Catalunya"]):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, ni tgss":
            if (descarga_result.title in ["Notificació TGSS", "Notificació ATC", 
                                        "Tesoreria General de la Seguridad Social", 
                                        "Organismo Estatal Inspección de Trabajo y Seguridad Social"] and
                descarga_result.org.strip() in ["Generalitat de Catalunya", 
                                               "Ministerio de Inclusión, Seguridad Social y Migraciones"]):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, si tráfico":
            # Solo aplicar si es notificación ATC de Generalitat
            if (descarga_result.title in ["Notificació ATC"] and 
                descarga_result.org.strip() in ["Generalitat de Catalunya"]):
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
            if descargaespecial not in DESCARGA_ESPECIAL:
                # Aviso no reconocido
                self._log(logging.ERROR, self.task_id, 'Failure', 
                        f"Aviso especial no reconocido: {descargaespecial} para {self.task_id}")
                return False
            else:
                # Aviso reconocido pero sin acción definida
                self._log(logging.WARNING, self.task_id, 'Pending', 
                        f"Aviso especial reconocido pero sin acción definida: {descargaespecial} para {self.task_id}")
                return False
        
        # Por defecto, no saltar la notificación
        return False

