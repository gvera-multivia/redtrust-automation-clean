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

class RobotAtib:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link : str ='https://sede.atib.es/cva/perfil', sede : str ='atib',
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


    def _login_atib(self, driver) -> bool:
        try: 
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="root"]/div[2]/main/div/div[1]/div/div/div[1]/div/div[2]/button'))
            ).click()
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '/body/div[5]/div[3]/div/div/form/div/div[6]/button'))
            ).click()
            random_wait(wait_type='MEDIUM', wait=False)
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                ).click()
            except Exception as e:
                self._log(logging.INFO, self.sede, "Pending", f"Botón adicional no encontrado o no necesario: {e}")
                return False

            xpaths = '/html/body/div[6]/div[3]/div'

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths: 
                    if driver.find_elements(By.XPATH, xpath): 
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True 
                random_wait(wait_type='SHORT', wait=False)
            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=False)

    def _subscribe(self, direccion: dict ) -> bool:
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
            site=self.sede
        )
        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait(wait_type='LONG', wait=False)

        try: 

            if self._login_atib(driver):
                try:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/body/div[6]/div[3]/div/div[3]/a'))
                    ).click()
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div[5]/div[3]/div'))
                    )
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div[3]/div/div[3]/button'))
                    ).click()
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error accediendo al formulario de alta: {e}")
                    return False, (0, f"Error accediendo al formulario de alta")
                
                try:
                    campos = driver.find_elements(By.XPATH, '/html/body/div[5]/div[3]/div/div[2]/div[2]/div/div')
                    for campo in campos:
                        try:
                            label_elem = campo.find_element(By.XPATH, './div/label')
                            label_text = label_elem.text.strip()
                            if label_text == "Calle":
                                input_elem = campo.find_element(By.XPATH, './/div/div/div/div/input')
                                input_elem.clear()
                                input_elem.send_keys(direccion.get('calle'))
                            elif label_text == "Codigo Postal":
                                input_elem = campo.find_element(By.XPATH, './/div/div/div/div/input')
                                input_elem.clear()
                                input_elem.send_keys(direccion.get('codigo_postal'))
                            elif label_text == "Provincia":
                                select_elem = campo.find_element(By.XPATH, './/div/div/select')
                                for option in select_elem.find_elements(By.TAG_NAME, 'option'):
                                    if option.text.strip().upper() == direccion.get('provincia').upper():
                                        option.click()
                                        break
                            elif label_text == "Municipio":
                                select_elem = campo.find_element(By.XPATH, './/div/div/select')
                                for option in select_elem.find_elements(By.TAG_NAME, 'option'):
                                    if option.text.strip().upper() == direccion.get('poblacion').upper():
                                        option.click()
                                        break
                            elif label_text == "Población":
                                select_elem = campo.find_element(By.XPATH, './/div/div/select')
                                for option in select_elem.find_elements(By.TAG_NAME, 'option'):
                                    if option.text.strip().upper() == direccion.get('poblacion').upper():
                                        option.click()
                                        break
                        except Exception as e:
                            self._log(logging.INFO, self.sede, "Pending", f"Campo {label_text if 'label_text' in locals() else ''} no procesado: {e}")
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[5]/div[3]/div/div[3]/button[2]'))
                    ).click()
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al completar el formulario de datos personales: {e}")
                    return False, (0, f"Error al completar el formulario de datos personales")
                
                self._log(logging.INFO, self.sede, "Success", "Suscripción completada correctamente")
                # return True, (1, "Suscripción completada correctamente")
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en el login")
                return False, (0,"Error en el login")

        except Exception as e:
            self._log(logging.INFO, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")

        finally:
            random_wait(wait_type='LONG', wait=False)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
