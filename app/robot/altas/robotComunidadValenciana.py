from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid
import logging

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import CERT_SEDES_ACTION, random_wait


class RobotComunidadValenciana:
    def __init__(self, mail: str, date: str, cliente: str, log_queue: Queue, execution_id: str, module : str ="Altas", portal_link: str = 'https://www.comunicaciones.gva.es/comunicaciones/login.html?lang=ca', sede: str = 'comunidad valenciana',
            n_mails: int = 1,
            multivia: dict = {
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

    def _login_cvalenciana(self, driver) -> bool:
        try: 
            WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="formLogin"]/div/div[2]/div/p/a'))).click()

            xpaths = [
                '//*[@id="contenedor"]'
            ]

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False) 
            while time.time() < end_time:
                for xpath in xpaths: 
                    if driver.find_elements(By.XPATH, xpath): 
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso: {xpath} encontrado.")
                        return True 
                random_wait(wait_type='SHORT', wait=True)

            self._log(logging.INFO, self.sede, "Failure", "Login fallido: No se encontraron los elementos esperados.")
            return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en login: {e}")
            return False

        finally:
            random_wait(wait_type='MEDIUM', wait=True)

    def subscribe(self, id_cliente: str, nif_cif: str) -> bool:
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
            login = self._login_cvalenciana(driver)
            if login:
                try:
                    ul = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="apartats_contingut"]/ul')))
                    for li in ul.find_elements(By.TAG_NAME, 'li'):
                        if li.text == 'PERSONALITZAR':
                            li.click()
                            break
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error en el menu de navegación: {e}")
                    return False, (0, f"Error en el menu de navegación")

                random_wait(wait_type='MEDIUM', wait=True)
                
                # Datos de contacto
                try:
                    avisos_select = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="avisos"]')))
                    Select(avisos_select).select_by_value("S")
                    
                    email_field = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="correo"]')))
                    email_value = email_field.get_attribute('value').strip()

                    if email_value: 
                        if self.mail == email_value:
                            self._log(logging.INFO, self.sede, "Success", f"El correo {email_value} ya está registrado.")
                            action = list(CERT_SEDES_ACTION.items())[6]  # 7: alta ya realizada                    
                        elif self.mail != email_value and self.multivia.get('mail') == email_value:
                            action = list(CERT_SEDES_ACTION.items())[4]  # 5: MULTIVIA sustituido por cliente
                        elif self.mail != email_value and self.multivia.get('mail') != email_value:
                            action = list(CERT_SEDES_ACTION.items())[3]  # 4: Correo sustituido por el de MULTIVIA correctamente.
                        else:
                            # try:
                            #     driver.get('https://carpetaciudadana.gva.es/micarpeta/?idioma=es')
                            #     WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            #         EC.presence_of_element_located((By.XPATH, '//*[@id="imc--contingut"]/div/div/div[2]/div[2]/button'))
                            #     ).click()
                            #     random_wait(wait_type='MEDIUM', wait=True)
                            #     driver.get('https://carpetaciudadana.gva.es/micarpeta/app/Configuracion')

                            # except Exception as e:
                            #     self._log(logging.ERROR, self.sede, "Failure", f"Error al navegar a micarpeta: {e}")
                            #     return False, (0, f"Error al navegar a micarpeta")
                            self._log(logging.ERROR, self.sede, "Failure", "Impossible añadir el correo del cliente")
                            return False, (-1, "Impossible añadir el correo del cliente")
                        
                    else:
                        if self.mail == self.multivia.get('mail'):
                            action = list(CERT_SEDES_ACTION.items())[0]  # 1: alta realizada correctamente
                        else:
                            action = list(CERT_SEDES_ACTION.items())[2]  # 3: correo cliente añadido

                    email_field.clear()
                    email_field.send_keys(self.mail)

                    modo_preferente_select = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="modoPreferente"]')))
                    Select(modo_preferente_select).select_by_value("S")

                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="btnGuardar"]'))).click()

                    # Aceptar la alerta
                    WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="missatge"]/div/div[2]/div[2]/div[2]/ul/li/a'))).click()

                    random_wait(wait_type='MEDIUM', wait=True)
                except Exception as e:
                    self._log(logging.INFO, self.sede, "Failure", f"Error añadiendo los datos de contacto {e}")
                    return False, (0, f"Error añadiendo los datos de contacto")
                
                # Verificar
                random_wait(wait_type='LONG', wait=True)
                try:
                    resultado_mail = WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(EC.presence_of_element_located((By.XPATH, '//*[@id="resultado"]/div/ul[2]/li[2]'))).text
                    if self.multivia.get('mail') in resultado_mail:
                        self._log(logging.INFO, self.sede, "Success", f"✅ Verificación exitosa: El correo {self.multivia.get('mail')} está presente.")
                        random_wait(wait_type='LONG', wait=True)
                        return True, action
                    
                except Exception as e:
                    self._log(logging.INFO, self.sede, "Failure", f"Error en la verificación: {e}")
                    random_wait(wait_type='X_LONG', wait=True)
                    return False, (0, f"Error en la verificación: {e}")
            else:
                self._log(logging.INFO, self.sede, "Failure", "Error en login")
                return False, (0, "Error en login")

        except Exception as e:
            self._log(logging.INFO, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            random_wait(wait_type='LONG', wait=True)
            return False, (0, f"Error en darse de alta en {self.portal_link}: {e}")

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
