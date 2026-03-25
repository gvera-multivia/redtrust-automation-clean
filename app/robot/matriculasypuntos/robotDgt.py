from queue import Queue
import shutil
import time
import unicodedata
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import uuid
import tempfile
from app.models.database_models import AlertasExtraidas, InformesDgtAutomatizaciones, MatriculasExtraidas, SancionesExtraidas
from app.utils.setup import WebDriverSetup
from app.utils.utils import random_wait
import logging
from datetime import datetime
import re

class RobotDgt:
    def __init__(self, cliente: str, task_id: str, date: str, execution_id:str, log_queue:Queue, module="MatriculasyPuntos" ):
        self.driver = None
        self.cliente = cliente
        self.task_id = task_id
        self.execution_id = execution_id    
        self.module = module
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.cliente = cliente
        self.task_id = task_id
        self.date = date
        self.log_queue = log_queue
        self.sede = 'dgt'
    
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

    def login(self):
        try:
            WebDriverWait(self.driver, random_wait('X_LONG')).until(
                EC.element_to_be_clickable((By.XPATH, '//*[@id="ID_main"]/div[2]/div/div/div/article[2]/div[4]/button'))
            ).click()
            self._log(logging.INFO, self.task_id, "Success", "Botón de inicio de sesión clicado correctamente")
        except Exception:
            self._log(logging.ERROR, self.task_id, "Failure", "No se pudo encontrar el botón de inicio de sesión")

    def get_matriculas(self, informe_id: str) -> dict | None:  
        matriculas = {
            "fecha_extraccion": time.strftime("%Y-%d-%m %H:%M:%S"),
            "vehiculos": [], 
            "alertas": []
        }
        try:
            try:
                WebDriverWait(self.driver, random_wait('X_LONG')).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="cconsent-bar"]/div/div[2]/div/button[2]'))
                ).click()
                self._log(logging.INFO, self.task_id, "Success", "Banner de cookies cerrado correctamente")
            except Exception:
                self._log(logging.WARNING, self.task_id, "Pending", "No se encontró el banner de cookies o ya estaba cerrado")

            for xpath, msg in [
                ('//*[@id="error"]', "Elemento de error detectado en la página."),
                ('//*[@id="main-frame-error"]', "Frame de error detectado en la página.")
            ]:
                try:
                    el = WebDriverWait(self.driver, random_wait('MEDIUM')).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    if el and el.is_displayed():
                        self._log(logging.ERROR, self.task_id, "Failure", msg)
                        return None
                except Exception:
                    pass

            vehiculos_count = 0
            start_retry = time.time()
            while time.time() - start_retry < 60:
                try:
                    random_wait('LONG', wait=True)
                    vehiculos_btn = WebDriverWait(self.driver, random_wait('X_LONG')).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="showVehiculos"]'))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", vehiculos_btn)
                    WebDriverWait(self.driver, random_wait('X_LONG')).until(EC.element_to_be_clickable((By.XPATH, '//*[@id="showVehiculos"]')))
                    btn_text = vehiculos_btn.text.strip()
                    if btn_text.isdigit():
                        vehiculos_count = int(btn_text)
                        if vehiculos_count == 0:
                            self._log(logging.ERROR, self.task_id, "Failure", "No se han encontrado vehículos para el cliente.")
                            return matriculas
                        self._log(logging.INFO, self.task_id, "Success", f"Cantidad de vehículos detectados: {vehiculos_count}")
                        break
                    elif btn_text == "Loading...":
                        self._log(logging.WARNING, self.task_id, "Pending", "El botón de vehículos está cargando. Reintentando...")
                        self.driver.refresh()
                    else:
                        self._log(logging.WARNING, self.task_id, "Pending", "El texto del botón de vehículos no es el esperado. Reintentando...")
                        self.driver.refresh()
                except Exception as e:
                    e_str = str(e)
                    stacktrace_index = e_str.find('Stacktrace')
                    if stacktrace_index != -1:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Intento fallido: {e_str[:stacktrace_index + len('Stacktrace:')]}")
                    else:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Intento fallido: {e_str}")
                    random_wait('SHORT', wait=True)

            if vehiculos_count == 0:
                return matriculas

            self.driver.get("https://sede.dgt.gob.es/es/mi_dgt/mis-vehiculos/")

            if vehiculos_count <= 20:
                try:
                    try:
                        Select(WebDriverWait(self.driver, random_wait('X_LONG')).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="DataTables_Table_0_length"]/label/select'))
                        )).select_by_value("100")
                        self._log(logging.INFO, self.task_id, "Success", "Selector de filas de la tabla ajustado a 100")
                    except Exception:
                        self._log(logging.WARNING, self.task_id, "Pending", "No se pudo ajustar el selector de filas de la tabla")

                    page_source = self.driver.page_source
                    soup = BeautifulSoup(page_source, "html.parser")
                    table = soup.find("table", {"id": "DataTables_Table_0"})
                    if not table:
                        self._log(logging.ERROR, self.task_id, "Failure", "No se ha encontrado la tabla de vehículos.")
                        return None
                    rows = table.find("tbody").find_all("tr")
                    for row in rows:
                        cols = row.find_all("td")
                        if not cols:
                            continue
                        matricula = cols[0].get_text(strip=True)
                        if not matricula:
                            continue
                        try:
                            data = self.driver.execute_async_script("""
                                const url = arguments[0];
                                const callback = arguments[1];
                                fetch(url)
                                    .then(response => response.json())
                                    .then(data => callback(data))
                                    .catch(error => callback({'error': error.toString()}));
                            """, f"https://sede.dgt.gob.es/system/modules/es.trafico.dgt.sedeV5/functions/mi_dgt/componentes/service_atex_vehiculo.jsp?matricula={matricula}")
                            if data and 'detallevehiculo' in data:
                                try:                                 
                                    detalle = data.get("detallevehiculo", {})
                                    
                                    # map common keys from detallevehiculo to MatriculasExtraidas fields
                                    matricula_extraida = MatriculasExtraidas(
                                        id=uuid.uuid4(),
                                        informe_id=informe_id,  # placeholder; replace with real informe id when available
                                        matricula=detalle.get("matricula") or matricula,
                                        matriculacion=(
                                            (
                                                datetime.strptime(detalle.get("matriculacion"), "%Y-%m-%d %H:%M:%S")
                                                if "-" in detalle.get("matriculacion")
                                                else datetime.strptime(detalle.get("matriculacion"), "%d/%m/%Y")
                                            )
                                            if detalle.get("matriculacion") else None
                                        ),
                                        marca=detalle.get("marca"),
                                        modelo=detalle.get("modelo"),
                                        combustible=detalle.get("combustible") or detalle.get("carburante"),                                        
                                        created_at=datetime.now(),
                                        updated_at=None,
                                    )

                                    matriculas["vehiculos"].append(matricula_extraida)

                                    # if  'avisos' in detalle and detalle['avisos'] and len(detalle['avisos']) > 0:
                                    #     for aviso in detalle['avisos']:
                                    #         texto_alerta = aviso
                                    #         matriculas["alertas"].append(
                                    #             AlertasExtraidas(
                                    #                 id=uuid.uuid4(),
                                    #                 matricula_id=matricula_extraida.id,
                                    #                 alertas_vehiculo=texto_alerta,
                                    #                 created_at=datetime.now(),
                                    #             )
                                    #         )
                                    #         self._log(logging.DEBUG, self.task_id, "Pending", f"Alerta encontrada para matrícula {matricula}: {texto_alerta}")


                                except Exception as exc:
                                    self._log(logging.WARNING, self.task_id, "Pending", f"No se pudo inicializar MatriculasExtraidas para {matricula}: {exc}")

                                self._log(logging.INFO, self.task_id, "Success", f"Detalle de vehículo obtenido para matrícula {matricula}")
                            else:
                                self._log(logging.WARNING, self.task_id, "Pending", f"No se ha encontrado 'detallevehiculo' para la matrícula {matricula}")
                        except Exception as e:
                            self._log(logging.ERROR, self.task_id, "Failure", f"Error obteniendo datos para la matrícula {matricula}: {e}")
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, "Failure", f"Error leyendo las matrículas del cliente: {e}")
                    return None

            else:
                try:
                    page_source = self.driver.page_source
                    soup = BeautifulSoup(page_source, "html.parser")
                    select = soup.find("select", {"id": "listaMatricula"})
                    if not select:
                        self._log(logging.ERROR, self.task_id, "Failure", "No se ha encontrado el selector de matrículas.")
                        return matriculas
                    options = select.find_all("option")[1:]
                    for option in options:
                        matricula = option.get("value")
                        if not matricula:
                            continue
                        try:
                            data = self.driver.execute_async_script("""
                                const url = arguments[0];
                                const callback = arguments[1];
                                fetch(url)
                                    .then(response => response.json())
                                    .then(data => callback(data))
                                    .catch(error => callback({'error': error.toString()}));
                            """, f"https://sede.dgt.gob.es/system/modules/es.trafico.dgt.sedeV5/functions/mi_dgt/componentes/service_atex_vehiculo.jsp?matricula={matricula}")
                            if data and 'detallevehiculo' in data:
                                try:                                 
                                    detalle = data.get("detallevehiculo", {})

                                    # map common keys from detallevehiculo to MatriculasExtraidas fields
                                    matricula_extraida = MatriculasExtraidas(
                                        id=uuid.uuid4(),
                                        informe_id=informe_id,  # placeholder; replace with real informe id when available
                                        matricula=detalle.get("matricula") or matricula,
                                        matriculacion=(
                                            (
                                                datetime.strptime(detalle.get("matriculacion"), "%Y-%m-%d %H:%M:%S")
                                                if "-" in detalle.get("matriculacion")
                                                else datetime.strptime(detalle.get("matriculacion"), "%d/%m/%Y")
                                            )
                                            if detalle.get("matriculacion") else None
                                        ),
                                        marca=detalle.get("marca"),
                                        modelo=detalle.get("modelo"),
                                        combustible=detalle.get("combustible") or detalle.get("carburante"),                                        
                                        created_at=datetime.now(),
                                        updated_at=None,
                                    )

                                    matriculas["vehiculos"].append(matricula_extraida)

                                    # if  'avisos' in detalle and detalle['avisos'] and len(detalle['avisos']) > 0:
                                    #     for aviso in detalle['avisos']:
                                    #         texto_alerta = aviso
                                    #         matriculas["alertas"].append(
                                    #             AlertasExtraidas(
                                    #                 id=uuid.uuid4(),
                                    #                 matricula_id=matricula_extraida.id,
                                    #                 alertas_vehiculo=texto_alerta,
                                    #                 created_at=datetime.now(),
                                    #             )
                                    #         )
                                    #         self._log(logging.DEBUG, self.task_id, "Pending", f"Alerta encontrada para matrícula {matricula}: {texto_alerta}")

                                except Exception as exc:
                                    self._log(logging.WARNING, self.task_id, "Pending", f"No se pudo inicializar MatriculasExtraidas para {matricula}: {exc}")
                                    
                                self._log(logging.INFO, self.task_id, "Success", f"Detalle de vehículo obtenido para matrícula {matricula}")
                            else:
                                self._log(logging.WARNING, self.task_id, "Pending", f"No se ha encontrado 'detallevehiculo' para la matrícula {matricula}")
                        except Exception as e:
                            self._log(logging.ERROR, self.task_id, "Failure", f"Error obteniendo datos para la matrícula {matricula}: {e}")
                except Exception as e:
                    self._log(logging.ERROR, self.task_id, "Failure", f"Error extrayendo datos de vehículos: {e}")
                    return None

            for index, vehiculo in enumerate(matriculas["vehiculos"], start=1):
                try:
                    matricula = getattr(vehiculo, "matricula", None)
                    if not matricula:
                        continue
                    self.driver.get(f"https://sede.dgt.gob.es/es/mi_dgt/mis-vehiculos/detalle-vehiculo/?matricula={matricula}&entidad=usuario")
                    random_wait('SHORT', wait=True)
                    detalle_page_source = self.driver.page_source
                    detalle_soup = BeautifulSoup(detalle_page_source, "html.parser")


                    columna1 = detalle_soup.find('div', {'id': 'columna1'})
                    divs = columna1.find_all('div', recursive=False)[1].find_all('div', recursive=False)                    

                    for div in divs:   
                        if 'alert' in div.get('class', []):
                            try:
                                # Extraer elementos tipo lista (ol/ul > li)
                                list_items = div.select('ol > li, ul > li')
                                if list_items:
                                    for li in list_items:
                                        texto_alerta = li.get_text(strip=True)
                                        if not texto_alerta:
                                            continue
                                        matriculas["alertas"].append(
                                            AlertasExtraidas(
                                                id=uuid.uuid4(),
                                                matricula_id=vehiculo.id,
                                                alertas_vehiculo=texto_alerta,
                                                created_at=datetime.now(),
                                            )
                                        )
                                        self._log(logging.DEBUG, self.task_id, "Pending", f"Alerta encontrada (li) para matrícula {matricula}: {texto_alerta}")
                                
                            except Exception as e:
                                self._log(logging.WARNING, self.task_id, "Pending", f"Error extrayendo alertas desde un div alert para {matricula}: {e}")


                        if 'fondo_gris' in div.get('class', []):
                            row_div = div.find('div', class_='row')
                            if row_div:
                                serv_containers = row_div.find_all('div', class_='col serv-container')
                                for serv_container in serv_containers:
                                    key = None

                                    h4 = serv_container.find('h4', class_='col subtitle')
                                    if h4:
                                        key = h4.get_text(strip=True)
                                        key = key.lower()
                                        key = ''.join(
                                            c for c in unicodedata.normalize('NFD', key)
                                            if unicodedata.category(c) != 'Mn'
                                        )
                                        key = key.replace(' ', '_')
                                        key = key.replace('(', '').replace(')', '')

                                    self._log(logging.DEBUG, self.task_id, "Pending", f"Procesando clave: {key} para la matrícula {matricula}")

                                    if key == "distintivo_ambiental":
                                        a_tag = serv_container.find('p').find('a')
                                        if a_tag and a_tag.has_attr('href'):
                                            href = a_tag['href']
                                            etiqueta = href.rstrip('/').split('/')[-1]
                                            vehiculo.distintivo_ambiental = etiqueta
                                    elif key in ["descargar", "carburante"]:
                                        continue
                                    elif key:
                                        values = []
                                        for p in serv_container.find_all('p'):
                                            values.append(p.get_text(strip=True))
                                        if not values:
                                            license_div = serv_container.find('div', class_='license')
                                            if license_div:
                                                text = license_div.get_text(strip=True)
                                                if text:
                                                    values.append(text)
                                        if not values:
                                            for d in serv_container.find_all('div'):
                                                text = d.get_text(strip=True)
                                                if text:
                                                    values.append(text)
                                        value = ' '.join(values)

                                        if key == "cilinidrada_cm":
                                            try:
                                                value = float(value)
                                            except ValueError:
                                                value = None
                                        elif key == "km_ultima_itv":
                                            try:
                                                value = int(value)
                                            except ValueError:
                                                value = None
                                        elif key == "direccion":
                                            value = ' '.join(value.split())

                                        
                                        if key in vehiculo.__fields__:
                                            vehiculo.__setattr__(key, value)
                                        else:
                                            self._log(logging.WARNING, self.task_id, "Pending", f"La clave {key} no existe en el modelo MatriculasExtraidas")
                                            continue
                                        self._log(logging.DEBUG, self.task_id, "Success", f"Detalle {key} extraído para matrícula {matricula}")

                except Exception as e:
                    self._log(logging.ERROR, self.task_id, "Failure", f"Error procesando el detalle del vehículo {getattr(vehiculo, 'matricula', '')}: {e}")
                    continue
                finally:
                    current_mat = getattr(vehiculo, 'matricula', '')
                    self._log(logging.INFO, self.task_id, "Success", f"Detalle del vehículo procesado para matrícula {current_mat}. Matriculas procesadas hasta ahora: {index}/{len(matriculas['vehiculos'])}")
                    
            self._log(logging.INFO, self.task_id, "Success", f"Extracción de matrículas finalizada para el cliente {self.cliente}")
            return matriculas

        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"Error en el proceso de recuperación de matrículas: {e}")
            return None     

    def get_puntos(self,  informe_id: str) -> dict | None:
        try:
            self.driver.get("https://sede.dgt.gob.es/es/permisos-de-conducir/permiso-por-puntos/consulta-de-puntos/")
            try:
                try:
                    WebDriverWait(self.driver, random_wait('X_LONG')).until(
                        EC.element_to_be_clickable((By.XPATH, '//*[@id="columna1"]/div[1]/div/div/div[1]/a'))
                    ).click()
                    self.login()
                except Exception as e:
                    self._log(logging.WARNING, self.task_id, "Pending", f"No se pudo hacer clic en el enlace de puntos: {e}")

                try:
                    try:
                        self.driver.switch_to.window(self.driver.window_handles[-1])
                    except Exception as e:
                        self._log(logging.ERROR, self.task_id, "Failure", f"Error al cambiar a la nueva ventana: {e}")

                    WebDriverWait(self.driver, random_wait('XX_LONG')).until(
                        EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'frmSaldoPuntos')]"))
                    ).is_displayed()

                    try:
                        message = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="lblMsgError"]'))
                        )
                        if message:
                            self._log(logging.ERROR, self.task_id, "Failure", message.text.strip())
                            return None
                    except Exception:
                        pass

                    try:
                        error_frame = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.presence_of_element_located((By.XPATH, '//*[@id="main-frame-error"]'))
                        )
                        if error_frame and error_frame.is_displayed():
                            self._log(logging.ERROR, self.task_id, "Failure", "Error frame detected on the page.")
                            return None
                    except Exception:
                        pass

                    try:
                        nif = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.visibility_of_element_located((By.ID, 'frmSaldoPuntos:txtNIF'))
                        ).text.strip()
                    except Exception:
                        self._log(logging.WARNING, self.task_id, "Pending", "Error al obtener el NIF")
                        nif = ""

                    try:
                        name = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.visibility_of_element_located((By.ID, 'frmSaldoPuntos:txtNombre'))
                        ).text.strip()
                    except Exception:
                        self._log(logging.WARNING, self.task_id, "Pending", "Error al obtener el nombre")
                        name = ""

                    try:
                        surname1 = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.visibility_of_element_located((By.ID, 'frmSaldoPuntos:txtApellido1'))
                        ).text.strip()
                    except Exception:
                        self._log(logging.WARNING, self.task_id, "Pending", "Error al obtener el primer apellido")
                        surname1 = ""

                    try:
                        surname2 = WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.visibility_of_element_located((By.ID, 'frmSaldoPuntos:txtApellido2'))
                        ).text.strip()
                    except Exception:
                        self._log(logging.WARNING, self.task_id, "Pending", "Error al obtener el segundo apellido")
                        surname2 = ""

                    fullname = f"{name} {surname1} {surname2}"
                    points_balance = WebDriverWait(self.driver, random_wait('LONG')).until(
                        EC.visibility_of_element_located((By.ID, 'frmSaldoPuntos:txtSaldoPuntos'))
                    ).text.strip()

                    puntos = {
                        "fecha_extraccion": time.strftime("%Y-%d-%m %H:%M:%S"),
                        "NIF": nif,
                        "nombre": fullname,
                        "puntos": points_balance.replace("\n", " ").split(" ")[0],
                    }
                    self._log(logging.INFO, self.task_id, "Success", f"Puntos obtenidos correctamente: {puntos['puntos']}")

                    try:
                        WebDriverWait(self.driver, random_wait('LONG')).until(
                            EC.presence_of_element_located((By.ID, 'frmSaldoPuntos:tblAntecedentes'))
                        )

                        sanciones = []
                        rows = self.driver.find_elements(By.XPATH, '//*[@id="frmSaldoPuntos:tblAntecedentes"]/tbody/tr')
                        for row in rows:
                            cells = row.find_elements(By.TAG_NAME, 'td')
                            if len(cells) >= 6:
                                try:
                                    # Extract raw texts safely
                                    fecha_text = cells[0].find_element(By.CLASS_NAME, "fecha-tbl").text.strip() if cells[0].find_elements(By.CLASS_NAME, "fecha-tbl") else ""
                                    puntos_text = cells[1].find_element(By.TAG_NAME, "span").text.strip().lstrip('+') if cells[1].find_elements(By.TAG_NAME, "span") else ""
                                    movimiento_text = cells[2].find_element(By.TAG_NAME, "span").text.strip() if cells[2].find_elements(By.TAG_NAME, "span") else ""
                                    saldo_text = cells[3].find_element(By.TAG_NAME, "span").text.strip() if cells[3].find_elements(By.TAG_NAME, "span") else ""
                                    organismo_text = cells[4].find_element(By.TAG_NAME, "span").text.strip() if cells[4].find_elements(By.TAG_NAME, "span") else ""

                                    # Parse fecha into datetime (normalize separators like '.' or '-' to '/')
                                    fecha_dt = None
                                    if fecha_text:
                                        fecha_norm = fecha_text.strip().replace('.', '/').replace('-', '/')
                                        fecha_norm = ' '.join(fecha_norm.split())
                                        for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M:%S", "%Y/%m/%d", "%Y/%m/%d %H:%M:%S"):
                                            try:
                                                fecha_dt = datetime.strptime(fecha_norm, fmt)
                                                break
                                            except Exception:
                                                continue

                                    try:
                                        p_text = puntos_text.strip().replace('\u2212', '-')
                                        try:
                                            puntos_formated = int(p_text)
                                        except Exception:
                                            m = re.search(r'[-+]?\d+', p_text)
                                            puntos_formated = int(m.group(0)) if m else None
                                    except Exception:
                                        puntos_formated = puntos_text


                                    sanciones.append(
                                        SancionesExtraidas(
                                            id=uuid.uuid4(),
                                            informe_id=informe_id,
                                            fecha_sancion=fecha_dt,
                                            puntos_sancion=puntos_formated,
                                            sancion=movimiento_text or None,
                                            saldo_puntos_final=int(saldo_text) if saldo_text.isdigit() else None,
                                            organismo_sancionador=organismo_text or None,
                                            created_at=datetime.now(),
                                        )
                                    )

                                except Exception as e:
                                    self._log(logging.WARNING, self.task_id, "Pending", f"Error procesando fila de sanción: {e}")

                        puntos["sanciones"] = sanciones
                        self._log(logging.INFO, self.task_id, "Success", f"Sanciones obtenidas correctamente para el cliente {self.cliente}")
                    except Exception as e:
                        self._log(logging.WARNING, self.task_id, "Pending", f"Error al obtener las sanciones del cliente {self.cliente}: {e}")
                        return None

                    return puntos

                except Exception as e:
                    self._log(logging.ERROR, self.task_id, "Failure", f"Error al obtener los puntos del cliente {self.cliente}: {e}")
                    return None

            except Exception as e:
                self._log(logging.ERROR, self.task_id, "Failure", f"Error al hacer clic en el enlace para obtener los puntos del cliente {self.cliente}: {e}")
                return None

        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"Error al obtener los puntos del cliente {self.cliente}: {e}")
            raise e

    def informeDgt(self, informeDgt : InformesDgtAutomatizaciones):
        temp_profile = tempfile.mkdtemp(prefix=f"dgt_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link='https://sede.dgt.gob.es/es/mi_dgt/', 
            module="MatriculasyPuntos",
            log_dir="logs/matriculasypuntos",
            filename=f"matriculasypuntos",
            cliente=self.cliente,
            site='dev',
            task_id='MatriculasyPuntos',
            execution_id=self.execution_id
        )

        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait('LONG', wait=True)
        try:
            # assign driver to self so other methods can use it
            self.driver = driver
            self.login()
            random_wait('LONG', wait=True)
            try:
                WebDriverWait(driver, random_wait('X_LONG')).until(
                    EC.visibility_of_element_located((By.XPATH, '//*[@id="cconsent-bar"]'))
                )
                WebDriverWait(driver, random_wait('X_LONG')).until(
                    EC.element_to_be_clickable((By.XPATH, '//*[@id="cconsent-bar"]/div/div[2]/div/button[2]'))
                ).click()
                self._log(logging.INFO, self.task_id, "Success", "Banner de cookies cerrado correctamente")
            except Exception as e:
                e_str = str(e)
                stacktrace_index = e_str.find('Stacktrace')
                if stacktrace_index != -1:
                    self._log(logging.ERROR, self.task_id, "Failure",  f"Error cerrando banner cookies:{e_str[:stacktrace_index + len('Stacktrace:')]}")
                else:
                    self._log(logging.ERROR, self.task_id, "Failure",  f"Error cerrando banner cookies:{e_str}")
                driver.execute_script("window.scrollBy(0, 100);")

            matriculas = self.get_matriculas(informe_id = informeDgt.id)
            puntos = self.get_puntos(informe_id = informeDgt.id)

            informeDgt.matriculas = len(matriculas['vehiculos']) if matriculas else 0
            informeDgt.puntos = int(puntos.get('puntos')) if puntos and puntos.get('puntos') and puntos.get('puntos').isdigit() else 0
            informeDgt.nif_en_sede = puntos.get('NIF') if puntos else None
            informeDgt.nombre_en_sede = puntos.get('nombre') if puntos else None


            if matriculas:
                self._log(logging.INFO, self.task_id, "Success", f"Matriculas obtenidas correctamente: {len(matriculas.get('vehiculos'))}")
            if puntos:
                self._log(logging.INFO, self.task_id, "Success", f"Puntos obtenidos correctamente: {puntos.get('puntos')}")

            
            return informeDgt, matriculas, puntos            

            
        except Exception as e:
            self._log(logging.ERROR, self.task_id, "Failure", f"Error en la ejecución de recuperacion de datos de la DEV : {e}")
            return None, None, None
        finally:
            random_wait('LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
            
            