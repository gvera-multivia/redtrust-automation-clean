from datetime import datetime
import json
import logging
from queue import Queue
import re
import time
from uuid import uuid4
from dotenv import load_dotenv
import fitz  # PyMuPDF
import pytesseract
from PIL import Image
import io
import os
import cv2
import numpy as np

from app.helper.loggerV2 import LoggerV2
from app.utils.parser.ORG_EXPEDIENTE_PATTERNS import ORG_EXPEDIENTE_PATTERNS
from app.utils.parser.PDFMetadataExtractor import PDFMetadataExtractor

pytesseract.pytesseract.tesseract_cmd = r'\\192.168.184.162\c$\Users\Adria Martinez\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
# Ensure TESSDATA_PREFIX is set for pytesseract
if not os.environ.get('TESSDATA_PREFIX'):
    os.environ['TESSDATA_PREFIX'] = r'\\192.168.184.162\c$\Users\Adria Martinez\AppData\Local\Programs\Tesseract-OCR\tessdata'
pytesseract.pytesseract.tesseract_cmd = r'\\192.168.184.162\c$\Users\Adria Martinez\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'

class PDFOCRParser:
    def __init__(self, cliente: str, message_id : str, pdf_path:str, author: str = None):
        self.pdf_path = pdf_path
        self.doc = fitz.open(pdf_path)
        self.author = author 
        self.cliente = cliente if cliente else "PDFOCRParser"
        self.message_id = message_id if message_id else "DEFAULT_MESSAGE_ID"
        # print(os.environ['TESSDATA_PREFIX'])


    def process_pages(self, log:callable, show: bool = False):
        try:
            # Procesar solo la primera página
            if len(self.doc) > 0:
                for index, page in enumerate(list(self.doc)[:3]):
                    page = self.doc[0]
                    log(logging.INFO, self.message_id, "Pending", f"Procesando la página {index} para {self.pdf_path}")

                    # Renderizar página como imagen
                    pix = page.get_pixmap(dpi=400)
                    img_data = pix.tobytes("ppm")
                    img = Image.open(io.BytesIO(img_data))

                    # # OCR con pytesseract (ajustando parámetros para mejor detección de líneas)
                    # custom_config = r'--oem 3 --psm 6'
                    # text = pytesseract.image_to_string(img, lang='spa', config=custom_config)
                    # Renderizar página como imagen

                    # OCR con pytesseract
                    text = pytesseract.image_to_string(img, lang='spa')
                    lines = text.splitlines()
                    for line in lines:
                        if show:
                            print(f"{line.strip()}")
                        if self.author == 'Multas Madrid' and "REFERENCIA DEL EXPEDIENTE" in line.strip():
                            next_idx = lines.index(line) + 1
                            if next_idx < len(lines):
                                next_line = lines[next_idx]
                                expediente = next_line.split('NOTIFI')[0].strip()
                                if expediente:
                                    log(logging.INFO, self.message_id, "Success", f"Expediente encontrado tras referencia: {expediente} - Regla: Multas Madrid - Org: Multas Madrid - Linea: {next_line}")
                                    return expediente, rule, self.author
                        elif self.author == 'Ministerio del interior' and "N. EXPEDIENTE" in line.strip():
                            next_idx = lines.index(line) + 1
                            if next_idx < len(lines):
                                next_line = lines[next_idx]
                                expediente, rule, org = self.extract_expediente(line)
                                if expediente:
                                    log(logging.INFO, self.message_id, "Success", f"Expediente encontrado: {expediente} - Regla: Ministerio del Interior - Org: Ministerio del Interior - Linea: {line}")                        
                                    return self.sanitize_expediente(expediente), rule, org
                        elif self.author is not None:                                                                                         
                            expediente, rule, org = self.extract_expediente(line)
                            if expediente:
                                log(logging.INFO, self.message_id, "Success", f"Expediente encontrado: {expediente} - Regla: {rule} - Org: {org} - Linea: {line}")                        
                                return self.sanitize_expediente(expediente), rule, org
                        else:
                            self.author = "Common Rules"
                            expediente, rule, org = self.extract_expediente(line)
                            if expediente:
                                log(logging.INFO, self.message_id, "Success", f"Expediente encontrado: {expediente} - Regla: {rule} - Org: {org} - Linea: {line}")
                                return self.sanitize_expediente(expediente), rule, org
            
                    if show:
                        self._show_ocr_boxes(img, log)
                        
            return None, None, None
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error processing PDF {self.pdf_path}: {e}")
            return None, None, None
        finally:
            self.doc.close()

    
    def sanitize_expediente(self, expediente):
        if expediente:
            expediente = expediente.replace('/', '-').replace('\\', '-')
            expediente = expediente.replace('[', '').replace(']', '')
            expediente = expediente.replace('(', '').replace(')', '')
            expediente = expediente.replace('{', '').replace('}', '')
        return expediente

    def extract_expediente(self, text):
        if self.author and self.author in ORG_EXPEDIENTE_PATTERNS:
            patterns = ORG_EXPEDIENTE_PATTERNS[self.author]
            if isinstance(patterns, dict):
                for suborg, subpatterns in patterns.items():
                    for pattern, rule_name in subpatterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            if match.lastindex and match.lastindex >= 1:
                                return match.group(1), rule_name, f"{self.author} - {suborg}"
                            else:
                                return match.group(0), rule_name, f"{self.author} - {suborg}"
            else:
                for pattern, rule_name in patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        if match.lastindex and match.lastindex >= 1:
                            return match.group(1), rule_name, self.author
                        else:
                            return match.group(0), rule_name, self.author
        else:
            for org, patterns in ORG_EXPEDIENTE_PATTERNS.items():
                # If patterns is a dict (e.g., "Ayuntamientos"), iterate its values
                if isinstance(patterns, dict):
                    for suborg, subpatterns in patterns.items():
                        for pattern, rule_name in subpatterns:
                            match = re.search(pattern, text, re.IGNORECASE)
                            if match:
                                if match.lastindex and match.lastindex >= 1:
                                    return match.group(1), rule_name, f"{org} - {suborg}"
                                else:
                                    return match.group(0), rule_name, f"{org} - {suborg}"
                else:
                    for pattern, rule_name in patterns:
                        match = re.search(pattern, text, re.IGNORECASE)
                        if match:
                            if match.lastindex and match.lastindex >= 1:
                                return match.group(1), rule_name, org
                            else:
                                return match.group(0), rule_name, org
        return None, None, None

    def _show_ocr_boxes(self, pil_img, log:callable, scale=0.25):
        img_cv = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)

        for i in range(len(data['level'])):
            (x, y, w, h) = (data['left'][i], data['top'][i], data['width'][i], data['height'][i])
            cv2.rectangle(img_cv, (x, y), (x + w, y + h), (0, 255, 0), 2)

        # 🔍 Reducir el tamaño de la imagen
        width = int(img_cv.shape[1] * scale)
        height = int(img_cv.shape[0] * scale)
        img_resized = cv2.resize(img_cv, (width, height), interpolation=cv2.INTER_AREA)

        # Mostrar
        cv2.imshow('OCR Result (Zoom reducido)', img_resized)

        log(logging.INFO, self.message_id, "Pending", "Mostrando resultado OCR con cajas de detección, pulsa cualquier tecla para cerrar.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()

def seleccionar_pdf(execution_id: str):
    from tkinter import Tk
    from tkinter.filedialog import askopenfilename

    Tk().withdraw()  # Ocultar ventana principal
    file_path = askopenfilename(filetypes=[("PDF files", "*.pdf")])
    if file_path:
        def log_queue(level: str | int, task_id: str, result: str, message: str) -> None:
            try:
                logger = LoggerV2(
                    execution_id=execution_id,
                    module="Descargas", 
                    class_name="PDFParser", 
                    log_dir="logs", 
                    filename="pdf_parser"
                )

                # Mapear nivel de log a método del logger
                log_method = {
                    logging.ERROR: logger.error,
                    logging.WARNING: logger.warning,
                    logging.DEBUG: logger.debug,
                    logging.INFO: logger.info
                }.get(level, logger.info)

                log_method(
                    cliente="PDF",
                    task_id=task_id,
                    result=result,
                    message=message
                )

            except Exception as e:
                default_logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="LogListener", log_dir=r"logs\descargas",)
                default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")
        cliente = "PDF"
        task_id = "Parser"
        extractor = PDFMetadataExtractor()
        # Extract metadata
        author = extractor.extract_author(file_path, log_queue)

        parser = PDFOCRParser(
            cliente=cliente,
            message_id=task_id,
            pdf_path=file_path,
            author=author
        )
        expediente, rule, org = parser.process_pages(log=log_queue)
        log_queue(logging.INFO, task_id, "Success", f"Expediente encontrado: {expediente} (Regla: {rule}, Org: {org})")


