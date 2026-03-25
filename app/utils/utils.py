import asyncio
from enum import Enum
import glob
import hashlib
import logging
import os
import random
import shutil
import time
import re
from difflib import SequenceMatcher
from typing import Dict, Optional
from dotenv import load_dotenv
from googletrans import Translator
from selenium import webdriver

from app.helper.errors.robot_descargas import ErrorRobotDescargas
from app.utils.parser.PDFOCRParser import PDFOCRParser
from app.utils.parser.PDFMetadataExtractor import PDFMetadataExtractor

class ServiciosNEO(Enum):
    MULTINEO = "MULTINEO"
    NEOCASH = "NEOCASH"
    NEOESTATAL = "NEOESTATAL"
    INFONEO = "INFONEO"
    SUSCRIPCION = "SUSCRIPCION"
    BLINDAJE = "BLINDAJE"

common_rules = {
    "CT_Pattern": r"\b(CT\d{10,20})\b",
    "CC_Pattern": r"\b(CC\d{10,20})\b",
    "DH_Pattern": r"\b(DH\d{10,20})\b",
    "EE_Pattern": r"\b(EE\d{10,20})\b",
    "ET_Pattern": r"\b(ET\d{10,20})\b",
    "EX_Pattern": r"\b(EX\d{10,20})\b",
    "OA_Pattern": r"\b(OA\d{10,20})\b",
    "EB_Pattern": r"\b(EB\d{10,20})\b",
    "EI_Pattern": r"\b(EI\d{10,20})\b",
    "EJ_Pattern": r"\b(EJ\d{10,20})\b",
    "MX_Pattern": r"\b(MX\d{10,20})\b",
    "MU_Pattern": r"\b(MU\d{10,20})\b",
    "KC_Pattern": r"\b(KC[\d\/\- ]{10,20})\b",
    "KD_Pattern": r"\b(KD/\d{10,20})\b",
    "NUM_SCatTransit_Pattern": r"\b((?:25|17|08|43)/\d{6,12})\b", # Only match if the two digits before the slash are 25, 17, 08, or 43
    "MULTES_Poblacion": r"\b(MULTES\s(?:\(DEV\)\s)?-\s[A-ZÀ-ÿa-z'À-ÿ\s]{3,})\b",
    "TRIBUTS_Poblacion": r"\b(TRIBUTS\s-\s[A-ZÀ-ÿa-z'À-ÿ\s]{3,})\b",
    "DENUNCIA": r"\bDENÚNCIA-(\d+[A-Z]+\d+)\b",
    "REQUERIMENT_DENUNCIA": r"\bREQUERIMENT-(\d+[A-Z]+\d+)\b",
    "REGIMENES_SEG_SOCIAL_OBLIGADOS": r"REGIMENES SEG\. SOCIAL OBLIGADOS A RED\s*/\s*([A-Za-z0-9]{15,20})\s*/",
}

PLUS_TIME = 1
WAIT_TIME = {
    'SHORT': 1*PLUS_TIME,
    'MEDIUM': 2.5*PLUS_TIME,
    'LONG': 5*PLUS_TIME,
    'X_LONG': 10*PLUS_TIME,
    'XX_LONG': 30*PLUS_TIME,
    'XXX_LONG': 60*PLUS_TIME
}


# list(CERT_SEDES_ACTION.items())[2]
CERT_SEDES_ACTION = {
    1: "Alta realizada correctamente.",
    2: "Correo MULTIVIA añadido correctamente.",
    3: "Correo del Cliente añadido correctamente.",
    4: "Correo sustituido por el de MULTIVIA correctamente.",
    5: "Correo de MULTIVIA sustituido por el del Cliente correctamente.",
    6: "Orden de los correos cambiado correctamente.",
    7: "El alta ya está realizada con el correo correcto.",
    8: "Alta en sede ya realizada con el mail de cliente"
}

DESCARGA_ESPECIAL = [
    "No descargar AEAT",
    "No descargar AEAT, ni TGSS",
    "No descargar AEAT, si TRÁFICO",
    "No descargar DEHÚ",
    "No descargar leídas",
    "No descargar nada",
    # "No descargar TGSS",
    "Revisar DGT",
    "Solo TRÁFICO",
]

CONSULTA_RESULTS = {
    0: "Correcto",
    1: "Certificado No está en RedTrust",
    2: "Error en el Certificado",
    3: "Certificado Caducado",
    4: "Tiene Notif. pero No le Entran",
    5: "Correcto y Tiene ATC",
    6: "Certificado Revocado",
    7: "Correcto con Notificaciones Desc.",
    8: "Otro Error"
}


