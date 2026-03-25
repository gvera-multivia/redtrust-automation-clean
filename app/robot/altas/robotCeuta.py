from queue import Queue
import time, os, shutil, tempfile
import uuid
import logging 

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait



class RobotCeuta:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link : str ='https://sede.ceuta.es/controlador/controlador?cmd=inicio&modulo=carpeta', sede : str ='ceuta', 
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'info@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = portal_link
        self.sede = sede
        self.multivia = multivia
        self.mail = 'info@xvia-serviciosjuridicos.com'
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


    def _login_ceuta(self, driver) -> bool:
        try:
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="contenido"]/div[1]/div/button[1]'))).click()
            random_wait(wait_type='LONG', wait=True)
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="autentica-clave"]'))).click()
            random_wait(wait_type='LONG', wait=True)
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))).click()

            xpaths = [
                '//*[@id="datosForm"]'
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
            login = self._login_ceuta(driver)
            if login:
                try:
                    nif_element = driver.find_element(By.XPATH, '//*[@id="contenido"]/div[1]/div[2]/div[1]')
                    nif_text = nif_element.text.strip()
                    if nif_cif in nif_text:
                        self._log(logging.ERROR, self.sede, "Success", f"NIF/CIF encontrado en el portal: {nif_text}")
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", f"NIF/CIF no coincide. Encontrado: {nif_text}, Esperado: {nif_cif}")
                        return False, (0, f"NIF/CIF no coincide. Encontrado: {nif_text}, Esperado: {nif_cif}")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al buscar NIF/CIF en el portal: {e}")
                    return False, (0, f"Error al buscar NIF/CIF en el portal")

                fields = driver.find_elements(By.XPATH, '//form//div//div')

                for field in fields:
                    try:
                        label = field.find_element(By.XPATH, './/label')
                        label_text = label.text.strip()

                        if 'Correo' in label_text:
                            email_field = field.find_element(By.XPATH, './/input')
                            email_value = email_field.get_attribute('value').strip().lower()

                            if email_value: 
                                if self.mail == email_value and self.n_mails == 1:
                                    self._log(logging.INFO, self.sede, "Success", f"El correo {email_value} ya está registrado.")
                                    action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                                elif self.mail != email_value and self.multivia.get('mail') == email_value:
                                    self._log(logging.INFO, self.sede, "Pending", f"El correo MULTIVIA sustituido por cliente: {email_value}")
                                    action = list(CERT_SEDES_ACTION.items())[4]  # 5: MULTIVIA sustituido por cliente
                                else:
                                    self._log(logging.INFO, self.sede, "Pending", f"Cliente sustituido por MULTIVIA: {email_value}")
                                    action = list(CERT_SEDES_ACTION.items())[3]  # 4: Cliente sustituido por MULTIVIA
                                    email_field.clear()
                                    email_field.send_keys(self.mail)
                                break
                            else:
                                if self.mail == self.multivia.get('mail'):
                                    self._log(logging.INFO, self.sede, "Success", "Alta realizada correctamente")
                                    action = list(CERT_SEDES_ACTION.items())[0]  # 1: alta realizada correctamente
                                else:
                                    self._log(logging.INFO, self.sede, "Success", "Correo cliente añadido")
                                    action = list(CERT_SEDES_ACTION.items())[2]  # 3: correo cliente añadido
                                email_field.clear()
                                email_field.send_keys(self.mail)
                                break
                    except Exception:
                        self._log(logging.ERROR, self.sede, "Failure", "Error al buscar el campo de correo")
                        return False, (0, "Error al buscar el campo de correo")

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="verifica"]'))).click()
                return True, action
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en el proceso de suscripción: {e}")
            return False, (0, f"Error en el proceso de suscripción.")
        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
