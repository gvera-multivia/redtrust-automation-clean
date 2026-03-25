from multiprocessing import Queue
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


class RobotPaisVasco:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link : str ='https://www.euskadi.eus/mi-carpeta/web01-sede/es/', sede : str ='pais vasco',
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
        
    def _login_euskadi(self, driver):
        try: 
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="containeregoitza_eduki_orokorra"]/article/div/div[1]/div[2]/p[2]/a'))).click()

            random_wait(wait_type='MEDIUM', wait=True)
            ventanas = driver.window_handles        
            driver.switch_to.window(ventanas[-1])

            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="urn:safelayer:tws:policies:authentication:flow:cert"]/a'))).click()

            xpaths = [
                '//*[@id="main"]/div[2]/app-root/app-layout'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths: 
                    if driver.find_elements(By.XPATH, xpath): 
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True 
                random_wait(wait_type='MEDIUM', wait=True)
            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)  

    def _check_contact_information(self, driver):
        try:
            contact_details = driver.find_elements(By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-content/div[2]/div/div')
            for row in contact_details:
                label = row.find_element(By.XPATH, './/div/span[1]').text
                value = row.find_element(By.XPATH, './/div/span[3]/span').text
                if ('Teléfono' in label and value == self.multivia.get('phone')) or ('Correo' in label and value == self.multivia.get('mail')):
                    check = True
                else:
                    check = False
            return check
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error checking contact information: {e}")

    def subscribe(self, client_name:str, id_cliente: str, nif_cif: str, tipo_cliente : str) -> bool:
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
            login = self._login_euskadi(driver)
            action = None
            if login:
                try: 
                    nav_items = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '//*[@id="main"]/div[2]/app-root/app-layout/div/mat-sidenav-container/mat-sidenav/div/div/mat-nav-list/div/a'))
                    )
                    
                    for nav in nav_items:
                        span = nav.find_element(By.XPATH, './/span/span/span')
                        if span.text.lower() == 'mi perfil':                       
                            nav.click()
                            break
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Pending", f"Error Navegando a Mi perfil: {e}")

                random_wait(wait_type='MEDIUM', wait=True)
                # //*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span[2]/mat-card/mat-card-actions/div/button
                try:
                    # //*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span[2]/mat-card/mat-card-title/h2
                    try: 
                        perfil_title = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-title/h2'))
                        )                        
                    except Exception as e:
                        try:
                            perfil_title = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-title/h2'))
                            )
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Pending", f"Error obteniendo el título del perfil: {e}")


                    if nif_cif in perfil_title.text:
                        try:
                            email_label = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-content/div[2]/div/div/div/span[1]'))
                            )
                            if email_label.text == 'Correo electrónico':
                                self._log(logging.INFO, self.sede, "Success", "El correo electrónico ya está registrado.")
                                email_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-content/div[2]/div/div/div/span[3]'))
                                )
                                
                                if email_field.text.strip() == self.mail.strip():
                                    self._log(logging.INFO, self.sede, "Success", f"El correo {email_field.text} ya está registrado y verificado.")
                                    action = list(CERT_SEDES_ACTION.items())[6]
                                    return True, action
                                else:
                                    self._log(logging.WARNING, self.sede, "Pending", f"El correo registrado ({email_field.text}) no coincide con el esperado ({self.mail}).")
                                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.element_to_be_clickable((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-actions/span/div/button'))
                                    ).click()
                            else:
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-actions/div/button'))).click()  
                                random_wait(wait_type='MEDIUM', wait=True)
                        except Exception as e:
                            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="mat-tab-nav-panel-3"]/app-cuenta-resumen/span/mat-card/mat-card-actions/div/button'))).click()  
                            random_wait(wait_type='MEDIUM', wait=True)

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Pending", f"Error navegando a Mi perfil: {e}")
                try:                                       
                    if tipo_cliente == 'Particular':     
                        try:
                            try:
                                # Get value from first input using WebDriverWait
                                nombre_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field[1]/div[1]/div[2]/div/input'))
                                )
                                nombre_value = nombre_field.get_attribute('value')

                                # Second input using WebDriverWait
                                apellido_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field[2]/div[1]/div[2]/div/input'))
                                )

                                apellido2_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/div/mat-form-field/div[1]/div[2]/div/input'))
                                )

                                if nombre_value:
                                    parts = nombre_value.split(' ')
                                    nombre_field.clear()
                                    nombre_field.send_keys(parts[0])
                                    apellido_field.clear()
                                    apellido_field.send_keys(parts[1])
                                    apellido2_field.clear()
                                    apellido2_field.send_keys(parts[2] if len(parts) > 2 else '')
                                else:
                                    nombre_field.clear()
                                    nombre_field.send_keys(client_name.split(' ')[0])
                                    apellido_field.clear()
                                    apellido_field.send_keys(client_name.split(' ')[1])
                                    apellido2_field.clear()
                                    apellido2_field.send_keys(' '.join(client_name.split(' ')[2]))
                            except Exception as e:
                                self._log(logging.WARNING, self.sede, "Failure", f"Error introduciendo nombre y apellido.")

                            try:
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field[1]/div[1]/div[2]/div/mat-select/div'))
                                ).click()
                                random_wait(wait_type='MEDIUM', wait=True)

                                # Wait for the language dropdown options to be present
                                languages = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    lambda d: d.find_elements(By.XPATH, '//*[@id="mat-select-4-panel"]/mat-option')
                                )
                                
                                for option in languages:
                                    # self.logger.info(f"Idioma: {option.get_attribute('value')}")
                                    if option.get_attribute('value').lower() == 'es':
                                        option.click()
                                        break
                                
                                random_wait(wait_type='MEDIUM', wait=True)
                                
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error selecting option idioma.")
                                return False, (0, f"Error selecting option idioma")
                            
                            try:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field[2]/div[1]/div[2]/div/mat-select/div'))
                                ).click()
                                random_wait(wait_type='MEDIUM', wait=True)      
                                                    
                                # Use WebDriverWait to ensure the options are present
                                sexos = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    lambda d: d.find_elements(By.XPATH, '//*[@id="mat-select-8-panel"]/mat-option')
                                )
                                for sexo in sexos:
                                    if sexo.text.strip().lower() == 'hombre':
                                        sexo.click()
                                        break
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error seleccionando el sexo.")
                                return False, (0, f"Error seleccionando el sexo")

                            try:
                                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until( 
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[1]/div/mat-form-field/div[1]/div[2]/div/mat-select/div'))
                                ).click()
                                random_wait(wait_type='MEDIUM', wait=True)

                                canales = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    lambda d: d.find_elements(By.XPATH, '//*[@id="mat-select-6-panel"]/mat-option')
                                )
                                for canal in canales:
                                    # self.logger.info(f"Canal: {canal.get_attribute('value')}")
                                    if canal.get_attribute('value').lower() == 'electronico':
                                        canal.click()
                                        break

                                random_wait(wait_type='MEDIUM', wait=True)
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error seleccionando el canal de comunicacion {e}")
                                return False, (0, f"Error seleccionando el canal de comunicacion")
                            
                            
                            # div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[4]/div[1]
                            fields = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                lambda d: d.find_elements(By.XPATH, '//*[@id="mat-mdc-dialog-0"]/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[5]/div[1]')
                            )

                            driver.execute_script("window.scrollBy(0, 100);")
                            for index, field in reversed(list(enumerate(fields))):
                                try:
                                    # mat-form-field/div[1]/div[2]/div/label/mat-label
                                    # mat-form-field/div[1]/div[2]/div/input
                                    label = field.find_element(By.XPATH, './/mat-form-field/div[1]/div[2]/div/label/mat-label').text
                                    if 'Correo' in label:
                                        email_field = field.find_element(By.XPATH, './/mat-form-field/div[1]/div[2]/div/input')
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
                                            random_wait(wait_type='MEDIUM', wait=True)
                                            email_confirm_field = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                                EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[5]/div[2]/mat-form-field/div[1]/div[2]/div/input'))
                                            )
                                            email_confirm_field.clear()
                                            email_confirm_field.send_keys(self.mail)                                    
                                except Exception as e:
                                    self._log(logging.ERROR, self.sede, "Failure", f"Error processing field {index}: {e}")
                                    return False, (0, f"Error processing field {index}: {e}")

                            random_wait(wait_type='MEDIUM', wait=True)                                  
                            try:
                                checkbox = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until( 
                                    # /html/body/div[5]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/div/div[1]/mat-checkbox/div/div/input
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/div/div[1]/mat-checkbox/div'))
                                )
                                checkbox.click()                                
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error haciendo click en checkbox: {e}")
                                return False, (0, f"Error haciendo click en checkbox: {e}")
                            

                            save_button = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[3]/button[2]/span[2]'))
                            )
                            if save_button.text == 'GUARDAR':
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[3]/button[2]'))).click()
                                self._log(logging.INFO, self.sede, "Success", "Datos de contacto guardados correctamente.")
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "Error: No se encontró el botón GUARDAR")
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error Introduciendo datos de contacto: {e}")
                            return False , (0, f"Error Introduciendo datos de contacto: {e}")      
                    
                    elif tipo_cliente == 'Empresa':
                        try:
                            try:
                                # //*[@id="mat-mdc-dialog-0"]/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field/div[1]/div[2]/div
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[1]/mat-form-field/div[1]/div[2]/div/mat-select/div'))
                                ).click()
                                random_wait(wait_type='MEDIUM', wait=True)                                
                                languages = driver.find_elements(By.XPATH, '//*[@id="mat-select-4-panel"]/mat-option')
                                for option in languages:
                                    # self.logger.info(f"Idioma: {option.get_attribute('value')}")
                                    if option.get_attribute('value').lower() == 'es':
                                        option.click()
                                        break
                                
                                random_wait(wait_type='MEDIUM', wait=True)
                                
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error selecting option idioma {e}")
                                return False, (0, f"Error selecting option idioma")
                            # /mat-form-field/div[1]/div[2]/div
                            # /html/body/div[5]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[4]/div[1]/mat-form-field/div[1]/div[2]/div/label/mat-label
                            fields = driver.find_elements(By.XPATH, '//*[@id="mat-mdc-dialog-0"]/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[4]/div')
                            for index, field in reversed(list(enumerate(fields))):
                                try:
                                    label = field.find_element(By.XPATH, './/mat-form-field/div[1]/div[2]/div/label/mat-label').text
                                    if 'Correo' in label:
                                        email_field = field.find_element(By.XPATH, './/mat-form-field/div[1]/div[2]/div/input')
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
                                            random_wait(wait_type='MEDIUM', wait=True)
                                            email_confirm_field = field.find_element(By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/form/div[2]/div[4]/div[2]/mat-form-field/div[1]/div[2]/div/input')
                                            email_confirm_field.clear()
                                            email_confirm_field.send_keys(self.mail)                                    
                                except Exception as e:
                                    self._log(logging.ERROR, self.sede, "Failure", f"Error processing field {index}: {e}")
                                    return False, (0, f"Error processing field {index}: {e}")

                            checkbox = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[2]/div/div[1]/mat-checkbox/div'))
                            )
                            checkbox.click()
                            # //*[@id="mat-mdc-dialog-0"]/div/div/app-dialog-modificarcuenta/div[3]/button[2]/span[2]
                            save_button = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[3]/button[2]/span[2]'))
                            )
                            if save_button.text == 'GUARDAR':
                                # //*[@id="mat-mdc-dialog-0"]/div/div/app-dialog-modificarcuenta/div[3]/button[2]
                                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/div/div/app-dialog-modificarcuenta/div[3]/button[2]'))).click()
                                self._log(logging.INFO, self.sede, "Success", "Datos de contacto guardados correctamente.")
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "Error: No se encontró el botón GUARDAR")
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error Introduciendo datos de contacto: {e}")
                            return False , (0, f"Error Introduciendo datos de contacto: {e}")

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error actualizando mi perfil: {e}")
                    return False, (0, f"Error navegando a Mi perfil: {e}")
                              
                random_wait(wait_type='LONG', wait=True)
                verificacion = self._check_contact_information(driver)
                if verificacion:
                    self._log(logging.INFO, self.sede, "Success", "Los medios de contacto se han verificado.")
                    return True, action
                else:
                    self._log(logging.INFO, self.sede, "Pending", "Los medios de contacto NO se han verificado correctamente.")
                    return False, (0, "Los medios de contacto NO se han verificado correctamente.")
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

    # def getNotications(self, idCliente, idNotificacion, nif_cif, multivia, portalLink='https://www.euskadi.eus/mi-carpeta/web01-sede/es/'):
        # Crear una carpeta temporal para el perfil de usuario
        # temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        # driver_setup = WebDriverSetup(temp_profile, self.portal_link, self.sede)
        # driver = driver_setup.setup_chrome_driver_altas() 
        # random_wait(wait_type='LONG', wait=True))

        # try:
        #     login = self._login_euskadi(driver)
        #     if login:
        #         # Step 0: Navigate to the notifcations section
        #         try:
        #             print("Step 0: Navigate to the notifcations section")
        #             WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
        #                 EC.element_to_be_clickable((By.XPATH, '//*[@id="main"]/div[2]/app-root/app-layout/div/mat-sidenav-container/mat-sidenav/div/div/mat-nav-list/div/a[2]'))
        #             ).click()

        #         except Exception as e:
        #             print(f"Step 0 failed: {e}")
                
        #         notificationsSections = driver.find_elements(By.XPATH, '//*[@id="mat-tab-nav-panel-9"]/app-notificaciones-list/mat-nav-list')
                
        #         if notificationsSections:
        #             # Step 1: Access Section: /span
        #             for index, section in enumerate(notificationsSections, start=1):
        #                 try:
        #                     print(f"Step 1: Section {index}")

        #                     section.find_element(By.XPATH, f'.//span[{index}]/div/mat-list-item').click()
        #                     dropdown_element = section.find_element(By.XPATH, '//*[@id="mat-select-20"]')
        #                     dropdown_element.click()
        #                     option_element = section.find_element(By.XPATH, '//*[@id="mat-option-34"]')
        #                     option_element.click()

        #                     notifications = driver.find_elements(By.XPATH, '//*[@id="mat-tab-nav-panel-9"]/app-notificaciones-list/mat-nav-list/app-virtual-scroll/div')
        #                     notification_data = []

        #                     for index, notification in enumerate(notifications, start=1):
        #                         try:
        #                             # Extraer datos específicos dentro de cada notificación
        #                             print(f"Processing notification {index}:, {notification}")
        #                             acto = notification.find_element(By.XPATH, './/mat-list-item/span/span/span/span[2]').text
        #                             description = notification.find_element(By.XPATH, './/mat-list-item/span/span/p[1]').text
        #                             id = notification.find_element(By.XPATH, './/mat-list-item/span/span/p[2]/span/span[1]/span[3]').text
        #                             publication_date = notification.find_element(By.XPATH, './/mat-list-item/span/span/p[3]/span/span[1]/span[3]').text
        #                             expiration_date = notification.find_element(By.XPATH, './/mat-list-item/span/span/p[3]/span/span[3]/span[2]').text

        #                             print(f"Acto: {acto}, Description: {description}, ID: {id}, Publication Date: {publication_date}, Expiration Date: {expiration_date}")

        #                             notification_dict = {
        #                                 "acto": acto,
        #                                 "description": description,
        #                                 "id": id,
        #                                 "publication_date": publication_date,
        #                                 "expiration_date": expiration_date
        #                             }

        #                             notification_data.append(notification_dict)
                                    
        #                         except Exception as e:
        #                             print(f"Failed to parse notification: {e}")
                            
                            
        #                 except Exception as e:
        #                     print(f"Step 1 failed for section {index}: {e}")

        #         return notification_data
        #     else:
        #         print("Login failed")
        #         return None

        # except Exception as e:
        #     print(f"⚠️ Error en recuperar notificaciones en {portalLink}: {e}")
        #     return False

        # finally:
        #     # Cerrar navegador después de completar la acción
        #     random_wait(wait_type='LONG', wait=True))
        #     driver.quit()
        #     shutil.rmtree(temp_profile, ignore_errors=True)