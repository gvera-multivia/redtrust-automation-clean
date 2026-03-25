import time

# THIRD PARTY PACKAGES
import pyautogui
from typing import List
from pywinauto import Application, Desktop

# PERSONAL PACKAGES - UTILS
from app.utils.utils import WAIT_TIME, random_wait
import os
import sys


def automate_redtrust(certificates: List[str]) -> bool:
        """Automate the RedTrust process."""
        try:
            try:
                taskbar = Desktop(backend="uia").window(title="Barra de tareas", control_type="Pane")
                redtrust_button = taskbar.child_window(title="Redtrust", auto_id="NotifyItemIcon", control_type="Button")                                
                
            except Exception as e:
                print(f"⚠️ Error locating RedTrust icon: {e}")
                return False
            
            if redtrust_button and redtrust_button.exists():
                print("RedTrust button found. Starting automation...")
                
                redtrust_button.click_input(button='right')
                pyautogui.press('c')
                try:
                    time.sleep(WAIT_TIME['SHORT'])
                    print( "Logging into RedTrust...")
                    redtrust = Application(backend="uia").connect(title="RedTrust Agent")
                    redtrust_window = redtrust.window(title="RedTrust Agent")

                    user_field = redtrust_window.child_window(title="Login", control_type="Edit")
                    user_field.click_input()
                    user_field.type_keys("Informaticos@multivia")

                    time.sleep(WAIT_TIME['SHORT'])

                    password_field = redtrust_window.child_window(title="Contraseña:", control_type="Edit")
                    password_field.click_input()
                    password_field.type_keys("Informaticos")

                    accept_button = redtrust_window.child_window(auto_id="btnOk", control_type="Button")
                    accept_button.click_input()

                    time.sleep(WAIT_TIME['MEDIUM'])
                except Exception as e:
                    print(f"⚠️ Error during RedTrust login: {e}")
                    # return False
                    pass
                
                time.sleep(WAIT_TIME['MEDIUM'])
                redtrust_button.click_input(button='right')
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

                        for certificate_id in certificates:
                            try:
                                edit_field = redtrust_window.child_window(control_type="Edit")
                                edit_field.click_input()
                                edit_field.set_text("")
                                edit_field.type_keys(certificate_id)
                                pyautogui.press('space')
                                edit_field.type_keys('-')

                                listbox = redtrust_window.child_window(auto_id="certSelectList", control_type="List")
                                if not listbox.exists():
                                    print("Certificate list box not found.")
                                    raise Exception("Certificate list box not found.")
                                
                                certificate_items = listbox.children(control_type="CheckBox")
                                
                                if not certificate_items or len(list(certificate_items)) == 0:
                                    print(f"No certificates found matching ID: {certificate_id}")
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
                                            print(f"⚠️ No se encontró el CheckBox con título: {text}")

                                if not found:
                                    print(f"⚠️ Certificate with ID {certificate_id} not found.")
                                    # Add this code where the $SELECTION_PLACEHOLDER$ is located
                                    file_path = os.path.join(r"\\192.168.184.8\c$\Users\administrador\Documents\workspace\redtrust-automation\files", "certificate_errors.txt")
                                    with open(file_path, 'a') as f:
                                        f.write(f"{certificate_id}\n")
                                    raise Exception(f"Certificate with ID {certificate_id} not found.")
                            except Exception as e:
                                continue
                        
                        accept_button = redtrust_window.child_window(auto_id="btnOk", control_type="Button")
                        accept_button.click_input()
                        return True
                    except Exception as e:
                        print(f"⚠️ Attempt to select certificate failed: {e}")
                        cancel_button = redtrust_window.child_window(auto_id="btnCancel", control_type="Button")
                        cancel_button.click_input()          
                        
                    finally:
                        time.sleep(WAIT_TIME['MEDIUM'])
                        
                except Exception as e: 
                    print(f"⚠️ Error during RedTrust certificate selection: {e}")               
                    return False
                                
            else:
                print("RedTrust button not found.")
                return False
        except Exception as e:
            print(f"⚠️ Error automating RedTrust: {e}")
            return False
        

def find_window():
    """Find the window associated with the site."""
    try:
        start_time = time.time()
        while True:
            windows = Desktop(backend="uia").windows()
            for win in windows:
                if 'Cl@ve' in win.window_text():
                    window = win
                    window.set_focus()
                    print( f"Ventana encontrada")
                    return window

            if time.time() - start_time > 30:
                window = fallback()
                print( f"Timeout buscando ventana ")
                return None

            time.sleep(WAIT_TIME['SHORT'])
    except Exception as e:
        print( f"Error buscando ventana: {e}")
        return None

