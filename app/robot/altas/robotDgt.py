from multiprocessing import Queue
import os, shutil, time, tempfile
import uuid
import logging

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.helper.errors.base import ErrorBase
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait


class RobotDGT:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link : str ='https://sede.dgt.gob.es/es/multas/direccion-electronica-vial', sede : str ='dev',
            n_mails : int = 3,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = 'https://sede.dgt.gob.es/es/multas/direccion-electronica-vial/'
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


    def _login_dgt(self, driver):
        try:            
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="columna1"]/div[1]/div/div/div[1]/a'))
            ).click()

            driver.switch_to.window(driver.window_handles[-1])
            random_wait(wait_type='MEDIUM', wait=True)

            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="content"]/div/div/form/div/div[2]/a'))
            ).click()
            
            
            xpaths = [
                '//*[@id="nombreForm"]/div[2]',
                '//*[@id="listadoNotificacionesForm"]'
            ]

            error_paths = [
                '//*[@id="main-frame-error"]',
                '//*[@id="contenidoSSO"]/div[2]/p'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:
                try:
                    try:
                        for error_path in error_paths:
                            error = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, error_path))
                            )
                            if error:
                                self._log(logging.DEBUG, self.sede, 'Pending', f"Error page found: {error_path}")
                                break
                    except Exception as e:
                        error = None
                        self._log(logging.DEBUG, self.sede, 'Pending', f"No error page found: {e}")


                    if error:
                        self._log(logging.ERROR, self.sede, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, 'Error al procesar la solicitud de login')))
                        return False
                    else:
                        for xpath in xpaths:
                            try:
                                element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, xpath))
                                )
                                if element:
                                    self._log(logging.DEBUG, self.sede, 'Success', f"Login exitoso: {xpath} encontrado.")
                                    return True
                            except Exception as e:
                                self._log(logging.DEBUG, self.sede, 'Pending', f"No se encontró el elemento {xpath}: {e}")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, 'Failure', f"⚠️ Error al esperar el elemento: {e}")
                    random_wait(wait_type='MEDIUM', wait=True)
                    continue

            self._log(logging.ERROR, self.sede, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, 'Timeout al esperar el login')))
            return False
        except Exception as e:
            self._log(logging.ERROR, self.sede, 'Failure', str(ErrorBase.ErrorLoginSede(self.sede, e)))
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
            login = self._login_dgt(driver)
            if not login:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")

            # Continuar con el proceso de alta si el login fue exitoso
            try:
                email_input = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="nombreForm:correoElectronico"]'))
                )
                email_value = email_input.get_attribute('value')

                if email_value:
                    if self.mail not in email_value:
                        email_array = email_value.split(";")
                        if len(email_array) < self.n_mails:
                            email_array.append(self.mail)
                            email_input.clear()
                            emails = "; ".join(email_array)
                            email_input.send_keys(emails)
                            if self.mail == self.multivia.get('mail'):
                                action = list(CERT_SEDES_ACTION.items())[1]
                            else:
                                action = list(CERT_SEDES_ACTION.items())[2]
                        else:
                            self._log(logging.WARNING, self.sede, "Pending", f"No se puede añadir el correo {self.mail} porque ya hay {self.n_mails} correos.")
                            return False, (0, f"No se puede añadir el correo {self.mail} porque ya hay {self.n_mails} correos.")
                    else:
                        action = list(CERT_SEDES_ACTION.items())[6]
                else:
                    email_input.send_keys(self.mail)
                    action = list(CERT_SEDES_ACTION.items())[0]
                self._log(logging.INFO, self.sede, "Success", f"Se ha añadido el correo {self.mail} correctamente.")

                # Optimización: intentar secuencialmente los botones relevantes para continuar el proceso
                botones_xpath = [
                    '//*[@id="nombreForm:toggleAllMarcado2"]',
                    '//*[@id="nombreForm:toggleAllSimMarcar"]',
                    '//*[@id="formFirma:botonFirmar"]',
                    '//*[@id="nombreForm:modificar"]',
                    '//*[@id="nombreForm:botonFirmar"]'
                ]
                boton_clicado = False
                for xpath in botones_xpath:
                    try:
                        boton = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        boton.click()
                        if xpath == '//*[@id="nombreForm:toggleAllSimMarcar"]' or xpath == '//*[@id="nombreForm:toggleAllMarcado2"]':
                            random_wait(wait_type='MEDIUM', wait=True)
                            continue 
                        elif xpath == '//*[@id="nombreForm:modificar"]':
                            WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(                                    
                                EC.element_to_be_clickable((By.XPATH,'//*[@id="formFirma:botonFirmar"]'))
                            ).click()
                            boton_clicado = True
                            self._log(logging.INFO, self.sede, "Success", f"Botón encontrado y clicado: {xpath}")
                            random_wait(wait_type='MEDIUM', wait=True)
                            break
                        
                        else:
                            boton_clicado = True
                            self._log(logging.INFO, self.sede, "Success", f"Botón encontrado y clicado: {xpath}")
                            random_wait(wait_type='MEDIUM', wait=True)
                            break
                            
                    except Exception:
                        self._log(logging.WARNING, self.sede, "Pending", f"Botón no encontrado o no clicable: {xpath}")
                        continue

                if not boton_clicado:
                    self._log(logging.ERROR, self.sede, "Failure", "No se pudo hacer clic en ningún botón para continuar el proceso.")
                    return False, (0, "Error al continuar el proceso de alta.")

                random_wait(wait_type='MEDIUM', wait=True)

                # Confirmación final
                try:
                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="_id129"]/div[3]/input'))
                    ).click()
                except Exception:
                    self._log(logging.WARNING, self.sede, "Pending", "No se pudo hacer clic en el botón de confirmación final.")

                random_wait(wait_type='MEDIUM', wait=True)

                # Verificación
                try:
                    check = driver.find_element(By.XPATH, '//*[@id="centro"]/div[5]/div/div')
                    if ("finalizó satisfactoriamente" in check.text):
                        self._log(logging.INFO, self.sede, "Success", "✅ Suscripción exitosa")
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="dato"]/input[1]'))
                        ).click()
                        return True, action
                    else:
                        return False, (0, "Error: Verificando.")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al verificar el resultado: {e}")
                    return False, (0, "Error al verificar el resultado.")
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error al verificar el resultado: {e}")
                return False, (0, "Error al verificar el resultado.")
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")
        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
