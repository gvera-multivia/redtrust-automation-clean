import logging
from queue import Queue
import time, os, shutil, tempfile, sys, re
from typing import Any, Dict, List, Optional

# THIRD PARTY PACKAGES
import uuid
import pyautogui
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# PERSONAL PACKAGES - UTILS
from database.descargas.database_descargas import DescargaDatabase
from app.helper.errors.base import ErrorBase
from app.helper.errors.robot_descargas import ErrorRobotDescargas
from app.models.descarga_result import DescargaResult
from app.utils.setup import WebDriverSetup
from app.models.mailExtractionModel import ExtractionResponse
from app.utils.utils import DESCARGA_ESPECIAL, ServiciosNEO, cleanup_download_dir, common_rules, delete_download_dir, process_files, random_wait
from datetime import datetime

class RobotDehu:
    def __init__(self, cliente: str, task_id: str, execution_id: str, date: str, log_queue:Queue, db_manager: DescargaDatabase, module="Descargas" ):
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
        self.module = module
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.cliente = cliente
        self.task_id = task_id
        self.execution_id = execution_id
        self.date = date
        self.log_queue = log_queue
        self.database_manager = db_manager
        self.sede = 'dehù'
        self.download_path = None
        self.notification_date = None
        self.portalLink = None
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

    def check_web_error(self, driver: webdriver) -> bool:
        try:
            # Check for main-frame-error element
            error_element = driver.find_elements(By.XPATH, '//*[@id="main-frame-error"]')
            if error_element:
                self._log(logging.ERROR, self.task_id, "Failure", "Main frame error detected on the page.")
                return True
            return False
        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"Error checking for web error: {e}")
            return False

    def _check_download(self, download_path: str) -> bool:
        try:
            random_wait(wait_type='MEDIUM', wait=True)            
            if not download_path:
                self._log(logging.ERROR, self.task_id, 'Failure', "DOWNLOAD_PATH is not set in the environment variables.")
                raise FileNotFoundError("DOWNLOAD_PATH do not exist or is not set in the environment variables.")                                

            regex_pattern = r"\b\d{8}\s+CL\s+\d{5}\s+EXP\s+\S+\s+(SI|NO)\s+DES\b"

            # Get the two most recent files in the directory (skip directories)
            files = sorted(
                (
                    os.path.join(download_path, f)
                    for f in os.listdir(download_path)
                    if os.path.isfile(os.path.join(download_path, f))
                ),
                key=os.path.getmtime,
                reverse=True
            )[:2]

            if not files:
                self._log(logging.WARNING, self.task_id, 'Failure', "No files found in the download directory.")
                raise FileNotFoundError()

            non_matching_file = next(
                (file for file in files if not re.match(regex_pattern, os.path.basename(file))),
                None
            )

            if non_matching_file:
                # Only consider files, skip directories (even if named like 'revisar')
                if os.path.isfile(non_matching_file):
                    self._log(logging.INFO, self.task_id, 'Pending', f"Found a file not matching the pattern: {non_matching_file}")
                return True  
            else:
                self._log(logging.ERROR, self.task_id, 'Failure', "No file found that does not match the pattern.")
                raise ValueError()
            
        except (ValueError, FileNotFoundError) as e:
            return False
        except Exception as e:
            return False

    def _check_on_spinner(self, driver: webdriver) -> None:
        end_time = time.time() + random_wait('LONG', wait=False)  # Check spinner for up to 20 seconds
        while time.time() < end_time:
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/lib-spinner/dnt-spinner//div/slot/div'))
                )
                
            except Exception as e:
                random_wait(wait_type='MEDIUM', wait=True)
                break

    def handle_descarga_especial(self, descarga_especial: str, descarga_result: DescargaResult, 
                                expediente: str, title: str, org: str, notifications: List[Dict]) -> bool:
        """
        Maneja todos los avisos especiales de descarga de forma unificada para DEHU.
        
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
            """Verifica si una notificación es de tráfico basándose en patrones de DEHU"""
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
                return False
        
        # Procesar cada tipo de aviso especial
        if aviso == "no descargar nada":
            return log_and_update_status(14)
        
        elif aviso == "no descargar leídas":
            if descarga_result.desc == "SI":
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat":
            if (title and "Notificación administrativa" in title and 
                org and "Agencia Estatal de Administración Tributaria" in org):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, ni tgss":
            if (title and org and (
                ("Notificación administrativa" in title and 
                 "Agencia Estatal de Administración Tributaria" in org) or
                ("Tesoreria General de la Seguridad Social" in org) or
                ("Organismo Estatal Inspección de Trabajo y Seguridad Social" in org))):
                return log_and_update_status(8)
        
        elif aviso == "no descargar aeat, si tráfico":
            # Solo aplicar si es notificación AEAT
            if (title and "Notificación administrativa" in title and 
                org and "Agencia Estatal de Administración Tributaria" in org):
                # Si es tráfico, no saltar (continuar procesando)
                if is_traffic_notification():
                    return False
                else:
                    return log_and_update_status(8)
            # Si no es AEAT, no aplicar el filtro
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
    
    def _login_dehu(self, driver: WebDriverSetup, portalLink: str) -> bool:
        self._check_on_spinner(driver)

        end_time = time.time() + 30  # Retry for 30 seconds
        while time.time() < end_time:
            try:
                WebDriverWait(driver, random_wait('X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/div[1]/div/app-public-view/dnt-hero/div/div/dnt-button'))
                ).click()

                random_wait(wait_type='MEDIUM', wait=True)
                
                if self.check_web_error(driver):
                    self._log(logging.ERROR, self.task_id, 'Failure', "Web error detected during login navigation.")
                    return False
                
                self._check_on_spinner(driver)

                end_click_time = time.time() + 10  # Try for up to 10 seconds
                while time.time() < end_click_time:
                    try:
                        WebDriverWait(driver, random_wait('X_LONG', wait=False)).until(                                                                                       
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        break  # Exit the loop if the click is successful
                    except Exception as e:
                        random_wait(wait_type='SHORT', wait=True)  # Wait before retrying

                # Definir los elementos a verificar antes de salir
                xpaths = [
                    '/html/body/app-root/app-notifications',
                    '/html/body/app-root/app-comunications',
                    '/html/body/app-root/div[1]/div/app-home-view'                    
                ]
                random_wait(wait_type='X_LONG', wait=True)
                self._check_on_spinner(driver)
                # Check if the XPath exists in the HTML
                for xpath in xpaths:
                    try:
                        if WebDriverWait(driver, random_wait('X_LONG')).until(EC.presence_of_element_located((By.XPATH, xpath))):
                            random_wait(wait_type='MEDIUM', wait=True)
                            return True
                    except Exception as e:
                        self._log(logging.DEBUG, self.task_id, 'Pending', f"⚠️ Error checking XPath {xpath}: {e}")
                        continue

                error_paths = [
                    '//*[@id="wrap"]/div/div/span/img',
                    '//*[@id="sub-frame-error"]',
                    '//*[@id="main-frame-error"]'
                    '//*[@id="cuerpo_central_menu"]/p[1]'
                    '/html/body/h1'
                ]

                if self.check_web_error(driver):
                    self._log(logging.ERROR, self.task_id, 'Failure', "Web error detected during login navigation.")
                    return False

                error = any(driver.find_elements(By.XPATH, path) for path in error_paths)
                reload = driver.find_elements(By.XPATH, '//*[@id="id-main"]/div/div/div/div/div[2]/div[1]/p[2]/button')

                if error:
                    try:
                        if not 'No se encuentra disponible' in error.text:
                            continue
                        elif not 'Proxy error' in error.text:
                            continue
                        driver.execute_script("window.history.go(-1);")
                        random_wait(wait_type='MEDIUM', wait=True)
                        driver.execute_script("location.reload();")
                        random_wait(wait_type='MEDIUM', wait=True)
                        self._check_on_spinner(driver)
                        WebDriverWait(driver, random_wait('X_LONG')).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al recargar la página: {e}")
                        driver.get(self.portalLink) 
                        random_wait(wait_type='LONG', wait=True)
                    continue
                elif reload:
                    self._log(logging.DEBUG, self.task_id, 'Pending', f"Botón de recarga detectado. Intentando hacer clic para reintentar.")
                    try:
                        self._check_on_spinner(driver)
                        WebDriverWait(driver, random_wait('X_LONG')).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                        ).click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al hacer clic en el botón de recarga: {e}")
                        driver.get(self.portalLink) 
                        random_wait(wait_type='LONG', wait=True)
                    continue

            except Exception as e:
                self._log(logging.ERROR, self.task_id, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, e[50:])))
        self._log(logging.ERROR, self.task_id, 'Failure', "Login fallido: No se encontraron los elementos esperados.")
        return False

    def _handle(self, driver:webdriver, notification: Dict, idNotificacion: str, descarga_result: DescargaResult, services: str | List, descarga_especial: Optional[str], path: str) -> DescargaResult | Dict | None:
        try:
            # STEP 1: Check if there are pending notifications/communications
            self._check_on_spinner(driver)
            xpath_check = {   
                "communications": '/html/body/app-root/div[1]/div/app-communications-view/div/app-communications-list/div/p[2]',
                "notifications": '/html/body/app-root/div[1]/div/app-notifications-view/div/app-notifications-list/div/p[2]'
            }[path]

            random_wait('LONG', wait=True)

            try:
                any_rows_text = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, xpath_check))
                ).text
                
                message_text = {
                    "notifications": "Actualmente no dispones de notificaciones pendientes",
                    "communications": "Actualmente no dispones de comunicaciones emitidas"
                }[path]

                any_rows = message_text not in any_rows_text

            except Exception:
                self._log(logging.WARNING, self.task_id, 'Pending', str(ErrorBase.ErrorXpathElemento(xpath_check)))
                any_rows = True

            if not any_rows: 
                if path == "communications":
                    self._log(logging.ERROR, self.task_id, 'Failure', f"No hay comunicaciones emitidas pendientes para idNotificacion: {idNotificacion}.")
                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                    descarga_result.message = f"No hay comunicaciones emitidas pendientes para idNotificacion: {idNotificacion}."                        
                    return descarga_result
                elif path == "notifications":
                    driver.get(f'https://dehu.redsara.es/es/notifications?realized=true')
                    self._check_on_spinner(driver)
                    random_wait('LONG', wait=True)
                    path = "notifications-realized"
                    descarga_result.desc = "SI"
                    any_rows = True  # Force to check realized notifications
            

            # STEP 2: Filter notifications/communications by idNotificacion and find the row in the corresponding table
            if any_rows:
                filtered = self._filter_notifications_by_id(
                    driver=driver,
                    idNotificacion=idNotificacion,
                    path=path
                )
                
                if filtered:
                    # STEP 2.1: Check if the row corresponds with the notification to download
                    descarga_result.desc = "NO" if path == "notifications" else descarga_result.desc
                    return self._process_notifications(
                        driver, notification, idNotificacion, descarga_result, services, descarga_especial,path=path
                    )
                else:
                    # STEP 2.2: If not found, try in the other section or return error
                    if path == "communications":
                        self._log(logging.ERROR, self.task_id, 'Failure', f"No hay comunicaciones emitidas pendientes para idNotificacion: {idNotificacion}.")
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = f"No hay comunicaciones emitidas pendientes para idNotificacion: {idNotificacion}."                        
                        return descarga_result
                    
                    elif path == "notifications":
                        driver.get(f'https://dehu.redsara.es/es/notifications?realized=true')
                        self._check_on_spinner(driver)
                        random_wait('LONG', wait=True)
                        path = "notifications-realized"
                        filtered = self._filter_notifications_by_id(
                            driver=driver,
                            idNotificacion=idNotificacion,
                            path=path
                        )

                        if not filtered:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"No hay notificaciones realizadas para idNotificacion: {idNotificacion}.")
                            descarga_result.status = DescargaResult.StatusEnum.ERROR
                            descarga_result.message = f"No hay notificaciones realizadas para idNotificacion: {idNotificacion}."                        
                            return descarga_result
                        
                        
                    elif path == "notifications-realized": 
                        self._log(logging.ERROR, self.task_id, 'Failure', f"No hay notificaciones realizadas para idNotificacion: {idNotificacion}.")
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = f"No hay notificaciones realizadas para idNotificacion: {idNotificacion}."                        
                        return descarga_result
                    
                    return self._process_notifications(
                        driver, notification, idNotificacion, descarga_result, services, descarga_especial,
                        path=path
                    )
            else:
                self._log(logging.ERROR, self.task_id, 'Failure', f"No hay notificaciones/comunicaciones pendientes para idNotificacion: {idNotificacion}.")
                descarga_result.status = DescargaResult.StatusEnum.ERROR
                descarga_result.message = f"No hay notificaciones/comunicaciones pendientes para idNotificacion: {idNotificacion}."
                return descarga_result

                
        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error handling {path}: {e}")
            return None
    
    def _filter_notifications_by_id(self, driver: webdriver, idNotificacion: str | int, path: str) -> None:
        try:
            driver.execute_script("window.scrollBy(0,300);")

            # STEP 1: Click on the select to open the dropdown
            js_selector_map = {
                "notifications": (
                    "document.querySelector('#pane-0 > div > app-notification-filter-detail > form > "
                    "div > app-dinamic-field-filter > div > div.col-xs-12.col-sm-4.col-md-3.col-lg-3.min-height-field > "
                    "dnt-select')"
                    ".shadowRoot.querySelector('div > dnt-input')"
                    ".shadowRoot.querySelector('fieldset > div.dnt-input__content > div > input').click()"
                ),
                "notifications-realized": (
                    "document.querySelector('#pane-1 > div > app-notification-filter-detail > form > "
                    "div > app-dinamic-field-filter > div > div.col-xs-12.col-sm-4.col-md-3.col-lg-3.min-height-field > "
                    "dnt-select')"
                    ".shadowRoot.querySelector('div > dnt-input')"
                    ".shadowRoot.querySelector('fieldset > div.dnt-input__content > div > input').click()"
                ),
                "communications": (
                    "document.querySelector('body > app-root > div.content-page > div > app-communications-view >"
                    "div > app-communications-filter-view > div > div > form > div.form-wrapper >"
                    "app-communication-dynamic-filter > div > div.col-xs-12.col-sm-4.col-lg-3.dnt-mt-4.dnt-flex-grow > dnt-select')"
                    ".shadowRoot.querySelector('div > dnt-input')"
                    ".shadowRoot.querySelector('fieldset > div.dnt-input__content > div > input').click()"
                )
            }

            try:
                js_expr = js_selector_map[path]
                driver.execute_script(js_expr)
            except Exception as e:
                self._log(logging.DEBUG, self.task_id, 'Pending', f"⚠️ Error abriendo el dropdown del filtro en {path} via JS.")
                raise e
                

            # STEP 2: Select "Identificador" option from the dropdown
            xpath_selector = { 
                "communications": '/html/body/app-root/div[1]/div/app-communications-view/div/app-communications-filter-view/div/div/form/div[1]/app-communication-dynamic-filter/div/div[1]/dnt-select/dnt-option',
                "notifications-realized": '//*[@id="pane-1"]/div/app-notification-filter-detail/form/div/app-dinamic-field-filter/div/div[1]/dnt-select/dnt-option',
                "notifications": '//*[@id="pane-0"]/div/app-notification-filter-detail/form/div/app-dinamic-field-filter/div/div[1]/dnt-select/dnt-option'
            }

            try:
                selector_elements = WebDriverWait(driver, random_wait('X_LONG')).until(
                    EC.presence_of_all_elements_located((By.XPATH, xpath_selector[path]))
                )

                for select in selector_elements:
                    try:
                        # Execute JS to find and click the 'Identificador' option in one operation
                        clicked = driver.execute_script(
                            """
                                const opt = arguments[0];
                                
                                let text = null;
                                if (opt.shadowRoot) {
                                    const span = opt.shadowRoot.querySelector("div > slot > span");
                                    text = span ? span.textContent.trim() : opt.textContent.trim();
                                } else {
                                    text = opt.textContent.trim();
                                }
                                
                                if (text === 'Identificador') {
                                    try {
                                        if (opt.shadowRoot) {
                                            const span = opt.shadowRoot.querySelector("div > slot > span");
                                            if (span) span.click();
                                        } else {
                                            opt.click();
                                        }
                                        return true;
                                    } catch (e) {
                                        return false;
                                    }
                                }
                                return false;
                            """,
                            select
                        )
                        
                        if clicked:
                            break
                    except Exception:
                        continue

                random_wait('MEDIUM', wait=True)
            
            except Exception as e:
                self._log(logging.WARNING, self.task_id, 'Pending', f"⚠️ Error seleccionando 'Identificador' en el filtro: {e}.")
                raise e
                

            # STEP 3: Input the idNotificacion into the filter input
            try:
                id_input_js_selector = {
                    "notifications-realized": (
                        """
                            const host = document.querySelector(
                                "#pane-1 > div > app-notification-filter-detail > form > div > app-dinamic-field-filter > div > div.col-xs-12.col-sm-8.col-md-7.col-lg-6.dinamic-field-wrapper.min-height-field > div > div > dnt-input"
                            );
                            if (!host) return {result: false, message: 'No host found'};
                            if (!host.shadowRoot) return {result: false, message: 'No shadowroot found'};
                            const input = host.shadowRoot.querySelector("fieldset > div > div.dnt-input__wrap > input");
                            if (!input) return {result: false, message: 'No input found'};
                            input.value = arguments[0];
                            return {result: true, message: 'Input set successfully'};
                        """
                    ),
                    "notifications": (
                        """
                            const host = document.querySelector(
                                "#pane-0 > div > app-notification-filter-detail > form > div > app-dinamic-field-filter > div > div.col-xs-12.col-sm-8.col-md-7.col-lg-6.dinamic-field-wrapper.min-height-field > div > div > dnt-input"
                            );
                            
                            if (!host) return {result: false, message: 'No host found'};
                            if (!host.shadowRoot) return {result: false, message: 'No shadowroot found'};
                            const input = host.shadowRoot.querySelector("fieldset > div > div.dnt-input__wrap > input");
                            if (!input) return {result: false, message: 'No input found'};
                            input.value = arguments[0];
                            return {result: true, message: 'Input set successfully'};
                        """
                    ),
                    "communications": (
                        """
                            const host = document.querySelector(
                                'body > app-root > div.content-page > div > app-communications-view > div > app-communications-filter-view > div > div > form > div.form-wrapper > app-communication-dynamic-filter > div > div.col-xs-12.col-sm-7.col-lg-6.dinamic-field-wrapper > div > div > dnt-input'
                            );

                            if (!host ) return {result: false, message: 'No host found'};
                            if (!host.shadowRoot) return {result: false, message: 'No shadowroot found'};
                            const input = host.shadowRoot.querySelector('fieldset input.dnt-input__inner');
                            if (!input) return {result: false, message: 'No input found'};
                            input.focus();
                            input.value = arguments[0];
                            input.dispatchEvent(new Event('input', { bubbles: true }));
                            input.dispatchEvent(new Event('change', { bubbles: true }));
                            return {result: true, message: 'Input set successfully'};
                        """
                    )
                }

                # Execute the JS snippet which already locates the shadow DOM input and sets its value,
                try:
                    input_set = driver.execute_script(id_input_js_selector[path], str(idNotificacion))
                    id_input = bool(input_set.get('result', False))
                    random_wait('MEDIUM', wait=True)
                except Exception as e:
                    self._log(logging.DEBUG, self.task_id, 'Pending', f"Shadow DOM input not set via JS: {e}")
                
                if not id_input:
                    raise Exception("Shadow DOM input not set via JS")
                    
            except Exception as e:
                self._log(logging.WARNING, self.task_id, 'Pending', f"⚠️ Error accediendo al input de filtro por shadow DOM. Error: {e}.")
                raise e
            
            self._check_on_spinner(driver)

            # STEP 4: Apply the filter by clicking the search button
            search_btn_js_selector = {
                "communications": (
                    """
                        try {
                        var el = document.querySelector('body > app-root > div.content-page > div > app-communications-view > div > app-communications-filter-view > div > div > form > div.form-wrapper.ng-trigger > app-communication-dynamic-filter > div > div:nth-child(3) > div > div > dnt-button');
                        if (!el) return false;
                        var root = el.shadowRoot || el;
                        var btn = root.querySelector('button');
                        if (btn && typeof btn.click === 'function') { btn.click(); return true; }
                        return false;
                        } catch (err) { 
                        return false; 
                        }
                    """
                ),
                "notifications-realized": (
                    """
                        try {
                            var el = document.querySelector('#pane-1 > div > app-notification-filter-detail > form > div > app-dinamic-field-filter > div > div:nth-child(3) > div > div > dnt-button');
                            if (!el) return false;
                                var root = el.shadowRoot || el;
                                var btn = root.querySelector('button');
                                if (btn && typeof btn.click === 'function') { btn.click(); return true; }
                                return false;
                        } catch (err) { 
                            document.querySelector("#id-test").shadowRoot.querySelector("button")
                            return false; 
                        }
                    """
                ),
                "notifications": (
                    """
                        try {
                        var el = document.querySelector('#pane-0 > div > app-notification-filter-detail > form > div > app-dinamic-field-filter > div > div:nth-child(3) > div > div.col-xs-12.col-sm-6.col-lg-4 > dnt-button');
                        if (!el) return false;
                        var root = el.shadowRoot || el;
                        var btn = root.querySelector('button');
                        if (btn && typeof btn.click === 'function') { btn.click(); return true; }
                        return false;
                        } catch (err) { 
                        return false; 
                        }
                    """
                )
            }

            end_time = time.time() + 60  # try for up to 60 seconds
            found = False
            while time.time() < end_time:
                try:
                    clicked = driver.execute_script( search_btn_js_selector[path])
                    if not clicked:
                        raise RuntimeError("JS search button click not performed (element not found in DOM/shadowRoot).")
                        
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, 'Failure', f"Unexpected error clicking search button: {e}")  
                
                self._check_on_spinner(driver)

                # STEP 5: Wait for the results to load
                xpaths_message  = {
                    "notifications": '/html/body/app-root/div[1]/div/app-notifications-view/div/app-notifications-list/div/div/p[1]',
                    "notifications-realized": '/html/body/app-root/div[1]/div/app-realized-notifications-view/div/app-realized-notifications-list/div/div/p[1]',
                    "communications": '/html/body/app-root/div[1]/div/app-communications-view/div/app-communications-list-view/div/div/p[1]'
                }

                xpaths_tables = {
                    "notifications": "//*[@id='tablaNotificacionesPendientes']",
                    "notifications-realized": '//*[@id="tablaNotificacionesRealizadas"]',
                    "communications": "//*[@id='tablaComunicaciones']"
                }

                try:
                    message = WebDriverWait(driver, random_wait('X_LONG')).until(
                        EC.presence_of_element_located((By.XPATH, xpaths_message[path]))
                    ).text

                    if message.strip() == "No hemos encontrado resultados con los términos introducidos." :
                        self._log(logging.DEBUG, self.task_id, 'Pending', f"No se encontraron resultados tras filtrar por ID {idNotificacion} en {path}.")

                        try:
                            WebDriverWait(driver, random_wait('MEDIUM')).until(
                                EC.element_to_be_clickable((By.XPATH, '# /html/body/app-root/div[1]/div/app-communications-view/div/app-communications-filter-view/div/div/form/div[1]/app-communication-dynamic-filter/div/div[3]/div/div[1]/dnt-link'))
                            ).click()

                            random_wait('LONG', wait=True)

                            clicked = driver.execute_script(search_btn_js_selector[path])
                            if not clicked:
                                raise RuntimeError("JS search button click not performed (element not found in DOM/shadowRoot).")
                        except Exception:
                            pass

                        return False
                except Exception:
                    try:
                        WebDriverWait(driver, random_wait('X_LONG')).until(
                            EC.presence_of_element_located((By.XPATH, xpaths_tables[path]))
                        )

                        table_id = {
                            "notifications": "#tablaNotificacionesPendientes",
                            "notifications-realized": "#tablaNotificacionesRealizadas",
                            "communications": "#tablaComunicaciones"
                        }[path]                    
                        
                        # Use JavaScript to find the notification in the table
                        js = """
                            const tableId = arguments[0];
                            const searchId = arguments[1];
                            
                            const table = document.querySelector(tableId);
                            if (!table) return { found: false, reason: 'table_not_found' };
                            
                            const shadowRoot = table.shadowRoot || table;
                            const tbodies = shadowRoot.querySelectorAll('div > div > table > tbody');
                            
                            for (let tbody of tbodies) {
                                const rows = tbody.querySelectorAll('tr');
                                for (let row of rows) {
                                    const idCell = row.querySelector('td:nth-child(3) > div');
                                    if (idCell && idCell.textContent.trim() === searchId) {
                                        return { found: true, reason: 'id_matched' };
                                    }
                                }
                            }
                            
                            return { found: false, reason: 'id_not_found' };
                        """

                        result = driver.execute_script(js, table_id, str(idNotificacion))
                        found = result.get('found', False) if isinstance(result, dict) else False
                        break
                        

                    except  Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error comprobando si la notificación sigue en pendientes para id: {idNotificacion}: {e}")
                        found = False
                
            if found:
                return True
            else:
                try:
                    WebDriverWait(driver, random_wait('MEDIUM')).until(
                        EC.element_to_be_clickable((By.XPATH, '# /html/body/app-root/div[1]/div/app-communications-view/div/app-communications-filter-view/div/div/form/div[1]/app-communication-dynamic-filter/div/div[3]/div/div[1]/dnt-link'))
                    ).click()

                    random_wait('LONG', wait=True)

                    clicked = driver.execute_script(search_btn_js_selector[path])
                    if not clicked:
                        raise RuntimeError("JS search button click not performed (element not found in DOM/shadowRoot).")
                except Exception:
                    pass

                return False
                
                    

        except Exception as e:
            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error applying filter by ID {idNotificacion} on {path}: {e}")
            return False      
            
    def _process_notifications(self, driver : webdriver, notificacion: Dict, idNotificacion : str, descarga_result : DescargaResult,  services: str | List, descarga_especial: Optional[str], path:str) -> DescargaResult | None:
        try:
            random_wait('LONG', wait=True)
            
            try:
                # Use shadow DOM selectors to locate all tbody elements and click the action button
                table_selector = {
                    "notifications": "#tablaNotificacionesPendientes",
                    "notifications-realized": "#tablaNotificacionesRealizadas",
                    "communications": "#tablaComunicaciones"
                }[path] 

                self._check_on_spinner(driver)

                # Use JavaScript to find the notification in the table
                js = """
                    const searchId = arguments[0];
                    const tableSelector = arguments[1]; // replace with CSS selector or id

                    
                    const table = document.querySelector(tableSelector) || document.getElementById(tableSelector.replace(/^#/, ''));
                    if (!table) return { found: false, reason: 'table_not_found' };
                    
                    const shadowRoot = table.shadowRoot || table;
                    const tbodies = shadowRoot.querySelectorAll('div > div > table > tbody');
                    
                    for (let tbodyIndex = 0; tbodyIndex < tbodies.length; tbodyIndex++) {
                        const tbody = tbodies[tbodyIndex];
                        const rows = tbody.querySelectorAll('tr.dnt-table__row');
                        for (let row of rows) {
                            const idCell = row.querySelector('td:nth-child(3) > div');
                            if (idCell && idCell.textContent.trim() === searchId) {
                                const expandBtn = row.querySelector('td.dnt-table__cell.dnt-table__cell--expand > div > dnt-icon');
                                if (expandBtn) {
                                    expandBtn.click();
                                }

                                let identificador = null;
                                let title = null;
                                let organismo = null;
                                let disposition_date = null;
                                let status = null;
                                
                                if (tableSelector === '#tablaNotificacionesPendientes') {
                                    identificador = row.querySelector('td:nth-child(3) > div')?.textContent.trim() || null;
                                    titleElement = row.querySelector('td:nth-child(4) > div');
                                    title = titleElement ? titleElement.getAttribute('data-tooltip') : null;
                                    organismo = row.querySelector('td:nth-child(5) > div')?.textContent.trim() || null;
                                    disposition_date = row.querySelector('td:nth-child(7) > div')?.textContent.trim() || null;                                    
                                    status = null;

                                } else if (tableSelector === '#tablaNotificacionesRealizadas') {
                                    identificador = row.querySelector('td:nth-child(3) > div')?.textContent.trim() || null;
                                    organismo = row.querySelector('td:nth-child(4) > div')?.textContent.trim() || null;
                                    disposition_date = row.querySelector('td:nth-child(7) > div')?.textContent.trim() || null;
                                    status = row.querySelector('td:nth-child(10) > div > dnt-tag')?.textContent.trim() || null;
                                    title = tbody.querySelector("tr.dnt-table__row-expansion > td.dnt-table__cell.dnt-table__cell--expanded.dnt-table__cell--expanded-row > div > div:nth-child(1) > p:nth-child(2)")?.textContent.trim() || null;

                                } else if (tableSelector === '#tablaComunicaciones') {
                                    identificador = row.querySelector('td:nth-child(3) > div')?.textContent.trim() || null;
                                    title = row.querySelector('td:nth-child(4) > div')?.textContent.trim() || null;
                                    organismo = row.querySelector('td:nth-child(5) > div')?.textContent.trim() || null;
                                    disposition_date = row.querySelector('td:nth-child(8) > div')?.textContent.trim() || null;                                
                                    status = row.querySelector('td:nth-child(9) > div > dnt-tag')?.textContent.trim() || null;                                
                                } 
                                
                                return { 
                                    found: true, 
                                    reason: 'id_matched',
                                    tbodyIndex: tbodyIndex + 1,
                                    rowData: {
                                        title: title,
                                        identificador: identificador,
                                        dispositionDate: disposition_date,
                                        organismo: organismo
                                    }
                                };
                            }
                        }
                    }
                    
                    return { found: false, reason: 'id_not_found' };
                """
                try:
                    result = driver.execute_script(js, str(idNotificacion), table_selector)
                    found = result.get('found', False) if isinstance(result, dict) else False
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error localizando la notificación/comunicación para idNotificacion: {idNotificacion} en {path}: {e}")
                    found = False
                    raise e

                self._log(logging.DEBUG, self.task_id, 'Pending',
                    f"Located notification - title: {result.get('rowData', {}).get('title')}, identificador: {result.get('rowData', {}).get('identificador')}, "
                    f"disposition_date: {result.get('rowData', {}).get('dispositionDate')}, organismo: {result.get('rowData', {}).get('organismo')} for idNotificacion: {idNotificacion} in {path}.")

                if found:
                    expediente_valido = False 
                    if path == "communications":
                        row_data = result.get('rowData', {})
                        descarga_result.title = row_data.get('title')
                        descarga_result.identificador = row_data.get('identificador')
                        descarga_result.disposition_date = row_data.get('dispositionDate')
                        descarga_result.org = row_data.get('organismo')
                        descarga_result.desc = "SI" if result.get('status', '').lower() == 'leída' else "NO"

                        # Verificar aviso especial antes de continuar
                        if descarga_especial:
                            should_skip = self.handle_descarga_especial(
                                descarga_especial=descarga_especial,
                                descarga_result=descarga_result,
                                expediente=descarga_result.expediente,
                                title=descarga_result.title,
                                org=None,  # En pendientes no tenemos org aún
                                notifications=[]  # Se pasa lista vacía ya que el update se hace internamente
                            )
                            if should_skip:
                                raise ErrorRobotDescargas.ErrorAvisoEspecial(self.cliente, descarga_especial)
                            
                        # Filtrado por tipo de servicio y validación de expediente
                        if any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services):
                            expediente_valido = True
                            pass
                        elif any(service in ["SUSCRIPCION", "BLINDAJE", "INFONEO"] for service in services):
                            # Itera sobre los servicios y sus reglas regex, comprueba si el expediente cumple alguna
                            for service in services:
                                try:
                                    # Obtiene las reglas para el servicio actual
                                    service_enum = ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")]
                                    service_rules = self.rules.get(service_enum, [])
                                    for rule_key in service_rules:
                                        pattern = common_rules.get(rule_key)
                                        if pattern and descarga_result.expediente and re.match(pattern, descarga_result.expediente):
                                            expediente_valido = True
                                            break
                                    if expediente_valido:
                                        break
                                except Exception:
                                    continue
                            if not expediente_valido:
                                    if notificacion.get('status') in ["Agencia Tributaria", "Pendiente"]:
                                        self.database_manager.update_notification_status(
                                            cliente=self.cliente,
                                            message_key=self.task_id,
                                        )
                                    # raise ValueError(f"El expediente '{descarga_result.expediente}' no cumple ninguna regla regex de los servicios proporcionados.")
                                    raise ErrorRobotDescargas.InvalidServicio({
                                        "message_key": self.task_id,
                                        "identificador": idNotificacion,
                                        "servicio": services,
                                        "expediente": descarga_result.expediente
                                    })
                    
                    elif path == "notifications-realized":
                        row_data = result.get('rowData', {})
                        descarga_result.title = row_data.get('title')
                        descarga_result.identificador = row_data.get('identificador')
                        descarga_result.disposition_date = row_data.get('dispositionDate')
                        descarga_result.org = row_data.get('organismo')
                        descarga_result.desc = "SI" if result.get('status', '').lower() == 'aceptada' else descarga_result.desc

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
                        
                        # Filtrado por tipo de servicio y validación de expediente
                        if any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services):
                            expediente_valido = True
                            pass
                        elif any(service in ["SUSCRIPCION", "BLINDAJE", "INFONEO"] for service in services):
                            # Itera sobre los servicios y sus reglas regex, comprueba si el expediente cumple alguna
                            duda = True
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
                                # Logica para definir si es duda o no
                                if not expediente_valido:
                                    if descarga_result.title.strip() in ["Notificación administrativa"] and descarga_result.org.strip() in ["Agencia Estatal de Administración Tributaria"]:
                                        duda = True
                                    else:
                                        #TODO: implementar logica para deducir si una notificacion es seguro que no es trafico, cuando tiene los servicios BLINDAJE o SUSCRIPCION
                                        duda = False

                                if not expediente_valido and not duda:
                                    if notificacion.get('status') in ["Agencia Tributaria", "Pendiente"]:
                                        self.database_manager.update_notification_status(
                                            cliente=self.cliente,
                                            message_key=self.task_id,
                                        )
                                    # raise ValueError(f"El expediente '{descarga_result.expediente}' no cumple ninguna regla regex de los servicios proporcionados.")
                                    raise ErrorRobotDescargas.InvalidServicio({
                                        "message_key": self.task_id,
                                        "identificador": idNotificacion,
                                        "servicio": services,
                                        "expediente": descarga_result.expediente
                                    })
                            else:
                                # Verificar aviso especial para notificaciones ya leídas
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
                                self._log(logging.INFO, self.task_id, 'Pending', "Procediendo sin conocer el expediente ya que ha sido abierta previamente")
                    
                    elif path == "notifications":
                        row_data = result.get('rowData', {})
                        descarga_result.title = row_data.get('title')
                        descarga_result.identificador = row_data.get('identificador')
                        descarga_result.disposition_date = row_data.get('dispositionDate')
                        descarga_result.org = row_data.get('organismo')

                        # Verificar aviso especial antes de continuar
                        if descarga_especial:
                            should_skip = self.handle_descarga_especial(
                                descarga_especial=descarga_especial,
                                descarga_result=descarga_result,
                                expediente=descarga_result.expediente,
                                title=descarga_result.title,
                                org=None,  # En pendientes no tenemos org aún
                                notifications=[]  # Se pasa lista vacía ya que el update se hace internamente
                            )
                            if should_skip:
                                raise ErrorRobotDescargas.ErrorAvisoEspecial(self.cliente, descarga_especial)
                            
                        # Filtrado por tipo de servicio y validación de expediente
                        if any(service in ["NEOCASH", "MULTINEO", "NEOESTATAL"] for service in services):
                            expediente_valido = True
                            pass
                        elif any(service in ["SUSCRIPCION", "BLINDAJE", "INFONEO"] for service in services):
                            # Itera sobre los servicios y sus reglas regex, comprueba si el expediente cumple alguna
                            for service in services:
                                try:
                                    # Obtiene las reglas para el servicio actual
                                    service_enum = ServiciosNEO[service.replace("-", "").replace("_", "").replace(" ", "")]
                                    service_rules = self.rules.get(service_enum, [])
                                    for rule_key in service_rules:
                                        pattern = common_rules.get(rule_key)
                                        if pattern and descarga_result.expediente and re.match(pattern, descarga_result.expediente):
                                            expediente_valido = True
                                            break
                                    if expediente_valido:
                                        break
                                except Exception:
                                    continue
                            if not expediente_valido:
                                    if notificacion.get('status') in ["Agencia Tributaria", "Pendiente"]:
                                        self.database_manager.update_notification_status(
                                            cliente=self.cliente,
                                            message_key=self.task_id,
                                        )
                                    # raise ValueError(f"El expediente '{descarga_result.expediente}' no cumple ninguna regla regex de los servicios proporcionados.")
                                    raise ErrorRobotDescargas.InvalidServicio({
                                        "message_key": self.task_id,
                                        "identificador": idNotificacion,
                                        "servicio": services,
                                        "expediente": descarga_result.expediente
                                    })
                    
                    try:
                        # Click the action button based on path
                        action_button_selector = {
                            "communications": [
                                # "document.querySelector('#tablaComunicaciones').shadowRoot.querySelector('div > div > table > tbody.dnt-table__row-group.dnt-table__row--expanded > tr.dnt-table__row.dnt-table__row--grouped.dnt-table__row--expanded > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed.dnt-table__cell--expanded > div > app-shared-table-cell-multi-buttons > div > div > dnt-button').shadowRoot.querySelector('button')",
                                "div > div > table > tbody:nth-child(2) > tr.dnt-table__row.dnt-table__row--grouped > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed > div > app-shared-table-cell-multi-buttons > div > div > dnt-button"
                            ],
                            "notifications-realized": [
                                # "document.querySelector('#tablaNotificacionesRealizadas').shadowRoot.querySelector('div > div > table > tbody > tr.dnt-table__row.dnt-table__row--grouped.dnt-table__row--expanded > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed.dnt-table__cell--expanded > div > app-shared-table-cell-multi-buttons > div > div > dnt-button').shadowRoot.querySelector('button')",
                                "div > div > table > tbody > tr.dnt-table__row.dnt-table__row--grouped > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed > div > app-shared-table-cell-multi-buttons > div > div > dnt-button"
                            ],
                            "notifications": [
                                # "document.querySelector('#tablaNotificacionesPendientes').shadowRoot.querySelector('div > div > table > tbody.dnt-table__row-group.dnt-table__row--expanded > tr.dnt-table__row.dnt-table__row--grouped.dnt-table__row--expanded > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed.dnt-table__cell--expanded > div > app-shared-table-cell-multi-buttons > div > div > dnt-button').shadowRoot.querySelector('button')",
                                "div > div > table > tbody:nth-child(2) > tr.dnt-table__row.dnt-table__row--grouped > td.dnt-table__cell.dnt-table__cell--default.dnt-table__cell--fixed > div > app-shared-table-cell-multi-buttons > div > div > dnt-button"
                            ]
                        }[path]

                        try:
                            result = driver.execute_script("""
                                let table_selecter = arguments[0]; 
                                let action_button_selector = arguments[1];                 
                                                        
                                const table = document.querySelector(table_selecter);
                                if (table && table.shadowRoot) {
                                    const buttons = Array.from(
                                        table.shadowRoot.querySelectorAll(
                                            action_button_selector
                                        )
                                    );
                                                        
                                    if (table_selecter === "#tablaNotificacionesPendientes") {                                                       
                                        const acceptButton = buttons.find(button => button.textContent.includes('Aceptar'));
                                        if (acceptButton) {
                                            acceptButton.click();
                                            return true;
                                        } else {
                                            console.warn("Aceptar button not found.");
                                            return false;
                                        }
                                    } else if (table_selecter === "#tablaNotificacionesRealizadas") {
                                        const viewButton = buttons.find(button => button.textContent.includes('Detalle'));
                                        if (viewButton) {
                                            viewButton.click();
                                            return true;
                                        } else {
                                            console.warn("Detalles button not found.");
                                            return false;
                                        }
                                    } else if (table_selecter === "#tablaComunicaciones") {
                                        const readButton = buttons.find(button =>
                                            button.textContent.includes('Leer') || button.textContent.includes('Detalles')
                                        );

                                        if (readButton) {
                                            readButton.click();
                                            return true;
                                        } else {
                                            console.warn("Leer/Detalles button not found.");
                                            return false;
                                        }
                                    }

                                                        
                                } else {
                                    console.warn("Table or shadowRoot not found");
                                    return false;
                                }
                            """, table_selector, action_button_selector)
                        
                        except Exception as e:
                            self._log(logging.ERROR, self.task_id, 'Failure', f"⚠️ Error al hacer click en el botón de acción para idNotificacion: {idNotificacion} en {path}: {e}")
                            raise e

                        if not result:
                            raise RuntimeError("Failed to click Aceptar button in pending notifications table")

                        if path == "notifications" and expediente_valido and descarga_result.desc == "NO":
                            try:
                                random_wait(wait_type='LONG', wait=True)
                                # Click the checkbox to accept the notification
                                try:
                                    clicked_checkbox = driver.execute_script("""
                                        const checkbox = document.querySelector("#pane-0 > app-accept-reject-notification > form > dnt-checkbox");
                                        if (checkbox && checkbox.shadowRoot) {
                                            const input = checkbox.shadowRoot.querySelector("label > span > span.dnt-checkbox__input > input");
                                            if (input) {
                                                input.click();
                                                return true;
                                            }                                            
                                        }
                                        return false;
                                    """)
                                    random_wait(wait_type='SHORT', wait=True)
                                    if not clicked_checkbox:
                                        raise RuntimeError("Checkbox not found in modal")
                                except Exception as e:
                                    self._log(logging.WARNING, self.task_id, 'Pending', f"Could not click checkbox: {e}")
                                    raise e

                                # Find and click the 'Aceptar' button in the modal footer
                                try:
                                    accept_button = driver.execute_script("""
                                        const buttons = Array.from(document.querySelectorAll(
                                            'body > app-root > div.content-page > div > app-pending-notification-detail-view > div > dnt-section > div > app-pending-notification-detail-data > div.modal-footer.dnt-flex.dnt-justify-end.dnt-gap-6.actions.ng-star-inserted > dnt-button'
                                        ));
                                        const btn = buttons.find(b => b.textContent.includes('Aceptar'));
                                        if (btn && !btn.disabled) {
                                            btn.click();
                                            return true;
                                        }
                                        return false;
                                    """)
                                    if not accept_button:
                                        raise RuntimeError("Aceptar button not found or is disabled")
                                    
                                except Exception as e:
                                    self._log(logging.WARNING, self.task_id, 'Pending', f"Could not click Aceptar button: {e}")
                                    raise e

                                random_wait(wait_type='XX_LONG', wait=True)  
                            except Exception as e:
                                self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error during ACEPTAR process for notification pendiente {self.task_id}: {e}")
                                raise e                                                                                   
                        
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error al ACEPTAR la notificacion {self.task_id}: {e}")
                        raise e

                    # Click the found action button, determine base xpath and zero-based index, then extract row fields
                    try:                                         
                        # /html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[1]/div[2]/app-detail-data-box/div/span[2]
                        # title = get_value("Concepto") 
                        try:
                            random_wait(wait_type='MEDIUM', wait=True)

                            title = driver.execute_script(
                                "const el = document.querySelector('body > app-root > div.content-page > div > app-realized-notification-detail-view > div > dnt-section > div > app-realized-detail-panel > div > div:nth-child(1) > div:nth-child(2) > app-detail-data-box > div > span.value.dnt-txt-body-300'); " \
                                "return el ? el.textContent.trim() : null;"
                            )
                        except Exception:
                            try:
                                title = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[1]/div[2]/app-detail-data-box/div/span[2]'))
                                ).text.strip()
                            except Exception:
                                title = None
                            

                        # # /html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[1]/div[2]/app-detail-data-box/div/span[2]
                        # # identificador = get_value("Identificador")
                        # try:
                        #     random_wait(wait_type='MEDIUM', wait=True)

                        #     identificador = driver.execute_script(
                        #         "const el = document.querySelector('body > app-root > div.content-page > div > app-realized-notification-detail-view > div > dnt-section > div > app-realized-detail-panel > div > div:nth-child(1) > div:nth-child(1) > app-detail-data-box > div > span.value.dnt-txt-body-300'); " \
                        #         "return el ? el.textContent.trim() : null;",
                        #     )
                        # except Exception:
                        #     try:
                        #         identificador = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        #             EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[1]/div[2]/app-detail-data-box/div/span[2]'))
                        #         ).text.strip()
                        #     except Exception:
                        #         identificador = None
                        
                        # # /html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[4]/div[1]/div/div/app-detail-data-box/div/span[2]
                        # # disposition_date = get_value("Fecha de disposición")
                        # # disposition_date = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        # #     EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[4]/div[1]/div/div/app-detail-data-box/div/span[2]'))
                        # # ).text.strip()
                        # try:
                        #     random_wait(wait_type='MEDIUM', wait=True)

                        #     disposition_date = driver.execute_script(
                        #         "var el = document.querySelector('body > app-root > div.content-page > div > app-realized-notification-detail-view > div > dnt-section > div > app-realized-detail-panel > div > div:nth-child(5) > div.col-xs-12.col-md-4 > div > div > app-detail-data-box > div > span.value.dnt-txt-body-300');" \
                        #         "return el ? el.textContent.trim() : null;"
                        #     )
                        # except Exception:
                        #     try:
                        #         disposition_date = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        #             EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[4]/div[1]/div/div/app-detail-data-box/div/span[2]'))
                        #         ).text.strip()
                        #     except Exception:
                        #         disposition_date = None

                            

                        # # /html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[2]/div[1]/app-detail-data-box/div/span[2]
                        # # org = get_value("Organismo emisor")
                        # try:
                        #     random_wait(wait_type='MEDIUM', wait=True)

                        #     org = driver.execute_script(
                        #         "const el = document.querySelector('body > app-root > div.content-page > div > app-realized-notification-detail-view > div > dnt-section > div > app-realized-detail-panel > div > div:nth-child(2) > div:nth-child(1) > app-detail-data-box > div > span.value.dnt-txt-body-300');" \
                        #         "return el ? el.textContent.trim() : null;"
                        #     )
                        # except Exception:
                        #     try:
                        #         org = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        #             EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/div/app-realized-notification-detail-view/div/dnt-section/div/app-realized-detail-panel/div/div[2]/div[1]/app-detail-data-box/div/span[2]'))
                        #         ).text.strip()
                        #     except Exception:
                        #         org = None

                        # Populate descarga_result with whatever was extracted
                        if title:
                            descarga_result.title = title
                        # if identificador:
                        #     descarga_result.identificador = identificador
                        # if disposition_date:
                        #     descarga_result.disposition_date = disposition_date
                        # if org:
                        #     descarga_result.org = org
                        
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, 'Failure', f"Error extracting row details after clicking action button: {e}")   
                else:
                    self._log(logging.WARNING, self.task_id, "Pending", f"Could not locate notification {idNotificacion} in pendientes table: {result}")
                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                    descarga_result.message = f"Could not locate notification {idNotificacion} in pendientes table"
                    return descarga_result
                                                 
            except ErrorRobotDescargas.ErrorAvisoEspecial as e:
                raise e
            except ErrorRobotDescargas.InvalidServicio as e:
                raise e
            except Exception as e:
                self._log(logging.ERROR, self.task_id, 'Failure', f"Error locating/clicking notification row for {idNotificacion}: {e}")
            

            try:                
                start_time = time.time()
                while time.time() - start_time < random_wait(wait_type='XXX_LONG', wait=False):                                     
                    check = self._check_download(self.download_path)
                    if not check:
                        try:
                            self._check_on_spinner(driver)                            

                            try:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '//*[@id="contenedorBoton"]/dnt-button'))
                                ).click()
                            except Exception:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/div[1]/div/app-communication-detail-view/div/app-detail-info-communication/div/div[1]/div[3]/dnt-button'))
                                ).click()

                            random_wait('LONG', wait=True)

                            if path == "communications":
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '//*[@id="modalDocumentsCommunication"]'))
                                )
                                notification_link_xpaths = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, '//*[@id="modalDocumentsCommunication"]/div'))
                                )
                            else:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '//*[@id="modalDocumentsNotification"]'))
                                )

                                notification_link_xpaths = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, '//*[@id="modalDocumentsNotification"]/div'))
                                )
                            
                            random_wait('MEDIUM', wait=True)

                            link_xpath = None
                            for index, link in enumerate(notification_link_xpaths, start=1):
                                try:
                                    if 'Notificación' in WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, f'//*[@id="modalDocumentsNotification"]/div[{index}]/p'))
                                    ).text.strip():                                                                
                                        link_xpath = f'//*[@id="modalDocumentsNotification"]/div[{index}]/dnt-link'
                                        break
                                except Exception:
                                    pass

                                try:
                                    if 'Comunicación' in WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, f'//*[@id="modalDocumentsCommunication"]/div[{index}]/p'))
                                    ).text.strip():                                                                
                                        link_xpath = f'//*[@id="modalDocumentsCommunication"]/div[{index}]/dnt-link'
                                        break
                                except Exception:
                                    pass

                            # document.querySelector("#modalDocumentsNotification > div > dnt-link").shadowRoot.querySelector("a")
                            download_button = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, link_xpath))
                            )
                            ActionChains(driver).move_to_element(download_button).click().perform()
                            random_wait('LONG', wait=True)
                        except Exception as e:
                            self._log(logging.WARNING, self.task_id, "Pending", f"⚠️ Error finding file: {e}. Retrying...")
                            driver.refresh()
                            continue
                    else:
                        break
                      
                if check:
                    self._log(logging.INFO, self.task_id, "Success", f"Descarga procesada correctamente para notificacion {descarga_result.identificador}")

                    processed_file, expediente = process_files(self.download_path, self.task_id, descarga_result.to_dict(), self.cliente, self.date, self.notification_date, self._log)

                    if processed_file:
                        descarga_result.status = DescargaResult.StatusEnum.SUCCESS
                        descarga_result.expediente = expediente
                        descarga_result.message = f"Notificación procesada correctamente: {self.task_id}"
                        descarga_result.file = processed_file
                    else:
                        self._log(logging.ERROR, self.task_id,  "Failure", f"Error procesando archivo para notificacion {self.task_id}")
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = f"Error processing file for notification {self.task_id}"
                    
                else:
                    self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error procesando archivo para notificacion {self.task_id}")
                    descarga_result.status = DescargaResult.StatusEnum.ERROR
                    descarga_result.message = f"Error procesando archivo para notificacion {self.task_id}"
                    
            except Exception as e:
                self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error procesando notificacion {self.task_id}: {e}")        
                descarga_result.status = DescargaResult.StatusEnum.ERROR
                descarga_result.message = f"Error procesando notificacion {self.task_id}: {e}"
                return descarga_result    
        except RuntimeError as e:
            self._log(logging.WARNING, self.task_id, "Pending", str(e))
            descarga_result.status = DescargaResult.StatusEnum.PENDING
            descarga_result.message = str(e)
        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error procesando notificacion {self.task_id}: {e}")
            descarga_result.status = DescargaResult.StatusEnum.ERROR
            descarga_result.message = f"Error procesando notificacion {self.task_id}: {e}"
        finally:
            self._log(logging.INFO, self.task_id, 'Success', f"Notificación procesada correctamente {self.task_id}: {descarga_result.to_dict()}")
            return descarga_result
    
    def getNotifications(self, notification_data :  Dict[str, Any]) -> Dict[str, DescargaResult] | None:
        notifications = notification_data['notificaciones']
        if not notification_data or not notifications:
            self._log(logging.ERROR, self.task_id, "Failure", "No notifications provided.")
            return None

        if not isinstance(notifications, list) or len(notifications) == 0:
            self._log(logging.ERROR, self.task_id, "Failure", "Notifications should be a list of dictionaries.")
            return None

        
        portalLink = notifications[0].get('link', 'https://dehu.redsara.es')
        response = {}
        
        # Crear una carpeta temporal para el perfil de usuario
        temp_profile = tempfile.mkdtemp(prefix="dehu_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=portalLink if portalLink else 'https://dehu.redsara.es',
            module="Descargas",
            execution_id=self.execution_id,
            log_dir=r"logs\descargas",
            filename=f"descargas_{self.date}",
            cliente=self.cliente,
            task_id = self.task_id,
            site=self.sede
        )
        driver, self.download_path = driver_setup.setup_chrome_driver_descargas()
        random_wait('LONG', wait=True)

        try:
            login = self._login_dehu(driver, portalLink)

            if login:
                for notification in notifications:
                    self.task_id = notification.get('message_key')
                    notification_id = notification.get('identificador')
                    services = notification_data.get('servicios')
                    descarga_especial = notification_data.get('aviso_especial', None)
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
                        
                    notification_date = notification.get('date')
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
                    # Move mouse to avoid screen lock or inactivity
                    pyautogui.moveTo(1000, 550)
                    
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

                    if not notification_id:
                        self._log(logging.ERROR, self.task_id,  "Failure", "Notification ID is missing.")
                        descarga_result.status = 'Error'
                        descarga_result.message = "Notification ID is missing."
                        response[notification_id] = descarga_result
                        continue

                    cleanup_download_dir(self.download_path, self.sede, self._log)

                    self.portalLink = notification.get('link', portalLink)
                    path = "communications" if 'comunicaciones' in portalLink else "notifications" if 'notificaciones' in portalLink else "unknown"
                    driver.get(f'https://dehu.redsara.es/es/{path}')
                    random_wait('LONG', wait=True)

                    if path:
                        result = self._handle(
                            driver=driver,
                            notification=notification,
                            idNotificacion=notification_id,
                            descarga_result=descarga_result,
                            services=services,
                            descarga_especial=descarga_especial,
                            path=path
                        )
                    
                    else:
                        self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Unknown path: {path}. Cannot handle notifications.")                                                                        
                        descarga_result.status = DescargaResult.StatusEnum.ERROR
                        descarga_result.message = f"Unknown path: {path}. Cannot handle notifications."
                        response[notification.get('message_key')] = descarga_result
                        continue

                    if result.status == DescargaResult.StatusEnum.PENDING:
                        self._log(logging.WARNING, self.task_id,  "Pending", f"Notification {notification_id} is still pending.")
                        result.status = DescargaResult.StatusEnum.ERROR

                    response[notification.get('message_key')] = result
                
                return response 
                    
            else:
                self._log(logging.ERROR, self.task_id, "Failure", f"Error en el login")
                return None
        except Exception as e:
            self._log(logging.ERROR, self.task_id,  "Failure", ErrorBase.ErrorDescargaEnSede(portalLink, str(e)))
            return None
        finally:
            random_wait('LONG' , wait=True)
            driver.quit()
            shutil.rmtree(temp_profile)
            delete_download_dir(self.download_path, self.sede, self._log)
               
    def extract_from_body(self, body_html: str, services: List[str]) -> ExtractionResponse:
        """Extract fields from DEHU body HTML."""
        if not body_html:
            self._log(logging.ERROR, self.task_id,  "Failure", "body_html cannot be None or empty")
            raise ValueError("body_html cannot be None or empty")
        
        try:
            # Helper function to extract text between two markers
            def extract_between(mark_start, mark_end, default=""):
                start = body_html.find(mark_start) + len(mark_start)
                end = body_html.find(mark_end, start)
                return body_html[start:end].strip() if start > len(mark_start) - 1 and end > -1 else default

            # Extract fields
            nombre_cliente = extract_between("<li>", "con NIF/NIE:")
            identificador = extract_between("Identificador:", "</li>")
            concepto = extract_between("<li>Concepto:", "</li>")
            # Extract 'organismo' handling both possible labels
            organismo = extract_between("<li>Organismo emisor:", "</li>")
            if not organismo or organismo == "":
                organismo = extract_between("<li>Organismo:", "</li>")

            # Extract link
            link_match = re.search(r"(https://dehu\.redsara\.es/(comunicaciones|notificaciones-pendientes)/[a-zA-Z0-9]+/ver)", body_html)
            link = link_match.group(0) if link_match else None

            # Match Concepto with rules
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
                    
                    except Exception as e:
                        pass

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
                    
                    except Exception as e:
                        pass
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

                    except Exception as e:
                        pass
                else:
                    self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Service {service} not recognized or not supported for extraction.")
                    raise ValueError(f"Service {service} not recognized or not supported for extraction.")
            
            self._log(logging.INFO, self.task_id, "Success", f"Extracción completada para {self.cliente} - {concepto_value}")
            return ExtractionResponse(
                client_name=nombre_cliente,
                expediente=concepto_value,
                org=organismo,
                identificador=identificador,
                link=link
            )
        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"⚠️ Error extracting fields: {e}")
            raise KeyError(f"⚠️ Error extracting fields: {e}")
