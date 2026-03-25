import logging
from multiprocessing import Queue
import tempfile, time, shutil
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait



class RobotMahon:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link: str = 'https://www.carpetaciutadana.org/mao/Login/Login.aspx?URL=https://www.carpetaciutadana.org/mao/Solicituds/formsol.aspx¿TIPO=SNE^IDIOMA=1', sede: str = 'mahon',
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

    def _login_mahon(self, driver) -> bool:
        try:
            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_Content1_Button1"]'))
            ).click()

            random_wait(wait_type='X_LONG', wait=True)

            xpath = '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_pnlPersona"]'

            try:
                element= WebDriverWait(driver, random_wait(wait_type='XX_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, xpath))
                )

                if element.is_displayed():
                    self._log(logging.INFO, self.sede, "Success", "Login exitoso en Mahón")
                    return True
                else:
                    self._log(logging.ERROR, self.sede, "Failure", "Login fallido en Mahón: Elemento no visible")
                    return False
            except Exception:
                random_wait(wait_type='LONG', wait=True)
                return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False

    def subscribe(self, nif_cif: str, direccion: dict) -> bool:
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
            if self._login_mahon(driver):
                # Paso 1: Dades del sol·licitant
                try:
                    # Verificar si el campo NIF ya contiene el valor esperado
                    nif_element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_NIF_I"]'))
                    )

                    if nif_element.get_attribute('value') != nif_cif:
                        return False, (0, "El NIF/CIF no coincide con el esperado")
                    
                    # Completar los campos de dirección
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_TELEFON_I"]'))
                    ).send_keys(self.multivia.get('phone'))

                    email_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_EMAIL_I"]'))
                    )
                    
                    if not email_field.get_attribute('value'):              
                        email_field.send_keys(self.mail)

                        if self.mail == self.multivia.get('mail'):
                            action = list(CERT_SEDES_ACTION.keys())[0] # damos de alta
                        else:
                            action = list(CERT_SEDES_ACTION.keys())[2] # añadimos mail de cliente
                    else:
                        email_value = email_field.get_attribute('value')
                        if email_value != self.mail:
                            self._log(logging.INFO, self.sede, "Pending", f"El correo electrónico ya está configurado como: {email_value}. No se modificará.")
                            return False, (-1, f"El correo electrónico ya está configurado como: {email_value}. No se modificará.")
                        elif email_value == self.multivia.get('mail'):
                            email_field.clear()  # Limpiar el campo si es necesario
                            email_field.send_keys(self.mail)
                            action = list(CERT_SEDES_ACTION.keys())[6] # damos de alta con el mail correcto

                    random_wait(wait_type='MEDIUM', wait=True)                    

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_PAIS_I"]'))
                    ).send_keys(direccion.get('pais'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_PROVINCIA_I"]'))
                    ).send_keys(direccion.get('provincia'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_MUNICIPI_I"]'))
                    ).send_keys(direccion.get('municipio'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_CARRER_I"]'))
                    ).send_keys(direccion.get('calle'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_CPOSTAL_I"]'))
                    ).send_keys(direccion.get('codigo_postal'))

                    self._log(logging.INFO, self.sede, "Success", "Paso 1: Dades del sol·licitant completado")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en Paso 1: Dades del sol·licitant: {e}")
                    return False, (0, f"Error en Dades del sol·licitant")

                # Paso 2: Dades específiques
                try:
                    # Completar los campos específicos del formulario
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.ID, "ctl00_Content1_txtDadesEspecifiques"))
                    ).send_keys(self.multivia.get('purpose', ''))
                    # Otros campos según corresponda...
                    self._log(logging.INFO, self.sede, "Success", "Paso 2: Dades específiques completado")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en Paso 2: Dades específiques: {e}")
                    return False, (0, f"Error en Dades específiques")

                # Paso 3: Declaració responsable
                try:
                    # Marcar la declaración responsable
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.ID, "ctl00_Content1_chkDeclaracio"))
                    ).click()
                    self._log(logging.INFO, self.sede, "Success", "Paso 3: Declaració responsable completado")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en Paso 3: Declaració responsable: {e}")
                    return False, (0, f"Error en Declaració responsable")

                # Paso 4: Confirmació
                try:
                    # Confirmar y enviar el formulario
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.ID, "ctl00_Content1_btnConfirmar"))
                    ).click()
                    self._log(logging.INFO, self.sede, "Success", "Paso 4: Confirmació completado")
                    # return True, action
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en Paso 4: Confirmació: {e}")
                    return False, (0, f"Error en Confirmació")
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error al iniciar sesión en Mahón")
                return False, (0, "Error al iniciar sesión en Mahón")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")
        finally:
            random_wait(wait_type='XXX_LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
