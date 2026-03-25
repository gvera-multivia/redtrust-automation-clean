import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait


class RobotBadajoz:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id:str,  module : str ="Altas",  portal_link : str ='https://sede.dip-badajoz.es/portal/entidades.do?ent_id=10&idioma=1', sede : str ='burgos', 
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = portal_link
        self.sede = sede
        self.multivia = multivia
        self.mail = mail
        self.n_mails = n_mails
        self.cliente = cliente
        self.date = date
        self.module = module
        self.execution_id = execution_id
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.log_queue = log_queue
    
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
                

    def _login_badajoz(self, driver) -> bool:
        try: 
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/div[15]/div/div[3]/button[1]'))
                ).click()

                random_wait(wait_type='MEDIUM', wait=True)
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error al aceptar las cookies: {e}")
                
            # Esperar y cerrar el modal si aparece
            try:
                modal_button = WebDriverWait(driver, random_wait(wait_type='SHORT', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="modalAviso"]/div/div/div[3]/button'))
                )
                modal_button.click()
                random_wait(wait_type='MEDIUM', wait=True)
                self._log(logging.DEBUG, self.sede, "Success", "Modal de aviso cerrado.")
            except Exception:
                self._log(logging.DEBUG, self.sede, "Pending", "No apareció el modal de aviso.")

            try:
                # Esperar a que todos los enlaces estén presentes
                elements = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_all_elements_located((By.XPATH, '/html/body/main/div/div[1]/div/div/div[2]/div/div/div/a'))
                )
                for element in elements:
                    try:
                        span = element.find_element(By.XPATH, './span[2]')
                        if 'notificaciones y comunicaciones' in span.text.lower():
                            element.click()
                            random_wait(wait_type='MEDIUM', wait=True)

                            break
                    except Exception:
                        continue
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error al buscar el enlace 'notificaciones y comunicaciones': {e}")                
                return False
            
            try:
                random_wait(wait_type='LONG', wait=True) # Esperar a que se cargue la página
                btn_clave = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="btnClave"]'))
                )
                driver.execute_script("arguments[0].scrollIntoView(true);", btn_clave)
                btn_clave.click()
                random_wait(wait_type='LONG', wait=True)
                # Manejar el diálogo de confirmación tipo alert/confirm (como el de la imagen)
                try:
                    alert = driver.switch_to.alert
                    alert.accept()
                except Exception:
                    self._log(logging.DEBUG, self.sede, "Pending", "No apareció el diálogo de confirmación tipo alert/confirm.")
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                ).click()
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error al hacer login con Cl@ve: {e}")
                return False
            xpath = [
                '//*[@id="datos"]', 
                '/html/body/main/form'
            ]
            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:                
                if WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, xpath[0]))
                ): 
                    self._log(logging.INFO, self.sede, "Success", f"✅ Login exitoso: {xpath[0]} encontrado.")                     
                    return True 
                random_wait(wait_type='SHORT', wait=True)
            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False
        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def subscribe(self, id_cliente: str, nif_cif: str) -> bool:
        # Crear una carpeta temporal para el perfil de usuario
        temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=self.portal_link,
            module="Altas",
            execution_id=self.execution_id,
            log_dir="logs/altas",
            filename=f"altas",
            cliente=self.cliente,
            task_id=self.sede,
            site=self.sede
        )
        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait(wait_type='LONG', wait=True)
        try: 
            login = self._login_badajoz(driver)
            if login:   
                try:
                    try:
                        main_div = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '/html/body/main/div[1]/div'))
                        )
                        if main_div.text.strip() == "Buzón de Notificaciones":
                            driver.get("https://sede.dip-badajoz.es/sede/perfil.do?ent_id=10&idioma=1")
                            random_wait(wait_type='LONG', wait=True)
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, "Pending", f"No se encontró el panel 'Buzón de Notificaciones': {e}")
                        
                    try:
                        # Rellenar los campos según el label
                        form_fields = driver.find_elements(By.XPATH, '//*[@id="datos"]/div[3]/div')
                        for input_field in form_fields:
                            try:
                                label = input_field.find_element(By.XPATH, './/label').text.lower()
                                if label == 'Tipo de Documento':
                                    continue  # No hacer nada para este campo
                                input_elem = input_field.find_element(By.XPATH, './/input')
                                if 'documento' in label:
                                    # Comprobar que el valor es igual a nif_cif
                                    value = input_elem.get_attribute('value')
                                    if value.strip().upper() != nif_cif.strip().upper():
                                        self._log(logging.ERROR, self.sede, "Failure", f"El valor del documento ({value}) no coincide con el NIF/CIF proporcionado ({nif_cif})")
                                        return False, (0, f"El valor del documento ({value}) no coincide con el NIF/CIF proporcionado ({nif_cif})")
                                elif 'correo electrónico' in label:
                                    email_value = input_elem.get_attribute('value')  # Obtener el valor actual del campo
                                    if email_value: 
                                        if self.mail == email_value:
                                            self._log(logging.INFO, self.sede, "Pending", f"El correo {email_value} ya está registrado.")
                                            if self.multivia.get('mail') == email_value:
                                                action = list(CERT_SEDES_ACTION.items())[6]
                                            elif self.n_mails > 1 and self.multivia.get('mail') != email_value:
                                                action = list(CERT_SEDES_ACTION.items())[1] 
                                                try:
                                                    second_mail_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, '//*[@id="prf_dca"]'))
                                                    )
                                                    second_mail_field.clear()
                                                    second_mail_field.send_keys(self.multivia.get('mail'))
                                                    random_wait(wait_type='MEDIUM', wait=True)

                                                    mail_canal = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, '//*[@id="prf_mrp"]'))
                                                    )
                                                    select = Select(mail_canal)
                                                    select.select_by_visible_text('De manera telemática')
                                                    random_wait(wait_type='MEDIUM', wait=True)

                                                except Exception:
                                                    self._log(logging.ERROR, self.sede, "Failure", "Error al añadir el mail de MULTIVIA como secundario")
                                                    return False, (0, "Error al añadir el mail de MULTIVIA como secundario")
                                            else:
                                                action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                                        else:
                                            self._log(logging.INFO, self.sede, "Pending", f"El correo {email_value} no coincide con el proporcionado {self.mail}. Actualizando...")
                                            try:
                                                second_mail_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="prf_dca"]'))
                                                )
                                                second_mail_field.clear()
                                                second_mail_field.send_keys(self.mail)
                                                random_wait(wait_type='MEDIUM', wait=True)

                                                mail_canal = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="prf_mrp"]'))
                                                )
                                                select = Select(mail_canal)
                                                select.select_by_visible_text('De manera telemática')
                                                random_wait(wait_type='MEDIUM', wait=True)
                                            except Exception:
                                                self._log(logging.ERROR, self.sede, "Failure", "Error al añadir el mail de MULTIVIA como secundario")
                                                return False, (0, "Error al añadir el mail de MULTIVIA como secundario")
                                            
                                            if self.multivia.get('mail') == self.mail:
                                                action = list(CERT_SEDES_ACTION.items())[1]
                                            else:
                                                action = list(CERT_SEDES_ACTION.items())[2]
                                    else:
                                        input_elem.clear()
                                        input_elem.send_keys(self.mail)
                                        action = list(CERT_SEDES_ACTION.items())[0] 
                                        random_wait(wait_type='MEDIUM', wait=True)                                 
                                elif 'confirmar correo' in label:
                                    if not input_elem.get_attribute('value'):
                                        input_elem.clear()
                                        input_elem.send_keys(self.mail)
                            except Exception as e:
                                self._log(logging.INFO, self.sede, "Pending", f"No se pudo procesar un campo: {e}")
                                continue
                        # Click en el botón para continuar
                        continuar_btn = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="datos"]/div[9]/div[2]/button'))
                        )
                        continuar_btn.click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error en el proceso de rellenar datos y continuar: {e}")
                        return False, (0, f"Error en el proceso de rellenar datos y continuar")
                    # Comprobar si existe el mensaje de éxito
                    try:
                        success_panel = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="panelMiPerfil"]/div[1]/div/div'))
                        )
                        if success_panel.text.strip() in ("Se ha generado correctamente su perfil, puede continuar navegando", "Operación realizada correctamente"):
                            self._log(logging.INFO, self.sede, "Success", "Perfil generado correctamente.")
                            return True, action
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "No se ha encontrado la verificación")
                            return False, (0, f"No se ha encontrado la verificación")
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"No se encontró el panel de éxito o texto incorrecto: {e}")
                        return False, (0, "No se encontró el panel de éxito o texto incorrecto")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error introduciendo los datos de contacto: {e}")
                    return False, (0, f"Error introduciendo los datos de contacto: {e}")
            else:
                self._log(logging.INFO, self.sede, "Failure", "Error en el login")
                return False, (0, "Error en el login")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")
        finally:
            # Cerrar navegador después de completar la acción
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)