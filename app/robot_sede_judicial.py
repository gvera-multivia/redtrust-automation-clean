import logging
import os, time, json, argparse
from datetime import datetime
from typing import Dict, List, Any, Optional
from uuid import uuid4
import re
import uuid

# THIRD PARTY PACKAGES
from dotenv import load_dotenv
from multiprocessing import Process, Manager, Queue

# PERSONAL PACKAGES - ROBOTS
from app.helper.errors.redtrust import ErrorRedtrust
from app.models.database_models import (
    HistoricoAutomatizaciones,
    SedeJudicialAutomatizaciones,
    ExpedienteJudicial,
    SeñalamientoJudicial,
    JusticiaGratuitaJudicial,
    HitosProcesalesExpediente,
    IntervinientesExpediente,
    OtrosProcedimientosExpediente,
)
from decimal import Decimal
from app.redtrust.redtrust_manager import RedTrustManager
from database.sedejudicial.database_sedejudicial import SedeJudicialDatabase
from app.robot.handle_certificate import CertificateManager

# PERSONAL PACKAGES - ROBOTS SEU JUDICIAL
from app.robot.sedejudicial.RobotSeuJudicialGencat import RobotSeuJudicialGencat
from app.models.database_models import SedeJudicialAutomatizaciones

# PERSONAL PACKAGES - UTILS
from app.utils.utils import random_wait
from app.helper.loggerV2 import LoggerV2
from types import SimpleNamespace

date = datetime.now().strftime("%Y%m%d")

def run_portal_robot_static(logger: LoggerV2, robot_class: RobotSeuJudicialGencat, cliente: str, sede: str, result_queue: List):
    try:
        logger.info(cliente, sede, "Pending", f"Starting portal robot for task {cliente} (type: {sede})")

        check, datatables = robot_class.inspect()
        if check: 
            result_queue.append((f"{cliente}-{sede}", 'completed', datatables))
        else:
            result_queue.append((f"{cliente}-{sede}", 'error', {'error': 'Inspection failed'}))
            logger.error(cliente, sede, "Failure", f"⚠️ No result from portal robot for task {cliente}")
    except Exception as e:
        logger.error(cliente, sede, "Failure", f"⚠️ Error in portal robot for task {cliente} : {e}")
        result_queue.append((f"{cliente}-{sede}", 'error', {'error': str(e)}))

def run_certificate_handler_static(logger : LoggerV2, cliente: str, sede: str, recipient:str, execution_id:str, result_queue: List):
    certificate_manager = CertificateManager(
        cliente = cliente,
        task_id = sede,
        sede = sede.lower(),
        date = date,
        module="SedeJudicial",
        filename=f"sedejudicial",
        execution_id=execution_id
    )
    try:
        logger.info(cliente, sede, "Pending", f"Starting certificate handler for task {sede}")
        result = certificate_manager.handle_certificate(recipient)
        if result:
            logger.info(cliente, sede, "Success", f"Certificate handler for task {sede} completed with result: {result}")
            result_queue.append((sede, 'certificate_handled', result))
        else:
            logger.error(cliente, sede, "Failure", f"Certificate handler for task {sede} failed. Retrying...")
            result_queue.append((sede, 'certificate_handled', False))
    except Exception as e:
        logger.error(cliente, sede, "Failure", f"⚠️ Error in certificate handler for task {sede}: {e}")
        result_queue.append((sede, 'certificate_handled', False)) 

def log_listener(queue:Queue, date:str, execution_id: str):
    """Escucha logs y escribe con el logger adecuado por clase/tarea."""
    loggers = {}

    while True:
        try:
            record = queue.get()
            if record is None:
                break

            # Obtener o crear el logger basado en módulo y clase
            key = (record["module"], record["class_name"])
            if key not in loggers:
                loggers[key] = LoggerV2(
                    execution_id=execution_id,
                    module=record["module"],
                    class_name=record["class_name"],
                    filename=f"SedeJudicial",
                    log_dir=r"logs\sedejudicial",
                )

            logger = loggers[key]
            level = record.get("level", logging.INFO)

            # Mapear nivel de log a método del logger
            log_method = {
                logging.ERROR: logger.error,
                logging.WARNING: logger.warning,
                logging.DEBUG: logger.debug,
                logging.INFO: logger.info
            }.get(level, logger.info)


            log_method(
                cliente=record["cliente"],
                task_id=record["task_id"],
                result=record["result"],
                message=record["message"]
            )


        except Exception as e:
            default_logger = LoggerV2(execution_id=execution_id, module="SedeJudicial", class_name="LogListener", log_dir=r"logs\sedejudicial",)
            default_logger.error("Listener", "Main", "Failure", f"Log listener failed: {e}")
                  
