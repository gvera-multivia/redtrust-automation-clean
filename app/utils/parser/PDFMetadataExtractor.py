import json
import logging
import os
from uuid import uuid4
from dotenv import load_dotenv
import fitz
from app.helper.loggerV2 import LoggerV2  
from app.utils.parser.ORG_EXPEDIENTE_PATTERNS import ORG_EXPEDIENTE_PATTERNS
from difflib import SequenceMatcher

# Longitud máxima de ruta permitida
LONGITUD_MAXIMA_RUTA = 255

class PDFMetadataExtractor:
    def __init__(self, cliente: str = None, message_id : str = None):
        self.cliente = cliente if cliente else "PDFEXTRACTOR"
        self.message_id = message_id if message_id else "DEFAULT_MESSAGE_ID"
    
    def extract_author(self, file_path :str, log:callable) -> str:
        """
        Extrae el autor de un archivo PDF.
        
        :param file_path: Ruta del archivo PDF.
        :return: Autor del PDF o 'Unknown' si no se encuentra.
        """
        try:
            try:
                # Abrir el PDF y obtener sus metadatos
                pdf = fitz.open(file_path)
                metadatos = pdf.metadata       
                item = {'file': os.path.basename(file_path), 'metadatos': metadatos}         
                pdf.close()
            except Exception as e:
                log(logging.ERROR, self.message_id, "Failure", f"Error abriendo el PDF {file_path}: {e}")

            try:
                author, _, _ = self._extract_from_metadata(item)
            except Exception as e:
                log(logging.ERROR, self.message_id, "Failure", f"Error extrayendo metadatos de {file_path}: {e}")
                return 'Unknown'            
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error general al extraer el autor de {file_path}: {e}")
            return 'Unknown'
        finally:
            return author if author else 'Unknown'
    
    def create_metadata_dict(self, directory_path: str, log:callable, save_archives : bool = False) -> list:        
        """
        Crea un diccionario con los metadatos de todos los PDFs en un directorio.
        
        :param directory_path: Ruta del directorio que contiene los PDFs.
        :return: Diccionario con los metadatos de los PDFs.
        """        
        metadatos_lista = []  # Lista para almacenar los metadatos de todos los PDFs

        # Recorrer todas las subcarpetas y archivos
        for root, _, files in os.walk(directory_path):
            log(logging.INFO, self.message_id, "Pending", f"Archivos encontrados en {root}: {len(files)}")

            for archivo in files:
                if archivo.lower().endswith('.pdf'):
                    ruta_pdf = os.path.join(root, archivo)
                    
                    # Verificar si la ruta es demasiado larga
                    if len(ruta_pdf) > LONGITUD_MAXIMA_RUTA:
                        log(logging.WARNING, self.message_id, "Pending", f"Omitiendo archivo por ruta demasiado larga ({len(ruta_pdf)} caracteres): {ruta_pdf}")
                        continue  
                    
                    try:
                        # Abrir el PDF y obtener sus metadatos
                        pdf = fitz.open(ruta_pdf)
                        metadatos = pdf.metadata

                        metadatos_lista.append({'file': archivo, 'metadatos': metadatos})                
                        
                        pdf.close()
                    except Exception as e:
                        log(logging.ERROR, self.message_id, "Failure", f"Error abriendo el PDF {ruta_pdf}: {e}")

        # --- Generar diccionario agrupado por autor/creator/producer ---
        try:
            diccionario_autores = {}
            for item in metadatos_lista:
                try:
                    key, creator, producer = self._extract_from_metadata(item)
                    # Buscar si el autor/clave coincide con algún patrón de ORG_EXPEDIENTE_PATTERNS
                    
                except Exception as e:
                    log(logging.ERROR, self.message_id, "Failure", f"Error extrayendo metadatos de {item['file']}: {e}")
                    continue

                regex_patterns = []
                for org, patterns in ORG_EXPEDIENTE_PATTERNS.items():
                    if key == org:  
                        regex_patterns = patterns  
                        log(logging.INFO, self.message_id, "Pending", f"Patrones encontrados para {org}: {regex_patterns}")

                if key not in diccionario_autores:
                    diccionario_autores[key] = {'creator': '', 'producer': '', 'regex': {}, 'files': []}
                if creator and not diccionario_autores[key]['creator']:
                    diccionario_autores[key]['creator'] = creator
                if producer and not diccionario_autores[key]['producer']:
                    diccionario_autores[key]['producer'] = producer
                if regex_patterns:
                    # Añade solo si no existe ya ese nombre de patrón en 'regex'
                    for reg in regex_patterns:
                        if isinstance(reg, tuple) and len(reg) == 2:
                            pattern, name = reg
                            # Evita duplicados por clave 'name' en la lista de dicts
                            existing_names = {list(r.keys())[0] for r in diccionario_autores[key]['regex'] if isinstance(r, dict) and len(r) == 1}
                            if name not in existing_names:
                                diccionario_autores[key]['regex'][name] = pattern
                    log(logging.INFO, self.message_id, "Pending", f"Expresiones regulares añadidas para {key}: {regex_patterns}")
                if save_archives and item['file'] not in diccionario_autores[key]['files']:
                    diccionario_autores[key]['files'].append(item['file'])


                # Convierte los sets a listas para serializar
            for key in diccionario_autores:
                diccionario_autores[key]['creator'] = diccionario_autores[key]['creator']
                diccionario_autores[key]['producer'] = diccionario_autores[key]['producer']

            # Ordenar el diccionario de autores por clave antes de guardar
            diccionario_autores = dict(sorted(diccionario_autores.items(), key=lambda x: x[0].lower()))
            metadatos_lista.sort(key=lambda x: x.get('file', '').lower())

            output_path = self._append_metadata_to_file(diccionario_autores, log)
            
            log(logging.INFO, self.message_id, "Success", f"Metadatos guardados en {output_path}")
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error general al agrupar o guardar metadatos: {e}")

    def _extract_from_metadata(self, item : dict) -> tuple:
        archivo = item.get('file', '')
        metadatos = item.get('metadatos', {})
        author = metadatos.get('author', None)
        creator = metadatos.get('creator', None)
        producer = metadatos.get('producer', None)
        version = metadatos.get('version', None)
        # Prioriza author, si no existe usa "Unknown - filename"
        key = None
        if author == '':
            author = None
        if creator == '':
            creator = None
        if producer == '':
            producer = None

        if author:
            if author == 'Fluent Engine 23.4.3.2 (java) www.windwardstudios.com' and producer == "iText® 5.5.13.3 ©2000-2022 iText Group NV (Fluent; licensed version)":
                author = 'Ajuntament de Barcelona'
            elif author == 'G5Admin' and creator == 'Microsoft® Word 2016' and producer ==  "Microsoft® Word 2016; modified using iText® 5.5.12 ©2000-2017 iText Group NV (AGPL-version); modified using OpenPDF 1.3.29":
                author = 'Ajuntament de Matadepera'
            elif author == 'Jbenitac' and creator == 'PScript5.dll Version 5.2.2' and producer == 'Acrobat Distiller 15.0 (Windows); modified using iText 2.1.7 by 1T3XT':
                author = 'Diputación de Cadiz'
            elif author == 'Polideportivo' and creator == 'Writer' and producer == 'LibreOffice 7.0; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA':
                author = 'Ayuntamiento de Collado Mediano'
            elif author == 'José Luis Otero López' and creator == 'Microsoft® Word para Microsoft 365' and producer == 'Microsoft® Word para Microsoft 365; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA':
                author = 'Autoridad Portuaria de la Bahía de Cádiz'
            elif author == 'Martín Martín María Elena (Tragsatec)' and producer == "Microsoft: Print To PDF; modified using iTextSharp 5.5.13.2 ©2000-2020 iText Group NV (AGPL-version); modified using iText® 5.3.2 ©2000-2012 1T3XT BVBA (AGPL-version)":
                author = 'Registro Marítimo Español'
            elif author == 'bpgomez' and creator == 'PDFCreator Free 5.0.3' and producer == 'GPL Ghostscript 9.55.0':
                author = 'Ministerio de Hacienda'
            elif author == 'Consultrans' and creator == 'Microsoft Office Word' and producer == 'Cliente @firma; modified using iText 2.1.7 by 1T3XT; modified using iText® 5.3.2 ©2000-2012 1T3XT BVBA (AGPL-version)':                
                author = 'Gobierno de Aragón'
            elif author == "Montse Fernández Dalemus" and creator == "Writer" and producer == "LibreOffice 7.0; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA":
                    author = "Common Rules"
            elif author == 'GESFARMA' and producer == "iText® 5.5.13.3 ©2000-2022 iText Group NV (AGPL-version); modified using iText® 5.5.13.3 ©2000-2022 iText Group NV (AGPL-version); modified using OpenPDF 1.3.26":
                author = 'Ministerio de Sanidad'   

            key = author 
        else:
            if producer == 'iText 2.1.7 by 1T3XT':
                if creator == "Motor de informes de BIRT 3.7.2.v20170213-0100 usando iText /E:/APP/Actuate11SP6/iServer/Jar/BIRT/platform/plugins/org.eclipse.birt.report.engine_3.7.2.v20170213-0100.jar.":
                    key = "Diputació de Valencia"
                elif creator == "BIRT Report Engine /apps/saintsid/9090/ReportEngine/lib/org.eclipse.birt.runtime_3.7.2.v20120214-1408.jar using iText /apps/saintsid/9090/ReportEngine/lib/org.eclipse.birt.runtime_3.7.2.v20120214-1408.jar.":
                    key = "Tesoreria General de la Seguridad Social"
                elif creator == "BIRT Report Engine 3.7.2.v20170213-0100 using iText /E:/app/Actuate11Sp6/iServer/Jar/BIRT/platform/plugins/org.eclipse.birt.report.engine_3.7.2.v20170213-0100.jar.":
                    key = "Ayuntamiento de Peñiscola"
                elif creator is None:
                    if version == "1.4":
                        key = "Organismo Estatal Inspección de Trabajo y Seguridad Social"
                    else:
                        key = "Kit digital" # Inspeccion de Trabajo y Seguridad Social

            elif producer == 'LibreOffice 7.0; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA':
                if creator == "Writer":
                    key = "Ayuntamiento de Begur"
            elif producer == "iText 2.0.5 (by lowagie.com)":
                if creator == "JasperReports (Notificacion716)":
                    key = "Ministerio del Interior"
                if creator == "JasperReports (AV002)":
                    key = "Ministerio del Interior"
                else:
                    key = "Multas DGT"
            elif producer == "Foxit Quick PDF Library 18.11 (www.debenu.com)" :
                if creator == "Foxit Quick PDF Library 18.11 (www.debenu.com)":
                    key = "Ayuntaminto de Madrid"
            elif producer in ["ISIS Papyrus Software AG  ", "ISIS Papyrus Software AG  ; modified using iText® 5.5.0 ©2000-2013 iText Group NV (AGPL-version)"]:
                if creator == "Papyrus Server":
                    key = "Multas Madrid"
            elif producer == "iText® 5.5.13 ©2000-2018 iText Group NV (AGPL-version)":
                if creator == "":
                    key = "Tribunal Municipal de Madrid"
            elif producer == "Microsoft® Access® 2016; modified using iText® 5.2.1 ©2000-2012 1T3XT BVBA":
                if creator == "Microsoft® Access® 2016":
                    key = "Xaloc"
            elif producer == "Aspose.PDF for .NET 21.8.0":
                if creator == "Aspose Ltd.":
                    key = "Common Rules"
            elif producer == "PDFlib+PDI 8.0.6 (.NET/Win32)":
                key = "Ayuntamientos Varios"
            elif producer == "iTextSharp™ 5.5.8 ©2000-2015 iText Group NV (AGPL-version); modified using iText® 5.1.3 ©2000-2011 1T3XT BVBA":
                key = "Aytuntamiento de Sant Celoni"
            elif producer == "Qt 4.8.7; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA":
                if creator == "wkhtmltopdf 0.12.3":
                    key = "Ayuntamiento de Barcelona"
            elif producer == "OpenPDF 1.3.29":
                key = "Ajuntaments de Catalunya"
            elif producer == "Adobe Experience Manager forms output":
                if creator in ["Designer 6.4", "Designer 6.5"]:
                    key = "Diputación de Barcelona"                       
            elif producer and creator == "Microsoft® Word per al Microsoft 365":
                key = "Ajuntament de Barcelona"
            elif producer == "iText 2.1.7 by 1T3XT; modified using iText® 5.2.1 ©2000-2012 1T3XT BVBA":
                if creator == "Motor de informes de BIRT 3.7.2.v20170213-0100 usando iText /E:/App/Actuate11SP6/iServer/Jar/BIRT/platform/plugins/org.eclipse.birt.report.engine_3.7.2.v20170213-0100.jar.":
                    key = "Ayuntamiento de Gijon"  
            elif producer == "iText 2.1.7 by 1T3XT; modified using iText® 5.5.0 ©2000-2013 iText Group NV (AGPL-version)":
                # Si el creator es similar en un 80% a los valores indicados, asignar "Diputació de Tarragona"
                if SequenceMatcher(None, creator, "JasperReports (MGCE001)").ratio() > 0.8:
                    key = "Diputació de Tarragona"
            elif creator == "Crystal Reports" and producer == "Powered By Crystal":
                key = "Ajuntament de Manresa"
            elif creator == "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36" and producer == "Skia/PDF m138":
                key = "Consell Comarcal La Selva"
            elif producer == "Aspose.Words for Java 24.4.0; modified using iText® 5.2.1 ©2000-2012 1T3XT BVBA":
                if creator == "Microsoft Office Word" : 
                    key = "Ayuntamiento de Sant Adria de Besos"
                elif creator is None:
                    key = "Ayuntamiento de Granollers"
            elif producer == "iTextSharp 5.0.5 (c) 1T3XT BVBA" and creator is None:
                key = "Ayuntamiento de Valencia"
            elif producer is None and creator == "Quadient~Inspire~16.0.633.12":
                key = "Common rules" #  Ayuntamiento de Sevilla
            elif producer and creator == "Microsoft® Word 2019":
                key = "Ajuntament del Prat de Llobregat"
            
            
            
            
            
            
            if creator is None:
                if producer == "3-Heights(TM) PDF Producer 4.4.43.2 (http://www.pdf-tools.com)" and creator is None:         
                    key = "Organismo Estatal Inspección de Trabajo y Seguridad Social"
                elif producer == "iText® 5.5.13.4 ©2000-2024 iText Group NV (AGPL-version)":
                    key = "Junta de Andalucía"
                elif producer == "; modified using iText 5.0.1_SNAPSHOT (c) 1T3XT BVBA" and creator is None:
                    key = "Ajuntament de Parets del Vallès"
                elif producer == "iText® 5.5.6 ©2000-2015 iText Group NV (AGPL-version)":
                    key = "Infracciones Administrativas"
                elif producer == "iText® 5.5.13.1 ©2000-2019 iText Group NV (AGPL-version); modified using iText® 5.5.13.1 ©2000-2019 iText Group NV (AGPL-version)":
                    key = "Puertos Baleares"                

        if not key:
            key = f"Unknown - {archivo}"

        return key, creator, producer
    
    def _append_metadata_to_file(self, diccionario_autores: dict, log:callable) -> str:
        """
        Guarda los metadatos en un archivo JSON, haciendo append inteligente.
        """
        output_path = os.path.join(r"\\192.168.184.162\c$\Users\Adria Martinez\Documents\workspace\redtrust-automation\files\resultados", 'autores_creators_producers.json')
        try:
            # Leer el archivo existente si existe
            if os.path.exists(output_path):
                try:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except Exception as e:
                    log(logging.ERROR, self.message_id, "Failure", f"Error leyendo el archivo JSON: {e}")
                    data = {}
            else:
                data = {}
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error comprobando existencia del archivo: {e}")
            data = {}

        # Eliminar claves que empiezan por 'Unknown' en el archivo existente
        try:
            keys_to_delete = [k for k in data if k.startswith("Unknown")]
            for k in keys_to_delete:
                del data[k]
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error eliminando claves Unknown: {e}")

        # Actualizar el diccionario existente con los nuevos datos
        try:
            for key, value in diccionario_autores.items():
                if key in data:
                    # Actualizar creator y producer si están vacíos
                    if not data[key].get('creator') and value.get('creator'):
                        data[key]['creator'] = value['creator']
                    if not data[key].get('producer') and value.get('producer'):
                        data[key]['producer'] = value['producer']

                    # Merge 'regex' dictionaries
                    if 'regex' not in data[key] or not isinstance(data[key]['regex'], dict):
                        data[key]['regex'] = {}
                    if 'regex' in value and isinstance(value['regex'], dict):
                        for reg_name, reg_pattern in value['regex'].items():
                            if reg_name not in data[key]['regex']:
                                data[key]['regex'][reg_name] = reg_pattern
                else:
                    data[key] = value
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error actualizando el diccionario de autores: {e}")

        # Ordenar alfabéticamente antes de guardar
        try:
            sorted_data = dict(sorted(data.items(), key=lambda x: x[0].lower()))
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log(logging.ERROR, self.message_id, "Failure", f"Error guardando el archivo JSON: {e}")
        
        return output_path

if __name__ == "__main__":
    # Configura los parámetros necesarios
    cliente = "PDFEXTRACTOR"
    message_id = "DEFAULT_MESSAGE_ID"
    execution_id = uuid4()
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
                cliente="PDFParser",
                task_id=task_id,
                result=result,
                message=message
            )

        except Exception as e:
            default_logger = LoggerV2(
                execution_id=execution_id,
                module="Descargas", 
                class_name="LogListener", 
                log_dir=r"logs\descargas"
                )
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")

    load_dotenv()
    extractor = PDFMetadataExtractor(cliente, message_id)
    # directory_path = os.path.join(r"C:\Users\Adria Martinez\Documents\workspace\redtrust-automation\files\examples")
    directory_path = os.path.join(rf"\{os.getenv('DOWNLOAD_DIR')}", "revisar", "20250802", "sin-expediente")

    log_queue(logging.INFO, message_id, "Pending", f"Extrayendo metadatos de PDFs en {directory_path}")
    extractor.create_metadata_dict(directory_path, log_queue, save_archives=True)
    log_queue(logging.INFO, message_id, "Success", f"Metadatos extraídos y guardados correctamente en {directory_path}")

    

