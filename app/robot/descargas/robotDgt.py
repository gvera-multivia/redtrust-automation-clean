import glob
import logging
import os
from queue import Queue
import shutil, time, tempfile, re, pyautogui
import uuid
import re 
from typing import List

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime
from bs4 import BeautifulSoup 
from pywinauto import Desktop

# PERSONAL PACKAGES
from app.helper.errors.base import ErrorBase
from app.models.descarga_result import DescargaResult

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import cleanup_download_dir, delete_download_dir, process_files, random_wait, ServiciosNEO, common_rules
from app.models.mailExtractionModel import ExtractionResponse
from typing import Dict, Any

class RobotDgt:
    def __init__(self, cliente: str, task_id: str, execution_id: str, date: str, log_queue: Queue, module="Descargas"):
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
        self.sede = 'dev' # 'dgt'
        self.log_queue = log_queue
        self.download_path = None
        self.notification_date = None
        # self._log(logging.INFO, self.task_id, 'Pending', f"{self.__class__.__name__} initialized for client {cliente} with task ID {task_id} on date {date}")
    
    def _log(self, level: int | str, task_id: str, result: str, message: str) -> None:
        self.log_queue.put({
            "module": self.module,
            "cliente": self.cliente,
            "task_id": task_id,
            "class_name": self.class_name,
            "level": level,
            "result": result,
            "message": message
        })
        
    def _login_dgt(self, driver):
        try:            
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/form/div/div[2]/a'))
            ).click()
            
            xpaths = [
                '//*[@id="nombreForm"]/div[2]',
                '//*[@id="listadoNotificacionesForm"]'
            ]

            error_paths = [
                '//*[@id="main-frame-error"]',
                '//*[@id="contenidoSSO"]/div[2]/p'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:
                try:
                    try:
                        for error_path in error_paths:
                            error = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, error_path))
                            )
                            if error:
                                self._log(logging.DEBUG, self.task_id, 'Pending', f"Error page found: {error_path}")
                                break
                    except Exception as e:
                        error = None
                        self._log(logging.DEBUG, self.task_id, 'Pending', f"No error page found: {e}")


                    if error:
                        self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, 'Error al procesar la solicitud de login')))
                        return False
                    else:
                        for xpath in xpaths:
                            try:
                                element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, xpath))
                                )
                                if element:
                                    self._log(logging.DEBUG, self.task_id, 'Success', f"Login exitoso: {xpath} encontrado.")
                                    return True
                            except Exception as e:
                                self._log(logging.DEBUG, self.task_id, 'Pending', f"No se encontró el elemento {xpath}: {e}")
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al esperar el elemento: {e}")
                    random_wait(wait_type='MEDIUM', wait=True)
                    continue

            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, 'Timeout al esperar el login')))
            return False
        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, e)))
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True) 

    def getNotifications(self, notification_data :  Dict[str, Any]) -> Dict[str, DescargaResult] | None:
        notifications = sorted(
            notification_data['notificaciones'],
            key=lambda n: n.get('date') or n.get('timestamp'),
            reverse=True
        )
        self.task_id = notifications[0]['message_key'] 
        if not notification_data or not notifications :
            self._log(logging.ERROR, self.task_id, 'Failure', "No notifications provided.")
            return None

        if not isinstance(notifications, list) or len(notifications) == 0:
            self._log(logging.ERROR, self.task_id, 'Failure', "Notifications should be a list of dictionaries.")
            return None

        portalLink = 'https://sedeweb.dgt.gob.es/WEB_NTRA_CONSULTA/listadoNotificaciones.faces'
        # 'https://sede.dgt.gob.es/es/multas/direccion-electronica-vial/'
        response = {}

        # Crear una carpeta temporal para el perfil de usuario
        temp_profile = tempfile.mkdtemp(prefix="dgt_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=portalLink,
            module="Descargas",
            execution_id = self.execution_id,
            log_dir="logs/descargas",
            filename=f"descargas_{self.date}",
            cliente=self.cliente,
            task_id = self.task_id,
            site=self.sede
        )
        driver, self.download_path = driver_setup.setup_chrome_driver_descargas() 
        random_wait(wait_type='LONG', wait=True)

        desc = False
        try: 
            # Login to the DEHU portal
            login = self._login_dgt(driver)

            if login:                
                pre_response = {}
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="notificacionesBusquedaForm:notificaciones"]'))
                ).click()

                random_wait(wait_type='LONG', wait=True)
                
                cleanup_download_dir(self.download_path, self.sede, self._log)

                # Wait for up to 60 seconds for the notification list to load
                end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)
                while time.time() < end_time:
                    try:
                        notification_list = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="listadoNotificacionesForm:resultado1"]'))
                        )
                        if notification_list:
                            self._log(logging.DEBUG, self.task_id, 'Success', "Notification list loaded successfully.")
                            break
                    except Exception as e:
                        # https://sedeapl.dgt.gob.es:9443/WEB_NTRA_CONSULTA/listadoNotificacionesIdiomaPostback.faces?idioma=es
                        driver.get('https://sedeweb.dgt.gob.es/WEB_NTRA_CONSULTA/listadoNotificaciones.faces')
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al cargar la página de notificaciones: {e}")
                        random_wait(wait_type='LONG', wait=True)  # Wait before retrying
                            
                random_wait(wait_type='LONG', wait=True)
                try:
                    # Fix: Use the first notification as reference for timestamp if available
                    notification = notifications[0] if notifications else {}
                    timestamp = notification.get('date') or notification.get('timestamp')
                    descarga_especial = notification_data.get('aviso_especial', None)
                    pre_response = {}
                    fecha = None
                    last_fecha = None
                     
                    while True:
                        try:
                            error_element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="notificacionesBusquedaForm"]/div[5]/div/div/div'))
                            )
                        except Exception:
                            error_element = None

                        if error_element and 'Error de la aplicación' in error_element.text:
                            self._log(logging.INFO, self.task_id, 'Pending', "Error al cargar la sede: Se ha producido un error en la página. Recargando...")
                            driver.refresh()  # Reload the page
                            random_wait(wait_type='MEDIUM', wait=True)  # Wait before retrying
                        else:
                            break  
                    
                    try:
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="notificacionesBusquedaForm"]/div[4]/div/div/div[2]/div/div[2]/input'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)

                        filter_date = timestamp.strftime("%d/%m/%Y")
                        
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="notificacionesBusquedaForm:fec_iniInputDate"]'))
                        ).send_keys(filter_date)
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="notificacionesBusquedaForm:fec_finInputDate"]'))
                        ).send_keys(filter_date)

                        random_wait(wait_type='MEDIUM', wait=True)

                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="notificacionesBusquedaForm:Buscar"]'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)

                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al filtrar por fecha: {e}")
                        return None


                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '//*[@id="listadoNotificacionesForm:resultado1"]'))
                    )

                    notifications_rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '//*[@id="listadoNotificacionesForm:resultado1"]/div'))
                    )

                    try:
                        paginator_element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="paginadorComponente"]'))
                        )
                        paginator_text = paginator_element.text
                        # Extract current page and total records from paginator text
                        # Example paginator_text: "Registro 1 al 15 de 113"
                        match = re.search(r'Registro\s+(\d+)\s+al\s+(\d+)\s+de\s+(\d+)', paginator_text)
                        if match:
                            n_per_page = int(match.group(2))
                            total_records = int(match.group(3))
                        else:
                            n_per_page = len(notifications_rows)
                        match = re.search(r'de\s+(\d+)', paginator_text)
                        total_records = int(match.group(1)) if match else None
                        self._log(logging.DEBUG, self.task_id, 'Success', f'Paginador text: {paginator_text}')
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error getting paginator text")
                        total_records = len(notifications_rows)  
                        n_per_page = 15
                    

                    # Inicialización segura de variables fuera del bucle
                    self.task_id = str(notifications[0].get('message_key')) if notifications else f"id-notifications-0"
                    descarga_result = None

                    pages = (total_records // n_per_page) + (1 if total_records % n_per_page > 0 else 0)

                    for page in range(0, pages):
                        notifications_rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_all_elements_located((By.XPATH, '//*[@id="listadoNotificacionesForm:resultado1"]/div'))
                        )
                        # //*[@id="listadoNotificacionesForm:resultado1"]/div[1]
                        for index, row in enumerate(notifications_rows, start=0):
                            row = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, f'//*[@id="listadoNotificacionesForm:resultado1"]/div[{index+1}]'))
                            )
                            try:
                                # //*[@id="listadoNotificacionesForm:resultado1"]/div[50]
                                cleanup_download_dir(self.download_path, self.sede, self._log)                                     
                                descarga_result = DescargaResult(
                                    org=None,
                                    title=None,
                                    disposition_date=None,
                                    desc="NO",
                                    status=DescargaResult.StatusEnum.PENDING,
                                    message=None,
                                    expediente=None,
                                )
                                try:
                                    if self.task_id in pre_response:
                                        if notifications:
                                            if notifications[0].get("message_key") not in pre_response:
                                                notif = notifications.pop(0)
                                                self.task_id =str(notif.get('message_key'))
                                                timestamp = notif.get('date') or notif.get('timestamp')
                                                if timestamp:
                                                    try:
                                                        if isinstance(timestamp, datetime):
                                                            formatted_date = timestamp.strftime("%Y%m%d")
                                                        else:
                                                            try:
                                                                formatted_date = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S").strftime("%Y%m%d")
                                                            except Exception:
                                                                try:
                                                                    formatted_date = datetime.strptime(timestamp, "%Y-%m-%d").strftime("%Y%m%d")
                                                                except Exception:
                                                                    formatted_date = timestamp
                                                        self.notification_date = formatted_date
                                                    except Exception:
                                                        pass                                
                                            else:
                                                self.task_id = f"id-notifications-{index + ((page)*n_per_page)}"
                                        else:
                                            self.task_id = f"id-notifications-{index + ((page)*n_per_page)}"
                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al obtener el task_id")
                                    self.task_id = f"id-notifications-{index + ((page)*n_per_page)}"
                                                                    
                                if (index+1) % 4 == 0:
                                    driver.execute_script(f"window.scrollBy(0, 200);")
                                
                                fecha = row.find_element(By.XPATH, './/div[3]/div').text
                                try:                                            
                                    fecha_row_dt = datetime.strptime(fecha, "%d/%m/%y %H:%M:%S")
                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error parsing fecha '{fecha}'")
                                    continue
                                    
                                if timestamp:
                                    if isinstance(timestamp, str):
                                        try:
                                            timestamp_dt = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
                                        except Exception as e:
                                            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error parsing timestamp '{timestamp}'")
                                            continue
                                    else:
                                        timestamp_dt = timestamp

                                if last_fecha is not None:                                                                                                              
                                    try:
                                        last_fecha_dt = datetime.strptime(last_fecha, "%d/%m/%y %H:%M:%S")
                                    except Exception as e:
                                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error parsing last_fecha '{last_fecha}'")
                                
                                self._log(logging.DEBUG, self.task_id, 'Success', f"Task ID: {self.task_id}, Fecha encontrada: {fecha_row_dt}, Timestamp: {timestamp_dt}, Last Fecha: {last_fecha}, Index: {index + ((page)*n_per_page)}")

                                # Skip this row if it's after the reference date
                                # EXAMPLE: Task ID: 289114, Fecha encontrada: 2025-07-22 06:51:55, Timestamp: 2025-07-22 02:58:25, Last Fecha: 22/07/25 06:51:55, Index: 50
                                if (last_fecha is None and fecha_row_dt > timestamp_dt) or (last_fecha is not None and (fecha_row_dt >= last_fecha_dt or fecha_row_dt > timestamp_dt)):
                                    continue
                                                                

                                read = row.find_element(By.XPATH, './/div[2]/span')
                                if any(status in read.text for status in ['Leída', 'Caducada', 'Rechazada']) and descarga_especial and descarga_especial.lower() == 'no descargar leídas':
                                    self._log(logging.DEBUG, self.task_id, 'Success', f"Notificación {index+1} ya leída o caducada. No se descarga por aviso especial.")
                                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                                    descarga_result.message = f"Notificación {index + ((page)*n_per_page)} ya leída o caducada. No se descarga por aviso especial."
                                    descarga_result.disposition_date = fecha
                                    descarga_result.desc = "SI"
                                    pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                                    continue

                                if any(status in read.text for status in ['Leída', 'Caducada', 'Rechazada']):
                                    self._log(logging.DEBUG, self.task_id, 'Success', f"Notificación {index+1} ya leída o caducada.")
                                    desc = True
                                else:
                                    desc = False    

                                descarga_result.disposition_date = fecha
                                
                                try:
                                    WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                        EC.element_to_be_clickable((By.XPATH, f'//*[@id="listadoNotificacionesForm:resultado1:{index}:desplegar"]'))
                                    ).click()

                                    random_wait(wait_type='MEDIUM', wait=True)                                    
                                    
                                    descarga_result.title = row.find_element(By.XPATH, './/div[1]/div[4]').text
                                    descarga_result.org = row.find_element(By.XPATH, './/div[1]/div[2]').text
                                    concepto = row.find_element(By.XPATH, './/div[1]/div[4]').text
                                    
                                    expediente_match = re.search(r"(?:Expdt|Expediente(?: Sancionador)?):?\s*([\d/]+)", concepto)
                                    expediente = expediente_match.group(1).replace("\\", "_").replace("/", "_") if expediente_match else None
                                    if expediente is None:
                                        try:
                                            expediente_span = WebDriverWait(row, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, f'.//div[4]/span[8]'))
                                            )
                                            expediente_text = expediente_span.text.strip()
                                            expediente = expediente_text if expediente_text else None
                                        except Exception:
                                            expediente = None

                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al obtener el expediente")
                                    expediente = None

                                # Convert fecha to datetime and compare with timestamp or last_fecha if available
                                descarga_result.expediente = expediente

                                # Locate the dropdown dynamically
                                try:
                                    dropdown = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, f'//*[@id="listadoNotificacionesForm:resultado1:{index}:select{"LE" if desc else "PD"}"]'))
                                    )
                                    dropdown.click()
                                    random_wait(wait_type='MEDIUM', wait=True)  # Wait for the dropdown to be clickable
                                    for option in dropdown.find_elements(By.TAG_NAME, 'option'):
                                        if option.get_attribute('value') == 'LE' and option.text.strip().lower() == 'leer':
                                            option.click()
                                            break

                                    button = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                        EC.element_to_be_clickable((By.XPATH, f'//*[@id="listadoNotificacionesForm:resultado1"]/div[{index+1}]/div[3]/input[2]'))
                                    )
                                    button.click()
                                except Exception as e:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al seleccionar opcion en el dropdown: {e}")
                                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                                    descarga_result.message = f"⚠️ Error al seleccionar opcion en el dropdown"
                                    pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                                    continue

                                
                                if not desc:
                                    try: 
                                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                            EC.element_to_be_clickable((By.XPATH, f'//*[@id="formFirma:botonFirmar"]'))
                                        ).click()

                                        random_wait(wait_type='MEDIUM', wait=True)  
                                    except Exception as e:
                                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al firmar la notificación: {e}")
                                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                                        descarga_result.message = f"⚠️ Error al firmar la notificación."
                                        pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                                        continue
                                            
                        
                                descarga_result.desc = "SI" if desc else "NO"

                                start_time = time.time()
                                # Set a timeout for the download click loop
                                timeout = random_wait(wait_type='XXX_LONG', wait=False)
                                while time.time() - start_time < timeout:
                                    try:
                                        # Bring the Chrome window to the foreground
                                        windows = Desktop(backend="uia").windows()                    
                                        
                                        for win in windows:
                                            if 'NOSTRA' in win.window_text():                        
                                                win.set_focus()

                                        random_wait(wait_type='MEDIUM', wait=True)  # Wait for the window to be focused

                                        # Wait for the iframe element to be present
                                        iframe = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="principal"]/div[2]/div/div[2]/div[3]/div/iframe'))
                                        )

                                        # Get the location and size of the iframe
                                        location = iframe.location
                                        size = iframe.size

                                        # Calculate the midpoint in pixels
                                        midpoint_x = int(location['x'] + size['width'] / 2)
                                        midpoint_y = int(location['y'] + 135 + size['height'] / 2)

                                        # Move the mouse to the midpoint and perform a right-click
                                        pyautogui.moveTo(midpoint_x, midpoint_y)
                                        pyautogui.click(button='left')

                                    except Exception as e:
                                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error performing click in download button: {e}")
                                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                                        descarga_result.message = f"⚠️ Error performing click in download button."   
                                        pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                                        continue
                                    finally:
                                        random_wait(wait_type='LONG', wait=True)  # Wait for the download to complete
                                        try:
                                            files = glob.glob(os.path.join(self.download_path, "*"))
                                            if files:
                                                files.sort(key=os.path.getmtime, reverse=True)
                                                last_file = files[0]
                                                break
                                        except Exception as e:
                                            continue

                            
                                processed_file, expediente = process_files(self.download_path, self.task_id, descarga_result.to_dict(), self.cliente, self.date, self.notification_date, self._log)

                                if processed_file:
                                    descarga_result.status = DescargaResult.StatusEnum.SUCCESS
                                    descarga_result.expediente = expediente
                                    descarga_result.message = f"Notificación procesada correctamente: {index + ((page)*n_per_page)}"
                                    descarga_result.file = processed_file
                                else:
                                    self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando archivo para notificacion {index + ((page)*n_per_page)}")
                                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                                    descarga_result.message = f"Error procesando archivo para notificacion {index + ((page)*n_per_page)}"
                                    pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                                    continue

                                pre_response[self.task_id] = descarga_result.to_dict()
                            except Exception as e:
                                self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando notificacion {index + ((page)*n_per_page)}")
                                descarga_result.status = DescargaResult.StatusEnum.ERROR
                                descarga_result.message = f"Error procesando notificacion {index + ((page)*n_per_page)}."
                                pre_response[f"id-notifications-{index + ((page)*n_per_page)}"] = descarga_result.to_dict()
                            finally:
                                if pre_response.get(self.task_id) and self.task_id != "post-notifications" and "id-notifications" not in self.task_id:
                                    response[self.task_id] = DescargaResult.from_dict(pre_response[self.task_id])
                                
                                if descarga_result.status == DescargaResult.StatusEnum.SUCCESS:
                                    self._log(logging.INFO, self.task_id, 'Success', f"Notificación procesada correctamente {self.task_id}: {descarga_result.to_dict()}")
                                    if descarga_result.desc == "SI" :
                                        driver.back()
                                    else:
                                        driver.back()
                                        random_wait(wait_type='MEDIUM', wait=True)
                                        driver.back()
                                        random_wait(wait_type='LONG', wait=True)

                                    self._log(logging.INFO, self.task_id, 'Success', f"Notificación {index + ((page)*n_per_page)} procesada correctamente.")

                        try:
                            next_button = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="paginadorComponente"]/input[3]'))
                            )
                            next_button.click()
                            last_fecha = fecha

                            random_wait(wait_type='MEDIUM', wait=True)
                        except Exception as e:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al pasar de página en el paginador")
                            continue
                            
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, 'Failure', f"Error procesando notificaciones: {e}")
                    return None
     
            else:
                self._log(logging.ERROR, self.task_id, 'Failure', "Error en login")
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
        """Extract specific elements from the provided HTML content."""
        if not body_html:
            self._log(logging.ERROR, self.task_id, 'Failure', "body_html cannot be None or empty")
            raise ValueError("body_html cannot be None or empty")
        try:
            soup = BeautifulSoup(body_html, 'html.parser')

            # Extract the identifier
            identifier_element = soup.find('h2', style='background: white')
            identificador = None
            if identifier_element:
                identifier_text = identifier_element.get_text(strip=True)
                identificador = re.search(r'\b[A-Z0-9]+\b', identifier_text).group(0) if identifier_text else None
                # identifier = identifier_text.split()[-1]  # Extract the last word (e.g., B67047688)

            # Extract the link
            link_element = soup.find('a', href=True, string='https://sede.dgt.gob.es/')
            link = link_element['href'] if link_element else None

            self._log(logging.INFO, self.task_id, 'Success', f"Extracción completada para {self.cliente} - {identificador}")

            # Return the extracted elements in a dictionary
            return ExtractionResponse(
                client_name=None,
                expediente=None,
                org = "DGT",
                identificador=identificador,
                link=link
            )
        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error extracting fields: {e}")
            raise KeyError(f"⚠️ Error extracting fields: {e}")