class RobotSedeJudicial:
    """
    Main class to manage the execution of multiple robots in parallel
    """
    load_dotenv(dotenv_path='.env', override=True)
    db_config = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "server": os.getenv("DB_SERVER"),
        "database": os.getenv("DB_NAME"),
        "options": {
            "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
            "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
        }
    }

    def __init__(self, execution_id : str, db_path: str = "robots.db"):
        self.db_path = db_path
        self.tasks = []
        self.results = {}
        self.lock = None  # Si usas threading, puedes inicializar un Lock
        self.default_date = date

        # Progreso 
        self.total_tasks = 0
        self.completed_tasks = 0
        self.progress = 0.0
        self.progress_by_task = {}  # (cliente, sede): porcentaje

        # Initialize logger
        self.execution_id = execution_id
        self.logger = LoggerV2(
            execution_id=self.execution_id,
            module="SedeJudicial",
            class_name=self.__class__.__name__,
            log_dir="logs/sedejudicial",
            filename=f"sedejudicial"
        )

        # Managers
        self.database_manager = SedeJudicialDatabase(
            db_config=self.db_config, 
            date = self.default_date,  
            module="SedeJudicial",
            filename=f"sedejudicial",
            execution_id=self.execution_id
        )

        self.redtrust_manager = None  
        self.certificate_manager = None 
        self.robot = None  # Inicializar más tarde

    def calcular_total_tasks(self, tasks):
        total = len(tasks)
        self.total_tasks = total
        self.logger.info("GLOBAL", "RUN", "Info", f"Total de tareas a ejecutar: {self.total_tasks}")

    def actualizar_progreso_fase(self, fase: str, extra: str = ""):
        fases_pesos = {
            'db_fetch': 15,
            'carga_certificados': 15,
            'ejecucion_tarea': 70,
            'finalizado': 0,  # <-- Add this line
        }
        if not hasattr(self, '_progreso_fases'):
            self._progreso_fases = {k: False for k in fases_pesos}
            self._progreso_base = 0
            self._progreso_tarea_unit = 0
        if fase != 'ejecucion_tarea' and not self._progreso_fases[fase]:
            self._progreso_base += fases_pesos[fase]
            # Set progress to 100% if finalizado
            if fase == 'finalizado':
                self.progress = 100.0
            else:
                self.progress = self._progreso_base
            self._progreso_fases[fase] = True
            self.logger.info("GLOBAL", "RUN", "Info", f"Progreso: {self.progress:.2f}% - Fase completada: {fase}. {extra}")
        elif fase == 'ejecucion_tarea':
            self.completed_tasks += 1
            if self.total_tasks > 0:
                self._progreso_tarea_unit = fases_pesos['ejecucion_tarea'] / self.total_tasks
            else:
                self._progreso_tarea_unit = 0
            self.progress = self._progreso_base + self.completed_tasks * self._progreso_tarea_unit
            self.logger.info("GLOBAL", "RUN", "Info", f"Progreso: {self.progress:.2f}% - Ejecutada tarea {self.completed_tasks} de {self.total_tasks}. {extra}")

    def _load_certificate(self, certificate_id: str) -> bool:
        try:
            if self.redtrust_manager is None:
                credentials = {
                    "usuario": os.getenv("USUARIO"),
                    "password": os.getenv("PASSWORD")
                }
                self.redtrust_manager = RedTrustManager(
                    cliente = certificate_id,
                    execution_id=self.execution_id,                    
                    credentials=credentials, 
                    date = self.default_date,  
                    module="SedeJudicial",
                    filename=f"sedejudicial"
                )
            success = self.redtrust_manager.automate_redtrust(certificate_id)
            if success:
                self.logger.info(certificate_id, "CERTIFICATE", "Success", f"Certificate {certificate_id} loaded successfully")
            else:
                self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRedtrust.CertificateLoad(certificate_id))
            return success
        except Exception as e:
            self.logger.error(certificate_id, "CERTIFICATE", "Failure", ErrorRedtrust.CertificateLoad(certificate_id))
            return False

    def _build_db_models(self, execution_id: str, resultado: Dict[str, Any]):
        """
        Construye instancias Pydantic (estrictas) a partir del JSON de resultado.
        Realiza conversiones de tipo y validaciones (fechas -> datetime,
        importes -> Decimal, emails validados por Pydantic, UUIDs generados,
        etc.). Devuelve una tupla:
        (sede_model, [ExpedienteJudicial...], [SeñalamientoJudicial...], justicia_list)
        """
        def parse_date(val: Any) -> Optional[datetime]:
            if not val:
                return None
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                # try dd/mm/YYYY
                for fmt in ("%d/%m/%Y", "%d/%m/%Y %H:%M", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(val.strip(), fmt)
                    except Exception:
                        continue
            return None

        def parse_decimal(val: Any) -> Optional[Decimal]:
            if val is None:
                return None
            try:
                if isinstance(val, (int, float, Decimal)):
                    return Decimal(str(val))
                if isinstance(val, str):
                    s = val.replace('.', '').replace(',', '.') if ',' in val and '.' in val else val.replace(',', '.')
                    return Decimal(s)
            except Exception:
                return None
            return None

        try:
            expedients = resultado.get('expedients') or resultado.get('expedients') or []
            señalaments = resultado.get('assenyalaments') or resultado.get('assenyalaments') or []
            justicia = resultado.get("justícia gratuïta") or resultado.get('justícia gratuïta') or resultado.get('justicia gratuita') or []

            # create a sede id to link expedientes
            sede_id = uuid4()

            expedientes_models: List[ExpedienteJudicial] = []
            señalamientos_models: List[SeñalamientoJudicial] = []
            for row in expedients:
                nested = None
                for k in list(row.keys()):
                    if isinstance(k, str) and k.lower().startswith('detalles'):
                        nested = row.get(k) or {}
                        break

                def _get(d, *cands):
                    if not d:
                        return None
                    for c in cands:
                        if c in d:
                            return d[c]
                        for kk in d.keys():
                            try:
                                if kk.lower() == c.lower():
                                    return d[kk]
                            except Exception:
                                continue
                    return None

                exp_id = uuid4()
                any_expediente = _get(row, 'any', 'any_expediente', 'Any')
                try:
                    any_expediente = int(any_expediente) if any_expediente is not None and str(any_expediente).isdigit() else any_expediente
                except Exception:
                    any_expediente = None

                fecha_expediente = parse_date(_get(row, 'data', 'fecha', 'fecha_expediente'))
                organo = _get(row, "òrgan judicial", 'òrgan_judicial', 'òrgan', 'organo_judicial', 'Òrgan judicial')
                procedimiento = _get(row, 'procediment', 'procedimiento', 'Procediment')
                numero_any = _get(row, 'número/any/secció', 'número/any', 'Número/Any/Secció', 'número_any_secció')
                nig = _get(row, 'NIG', 'nig')
                ambito = _get(row, 'Àmbit', 'ambit', 'ambito')
                num_demanda = _get(row, 'Núm. de la demanda', 'Num. de la demanda', 'número de la demanda')

                datos_registro = _get(nested, "Dades de registre") or _get(nested, 'Dades de registre') or {}
                fecha_presentacion = parse_date(_get(datos_registro, 'Data de presentació', 'Data de presentacion', 'fecha_presentacion') or _get(nested, 'Data de presentació'))
                fecha_registro = parse_date(_get(datos_registro, 'Data de registre', 'Data de registro') or _get(nested, 'Data de registre'))

                datos_proced = _get(nested, "Dades del procediment") or {}
                importe_principal = parse_decimal(_get(datos_proced, 'Import principal') or _get(datos_proced, 'Import principal', 'Importe principal'))
                tipo_quantia = _get(datos_proced, 'Tipus de quantia', 'Tipo de quantia', 'Tipus de quantia')

                estado = _get(row, 'Estat', 'estado', 'Estado') or _get(nested, 'Estat')
                juzgado = _get(nested, 'Jutjat') or _get(row, 'Jutjat')
                fecha_incoacion = parse_date(_get(row, "Data d'incoació", 'Data d\'incoació', 'Data d\'incoacio') or _get(nested, "Data d'incoació"))
                fase = _get(row, 'Fase')

                # Otros procedimientos
                otros_models: List[OtrosProcedimientosExpediente] = []
                otros = _get(nested, 'Altres procediments') or _get(row, 'Altres procediments') or _get(nested, 'Altres procediments', {})
                if isinstance(otros, dict):
                    for date_key, val in otros.items():
                        if not isinstance(val, dict):
                            continue
                        fecha_proc = parse_date(val.get('Data') or date_key)
                        op = OtrosProcedimientosExpediente(
                            id=uuid4(),
                            expediente_judicial_id=sede_id,
                            fecha_procedimiento=fecha_proc,
                            estado_procedimiento=val.get('Estat') or val.get('Estado'),
                            tipo_procedimiento=val.get('Procediment') or val.get('Procedimiento'),
                            numero_año=val.get('Número/any') or val.get('Número/Any/Secció'),
                            organo_judicial=val.get('Òrgan judicial') or val.get('Òrgan')
                        )
                        otros_models.append(op)
                elif isinstance(otros, list):
                    for val in otros:
                        if not isinstance(val, dict):
                            continue
                        fecha_proc = parse_date(val.get('Data') or val.get('data'))
                        op = OtrosProcedimientosExpediente(
                            id=uuid4(),
                            expediente_judicial_id=sede_id,
                            fecha_procedimiento=fecha_proc,
                            estado_procedimiento=val.get('Estat') or val.get('Estado'),
                            tipo_procedimiento=val.get('Procediment') or val.get('Procedimiento'),
                            numero_año=val.get('Número/any') or val.get('Número/Any/Secció'),
                            organo_judicial=val.get('Òrgan judicial') or val.get('Òrgan')
                        )
                        otros_models.append(op)

                # Intervinientes
                intervinientes_models: List[IntervinientesExpediente] = []
                inters = _get(nested, 'Intervinents') or _get(row, 'Intervinents') or []
                if isinstance(inters, list):
                    for p in inters:
                        role = p.get('role') or _get(p, 'Role') or ''
                        ident = p.get('Identificació de la persona') or p.get('Identificació de la persona') or p.get('Identificacion de la persona') or {}
                        contact = p.get('Dades de contacte') or p.get('Dades de contacte') or {}
                        nombre = None
                        if isinstance(ident, dict):
                            nombre = ident.get('Nom') or ident.get('Nom i cognoms') or ident.get('Nombre')
                        correo = None
                        if isinstance(contact, dict):
                            correo = contact.get('Correu electrònic') or contact.get('Correu electrònic') or contact.get('Correu electronic') or contact.get('Correu') or contact.get('Correo')
                        try:
                            inter_model = IntervinientesExpediente(
                                id=uuid4(),
                                expediente_judicial_id=sede_id,
                                nombre_interviniente=nombre,
                                rol_interviniente=role,
                                correo_electronico=correo,
                                direccion=(', '.join([str(contact.get('Tipus de via') or ''), str(contact.get('Nom de la via') or ''), str(contact.get('Número') or '')]).strip()) if isinstance(contact, dict) else None,
                                poblacion=contact.get('Població') or contact.get('Poblacion') or contact.get('Municipi'),
                                municipio=contact.get('Municipi') or contact.get('Municipi') or contact.get('Municipio'),
                                provincia=contact.get('Província') or contact.get('Provincia') or contact.get('Provincía'),
                                pais=contact.get('País') or contact.get('Pais') or contact.get('Pais'),
                                codigo_postal=contact.get('Codi postal') or contact.get('Codi_postal') or contact.get('CodiPostal'),
                                telefono=contact.get('Telèfon') or contact.get('Teléfono') or contact.get('Telefono')
                            )
                            intervinientes_models.append(inter_model)
                        except Exception:
                            # skip invalid interviniente (invalid email etc.)
                            continue
                
                dades_tramitacio = _get(nested, 'Dades de la tramitació') or _get(nested, "dades de la tramitació") or []
                # Hitos procesales
                hitos_models: List[HitosProcesalesExpediente] = []
                fites = _get(dades_tramitacio, 'Fites processals') or _get(dades_tramitacio, "Fites processals") or []
                if isinstance(fites, list):
                    for item in fites:
                        if isinstance(item, dict):
                            for kk, vv in item.items():
                                # if kk looks like a date, parse
                                if isinstance(kk, str) and re.match(r"\d{2}/\d{2}/\d{4}", kk):
                                    fecha_h = parse_date(kk)
                                    try:
                                        h_model = HitosProcesalesExpediente(
                                            id=uuid4(),
                                            expediente_judicial_id=sede_id,
                                            fecha_hito=fecha_h,
                                            descripcion_hito=vv,
                                            fecha_resolucion=None,
                                            fecha_incoacion=None
                                        )
                                        hitos_models.append(h_model)
                                    except Exception:
                                        continue
                
                    
                agenda = _get(dades_tramitacio, "Agenda d'assenyalaments") or _get(dades_tramitacio, "agenda d'assenyalaments") or []
                # Support both dict and list representations
                if isinstance(agenda, dict):
                    items = list(agenda.items())
                elif isinstance(agenda, list):
                    items = []
                    for it in agenda:
                        if isinstance(it, dict):
                            items.extend(it.items())
                else:
                    items = []

                # Skip the first item because it contains headers
                if len(items) > 0:
                    items = items[1:]

                for kk, vv in items:
                    try:
                        if not isinstance(vv, dict):
                            continue
                        # Prefer key when it's a date-like string, otherwise use vv.get('Data')
                        date_candidate = kk if isinstance(kk, str) and re.match(r"\d{2}/\d{2}/\d{4}", kk) else vv.get('Data') or kk
                        fecha_h = parse_date(date_candidate)
                        if fecha_h is None:
                            continue

                        señ_model = SeñalamientoJudicial(
                            id=uuid4(),
                            sedejudicial_id=sede_id,
                            expediente_judicial_id=exp_id,
                            fecha_señalamiento=fecha_h,
                            hora_inicio=vv.get("Hora d'inici") or vv.get('Hora inicio') or vv.get('hora_inicio'),
                            hora_fin=vv.get("Hora d'acabament") or vv.get('Hora fin') or vv.get('hora_fin'),
                            sala=vv.get('Sala'),
                            estado=vv.get('Estat') or vv.get('Estado') or vv.get('estado'),
                            motivo_anulacion=vv.get("Motiu de l'anul·lació") or vv.get("Motiu de l'anulacio") or vv.get('motivo_anulacion'),
                            procedimiento=vv.get('Procediment') or vv.get('Procedimiento') or vv.get('procedimiento'),
                            created_at=datetime.now(),
                            updated_at=None
                        )
                        señalamientos_models.append(señ_model)
                    except Exception:
                        continue

                # Build ExpedienteJudicial (pydantic)
                try:
                    expediente = ExpedienteJudicial(
                        id=exp_id,
                        sedejudicial_id=sede_id,
                        any_expediente=any_expediente,
                        fecha_expediente=fecha_expediente,
                        organo_judicial=organo,
                        procedimiento=procedimiento,
                        numero_any_seccion=numero_any,
                        nig=nig,
                        ambito=ambito,
                        num_demanda=num_demanda,
                        fecha_presentacion=fecha_presentacion,
                        fecha_registro=fecha_registro,
                        estado_expediente=estado,
                        juzgado=juzgado,
                        fecha_incoacion=fecha_incoacion,
                        fase=fase,
                        tipo_quantia=tipo_quantia,
                        importe_principal=importe_principal,
                        otros_procedimientos=otros_models,
                        intervinientes=intervinientes_models,
                        hitos_procesales=hitos_models,
                        created_at=datetime.now(),
                        updated_at=None
                    )
                    expedientes_models.append(expediente)
                except Exception as e:
                    # skip invalid expediente and log
                    self.logger.error('GLOBAL', 'BUILD_MODELS', 'Failure', f"Invalid expediente skipped: {e}")
                    continue

            # Señalamientos
            for s in señalaments:
                try:
                    se_model = SeñalamientoJudicial(
                        id=uuid4(),
                        sedejudicial_id=sede_id,
                        expediente_judicial_id=None,
                        fecha_señalamiento=parse_date(s.get('data') or s.get('Data') or s.get('fecha')),
                        hora_inicio=s.get("Hora d'inici") or s.get('Hora inicio') or s.get('hora_inicio'),
                        hora_fin=s.get("Hora d'acabament") or s.get('Hora fin') or s.get('hora_fin'),
                        sala=s.get('Sala') or s.get('sala'),
                        estado=s.get('Estat') or s.get('estado') or s.get('Estado'),
                        motivo_anulacion=s.get('Motiu de l\'anul·lació') or s.get('Motiu de l\'anulacio') or s.get('motivo_anulacion'),
                        procedimiento=s.get('Procediment') or s.get('procediment') or s.get('procedimiento'),
                        created_at=datetime.now(),
                        updated_at=None
                    )
                    señalamientos_models.append(se_model)
                except Exception as e:
                    self.logger.error('GLOBAL', 'BUILD_MODELS', 'Failure', f"Invalid señalamaiento skipped: {e}")
                    continue
            
            justicicagratuita_models: List[JusticiaGratuitaJudicial] = []
            for j in justicia:
                try:
                    jg_id = uuid4()
                    jg_model = JusticiaGratuitaJudicial(
                        id=jg_id,
                        sedejudicial_id=sede_id,
                        codi_expedient=j.get('codi expedient') or j.get('Código expediente') or j.get('codi_expedient'),
                        organ_judicial=j.get('òrgan judicial') or j.get('Órgano judicial') or j.get('organ_judicial'),
                        procediment=j.get('procediment') or j.get('Procedimiento') or j.get('procediment'),
                        n_act=j.get("n.act.") or j.get("Núm. de acte") or j.get('Número de acto') or j.get('n_act'),
                        estat=j.get('estat') or j.get('Estat') or j.get('Estado'),
                        dictamen=j.get('Dictamen') or j.get('dictamen'),
                        sentit_resolucio_final=j.get('sentit resolució final') or j.get('Sentido resolución final') or j.get('sentit_resolucio_final'),
                        tipologia_resolucio=j.get('tipologia resolució') or j.get('Tipología resolución') or j.get('tipologia_resolucio'),
                        created_at=datetime.now(),
                        updated_at=None
                    )

                    justicicagratuita_models.append(jg_model)

                    # Process detalles justícia gratuïta if present
                    detalles_jg = j.get('detalles justícia gratuïta') or j.get('detalles justicia gratuita') or {}
                    dades_expedient = detalles_jg.get("Dades de l'expedient") or detalles_jg.get("Dades de l'expedient") or {}
                    
                    if dades_expedient:
                        try:
                            expediente_detalle_model = ExpedienteJudicial(
                                id=uuid4(),
                                sedejudicial_id=sede_id,
                                justiciagratuita_id=jg_id,
                                any_expediente=None,
                                fecha_expediente=parse_date(dades_expedient.get('Data Sol·licitud') or dades_expedient.get('Data Solicitud') or dades_expedient.get('Fecha Solicitud')),
                                organo_judicial=dades_expedient.get('Òrgan judicial') or dades_expedient.get('Órgano judicial'),
                                procedimiento=dades_expedient.get('Procediment') or dades_expedient.get('Procedimiento'),
                                numero_any_seccion=dades_expedient.get("Número d'actuació") or dades_expedient.get("Número de actuación"),
                                nig=dades_expedient.get('Identificació') or dades_expedient.get('Identificacion'),
                                ambito=dades_expedient.get('Jurisdicció') or dades_expedient.get('Jurisdicción'),
                                num_demanda=None,
                                fecha_presentacion=parse_date(dades_expedient.get('Data Entrada a CAJG') or dades_expedient.get('Fecha Entrada')),
                                fecha_registro=None,
                                estado_expediente=dades_expedient.get('Estat') or dades_expedient.get('Estado'),
                                juzgado=dades_expedient.get('Partit judicial') or dades_expedient.get('Partido judicial'),
                                fecha_incoacion=parse_date(dades_expedient.get("Data d'assistència") or dades_expedient.get("Fecha asistencia")),
                                fase=None,
                                tipo_quantia=None,
                                importe_principal=None,
                                otros_procedimientos=[],
                                intervinientes=[],
                                hitos_procesales=[],
                                created_at=datetime.now(),
                                updated_at=None
                            )
                            expedientes_models.append(expediente_detalle_model)
                        except Exception:
                            self.logger.error('GLOBAL', 'BUILD_MODELS', 'Failure', f"Invalid expediente de justicia gratuita skipped: {e}")

                            pass                                          

                except Exception as e:
                    self.logger.error('GLOBAL', 'BUILD_MODELS', 'Failure', f"Invalid justicia gratuita skipped: {e}")
                    continue

            # Sede summary model
            sede_model = SedeJudicialAutomatizaciones(
                id=sede_id,
                execution_id=execution_id,
                num_expedientes=len(expedientes_models),
                num_señalamientos=len(señalamientos_models),
                num_justicia_gratuita=len(justicicagratuita_models),
                created_at=datetime.now(),
                updated_at=None
            )

            return sede_model, expedientes_models, señalamientos_models, justicicagratuita_models
        except Exception as e:
            self.logger.error('GLOBAL', 'BUILD_MODELS', 'Failure', f"Error building DB models: {e}")
            return None, [], [], []

    ''' SedeJudicial with robots'''
    def _subscribe_sedes_with_certificate(self, cliente: str, cliente_info: Dict[str, Any], task : Dict, sedes: Optional[list] = None):   
        try:
            log_queue = Queue()
            listener = Process(target=log_listener, args=(log_queue,self.default_date, str(self.execution_id)))
            listener.start()

            # Start portal robot and certificate handler processes for each task
            with Manager() as manager:
                result_queue = manager.list()  # Shared list for inter-process communication
                for sede in sedes:
                    execution_record = HistoricoAutomatizaciones(
                        execution_id=uuid4(),
                        cliente=cliente,
                        nif=cliente_info.get('nif'),
                        cif=cliente_info.get('cif'),
                        tipo_cliente=cliente_info.get('tipo_cliente'),
                        robot_name="RobotSedeJudicial",
                        status="pending",
                        sede=sede,
                        result_robot=None,
                        result_certificate=None,
                        execution_message=f"Ejecución iniciada para cliente {cliente} en sede {sede}",
                        updated_by_user_id=78,
                        updated_by_user_name="Adría Martínez",
                        created_at=datetime.now(),
                        updated_at=None,                    
                    )

                    self.database_manager.insert_historico(execution_record)

                    processes = []                    

                    # Initialize the robot class
                    robot_instance =  RobotSeuJudicialGencat(
                        sede=sede,
                        date=date,
                        cliente=cliente,   
                        log_queue=log_queue, 
                    )

                    # Create portal robot process
                    portal_process = Process(
                        target=run_portal_robot_static,
                        args=(self.logger, robot_instance, cliente, sede, result_queue),
                        name=f"portal-{cliente}-{sede}"
                    )
                    processes.append(portal_process)
                    portal_process.start()

                    # Create certificate handler process
                    cert_process = Process(
                        target=run_certificate_handler_static,
                        args=(self.logger, cliente, sede, cliente_info.get("recipient_name"), self.execution_id, result_queue),
                        name=f"cert-{cliente}-{sede}"
                    )
                    processes.append(cert_process)
                    cert_process.start()

                    # Wait for the portal robot process to complete
                    portal_process.join()
                    # If portal_process finished, terminate cert_process if it's still running
                    
                    if cert_process.is_alive():
                        cert_process.terminate()
                        self.logger.info(cliente, sede, "Info", f"Certificate process for {cliente}-{sede} terminated as portal process finished.")

                    cert_process.join()

                    # Only process results if result_queue is not empty
                    if not result_queue:
                        self.logger.warning(cliente, sede, "Info", f"No results found for task {cliente}-{sede}. Skipping result processing.")
                        execution_record.execution_message = f"No results found for task {cliente}-{sede}."
                        execution_record.status = 'error'
                        execution_record.result_robot = None
                        execution_record.result_certificate = None

                    # Process results
                    for result in result_queue:   
                        sedejudicial_id, status, resultado = result
                        self.logger.info(cliente, sede, "Info", f"Processing result for task: {sedejudicial_id}, with status: {status}")                                             
                        execution_record.result_robot = str(resultado)

                        if status == 'completed':
                            execution_record.status = status

                            sede_model, expedientes_models, señalamientos_models, justicia_models = self._build_db_models(str(execution_record.execution_id), resultado)

                            self.logger.info(cliente, sede, "Success", f"Task {sedejudicial_id} completed successfully with data: {sede_model}, {len(expedientes_models)} expedientes, {len(señalamientos_models)} señalamientos, {len(justicia_models)} justicias.")

                            # Always set a default non-None execution_message
                            execution_record.execution_message = f"Inspección completada para {cliente} en sede {sede}"

                            if result is not None and isinstance(resultado, dict) and resultado != {}:
                                self.logger.info(cliente, sede, "Info", f"Resultado con keys: {list(resultado.keys())}")

                                # Ensure execution_id is set on sede_model
                                if sede_model is None:
                                    sede_model = SedeJudicialAutomatizaciones(
                                        id=uuid4(),
                                        execution_id=execution_record.execution_id,
                                        num_expedientes=len(expedientes_models),
                                        num_señalamientos=len(señalamientos_models),
                                        num_justicia_gratuita=len(justicia_models),
                                        created_at=datetime.now(),
                                        updated_at=None
                                    )
                                

                                execution_record.execution_message = f"Inspección completada con {sede_model.num_expedientes} expedientes, {sede_model.num_señalamientos} señalamientos y {sede_model.num_justicia_gratuita} justificaciones de gratuidad para {cliente} en sede {sede}"
                                
                                # Guardar el JSON de debug en el registro de ejecución para su posterior inspección
                                execution_record.result_robot = str(sede_model.model_dump_json())
                                self.logger.info(cliente, sede, "Success", f"Sede Judicical model stored for task {sedejudicial_id}")


                        elif status == 'certificate_handled':
                            self.logger.info(cliente, sede, "Success", f"Certificate handled for task {sedejudicial_id} with data: {resultado}")
                            execution_record.result_certificate=resultado
                        
                        elif status == 'error':
                            execution_record.status = status
                            self.logger.error(cliente, sede, "Failure", f"Task {sedejudicial_id} encountered an error: {resultado.get('error', '')}")
                            execution_record.execution_message=f"Error in task {sedejudicial_id}: {resultado.get('error', '')}"

                        else:
                            self.logger.error(cliente, sede, "Failure", f"Unknown status for task {sedejudicial_id}: {status}")
                            execution_record.execution_message=f"Unknown status for task {sedejudicial_id}: {status}"
                    
                    
                    # Persist validated models into DB via the database manager
                    try:
                        # call the DB updater which expects Pydantic models or objects with attributes
                        self.database_manager.update_historico_sedejudicial(
                            record=execution_record,
                            sedejudicial_record=sede_model,
                            expedientes_judicial=expedientes_models,
                            señalamientos_judicial=señalamientos_models,
                            justiciagratuita_judicial=justicia_models,
                        )
                    except Exception as e:
                        self.logger.error(cliente, sede, "Failure", f"Failed to update database for task {cliente}-{sede}: {e}")

                    result_queue[:] = []
                    self.actualizar_progreso_fase('ejecucion_tarea', f'Cliente={cliente}, Sede={sede}')

            # Signal the log_listener to exit and wait for it to finish
            log_queue.put(None)
            listener.join()

        except Exception as e:
            self.logger.error(cliente, None, "Failure", f"⚠️ Error in _subscribe_sedes_with_certificate: {e}")
            raise


    '''Main execution'''
    def run(self, cliente: Optional[str] = None):
        """Main method to run the robot manager"""
        start_time = time.time()
        self.logger.info("GLOBAL", "RUN", "Pending", f"Starting Robot Sede Judicial Manager with args: cliente {cliente} for execution_id: " + self.execution_id)
        try:
            sedejudicial_clientes = self.database_manager.fetch_sedejudicial(
                cliente=cliente,
            )
            self.actualizar_progreso_fase('db_fetch', 'Consultando tareas en base de datos...')
            if not sedejudicial_clientes:
                self.logger.info("GLOBAL", "RUN", "Info", "No pending altas found")
                return
            
            # Calcular total de tareas para el reparto de progreso
            self.calcular_total_tasks(sedejudicial_clientes)

            for sedejudicial_cliente in sedejudicial_clientes:
                self.database_manager.insert_assignment_log(
                    id_value=f"{str(sedejudicial_cliente.get('id_cliente') or sedejudicial_cliente.get('cliente'))}_sedejudicial",
                    cliente=sedejudicial_cliente.get('id_cliente') or sedejudicial_cliente.get('cliente'),
                    sede=sedejudicial_cliente.get('sede'),
                    robot_name="RobotSedeJudicial",
                    assigned_by="Adrià Martínez"
                )
            
            # Procesar cada grupo de tareas con el mismo certificado
            # sedejudicial_clientes is always a list
            for task in sedejudicial_clientes:
                id_cliente = task.get('id_cliente') or task.get('cliente') 
                if cliente and str(id_cliente) != str(cliente):
                    continue

                self.logger.info(id_cliente, "RUN", "Info", f"Procesando tarea de scraping de la sede judicial par el cliente {id_cliente}")

                if not self._load_certificate(str(id_cliente)):
                    self.logger.error(id_cliente, "RUN", "Failure", f"⚠️ Failed to load certificate {id_cliente}")
                    self.actualizar_progreso_fase('carga_certificados', f'Cargando certificado {id_cliente}...')
                    continue
                
                cliente_info = {
                    "nif": task.get("nif"),
                    "cif": task.get("cif"),
                    "tipo_cliente": task.get("tipo_cliente"),
                    "recipient_name": task.get("recipient_name"),
                }
                # Pass the single alta as a list of altas; restrict to its sede if provided
                sedes = [task.get("sede")] if task.get("sede") else None
                self._subscribe_sedes_with_certificate(id_cliente, cliente_info, [task], sedes=sedes)

            elapsed_time = time.time() - start_time
            self.actualizar_progreso_fase('finalizado', 'Proceso completado')
            self.logger.info("GLOBAL", "RUN", "Success", f"✅ Robot Manager execution completed in {elapsed_time:.2f} seconds")
        except Exception as e:
            self.logger.error("GLOBAL", "RUN", "Failure", f"⚠️ Error in Robot Manager: {e}")
            raise

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="RobotSedeJudicial Manager")
    parser.add_argument('--clientes', type=str, default=None, help='IDs de clientes a procesar, separados por comas (por defecto todos los pendientes)')
    args = parser.parse_args()

    manager = RobotSedeJudicial(execution_id=str(uuid4()))
    
    if args.clientes:
        clientes = args.clientes.split(',')
        for cliente in clientes:
            cliente = cliente.strip()
            manager.run(cliente=cliente)
    else:
        manager.run(cliente=None)
