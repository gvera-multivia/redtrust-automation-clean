import logging
from multiprocessing import Queue
import time, tempfile, shutil
from enum import Enum
from typing import Tuple, Union
import uuid

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# PERSONAL PACKAGES - UTILS
from app.redtrust.redtrust_manager import RedTrustManager
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait

class ExecutionPath(Enum):
    LOGGED_IN = 'LOGGED_IN'
    LOGGED_IN_2 = 'LOGGED_IN2'
    NO_LOGIN = 'NO_LOGIN'
    NO_LOGIN_2 = 'NO_LOGIN_2'
    MULTIVIA = 'MULTIVIA'
    UNKNOWN = 'UNKNOWN'

class RobotEnotum:
    def __init__(self, mail : str, date : str, cliente : str, log_queue: Queue, execution_id: str,  module : str ="Altas", portal_link : str ='https://canalempresa.gencat.cat/ca/inici/', sede : str ='enotum',
            n_mails : int = 2,
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

    def _login_enotum(self, driver) -> Tuple[bool, Union[ExecutionPath, None], Union[str, None]]:
        try: 
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="ppms_cm_reject-all"]'))
                ).click()
            except Exception:
                self._log(logging.INFO, self.sede, "Pending", "No se encontró el botón de cookies, continuando...")

            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="hTContainer"]/div/div[1]/div[1]/div/div/div[2]/div/ul/li[1]/a'))
            ).click()

            ventanas = driver.window_handles
            driver.switch_to.window(ventanas[-1])

            # Continuar con el certificado digital
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
            except Exception:   
                self._log(logging.INFO, self.sede, "Pending", "No se encontró el botón de aceptar certificado, continuando...")            

            xpaths = [
                {'element':'/html/body/app-root/app-header/header/content[2]/app-info-perfil/div/label[1]', 'path' : ExecutionPath.LOGGED_IN},
                # {'element': '/html/body/app-root/main/app-inici/section/notificacions-avisos', 'path': ExecutionPath.LOGGED_IN},
                {'element': '/html/body/app-root/main/seleccion-perfil-pf', 'path': ExecutionPath.LOGGED_IN_2},                
                {'element': '/html/body/app-root/main/lopd-onboarding', 'path': ExecutionPath.NO_LOGIN},
                {'element': '/html/body/app-root/main/bienvenida-onboarding', 'path': ExecutionPath.NO_LOGIN},
                {'element': '/html/body/app-root/main/seleccion-perfil-pf/div/div[1]/div[1]', 'path': ExecutionPath.UNKNOWN},
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:  
                for xpath_dict in xpaths: 
                    try:
                        element = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, xpath_dict['element'])))
                        if element: 
                            if 'MULTIVIA' in element.text:
                                self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath_dict['path']} encontrado.")
                                return True, ExecutionPath.MULTIVIA
                            else:
                                self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath_dict['path']} encontrado.")
                                return True, xpath_dict['path']

                    except Exception as e:
                        self._log(logging.INFO, self.sede, "Pending", f"No se encontró el elemento para {xpath_dict['element']}")

            self._log(logging.ERROR, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False, None

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False, None

    def subscribe(self, id_cliente: str, nif_cif: str, client : str) -> bool:
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
            login, execution_path = self._login_enotum(driver)
            if login:
                if execution_path == ExecutionPath.LOGGED_IN:
                    self._log(logging.INFO, self.sede, "Success", "Ya logueado en el portal")
                    try:
                        random_wait(wait_type='LONG', wait=True)
                        driver.get('https://carpeta.canalempresa.gencat.cat/canalempresa360#/gestio-perfils-i-permisos')
                        random_wait(wait_type='MEDIUM', wait=True)

                        table_rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_all_elements_located((By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr'))
                        )

                        action = list(CERT_SEDES_ACTION.items())[6]
                        
                        for row in table_rows:
                            try:
                                span1_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[1]'))
                                ).text.strip()
                                span2_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[2]'))
                                ).text.strip()

                                self._log(logging.INFO, self.sede, "Pending", f"Checking row: {span1_text} - {span2_text}")
                                if 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL' in span1_text or 'B62798210' in span2_text:
                                    self._log(logging.INFO, self.sede, "Success", "Found the expected collaborator in the table.")
                                    return True, action
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error accessing collaborator row elements: {e}")
                                continue
                            
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error buscando el colaborador en la tabla. {e}")
                        return False, (0, "Error buscando el colaborador en la tabla")
        
                    result, action = self._subscribe_atc_already_logged_in(driver, self.multivia, client)
                    if result:
                        # Load Multivia certificate
                        redtrust = RedTrustManager({"usuario": "MULTIVIA", "password": "MULTIVIA"})
                        redtrust.automate_redtrust('MULTIVIA')
                        
                        # New driver for Multivia
                        temp_profile_multivia = tempfile.mkdtemp(prefix=f"multivia_temp_profile_")
                        driver_setup_multivia = WebDriverSetup(
                            temp_profile=temp_profile_multivia,
                            portal_link=self.portal_link,
                            module="Altas",
                            execution_id=self.execution_id,
                            log_dir="logs/altas",
                            filename=f"altas",
                            cliente=self.cliente,
                            task_id=self.sede,
                            site=self.sede
                        )
                        driver_multivia = driver_setup_multivia.setup_chrome_driver_altas() 

                        login, execution_path = self._login_enotum(driver_multivia)

                        if login:
                            if execution_path == ExecutionPath.MULTIVIA:
                                # multivia = self._multivia_accept_invitation(driver_multivia, nif_cif)
                                multivia = True
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "Error desconocido")
                                return False, (0, "Error desconocido")
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "Error en login para Multivia")
                            return False, (0, "Error en login para Multivia")
                        
                        if multivia:
                            # Check if the contact details are verified
                            self._log(logging.INFO, self.sede, "Success", "Contact details verified")
                            driver.refresh()
                            rows = driver.find_elements(By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr')
                            for row in rows:
                                status_icon = row.find_element(By.XPATH, './td[7]/span/mat-icon')
                                if status_icon.get_attribute('title') == "Actiu":
                                    self._log(logging.INFO, self.sede, "Success", "Found an active collaborator.")
                                    return True, action
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "No active collaborator found.")
                                return False, (0, "No active collaborator found.")
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "Error en Multivia")
                            return False, (0, "Error en Multivia")
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "Error en darse de alta")
                        return False, (0, "Error en darse de alta")
                        
                elif execution_path == ExecutionPath.LOGGED_IN_2:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/seleccion-perfil-pf/div/div[1]/div[1]/div'))
                    ).click()

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/seleccion-perfil-pf/div/div[3]/div/button'))
                    ).click()
                    random_wait(wait_type='MEDIUM', wait=True)

                    try:
                        random_wait(wait_type='LONG', wait=True)
                        driver.get('https://carpeta.canalempresa.gencat.cat/canalempresa360#/gestio-perfils-i-permisos')
                        random_wait(wait_type='MEDIUM', wait=True)

                        table_rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_all_elements_located((By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr'))
                        )

                        action = list(CERT_SEDES_ACTION.items())[6]
                        
                        for row in table_rows:
                            try:
                                span1_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[1]'))
                                ).text.strip()
                                span2_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                                    EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[2]'))
                                ).text.strip()

                                self._log(logging.INFO, self.sede, "Pending", f"Checking row: {span1_text} - {span2_text}")
                                if 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL' in span1_text or 'B62798210' in span2_text:
                                    self._log(logging.INFO, self.sede, "Success", "Found the expected collaborator in the table.")
                                    return True, action
                            except Exception as e:
                                self._log(logging.ERROR, self.sede, "Failure", f"Error accessing collaborator row elements: {e}")
                                continue
                            
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error buscando el colaborador en la tabla. {e}")
                        return False, (0, "Error buscando el colaborador en la tabla")

                    result, action = self._subscribe_atc_already_logged_in(driver, self.multivia, client)
                    if result:
                        # Load Multivia certificate
                        redtrust = RedTrustManager({"usuario": "MULTIVIA", "password": "MULTIVIA"})
                        redtrust.automate_redtrust('MULTIVIA')
                        
                        # New driver for Multivia
                        temp_profile_multivia = tempfile.mkdtemp(prefix=f"multivia_temp_profile_")
                        driver_setup_multivia = WebDriverSetup(
                            temp_profile=temp_profile_multivia,
                            portal_link=self.portal_link,
                            module="Altas",
                            execution_id=self.execution_id,
                            log_dir="logs/altas",
                            filename=f"altas",
                            cliente=self.cliente,
                            task_id=self.sede,
                            site=self.sede
                        )
                        driver_multivia = driver_setup_multivia.setup_chrome_driver_altas() 

                        login, execution_path = self._login_enotum(driver_multivia)

                        if login:
                            if execution_path == ExecutionPath.MULTIVIA:
                                multivia = self._multivia_accept_invitation(driver_multivia, nif_cif)
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "Error desconocido")
                                return False, (0, "Error desconocido")
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "Error en login para Multivia")
                            return False, (0, "Error en login para Multivia")
                        
                        if multivia:
                            # Check if the contact details are verified
                            self._log(logging.INFO, self.sede, "Success", "Contact details verified")
                            driver.refresh()
                            rows = driver.find_elements(By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr')
                            for row in rows:
                                status_icon = row.find_element(By.XPATH, './td[7]/span/mat-icon')
                                if status_icon.get_attribute('title') == "Actiu":
                                    self._log(logging.INFO, self.sede, "Success", "Found an active collaborator.")
                                    return True, action
                            else:
                                self._log(logging.ERROR, self.sede, "Failure", "No active collaborator found.")
                                return False, (0, "No active collaborator found.")
                        else:
                            self._log(logging.ERROR, self.sede, "Failure", "Error en Multivia")
                            return False, (0, "Error en Multivia")
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", "Error en darse de alta")
                        return False, (0, "Error en darse de alta")

                elif execution_path == ExecutionPath.NO_LOGIN:
                    self._log(logging.INFO, self.sede, "Pending", "No logueado en el portal")
                    result, action = self._subscribe_atc_not_logged_in(driver, self.multivia, nif_cif)
                    self._log(logging.INFO, self.sede, "Pending", f"Result: {result}, Action: {action}")
                    return result, action                    
                elif execution_path == ExecutionPath.UNKNOWN:
                    self._log(logging.INFO, self.sede, "Pending", "UNKNOWN")
                    return False, (0, "UNKNOWN")
                else:
                    self._log(logging.ERROR, self.sede, "Failure", "Error desconocido")
                    return False, (0, "Error desconocido")            
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en darse de alta en {self.portal_link}: {e}")
            return False, (0, f"Error en darse de alta en {self.portal_link}")

        finally:
            # Cerrar navegador después de completar la acción
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)

    def _subscribe_atc_already_logged_in(self, driver, multivia : dict, client : str) -> bool:
        try:
            # Ensure we are on the correct page before proceeding
            if driver.current_url != "https://carpeta.canalempresa.gencat.cat/canalempresa360#/gestio-perfils-i-permisos":
                driver.get("https://carpeta.canalempresa.gencat.cat/canalempresa360#/gestio-perfils-i-permisos")
                random_wait(wait_type='MEDIUM', wait=True)

            random_wait(wait_type='LONG', wait=True)
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/app-botonera-colaboradors/div[1]/div/button'))
            ).click()

            self._log(logging.INFO, self.sede, "Pending", "Esperando a que se abra el modal de nuevo colaborador")

            random_wait(wait_type='MEDIUM', wait=True)

            try:
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-1/app-dades-personals-colaborador/div/form/div[1]/div[2]'))).click()
                dropdown_cif = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="tipusDocumentPF"]'))
                )
                Select(dropdown_cif).select_by_value('2')  # 1: DNI, 2: DNI estranger, 3: NIE, 4: NIF empresa, 5: Passaport
                random_wait(wait_type='MEDIUM', wait=True)

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="dni"]'))
                ).send_keys(multivia.get('nif'))

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="raoSocial"]'))
                ).send_keys(multivia.get('purpose'))

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="correu"]'))
                ).send_keys(multivia.get('mail'))

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="movil"]'))
                ).send_keys(multivia.get('phone'))

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-1/app-dades-personals-colaborador/div/form/div[7]/label/span'))
                ).click()

                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-1/app-dades-personals-colaborador/div/form/div[8]/label/span'))
                ).click()

                random_wait(wait_type='MEDIUM', wait=True)
                
                if self.mail == self.multivia.get('mail'):
                    action = list(CERT_SEDES_ACTION.items())[1]
                else:
                    action = list(CERT_SEDES_ACTION.items())[2]

                # Accept Button
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-1/div[2]/button[2]'))
                ).click()
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", "Error completando formulario de contacto")
                return False, (0, "Error completando formulario de contacto")
            
            try:
                colaborador = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="depenDe"]'))
                )
                self._log(logging.INFO, self.sede, "Success", f"Colaborador encontrado: {client}")
                Select(colaborador).select_by_visible_text(client) # ! TODO
                random_wait(wait_type='MEDIUM', wait=True)
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-2/div/button[2]'))
                ).click()
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-3/app-permisos-tramits/div[3]/div[1]/label/span'))    
                ).click()
                random_wait(wait_type='MEDIUM', wait=True)
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(  
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-3/div[2]/button[2]'))
                ).click()
                WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="alta-colaborador"]/div[1]/div/app-modal-nuevo-colaborador/app-nuevo-colaborador-pas-5/div/button[3]'))
                ).click()

            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", "Error rellenando permisos")
                return False, (0, "Error rellenando permisos")

            try:
                for index, element in enumerate(driver.find_elements(By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr')):
                    if 'MULTIVIA' in element.find_element(By.XPATH, './td[1]/div[3]/span[1]').text and multivia.get('nif') in element.find_element(By.XPATH, './td[1]/div[3]/span[2]').text:
                        return True, action
                    random_wait(wait_type='MEDIUM', wait=True)
            except Exception as e:  
                self._log(logging.ERROR, self.sede, "Failure", "Verificacion fallida: no encontramos Multivia")
                return False, (0, "Verificacion fallida: no encontramos Multivia")
            
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en el proceso de suscripción, previamente ya loggeado: {e}")
            return False, (0, f"Error en el proceso de suscripción, previamente ya loggeado")
        
    def _subscribe_atc_not_logged_in(self, driver, multivia : dict, client : str) -> bool:
        try:
            try:
                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/lopd-onboarding/div/div[1]/lopd/div/div[2]/div[1]/label'))
                ).click()

                WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/lopd-onboarding/div/div[2]/div/button'))
                ).click()
                
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", "Error al aceptar la política de privacidad")

            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/bienvenida-onboarding/div/div[4]/div/button'))
            ).click()
            
            random_wait(wait_type='MEDIUM', wait=True)

            nif_cif = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(  
                EC.presence_of_element_located((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[2]/datos/div/div/table/tr[2]/td[2]'))
            ).text

            if client == nif_cif:
                try:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[3]/div/button[2]'))
                    ).click()
                
                    boxes = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, 'html/body/app-root/main/datos-onboarding/div/div[3]/div'))
                    )

                    for box in boxes:
                        if box.find_element('.//div').text == "SOC PROFESSIONAL O EMPRESARI/ÀRIA":
                            box.click()
                            break
                                                             
                    # profile_box = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    #     EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[3]/div[1]/div'))
                    # )
                    # if profile_box.text == "SOC PROFESSIONAL O EMPRESARI/ÀRIA":
                    #     profile_box.click()

                    random_wait(wait_type='MEDIUM', wait=True)

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[5]/div/button[2]'))
                    ).click()

                    try:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[5]/div/button[2]'))
                        ).click()

                        random_wait(wait_type='LONG', wait=True)

                        if driver.get_url != 'https://carpeta.canalempresa.gencat.cat/canalempresa360#/onboarding-avisos':
                            WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[5]/div/button[2]'))
                            ).click()
                        random_wait(wait_type='MEDIUM', wait=True)
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", "Error haciendo click en continuar después de datos de onboarding")
                    

                    random_wait(wait_type='MEDIUM', wait=True)

                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", "Error en el onboarding")
                    return False, (0, "Error en el onboarding")
                
                try:
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[1]/details/dades-contacte/div[4]/button[1]'))
                    ).click()
                    dropdown_cif = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[1]/details/dades-contacte/p-dialog/div/div[2]/div/form/div[1]/select'))
                    )
                    Select(dropdown_cif).select_by_value('2')  # 1: DNI, 8: DNI estranger, 4: NIE, 2: NIF empresa, 3: Passaport
                    random_wait(wait_type='MEDIUM', wait=True)

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="numDocument"]'))
                    ).send_keys(multivia.get('nif'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="raoSocial"]'))
                    ).send_keys(multivia.get('purpose'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="email"]'))
                    ).send_keys(multivia.get('mail'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="movil"]'))
                    ).send_keys(multivia.get('phone'))

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[1]/details/dades-contacte/p-dialog/div/div[2]/div/form/div[6]/div'))
                    ).click()

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[1]/details/dades-contacte/p-dialog/div/div[2]/div/form/div[7]/div'))
                    ).click()
                    random_wait(wait_type='LONG', wait=True)
            
                    # Accept Button
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[1]/details/dades-contacte/p-dialog/div/div[2]/div/p-footer/div/div/button[2]'))
                    ).click()
                    random_wait(wait_type='LONG', wait=True)
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", "Error añadiendo datos de contacto")
                    return False, (0, "Error añadiendo datos de contacto")
                                
                try: 
                    dropdown_option = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/avisos-comunicaciones/div[4]/div/div/select'))
                    )
                    Select(dropdown_option).select_by_value(self.mail)  
                    
                    random_wait(wait_type='MEDIUM', wait=True)
                    
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    random_wait(wait_type='MEDIUM', wait=True)

                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/datos-onboarding/div/div[2]/div/button[2]'))
                    ).click()
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", "Error seleccionando el mail de notificaciones en el dropdown")
                    return False, (0, "Error seleccionando el mail de notificaciones en el dropdown")
                
                try:
                    # Click on the first checkbox
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/intereses-onboarding/div[1]/intereses/div/div/p-treetable/div/div/table/thead/tr/th[2]/div/label'))
                    ).click()

                    # Click on the second checkbox
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/intereses-onboarding/div[1]/intereses/div/div/p-treetable/div/div/table/thead/tr/th[3]/div/label'))
                    ).click()

                    random_wait(wait_type='MEDIUM', wait=True)
                    # Click on the "Continue" button
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/intereses-onboarding/div[2]/div/button[2]'))
                    ).click()
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", "Error seleccionando los intereses a informar")
                    return False, (0, "Error seleccionando los intereses a informar")
            else:
                self._log(logging.ERROR, self.sede, "Failure", f"El cliente no coincide con el NIF/CIF {nif_cif} - {client}.")
                return False, (0, f"El cliente no coincide con el NIF/CIF {nif_cif} - {client}.")

            try:
                # Verificar mensaje de éxito
                success_message = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/main/finalizar-onboarding/div/h1'))
                ).text

                if success_message == "Fet! Ja tenim preparada la teva àrea privada":
                    WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/app-root/main/finalizar-onboarding/div/div[3]/div/button[2]'))
                    ).click()
                    self._log(logging.INFO, self.sede, "Success", "Onboarding finalizado con éxito.")
                else:
                    self._log(logging.ERROR, self.sede, "Failure", "Mensaje de éxito no encontrado.")
                    return False, (0, "Mensaje de éxito no encontrado.")
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", "Error en la verificación del onboarding")
                return False, (0, "Error en la verificación del onboarding")
            

            try:
                random_wait(wait_type='LONG', wait=True)
                driver.get('https://carpeta.canalempresa.gencat.cat/canalempresa360#/gestio-perfils-i-permisos')
                random_wait(wait_type='MEDIUM', wait=True)

                table_rows = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                    EC.presence_of_all_elements_located((By.XPATH, '/html/body/app-root/main/gestio-perfils-i-permisos/div[2]/app-vista-colaborador-list/div[1]/table/tbody/tr'))
                )

                if self.mail == multivia.get('mail'):
                    action = list(CERT_SEDES_ACTION.items())[0]
                else:
                    action = list(CERT_SEDES_ACTION.items())[2]
                
                for row in table_rows:
                    try:
                        span1_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[1]'))
                        ).text.strip()
                        span2_text = WebDriverWait(row, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, './td[1]/div[2]/span[2]'))
                        ).text.strip()

                        self._log(logging.DEBUG, self.sede, "Pending", f"Checking row: {span1_text} - {span2_text}")
                        if 'MULTIVIA NEGOCIADO Y DEFENSA ADMINISTRATIVA Y JURIDICA ESPAÑA SL' in span1_text or 'B62798210' in span2_text:
                            self._log(logging.INFO, self.sede, "Success", "Found the expected collaborator in the table.")
                            return True, action
                    except Exception as e:
                        self._log(logging.ERROR, self.sede, "Failure", f"Error accessing collaborator row elements: {e}")
                        continue

                # Only reach here if the loop did not return
                return False, (0, "No se encontró el colaborador esperado en la tabla")
                    
            except Exception as e:
                self._log(logging.ERROR, self.sede, "Failure", f"Error buscando el colaborador en la tabla. {e}")
                return False, (0, "Error buscando el colaborador en la tabla")
            
        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error completando formulario de contacto: {e}")           
            return False, (0, "Error completando formulario de contacto")
