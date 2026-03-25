import time

# THIRD PARTY PACKAGES
import pyautogui
from typing import Union
from pywinauto import Application, Desktop

# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.utils.utils import WAIT_TIME
import os


class RedTrustManager:
    """Class to manage loading certificates for RedTrust."""

    def __init__(self, cliente:str, execution_id:str, credentials : dict, date: str, module:str, filename: str = None):
        self.usuario = credentials["usuario"]
        self.password = credentials["password"]
        self.cliente = cliente
        self.task_id = 'REDTRUST'
        self.date = date
        self.execution_id = execution_id
        self.logger = LoggerV2(
            execution_id=self.execution_id,
            module=module,
            class_name=self.__class__.__name__,
            log_dir=f"logs/{module.lower()}",
            filename=filename
        )

    def automate_redtrust(self, certificates: Union[str, list]) -> bool:
        """Automate the RedTrust process."""
        try:
            redtrust_button = self._locate_redtrust_icon()
            if redtrust_button and redtrust_button.exists():
                self.logger.debug(self.cliente, self.task_id, "Success", "RedTrust button found. Starting automation...")
                
                redtrust_button.click_input(button='right')
                pyautogui.press('c')
                self._login_redtrust()
                time.sleep(WAIT_TIME['MEDIUM'])
                redtrust_button.click_input(button='right')
                if isinstance(certificates, list) and len(certificates) > 1:
                    self._select_certificates(certificates)
                else:
                    self._select_certificate(certificates if isinstance(certificates, str) else certificates[0])
                return True
            else:
                self.logger.error(self.cliente, self.task_id, "Failure", "RedTrust button not found.")
                return False
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error automating RedTrust: {e}")
            return False
    
    def _locate_redtrust_icon(self):
        try:
            tray_window = Desktop(backend="uia").window(class_name="Shell_TrayWnd")
            # Try to find the Redtrust icon by its title (case-insensitive)
            redtrust_icon = tray_window.child_window(title_re="(?i)^Redtrust$", auto_id="NotifyItemIcon", control_type="Button")
            if redtrust_icon.exists():
                return redtrust_icon

            # Fallback: search all buttons for one with 'Redtrust' in the title
            for btn in tray_window.descendants(control_type="Button"):
                if hasattr(btn, "window_text") and "redtrust" in btn.window_text().lower():
                    return btn

            raise RuntimeError("RedTrust icon not found in the system tray.")
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error locating RedTrust icon: {e}")
            raise RuntimeError("Failed to locate the RedTrust icon.") from e    

    def _login_redtrust(self):
        """Log in to the RedTrust application."""
        try:
            time.sleep(WAIT_TIME['SHORT'])
            self.logger.debug(self.cliente, self.task_id, "Pending", "Logging into RedTrust...")

            redtrust = Application(backend="uia").connect(title="RedTrust Agent")
            redtrust_window = redtrust.window(title="RedTrust Agent")
            conectar_window = redtrust_window.child_window(title="Conectar", auto_id="frmLogin", control_type="Window")

            # Username field
            user_pane = conectar_window.child_window(title="Login", auto_id="txtUsername", control_type="Pane")
            user_edit = user_pane.child_window(control_type="Edit")
            user_edit.click_input()
            user_edit.set_text("")
            user_edit.type_keys(self.usuario, with_spaces=True)

            time.sleep(WAIT_TIME['SHORT'])

            # Password field
            pass_pane = conectar_window.child_window(title="Contraseña:", auto_id="txtPassword", control_type="Pane")
            pass_edit = pass_pane.child_window(control_type="Edit")
            pass_edit.click_input()
            pass_edit.set_text("")
            pass_edit.type_keys(self.password, with_spaces=True)

            # Accept button
            accept_button = conectar_window.child_window(title="Aceptar", auto_id="btnOk", control_type="Button")
            accept_button.click_input()

            time.sleep(WAIT_TIME['MEDIUM'])
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error during login: {e}")
            pass

    # Private method
    def _select_certificate(self, certificate_id):
        """Select a certificate in the RedTrust application."""
        try:
            time.sleep(WAIT_TIME['SHORT'])
            pyautogui.press('c')
            pyautogui.press('enter')

            start_time = time.time()
            redtrust_window = None

            while time.time() - start_time < 60:
                try:
                    redtrust = Application(backend="uia").connect(title="RedTrust Agent")
                    redtrust_window = redtrust.window(title="RedTrust Agent")
                    if redtrust_window.exists():
                        break
                except Exception:
                    pass
                time.sleep(WAIT_TIME['SHORT'])

            if redtrust_window is None:
                raise Exception("Failed to connect to RedTrust Agent within the timeout period.")

            try:
                redtrust_window.set_focus()
                unselect_all = redtrust_window.child_window(auto_id="selectAllToggle", control_type="CheckBox")
                unselect_all.click_input()
                unselect_all.click_input()

                see_all = redtrust_window.child_window(title="Todos", auto_id="radioall", control_type="RadioButton")
                see_all.click_input()

                edit_field = redtrust_window.child_window(control_type="Edit")
                edit_field.click_input()
                edit_field.set_text("")
                edit_field.type_keys(certificate_id)
                pyautogui.press('space')
                edit_field.type_keys('-')

                listbox = redtrust_window.child_window(auto_id="certSelectList", control_type="List")
                if not listbox.exists():
                    self.logger.error(self.cliente, self.task_id, "Failure", "Certificate list box not found.")
                    raise Exception("Certificate list box not found.")
                
                certificate_items = listbox.children(control_type="CheckBox")
                
                if not certificate_items or len(list(certificate_items)) == 0:
                    self.logger.error(self.cliente, self.task_id, "Failure", f"No certificates found matching ID: {certificate_id}")
                    # Add this code where the $SELECTION_PLACEHOLDER$ is located
                    file_path = os.path.join(r"\\192.168.184.8\c$\Users\administrador\Documents\workspace\redtrust-automation\files", "certificate_errors.txt")
                    with open(file_path, 'a') as f:
                        f.write(f"{certificate_id}\n")
                    raise Exception(f"No certificates found matching ID: {certificate_id}")
                
                found = False
                for index, checkbox in enumerate(certificate_items, start=1):
                    text = checkbox.window_text()
                    if text.split('-')[0].strip() == str(certificate_id).strip():
                        cert_checkbox = listbox.child_window(title_re=f".*{text[:20]}.*", control_type="CheckBox")

                        if cert_checkbox.exists(): 
                            found = True
                            if index == 1:
                                cert_checkbox.click_input()
                            else:
                                cert_checkbox.click_input(double=True)                                                   
                            break
                        else:
                            self.logger.info(self.cliente, self.task_id, "Failure", f"⚠️ No se encontró el CheckBox con título: {text}")

                if not found:
                    self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Certificate with ID {certificate_id} not found.")
                    # Add this code where the $SELECTION_PLACEHOLDER$ is located
                    file_path = os.path.join(r"\\192.168.184.8\c$\Users\administrador\Documents\workspace\redtrust-automation\files", "certificate_errors.txt")
                    with open(file_path, 'a') as f:
                        f.write(f"{certificate_id}\n")
                    raise Exception(f"Certificate with ID {certificate_id} not found.")
                
                accept_button = redtrust_window.child_window(auto_id="btnOk", control_type="Button")
                accept_button.click_input()
                return
            except Exception as e:
                self.logger.warning(self.cliente, self.task_id, "Failure", f"⚠️ Attempt to select certificate failed: {e}")
                cancel_button = redtrust_window.child_window(auto_id="btnCancel", control_type="Button")
                cancel_button.click_input()          

                raise
                
            finally:
                time.sleep(WAIT_TIME['MEDIUM'])
                
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error selecting certificate {certificate_id}: {e}")
            raise

    def _select_certificates(self, certificates:list):
        """Select more than one certificate in the RedTrust application."""
        try:
            time.sleep(WAIT_TIME['SHORT'])
            pyautogui.press('c')
            pyautogui.press('enter')

            start_time = time.time()
            redtrust_window = None

            while time.time() - start_time < 60:
                try:
                    redtrust = Application(backend="uia").connect(title="RedTrust Agent")
                    redtrust_window = redtrust.window(title="RedTrust Agent")
                    if redtrust_window.exists():
                        break
                except Exception:
                    pass
                time.sleep(WAIT_TIME['SHORT'])

            if redtrust_window is None:
                raise Exception("Failed to connect to RedTrust Agent within the timeout period.")

            cert_not_found = 0
            try:
                redtrust_window.set_focus()
                unselect_all = redtrust_window.child_window(auto_id="selectAllToggle", control_type="CheckBox")
                unselect_all.click_input()
                unselect_all.click_input()

                see_all = redtrust_window.child_window(title="Todos", auto_id="radioall", control_type="RadioButton")
                see_all.click_input()

                for certificate_id in certificates:
                    edit_field = redtrust_window.child_window(control_type="Edit")
                    edit_field.click_input()
                    edit_field.set_text("")
                    edit_field.type_keys(certificate_id)
                    pyautogui.press('space')
                    edit_field.type_keys('-')


                    listbox = redtrust_window.child_window(auto_id="certSelectList", control_type="List")
                    if not listbox.exists():
                        self.logger.error(self.cliente, self.task_id, "Failure", "Certificate list box not found.")
                        continue

                    certificate_items = listbox.children(control_type="CheckBox")
                
                    if not certificate_items or len(list(certificate_items)) == 0:
                        self.logger.error(self.cliente, self.task_id, "Failure", f"No certificates found matching ID: {certificate_id}")
                        # Add this code where the $SELECTION_PLACEHOLDER$ is located
                        file_path = os.path.join(r"\\192.168.184.8\c$\Users\administrador\Documents\workspace\redtrust-automation\files", "certificate_errors.txt")
                        with open(file_path, 'a') as f:
                            f.write(f"{certificate_id}\n")
                        continue
                    
                    found = False
                    for index, checkbox in enumerate(certificate_items, start=1):
                        text = checkbox.window_text()
                        if text.split('-')[0].strip() == str(certificate_id).strip():
                            cert_checkbox = listbox.child_window(title_re=f".*{text[:20]}.*", control_type="CheckBox")

                            if cert_checkbox.exists(): 
                                found = True
                                if index == 1:
                                    cert_checkbox.click_input()
                                else:
                                    cert_checkbox.click_input(double=True)                                                   
                                break
                            else:
                                self.logger.info(self.cliente, self.task_id, "Failure", f"⚠️ No se encontró el CheckBox con título: {text}")

                    if not found:
                        cert_not_found += 1
                        self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Certificate with ID {certificate_id} not found.")
                        # Add this code where the $SELECTION_PLACEHOLDER$ is located
                        file_path = os.path.join(r"\\192.168.184.8\c$\Users\administrador\Documents\workspace\redtrust-automation\files", "certificate_errors.txt")
                        with open(file_path, 'a') as f:
                            f.write(f"{certificate_id}\n")
                        continue
                
                if cert_not_found == len(certificates):
                    self.logger.error(self.cliente, self.task_id, "Failure", "⚠️ None of the specified certificates were found.")
                    raise Exception("None of the specified certificates were found.")

                accept_button = redtrust_window.child_window(auto_id="btnOk", control_type="Button")
                accept_button.click_input()
                return
            except Exception as e:
                self.logger.warning(self.cliente, self.task_id, "Failure", f"⚠️ Attempt to select certificates failed: {e}")
                redtrust_window.child_window(auto_id="btnCancel", control_type="Button").click_input()
                raise
            finally:
                time.sleep(WAIT_TIME['MEDIUM'])
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"⚠️ Error selecting certificate {certificate_id}: {e}")
            raise


if __name__ == "__main__":
    test_credentials = {
        "usuario": "ADMartinez@multivia",
        "password": "ADMartinez"
    }

    redtrust_manager = RedTrustManager(
        cliente="Test Client",                
        credentials=test_credentials, 
        execution_id="TEST_EXEC_001",
        date="20251217", 
        module="Playground",
        filename="playground"
    )
    
    # result = redtrust_manager.automate_redtrust("41421")
    # print("Automation result:", result)

    list_clients = [13674,28364,43020,43473]

    for client in list_clients:
        print("Processing client:", client)
        result = redtrust_manager.automate_redtrust(str(client))
        print("Automation result for client", client, ":", result)


    

