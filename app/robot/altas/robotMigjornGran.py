import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googletrans import Translator, LANGUAGES

from selenium.webdriver.common.keys import Keys 
# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.utils.setup import WebDriverSetup
from app.utils.utils import random_wait, CERT_SEDES_ACTION, translate_direction


class RobotMigjornGran:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link : str ='https://www.carpetaciutadana.org/esmigjorn/Login/Login.aspx?URL=https://www.carpetaciutadana.org/esmigjorn/solicituds/iniciartramit.aspx¿TIPO=DNOT', sede : str ='migjorn gran',
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = 'https://www.carpetaciutadana.org/esmigjorn/Login/Login.aspx?URL=https://www.carpetaciutadana.org/esmigjorn/solicituds/iniciartramit.aspx¿TIPO=DNOT'
        self.module = module
        self.execution_id = execution_id
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.sede = sede
        self.multivia = multivia
        self.mail = mail
        self.n_mails = n_mails
        self.cliente = cliente
        self.date = date
        self.module = module
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

    def _login_migjorngran(self, driver) -> bool:
        try: 
            try:           
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_Content1_Button1"]'))
                ).click()
            except Exception as e:
                try:
                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/form/div[4]/div/div/div[2]/div[1]/div/div[1]/div/div[2]/input[1]'))
                    ).click()
                except Exception as e2:
                    self._log(logging.WARNING, self.sede, "Pending", f"No se pudo clicar el botón alternativo: {e2}")
                    try:
                        # último recurso: recargar la página principal del portal
                        driver.get(self.portal_link)
                        random_wait(wait_type='SHORT', wait=True)
                    except Exception as e3:
                        self._log(logging.ERROR, self.sede, "Failure", f"Fallo al recargar portal tras no poder clicar botones: {e3}")
            
            
            xpaths = [
                '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_pnlPersona"]/div[2]',
                '/html/body/form/div[4]/div/div/div[2]/div[1]/div/div[1]/div/div/div[2]/div/div/div/div[2]'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)
            while time.time() < end_time:
                for xpath in xpaths:
                    try:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, xpath))
                        )
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True
                    except Exception:
                        # No element found for this xpath within the wait time; continue with next xpath
                        pass

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def subscribe(self, tipo_cliente:str, direccion:dict, nif_cif: str) -> bool:
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
        directions_old = direccion.copy()

        try:
            login = self._login_migjorngran(driver)
            if login:
                action = None
                try:
                    try:
                        element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_NIF_I"]'))
                        )
                        nif_value = (element.get_attribute('value') or element.text or "").strip()

                        if nif_value.upper() == nif_cif.strip().upper():
                            self._log(logging.INFO, self.sede, "Success", f"NIF coincide: {nif_value}")
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", f"NIF no coincide. Esperado: {nif_cif}, Encontrado: {nif_value}")
                            return False, (0, f"NIF no coincide. Esperado: {nif_cif}, Encontrado: {nif_value}")         

                        try:                            
                            doc_input = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/form/div[4]/div/div/div[2]/div[1]/div/div[1]/div/div/div[2]/div/div/div/div[2]/div[2]/table/tbody/tr/td[2]/input[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_TIPODOC_I"]'))
                            )

                            if tipo_cliente.lower() == "particular":
                                doc_input.click()
                                random_wait(wait_type='SHORT', wait=True)
                                options = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, '/html/body/form/div[4]/div/div/div[2]/div[1]/div/div[1]/div/div/div[2]/div/div/div/div[2]/div[2]/div/div/div/div/table/tbody/tr/td/div/div[1]/table[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_TIPODOC_DDD_L_LBT"]/tr'))
                                )
                                for option in options:
                                    if 'DNI' in option.find_element(By.XPATH, './/td').text:
                                        option.click()
                                        break
                                # doc_input.send_keys('\n')
                                random_wait(wait_type='SHORT', wait=True)

                            elif tipo_cliente.lower() in ["empresa", "holding"]:
                                doc_input.click()
                                random_wait(wait_type='SHORT', wait=True)

                                options = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, '/html/body/form/div[4]/div/div/div[2]/div[1]/div/div[1]/div/div/div[2]/div/div/div/div[2]/div[2]/div/div/div/div/table/tbody/tr/td/div/div[1]/table[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_TIPODOC_DDD_L_LBT"]/tr'))
                                )
                                for option in options:
                                    if 'CIF' in option.find_element(By.XPATH, './/td').text:
                                        option.click()
                                        break
                                # doc_input.send_keys('\n')
                                random_wait(wait_type='SHORT', wait=True)

                            else:
                                self._log(logging.ERROR, self.sede, "Failure", f"Tipo de cliente no válido: {tipo_cliente}")
                                return False, (0, f"Tipo de cliente no válido: {tipo_cliente}")

                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al introducir identificador según tipo_cliente: {e}")
                            return False, (0, f"⚠️ Error al introducir identificador según tipo_cliente: {e}")

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al verificar NIF: {e}")
                        return False, (0, f"⚠️ Error al verificar NIF: {e}")
                    
                    try:
                        tries = 0
                        while tries < 3:
                            if tries == 0:
                                direccion = translate_direction(
                                    direccion=directions_old, 
                                    sede=self.sede, 
                                    log=self._log ,
                                    target_language='ca'
                                )
                            elif tries == 1:
                                # direccion = self.database_manager.get_direction_for_cliente(self.cliente, self.sede)
                                # and direccion = translate_direction(
                                    # direccion=direccion, 
                                    # sede=self.sede, 
                                    # log=self._log ,
                                    # target_language='ca'
                                # )
                                print("TODO: Implementar otra estrategia de corrección si la traducción falla dos veces.")
                            else:
                                direccion = directions_old  # Revertir a la dirección original en el último intento
                                
                            try:
                                fields = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_pnlPersona"]/div[2]/div'))
                                )

                                for index, field in enumerate(fields, start=1): 
                                    # aceptar alertas de Chrome si aparecen (puede haber varias seguidas)
                                    try:
                                        WebDriverWait(driver, random_wait(wait_type='SHORT', wait=False)).until(EC.alert_is_present())
                                        alert = driver.switch_to.alert
                                        alert_text = (alert.text or "").strip()
                                        alert.accept()
                                        self._log(logging.INFO, self.sede, "Success", f"Alerta aceptada: {alert_text}")
                                        random_wait(wait_type='SHORT', wait=True)
                                    except Exception:
                                        pass


                                    field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, f'//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_pnlPersona"]/div[2]/div[{index}]'))
                                    ) 
                                    label = field.find_element(By.XPATH, './span').text.strip()

                                    try:
                                        if any(keyword in label for keyword in ['Teléfono', 'Telèfon', 'Phone']):
                                            input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td/input'))
                                            )
                                            input_element.click()
                                            input_element.clear()
                                            input_element.send_keys(self.multivia['phone'])
                                                                                
                                        elif any(keyword in label for keyword in ['Correo electrónico', 'Correu electrònic', 'Email', 'E-mail', 'e-Mail']):
                                            input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td/input'))
                                            )
                                            input_element.click()
                                            input_element.clear()
                                            input_element.send_keys(self.mail)

                                        elif any(keyword in label for keyword in ['País']):
                                            input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td[2]/input'))
                                            )
                                            input_element.click()
                                            input_element.clear()
                                            input_element.send_keys(direccion.get('pais'))
                                            # input_element.send_keys('ESPAÑA')
                                            input_element.send_keys('\n')

                                        elif any(keyword in label for keyword in ['Provincia', 'Província']):
                                            input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td[2]/input'))
                                            )
                                            input_element.click()
                                            input_element.clear()
                                            input_element.send_keys(direccion.get('provincia'))
                                            input_element.send_keys('\n')

                                        elif any(keyword in label for keyword in ['Municipio', 'Municipi']):
                                            input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td[2]/input'))
                                            )
                                            input_element.click()
                                            input_element.clear()
                                            input_element.send_keys(direccion.get('poblacion'))
                                            input_element.send_keys('\n')
                                        
                                        elif any(keyword in label for keyword in ['C.Postal', 'Código Postal']):
                                            try:
                                                input_element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_CPOSTAL_I"]'))
                                                )
                                            except Exception:
                                                input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td/input'))
                                                )

                                            

                                            # Esperar hasta que el input sea interactuable
                                            end_time = time.time() + random_wait(wait_type='X_LONG', wait=False)
                                            while time.time() < end_time:
                                                if input_element.is_displayed() and input_element.is_enabled():
                                                    break
                                                random_wait(wait_type='SHORT', wait=True)
                                            if input_element.is_displayed() and input_element.is_enabled():
                                                input_element.click()
                                                input_element.clear()
                                                input_element.send_keys(direccion.get('codigo_postal'))
                                                # input_element.send_keys('\n')
                                            else:
                                                self._log(logging.WARNING, self.sede, "Pending", f"Input C.Postal no interactuable (displayed={input_element.is_displayed()}, enabled={input_element.is_enabled()})")
                                                continue

                                        elif any(keyword in label for keyword in ['Dirección', 'Adreça', 'Carrer']):
                                            try:
                                                input_element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_CARRER_I"]'))
                                                )
                                            except Exception:
                                                input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td[2]/input'))
                                                )

                                            input_element.send_keys(Keys.DOWN)
                                            random_wait(wait_type='MEDIUM', wait=True)
                                            try:
                                                input_element = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_NCARRER_I"]'))
                                                )
                                            except Exception:
                                                input_element = WebDriverWait(field, random_wait(wait_type='MEDIUM', wait=False)).until(
                                                    EC.presence_of_element_located((By.XPATH, './/table/tbody/tr/td/input'))
                                                )

                                            # Esperar hasta que el input sea interactuable
                                            end_time = time.time() + random_wait(wait_type='X_LONG', wait=False)
                                            while time.time() < end_time:
                                                if input_element.is_displayed() and input_element.is_enabled():
                                                    break
                                                random_wait(wait_type='SHORT', wait=True)
                                            if input_element.is_displayed() and input_element.is_enabled():
                                                input_element.click()
                                                input_element.clear()
                                                input_element.send_keys(directions_old.get('calle'))
                                                # input_element.send_keys('\n')
                                            else:
                                                self._log(logging.WARNING, self.sede, "Pending", f"Input Dirección no interactuable (displayed={input_element.is_displayed()}, enabled={input_element.is_enabled()})")
                                                continue
                                        
                                        elif any(keyword in label for keyword in ['Número', 'Pis', 'Porta']):
                                            break


                                        random_wait(wait_type='MEDIUM', wait=True)
                                        
                                    except Exception as e:
                                        self._log(logging.WARNING, self.sede, "Pending", f"No se pudo rellenar el campo {label}: {e}")
                                        continue

                                #t Comprobarr que los campos están bieny rellenados; si es así romper el while
                                try:
                                    # Recolectar valores actuales de los campos visibles en el panel
                                    filled = {}
                                    for index in range(1, len(fields) + 1):
                                        try:
                                            field_elem = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, f'//*[@id="ctl00_Content1_frameDadesSolicitant1_FrameDadesPersonals1_pnlPersona"]/div[2]/div[{index}]'))
                                            )
                                        except Exception:
                                            continue

                                        try:
                                            label = (field_elem.find_element(By.XPATH, './span').text or "").strip()
                                        except Exception:
                                            label = f"field_{index}"

                                        # Intentar obtener un input representativo dentro del field
                                        value = ""
                                        for xp in ('.//table/tbody/tr/td/input', './/table/tbody/tr/td[2]/input', './/input'):
                                            try:
                                                inp = field_elem.find_element(By.XPATH, xp)
                                                if (any (keyword in label for keyword in ['Muncipi', 'Municipio', 'Provincia', 'Província', 'País'])):
                                                    value = inp.get_attribute('value').strip()
                                                else:
                                                    value = (inp.get_attribute('value') or inp.text or "").strip()
                                            
                                                if value != "":
                                                    break
                                            except Exception:
                                                continue

                                        filled[label] = value

                                    # Función auxiliar para comprobar por etiquetas posibles
                                    def label_contains_any(label, keywords):
                                        return any(k.lower() in label.lower() for k in keywords)

                                    def find_value_for(keywords):
                                        for lbl, val in filled.items():
                                            if label_contains_any(lbl, keywords):
                                                return val
                                        return ""

                                    checks = {
                                        "phone": (find_value_for(['Teléfono', 'Telèfon', 'Phone']), self.multivia.get('phone')),
                                        "mail": (find_value_for(['Correo electrónico', 'Correu electrònic', 'Email', 'E-mail', 'e-Mail']), self.mail),
                                        "pais": (find_value_for(['País']), direccion.get('pais')),
                                        "provincia": (find_value_for(['Provincia', 'Província']), direccion.get('provincia')),
                                        "municipio": (find_value_for(['Municipio', 'Municipi']), direccion.get('poblacion')),
                                        "codigo_postal": (find_value_for(['C.Postal', 'Código Postal']), direccion.get('codigo_postal')),
                                        "direccion": (find_value_for(['Dirección', 'Adreça', 'Carrer']), direccion.get('calle')),
                                    }

                                    missing = []
                                    for key, (found, expected) in checks.items():
                                        for key, (found, expected) in checks.items():
                                            try:
                                                # Para país/provincia/municipio solo comprobamos que exista un valor no vacío
                                                if key in ("pais", "provincia", "municipio"):
                                                    if not found or not str(found).strip():
                                                        missing.append(key)
                                                    continue

                                                # Si no se espera un valor (None o ""), no lo consideramos obligatorio
                                                if expected in (None, ""):
                                                    continue

                                                if not found or expected.strip().lower() not in str(found).strip().lower():
                                                    missing.append(key)
                                            except Exception:
                                                # En caso de error al comprobar, marcar como faltante para reintento
                                                missing.append(key)
                                        # Si no se espera un valor (None o ""), no lo consideramos obligatorio
                                        if expected in (None, ""):
                                            continue
                                        if not found or expected.strip().lower() not in found.strip().lower():
                                            missing.append(key)

                                    if not missing:
                                        self._log(logging.INFO, self.sede, "Success", f"Campos verificados: todos los campos requeridos están bien rellenados. Intent: {tries+1}")
                                        break  # romper el while si todo está correcto
                                    else:
                                        self._log(logging.WARNING, self.sede, "Pending", f"Campos incompletos o no coincidentes: {missing}. Intent: {tries+1}")

                                except Exception as e:
                                    self._log(logging.WARNING, self.sede, "Pending", f"Error comprobando campos rellenados: {e}")

                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al rellenar datos: {e}")
                                return False, (0, f"⚠️ Error al rellenar datos: {e}")
                            finally:
                                tries += 1
                        
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_Content1_Button1"]'))
                        ).click()
                        random_wait(wait_type='LONG', wait=True)

                        self._log(logging.INFO, self.sede, "Success", "Paso 1 completado: datos rellenados y botón pulsado.")

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en el paso 1 de dar de Alta: {e}")
                        return False, (0, f"⚠️ Error en el paso 1 de dar de Alta: {e}")
                    

                    try:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_table64"]'))
                        )

                        try:
                            mail_input = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_MAIL_I"]'))
                            )
                            mail_value = mail_input.get_attribute('value')

                            if mail_value: 
                                if mail_value not in ["", " "]:
                                    if mail_value.strip().lower() == self.mail.strip().lower():
                                        self._log(logging.INFO, self.sede, "Success", f"El correo ya estaba prellenado y coincide: {mail_value}")
                                        if self.mail == self.multivia['mail']:
                                            action = list(CERT_SEDES_ACTION.items())[6]
                                        else:
                                            action = list(CERT_SEDES_ACTION.items())[7]
                                else:
                                    if self.n_mails == 1:
                                        if self.mail == self.multivia['mail']:
                                            action= list(CERT_SEDES_ACTION.items())[0]
                                        else:
                                            action= list(CERT_SEDES_ACTION.items())[2]

                            else:
                                if self.n_mails == 1:
                                    if self.mail == self.multivia['mail']:
                                        action= list(CERT_SEDES_ACTION.items())[0]
                                    else:
                                        action= list(CERT_SEDES_ACTION.items())[2]

                            mail_input.clear() 
                            mail_input.send_keys(self.mail)
                            random_wait(wait_type='SHORT', wait=True)
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al introducir el correo: {e}")
                            return False, (0, f"⚠️ Error al introducir el correo: {e}")

                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_Content1_Button1"]'))
                        ).click()
                        random_wait(wait_type='LONG', wait=True)

                        self._log(logging.INFO, self.sede, "Success", "Paso 2 completado: correo introducido y botón pulsado.")
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en el paso 2 de dar de Alta: {e}")
                        return False, (0, f"⚠️ Error en el paso 2 de dar de Alta: {e}")
                    
                    try:
                        # Esperar el panel de confirmación
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_pnlSol"]'))
                        )

                        # Comprobar que el correo mostrado coincide con self.mail
                        confirm_mail = WebDriverWait(driver, random_wait(wait_type='MEDIUM', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_TableConfirmacio"]/tbody/tr/td[2]'))
                        )
                        confirm_mail = (confirm_mail.text or "").strip()
                        if confirm_mail.lower() != (self.mail or "").strip().lower():
                            self._log(logging.ERROR, self.sede, "Failure", f"Correo de confirmación no coincide. Esperado: {self.mail}, Encontrado: {confirm_mail}")
                            return False, (0, f"Correo de confirmación no coincide. Esperado: {self.mail}, Encontrado: {confirm_mail}")

                        # Pulsar el botón de confirmación
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="ctl00_Content1_Button1"]'))
                        ).click()
                        random_wait(wait_type='LONG', wait=True)

                        self._log(logging.INFO, self.sede, "Success", "Paso 3 completado: confirmación verificada y botón pulsado.")
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en el paso 3 de dar de Alta: {e}")
                        return False, (0, f"⚠️ Error en el paso 3 de dar de Alta: {e}")
                    
                    try:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Content1_FrameDadesPersonals1_pnlPersona"]'))
                        )

                        try:
                            panel = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="ctl00_Panel1"]/div[1]/div/div/div[3]'))
                            )
                            panel_text = (panel.text or "").strip()
                            random_wait(wait_type='SHORT', wait=True)

                            if self.mail.strip().lower() in panel_text.lower():
                                self._log(logging.INFO, self.sede, "Success", f"Verificación exitosa: correo encontrado en panel: {panel_text}")
                                return True, action
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", f"Verificación fallida: correo {self.mail} no encontrado en panel. Texto: {panel_text}")
                                return False, (0, f"Verificación fallida: correo {self.mail} no encontrado en panel. Texto: {panel_text}")
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al verificar el panel final: {e}")
                            return False, (0, f"⚠️ Error al verificar el panel final: {e}")

                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error verificando el Alta en {self.sede}: {e}")
                        return False, (0, f"⚠️ Error verificando el Alta en {self.sede}: {e}")

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en el proceso de alta: {e}")
                    return False, (0, f"⚠️ Error en el proceso de alta: {e}")                    
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
