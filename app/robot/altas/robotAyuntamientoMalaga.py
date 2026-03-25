import asyncio
import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from googletrans import Translator
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import random_wait, CERT_SEDES_ACTION, translate_direction
from selenium.webdriver.support.ui import Select
import re
from difflib import SequenceMatcher
import unicodedata


class RobotAyuntamientoMalaga:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link : str =r'https://sede.malaga.eu/micarpeta_p/identificacion.seam?service=https%253A%252F%252Fsede.malaga.eu%252Fcomenot%252F', sede : str ='Ayunamiento Malaga',
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link = r'https://sede.malaga.eu/micarpeta_p/identificacion.seam?service=https%253A%252F%252Fsede.malaga.eu%252Fcomenot%252F'
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

    def _login_ayuntamientomalaga(self, driver) -> bool:
        try:
            WebDriverWait(driver, random_wait('X_LONG')).until(
                EC.presence_of_element_located((By.XPATH, '//*[@id="cuerpo"]/div[3]/div/div[2]/a'))
            ).click()

            # Use a descendant selector and a direct id fallback to reliably find the element
            xpaths = [
                '/html/body/div/div[2]/div/div/div/form[@id="inicioForm"]',
                '/html/body/div/div[2]/div/div/div/form[@id="j_idt53"]'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)
            while time.time() < end_time:
                for xpath in xpaths:
                    if driver.find_elements(By.XPATH, xpath):
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def subscribe(self, client_name: str, nif_cif: str, direccion : dict) -> bool:
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
            login = self._login_ayuntamientomalaga(driver)
            if login:
                try:
                    registro = WebDriverWait(driver, random_wait('X_LONG')).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[1]/p[1]/strong'))
                    )

                    if any(k in (registro.text or "").lower() for k in ['registro', 'register', 'inscripción', 'inscripcion', 'alta']):
                        new_alta = True
                    else:
                        new_alta = False
                except Exception as e:
                    new_alta = False

                if new_alta:
                    try:
                        try:
                            try:
                                nif_value = WebDriverWait(driver, random_wait('X_LONG')).until(     #//*[@id="j_idt53:numeroIdentificador:documentoIdentificacion"]                       
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[2]/div/div[1]/div/span[1]/input[contains(@id,"numeroIdentificadorER:documentoIdentificacionER")]'))
                                ).get_attribute('value') or ''
                            except:
                                nif_value = WebDriverWait(driver, random_wait('X_LONG')).until(                     
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[2]/div/div[5]/div/span[1]/input[contains(@id,"j_idt53:numeroIdentificador:documentoIdentificacion")]'))
                                ).get_attribute('value') or ''



                            if nif_value.strip().lower() != nif_cif.lower().strip():
                                raise ValueError(f"El NIF/CIF en la página ({nif_value}) no coincide con el proporcionado ({nif_cif}).")
                            else:
                                self._log(logging.INFO, self.sede, "Success", "NIF/CIF verificado correctamente.")
                        
                        except ValueError as ve:
                            self._log(logging.ERROR, self.sede, "Failure", str(ve))
                            action = (0, str(ve))
                            return False, action, None
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error comprobando NIF/CIF: {e}")
                            action = (0, f"Error comprobando NIF/CIF: {e}")
                            return False, action, None
                        
                        try:
                            # Buscar campo de email con XPaths tolerantes a ids dinámicos
                            try:
                                email_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[3]/div/div[4]/div/span[1]/input[contains(@id,"email_datosContacto")]'))
                                )

                                if not email_elem:
                                    raise Exception("No se encontró el campo de correo (ids dinámicos).")

                                email_value = (email_elem.get_attribute('value') or '').strip()

                                if email_value:
                                    if self.n_mails == 1:
                                        if self.mail == email_value:
                                            action = list(CERT_SEDES_ACTION.items())[6]
                                        else:
                                            if self.mail == self.multivia.get('mail'):
                                                action = list(CERT_SEDES_ACTION.items())[0]
                                            else:
                                                action = list(CERT_SEDES_ACTION.items())[2]
                                else:
                                    if self.mail == self.multivia.get('mail'):
                                        action = list(CERT_SEDES_ACTION.items())[0]
                                    else:
                                        action = list(CERT_SEDES_ACTION.items())[2]

                                    email_elem.clear()
                                    email_elem.send_keys(self.mail)

                                random_wait(wait_type='MEDIUM', wait=True)

                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando formulario inicial (alta nueva): {e}")
                                action = (0, f"Error rellenando formulario inicial: {e}")
                                return False, action, None 
                            
                            try:
                                try:
                                    # Manejar opción "SIN DOMCILIO" si aparece y clicar su input asociado
                                    sin_dom_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                        EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt53"]/div[3]/p[1]'))
                                    )
                                    if (sin_dom_elem.text or '').strip().upper() == 'SIN DOMICILIO':
                                        sin_dom_btn = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.element_to_be_clickable((By.XPATH, '//*[@id="j_idt53"]/div[3]/p[1]/input'))
                                        )
                                        sin_dom_btn.click()
                                        random_wait(wait_type='LONG', wait=True)

                                    # Seleccionar país por texto "ESPAÑA"
                                    pais_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                        EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:paisField:paisSelectId"]'))
                                    )
                                    Select(pais_elem).select_by_visible_text('ESPAÑA')
                                    random_wait(wait_type='MEDIUM', wait=True)
                                    
                                    print(f"Direccion del cliente {self.cliente}: {direccion}")

                                    provincia_text = direccion.get('provincia', '').strip().upper()
                                    if provincia_text in ['ILLES BALEARS', 'ISLAS BALEARES', 'BALEARS', 'BALEARS']:
                                        provincia_text = 'BALEARES'


                                    calle_raw = (direccion.get('calle') or '').strip()
                                    m = re.search(r'\d+', calle_raw)
                                    numero_calle = m.group(0) if m else '1'
                                    # Extraer la parte de la calle que no es el número: eliminar dígitos y separadores comunes
                                    calle = re.sub(r'[\dºª/\\#\-,\.]+', ' ', calle_raw).strip()
                                    calle = re.sub(r'\s+', ' ', calle)  # normalizar espacios
                                    cod_postal = (direccion.get('codigo_postal') or direccion.get('codpostal') or '').strip()
                                    municipio = direccion.get('poblacion', '').upper()

                                    # Seleccionar provincia por texto si disponible
                                    if provincia_text:
                                        prov_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:provinciaField:provinciaSelectId"]'))
                                        )
                                        Select(prov_elem).select_by_visible_text(provincia_text)
                                        random_wait(wait_type='MEDIUM', wait=True)

                                    # Seleccionar municipio por texto si disponible
                                    if municipio:
                                        municipio_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:municipioField:municipioSelectId"]'))
                                        )
                                        try:
                                            def _normalize(s: str) -> str:
                                                s = (s or "").upper()
                                                s = unicodedata.normalize('NFD', s)
                                                s = ''.join(ch for ch in s if unicodedata.category(ch) != 'Mn')
                                                s = re.sub(r'[^\w\s]', ' ', s)
                                                s = re.sub(r'\s+', ' ', s).strip()
                                                return s

                                            threshold = 90
                                            target_norm = _normalize(municipio)
                                            alt_targets = [target_norm]
                                            tokens = target_norm.split()
                                            if tokens and tokens[0] in {'LA', 'EL', 'LOS', 'LAS'}:
                                                alt_targets.append(' '.join(tokens[1:] + [tokens[0]]))

                                            sel = Select(municipio_elem)
                                            best = None
                                            best_score = 0
                                            for opt in sel.options:
                                                opt_text = opt.text or ""
                                                opt_norm = _normalize(opt_text)
                                                for t in alt_targets:
                                                    score = int(SequenceMatcher(None, t, opt_norm).ratio() * 100)
                                                    if score > best_score:
                                                        best_score = score
                                                        best = opt_text

                                            if best and best_score >= threshold:
                                                Select(municipio_elem).select_by_visible_text(best)
                                            else:
                                                raise Exception(f"No matching municipio above {threshold}% (best {best_score}%)")
                                        except Exception as e:
                                            # Inicializa el traductor usando un service_url más fiable y preparado para fallos
                                            try:
                                                translator = Translator(service_urls=['translate.googleapis.com'])
                                            except Exception:
                                                # Fallback si la inicialización falla
                                                try:
                                                    translator = Translator()
                                                except Exception:
                                                    translator = None

                                            if translator:
                                                result = translator.translate(municipio, dest='es')
                                                if asyncio.iscoroutine(result):
                                                    result = asyncio.run(result)
                                                # Algunas implementaciones devuelven un objeto con atributo .text
                                                translated = getattr(result, "text", None)
                                                # Si no tiene .text o es None, usar la representación en cadena del resultado
                                                if translated is None:
                                                    if result is None:
                                                        raise ValueError("translate() returned None")
                                                    translated = str(result)

                                                translated_value = translated.strip()

                                            Select(municipio_elem).select_by_visible_text(translated_value)

                                        random_wait(wait_type='MEDIUM', wait=True)
                                    
                                    # Rellenar número de la calle si disponible
                                    if numero_calle:
                                        num_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:numeroField:numerocalle"]'))
                                        )
                                        num_elem.clear()
                                        num_elem.send_keys(numero_calle)


                                    if calle:
                                        calle_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:direnomalagaField:direccionnomalagaid"]'))
                                        )
                                        calle_elem.clear()
                                        calle_elem.send_keys(calle)


                                    # Rellenar código postal si disponible
                                    if cod_postal:
                                        cp_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                            EC.presence_of_element_located((By.XPATH, '//*[@id="j_idt52:codpostalEspField:codposesp"]'))
                                        )
                                        cp_elem.clear()
                                        cp_elem.send_keys(cod_postal)

                                    # Pulsar aceptar
                                    aceptar_btn = WebDriverWait(driver, random_wait('X_LONG')).until(
                                        EC.element_to_be_clickable((By.XPATH, '//*[@id="j_idt52:aceptar"]'))
                                    )
                                    aceptar_btn.click()
                                    random_wait(wait_type='LONG', wait=True)

                                except Exception as e:
                                    self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando dirección: {e}")
                                    action = (0, f"Error rellenando dirección: {e}")
                                    return False, action, None 
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error en manejo de dirección: {e}")
                                action = (0, f"Error en manejo de dirección: {e}")
                                return False, action, None 

                            
                            try:
                                # <input id="j_idt53:acepto" type="checkbox" name="j_idt53:acepto">
                                politicas_accept = WebDriverWait(driver, random_wait('X_LONG')).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[3]/p[2]/input[contains(@id,"acepto")]'))
                                )
                                if not politicas_accept.is_selected():
                                    politicas_accept.click()

                                # <input id="j_idt53:enviar" type="submit" name="j_idt53:enviar" value="Enviar" class="btn btn-success">
                                next_btn = WebDriverWait(driver, random_wait('X_LONG')).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div/div[2]/div/div/div/form/div[3]/input[contains(@id,"enviar")]'))
                                )   
                                next_btn.click()
                                random_wait(wait_type='MEDIUM', wait=True)

                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando formulario inicial (alta nueva - checkbox): {e}")
                                action = (0, f"Error rellenando formulario inicial: {e}")
                                return False, action, None 
                        except Exception as e:  
                            self._log(logging.ERROR, self.sede, "Failure", f"Error rellenando formulario inicial (alta nueva): {e}")
                            return False, (0, f"Error rellenando formulario inicial: {e}"), None
                        
                        # Verificación
                        try:
                            message = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="cuerpo"]/div[2]/b'))
                            )

                            if message and ("se han modificado sus datos personales como interesado del ayuntamiento de málaga" in message.text.strip().lower()):
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '//*[@id="cuerpo"]/a'))
                                ).click()

                                self._log(logging.INFO, self.sede, "Success", "Alta en sede verificado.")
                                return True, action, self.mail
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "Alta no verificado.")
                                return False, (0, "Alta no verificado."), None
                            
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error en verificación: {e}")
                            return False, (0, f"Error en verificación: {e}"), None


                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error en proceso de alta: {e}")
                        return False, (0, f"Error en proceso de alta: {e}"), None
                else:
                    try:
                        try:
                            nif_value = WebDriverWait(driver, random_wait('X_LONG')).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="inicioForm:dnicif_userId_field:dnicif_userId"]'))
                            ).get_attribute('value') or ''

                            if nif_value.strip().lower() != nif_cif.lower().strip():
                                raise ValueError(f"El NIF/CIF en la página ({nif_value}) no coincide con el proporcionado ({nif_cif}).")
                            else:
                                self._log(logging.INFO, self.sede, "Success", "NIF/CIF verificado correctamente.")
                        
                        except ValueError as ve:
                            self._log(logging.ERROR, self.sede, "Failure", str(ve))
                            action = (0, str(ve))
                            return False, action, None
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error comprobando NIF/CIF: {e}")
                            action = (0, f"Error comprobando NIF/CIF: {e}")
                            return False, action, None

                        # //*[@id="inicioForm:correoElectronicoField_:email_datosContacto_id"]

                        try:                       
                            email_elem = WebDriverWait(driver, random_wait('X_LONG')).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="inicioForm:correoElectronicoField_:email_datosContacto_id"]'))
                            )

                            email_value = email_elem.get_attribute('value').strip()
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error obteniendo el email del cliente: {e}")

                        
                        return True, list(CERT_SEDES_ACTION.items())[7] ,email_value
                        
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error en proceso de alta: {e}")
                        return False, (0, f"Error en proceso de alta: {e}"), None
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login.")
                return False, (0, "Error en login."), None

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"⚠️ Error en darse de alta en {self.portal_link}: {e}"), None

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
