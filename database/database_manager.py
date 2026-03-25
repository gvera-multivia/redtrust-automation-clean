from typing import List, Dict, Any, Callable, Optional
import time
import functools

# THIRD PARTY PACKAGES
import pymssql

# PERSONAL PACKAGES - UTILS
from app.helper.loggerV2 import LoggerV2
from app.models.database_models import HistoricoAutomatizaciones


def retry_on_deadlock(max_retries: int = 3, base_delay: float = 0.5):
    """Decorator to retry a database operation if a SQL Server deadlock occurs.

    It catches pymssql.Error and inspects the SQL state or message for the
    deadlock indicator (SQLSTATE '40001' or error number 1205). On match it
    retries the wrapped function with exponential backoff.
    """

    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except pymssql.Error as e:
                    # pymssql.Error often provides args like (sqlstate, message)
                    sqlstate = None
                    try:
                        if len(e.args) > 0:
                            sqlstate = str(e.args[0])
                    except Exception:
                        sqlstate = None

                    message = str(e)
                    is_deadlock = False
                    if sqlstate and sqlstate == '40001':
                        is_deadlock = True
                    if '1205' in message or 'deadlock' in message.lower():
                        is_deadlock = True

                    attempt += 1
                    if is_deadlock and attempt <= max_retries:
                        # If possible, try to pull a logger from self (first arg)
                        logger = None
                        try:
                            logger = getattr(args[0], 'logger', None)
                        except Exception:
                            logger = None

                        if logger:
                            logger.warning(getattr(args[0], 'cliente', 'DATABASE'),
                                           func.__name__,
                                           'Retry',
                                           f"Deadlock detected (attempt {attempt}/{max_retries}). Retrying after backoff. Error: {e}")
                        delay = base_delay * (2 ** (attempt - 1))
                        time.sleep(delay)
                        continue
                    # not a deadlock or exceeded retries -> re-raise
                    raise

        return wrapper

    return decorator

