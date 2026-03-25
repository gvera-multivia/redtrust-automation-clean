import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.utils.setup import WebDriverSetup
from app.utils.utils import random_wait, CERT_SEDES_ACTION


class RobotAndalucia:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id : str,  module : str ="Altas", portal_link : str ='https://www.juntadeandalucia.es/servicios/sede.html', sede : str ='Andalucia',
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = 'https://www.juntadeandalucia.es/servicios/sede.html'
        self.module = module
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
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

    def _login_andalucia(self, driver) -> bool:
        try:
            driver.get("https://ws020.juntadeandalucia.es/Notifica/auth/login")
            # WebDriverWait(driver, WAIT_TIME['X_LONG']).until(
            #     EC.presence_of_element_located((By.XPATH, '//*[@id="slick-slide02"]/div/a'))
            # ).click()
            elements = driver.find_elements(By.XPATH, '//*[@id="botonCE"]')
            for element in elements:
                if element.text.strip() == "Cl@ve":
                    element.click()
                    break

            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
            ).click()

            xpaths = [
                '/html/body/app-root/app-perfil/main/div[2]/form'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)
            while time.time() < end_time:
                for xpath in xpaths:
                    if driver.find_elements(By.XPATH, xpath):
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True
                    
                if driver.find_elements(By.XPATH, '/html/body/app-root/app-buzon/main'):
                    driver.get('https://ws020.juntadeandalucia.es/Notifica/user/perfil/4')
                    random_wait(wait_type='MEDIUM', wait=True)
                    if driver.find_elements(By.XPATH, '/html/body/app-root/app-perfil/main/div[2]/form'):
                        self._log(logging.INFO, self.sede, "Success", "Login exitoso: /html/body/app-root/app-perfil/main/div[2]/form encontrado.")
                        return True
                    
                driver.get('https://ws020.juntadeandalucia.es/Notifica/user/perfil/1')
                random_wait(wait_type='LONG', wait=True)

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def subscribe(self, client_name: str, nif_cif: str) -> bool:
        # Crear una carpeta temporal para el perfil de usuario
        temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=self.portal_link,
            module="Altas",
            log_dir="logs/altas",
            filename=f"altas",
            cliente=self.cliente,
            execution_id=self.execution_id,
            task_id=self.sede,
            site=self.sede
        )
        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait(wait_type='LONG', wait=True)

        try:
            login = self._login_andalucia(driver)
            if login:
                area_perfil = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-perfil/main/div[1]/div/p'))   
                )
                if area_perfil.text.strip() == "Gestión de datos personales":
                    try:
                        # Obtener el texto del elemento y verificar si coincide con NIF o CIF
                        identificador = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-0"]'))
                        )


                        value = identificador.get_attribute("value")
                        if not value or value.strip() in ("", "*"):
                            self._log(logging.INFO, self.sede, "Pending", "El campo NIF/CIF no se ha encontrado o está vacío.")
                            
                            identificador.send_keys(nif_cif)

                            nombre_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-1"]'))
                            )
                            if nombre_field and (nombre_field.get_attribute("value") is None or nombre_field.get_attribute("value").strip() == ""):
                                nombre_field.send_keys(client_name)
                                
                        else:
                            if identificador.get_attribute("value").lower() != nif_cif.lower():
                                self._log(logging.ERROR, self.sede, "Failure", f"El texto del elemento no coincide con NIF o CIF {nif_cif}. Valor encontrado: {identificador.get_attribute('value')}")
                                return False, (0, f"El texto del elemento no coincide con NIF o CIF {nif_cif}. Valor encontrado: {identificador}")
                        
                        try: 
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-2"]'))
                            ).send_keys(self.mail)

                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-3"]'))
                            ).send_keys(self.mail)

                            # WebDriverWait(driver, WAIT_TIME['X_LONG']).until(
                            #     EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-4"]'))
                            # ).send_keys(self.multivia.get('phone'))
                            
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error al rellenar el formulario: {e}")
                            return False, (0, f"Error al rellenar el formulario: {e}")
                        
                        try: 
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-radio-2-input"]'))
                            ).click()
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-radio-5-input"]'))
                            ).click()
                            # Check the checkbox and submit the form
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-mdc-checkbox-1-input"]'))
                            ).click()

                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-perfil/main/div[4]/div/button[1]'))
                            ).click()
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error al hacer submit del formulario: {e}")
                            return False, (0, f"Error al hacer submit del formulario: {e}")

                        if self.n_mails == 1:
                            if self.mail == self.multivia.get('mail'):
                                action = list(CERT_SEDES_ACTION.items())[1]
                            else:
                                action = list(CERT_SEDES_ACTION.items())[2]                             
                            
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error Datos de contacto fallido: {e}")
                        return False, (0, f"Error Datos de contacto fallido: {e}")
                    
                elif area_perfil.text.strip() == "Alta de abonado":
                    try:
                        # Obtener el texto del elemento y verificar si coincide con NIF o CIF
                        identificador = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-0"]'))
                        ).get_attribute("value")

                        if identificador != nif_cif:
                            self._log(logging.ERROR, self.sede, "Failure", f"El texto del elemento no coincide con NIF o CIF {nif_cif}. Valor encontrado: {identificador}")
                            return False, (0, f"El texto del elemento no coincide con NIF o CIF {nif_cif}. Valor encontrado: {identificador}")
                        
                        try: 
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-2"]'))
                            ).send_keys(self.mail)

                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-3"]'))
                            ).send_keys(self.mail)

                            # WebDriverWait(driver, WAIT_TIME['X_LONG']).until(
                            #     EC.presence_of_element_located((By.XPATH, '//*[@id="mat-input-4"]'))
                            # ).send_keys(self.multivia.get('phone'))
                            
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error al rellenar el formulario: {e}")
                            return False, (0, f"Error al rellenar el formulario: {e}")
                        
                        try: 
                            # Check the checkbox and submit the form
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-mdc-checkbox-1-input"]'))
                            ).click()

                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/app-root/app-perfil/main/div[4]/div/button[1]'))
                            ).click()
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error al hacer submit del formulario: {e}")
                            return False, (0, f"Error al hacer submit del formulario: {e}")

                        if self.n_mails == 1:
                            action=list(CERT_SEDES_ACTION.items())[0]                     

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error Datos de contacto fallido: {e}")    
                        return False, (0, f"Error Datos de contacto fallido: {e}")

                random_wait(wait_type='LONG', wait=True)

                # Verificación
                try:
                    verification = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="mat-snack-bar-container-live-0"]/div/simple-snack-bar/div[1]'))
                    )
                    if (verification.text.strip() == f"Alta de persona física {nif_cif} realizada correctamente" 
                        or verification.text.strip() == f"Usuario modificado correctamente"):
                        self._log(logging.INFO, self.sede, "Success", "Alta en sede verificado.")
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="mat-snack-bar-container-live-0"]/div/simple-snack-bar/div[2]/button'))
                        ).click()
                        
                        return True, action
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "Alta no verificado.")
                        return False, (0, "Alta no verificado.")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en verificación: {e}")
                    return False, (0, f"Error en verificación: {e}")
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login.")
                return False, (0, "Error en login.")

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"⚠️ Error en darse de alta en {self.portal_link}: {e}")

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