def main():    
    execution_id = uuid4()
    def log_queue(level: logging._Level, task_id: str, result: str, message: str) -> None:
        try:
            logger = LoggerV2(
                execution_id=execution_id,
                module="Descargas", 
                class_name="PDFParser", 
                log_dir="logs", 
                filename="pdf_parser"
            )

            # Mapear nivel de log a método del logger
            log_method = {
                logging.ERROR: logger.error,
                logging.WARNING: logger.warning,
                logging.DEBUG: logger.debug,
                logging.INFO: logger.info
            }.get(level, logger.info)

            log_method(
                cliente="PDF",
                task_id=task_id,
                result=result,
                message=message
            )

        except Exception as e:
            default_logger = LoggerV2(execution_id=execution_id, module="Descargas", class_name="LogListener", log_dir=r"logs\descargas")
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

        

    start_time = time.time()
    logger = LoggerV2(
        execution_id=execution_id,
        module="Descargas", 
        class_name="PDFParser", 
        log_dir="logs", 
        filename="pdf_parser"
    )
    cliente = "PDF"
    task_id = "Parser"
    logger.info(cliente, task_id, "Info", f"Start PDF parsing at {datetime.now()}")

    load_dotenv()
    folder_path = r"\\SERVER-DOC\dptos multivia\4 DPTO -  JURIDICO\CARPETAS VIRTUALES\PARA REVISAR - - - DEV Y ORGANISMOS LLAMADOS\ANNA Descargas\Adria Descargas\revisar"
    # folder_path = r"C:\Users\Adria Martinez\Documents\workspace\redtrust-automation\files\revisar\sin-expediente"

    result_dict = {}
    if not os.path.exists(folder_path):
        logger.error(cliente, task_id, "Failure", f"Folder not found: {folder_path}")
        return

    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf') ] #and f.startswith(date_prefix)
    if not pdf_files:
        logger.warning(cliente, task_id, "Info", f"No PDF files found in {folder_path}") #  with prefix {date_prefix}
        return

    for filename in pdf_files:
        extractor = PDFMetadataExtractor(
            logger=logger
        )
        # Extract metadata
        author = extractor.extract_author(os.path.join(folder_path, filename))
        pdf_path = os.path.join(folder_path, filename)
        pdfOCR = PDFOCRParser(
            cliente=cliente,
            message_id=task_id,
            log=log_queue,
            pdf_path=pdf_path,
            author=author
        )
        expediente, rule, org = pdfOCR.process_pages(log_queue)
        
        result_dict[filename] = {
            "organization": org,
            "expediente": expediente,
            "rule": rule,
            "found": expediente is not None
        }
        logger.info(cliente, task_id, "Info", f"File: {filename} | Org: {org} | Expediente: {expediente}, Rule: {rule}")

    elapsed = time.time() - start_time
    logger.info(cliente, task_id, "Info", f"Elapsed time: {elapsed:.2f} seconds")

    # Save result to JSON
    output_dir = r"\\192.168.184.162\c$\Users\Adria Martinez\Documents\workspace\redtrust-automation\files\resultados"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"expediente_results.json")
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        logger.info(cliente, task_id, "Success", f"Result saved to {output_path}")
    except Exception as e:
        logger.error(cliente, task_id, "Failure", f"Error saving result: {e}")
        

if __name__ == "__main__":
    # main()
    seleccionar_pdf(execution_id=str(uuid4()))
