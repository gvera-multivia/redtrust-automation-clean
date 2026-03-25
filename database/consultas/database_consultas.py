from typing import Optional, List, Dict, Any, Tuple, Union
import pymssql
from database.consultas.queries import getNotificacionesPendientesFromDate
from database.consultas.queries import getClientesConsultaEnotum
from database.database_manager import DatabaseManager, retry_on_deadlock
from app.models.database_models import HistoricoAutomatizaciones, ConsultaAutomatizaciones, DescargaConsulta
from app.utils.utils import CONSULTA_RESULTS


class ConsultasDatabase(DatabaseManager):
    """Database helper for 'consulta enotum' robot-specific DB actions."""
    def __init__(self, db_config: Dict[str, Any], date: str, module: str, execution_id: str, filename: str = None):
        super().__init__(db_config=db_config, date=date, module=module, execution_id=execution_id, filename=filename, cliente="CONSULTAS_ENOTUM_DATABASE")

    def consulta_clientes_enotum(
        self,
        cliente: Optional[Union[str, int]] = None,
        date: Optional[str] = None,
        limit: Optional[int|str] = 300
    ) -> List[Dict[str, Any]]:
        """Fetch clients for the 'consulta enotum' process."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            # Build dynamic query and parameters
            final_query, params = self._build_consultaenotum_query(
                cliente=cliente,
                date=date
            )
            
            params.append(limit)
            cursor.execute(final_query, params)
            columns = [col[0] for col in cursor.description]
            clientes = [dict(zip(columns, row)) for row in cursor.fetchall()]

            self.logger.info(
                self.cliente,
                "FETCH",
                "Success",
                f"Fetched {len(clientes)} clients for consulta enotum"
            )
            return clientes

        except pymssql.Error as e:
            self.logger.error(
                self.cliente,
                "FETCH",
                "Failure",
                f"Error fetching clients for consulta enotum: {e}"
            )
            raise

        finally:
            conn.close()

    def get_notificaciones_from_date(
        self,
        cliente: str,
        fecha_revision: str
    ) -> List[Dict[str, Any]]:
        """Retrieve notifications for a given client from a specific revision date."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute(
                getNotificacionesPendientesFromDate.getNotificacionesPendientesFromDate,
                (cliente, cliente, "enotum", "dehù", fecha_revision)  
            )

            columns = [col[0] for col in cursor.description]
            notifications = [dict(zip(columns, row)) for row in cursor.fetchall()]

            self.logger.info(
                self.cliente,
                "FETCH",
                "Success",
                f"Fetched {len(notifications)} notifications for cliente {cliente} from {fecha_revision}"
            )
            return notifications

        except pymssql.Error as e:
            self.logger.error(
                self.cliente,
                "FETCH",
                "Failure",
                f"Error fetching notifications: {e}"
            )
            raise

        finally:
            conn.close()

    def _build_consultaenotum_query(
        self,
        cliente: Optional[Union[str, int]] = None,
        date: Optional[str] = None
    ) -> Tuple[str, List[Any]]:
        """
        Build the dynamic SQL query for fetching clients in consulta enotum.
        Adds filters for client and date dynamically.
        """
        base_query = getClientesConsultaEnotum.getClientesConsultaEnotum_paquete
        params: List[Any] = []
        additional_conditions: List[str] = []

        if cliente:
            additional_conditions.append("cm.customer_number = %s")
            params.append(cliente)

        if date:
            base_query = base_query.replace(
                "SET @fecha_revision = NULL;",
                f"SET @fecha_revision = '{date}';"
            )

        if additional_conditions:
            base_query = base_query.replace(
                "WHERE 1=1\n",
                f"WHERE 1=1 AND {' AND '.join(additional_conditions)}\n"
            )

        return base_query, params

    def update_consulta_enotum(
        self,
        idconsulta: str,
        cliente: str,
        nombre_cliente: str,
        resultado: int,
        notas: str,
        fecha_rueda: str,
        descarga_data: Optional[Dict[str, Any]] = None,
        sede: str = "enotum",
        user_name: str = "Adría Martinez"
    ) -> None:
        """Update the consulta enotum record with results and download info."""
        @retry_on_deadlock()
        def _update_consulta_enotum_inner():
            conn = self.connect()
            cursor = conn.cursor()

            try:
                cursor.execute(
                    """
                    INSERT INTO controlpasorobot (
                        id,
                        cliente, nombre_cliente, sede, resultado, fechapaso, notas, usuario,
                        descarga, url, id_notificacion, asunto_notificacion,
                        organismo_notificacion, fecha_notificacion, prev_descargado,
                        expediente_notificacion, descarga_status, fecha_rueda
                    ) VALUES (%s, %s, %s, %s, %s, GETDATE(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        idconsulta,
                        cliente,
                        nombre_cliente,
                        sede,
                        CONSULTA_RESULTS.get(resultado, "Desconocido"),
                        notas,
                        user_name,
                        bool(descarga_data),
                        descarga_data.get("url") if descarga_data else None,
                        descarga_data.get("identificador") if descarga_data else None,
                        descarga_data.get("title") if descarga_data else None,
                        descarga_data.get("org") if descarga_data else None,
                        descarga_data.get("disposition_date") if descarga_data else None,
                        descarga_data.get("desc") if descarga_data else None,
                        descarga_data.get("expediente") if descarga_data else None,
                        descarga_data.get("status") if descarga_data else None,
                        fecha_rueda
                    )
                )

                conn.commit()
                self.logger.info(
                    self.cliente,
                    "UPDATE",
                    "Success",
                    f"Updated consulta enotum for cliente {cliente} to resultado {resultado}"
                )
            except pymssql.Error as e:
                self.logger.error(
                    self.cliente,
                    "UPDATE",
                    "Failure",
                    f"Error updating consulta enotum: {e}"
                )
                raise
            finally:
                self.delete_assignment_log(id_value=f"consulta_{cliente}_enotum", robot_name="RobotConsulta")
                conn.close()

        return _update_consulta_enotum_inner()

    def update_historico_consulta(
        self,
        record: HistoricoAutomatizaciones,
        consulta_record: ConsultaAutomatizaciones,
        descarga_consulta_records: List[DescargaConsulta] = None
    ) -> None:
        """
        Update historico_automatizaciones and related consultas_automatizadas records.
        """
        # First update the historico record (may raise)
        self.update_historico(record)

        # If there's no consulta record (e.g., the portal run produced no actionable alta),
        # we only needed to update the historico table above — nothing more to insert.
        if consulta_record is None:
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Info",
                f"No consulta_automatizaciones to insert for execution {record.execution_id}; historico updated only"
            )
            return


        @retry_on_deadlock()
        def _update_historico_consulta_inner():
            conn = self.connect()
            cursor = conn.cursor()
            try:
                # Insert consulta_automatizaciones record
                cursor.execute(
                    """
                    INSERT INTO consulta_automatizaciones (
                        id, execution_id, resultado, notas, descarga
                    ) VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        consulta_record.id,
                        record.execution_id,
                        consulta_record.resultado,
                        consulta_record.notas,
                        bool(consulta_record.descarga)
                    )
                )
                conn.commit()

                self.logger.info(
                    self.cliente,
                    record.execution_id,
                    "Success",
                    f"Inserted consulta_automatizaciones for execution {record.execution_id}"
                )

                # Insert descarga_consulta records if any
                for descarga in descarga_consulta_records or []:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO descarga_consulta (
                                id, id_consulta, url, id_notificacion, asunto_notificacion,
                                organismo_notificacion, fecha_notificacion, descargada_notificacion, expediente_notificacion, descarga_status
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                descarga.id,
                                consulta_record.id,
                                descarga.url,
                                descarga.id_notificacion,
                                descarga.asunto_notificacion,
                                descarga.organismo_notificacion,
                                descarga.fecha_notificacion,
                                descarga.descargada_notificacion,
                                descarga.expediente_notificacion,
                                descarga.descarga_status
                            )
                        )

                        # Commit once after all inserts
                        conn.commit()

                        self.logger.info(
                            self.cliente,
                            record.execution_id,
                            "Success",
                            f"Inserted descarga_consulta record {descarga.id} for consulta {consulta_record.id}"
                        )

                    except pymssql.Error as e:
                        self.logger.error(
                            self.cliente,
                            record.execution_id,
                            "Failure",
                            f"Error inserting descarga_consulta records: {e}"
                        )
                        raise
            except pymssql.Error as e:
                conn.rollback()
                self.logger.error(
                    self.cliente,
                    record.execution_id,
                    "Failure",
                    f"Error inserting historico/consulta/descarga records: {e}"
                )
                raise
            except Exception as e:
                self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating consulta_automatizaciones: {e}")
                conn.rollback()
                raise
            finally:
                conn.close()

        return _update_historico_consulta_inner()
				
     
            