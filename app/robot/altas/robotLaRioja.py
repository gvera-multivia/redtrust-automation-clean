import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait
from app.helper.loggerV2 import LoggerV2



class RobotLaRioja:
    def __init__(self, mail: str, date : str, cliente: str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link='https://www.larioja.org/notificaciones-electa/es', sede : str = 'la rioja',
            n_mails : int = 3,
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
        
    def _login_larioja(self, driver) -> bool:
        try: 
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '/html/body/div[3]/div[2]/div/div/div/div[3]/div/div/div[2]/div/div/div[1]/div/div/div/div/div/div[1]/p/a'))).click()

            self._log(logging.INFO, self.sede, "Pending", f"Ventanas disponibles: {len(driver.window_handles)}")
            driver.switch_to.window(driver.window_handles[-1])

            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="nav-tabs"]/li[1]/a'))).click()
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="boton_certificado"]'))).click()

            xpaths = [
                '//*[@id="oForm"]/div[3]/div[1]/fieldset',
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths: 
                    if driver.find_elements(By.XPATH, xpath): 
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True 
                random_wait(wait_type='SHORT', wait=True) 

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
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
            login = self._login_larioja(driver)
            if login:
                try:
                    fields = driver.find_elements(By.XPATH, '//*[@id="oForm"]/div[3]/div[1]/fieldset/div/div')
                    for field in fields:                         
                        label_text = field.find_element(By.XPATH, './/label').text
                        self._log(logging.INFO, self.sede, "Pending", f"Campo encontrado: {label_text}")
                        if 'NIF' in label_text:
                            input_field = field.find_element(By.XPATH, './/input').get_attribute('value')
                            if input_field == nif_cif:
                                continue
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", f"NIF no coincide: esperado {nif_cif}, encontrado {input_field}")
                                return False, (0, f"NIF no coincide: esperado {nif_cif}, encontrado {input_field}")
                        if 'Correo' in label_text:
                            try:                           
                                email_fields = driver.find_elements(By.XPATH, '//*[starts-with(@id, "sccoel")]')
                                self._log(logging.INFO, self.sede, "Pending", f"Campos de email encontrados: {len(email_fields)}")
                                open_email_fields = [field for field in email_fields if field.is_displayed() and field.is_enabled()]
                                for i in range(1, len(open_email_fields) + 1):
                                    try:
                                        if email_fields == 1 and email_fields[0].get_attribute('value') is None:
                                            email_field[0].send_keys(self.mail)
                                            action = list(CERT_SEDES_ACTION.items())[0]
                                            break
                                    except Exception as e:
                                        self._log(logging.ERROR, self.sede, "Failure", f"Error añadiendo el correo en el campo email{i}: {e}")
                                        return False, (0, f"Error añadiendo el correo en el campo email{i}: {e}")
                                    try:
                                        email_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, f'//*[@id="sccoel{i}"]')))
                                        if email_field.get_attribute('value') == self.mail:
                                            self._log(logging.INFO, self.sede, "Success", f"Mail {self.mail} ya añadido en el campo email{i}.")
                                            if self.mail == self.multivia.get('mail'):
                                                self._log(logging.INFO, self.sede, "Success", f"Mail {self.mail} ya añadido en el campo email{i}.")
                                                action = list(CERT_SEDES_ACTION.items())[6]
                                                break
                                            else:
                                                self._log(logging.INFO, self.sede, "Pending", f"Mail {self.mail} ya añadido en el campo email{i}. Añadimos el de MULTIVIA.")
                                                action = list(CERT_SEDES_ACTION.items())[1]
                                                if len(open_email_fields) + 1 <= self.n_mails:
                                                    try:
                                                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="mas"]'))).click()
                                                        random_wait(wait_type='MEDIUM', wait=True)
                                                        email_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                            EC.presence_of_element_located((By.XPATH, f'//*[@id="sccoel{i+1}"]'))
                                                        )
                                                        email_field.clear()
                                                        email_field.send_keys(self.multivia.get('mail'))
                                                    except Exception as e:
                                                        self._log(logging.ERROR, self.sede, "Failure", f"Error al hacer clic en el button del campo email{i}: {e}")
                                                        return False, (0, f"Error al hacer clic en el button del campo email{i}")
                                        else:                                            
                                            if i == len(open_email_fields) and len(open_email_fields) + 1 <= self.n_mails:
                                                try:
                                                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="mas"]'))).click()
                                                    random_wait(wait_type='MEDIUM', wait=True)
                                                except Exception as e:
                                                    self._log(logging.ERROR, self.sede, "Failure", f"Error al hacer clic en el button del campo email{i}: {e}")
                                                    raise(f"Error al hacer clic en el button del campo email{i}")
                                                email_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, f'//*[@id="sccoel{i+1}"]'))
                                                )
                                                email_field.clear()
                                                email_field.send_keys(self.mail)
                                                if self.mail == self.multivia.get('mail'):
                                                    action = list(CERT_SEDES_ACTION.items())[1]
                                                else:
                                                    action = list(CERT_SEDES_ACTION.items())[2]
                                    except Exception as e:
                                        self._log(logging.ERROR, self.sede, "Failure", f"Error verificando el mail {self.mail[0]} en el campo email{i}: {e}")
                                        return False, (0, f"Error verificando el mail {self.mail[0]} en el campo email{i}: {e}")   
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error añadiendo el correo en el campo: {e}")
                                return False, (0, f"Error añadiendo el correo en el campo")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando el formulario de datos de contacto: {e}")
                    return False, (0, f"Error rellenando el formulario de datos de contacto")
                
                buttons = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.presence_of_all_elements_located((By.XPATH, '//*[@id="oBotonera"]/input')))
                for button in buttons:
                    button_value = button.get_attribute('value')
                    if button_value == 'Guardar' or button_value == 'Alta':
                        button.click()
                        break
                    else:
                        self._log(logging.INFO, self.sede, "Pending", f"Botón no tiene el valor esperado: {button_value}")

                random_wait(wait_type='LONG', wait=True)

                #Verificacion de la subscripción
                try: 
                    confirmation = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="oForm"]/div/div[1]/div/div')))
                    self._log(logging.INFO, self.sede, "Pending", f"Texto de confirmación: {confirmation.text}")
                    if any(msg in confirmation.text for msg in ['Su suscripción se ha creado correctamente', 'Su modificación se ha realizado correctamente']):
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="mensajeBoton"]/button'))).click()
                        self._log(logging.INFO, self.sede, "Success", "Subscripción exitosa")
                        return True, action
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error verificando la subscripción: {e}")
                    return False, (0, f"Error verificando la subscripción: {e}")
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en el login")
                return False, (0, f"Error en el login")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")
        finally:
            # Cerrar navegador después de completar la acción
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
