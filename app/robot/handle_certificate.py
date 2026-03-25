import time
from uuid import uuid4

# THIRD PARTY PACKAGES
from pywinauto import Application, Desktop
import pyautogui

# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.utils.utils import WAIT_TIME, random_wait

# Tiempo máximo de reintento en segundos
TIMETRYING = 10

# 🎯 Diccionario de portales y sus ventanas asociadas
SITES = {
    "andalucía":  "Cl@ve", # or  "Sistema de Notificaciones Telemáticas - Notific@"
    "asturias": "Cl@ve", # or "Consultar sus notificaciones",
    "agencia tributaria de catalunya": "Inici de sessió",
    "badajoz": "Cl@ve", #"OAR - Accediendo",
    "baleares": "Cl@ve",
    "burgos": "Buzón de notificaciones",
    "castilla la mancha": "Cl@ve",
    "castilla y león": "Cl@ve",#"NOTIFICA | Inicio",
    "ceuta": "Cl@ve",
    "comunidad valenciana": "Comunicacions - Generalitat Valenciana",
    "la rioja": "Sistema Central de Autenticación del Gobierno de La Rioja",
    "madrid": "Acceso unificado a las aplicaciones de la Comunidad de Madrid", 
    "melilla": "Notificaciones single", #"Cl@ve"
    "pais vasco": "Delegated Authentication",
    "enotum": "Inici de sessió",
    "mahon": "Inici de sessió",
    "dev": "DGT Acceso", # "sede.dgt.gob.es",
    "dgt": "Cl@ve",
    "dehù": "Cl@ve",
    "oficina virtual ayuntamiento terrassa": "Inici de sessió",
    "xaloc": "Inici de sessió",
    "migjorn gran": "Carpeta Ciutadana",
    "ayuntamiento de málaga": "Mi Carpeta",
    "seu judicial gencat": "Inici de sessió",
}

class CertificateManager:
    def __init__(self, cliente: str, task_id:str, execution_id:str, sede : str, date: str, module:str, filename: str = None):
        self.sede = sede
        self.start_time = time.time()
        self.window = None
        self.cliente = cliente
        self.task_id = task_id
        self.date = date
        self.logger = LoggerV2(
            execution_id=execution_id,
            module=module,
            class_name=self.__class__.__name__,
            log_dir=f"logs/{module.lower()}",
            filename=filename
        )


    def find_window(self):
        """Find the window associated with the site."""
        try:
            while True:
                windows = Desktop(backend="uia").windows()
                for win in windows:
                    if SITES[self.sede] in win.window_text():
                        self.window = win
                        self.window.set_focus()
                        self.logger.info(self.cliente, self.task_id, "Success", f"Ventana encontrada para {self.sede}")
                        return True

                if time.time() - self.start_time > TIMETRYING:
                    self.fallback()
                    self.logger.error(self.cliente, self.task_id, "Failure", f"Timeout buscando ventana para {self.sede}")
                    return False

                time.sleep(WAIT_TIME['SHORT'])
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"Error buscando ventana: {e}")
            return False
    
    def handle_certificate(self, recipient_name:str) -> bool:
        try:
            time.sleep(WAIT_TIME['MEDIUM'])
            self.start_time = time.time()
            cert_found = False
            while time.time() < self.start_time + random_wait(wait_type='XXX_LONG', wait = False):
                try:
                    if not self.find_window():
                        self.logger.error(self.cliente, self.task_id, "Failure", f"No se encontró la ventana del certificado para {self.sede}.")
                        random_wait(wait_type='MEDIUM', wait=True)
                        continue

                    app = Application(backend="uia").connect(handle=self.window.handle)
                    cert_window = app.window(handle=self.window.handle)

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
                                            self.logger.info(self.cliente, self.task_id, "Success", f"Seleccionando el certificado: {recipient_name.lower()}")
                                            item.click_input()
                                            cert_found = True
                                            break
                                    except Exception as e:
                                        self.logger.error(self.cliente, self.task_id, "Failure", f"Error al procesar el certificado: {e}")
                                        continue
                                    
                                if not cert_found:
                                    self.logger.error(self.cliente, self.task_id, "Failure", f"Certificado no encontrado: {recipient_name}")                                
                                    continue
                            else:
                                self.logger.error(self.cliente, self.task_id, "Failure", "No se encontró el contenedor de certificados (Pane).")
                                random_wait(wait_type='MEDIUM', wait=True)
                                continue
                        else:
                            self.logger.error(self.cliente, self.task_id, "Failure", "Ventana de selección de certificado no encontrada.")
                            random_wait(wait_type='MEDIUM', wait=True)

                            continue               
                    else:
                        self.logger.error(self.cliente, self.task_id, "Failure", "Ventana de selección de certificado no encontrada.")
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
                        self.logger.error(self.cliente, self.task_id, "Failure", "Botón aceptar no encontrado.")
                        continue
                except Exception as e:
                    self.logger.error(self.cliente, self.task_id, "Failure", f"Error accediendo a la ventana del certificado: {e}")
                    continue
                finally:
                    random_wait(wait_type='LONG', wait=True)
                
            if not cert_found:
                # Intentar pulsar "Cancelar" si no se encuentra el certificado y retornar False
                self.logger.error(self.cliente, self.task_id, "Failure", f"Certificado no encontrado tras varios intentos para {recipient_name}")
                # cert_window.print_control_identifiers()
                cancelar_button = cert_window.child_window(title="Cancelar", control_type="Button")
                if cancelar_button.exists():
                    cancelar_button.click()

                    time.sleep(WAIT_TIME['X_LONG'])
                    for win in Desktop(backend="uia").windows():
                        if any(keyword in win.window_text() for keyword in [SITES[self.sede], 'Seleccionar un certificado']):
                            win.set_focus()
                            cancelar_button.click()
                            self.logger.info(self.cliente, self.task_id, "Failure", f"Cancelando operación tras no encontrar certificado para {recipient_name}")
                            print("Certificado no encontrado, operación cancelada.")
                            break
                    return False
                else:
                    self.logger.error(self.cliente, self.task_id, "Failure", "Botón cancelar no encontrado.")
                    self.fallback()
                    return False
                
        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"Error al manejar el certificado: {e}")
            return False
        
    
    def fallback(self):
        """Fallback method to handle unexpected situations."""
        try:
            windows = Desktop(backend="uia").windows()
            for win in windows:
                if 'Google Chrome' in win.window_text():
                    self.window = win
                    self.window.set_focus()
                    pyautogui.hotkey('alt', 'tab')  

        except Exception as e:
            self.logger.error(self.cliente, self.task_id, "Failure", f"Error in fallback method: {e}")

if __name__ == "__main__":
    cliente = "HandleCertificateClient"
    task_id = "task_001"
    sede = "migjorn gran"
    recipient_name = "40989634T RAFAEL ARAQUE JAENES (R: B63315501)"
    date = time.strftime("%Y-%m-%d")
    module = "Playground"

    if sede == "migjorn gran":
        manager = CertificateManager(
            cliente=cliente, 
            task_id=task_id, 
            execution_id=str(uuid4()),
            sede=sede, 
            date=date, 
            module=module)
        result = manager.handle_certificate(recipient_name)
        print("Success" if result else "Failure")
    else:
        print(f"Sede '{sede}' no es 'migjorn gran'. No se realiza ninguna acción.")