def random_wait(wait_type : str ='LONG', extra : int = 0, wait : bool = False) -> float:
    """
    Espera un tiempo aleatorio basado en WAIT_TIME[wait_type].
    extra: segundos adicionales opcionales.
    """
    base = WAIT_TIME.get(wait_type, 2)
    # 70% a 130% del valor base, más un extra opcional
    delay = random.uniform(0.7, 1.3) * base + extra
    if wait:
        time.sleep(delay)
    return delay


def email_validator(email: str) -> str:
    """
    Valida el formato de un correo electrónico.
    - Si es válido, devuelve el correo;
    - Si es de multivia y se parece mucho a los defaults, lo reajusta al default correspondiente;
    - Si no es válido, devuelve el mail default de multivia (notificaciones).
    """
    DEFAULT_MAILS = [
        "notificaciones@xvia-serviciosjuridicos.com",
        "info@xvia-serviciosjuridicos.com"
    ]

    if not email:
        return DEFAULT_MAILS[0]
    
    email = email.strip()
    email_lower = email.lower()

    # Si se parece mucho a alguno de los mails de multivia, lo reajusta
    for default_mail in DEFAULT_MAILS:
        similarity = SequenceMatcher(None, email_lower, default_mail).ratio()
        if similarity > 0.85:
            return default_mail

    # Validación estándar de email
    pattern = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
    if re.match(pattern, email):
        return email
    else:
        return DEFAULT_MAILS[0]  # notificaciones@xvia-serviciosjuridicos.com


def random_action(driver: webdriver, action: str = None) -> str:
    """
    Realiza una acción aleatoria sobre el driver: click neutro, scroll, movimiento de mouse, resize, focus, blur, reload, y scroll lateral.
    """
    actions = [
        'random_click',
        'random_scroll',
        'move_mouse_js',
        'resize_window',
        'focus_blur',
        # 'reload_page',
        'horizontal_scroll',
        # 'scroll_top',
        # 'scroll_bottom',
    ]
    if action is None:
        action = random.choice(actions)
    elif action not in actions:
        raise ValueError(f"Action '{action}' is not a valid action. Choose from {actions}.")
    
    if action == 'random_click':
        width = driver.execute_script('return window.innerWidth')
        height = driver.execute_script('return window.innerHeight')
        for _ in range(10):
            x = random.randint(0, max(0, width - 1))
            y = random.randint(0, max(0, height - 1))
            el = driver.execute_script('return document.elementFromPoint(arguments[0], arguments[1]);', x, y)
            if el is None:
                continue
            tag = el.tag_name.lower()
            if tag in ['button', 'a', 'input', 'select', 'textarea', 'option']:
                continue
            driver.execute_script('var ev = new MouseEvent("click", {clientX: arguments[0], clientY: arguments[1], bubbles: true}); document.elementFromPoint(arguments[0], arguments[1]).dispatchEvent(ev);', x, y)
            return f'random_click_neutral_{x}_{y}'
        return 'no_neutral_point_found'
    elif action == 'random_scroll':
        scroll_height = driver.execute_script('return document.body.scrollHeight')
        y = random.randint(0, max(0, scroll_height - 1))
        driver.execute_script(f'window.scrollTo(0, {y});')
        return f'random_scroll_to_{y}'
    elif action == 'move_mouse_js':
        width = driver.execute_script('return window.innerWidth')
        height = driver.execute_script('return window.innerHeight')
        x = random.randint(0, max(0, width - 1))
        y = random.randint(0, max(0, height - 1))
        driver.execute_script(f"var ev = new MouseEvent('mousemove', {{clientX: {x}, clientY: {y}}}); document.dispatchEvent(ev);")
        return f'move_mouse_js_{x}_{y}'
    elif action == 'resize_window':
        width = random.randint(1200, 1600)
        height = random.randint(800, 1000)
        driver.set_window_size(width, height)
        return f'resize_window_{width}_{height}'
    elif action == 'focus_blur':
        # Alterna el foco de la ventana
        driver.execute_script('window.blur();')
        time.sleep(0.1)
        driver.execute_script('window.focus();')
        return 'focus_blur'
    # elif action == 'reload_page':
    #     driver.refresh()
    #     return 'reload_page'
    elif action == 'horizontal_scroll':
        scroll_width = driver.execute_script('return document.body.scrollWidth')
        x = random.randint(0, max(0, scroll_width - 1))
        driver.execute_script(f'window.scrollTo({x}, window.scrollY);')
        return f'horizontal_scroll_to_{x}'
    # elif action == 'scroll_top':
    #     driver.execute_script('window.scrollTo(0, 0);')
    #     return 'scroll_top'
    # elif action == 'scroll_bottom':
    #     scroll_height = driver.execute_script('return document.body.scrollHeight')
    #     driver.execute_script(f'window.scrollTo(0, {scroll_height});')
    #     return 'scroll_bottom'
    return 'no_action'

