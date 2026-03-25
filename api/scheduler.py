import math
import pymssql
import threading
import time
from datetime import datetime, timedelta
from api.enqueuer import enqueue_task
from database.database_manager import DatabaseManager
from database.descargas.queries.getNotificacionesDehu import getNotificacionesDehu
from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings


class Scheduler:
    def __init__(self):
        self.logger = LoggerV2(
            module="API",
            class_name=self.__class__.__name__,
            log_dir=settings.LOG_DIR,
            filename=settings.LOG_FILE,
        )
        self.stop_event = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)

    def start(self):
        self.logger.info("API", "Scheduler", "Success", "Scheduler iniciado y esperando tareas programadas.")
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        self.thread.join(timeout=5)
        self.logger.info("API", "Scheduler", "Success", "Scheduler detenido.")

    def run(self):
        # Horarios en formato (hora, minuto, función)
        schedule = [
            # Tareas de descargas
            (1, 0, lambda: self.run_descargas_yesterday(less_days=1)),
            (2, 0, lambda: self.run_descargas_yesterday(less_days=2)),            
            (17, 0, lambda: self.run_descargas_yesterday(less_days=1)),
            # Tarea de limpieza de descargas Dehú
            (8, 0, lambda: self.run_cleanup_descargas(less_days=7)),

            # Tareas de altas
            (20, 0, lambda: self.run_altas_default()),
            # Tareas de matriculas
            (0, 0, lambda: self.run_matriculas_default()),     
            (4, 0, lambda: self.run_data_360()),
            # Tareas de consulta enotum
            (3, 0, lambda: self.run_consulta_enotum()),
            (18, 0, lambda: self.run_consulta_enotum()),
        ]

        last_run = {}
        while not self.stop_event.is_set():
            now = datetime.now()
            self.logger.debug("API", "Scheduler", "Pending", f"Checking schedule at {now}")
            for hour, minute, func in schedule:
                key = f"{hour:02d}:{minute:02d}:{getattr(func, '__name__', func.__class__.__name__)}"
                if now.hour == hour and now.minute == minute:
                    self.logger.debug("API", "Scheduler", "Pending", f"Time match for {key}")
                    # Solo ejecuta una vez por minuto
                    if last_run.get(key) != now.strftime('%Y-%m-%d %H:%M'):
                        self.logger.info("API", "Scheduler", "Pending", f"Executing {key}")
                        try:
                            func()
                            last_run[key] = now.strftime('%Y-%m-%d %H:%M')
                        except Exception as e:
                            self.logger.error("API", "Scheduler", "Failure", f"Error ejecutando tarea programada {key}: {e}")
                    else:
                        self.logger.debug("API", "Scheduler", "Pending", f"Skipping {key}, already run")
                else:
                    self.logger.debug("API", "Scheduler", "Pending", f"Skipping {key}, time mismatch {now.hour}:{now.minute} != {hour}:{minute}")
            time.sleep(30)

    def run_descargas_yesterday(self, less_days: str | int = 1):
        yesterday = (datetime.now() - timedelta(days=int(less_days))).strftime('%Y-%m-%d')
        enqueue_task('run_robot_descargas', kwargs={'date': yesterday})
        self.logger.info("API", "Scheduler", "Success", f"Tarea run_robot_descargas encolada para fecha {yesterday}")   

    def run_altas_default(self):
        enqueue_task('run_robot_altas', kwargs={'limit': 25})
        self.logger.info("API", "Scheduler", "Success", "Tarea run_robot_altas encolada con sedes por defecto")

    def run_matriculas_default(self):
        enqueue_task('run_robot_matriculas')
        self.logger.info("API", "Scheduler", "Success", "Tarea run_robot_matriculas encolada con sedes por defecto")
    
    def run_consulta_enotum(self):
        enqueue_task('run_robot_consulta_enotum')
        self.logger.info("API", "Scheduler", "Success", "Tarea run_robot_consulta_enotum encolada con sedes por defecto")

    def run_cleanup_descargas(self, less_days: str | int = 1, sedes: list[str] = ['dehù', 'enotum', 'dev']):
        self.logger.info("API", "Scheduler", "Pending", f"Iniciando tarea programada run_cleanup_descargas, con less_days={less_days}")
        database_manager = DatabaseManager(
            execution_id="Scheduler.run_cleanup_descargas",
            db_config=settings.DB_CONFIG,
            date=datetime.now().strftime('%Y-%m-%d'),
            module="Descargas",
            filename=settings.LOG_FILE
        )
        
        sedes_str = "'" + "', '".join([sede.lower() for sede in sedes]) + "'"
        try:
            self.logger.info("API", "Scheduler", "Pending", "Conectando a la base de datos...")
            conn = database_manager.connect()
            cursor = conn.cursor(as_dict=True)
            
            # Build query dynamically with proper placeholders for sedes
            query = getNotificacionesDehu
            sedes_placeholders = ", ".join(["%s"] * len(sedes))
            query = query.replace("%SEDES_PLACEHOLDER%", sedes_placeholders)
            
            # Build params list: less_days followed by each sede (lowercase)
            params = [less_days] + [sede.lower() for sede in sedes]
            
            self.logger.info("API", "Scheduler", "Pending", f"Ejecutando consulta de clientes run_cleanup_descargas con less_days={less_days} y sedes={sedes_str}")
            cursor.execute(query, params)
            rows = cursor.fetchall()
            message_keys = [row['message_key'] for row in rows]
            conn.commit()

            self.logger.info("API", "Scheduler", "Success", f"Extrayendo keys de mensaje para limpiar descargas. Total encontrados: {len(message_keys)}")
        except pymssql.Error as e:
            self.logger.error("API", "Scheduler", "Failure", f"Error actualizando tarea en el historico: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

        # Generate batches of 150 message keys and enqueue each batch
        self.logger.info("API", "Scheduler", "Pending", f"Encolando tarea run_cleanup_descargas para {len(message_keys)} keys de mensaje")
        batch_size = 150
        for i in range(0, len(message_keys), batch_size):
            batch = message_keys[i:i + batch_size]
            enqueue_task('run_robot_descargas', kwargs={
                'message_keys': batch,
                'date': datetime.now().strftime('%Y-%m-%d'),
            })
            self.logger.info("API", "Scheduler", "Success", f"Batch {i//batch_size + 1} encolado con {len(batch)} keys de mensaje")
        
        self.logger.info("API", "Scheduler", "Success", "Tarea run_cleanup_descargas encolada con keys de mensaje para limpieza de descargas Dehú")
        


    def run_data_360(self):
        print("Iniciando tarea programada run_data_360")
        self.logger.info("API", "Scheduler", "Pending", "Iniciando preparación de tarea run_data_360")
        database_manager = DatabaseManager(
            execution_id="Scheduler.run_data_360",
            db_config=settings.DB_CONFIG,
            date=datetime.now().strftime('%Y-%m-%d'),
            module="MatriculasyPuntos",
            filename=settings.LOG_FILE
        )

        try:
            self.logger.info("API", "Scheduler", "Pending", "Conectando a la base de datos...")
            conn = database_manager.connect()
            cursor = conn.cursor()
            query = """ 
                WITH ha_latest AS (
                    SELECT ha.*, ROW_NUMBER() OVER (PARTITION BY ha.cliente ORDER BY ha.created_at DESC) AS rn
                    FROM historico_automatizaciones ha 
                    INNER JOIN informes_dgt_automatizaciones ida ON ida.execution_id = ha.execution_id
                )
                SELECT Distinct idbenef as cliente,
                    CASE WHEN ha.robot_name = 'RobotInformesDGT' THEN ha.created_at ELSE NULL END as last_date
                FROM info.BeneficiarioBonos ibb
                LEFT JOIN ha_latest ha ON ha.cliente = ibb.idbenef AND ha.rn = 1
                LEFT JOIN informes_dgt_automatizaciones ida ON ida.execution_id = ha.execution_id
                LEFT JOIN matriculas_extraidas me ON ida.id = me.informe_id
                LEFT JOIN alertas_extraidas ae ON ae.matricula_id = me.id
                LEFT JOIN sanciones_extraidas se ON ida.id = se.informe_id
                WHERE 1=1
                    AND ibb.servicio IN ('DATA_360_TRAFICO', 'DATA_360_TRAFICO Económico')
                    AND ibb.situacion LIKE '%COBRADO%'
                ORDER BY last_date ASC
            """

            self.logger.info("API", "Scheduler", "Pending", "Ejecutando consulta de clientes Data 360")
            cursor.execute(query)
            rows = cursor.fetchall()
            clientes = [row.cliente for row in rows]
            conn.commit()

            self.logger.info("API", "Scheduler", "Success", f"Extrayendo clientes para el servicio Data 360. Total encontrados: {len(clientes)}")
        except pymssql.Error as e:
            self.logger.error("API", "Scheduler", "Failure", f"Error updating task en el historico: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()


        self.logger.info("API", "Scheduler", "Pending", f"Encolando tarea run_robot_matriculas para {len(clientes)} clientes")
        enqueue_task('run_robot_matriculas', kwargs={
            'clientes': clientes,
            'date': datetime.now().strftime('%Y-%m-%d'),
        })
        self.logger.info("API", "Scheduler", "Success", "Tarea run_robot_data_360 encolada con sedes por defecto")

    def run_test(self, iterations=100000):
        self.logger.info("API", "Scheduler", "Success", "Ejecutando tarea de prueba")
        """Simula una tarea de benchmark con operaciones matemáticas."""
        try:
            self.logger.info("API", "Scheduler", "Success", f"Iniciando tarea de prueba con {iterations} iteraciones.")
            start_time = time.time()

            for i in range(1, iterations):
                result = sum(math.sqrt(j) for j in range(1, 1000))
                if i % 100 == 0:
                    self.logger.debug("API", "Scheduler", "Success", f"Iteración {i} completada. Resultado parcial: {result:.2f}")
                    # self._log("Info", f"Iteración {i} completada. Resultado parcial: {result:.2f}")

            duration = time.time() - start_time
            self.logger.info("API", "Scheduler", "Success", f"Tarea de prueba de {duration:.2f} segundos con resultado {result:.2f}.")
            return result

        except Exception as e:
            self.logger.error("API", "Scheduler", "Failure", f"Error en la tarea de prueba: {e}")
            return None