import os
import logging
import pyautogui
import time
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import pymssql

class RedTrustCertificateLoader:
    def __init__(self, cliente, password, certificate_path):
        load_dotenv(dotenv_path='.env', override=True)
        self.db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        self.redtrust_config = {
            "url": os.getenv("REDTRUST_URL"),
            "username": os.getenv("REDTRUST_USERNAME"),
            "password": os.getenv("REDTRUST_PASSWORD"),
        }
        self.cliente = cliente
        self.password = password
        self.nif = None
        self.certificate_path = certificate_path
        self.driver = None
        self.logger = self.setup_logger()
        self.db_connection = self.setup_database()

    def setup_logger(self):
        logger = logging.getLogger("RedTrustCertificateLoader")
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def setup_database(self) -> pymssql.Connection:
        """Establish a connection to the database"""
        try:
            connection_string = (
                f"DRIVER={{SQL Server}};"
                f"SERVER={self.db_config['server']};"
                f"DATABASE={self.db_config['database']};"
                f"UID={self.db_config['user']};"
                f"PWD={self.db_config['password']};"
                f"Encrypt={'yes' if self.db_config['options']['encrypt'] else 'no'};"
                f"TrustServerCertificate=yes;"
                f"APP=PythonApp;"
            )
            conn = pymssql.connect(connection_string)
            return conn
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error connecting to the database: {e}")
            raise

    def setup_driver(self):
        self.logger.info("Setting up the WebDriver.")
        options = Options()
        
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_argument("--start-maximized")
        options.add_argument("--timeout=60000")
        options.add_argument("--log-level=3")
        
        # options.add_argument("--headless=new")  # Enable headless mode

        prefs = {
            "plugins.always_open_pdf_externally": True,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True,
            # Disable password saving and autofill
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.autofill_profile_enabled": False,
            "profile.autofill_credit_card_enabled": False,
        }
        options.add_experimental_option("prefs", prefs)

        self.driver = webdriver.Chrome(options=options)

    def login(self):
        try:
            self.logger.info("Logging into RedTrust.")
            self.driver.get(self.redtrust_config["url"])
            time.sleep(3)

            # Enter username
            username_input = self.driver.find_element(By.XPATH, "/html/body/app-root/div[1]/app-login/section/mat-card/mat-card-content/div[1]/form/mat-form-field[1]/div/div[1]/div//*[@id='username']")
            username_input.send_keys(self.redtrust_config["username"])
            time.sleep(2)

            # Click "Siguiente" or "Next" button after entering username
            next_button = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='content']/div[1]/app-login/section/mat-card/mat-card-content/div[1]/form/button"))
            )
            next_button.click()
            time.sleep(2)

            # Enter password
            password_input = self.driver.find_element(By.XPATH, "/html/body/app-root/div[1]/app-login/section/mat-card/mat-card-content/div[2]/form/mat-form-field/div/div[1]/div[1]//*[@id='password']")
            password_input.send_keys(self.redtrust_config["password"])
            time.sleep(2)

            # Click login button
            login_button = self.driver.find_element(By.XPATH, "//*[@id='content']/div[1]/app-login/section/mat-card/mat-card-content/div[2]/form/button[1]")
            login_button.click()
            time.sleep(3)
            return True
        
        except Exception as e:
            self.logger.error(f"Error during RedTrust login: {e}")
            return False

    def upload_certificate(self) -> bool:
        self.logger.info("Navigating to certificates page.")
        self.driver.get("https://redtrust.cloud/certificates")
        time.sleep(3)

        try:
            # Wait for spinner to disappear
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.invisibility_of_element((By.XPATH, "/html/body/app-root/div[1]/app-certificates/div[2]/mat-tab-group/div/mat-tab-body/div/app-private-certificates/div[1]/span"))
                )
                time.sleep(2)
            
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/app-root/div[1]/app-certificates/div[2]/mat-tab-group/div/mat-tab-body/div/app-private-certificates/div/div[2]/table'))
                )
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Certificates table did not load: {e}")
                return False

            try:
                fallback = self.fallback_method(str(self.cliente))
                if not fallback:
                    fallback = self.fallback_method(self.nif)


                if fallback:
                    fallback.find_element(By.XPATH, './/td[11]/button').click()
                    time.sleep(1)
                    # Wait for all buttons in the modal to be present
                    action_buttons = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_all_elements_located((By.XPATH, "/html/body/div[4]/div[2]/div/div/div/button"))
                    )

                    for btn in action_buttons:
                        try:
                            span = btn.find_element(By.XPATH, "./span")
                            if span.text.strip().lower() == "eliminar":
                                btn.click()
                                self.logger.info("Clicked 'Eliminar' button.")
                                time.sleep(2)                                
                                break
                            # if span.text.strip().lower() == "sustituir certificado":
                            #     btn.click()
                            #     self.logger.info("Clicked 'Sustituir certificado' button.")
                            #     time.sleep(2)
                            #     break
                        except Exception as e:
                            self.logger.warning(f"Error checking button text: {e}")
                    
                    eliminate_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-destroy/div/div[2]/div/button[1]'))
                    )
                    eliminate_btn.click()
                    time.sleep(2)
            except Exception as e:
                self.logger.error(f"Error in fallback certificate deletion: {e}")

            try:            
                # Click upload certificate button
                upload_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/div[1]/app-certificates/div[2]/mat-tab-group/div/mat-tab-body/div/app-private-certificates/div/div[1]/div[1]/div[1]/span[1]/button"))
                )
                upload_button.click()
                time.sleep(3)
            except Exception as e:
                self.logger.error(f"Error navigating to upload certificate modal: {e}")
                return False
            
            # CERTIFICATE UPLOAD MODAL PROCESS
            try:
                try:
                    # Fill in modal fields 
                    self.logger.info("Filling in certificate details.")
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-upload"))
                    )
                    time.sleep(2)

                    WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-upload/div/div[1]/div/div/div[1]/div[1]/ng-select"))
                    ).click()
                    time.sleep(2)

                    group_input = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-upload/div/div[1]/div/div/div[1]/div[1]/ng-select/div/div/div[2]/input"))
                    )
                    group_input.click()
                    time.sleep(2)
                    group_input.send_keys("multivia")
                    group_input.send_keys(Keys.RETURN)
                    time.sleep(2)

                    password_input = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-upload/div/div[1]/div/div/div[1]/div[2]/mat-form-field/div/div[1]/div[1]//input[starts-with(@id, 'mat-input-')]"))
                    )
                    password_input.send_keys(self.password)
                    time.sleep(2)

                except Exception as e:
                    self.logger.error(f"Error filling in certificate modal fields: {e}")
                    return False

                try:
                    file_input = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((
                            By.XPATH,
                            "//input[@type='file' and @accept='.pfx, .p12' and @data-selenium='input-upload-cert-file']"
                        ))
                    )

                    self.driver.execute_script("arguments[0].removeAttribute('hidden');", file_input)
                    file_input.send_keys(self.certificate_path)
                    self.logger.info(f"Certificate uploaded: {self.certificate_path}")
                    time.sleep(5)

                except Exception as e:
                    self.logger.error(f"Error uploading certificate file: {e}")
                    return False
               
                # Click accept upload button
                accept_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-upload/div/div[2]/div/button[1]"))
                )
                accept_button.click()
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Error filling certificate modal fields for upload: {e}")
                return False

            # UPLOAD CONFIRMATION PROCESS OR NAVIGATE TO THE CERTIFICATE MODAL
            try:
                try:
                    notification = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="toast-container"]/app-toastr-custom-action/div[1]/div/div[1]'))
                    )

                    notification_text = notification.text.strip().lower()
                    if "éxito" in notification_text or "success" in notification_text:
                        self.logger.info("Certificate uploaded successfully.")
                        time.sleep(2)
                        WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="toast-container"]/app-toastr-custom-action/div[1]/div/div[2]/a'))
                        ).click()
                        time.sleep(3)
                    else:
                        self.logger.error(f"Notification from the upload returned an error message: {notification_text}")
                        return False
                                    
                except Exception as e:
                    self.logger.error(f"Notification not found or not clickable: {e}")
                    fallback = self.fallback_method(self.nif)

                    if not fallback:
                        self.logger.error("Fallback method failed.")
                        return False
                    else:
                        fallback.find_element(By.XPATH, './/td[2]').click()
                        time.sleep(3)

            except Exception as e:
                self.logger.error(F"Error navigating to certificate modal after upload: {e}")
                return False

            # UPDATE CERTIFICATE MODAL PARAMS
            try:
                # Open certificate modal
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-view'))
                )
                time.sleep(2)

                # Delete all and input client number
                client_input = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-view/div/div[1]/mat-tab-group/div/mat-tab-body[1]/div/div/div[2]/div[1]/div[1]/mat-form-field/div/div[1]/div//input[starts-with(@id, "mat-input-")]'))
                )
                client_input.clear()
                client_input.send_keys(str(self.cliente))
                time.sleep(2)

                # Accept changes
                accept_changes_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-view/div/div[2]/div/button[1]'))
                )
                accept_changes_btn.click()
                time.sleep(3)

                # Click the accept button in the policy change resume modal
                accept_confirm_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[4]/div/mat-dialog-container/app-dialog-confirm-changes/div/div[2]/div/button[1]'))
                )
                accept_confirm_btn.click()
                time.sleep(2)

                # Click the close button in the certificate modal
                close_btn = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-view/div/div[2]/div/button'))
                )
                close_btn.click()
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Error updating certificate modal parameters: {e}")
                return False

            # POLICY ASSIGNMENT PROCESS
            try:
                # Go to policies page
                self.driver.get("https://redtrust.cloud/policies")
                time.sleep(3)

                # Iterate over policy rows
                policy_rows = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_all_elements_located((By.XPATH, '/html/body/app-root/div[1]/app-policies/div[2]/mat-tab-group/div/mat-tab-body[1]/div/app-private-policies/div/div[2]/table/tbody/tr'))
                )
                for row in policy_rows:
                    policy_span = row.find_element(By.XPATH, './td[5]/span')
                    if 'multivia' in policy_span.text.strip().lower():
                        policy_span.click()
                        time.sleep(2)
                        break

                try:
                    # Wait for modal
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '/html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view'))
                        )
                    except Exception as e:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.XPATH, '/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view'))
                        )
                    
                    time.sleep(2)
                    # Iterate tabs
                    tab_headers = WebDriverWait(self.driver, 10).until( 
                        EC.presence_of_all_elements_located((By.XPATH, '/html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view/div/div[1]/mat-tab-group/mat-tab-header/div/div/div/div'))
                    )
                    self.logger.info("Iterating over policy modal tabs to find 'certificados/certificates'.")
                    for tab in tab_headers:
                        tab_text = tab.find_element(By.XPATH, './/div/div').text
                        self.logger.info(f"Found tab: {tab_text}")
                        if any(word in tab_text.strip().lower() for word in ['certificados', 'certificates']):
                            self.logger.info(f"Clicking tab: {tab_text}")
                            tab.click()
                            time.sleep(2)
                            break

                    self.logger.info("Waiting for certificates table to be visible in policy modal.")
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '/html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view/div/div[1]/mat-tab-group/div/mat-tab-body[2]/div/div/div[2]/div/div[3]/div/table'))
                    )
                    time.sleep(2)

                    self.logger.info(f"Inputting client number {self.cliente} in policy modal.")
                    client_input_number = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view/div/div[1]/mat-tab-group/div/mat-tab-body[2]/div/div/div[2]/div/div[1]/mat-form-field/div/div[1]/div//input[starts-with(@id, "mat-input-")]'))
                    )
                    client_input_number.send_keys(str(self.cliente))
                    time.sleep(2)

                    # Select client if option appears
                    try:
                        options = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_all_elements_located((By.XPATH, '/html/body/div[3]/div[3]/div/div/mat-option'))
                        )
                        for option in options:
                            option_label = option.find_element(By.XPATH, './/span/span/small')
                            if str(self.cliente) in option_label.text:
                                option.click()
                                time.sleep(2)
                                break
                    except Exception:
                        pass

                    # Wait for notification
                    try:
                        notification = WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="toast-container"]/app-toastr-custom-action'))
                        )
                        notification.click()
                        time.sleep(2)
                    except Exception:
                        pass

                    # Accept changes - /html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view/div/div[2]/div/button[1]
                    accept_policy_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div[2]/div/mat-dialog-container/app-dialog-private-policy-view/div/div[2]/div/button[1]'))
                    )
                    accept_policy_btn.click()
                    time.sleep(3)

                    # Click the accept button in the policy change resume modal - /html/body/div[3]/div[4]/div/mat-dialog-container/app-dialog-private-policy-change-resume/div/div[2]/div/button[1]
                    accept_resume_btn = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, '/html/body/div[3]/div[4]/div/mat-dialog-container/app-dialog-private-policy-change-resume/div/div[2]/div/button[1]'))
                    )
                    accept_resume_btn.click()
                    time.sleep(5)
                except Exception as e:
                    self.logger.error(f"Error updating policies on Multivia: {e}")
                    return False

                # Check for success notification
                try:
                    toast = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="toast-container"]/app-toastr-custom-action/div[1]/div/div[1]'))
                    )
                    toast_text = toast.text.strip().lower()
                    if "éxito" in toast_text or "success" in toast_text:
                        self.logger.info("Certificate assignment successful.")
                        return True
                    else:
                        self.logger.warning(f"Certificate assignment notification: {toast.text}")
                        return False
                except Exception as e:
                    self.logger.error(f"Could not find success notification: {e}")
                    return False

            except Exception as e:
                self.logger.error(f"Error during policy assignment process: {e}")
                return False

        except Exception as e:
            self.logger.error(f"Error during redtrust certificate upload process: {e}")
            return False
        finally:
            time.sleep(5)

    def update_certificate_modal(self) -> bool:
        try:
            # Wait for the certificate replace modal to appear
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-replace"))
            )
            time.sleep(2)

            try:
                # Add file
                # file_input = WebDriverWait(self.driver, 10).until(
                #     EC.presence_of_element_located((By.XPATH, "//input[@type='file' and contains(@class, 'mat-input-element') and @data-placeholder='Seleccione el archivo...' and not(@disabled)]"))
                # )
                # self.driver.execute_script("arguments[0].removeAttribute('readonly'); arguments[0].removeAttribute('disabled');", file_input)
                file_input = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-replace/div/div[1]/div[1]/mat-form-field/div/div[1]/div[1]/input"))
                )
                file_input.send_keys(self.certificate_path)
                time.sleep(2)

                # Add password
                password_input = WebDriverWait(self.driver, 10).until(
                    EC.visibility_of_element_located((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-replace/div/div[1]/div[2]/mat-form-field/div/div[1]/div[1]/input"))
                )
                password_input.send_keys(self.password)
                time.sleep(2)
            except Exception as e:
                self.logger.error(f"Error filling in certificate replace modal fields: {e}")
                return False

            # Click accept button
            accept_btn = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/div[4]/div[2]/div/mat-dialog-container/app-dialog-private-cert-replace/div/div[2]/div/button[1]"))
            )
            accept_btn.click()
            time.sleep(2)
            self.logger.info("Certificate replaced successfully in modal.")
            return True
        except Exception as e:
            self.logger.error(f"Error replacing certificate in modal: {e}")
            return False

    def fallback_method(self, credential:str):
        self.logger.info("Executing fallback method (BUSCANDO NIF).")
        try:
            nif_input = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "/html/body/app-root/div[1]/app-certificates/div[2]/mat-tab-group/div/mat-tab-body/div/app-private-certificates/div/div[1]/div[2]/div[2]/mat-form-field/div/div[1]/div[1]//input[starts-with(@id, 'mat-input-')]"))
            )
            nif_input.clear()
            time.sleep(2)
            nif_input.send_keys(credential)
            nif_input.send_keys(Keys.RETURN)
            time.sleep(5)

            rows = WebDriverWait(self.driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, '/html/body/app-root/div[1]/app-certificates/div[2]/mat-tab-group/div/mat-tab-body/div/app-private-certificates/div/div[2]/table/tbody/tr'))
            )

            for row in rows:
                td_cliente = row.find_element(By.XPATH, './/td[2]')
                if td_cliente.text.strip() == credential:
                    return row
        except Exception as e:
            self.logger.error(f"Error in fallback method: {e}")
            return None

    def run(self):
        try:
            cursor = self.db_connection.cursor()
            cursor.execute(f"SELECT nif FROM clientes c WHERE c.numerocliente={self.cliente}")
            row = cursor.fetchone()
            if row:
                self.logger.info(f"NIF for cliente {self.cliente}: {row[0]}")
                self.nif = row[0]
            else:
                self.logger.warning(f"No NIF found for cliente {self.cliente}")
                return False
            
            self.setup_driver()

            login = self.login()
            if not login:
                return False
            
            response = self.upload_certificate()
            return response
        except Exception as e:
            self.logger.error(f"An error occurred: {e}")
            return None
        finally:
            if self.driver is not None:
                self.driver.quit()