'''Related to File Processing'''
def process_files(src_path: str, task_id: str | int, results: Dict, cliente: str, date: str, notification_date:str, log:callable, filepath: Optional[str] = None) -> tuple[str, str | None]:
    """Process files after robot execution (move, rename, etc.)"""
    try:
        if notification_date is None:
            notification_date = date
            
        expediente = results.get('expediente', None)
        con_expediente = False
        load_dotenv(dotenv_path='.env', override=True)

        # Find all files in the source directory
        files = glob.glob(os.path.join(src_path, '*'))
        if not files:
            log(logging.ERROR, task_id, "Failure", f"No files found in download path: {src_path}")
            return None
        latest_file = max(files, key=os.path.getmtime)

        # Set the new filename
        file_extension = os.path.splitext(latest_file)[1].lower()

        DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR")
        if filepath:
            dst_path = os.path.join(DOWNLOAD_DIR, 'revisar', filepath)
        else:
            dst_path = os.path.join(DOWNLOAD_DIR, 'revisar')
            
            
        os.makedirs(dst_path, exist_ok=True)

        # If it's a zip, sólo renombrar con los datos disponibles o fallback para expediente
        if file_extension == '.zip':
            if not expediente or expediente in ('None', 'N/A'):
                expediente = f"TODO{os.urandom(2).hex()[:5]}"
                con_expediente = False
            else:
                con_expediente = True

            new_file_name = f"N{notification_date} CL {cliente} EXP {expediente} {results.get('desc')} DES{file_extension}"
        else:
            detected = detectar_archivo_duplicado(dst_path, latest_file)
            if detected:
                log(logging.INFO, task_id, "Info", f"Duplicate file detected. Skipping move for file: {latest_file}")
                return detected, expediente

            # Para PDFs u otros, intentar extraer expediente si no viene en results
            extractor = PDFMetadataExtractor(
                cliente=cliente,
                message_id=task_id,
            )
            author = extractor.extract_author(latest_file, log)

            parser = PDFOCRParser(
                cliente=cliente,
                message_id=task_id,
                pdf_path=latest_file,
                author=author
            )

            if not expediente or expediente in ('None', 'N/A'):
                expediente_extracted, _rule, _org = parser.process_pages(log)
                if not expediente_extracted or expediente_extracted in ('None', 'N/A'):
                    expediente = f"TODO{os.urandom(2).hex()[:5]}"
                else:
                    expediente = expediente_extracted
                new_file_name = f"N{notification_date} CL {cliente} EXP {expediente} {results.get('desc')} DES{file_extension}"
            else:
                expediente_extracted, _rule, _org = parser.process_pages(log)
                if expediente_extracted and expediente_extracted not in ('None', 'N/A'):
                    new_file_name = f"N{notification_date} CL {cliente} EXP {expediente_extracted} {results.get('desc')} DES{file_extension}"
                else:
                    new_file_name = f"N{notification_date} CL {cliente} EXP {expediente} {results.get('desc')} DES{file_extension}"

        # Sanitize filename to remove or replace problematic characters
        def sanitize_filename(filename):
            # Remove or replace characters not allowed in Windows filenames
            return re.sub(r'[<>:"/\\|?*\']', '_', filename)                

        safe_file_name = sanitize_filename(new_file_name)

        # Check if file with the same name exists in destination path
        if os.path.exists(os.path.join(dst_path, safe_file_name)):            
            name, ext = os.path.splitext(new_file_name)
            random_digits = f"{random.randint(0, 999):03d}"
            new_file_name = f"{name} DUPL{random_digits}{ext}"            
            safe_file_name = sanitize_filename(new_file_name)

        log(logging.INFO, task_id, "Success", f"Renaming file to: {safe_file_name}")

        # Ensure destination directory exists
        dst_path = os.path.join(dst_path, safe_file_name)

        # Move and rename the file
        shutil.move(latest_file, dst_path)

        return dst_path, expediente
        
    except Exception as e:
        log(logging.ERROR, task_id, "Failure", ErrorRobotDescargas.ProcessFile(task_id, e))
        return None
    