def handle_certificate(recipient_name:str) -> bool:
    try:
        time.sleep(WAIT_TIME['MEDIUM'])
        start_time = time.time()
        cert_found = False
        while time.time() < start_time + random_wait(wait_type='XXX_LONG', wait = False):
            try:
                window = find_window()
                if not window:
                    print( f"No se encontró la ventana del certificado para Cl@ve.")
                    random_wait(wait_type='MEDIUM', wait=True)
                    continue

                app = Application(backend="uia").connect(handle=window.handle)
                cert_window = app.window(handle=window.handle)

                if cert_window.exists():
                    cert_window.set_focus()
                    # custom_window = cert_window.child_window(title_re="(Seleccionar un certificado|Select a certificate|Elegir un certificado)", control_type="Custom")
                    custom_window = None
                    for ctype in ["Window", "Custom", "Pane"]:
                        try:
                            custom_window = cert_window.child_window(title_re="(Seleccionar un certificado|Select a certificate|Elegir un certificado)", control_type=ctype)
                            if custom_window.exists():
                                break
                        except Exception:
                            random_wait(wait_type='MEDIUM', wait=True)
                            continue
                    
                    if custom_window.exists():
                        # Navegar por los Pane hasta encontrar los DataItem de certificados
                        pane = custom_window.child_window(control_type="Pane", found_index=1)
                        # pane.print_control_identifiers()
                        if pane.exists():
                            # Buscar todos los DataItem (certificados)
                            for item in pane.descendants(control_type="DataItem"):
                                try:
                                    name = item.window_text().strip()
                                    if recipient_name.lower().strip() in name.lower():
                                        print( f"Seleccionando el certificado: {recipient_name.lower()}")
                                        item.click_input()
                                        cert_found = True
                                        break
                                except Exception as e:
                                    print( f"Error al procesar el certificado: {e}")
                                    continue
                                
                            if not cert_found:
                                print( f"Certificado no encontrado: {recipient_name}")                                
                                continue
                        else:
                            print( "No se encontró el contenedor de certificados (Pane).")
                            random_wait(wait_type='MEDIUM', wait=True)
                            continue
                    else:
                        print( "Ventana de selección de certificado no encontrada.")
                        random_wait(wait_type='MEDIUM', wait=True)

                        continue               
                else:
                    print( "Ventana de selección de certificado no encontrada.")
                    random_wait(wait_type='MEDIUM', wait=True)
                    continue

                accept_button = cert_window.child_window(title="Aceptar", control_type="Button")
                if accept_button.exists():
                    accept_button.click()

                    random_wait(wait_type='MEDIUM', wait=True)
                    accept_button = cert_window.child_window(title="Aceptar", control_type="Button")
                    if accept_button.exists():
                        accept_button.click()
                    return True
                else:
                    print( "Botón aceptar no encontrado.")
                    continue
            except Exception as e:
                print( f"Error accediendo a la ventana del certificado: {e}")
                continue
            finally:
                random_wait(wait_type='LONG', wait=True)
            
        if not cert_found:
            # Intentar pulsar "Cancelar" si no se encuentra el certificado y retornar False
            print( f"Certificado no encontrado tras varios intentos para {recipient_name}")
            # cert_window.print_control_identifiers()
            cancelar_button = cert_window.child_window(title="Cancelar", control_type="Button")
            if cancelar_button.exists():
                cancelar_button.click()

                time.sleep(WAIT_TIME['X_LONG'])
                for win in Desktop(backend="uia").windows():
                    if any(keyword in win.window_text() for keyword in ['Cl@ve', 'Seleccionar un certificado']):
                        win.set_focus()
                        cancelar_button.click()
                        print( f"Cancelando operación tras no encontrar certificado para {recipient_name}")
                        print("Certificado no encontrado, operación cancelada.")
                        break
                return False
            else:
                print( "Botón cancelar no encontrado.")
                fallback()
                return False
            
    except Exception as e:
        print( f"Error al manejar el certificado: {e}")
        return False

    
def fallback():
    """Fallback method to handle unexpected situations."""
    try:
        windows = Desktop(backend="uia").windows()
        for win in windows:
            if 'Google Chrome' in win.window_text():
                window = win
                window.set_focus()
                pyautogui.hotkey('alt', 'tab')  
                return window

    except Exception as e:
        pass


if __name__ == "__main__":
    
    if len(sys.argv) > 1:
        action = sys.argv[1]
        
        if action == "search":
            cert_id = "27388"
            if len(sys.argv) > 2:
                cert_id = sys.argv[2]
            print(f"Searching for certificate ID: {cert_id}")
            result = automate_redtrust([cert_id])
            print(f"RedTrust automation result: {result}")
            
        elif action == "select":
            recipient_name = "52178739L JORDI CUELLO (R: A62518121)"
            if len(sys.argv) > 2:
                recipient_name = '52178739L JORDI CUELLO (R: A62518121)'
            print(f"Selecting certificate for: {recipient_name}")
            result = handle_certificate(recipient_name)
            print(f"Certificate selection result: {result}")
        else:
            print("Unknown action. Use 'search' or 'select'")
    else:
        print("Usage:")
        print("  python redtrust_window_inspect.py search [cert_id]  - Search certificate in RedTrust")
        print("  python redtrust_window_inspect.py select [name]    - Select certificate in window")
        print("\nRunning default: search for cert_id 27388")
        result = automate_redtrust(["27388"])
        print(f"Result: {result}")