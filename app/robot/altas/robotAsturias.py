import logging
from multiprocessing import Queue
import tempfile, time, os, shutil
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait
from app.helper.loggerV2 import LoggerV2


class RobotAsturias:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link : str ='https://tramita.asturias.es/sta/CarpetaPrivate/Login?APP_CODE=STA&PAGE_CODE=DATOS_PERSONALES', sede : str ='asturias',
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

    def _login_asturias(self, driver) -> bool:
        try: 
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="link-certificado"]'))
                ).click()
            except Exception:
                try:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
                    ).click()
                except Exception:
                    pass

            xpaths = [
                '//*[@id="page_SINGLE_NOTIF"]',
                '//*[@id="aazone.NOTIFICACIONES"]',
                '//*[@id="aazone.DATOS_PERSONALES"]'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths: 
                    if driver.find_elements(By.XPATH, xpath): 
                        driver.get("https://tramita.asturias.es/sta/CarpetaPrivate/Login?APP_CODE=STA&PAGE_CODE=DATOS_PERSONALES")
                        driver.switch_to.window(driver.window_handles[-1])
                        return True 
                random_wait(wait_type='SHORT', wait=True)

            return False

        except Exception as e:
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)
    
    def _modify_contact_information(self, driver):
        try:
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="phone"]'))).send_keys(self.multivia.get('phone'))
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="mail"]'))).send_keys(self.multivia.get('mail'))
            random_wait(wait_type='MEDIUM', wait=True)
            buttons = driver.find_elements(By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/a')
            for button in buttons:
                if button.text.strip() == 'Continuar' or button.text.strip() == 'Aceptar' or button.text.strip() == 'Guardar':
                    button.click()
                    break
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al modificar la información de contacto: {e}")

    def _check_contact_information(self, driver):
        try:
            random_wait(wait_type='MEDIUM', wait=True)
            check = False
            fields = driver.find_elements(By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/dl/div')
            for field in fields:
                label = WebDriverWait(field, random_wait(wait_type='LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, './dt'))).text.strip()
                value = WebDriverWait(field, random_wait(wait_type='LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, './dd'))).text.strip()
                if ('Teléfono' in label and value == self.multivia.get('phone')) or ('Correo' in label and value == self.multivia.get('mail')):
                    check = True
                else:
                    check = False
            return check
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al verificar la información de contacto: {e}")
            return False

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
            login = self._login_asturias(driver)
            if login:   
                self._log(logging.INFO, self.sede, "Success", f"Login exitoso en {self.portal_link}")
                try:
                    confirm_message = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until( 
                        EC.presence_of_element_located((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/span'))
                    ).text
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", "⚠️ Error al obtener la confirmación de contacto")
                    confirm_message = None
                if confirm_message:
                    if confirm_message.strip() == "¿Los medios de contacto son correctos?" :
                        try:
                            check = self._check_contact_information(driver)
                            if check:                                   
                                buttons = driver.find_elements(By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/a')
                                for button in buttons:
                                    if button.text.strip().lower() == 'sí':
                                        button.click()
                                        break
                                verificación = self._check_contact_information(driver)
                                if verificación:
                                    self._log(logging.INFO, self.sede, "Success", "Los medios de contacto se han verificado.")
                                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[4]/div/a'))).click()
                                    return True, list(CERT_SEDES_ACTION.items())[6]
                                else:
                                    self._log(logging.ERROR, self.sede, "Failure", "Los medios de contacto NO se han verificado correctamente.")
                                    return False, (0, "Los medios de contacto NO se han verificado correctamente.")
                            else:
                                buttons = driver.find_elements(By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/a')
                                for button in buttons:
                                    if button.text.strip().lower() == 'no':
                                        button.click()
                                        break
                                random_wait(wait_type='MEDIUM', wait=True)
                                self._modify_contact_information(driver)
                                verificación = self._check_contact_information(driver)
                                if verificación:
                                    self._log(logging.INFO, self.sede, "Success", "Los medios de contacto se han verificado.")
                                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[4]/div/a'))).click()
                                    if self.mail == self.multivia.get('mail'):
                                        return True, list(CERT_SEDES_ACTION.items())[1]
                                    else:
                                        return True, list(CERT_SEDES_ACTION.items())[2]
                                else:
                                    self._log(logging.ERROR, self.sede, "Failure", "Los medios de contacto NO se han verificado correctamente.")
                                    return False, (0, "Los medios de contacto NO se han verificado correctamente.")
                        except Exception as e:
                            self._log(logging.ERROR,self.sede, "Failure", f"⚠️ Error al comprobar los medios de contacto: {e}")
                            return False, (0, "Error al comprobar los medios de contacto.")
                    elif confirm_message.strip() == "Los medios de contacto han sido confirmados.":
                        try:
                            check = self._check_contact_information(driver)
                            if check:    
                                return True, list(CERT_SEDES_ACTION.items())[6]
                            else:                               
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/a'))).click()
                                self._modify_contact_information(driver)
                                verificación = self._check_contact_information(driver)
                                if verificación:
                                    self._log(logging.INFO, self.sede, "Success", "Los medios de contacto se han verificado.")
                                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[4]/div/a'))).click()
                                    if self.mail == self.multivia.get('mail'):
                                        return True, list(CERT_SEDES_ACTION.items())[1]
                                    else:
                                        return True, list(CERT_SEDES_ACTION.items())[2]
                                else:
                                    self._log(logging.ERROR, self.sede, "Failure", "Los medios de contacto NO se han verificado correctamente.")
                                    return False, (0, "Los medios de contacto NO se han verificado correctamente.")
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al verificar los medios de contacto: {e}")
                            return False, (0, "Error al verificar los medios de contacto.")
                else: 
                    check = self._check_contact_information(driver)
                    if check:
                        self._log(logging.INFO, self.sede, "Success", "Los medios de contacto son correctos.")                    
                        return True, list(CERT_SEDES_ACTION.items())[6]
                    else:
                        self._modify_contact_information(driver)
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="aazone.DATOS_PERSONALES"]/div/div/div/div[2]/div/div/a'))).click()
                        verificación = self._check_contact_information(driver)
                        if verificación:
                            self._log(logging.INFO, self.sede, "Success", "Los medios de contacto se han verificado.")
                            return True, list(CERT_SEDES_ACTION.items())[0]
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "Los medios de contacto NO se han verificado correctamente.")
                            return False, (0, "Los medios de contacto NO se han verificado correctamente.")
            else:
                self._log(logging.ERROR,self.sede, "Failure", "Error en el login")
                return False, (0, "Error en el login")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")
        finally:
            # Cerrar navegador después de completar la acción
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)