def detectar_archivo_duplicado(origen: str, pdf_to_compare: str) -> Optional[str]:
    try:
        pdfs = [os.path.join(origen, f)
            for f in os.listdir(origen)
            if os.path.isfile(os.path.join(origen, f)) and f.lower().endswith(".pdf")]

        if not pdfs:        
            return None
        

        def hash_archivo(self, path, block_size=65536):
            hasher = hashlib.sha256()
            with open(path, "rb") as f:
                buf = f.read(block_size)
                while buf:
                    hasher.update(buf)
                    buf = f.read(block_size)
            return hasher.hexdigest()

        hash_to_compare = hash_archivo(pdf_to_compare)
        for pdf in pdfs:
            h = hash_archivo(pdf)
            
            if h == hash_to_compare:
                return pdf # Archivo duplicado encontrado
        
        return None

    except Exception as e:
        return None


""" Utility functions for download directory management and translation """
def cleanup_download_dir(sede_path: str, sede: str, log) -> None:
    """Clean up the download directory for a specific sede."""
    try:
        if os.path.exists(sede_path):
            for filename in os.listdir(sede_path):
                file_path = os.path.join(sede_path, filename)
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            log(logging.DEBUG, None, "Success", f"Download directory cleaned up for {sede}.")
        else:
            log(logging.WARNING, None, "Warning", f"Download directory for {sede} does not exist.")
    except Exception as e:
        log(logging.ERROR, None, "Failure", f"Error cleaning up download directory for {sede}: {e}")

def delete_download_dir(sede_path: str, sede: str, log) -> None:
    """Clean up the download directory for a specific sede."""
    try:
        if os.path.exists(sede_path):
            shutil.rmtree(sede_path)
            log(logging.INFO, None, "Success", f"Deleted directory: {sede_path}")
        else:
            log(logging.INFO, None, "Info", f"No directory to delete for sede: {sede}")
    except Exception as e:
        log(logging.ERROR, None, "Failure", f"Error cleaning up download directory for {sede}: {e}")


""" Translation utilities """
def translate_direction(direccion: Dict, sede:str, log ,target_language: str = 'ca') -> Dict:
    """
    Translates the keys of a direction dictionary to the target language.
    Supported languages: 'es' (Spanish), 'en' (English)
    """
    # Inicializa el traductor usando un service_url más fiable y preparado para fallos
    try:
        translator = Translator(service_urls=['translate.googleapis.com'])
    except Exception:
        # Fallback si la inicialización falla
        try:
            translator = Translator()
        except Exception:
            translator = None

    # Traducir cada valor de 'direccion' al catalán ('ca')
    for key, value in list(direccion.items()):
        if not value:
            continue
        # Solo traducir si es texto con letras (evitar códigos postales o números)
        if not (isinstance(value, str) and any(ch.isalpha() for ch in value)):
            continue

        translated_value = value  # fallback al valor original
        if translator is None:
            log(logging.WARNING, sede, "Pending", "El traductor no está disponible; se mantiene el valor original.")
            direccion[key] = translated_value
            continue

        # Intentos con backoff en caso de errores temporales
        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                result = translator.translate(value, dest=target_language)
                # Si la librería devuelve una coroutine (async), la ejecutamos y obtenemos el resultado
                if asyncio.iscoroutine(result):
                    result = asyncio.run(result)
                # Algunas implementaciones devuelven un objeto con atributo .text
                translated = getattr(result, "text", None)
                # Si no tiene .text o es None, usar la representación en cadena del resultado
                if translated is None:
                    if result is None:
                        raise ValueError("translate() returned None")
                    translated = str(result)
                translated_value = translated.strip()
                # Asignar y salir del loop de reintentos
                direccion[key] = translated_value
                break
            except Exception as e:
                # Si es el último intento, mantener el valor original y mostrar advertencia
                if attempt == max_retries:
                    log(logging.ERROR, sede, "Failure", f"Error al traducir {key} tras {max_retries} intentos: {e}; se mantiene '{value}'")
                    direccion[key] = translated_value
                else:
                    # Espera exponencial breve antes de reintentar
                    random_wait(wait_type='SHORT', wait=True)

    
    return direccion

def longest_common_substring(s1:str, s2:str) -> tuple[str, float]:
    def normalizar(texto):
        texto = texto.upper()
        texto = re.sub(r'[^A-ZÁÉÍÓÚÜÑ ]', ' ', texto)
        texto = re.sub(r'\s+', ' ', texto).strip()
        return texto
    
    s1 = normalizar(s1)
    s2 = normalizar(s2)

    m = len(s1)
    n = len(s2)

    dp = [[0] * (n + 1) for _ in range(m + 1)]

    longest = 0
    end_pos = 0

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if s1[i - 1] == s2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
                if dp[i][j] > longest:
                    longest = dp[i][j]
                    end_pos = i
            else:
                dp[i][j] = 0

    match = s1[end_pos - longest:end_pos]

    ratio = round(longest / len(s1), 2) if len(s1) > 0 else 0.0

    return match, ratio
