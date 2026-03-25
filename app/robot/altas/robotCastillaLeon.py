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

class RobotCastillaLeon:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link: str ='https://www.ae.jcyl.es/notifica/#/', sede : str ='castilla y león', 
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
        

    def login_castillaLeon(self, driver) -> bool:
        try:
            # /html/body/main/app-root/app-inicio/div/div[2]/div[2]/table/tbody/tr[1]/td/button
            # /html/body/main/app-root/app-inicio/div/div[2]/div[2]/table/tbody/tr[2]/td/div/button
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '/html/body/main/app-root/app-inicio/div/div[2]/div[2]/table/tbody/tr[1]/td/button'))
            ).click()

            random_wait(wait_type='LONG', wait=True)

            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
            ).click()
            
            random_wait(wait_type='LONG', wait=True)

            xpaths = [
                '/html/body/main/app-root/app-notificaciones-acceso',
                # '//*[@id="menu"]',
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
            login = self.login_castillaLeon(driver)
            action = None
            if login:
                try:
                    WebDriverWait(driver, random_wait(wait_type='XX_LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="menu"]/li[2]/a'))
                    ).click()

                    # driver.get(F"{self.portal_link}/bec/editar") 
                    random_wait(wait_type='MEDIUM', wait=True)

                    fields = []
                    container_divs = driver.find_elements(By.XPATH, '/html/body/main/app-root/app-bec-editar/div/div/form/fieldset/div/div')
                    for container in container_divs:
                        inner_divs = container.find_elements(By.XPATH, './div')

                        for div in inner_divs:
                            fields.append(div)

                    self._log(logging.INFO, self.sede, "Pending", f"Campos encontrados: {len(fields)}")
                    for field in fields:
                        try:
                            label = field.find_element(By.XPATH, './/label')
                            label_text = label.text.strip()

                            # if 'CIF' in label_text:
                            #     input_field = field.find_element(By.XPATH, './/input')
                            #     input_value = input_field.text.strip()
                            #     if input_value != nif_cif:
                            #         self_log(logging.ERROR, f"CIF no coincide: {input_value} != {nif_cif}")
                            #         return False

                            if 'Correo' in label_text:
                                email_field = field.find_element(By.XPATH, './/input')
                                email_value = email_field.get_attribute('value')

                                if email_value: 
                                    if self.mail == email_value and self.n_mails == 1:
                                        self._log(logging.INFO, self.sede, "Success", f"El correo {email_value} ya está registrado.")
                                        action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                                    
                                    elif self.mail != email_value and self.multivia.get('mail') == email_value:
                                        self._log(logging.INFO, self.sede, "Pending", f"El correo MULTIVIA sustituido por cliente: {email_value}")
                                        action = list(CERT_SEDES_ACTION.items())[4]  # 5: MULTIVIA sustituido por cliente

                                    else:
                                        self._log(logging.ERROR, self.sede, "Failure", "Impossible añadir el correo del cliente")
                                        return False, (-1, "Impossible añadir el correo del cliente")

                                else:
                                    if self.mail == self.multivia.get('mail'):
                                        self._log(logging.INFO, self.sede, "Success", "Alta realizada correctamente")
                                        action = list(CERT_SEDES_ACTION.items())[0]  # 1: alta realizada correctamente
                                    else:
                                        self._log(logging.INFO, self.sede, "Success", "Correo cliente añadido")
                                        action = list(CERT_SEDES_ACTION.items())[2]  # 3: correo cliente añadido

                                    email_field.clear()
                                    email_field.send_keys(self.mail)

                                    random_wait(wait_type='LONG', wait=True)

                            # elif 'Teléfono' in label_text:
                            #     input_field = field.find_element(By.XPATH, './/input')
                            #     input_field.clear()
                            #     input_field.send_keys(self.multivia['phone'])

                        except Exception as e:
                            self._log(logging.INFO, self.sede, "Pending", f"Error procesando campo: {field.text.strip()}")
                            continue
                            
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/main/app-root/app-bec-editar/div/div/form/div/button'))
                    ).click()

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error introduciendo datos personales: {e}")
                    return False, (0, f"Error introduciendo datos personales: {e}")

                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="cboxLoadedContent"]/button'))
                ).click()

                random_wait(wait_type='LONG', wait=True)

                if not action: 
                    if self.mail == self.multivia.get('mail'):
                        action = list(CERT_SEDES_ACTION.items())[0]
                    else:
                        action = list(CERT_SEDES_ACTION.items())[2]


                return True, action

            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
