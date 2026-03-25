from multiprocessing import Queue
import tempfile, time, os, shutil, re
import uuid
import logging

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait


class RobotTerrassa:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link: str = 'https://tributs.terrassa.cat/ct/082790/ATERRASSA/', sede: str = 'oficina virtual ayuntamiento terrassa',
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

    def _login_terrassa(self, driver) -> bool:
        try:
            try:
                # //*[@id="app"]/div/div/div[2]/div/div/div[1]/div/div[2]/aside/article/div[2]/ul/li/a
                random_wait(wait_type='LONG', wait=True)
                WebDriverWait(driver,  random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div[5]/div/div'))
                )

                random_wait(wait_type='MEDIUM', wait=True) 

                reject_cookies_btn = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="btn-reject-cookies"]'))
                )
                reject_cookies_btn.click()
            except Exception:
                self._log(logging.INFO, self.sede, "Pending", "No se encontró el botón de cookies o ya fueron aceptadas.")
            

            try:
                # //*[@id="opcion-login-aut.aoc"]//*[@id="opcion-login-aut.certificado"]
                try:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="opcion-login-aut.aoc"]'))
                    ).click()
                except Exception:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="app"]/div[1]/div/div[2]/div/div/div[1]/div/div[2]/aside/article/div[2]/ul/li/a'))
                    ).click()
                random_wait(wait_type='LONG', wait=True)

                end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)
                while time.time() < end_time:
                    try:
                        try:
                            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCertCaptcha"]'))
                            ).click()
                        except Exception:
                            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCert"]'))
                            ).click()

                        try:
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '//*[@id="modalCertificat"]/div/div/div[3]/button'))
                            ).click()
                        except Exception:
                            pass

                        # If neither button is present, break; if any is present, continue
                        if not (driver.find_elements(By.XPATH, '//*[@id="btnContinuaCert"]') or driver.find_elements(By.XPATH, '//*[@id="btnContinuaCertCaptcha"]')):
                            break
                    except Exception as e:  
                        random_wait(wait_type='SHORT', wait=True)
                        continue

                if time.time() >= end_time:
                    raise TimeoutError("Timeout while waiting for certificate login buttons to appear.")
            except Exception as e:  
                self._log(logging.ERROR, self.sede, "Failure", f"Error accediendo al login con certificado: {e}")


            # Intentar login con AOC en bucle hasta que aparezca el formulario o pasen 30 segundos
            xpath = '//*[@id="main-role"]/article/form'
            start_time = time.time()
            while time.time() - start_time < random_wait(wait_type='XX_LONG', wait=False):
                try:
                    reject_cookies_btn = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="btn-reject-cookies"]'))
                    )
                    reject_cookies_btn.click()
                except Exception:
                    self._log(logging.DEBUG, self.sede, "Pending", "No se encontró el botón de cookies o ya fueron aceptadas.")                

                try:
                    element= WebDriverWait(driver, random_wait(wait_type='XX_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )

                    if element.is_displayed():
                        self._log(logging.INFO, self.sede, "Success", "Login exitoso en Terrassa")

                        return True
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "Login fallido en Terrassa: Elemento no visible")
                        return False
                except Exception:
                    random_wait(wait_type='LONG', wait=True)
                    return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False
    

    def subscribe(self, client_name:str, tipo_cliente:str, nif_cif: str, direccion: str) -> bool:
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
            if self._login_terrassa(driver):
                # Accept cookies if the button exists
                try:
                    WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="app"]/div[5]/div/div'))
                    )

                    reject_cookies_btn = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="btn-reject-cookies"]'))
                    )
                    reject_cookies_btn.click()
                except Exception:
                    self._log(logging.DEBUG, self.sede, "Pending", "No se encontró el botón de cookies o ya fueron aceptadas.")

                try:
                    # Esperar a que el campo NIF/CIF esté presente
                    nif_input = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-nif"]'))
                    )

                    nif_value = nif_input.get_attribute("value")

                    if nif_value.strip().upper() != nif_cif.strip().upper():
                        self._log(logging.ERROR, self.sede, "Failure", f"NIF/CIF en el formulario ({nif_value}) no coincide con el proporcionado ({nif_cif})")
                        return False, (0, f"NIF/CIF en el formulario ({nif_value}) no coincide con el proporcionado ({nif_cif})"), None

                    self._log(logging.INFO, self.sede, "Success", f"NIF/CIF validado correctamente: {nif_value}")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al validar el NIF/CIF: {e}")
                    return False, (0, f"Error al validar el NIF/CIF: {e}"), None
                
                # Rellenar el formulario de suscripción usando WebDriverWait en todos los elementos
                try:
                    try:
                        nombre_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-nombre"]'))
                        )
                                    
                        if tipo_cliente.lower() == 'particular':
                            name = client_name.split(' ')
                            if name and len(name) > 3:
                                nombre = name[0] + " " + name[1]
                                apellido = name[2]
                            else:
                                nombre = name[0] 
                                apellido = name[1]
                            
                            apellido_input = WebDriverWait(driver, 10).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-apellido1"]'))
                            )

                            nombre_input.clear()
                            nombre_input.send_keys(nombre)

                            apellido_input.clear()
                            apellido_input.send_keys(apellido)  # Rellenar si tienes el dato
                        else:
                            nombre_input.clear()
                            nombre_input.send_keys(client_name)
                            apellido_input = None

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error al rellenar los datos del cliente")
                        return False, (0, f"Error al rellenar los datos del cliente"), None
                
                    try:
                        municipio_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-municipio"]'))
                        )
                        provincia_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-provincia"]'))
                        )
                        tipo_via_dropdown = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="txt-ciudadano-tipo-via"]'))
                        )
                        direccion_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-direccion"]'))
                        )
                        numero_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="main-role"]/article/form/div[3]/div[5]/div/div/input'))
                        )
                        postal_input = WebDriverWait(driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-postal"]'))
                        )

                        municipio_input.clear()
                        municipio_input.send_keys(direccion.get('poblacion'))

                        random_wait(wait_type='MEDIUM', wait=True)

                        provincia_input.clear()
                        provincia_input.send_keys(direccion.get('provincia'))

                        random_wait(wait_type='MEDIUM', wait=True)

                        tipo_via_dropdown.click()
                        tipo_via_option = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="list-item-326-22"]/div/div'))
                        )
                        tipo_via_option.click()
                        

                        random_wait(wait_type='MEDIUM', wait=True)  

                        direccion_input.clear()
                        direccion_input.send_keys(direccion.get('calle')) 
                        random_wait(wait_type='MEDIUM', wait=True)

                        numero_input.clear()
                        calle = direccion.get('calle', '')
                        match = re.search(r'\d+', calle)
                        numero = match.group() if match else ''
                        numero_input.send_keys(numero)
                        random_wait(wait_type='MEDIUM', wait=True)

                        postal_input.clear()
                        postal_input.send_keys(direccion.get('codigo_postal'))  
                        random_wait(wait_type='MEDIUM', wait=True)

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error al rellenar los datos de domicilio")
                        return False, (0, f"Error al rellenar los datos del cliente"), None

                    email_field = WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="txt-ciudadano-email"]'))
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
                            email_field.clear()
                            email_field.send_keys(self.mail)
                            action = list(CERT_SEDES_ACTION.items())[3]
                        elif email_value == self.multivia.get('mail'):
                            email_field.clear()  # Limpiar el campo si es necesario
                            email_field.send_keys(self.mail)
                            action = list(CERT_SEDES_ACTION.keys())[6] # damos de alta con el mail correcto

                    random_wait(wait_type='MEDIUM', wait=True)  
                
                    try:
                        # Aceptar privacidad
                        privacidad_checkbox = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="txt-ciudadano-privacidad"]'))
                        )
                        privacidad_checkbox.click()

                        # Click en suscribirse
                        suscripcion_btn = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="txt-ciudadano-suscripcion"]'))
                        )
                        suscripcion_btn.click()

                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="btn-ciudadano-accion"]'))
                        ).click()
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error al aceptar tèrminos y políticas de privacidad")
                        return False, (0, f"Error al aceptar tèrminos y políticas de privacidad"), None

                    self._log(logging.INFO, self.sede, "Success", "Formulario de suscripción enviado correctamente.")
                    random_wait(wait_type='XX_LONG', wait=True, extra=30)
                    # return True, action, email_value
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error al rellenar el formulario de suscripción")
                    return False, (0, f"Error al rellenar el formulario de suscripción"), None

            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en el login")
                return False, (0, "Error en el login"), None             
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}"), None
        finally:
            random_wait(wait_type='XXX_LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
