from queue import Queue
import time, os, shutil, tempfile
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pyautogui
import logging

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait

class RobotAtc:
    def __init__(self, mail : str, date : str, cliente : str, portal_link : str, execution_id: str, log_queue: Queue,  module : str ="Altas", sede : str ='atc',
            n_mails : int = 1,
            multivia : dict = {
                'nif': 'B62798210',
                'purpose': 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL',
                'mail': 'notificaciones@xvia-serviciosjuridicos.com',
                'phone': '722761154'
            }):
        self.portal_link ='https://seu2.atc.gencat.cat/ca/secured/el-meu-espai-atc'
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
        
    def _login_atc(self, driver) -> bool:
        try:
            # #Cookies
            # WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
            #     EC.element_to_be_clickable((By.XPATH, '//*[@id="ppms_cm_reject-all"]'))
            # ).click()

            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCertCaptcha"]'))
                ).click()
            except Exception:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCert"]'))
                ).click()
            
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="modalCertificat"]/div/div/div[3]/button'))
                ).click()
            except Exception as e:
                self._log(logging.DEBUG, self.sede, "Failure", f"⚠️ Error al cerrar el modal de certificado: {e}")
                
            xpaths = [
                "/html/body/ngb-modal-window/div/div/app-contact-data-modal/div/app-modal-initial-page",
                "/html/body/div[1]/div/mf-dispatcher/div/app-el-meu-espai",
                '//*[@id="modal-initial-page"]'
              ]
            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:  
                for xpath in xpaths: 
                    try:
                        element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, xpath)))
                        if element: 
                            return True
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, "Pending", f"No se encontró el elemento para {xpath}: {e}")
            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False
        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def _update_profile_modal(self, driver, nif_cif: str, tipo_cliente: str) -> bool:
        try:
            try:
                nif = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="modal-initial-page"]/div/div/div[2]/div[2]/span[2]'))
                ).text
                if nif == nif_cif:
                    self._log(logging.INFO, self.sede, "Success", f"El NIF coincide con el esperado.")
                else:
                    self._log(logging.ERROR, self.sede, "Failure", f"El NIF no coincide. Esperado: {nif_cif}, Obtenido: {nif}")
                    return False, (0, "El NIF no coincide.")
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al obtener el NIF: {e}")
                return False, (0, f"Error al obtener el NIF")
            try:
                email_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="email"]'))
                )
                email_value = email_field.get_attribute('value')
                if email_value:
                    self._log(logging.INFO, self.sede, "Pending", f"El correo ya está registrado: {email_value}")
                    if self.mail == email_value and self.n_mails == 1:
                        self._log(logging.INFO, self.sede, "Pending", f"El correo {email_value} ya está registrado.")
                        action = list(CERT_SEDES_ACTION.items())[6]
                    else:
                        action = (-1, "Imposible añadir el correo del cliente")
                else:
                    self._log(logging.INFO, self.sede, "Pending", "No hay correo registrado, se procede a añadir el nuevo.")
                    try:
                        # //*[@id="dropdown"]/span[2] || /html/body/ngb-modal-window/div/div/app-contact-data-modal/div/app-modal-initial-page/se-modal/div/div/div[2]/app-modal-data-form/div/div[1]/div/se-dropdown/div/p-dropdown/div/span[2]
                        dropdown = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="dropdown"]/span[2]'))
                        )
                        if dropdown:
                            dropdown.click()
                        
                    except Exception as e:
                        self._log(logging.DEBUG, self.sede, "Pending", f"Error checking dropdown presence: {e}")
                    try:
                        email_field.click()
                        pyautogui.FAILSAFE = False
                        pyautogui.hotkey('ctrl', 'a')
                        pyautogui.hotkey('backspace')
                        random_wait(wait_type='SHORT', wait=True)
                        for char in self.mail:
                            if char == '@' or char == '#':
                                pyautogui.hotkey('altright', '2')
                            else:
                                pyautogui.typewrite(char, interval=0.01)
                        random_wait(wait_type='SHORT', wait=True)
                        email_confirm_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="confirmEmail"]'))
                        )
                        email_confirm_field.click()
                        for char in self.mail:
                            if char == '@' or char == '#':
                                pyautogui.hotkey('altright', '2')
                            else:
                                pyautogui.typewrite(char, interval=0.01)
                        random_wait(wait_type='SHORT', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al rellenar el campo de correo: {e}")
                        return False, (0, f"Error al rellenar el campo de correo: {e}")
                    if self.mail == self.multivia.get('mail'):
                        action = list(CERT_SEDES_ACTION.items())[0]
                    else:
                        action = list(CERT_SEDES_ACTION.items())[2]
                self._log(logging.INFO, self.sede, "Success", f"Correo rellenado correctamente: {self.mail}")
                try:
                    if tipo_cliente == 'Particular':
                        phone_input = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="phone"]'))
                        ).click()
                        pyautogui.hotkey('ctrl', 'a')
                        pyautogui.hotkey('backspace')
                        random_wait(wait_type='SHORT', wait=True)
                        for char in self.multivia['phone']:
                            pyautogui.typewrite(char, interval=0.01)
                        random_wait(wait_type='SHORT', wait=True)
                        confirm_phone_input = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="confirmPhone"]'))
                        )
                        confirm_phone_input.click()
                        for char in self.multivia['phone']:
                            pyautogui.typewrite(char, interval=0.01)
                        random_wait(wait_type='SHORT', wait=True)
                        self._log(logging.INFO, self.sede, "Success", "Teléfono rellenado correctamente.")
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al rellenar el campo de teléfono: {e}")
                    return False, (0, f"Error al rellenar el campo de teléfono: {e}")
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error rellenando los datos de contacto: {e}")
                return False, (0, f"Error rellenando los datos de contacto")
            try:
                pyautogui.click(x=100, y=500)  # Click outside to close any open dropdowns

                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="rgpd_checkbox-input"]'))
                ).click()

                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="notice_checkbox-input"]'))
                ).click()

                random_wait(wait_type='MEDIUM', wait=True)
                # checkboxes = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                #     EC.presence_of_all_elements_located((By.XPATH, '//*[@id="undefined_checkbox-input"]'))
                # )
                # for checkbox in checkboxes:
                #     if checkbox.is_enabled() and not checkbox.is_selected():
                #         try:
                #             driver.execute_script("arguments[0].click();", checkbox)
                #         except Exception as e:
                #             self._log(logging.WARNING, self.sede, "Pending", f"JavaScript click failed: {e}")
                #     random_wait(wait_type='SHORT', wait=True)

                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="modal-initial-page"]/div/div/div[3]/div/se-button[2]/button'))
                ).click()
                random_wait(wait_type='X_LONG', wait=True)
            except Exception as e:
                try:
                    driver.execute_script("""
                        document.querySelector("#rgpd_checkbox-input").click();
                        document.querySelector("#notice_checkbox-input").click();
                    """)  # document.querySelector("#modal-initial-page > div > div > div.modal-footer.d-flex.justify-content-end > div > se-button:nth-child(2) > button").click();

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="modal-initial-page"]/div/div/div[3]/div/se-button[2]/button'))
                    ).click()
                    random_wait(wait_type='X_LONG', wait=True)
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al confirmar la suscripción: {e}")
                    return False, (0, "Error al confirmar la suscripción")
            return True, action 
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al actualizar el perfil: {e}")
            return False, (0, f"Error al actualizar el perfil: {e}")

    def subscribe(self, id_cliente: str, nif_cif: str, tipo_cliente: str) -> bool:
        temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=self.portal_link,
            module="Altas",
            execution_id=self.execution_id,
            log_dir="logs/altas",
            filename=f"altas",
            cliente=self.cliente,
            site=self.sede,
            task_id=self.sede
        )
        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait(wait_type='LONG', wait=True)
        try:
            if self._login_atc(driver):
                try:
                    modals = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '/html/body/ngb-modal-window'))
                    )
                    while True:
                        try:
                            modal = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/ngb-modal-window[2]/div/div/app-co2-campaign-modal'))
                            )
                        except Exception as e:
                            modal = None
                            try:
                                welcome_modal = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/ngb-modal-window/div/div/app-welcome-modal'))
                                )
                                if welcome_modal:
                                    label = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, '/html/body/ngb-modal-window/div/div/app-welcome-modal/se-modal/div/div/div[3]/div/div/form/se-checkbox/div/div/label'))
                                    )
                                    self._log(logging.INFO, self.sede, "Pending", f"Label encontrado: {label.text.strip()}")
                                    if label.text.strip() == 'No tornar a mostrar':
                                        label.click()
                                        
                                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.element_to_be_clickable((By.XPATH, '/html/body/ngb-modal-window/div/div/app-welcome-modal/se-modal/div/div/div[3]/div/div/se-button/button'))
                                    ).click()
                                else:
                                    continue

                            except Exception as e:
                                if WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/mf-dispatcher/div/app-el-meu-espai/se-el-meu-espai/main/div/app-home'))
                                ):
                                    break
                                else:
                                    continue
                        finally:
                            if modal:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/ngb-modal-window[2]/div/div/app-co2-campaign-modal/se-modal/div/div/div[3]/div/div/se-button/button'))
                                ).click()

                            random_wait(wait_type='SHORT', wait=True)

                except Exception as e:
                    self._log(logging.INFO, self.sede, "Failure", "Error cerrando ventanas emergentes.")
                    modals = None
                
                if modals:
                    header = WebDriverWait(driver, random_wait('LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div[1]/div/mf-dispatcher/div/app-el-meu-espai/se-el-meu-espai/main/div/app-home/app-header-content/section/div[1]/h1'))
                    )
                    if header.text.strip() in ['Benvingut al teu espai', 'Bienvenido a tu área', 'Welcome to your area']:
                        self._log(logging.INFO, self.sede, "Success", "Login exitoso: Página principal cargada correctamente.")
                        driver.get("https://seu2.atc.gencat.cat/ca/secured/el-meu-espai-atc/les-meves-dades")
                        random_wait('LONG', wait=True)
                        
                        try:
                            elements = WebDriverWait(driver, random_wait('LONG', wait=False)).until(
                                EC.presence_of_all_elements_located((By.XPATH, '/html/body/div[1]/div/mf-dispatcher/div/app-el-meu-espai/se-el-meu-espai/main/div/app-my-data/se-side-tabs/div/div[2]/mf-contribuent-user-personal-info/section/app-person-info[2]/se-panel/p-panel/div/div[2]/div/div/div[3]/div'))
                            )   
                            for element in elements:
                                label = WebDriverWait(element, random_wait('LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './div/span[1]'))
                                )
                                if label.text.strip() == 'Adreça electrònica':
                                    try:
                                        email = WebDriverWait(element, random_wait('X_LONG', wait=False)).until(
                                            EC.presence_of_element_located((By.XPATH, './div/span[2]'))
                                        )
                                        if email.text.strip().lower() == self.mail.lower():
                                            self._log(logging.INFO, self.sede, "Success", f"Mail encontrado: {email.text.strip()}")
                                            action = list(CERT_SEDES_ACTION.items())[6]
                                            random_wait('LONG', wait=True)
                                            return True, action, self.mail
                                        elif email.text.strip() == self.multivia.get('mail'):
                                            self._log(logging.INFO, self.sede, "Success", f"Mail encontrado: {email.text.strip()}")
                                            action = list(CERT_SEDES_ACTION.items())[0]
                                            random_wait('LONG', wait=True)

                                            return True, action, self.multivia.get('mail')
                                        else:
                                            self._log(logging.WARNING, self.sede, "Pending", f"Mail no encotrado. Expected: {self.mail}, Found: {email.text.strip()}")
                                            return True, list(CERT_SEDES_ACTION.items())[7], email.text.strip()
                                    except Exception as e:
                                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error while verifying hidden label: {e}")
                                        action = (0, "Error verificando mail del label")
                            
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error interacting with the mail field: {e}")
                            return False, (0, f"Error interacting with the mail field"), None
                
                else:
                    form  = WebDriverWait(driver, random_wait('LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="modal-initial-page"]/div/div/div[1]/div/span'))
                    )
                    if form.text.strip() in ['Confirma o actualitza les dades de contacte.', 'Confirma o actualiza los datos de contacto.', 'Confirm or update contact details']:
                        update, action = self._update_profile_modal(driver, nif_cif, tipo_cliente)                        
                        random_wait('LONG', wait=True)

                    else:
                        pass

                if update:
                    try:
                        confirmation = WebDriverWait(driver, random_wait('LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, ' /html/body/ngb-modal-window/div/div/app-contact-data-modal/div/app-modal-confirmation-page/se-modal/div/div/div[1]/div/span'))
                        )
                        if confirmation.text.strip() in ['Dades enviades correctament', 'Datos enviados correctamente', 'Data sent successfully']:
                            WebDriverWait(driver, random_wait('LONG', wait=False)).until( 
                                EC.element_to_be_clickable((By.XPATH, '/html/body/ngb-modal-window/div/div/app-contact-data-modal/div/app-modal-confirmation-page/se-modal/div/div/div[3]/div/se-button/button'))
                            ).click()
                        return True, action, self.mail
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al finalizar el proceso: {e}")
                        return False, (0, "Error al finalizar el proceso"), None
                else:
                    self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error al actualizar el perfil: {action}")
                    return False, action, None
 
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login"), None
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}"), None
        finally:
            random_wait('LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
