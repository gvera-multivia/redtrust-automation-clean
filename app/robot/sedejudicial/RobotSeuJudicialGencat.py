import logging
from multiprocessing import Queue
import time, os, shutil, tempfile
import uuid
import re
import json

# THIRD PARTY PACKAGES
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# PERSONAL PACKAGES - UTILS
from app.utils.setup import WebDriverSetup
from app.utils.utils import random_wait
from bs4 import BeautifulSoup
from typing import Dict, Any, List


class RobotSeuJudicialGencat:
    def __init__(
            self, 
            date : str, 
            cliente : str, 
            log_queue: Queue, 
            execution_id: str,
            module : str = "SedeJudicial",
            sede : str ='Seu Judicial Gencat'
    ):
            
        self.portal_link = 'https://valid.aoc.cat/o/oauth2/auth?scope=autenticacio_usuari&state=principalAuth&response_type=code&client_id=gencat.vass.cat&approval_prompt=auto&access_type=online&redirect_uri=https://seujudicial.justicia.gencat.cat/SJC/AppJava/home'
        self.module = module
        self.execution_id = execution_id
        self.class_name = f"{self.__class__.__name__}_{uuid.uuid4().hex[:6]}"
        self.sede = sede
        self.cliente = cliente
        self.date = date
        self.module = module
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

    def _login_seujudicial_gencat(self, driver) -> bool:
        try:
            while True:
                try:
                    try:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCertCaptcha"]'))
                        ).click()
                    except Exception:
                        WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="btnContinuaCert"]'))
                        ).click()

                    try:
                        WebDriverWait(driver, random_wait(wait_type='X_LONG', wait=False)).until(
                            EC.element_to_be_clickable((By.XPATH, '//*[@id="modalCertificat"]/div/div/div[3]/button'))
                        ).click()
                    except Exception:
                        pass

                    # If neither button is present, break; if any is present, continue
                    if not (driver.find_elements(By.XPATH, '//*[@id="btnContinuaCert"]') or driver.find_elements(By.XPATH, '//*[@id="btnContinuaCertCaptcha"]')):
                        break
                except Exception as e:  
                    self._log(logging.ERROR, self.sede, "Failure", f"Error accediendo al login con certificado")
                    random_wait(wait_type='SHORT', wait=True)

            xpath = '/html/body/sjc-root/sjc-home/div ' # TODO

            end_time = time.time() + random_wait(wait_type='XX_LONG', wait=False)   
            while time.time() < end_time:  
                try:
                    element= WebDriverWait(driver, random_wait(wait_type='XX_LONG', wait=False)).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )

                    if element.is_displayed():
                        self._log(logging.INFO, self.sede, "Success", f"Login exitoso en {self.sede}")

                        return True
                    else:
                        self._log(logging.ERROR, self.sede, "Failure", f"Login fallido en {self.sede}: Elemento no visible")
                        return False
                except Exception:
                    random_wait(wait_type='X_LONG', wait=True)
                    return False

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"Error en login: {e}")
            return False
        finally:
            random_wait(wait_type='LONG', wait=True)

    def inspect(self) -> bool:
        # Crear una carpeta temporal para el perfil de usuario
        temp_profile = tempfile.mkdtemp(prefix=f"{self.sede}_temp_profile_")
        driver_setup = WebDriverSetup(
            temp_profile=temp_profile,
            portal_link=self.portal_link,
            module="SedeJudicial",
            log_dir="logs/sedejudicial",
            filename=f"sedejudicial",
            cliente=self.cliente,
            task_id=self.sede,
            site=self.sede,
            execution_id=self.execution_id

        )
        driver = driver_setup.setup_chrome_driver_altas() 
        random_wait(wait_type='LONG', wait=True)

        # ✅ Mapeo dinámico según título identificado del heading
        XPATH_MAP = {
            "expedients": {
                "container":   "div/sjc-container-expedient",  # /html/body/sjc-root/sjc-home/div[4]/div/sjc-container-expedient
                "table":       "div/sjc-expedient-llista/div/div/div/div/div/table", # /html/body/sjc-root/sjc-home/div[4]/div/sjc-container-expedient/div/div/div[2]/div/sjc-expedient-llista/div/div/div/div/div/table
                "paginator":   "div/sjc-expedient-llista/div/div/div/div/div/div/ul/li[contains(@class,'actiu2')]", # /html/body/sjc-root/sjc-home/div[4]/div/sjc-container-expedient/div/div/div[2]/div/sjc-expedient-llista/div/div/div/div/div/div/ul/li[3]/a
                "cells":       "div/sjc-expedient-llista/div/div/div" # /html/body/sjc-root/sjc-home/div[4]/div/sjc-container-expedient/div/div/div[2]/div/sjc-expedient-llista/div/div/div/div/div/table/tbody/tr[1]/td[1]
            },
            "assenyalaments": {
                "container":   "div/sjc-container-assenyalament", # /html/body/sjc-root/sjc-home/div[4]/div/sjc-container-assenyalament
                "table":       "div/sjc-assenyalament-llista/div[2]/div/div/div/table", # /html/body/sjc-root/sjc-home/div[5]/div/sjc-container-assenyalament/div/div/div[2]/div/sjc-assenyalament-llista/div[2]/div/div/div/table
                "paginator":   "div/sjc-assenyalament-llista/div[2]/div/div/div/div/ul/li[contains(@class,'actiu2')]", # /html/body/sjc-root/sjc-home/div[5]/div/sjc-container-assenyalament/div/div/div[2]/div/sjc-assenyalament-llista/div[2]/div/div/div/div/ul/li[3]/a
                "cells":       "div/sjc-assenyalament-llista/div[2]/div" # /html/body/sjc-root/sjc-home/div[5]/div/sjc-container-assenyalament/div/div/div[2]/div/sjc-assenyalament-llista/div[2]/div/div/div/table/tbody/tr[1]/td[1]
            },
            "justícia gratuïta": {
                "container":   "div/sjc-container-justicia-gratuita", # /html/body/sjc-root/sjc-home/div[6]/div/sjc-container-justicia-gratuita
                "table":       "div/sjc-justicia-gratuita-llista/div[2]/div/div/div/table", # /html/body/sjc-root/sjc-home/div[6]/div/sjc-container-justicia-gratuita/div/div/div[2]/div/sjc-justicia-gratuita-llista/div[2]/div/div/div/table
                "paginator":   "div/sjc-justicia-gratuita-llista/div[2]/div/div/div/div/ul/li[contains(@class,'actiu2')]", # /html/body/sjc-root/sjc-home/div[6]/div/sjc-container-justicia-gratuita/div/div/div[2]/div/sjc-justicia-gratuita-llista/div[2]/div/div/div/div/ul/li[3]/a
                "cells":       "div/sjc-justicia-gratuita-llista/div[2]/div" # /html/body/sjc-root/sjc-home/div[6]/div/sjc-container-justicia-gratuita/div/div/div[2]/div/sjc-justicia-gratuita-llista/div[2]/div/div/div/table/tbody/tr[1]/td[1]
            }
        }

        try:
            login = self._login_seujudicial_gencat(driver)
            datatables = {}
            if login:
                try:
                    sections = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                        EC.presence_of_all_elements_located((By.XPATH, '/html/body/sjc-root/sjc-home/div'))
                    )
                    for index_s in range(len(sections)):
                        section = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                            EC.presence_of_element_located((By.XPATH, f'/html/body/sjc-root/sjc-home/div[{index_s+1}]'))
                        )

                        try:
                            candidates_heading = [
                                f"/html/body/sjc-root/sjc-home/div[{index_s+1}]/div/sjc-container-expedient/div/div/div[1]/h2",
                                f"/html/body/sjc-root/sjc-home/div[{index_s+1}]/div/sjc-container-assenyalament/div/div/div[1]/h2",
                                f"/html/body/sjc-root/sjc-home/div[{index_s+1}]/div/sjc-container-justicia-gratuita/div/div/div[1]/h2"
                            ] 

                            # Ensure heading is always defined and iterate over a copy if we may modify the list
                            heading = None
                            for xpath_heading in candidates_heading:
                                try:
                                    heading = section.find_element(By.XPATH, xpath_heading)
                                    if heading:
                                        self._log(logging.INFO, self.sede, "Pending", f"Encabezado localizado con xpath absoluto para la sección index {index_s+1}.")
                                        # remove the xpath value safely (pop expects an index)
                                        try:
                                            candidates_heading.remove(xpath_heading)
                                        except ValueError:
                                            pass
                                        break
                                except Exception:
                                    heading = None
                                    continue
                            
                            if not heading:
                                self._log(logging.INFO, self.sede, "Pending", f"Encabezado no localizado con xpath absoluto para la sección index {index_s+1}.")
                                continue
                            
                            title = heading.text.strip().lower()

                            self._log(logging.INFO, self.sede, "Pending", f"Found section heading: {title}")
                            datatables[title] = []
                            
                            xpath_paginator = f"/html/body/sjc-root/sjc-home/div[{index_s+1}]/{XPATH_MAP[title].get('container')}/div/div/div[2]/{XPATH_MAP[title].get('paginator')}"

                            try:
                                paginator_items = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                    EC.presence_of_all_elements_located((By.XPATH, xpath_paginator))    
                                )   
                            except Exception:
                                paginator_items = None

                            if not paginator_items:
                                self._log(logging.INFO, self.sede, "Pending", f"Paginador no localizado con xpath absoluto para la sección {title}.")
                                raise Exception("Paginador no localizado")
                        
                            pages = int(paginator_items[-1].text.strip()) 

                            for index_p in range(1, pages+1): 

                                xpath_table = f"html/body/sjc-root/sjc-home/div[{index_s+1}]/{XPATH_MAP[title].get('container')}/div/div/div[2]/{XPATH_MAP[title].get('table')}"
                                try:
                                    table = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                        EC.presence_of_element_located((By.XPATH, xpath_table))
                                    )
                                except Exception:
                                    table = None


                                if table is None:
                                    self._log(logging.INFO, self.sede, "Pending", f"Tabla no localizada con xpath absoluto para la sección {title}.")
                                    raise Exception("Tabla no localizada")
                                    
                                                         
                                try:
                                    if table:
                                        headers = WebDriverWait(table, random_wait(wait_type='LONG', wait=False)).until(
                                            EC.presence_of_all_elements_located((By.XPATH, './thead/tr/th'))
                                        )
                                        header_titles = [header.text.strip().lower() for header in headers]

                                        rows = WebDriverWait(table, random_wait(wait_type='LONG', wait=False)).until(
                                            EC.presence_of_all_elements_located((By.XPATH, './tbody/tr'))
                                        )

                                        for index_r in range(len(rows)):
                                            try:   
                                                xpath_cell = f"html/body/sjc-root/sjc-home/div[{index_s+1}]/{XPATH_MAP[title].get('container')}/div/div/div[2]/{XPATH_MAP[title].get('cells')}"

                                                try:
                                                    cells = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                                        EC.presence_of_all_elements_located((By.XPATH, f"{xpath_cell}/div/div/table/tbody/tr[{index_r+1}]/td" ))
                                                    )

                                                except Exception:
                                                    cells = None
                                                    continue

                                                first_cell = cells[0].text.strip()
                                                if first_cell == '' or 'no hi ha resultats' in first_cell.lower():
                                                    # Skip rows that indicate "no results"
                                                    continue

                                                # Check if last cell contains a button-like element (button, input[type=button|submit], or role="button")
                                                try:
                                                    td_button = WebDriverWait(cells[-1], random_wait(wait_type='LONG', wait=False)).until(
                                                        EC.presence_of_element_located((By.XPATH, './/button | .//input[@type="button" or @type="submit"] | .//*[@role="button"]'))
                                                    )
                                                except Exception:
                                                    td_button = None

                                                if td_button is None:                                                
                                                    row_data = {header_titles[i]: cells[i].text.strip() for i in range(len(cells))}
                                                else:
                                                    row_data = {header_titles[i]: cells[i].text.strip() for i in range(len(cells)-1)}
                                                    try:
                                                        td_button.click()
                                                        random_wait(wait_type='LONG', wait=True)

                                                        # Extract additional details from the new page
                                                        html = driver.page_source
                                                        detalles = self.parse_seujudicial_expedient(html)

                                                        # Normalize title: remove trailing 's' if present; if no 's' at all, use empty string
                                                        normalized = title
                                                        if 's' not in normalized:
                                                            normalized = ''
                                                        else:
                                                            if normalized.endswith('s'):
                                                                normalized = normalized[:-1]
                                                        key = f"detalles {normalized}".strip()
                                                        row_data[key] = detalles
                            
                                                    except Exception:
                                                        self._log(logging.ERROR, self.sede, "Pending", f"No se encontró el botón en la última celda de la fila: {row_data}")
                                                        pass
                                                    finally:
                                                        driver.back()
                                                        random_wait(wait_type='MEDIUM', wait=True)
                                                        
                                                        next_page = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                                            EC.element_to_be_clickable((By.XPATH, f"{xpath_cell}/div/div/div/ul/li[contains(@class,'actiu2')][{index_p}]/a"))
                                                        )
                                                        # print(next_page.text)
                                                        next_page.click()
                                                        random_wait(wait_type='MEDIUM', wait=True)

                                                datatables[title].append(row_data)
                                            except Exception as e:
                                                self._log(logging.ERROR, self.sede, "Failure", f"Error procesando fila {index_r} en la sección '{title}', página {index_p}: {e}")
                                                continue                                                                    

                                        self._log(logging.INFO, self.sede, "Pending", f"Datos extraídos de la sección {title}: {len(datatables[title])} filas.")
                                except Exception as e:
                                    self._log(logging.ERROR, self.sede, "Failure", f"Error extrayendo datos de la seccion '{title}', pagina {index_p}: {e}")
                                finally:
                                    if index_p < pages:
                                        next_page = WebDriverWait(driver, random_wait(wait_type='LONG', wait=False)).until(
                                            EC.element_to_be_clickable((By.XPATH, f"{xpath_cell}/div/div/div/ul/li[contains(@class,'actiu2')][{index_p+1}]/a"))
                                        )
                                        # print(next_page.text)
                                        next_page.click()
                                    random_wait(wait_type='MEDIUM', wait=True)
                                    
                        except Exception as e:
                            self._log(logging.ERROR, self.sede, "Failure", f"Error extrayendo datos de la seccion '{title}': {e}")
                            continue
                    
                except Exception as e:
                    self._log(logging.ERROR, self.sede, "Failure", f"Error extrayendo datos de las tablas: {e}")
                    # return False, None

                try:
                    for k, v in list(datatables.items()):
                        # normalize nested list case where datatables[title] == [ [... ] ]
                        if isinstance(v, list):
                            if v and isinstance(v[0], list):
                                flat = v[0]
                            else:
                                flat = v

                            # If the list contains dict-like rows, dedupe them
                            dict_rows = [item for item in flat if isinstance(item, dict)]
                            non_dict_rows = [item for item in flat if not isinstance(item, dict)]

                            if dict_rows:
                                deduped = self._dedupe_list_of_dicts(dict_rows)
                                # preserve any non-dict rows by appending them after deduped dicts
                                datatables[k] = deduped + non_dict_rows
                            else:
                                # nothing to dedupe
                                datatables[k] = flat
                except Exception as e:
                    # If deduping fails for any reason, log and continue returning raw results
                    self._log(logging.ERROR, self.sede, "Pending", f"Error during deduplication: {e}")

                return True, datatables                            
                
            else:
                self._log(logging.ERROR, self.sede, "Failure", "Error en login.")
                return False, None

        except Exception as e:
            self._log(logging.ERROR, self.sede, "Failure", f"⚠️ Error en darse de alta en {self.portal_link}: {e}")
            return False, None

        finally:
            random_wait(wait_type='LONG', wait=True)
            driver.quit()
            shutil.rmtree(temp_profile, ignore_errors=True)
    
    def _table_to_kv(self, table) -> Dict[str, str]:
        """
        Convierte una tabla simple (tr con 2 tds: clave/valor) a dict.
        """
        data = {}
        if not table:
            return data
        for tr in table.find_all("tr", recursive=False):
            tds = tr.find_all(["td", "th"], recursive=False)
            if len(tds) >= 2:
                key = tds[0].get_text(strip=True)
                val = tds[1].get_text(strip=True)
                if key:
                    data[key] = val
        return data

    def _table_to_dict(self, table) -> Dict[str, Dict[str, str]]:
        """
        Convierte una tabla con o sin thead en un diccionario donde cada key es la
        primera columna de la fila, y el valor es otro diccionario con los datos.
        """
        rows_out = {}
        if not table:
            return rows_out

        # Obtener headers si existen en thead
        headers = []
        thead = table.find("thead")
        if thead:
            headers = [th.get_text(strip=True) for th in thead.find_all("th", recursive=False)]

        # Fallback si no hay headers
        if not headers:
            first_row = table.find("tr")
            if first_row:
                possible_headers = [cell.get_text(strip=True) for cell in first_row.find_all("th")]
                if possible_headers:
                    headers = possible_headers

        tbody = table.find("tbody") or table

        for tr in tbody.find_all("tr", recursive=False):
            cells = [td.get_text(strip=True) for td in tr.find_all(["td", "th"], recursive=False)]
            if not cells:
                continue
            
            if len(cells) == 2:
                # La primera celda será la key del diccionario
                rows_out[cells[0]] = cells[1]
            else:
                if headers and len(headers) <= len(cells):
                    row = {headers[i]: cells[i] for i in range(len(headers))}
                else:
                    # Si no hay headers, crear claves genéricas col_0, col_1...
                    row = {f"col_{i}": cells[i] for i in range(len(cells))}

                rows_out[cells[0]] = row

        return rows_out

    def _dedupe_list_of_dicts(self, items: List[Dict]) -> List[Dict]:
        """
        Remove duplicate dictionaries while preserving order.
        Uses a JSON-serialized canonical representation as a fingerprint.
        Falls back to str(sorted()) if serialization fails.
        """
        if not items:
            return []
        seen = set()
        out: List[Dict] = []
        for it in items:
            try:
                # ensure deterministic representation
                key = json.dumps(it, sort_keys=True, ensure_ascii=False)
            except Exception:
                try:
                    # fallback for un-serializable values
                    key = str(sorted(it.items()))
                except Exception:
                    key = str(it)
            if key in seen:
                continue
            seen.add(key)
            out.append(it)
        return out

    def parse_seujudicial_expedient(self, html: str) -> Dict[str, Any]:
        """
        Parsea la vista `sjc-expedient-vista` y devuelve un dict estructurado
        por secciones y subsecciones.

        Ejemplo de salida:
        {
        "Dades de l'assumpte": {"NIG": "...", "Àmbit":"..."},
        "Dades de registre": {"Núm. de la demanda":"...", ...},
        "Dades del procediment": {"Procediment":"...", "Número/Any/Secció":"...", ...},
        "Altres procediments": [ { "Data": "...", "Estat":"...", ... }, ... ],
        "Intervinents": [
            { "role": "Demandant", "Identificació de la persona": {...}, "Dades de contacte": {...} },
            ...
        ],
        "Dades de la tramitació": {
            "Fites processals": [ { "Data": "...", "Descripció": "..." }, ... ],
            "Agenda d'assenyalaments": [ ... ]
        },
        "Documents": [ { "Data":"...", "Estat":"...", "Títol":"...", "acciones": {...}, "attachments":[...] }, ... ],
        "actions": { "download_pdf_button_text": "Descarrega PDF" }  # si lo hay
        }
        """
        soup = BeautifulSoup(html, "html.parser")
        output: Dict[str, Any] = {}
        if not soup:
            return output

        # 1) Buscar todas las secciones principales (contenedores con collapser_container)
        containers = soup.select(".collapser_container")
        # Usaremos un recorrido y extraeremos según el título del botón collapser
        for c in containers:
            # título principal
            title_node = c.select_one(".collapser")
            if not title_node:
                # some containers might be nested non-standard; skip
                continue
            title = title_node.get_text(strip=True)
            # encontrar el bloque colapsado asociado: preferir .collapse dentro del mismo contenedor
            collapse = c.select_one(".collapse") or c.find_next_sibling(class_="collapse")
            # Si no hay collapse, extraer tablas dentro del container directamente
            if not collapse:
                collapse = c

            # Procesamiento por tipo (heurísticos según título)
            # tablas clave-valor simples
            tables = collapse.find_all("table", recursive=False)
            if title.lower().strip().startswith("dades") and tables:
                # muchas secciones 'Dades ...' son tablas clave-valor (2 columnas)
                # si existe más de una tabla, unirlas con sufijo incremental
                merged = {}
                for idx, table in enumerate(tables):
                    kv = self._table_to_kv(table)
                    # si solo una tabla, usar directamente; si varias, numerarlas
                    if len(tables) == 1:
                        merged.update(kv)
                    else:
                        merged[f"table_{idx}"] = kv
                output[title] = merged
                continue

            # 'Altres procediments' u otras tablas listadas con thead -> usar lista
            if collapse.find("table"):
                # si tabla tiene headers -> lista
                # detect documents-table specially
                doc_table = collapse.select_one(".documents-table")
                if doc_table:
                    docs = []
                    tbody = doc_table.find("tbody")
                    if tbody:
                        trs = tbody.find_all("tr", recursive=False)
                        i = 0
                        while i < len(trs):
                            tr = trs[i]
                            row = {}
                            # main row (puede ser fila con class 'border')
                            tds = tr.find_all("td", recursive=False)
                            if tds:
                                # map columns heurísticamente
                                # intentar obtener Data, Estat, Titol, Acció
                                # columnas visibles en el HTML: [col0, Data, Estat, Títol, Acció]
                                if len(tds) >= 5:
                                    row["data"] = tds[1].get_text(strip=True)
                                    row["estat"] = tds[2].get_text(strip=True)
                                    # título puede contener link y texto
                                    row["titol"] = tds[3].get_text(" ", strip=True)
                                    # acciones: puede estar en botón
                                    row["accion_text"] = tds[4].get_text(" ", strip=True)
                                else:
                                    # fallback: todas las celdas
                                    cells = [td.get_text(strip=True) for td in tds]
                                    row.update({cells[i]: cells[i+1] for i in range(0, len(cells), 2)})
                            # mirar si siguiente fila es detalle (tr con colspan)
                            if i + 1 < len(trs):
                                next_tr = trs[i + 1]
                                # detect nested details table
                                inside_table = next_tr.find("table")
                                if inside_table:
                                    row["attachments"] = self._table_to_dict(inside_table)
                                    i += 2
                                else:
                                    i += 1
                            else:
                                i += 1
                            docs.append(row)
                    output[title] = docs
                    continue

                # si hay tablas con thead -> listas de filas
                lists = []
                for table in collapse.find_all("table"):
                    # preferir las que tienen thead
                    if table.find("thead"):
                        lists = self._table_to_dict(table)
                        break
                if lists:
                    output[title] = lists
                    continue

            # 'Intervinents' es un contenedor con múltiples sub-collapsers
            if title.lower().startswith("intervinents"):
                parties = []
                # buscar sub-containers o secciones internas (cada intervinent)
                # dentro del collapse, buscar elementos que tengan collapser (roles)
                sub_collapsers = collapse.select(".div-button.collapser, .collapser.div-button")
                # Para evitar coger el título principal, filtramos por nodos dentro del collapse que tengan data-target o id
                for node in sub_collapsers:
                    role = node.get_text(strip=True)
                    # el panel asociado suele ser el siguiente .collapse con id correspondiente
                    # intentar encontrar por data-target (ej: #intervinent0)
                    data_target = node.get("data-target")
                    sub_block = None
                    if data_target:
                        # remove leading #
                        tid = data_target.lstrip("#")
                        sub_block = collapse.find(id=tid)
                    if not sub_block:
                        # fallback: next sibling collapse
                        sib = node.find_next_sibling(class_="collapse")
                        if sib:
                            sub_block = sib
                    if not sub_block:
                        # si no encontramos, continue
                        continue

                    party = {"role": role}
                    # dentro de sub_block hay tablas separadas por h3 con títulos de subsección
                    for h3 in sub_block.find_all("h3"):
                        sub_title = h3.get_text(strip=True)
                        # la tabla asociada puede ser el siguiente table
                        table = h3.find_next("table")
                        if table:
                            # si la tabla tiene pares clave-valor
                            kv = self._table_to_kv(table)
                            if kv:
                                party[sub_title] = kv
                            else:
                                party[sub_title] = self._table_to_dict(table)
                    # si no hay h3, buscar tablas directas
                    if not party.get("Identificació de la persona") and sub_block.find("table"):
                        # intentar convertir primera tabla a kv
                        first_table = sub_block.find("table")
                        party["content"] = self._table_to_kv(first_table) or self._table_to_dict(first_table)
                    parties.append(party)
                output[title] = parties
                continue

            # Dades de la tramitació -> buscar subsecciones internas como 'Fites processals' y 'Agenda d'assenyalaments'
            if title.lower().startswith("dades de la tramitació") or "tramitació" in title.lower():
                tram = {}
                # buscar collapser internos con texto
                inner_collapsers = collapse.select(".collapser")
                for node in inner_collapsers:
                    inner_title = node.get_text(strip=True)
                    inner_block = None
                    data_target = node.get("data-target")
                    if data_target:
                        tid = data_target.lstrip("#")
                        inner_block = collapse.find(id=tid)
                    if not inner_block:
                        inner_block = node.find_next_sibling(class_="collapse") or node.find_next("div", class_="collapse")
                    if not inner_block:
                        continue
                    # buscar tablas dentro
                    tables_in = inner_block.find_all("table")
                    if tables_in:
                        # prefer table with thead (list)
                        chosen = None
                        for t in tables_in:
                            if t.find("thead"):
                                chosen = t
                                break
                        chosen = chosen or tables_in[0]
                        tram[inner_title] = self._table_to_dict(chosen) if chosen else []
                    else:
                        tram[inner_title] = []
                output[title] = tram
                continue

            # si no entró en heurísticos, intentar leer cualquier tabla como lista o kv
            if collapse.find("table"):
                t = collapse.find("table")
                # si parece 2-col -> kv
                kv = self._table_to_kv(t)
                if kv:
                    output[title] = kv
                else:
                    output[title] = self._table_to_dict(t)
                continue

            # fallback: texto plano dentro del collapse
            text = collapse.get_text(" ", strip=True)
            output[title] = text

        # Botón de descarga de PDF o acciones finais
        # buscar botón con texto 'Descarrega PDF' o similar
        download_btn = soup.find("button", string=lambda s: s and "Descarrega" in s)
        if download_btn:
            output.setdefault("actions", {})["download_pdf_button_text"] = download_btn.get_text(strip=True)
        return output