import requests
from tkinter import Tk, filedialog
if __name__ == "__main__":
    print("Seleccione el archivo de certificado (.pfx o .p12):")
    certificate_path = filedialog.askopenfilename(
        filetypes=[("Certificado PFX/P12", "*.pfx *.p12")]
    )

    if not certificate_path:
        print("No se seleccionó ningún archivo. Saliendo...")
        exit()

    # Input client and password
    # cliente = input("Ingrese el cliente: ")
    # password = input("Ingrese la contraseña: ")
    cliente = "42005"  # Replace with actual client
    password = "ASTEC0427"  # Replace with actual password

    loader = RedTrustCertificateLoader(
        cliente=cliente,
        password=password,
        certificate_path=certificate_path
    )
    loader.run()



# if __name__ == "__main__":
#     # Suppress the root Tkinter window
#     root = Tk()
#     root.withdraw()

#     # Open file dialog to select the certificate file
#     print("Seleccione el archivo de certificado (.pfx o .p12):")
#     certificate_path = filedialog.askopenfilename(
#         filetypes=[("Certificado PFX/P12", "*.pfx *.p12")]
#     )

#     if not certificate_path:
#         print("No se seleccionó ningún archivo. Saliendo...")
#         exit()

#     # Input client and password
#     # cliente = input("Ingrese el cliente: ")
#     # password = input("Ingrese la contraseña: ")
#     cliente = "42907"  # Replace with actual client
#     password = "12345"  # Replace with actual password

#     # Endpoint URL
#     url = "http://192.168.184.162:8008/api/certificados/upload-certificado"

#     # Prepare the request
#     with open(certificate_path, "rb") as cert_file:
#         files = {"certificado": (certificate_path, cert_file, "application/x-pkcs12")}
#         data = {"cliente": cliente, "password": password}

#         try:
#             # Make the POST request
#             response = requests.post(url, data=data, files=files)
#             response.raise_for_status()  # Raise an error for HTTP codes 4xx/5xx

#             # Print the response
#             print("Respuesta del servidor:")
#             print(response.json())
#         except requests.exceptions.RequestException as e:
#             print(f"Error al realizar la solicitud: {e}")

