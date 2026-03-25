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


class RobotCastillaLaMancha:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link: str = 'https://notifica.jccm.es/notifica/', sede: str = 'castilla la mancha',
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
        
    def _login_castillalamancha(self, driver) -> bool:
        try:
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="form1"]/div/input'))
            ).click()
            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
            ).click()

            xpaths = [
                '//*[@id="form1"]/div[1]/table',
                '//*[@id="contenido_ppal.sin_dcha"]'
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

    def _check_mail(self, driver) -> bool:
        try:
            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="_idJsp5:_idJsp8"]'))
            ).click()
            random_wait(wait_type='MEDIUM', wait=True)


            email_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="form1:email"]'))
            )
            email_value = email_field.get_attribute('value')
            email_return = None
            if email_value:
                if self.mail == email_value and self.n_mails == 1:
                    self._log(logging.INFO, self.sede, "Success", f"El correo {email_value} ya está registrado.")
                    action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                elif self.mail != email_value and self.multivia.get('mail') == email_value:
                    email_return = email_value
                    self._log(logging.INFO, self.sede, "Pending", f"El correo MULTIVIA sustituido por cliente: {email_value}")
                    action = list(CERT_SEDES_ACTION.items())[1]  # 5: MULTIVIA sustituido por cliente
                else:
                    email_field.clear()
                    email_field.send_keys(self.mail)
                    action = list(CERT_SEDES_ACTION.items())[2]  # 6: correo cliente no añadido
                    self._log(logging.INFO, self.sede, "Success", f"Correo cliente añadido: {self.mail}")
                    email_return = email_value
            else:
                email_field.clear()
                email_field.send_keys(self.mail)
                action = list(CERT_SEDES_ACTION.items())[0]  # 1: alta

            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="form1:_idJsp15"]'))
            ).click()
            return action, True, email_return

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error al verificar el correo: {e}")
            return None, False
        
    def subscribe(self, id_cliente: str, nif_cif: str, tipo_cliente: str) -> bool:
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

        sede_mail = None

        try:
            if self._login_castillalamancha(driver):
                if tipo_cliente == 'Empresa':
                    try:
                        table = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_all_elements_located((By.XPATH,  '//*[@id="form1"]/div[1]/table/tbody/tr'))
                        )
                        found = False
                        for index, row in enumerate(table):
                            label = row.find_element(By.XPATH, './/td/label')
                            self._log(logging.DEBUG, self.sede, "Pending", f"{index}: {label.text}")
                            if nif_cif in label.text:
                                label.click()
                                found = True
                                break
                        if not found:
                            self._log(logging.ERROR, self.sede, "Failure", "No cliente identificador found in sede")
                            return False, (0, "No cliente identificador found in sede"), None
                        random_wait(wait_type='MEDIUM', wait=True)
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="form1:envio"]'))
                        ).click()
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error en seleccionar buzón: {e}")
                        return False, (0, "Error en seleccionar buzón"), None

                
                try:
                    alta = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="form1:_idJsp4"]'))
                    )
                except Exception as e:
                    alta = None

                if alta:
                    if alta and alta.get_attribute('value') == "Alta":
                        try:
                            email_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="form1:_idJsp2"]'))
                            )
                            email_value = email_field.get_attribute('value')
                            if email_value: 
                                if self.mail == email_value and self.n_mails == 1:
                                    self._log(logging.INFO, self.sede, "Success", f"El correo {email_value} ya está registrado.")
                                    action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                                elif self.mail != email_value and self.multivia.get('mail') == email_value:
                                    self._log(logging.INFO, self.sede, "Pending", f"El correo MULTIVIA sustituido por cliente: {email_value}")
                                    action = list(CERT_SEDES_ACTION.items())[4]  # 5: MULTIVIA sustituido por cliente
                                    sede_mail = email_value
                                else:
                                    self._log(logging.INFO, self.sede, "Pending", "El alta esta realizada con el mail correcto")
                                    action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada correctamente
                                    sede_mail = email_value
                            else:
                                if self.mail == self.multivia.get('mail'):
                                    self._log(logging.INFO, self.sede, "Success", "Alta realizada correctamente")
                                    action = list(CERT_SEDES_ACTION.items())[0]  # 1: alta realizada correctamente
                                else:
                                    self._log(logging.INFO, self.sede, "Success", "Correo cliente añadido")
                                    action = list(CERT_SEDES_ACTION.items())[0]  # 3: correo cliente añadido
                                email_field.clear()
                                email_field.send_keys(self.mail)
                            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="form1:_idJsp4"]'))
                            ).click()
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error en ingresar los datos de contacto: {e}")
                            return False, (0, "Error en ingresar los datos de contacto"), None
                    else:
                        driver.get('https://notifica.jccm.es/notifica/faces/ModificacionTercero.jsp')
                        random_wait(wait_type='MEDIUM', wait=True)
                        rows = driver.find_elements(By.XPATH, '//*[@id="form1"]/div/table/tbody/tr')
                        for index, row in enumerate(rows):
                            label = row.find_element(By.XPATH, './td[1]/b')
                            if "DNI" in label.text:
                                value = row.find_element(By.XPATH, './td[2]/label')
                                if not nif_cif in value.text:
                                    self._log(logging.ERROR, self.sede, "Failure", f"Error de cliente por {nif_cif}")
                                    return False, (0, f"Error de cliente por {nif_cif}"), None
                            if "Correo" in label.text:
                                email_field = row.find_element(By.XPATH, './/*[@id="form1:email"]')
                                email_value = email_field.get_attribute('value')
                                if email_value: 
                                    if self.mail == email_value and self.n_mails == 1:
                                        self._log(logging.INFO, self.sede, "Pending", f"El correo {email_value} ya está registrado.")
                                        action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada
                                    elif self.mail != email_value and self.multivia.get('mail') == email_value:
                                        self._log(logging.INFO, self.sede, "Pending", f"El correo MULTIVIA sustituido por cliente: {email_value}")
                                        action = list(CERT_SEDES_ACTION.items())[4]  # 5: MULTIVIA sustituido por cliente
                                        sede_mail = email_value
                                    else:
                                        self._log(logging.INFO, self.sede, "Pending", "El alta esta realizada con el mail correcto")
                                        action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada correctamente
                                        sede_mail = email_value
                                else:
                                    if self.mail == self.multivia.get('mail'):
                                        self._log(logging.INFO, self.sede, "Pending", "Alta realizada correctamente")
                                        action = list(CERT_SEDES_ACTION.items())[1]  # 1: alta realizada correctamente
                                    else:
                                        self._log(logging.INFO, self.sede, "Pending", "Correo cliente añadido")
                                        action = list(CERT_SEDES_ACTION.items())[2]  # 3: correo cliente añadido
                                    email_field.clear()
                                    email_field.send_keys(self.mail)
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="form1:_idJsp15"]'))
                        ).click()
                    random_wait(wait_type='LONG', wait=True)
                    container = driver.find_element(By.XPATH, '//*[@id="contenido_ppal.sin_dcha"]')
                    title = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/h3'))
                    )
                    self._log(logging.INFO, self.sede, "Success", f"Title: {title.text}, nif_cif: {nif_cif}")
                    return True, action, sede_mail
                else:
                    action, check, sede_mail = self._check_mail(driver)
                    if check:
                        self._log(logging.INFO, self.sede, "Success", f"Correo verificado: {self.mail}")
                        return True, action, sede_mail
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "Error al verificar el correo")
                        return False, (0, "Error al verificar el correo"), None

            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login"), None
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}"), None
        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