class DatabaseManager:
    """
    Class to manage database interactions
    """
    def __init__(self, db_config: Dict[str, Any], date : str, module : str, execution_id : str, filename: str = None, cliente: str = "DATABASE"):
        self.db_config = db_config
        self.logger = LoggerV2(
            execution_id=execution_id,
            module=module,
            class_name=self.__class__.__name__,
            log_dir=f"logs\\{module.lower()}",
            filename=filename
        )
        self.cliente = cliente
        self.date = date

    """ COMMON METHODS """
    def connect(self) -> pymssql.Connection:
        """Establish a connection to the database"""
        try:
            # Parse server optionally containing a port (format: host,port or host:port)
            server_raw = self.db_config.get('server', '')
            host = server_raw
            port = None
            if server_raw and (',' in server_raw or ':' in server_raw):
                sep = ',' if ',' in server_raw else ':'
                parts = server_raw.split(sep, 1)
                host = parts[0]
                try:
                    port = int(parts[1])
                except Exception:
                    port = None

            # Build connection using explicit host and port (if provided)
            if port:
                conn = pymssql.connect(server=host,
                                       port=port,
                                       user=self.db_config.get('user'),
                                       password=self.db_config.get('password'),
                                       database=self.db_config.get('database'),
                                       charset='UTF-8', tds_version=r'7.0',
                                       login_timeout=10)
            else:
                conn = pymssql.connect(server=host,
                                       user=self.db_config.get('user'),
                                       password=self.db_config.get('password'),
                                       database=self.db_config.get('database'),
                                       charset='UTF-8', tds_version=r'7.0',
                                       login_timeout=10)
            return conn
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error connecting to the database: {e}")
            raise
        except Exception as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Unexpected error connecting to the database: {e}")
            raise

    @retry_on_deadlock()
    def insert_historico(self, record: HistoricoAutomatizaciones):
        """
        Create the table if it does not exist and insert a new row into the database.
        """
        query = """
            INSERT INTO historico_automatizaciones (
                execution_id, cliente, nif, cif, 
                tipo_cliente, robot_name, status, sede,
                result_robot, result_certificate, execution_message, updated_by_user_id, 
                updated_by_user_name, created_at
            ) VALUES (%s, %s, %s, %s, 
                    %s, %s, %s, %s, 
                    %s, %s, %s, %s, 
                    %s, GETDATE())
        """
    
        try:
            conn = self.connect()
            cursor = conn.cursor()
            params = (
                str(record.execution_id), record.cliente, record.nif, record.cif, 
                record.tipo_cliente, record.robot_name, record.status, record.sede, 
                record.result_robot, 1 if record.result_certificate else 0, record.execution_message, record.updated_by_user_id, 
                record.updated_by_user_name
            )
            cursor.execute(query, params)
            conn.commit()

            self.logger.info(self.cliente, record.execution_id, "Success", f"Insertado una ejecución con id {record.execution_id} en HistoricoAutomatizaciones")
        except pymssql.Error as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating task en el historico: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def update_historico(self, record: HistoricoAutomatizaciones):
        """
        Create the table if it does not exist and insert a new row into the database.
        """
        query = """
            UPDATE historico_automatizaciones 
            SET
                cliente = %s,
                nif = %s,
                cif = %s,
                tipo_cliente = %s,
                robot_name = %s,
                status = %s,
                sede = %s,
                result_robot = %s,
                result_certificate = %s,
                execution_message = %s,
                updated_by_user_id = %s,
                updated_by_user_name = %s,
                updated_at = GETDATE()
                
            WHERE execution_id = %s
        """
    
        try:
            conn = self.connect()
            cursor = conn.cursor()
            # Determine status: if pending but there's a robot result, mark as error; otherwise keep original
            status_value = 'error' if (record.status == 'pending' and record.result_robot is not None) else record.status
            params = (
                record.cliente,
                record.nif,
                record.cif,
                record.tipo_cliente,
                record.robot_name,
                status_value,
                record.sede,
                record.result_robot,
                1 if record.result_certificate else 0,
                record.execution_message,
                record.updated_by_user_id,
                record.updated_by_user_name,
                str(record.execution_id),
            )
            cursor.execute(query, params)
            # If no rows were updated, the historico record may not exist yet -> insert it
            if cursor.rowcount == 0:
                conn.close()
                self.logger.info(self.cliente, record.execution_id, "Info", f"No existing historico for execution {record.execution_id}, inserting new record")
                # Use insert_historico which will create the row and commit
                return self.insert_historico(record)

            conn.commit()

            self.logger.info(self.cliente, record.execution_id, "Success", f"Actualizando la ejecución con id {record.execution_id} en HistoricoAutomatizaciones")
        except pymssql.Error as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating task en el historico: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def retrieve_historico(self, fecha_descarga: str) -> List[Dict[str, Any]]:
        """
        Retrieve records from historico_automatizaciones by fecha_descarga
        """
        from datetime import datetime
        query = """
            SELECT * 
            FROM historico_automatizaciones ha
                INNER JOIN descargas_automatizaciones da ON ha.execution_id = da.execution_id
            WHERE 
                CAST(da.fecha_descarga AS DATE) = %s
                AND ha.robot_name =  %s

            order by ha.created_at DESC
        """
        try:
            # Ensure fecha_descarga is in 'YYYY-MM-DD' format
            try:
                fecha_descarga_sql = datetime.strptime(fecha_descarga, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                # Try to parse other common formats, fallback to original if not possible
                try:
                    fecha_descarga_sql = datetime.strptime(fecha_descarga, "%d/%m/%Y").strftime("%Y-%m-%d")
                except ValueError:
                    fecha_descarga_sql = fecha_descarga  # Use as is, may still fail

            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query, (fecha_descarga_sql, 'RobotDescargas'))
            columns = [col[0] for col in cursor.description]
            records = [dict(zip(columns, row)) for row in cursor.fetchall()]
            self.logger.info(self.cliente, "FETCH", "Success", f"Retrieved {len(records)} records from historicoAutomatizaciones for fecha_descarga {fecha_descarga_sql}")
            return records
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error retrieving records: {e}")
            raise
        finally:
            conn.close()
            
    @retry_on_deadlock()
    def insert_assignment_log(self,
                              id_value: str,
                              cliente: Optional[str],
                              sede: Optional[str],
                              robot_name: str,
                              assigned_by: str = "Adria Martinez"
        ):
        """
        Insert a row into automations_assignment_log.
        id_value: string identifier (message_key or formats described by spec)
            | - [message_key]
            | - alta_[cliente]_[sede]
            | - informedgt_[cliente]_[sede]
            | - consulta_[cliente]_[sede]
            | - [cliente]_[sedejudicial]
        cliente, sede: optional strings
        robot_name: one of RobotDescargas, RobotAltas, RobotInformeDGT, RobotConsultaEnotum, RobotSedeJudicial
        assigned_by: default 'Adria Martinez'
        """
        
        query = """
            INSERT INTO automations_assignment_log
            (id, cliente, sede, robot_name, assigned_at, assigned_by)
            VALUES (%s, %s, %s, %s, GETDATE(), %s)
        """
        params = (id_value, cliente, sede, robot_name, assigned_by)

        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            self.logger.info(self.cliente, id_value, "Success", f"Inserted assignment log {id_value} for robot {robot_name}")
        except pymssql.Error as e:
            self.logger.error(self.cliente, id_value, "Failure", f"Error inserting assignment log: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def delete_assignment_log(self, id_value: str, robot_name: str):
        """
        Delete a row from automations_assignment_log by id.
        """
        query = "DELETE FROM automations_assignment_log WHERE robot_name = %s AND id = %s"
        try:
            conn = self.connect()
            cursor = conn.cursor()
            cursor.execute(query, (robot_name, id_value,))
            if cursor.rowcount == 0:
                conn.commit()
                self.logger.info(self.cliente, id_value, "Info", f"No assignment log found with id {id_value} to delete")
                return
            conn.commit()
            self.logger.info(self.cliente, id_value, "Success", f"Deleted assignment log {id_value}")
        except pymssql.Error as e:
            self.logger.error(self.cliente, id_value, "Failure", f"Error deleting assignment log: {e}")
            try:
                conn.rollback()
            except Exception:
                pass
            raise
        finally:
            try:
                conn.close()
            except Exception:
                pass