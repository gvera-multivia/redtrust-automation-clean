from typing import Optional, List, Dict, Any
import re
import pymssql
import database.descargas.queries.getNotificacionesPendientes as getNotificacionesPendientes
from database.database_manager import DatabaseManager, retry_on_deadlock
from app.models.database_models import HistoricoAutomatizaciones, DescargasAutomatizaciones


class DescargaDatabase(DatabaseManager):
    """Database helper for the 'descargas' robot.

    Exposes high-level methods the descargas robot uses so callers don't need to import
    DatabaseManager directly.
    """

    def __init__(self, db_config: Dict[str, Any], date: str, module: str, execution_id: str, filename: str = None):
        super().__init__(db_config=db_config, date=date, module=module, execution_id=execution_id, filename=filename, cliente="DESCARGAS_DATABASE")

    def _build_notifications_query(
        self,
        date: str,
        sedes: Optional[list] = None,
        cliente: Optional[str] = None,
        message_ids: Optional[List[str]] = None,
        message_keys: Optional[List[str]] = None,
        status: str = None,
        limit: Optional[str | int] = None,
    ) -> tuple[str, list]:
        """
        Build the dynamic query and parameters for notifications.
        Adapts the sedes filter and adds optional filters for cliente, message_id, message_key and status.
        When message_keys is provided, the date filter is removed since we're searching for specific messages.
        """
        base_query = getNotificacionesPendientes.getNotificacionesPendientes
        
        # Check if message_keys is provided and not empty
        has_message_keys = message_keys and len(message_keys) > 0
        
        # Initialize params: include date params only if message_keys is not provided
        if has_message_keys:
            params: list = []
            # Remove date filter when searching by message_keys
            base_query = re.sub(
                r'/\* DATE_FILTER_START \*/.*?/\* DATE_FILTER_END \*/',
                '',
                base_query,
                flags=re.DOTALL
            )
        else:
            params: list = [date, date]  # The query uses %s twice for date

        # Handle sedes parameter
        sedes_filter = "AND LOWER(cs.sede) IN (%s, %s, %s)"
        if sedes:
            sedes_placeholders = ", ".join(["%s" for _ in sedes])
            base_query = base_query.replace(
                sedes_filter,
                f"AND LOWER(cs.sede) IN ({sedes_placeholders})",
            )
            params.extend([sede.lower() for sede in sedes])
        else:
            # Remove sedes filter if not provided
            base_query = base_query.replace(sedes_filter, "")

        # Additional conditions for the outer query
        additional_conditions = []
        top_val = int(limit) if limit else 1000
        params.append(top_val)

        if cliente:
            additional_conditions.append("AND t.client_id = %s")
            params.append(cliente)

        if message_ids:
            placeholders = ", ".join(["%s"] * len(message_ids))
            additional_conditions.append(f"AND t.message_id IN ({placeholders})")
            params.extend(message_ids)

        if message_keys:
            placeholders = ", ".join(["%s"] * len(message_keys))
            additional_conditions.append(f"AND t.message_key IN ({placeholders})")
            params.extend(message_keys)

        if status:
            additional_conditions.append("AND t.status = %s")
            params.append(status)

        # Insert additional conditions in the final WHERE clause
        if additional_conditions:
            base_query = base_query.replace(
                "WHERE t.rn = 1\nORDER BY t.date ASC",
                f"WHERE t.rn = 1 {' '.join(additional_conditions)}\nORDER BY t.date ASC",
            )

        return base_query, params

    def fetch_notifications(
        self,
        date: str,
        sedes: Optional[list] = None,
        cliente: Optional[str] = None,
        message_ids: Optional[List[str]] = None,
        status: str = None,
        message_keys: Optional[List[str]] = None,
        limit: Optional[str | int] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch pending tasks from the database

        Args:
            date: Date to filter notifications (required)
            sedes: List of sedes to filter by (optional)
            cliente: Specific client ID to filter by (optional)
            message_id: Specific message ID to filter by (optional)
            status: Status to filter by (optional)

        Returns:
            List of notification dictionaries
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            # Build dynamic query and parameters
            final_query, params = self._build_notifications_query(
                date = date,
                sedes = sedes,
                cliente = cliente,
                message_ids = message_ids,
                message_keys = message_keys,
                status = status,
                limit = limit,
            )

            cursor.execute(final_query, params)
            columns = [col[0] for col in cursor.description]
            notifications = [dict(zip(columns, row)) for row in cursor.fetchall()]

            # Build filter info for logging
            filter_parts = [f"date={date}"]
            if sedes:
                filter_parts.append(f"sedes={sedes}")
            if cliente:
                filter_parts.append(f"cliente={cliente}")
            if message_ids:
                filter_parts.append(f"message_ids IN ({','.join(map(str, message_ids))})")
            if message_keys:
                filter_parts.append(f"message_keys IN ({','.join(map(str, message_keys))})")
            if status:
                filter_parts.append(f"status={status}")
            filter_info = ", ".join(filter_parts)

            self.logger.info(self.cliente, "FETCH", "Success", f"Fetched {len(notifications)} tasks from database with filters: {filter_info}")
            return notifications
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error fetching tasks: {e}")
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def assign_notifications(self, notifications_ids: str, user_name: str) -> None:
        """Assign a notification to a user"""
        conn = self.connect()
        cursor = conn.cursor()

        placeholders = ", ".join(["%s"] * len(notifications_ids))
        try:
            cursor.execute(
                f"""
                UPDATE em
                SET 
                    em.updatedby_user_id = u.id,
                    em.updatedby_user_name = u.name,
                    em.updated_at = GETDATE(),
                    em.user_id = u.id,
                    em.UsuarioAsignado = u.name,
                    em.asigned = 2
                FROM emails_messages em
                INNER JOIN users u ON u.name = %s
                WHERE em.message_key IN ({placeholders})
            """,
                ([user_name] + notifications_ids),
            )
            conn.commit()
            self.logger.info(self.cliente, "UPDATE", "Success", f"Assigned notification {len(notifications_ids)} to user {user_name}")
        except pymssql.Error as e:
            self.logger.error(self.cliente, "UPDATE", "Failure", f"Error assigning notification: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def update_notification_status(self, cliente: str, message_key: str, status_id: str | int | None = None) -> None:
        """
        Update the notification status in emails_messages.
        If status_id is None, do not update em.status_id.
            id	name	
            1	Pendiente	
            2	Descargado	
            3	Certificado caducado	
            4	Certificado revocado	
            5	Falta certificado	
            6	Anterior a fecha		
            7	Sin servicios NEO		
            8	No interesa	
            9	Agencia Tributaria		
            10	Otros		
            11	Sólo Suscripción		
            12	CLIENTE INACTIVO		
            13	Error notificación/Error descarga		
            14	NO DESCARGAR NADA	
            15	Error automatizacion	        
        """
        conn = self.connect()
        cursor = conn.cursor()
        try:
            allowed_status_ids = [1, 2, 7, 9, 11, 14, None]
            if status_id not in allowed_status_ids:
                raise ValueError(f"Invalid status_id {status_id}. Must be one of {allowed_status_ids}.")
            if status_id is None:
                cursor.execute(
                    """
                    UPDATE em
                    SET 
                        em.updated_at = GETDATE(),
                        em.user_id = NULL,
                        em.UsuarioAsignado = NULL,
                        em.asigned = 1
                    FROM emails_messages em
                    WHERE em.message_key = %s 
                        AND em.customer_number = %s 
                """,
                    (message_key, cliente),
                )
            else:
                cursor.execute(
                    """
                    UPDATE em
                    SET 
                        em.updated_at = GETDATE(),
                        em.user_id = NULL,
                        em.UsuarioAsignado = NULL,
                        em.asigned = 1,
                        em.status_id = %s
                    FROM emails_messages em
                    WHERE em.message_key = %s 
                        AND em.customer_number = %s 
                """,
                    (status_id, message_key, cliente),
                )
            conn.commit()
            self.logger.info(self.cliente, message_key, "Success", f"Updated descarga con message_id {message_key} en emails_messages")
        except pymssql.Error as e:
            self.logger.error(self.cliente, message_key, "Failure", f"Error updating el estado de la descarga: {e}")
            conn.rollback()
            raise
        except ValueError as ve:
            self.logger.error(self.cliente, message_key, "Failure", str(ve))
            raise
        finally:
            # self.delete_assignment_log(id_value = message_key, robot_name = "RobotDescargas")
            conn.close()

    @retry_on_deadlock()
    def update_historico_descarga(
        self,
        record: HistoricoAutomatizaciones,
        descarga_records: List[DescargasAutomatizaciones]
    ) -> None:
        """
        Update historico_automatizaciones and related descargas_automatizaciones records.
        """
        # First update the historico record (may raise)
        self.update_historico(record)

        conn = self.connect()
        cursor = conn.cursor()
        # Use descarga_record fields to populate descargas_automatizaciones
        try:
            for descarga_record in descarga_records:
                try:
                    cursor.execute(
                        """
                        INSERT INTO descargas_automatizaciones (
                            id,
                            execution_id,
                            message_key,
                            fecha_descarga,
                            identificador,
                            expediente,
                            prev_desc,
                            filename,
                            organismo,
                            created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, GETDATE())
                        """,
                        (
                            descarga_record.id,
                            record.execution_id,
                            descarga_record.message_key,
                            descarga_record.fecha_descarga,
                            descarga_record.identificador,
                            descarga_record.expediente,
                            descarga_record.prev_desc,
                            descarga_record.filename,
                            descarga_record.organismo,
                        ),
                    )

                    # Commit once after this insert
                    conn.commit()
                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted descargas_automatizaciones {descarga_record.id} with {descarga_record.message_key} for execution {record.execution_id}"
                    )

                except pymssql.Error as e:
                    conn.rollback()
                    self.logger.error(
                        self.cliente,
                        record.execution_id,
                        "Failure",
                        f"Error inserting historico/descarga records: {e}"
                    )
                    raise
        except Exception as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating descargas_automatizaciones: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()