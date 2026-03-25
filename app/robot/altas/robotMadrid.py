from multiprocessing import Queue
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


class RobotMadrid:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link: str = 'https://sede.comunidad.madrid/guia-tramitacion-electronica#notificaciones', sede: str = 'madrid',
                 n_mails : int = 1,
                 multivia : dict = {
                     'nif': 'B62798210',
                     'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                     'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                     'phone': '722761154'
                 }):
        self.portal_link = 'https://sede.comunidad.madrid/guia-tramitacion-electronica#notificaciones'
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

    def _login_cmadrid(self, driver) -> bool:
        try: 
            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="block-employmentoffer-theme-content"]/article/div/div/div[23]/div/div/ol/li[1]/p/a'))
            ).click()  

            random_wait(wait_type='SHORT', wait=True)

            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="autoAccessForm:linkIDPCD"]'))
            ).click()

            xpaths = ['/html/body/form/table[2]', '//*[@id="contenido_aplicacion"]']

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths:
                    try:
                        element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        if element:
                            self._log(logging.INFO, self.sede, "Success", f"Elemento encontrado: {xpath}")
                            return True
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, "Failure", f"Elemento no encontrado: {xpath} - Error: {e}")
                        continue    

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='SHORT', wait=True)

    def subscribe(self, nif_cif: str) -> tuple[bool, tuple[int, str], str | None]:
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
            login = self._login_cmadrid(driver)
            if login:
                # Comprobar si existe el elemento 'contenido_aplicacion'
                try: 
                    if WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="contenido_aplicacion"]'))
                    ):                    
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="menu_aplicacion"]/ul/li[2]/a'))
                        ).click()
                        random_wait(wait_type='SHORT', wait=True)
                        # Esperar a que todos los elementos de las filas de la tabla estén presentes
                        rows = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_all_elements_located((By.XPATH, '//*[@id="campos"]/form/table/tbody[2]/tr'))
                        )
                except Exception as e:
                    # Esperar a que todos los elementos de las filas de la tabla estén presentes
                    rows = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '/html/body/form/table[2]/tbody[2]/tr'))
                    )

                for index, row in enumerate(rows, start=1):                             
                    try:
                        label = WebDriverWait(row, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, './/td[1]/label'))
                        )
                        field = WebDriverWait(row, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, './/td[2]/input'))
                        )

                        if label.text.strip() == 'NIF':
                            try:            
                                nif_text = field.get_attribute('value').strip()
                                if nif_cif.strip().lower() != nif_text.strip().lower():
                                    self._log(logging.ERROR, self.sede, "Failure", f"NIF/CIF {nif_cif} no coincide con el encontrado {nif_text} en el portal.")
                                    return False, (0, f"NIF/CIF no coincide. Encontrado: {nif_text}, Esperado: {nif_cif}"), None
                                else:
                                    self._log(logging.INFO, self.sede, "Success", f"NIF/CIF {nif_cif} encontrado en el portal.")
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error al buscar NIF/CIF en el portal: {e}")
                                return False, (0, f"Error al buscar NIF/CIF en el portal"), None
                        elif 'Correo electrónico' in label.text.strip():
                            try:
                                email_value = field.get_attribute('value').strip().lower()
                                if not email_value or email_value == "":              
                                    field.send_keys(self.mail)

                                    if self.mail == self.multivia.get('mail'):
                                        action = list(CERT_SEDES_ACTION.items())[0] # damos de alta
                                    else:
                                        action = list(CERT_SEDES_ACTION.items())[2] # añadimos mail de cliente
                                else:                                    
                                    if email_value != self.mail:
                                        field.clear()
                                        field.send_keys(self.mail)
                                        action = list(CERT_SEDES_ACTION.items())[3]

                                    elif email_value == self.multivia.get('mail'):
                                        field.clear()  # Limpiar el campo si es necesario
                                        field.send_keys(self.mail)
                                        action = list(CERT_SEDES_ACTION.items())[6] # damos de alta con el mail correcto
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error al añadir {self.mail} en el portal: {e}")
                                return False, (0, f"Error al buscar Email en el portal"), None                                            
                        
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, "Failure", f"Error al procesar la fila {index}")
                        continue               
                try:
                    try:
                        condiciones_check = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '/html/body/form/table[2]/tbody[2]/tr[16]/td[1]/input'))
                        )
                    except Exception as e:
                        condiciones_check = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="campos"]/form/table/tbody[2]/tr[16]/td[1]/input'))
                        )
                    condiciones_check.click()
                    random_wait(wait_type='MEDIUM', wait=True)

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al aceptar las condiciones del formulario")
                    return False, (0, f"Error al aceptar condiciones del formulario"), None

                try:
                    # Click the "Aceptar" button to submit the form
                    accept_button = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="btnFirma"]'))
                    )
                    accept_button.click()
                    random_wait(wait_type='LONG', wait=True)
                    self._log(logging.INFO, self.sede, "Success", "Formulario enviado correctamente.")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al enviar el formulario")
                    return False, (0, f"Error al enviar el formulario"), None
                
                random_wait(wait_type='LONG', wait=True)

                if action:
                    if WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="contenido_aplicacion"]'))
                    ):
                        return True, action, email_value
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "No se encontró el contenido de aplicación tras el alta.")
                        return False, (0, "No se encontró el contenido de aplicación tras el alta."), None
                                    
                return False, (0, f"Error en darse de alta en {self.portal_link}"), None
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Login fallido")
                return False, (0, "Login fallido"), None

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}"), None

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
