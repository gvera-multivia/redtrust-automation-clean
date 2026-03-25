from typing import Optional, List, Dict, Any
import pymssql
import database.altas.queries.getAltasPendientes as getAltasPendientes
from database.database_manager import DatabaseManager, retry_on_deadlock
from app.utils.utils import email_validator
from app.models.database_models import HistoricoAutomatizaciones, AltasAutomatizaciones


class AltasDatabase(DatabaseManager):
    """Database wrapper for 'altas' robot operations."""

    def __init__(self, db_config: Dict[str, Any], date: str, module: str, execution_id: str, filename: str = None):
        super().__init__(db_config=db_config, date=date, module=module, execution_id=execution_id, filename=filename, cliente="ALTAS_DATABASE")

    def fetch_altas(self, sedes: List, cliente: Optional[str], limit : int = 5) -> List[Dict[str, Any]]:
        """Fetch pending altas from the database, parametrized for sedes and cliente."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            sedes_placeholders = ', '.join(['%s' for _ in sedes])
            cliente_filter = " AND cm.customer_number = %s" if cliente is not None else ""
            query = getAltasPendientes.getAltasPendientes \
                .replace('{sedes_placeholder}', sedes_placeholders) \
                .replace('{cliente_filter}', cliente_filter) \
                .replace('{limit}', str(limit))
            params = sedes[:]
            if cliente is not None:
                params.append(cliente)
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            altas = [dict(zip(columns, row)) for row in cursor.fetchall()]
            self.logger.info(self.cliente, "FETCH", "Success", f"Fetched {len(altas)} altas from database")

            structured_altas = {}
            for alta in altas:
                cliente = alta.get('cliente')
                if cliente not in structured_altas:
                    structured_altas[cliente] = {
                        "tipo_cliente": alta.get('tipo_cliente'),
                        "certificate_id": alta.get('certificate_id'),
                        "name": alta.get('name'),
                        "manager": alta.get('manager'),
                        "recipient_name": alta.get('recipient_name'),
                        "provincia": alta.get('provincia'),
                        "poblacion": alta.get('poblacion'),
                        "codigo_postal": alta.get('Cpostal'),
                        "calle": alta.get('calle'),
                        "CIF": alta.get('CIF').strip() if alta.get('CIF') else None,
                        "NIF": alta.get('NIF').strip(),
                        "state": alta.get('state'),
                        "valid_from": alta.get('valid_from'),
                        "valid_up_to": alta.get('valid_up_to'),
                        "sedes": []
                    }
                if alta.get('sede') not in [sede['sede'] for sede in structured_altas[cliente]["sedes"]]:
                    structured_altas[cliente]["sedes"].append({
                        "sede": alta.get('sede'),
                        "sede_id": alta.get('sede_id'),
                        "link": alta.get('url'),
                        "n_emails": alta.get('n_emails'),
                        "emails": email_validator(alta.get('emails')),
                        "certificate_id": alta.get('certificate_id'),
                        "created_at": alta.get('created_at')
                    })

            return structured_altas
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error fetching altas: {e}")
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def assign_certificates(self, cert_ids: Dict[str, Any], user_name: str) -> None:
        """Assign a notification to a user"""
        conn = self.connect()
        cursor = conn.cursor()

        placeholders = ', '.join(['%s'] * len(cert_ids))
        try:
            params = [user_name] + list(cert_ids)
            cursor.execute(f"""
                UPDATE em
                SET 
                    em.user_id = u.id,
                    em.UsuarioAsignado = u.name,
                    em.asigned = 2
                FROM certificates_managements_ em
                INNER JOIN users u ON u.name = %s
                WHERE em.id IN ({placeholders})
            """, params)
            conn.commit()
            self.logger.info(self.cliente, "UPDATE", "Success", f"Assigned certificate {len(cert_ids)} to user {user_name}")
        except pymssql.Error as e:
            self.logger.error(self.cliente, "UPDATE", "Failure", f"Error assigning certificate: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def unassign_certificate(self, cert_id: str | int, user_name: str) -> None:
        """Unassign a certificate from a user"""
        conn = self.connect()
        cursor = conn.cursor()

        try:
            cursor.execute(
                """
                UPDATE em
                SET 
                    em.user_id = NULL,
                    em.UsuarioAsignado = NULL,
                    em.asigned = 1
                FROM certificates_managements_ em                
                WHERE em.id IN (%s) and em.UsuarioAsignado = %s
            """,
                (cert_id, user_name),
            )
            conn.commit()
            self.logger.info(self.cliente, "UPDATE", "Success", f"Unasigned certificate {cert_id} from user {user_name}")
        except pymssql.Error as e:
            self.logger.error(self.cliente, "UPDATE", "Failure", f"Error assigning certificate: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def update_alta_status(self, cert_id: str, action: str, emails: str, user_name: str, sede: str, email_found: str, client_id: str) -> None:
        """Update certificate sede status and metadata"""
        conn = self.connect()
        cursor = conn.cursor()
        email_found_local = None if not email_found else email_found
        try:
            cursor.execute(f"""
            UPDATE certificates_sedes
            SET 
                state = 2,
                emails = %s,
                note= %s,
                action_id = %s,
                created_at_action = GETDATE(),
                downloads = {'NULL' if action == '8' else '1'},
                updatedby_user_id = 78,
                updatedby_user_name	= 'Adría Martínez',
                updated_at = GETDATE()
            FROM certificates_sedes cs
            WHERE cs.certificate_id = %s
            AND lower(sede) = %s
            """, (emails, email_found_local , action, cert_id, (sede).lower()))
            conn.commit()
            self.logger.info(self.cliente, sede, "Success", f"Updated certificates_sedes for user {user_name}")

        except pymssql.Error as e:
            self.logger.error(self.cliente, sede, "Failure", f"Error updating certificates_sedes: {e}")
            conn.rollback()
            raise
        finally:
            self.delete_assignment_log(id_value=f"alta_{client_id}_{sede}", robot_name="RobotAltas")
            conn.close()

    @retry_on_deadlock()
    def update_certificate_alert(self, certificate_id : str| int, cliente_id : str | int, alert_id : int, message: str, user_name: str) -> None:
        """Update certificate alert message"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            try:
                cursor.execute("""
                SELECT TOP 1 *
                    FROM certificates_managements_ 
                WHERE id = %s
                """, (certificate_id,))
                cert_info = cursor.fetchone()
                if not cert_info:
                    raise ValueError(f"Certificate with ID {certificate_id} not found.")
            except Exception as e:
                self.logger.error("ALTAS_DATABASE", cliente_id, "Failure", f"Error inspecting certificate info: {e}")
                raise

            # Build new note by concatenating existing note (if any) with incoming message
            existing_note = None
            try:
                existing_note = getattr(cert_info, 'note', None)
            except Exception:
                try:
                    existing_note = cert_info['note']
                except Exception:
                    existing_note = None

            new_note = f"{existing_note}\n{message}" if existing_note else message

            # Prepare existing certificate values safely (support attribute or mapping access)
            try:
                cert_created_at = getattr(cert_info, 'created_at')
            except Exception:
                try:
                    cert_created_at = cert_info['created_at']
                except Exception:
                    cert_created_at = None

            try:
                cert_created_warning_by_user_id = getattr(cert_info, 'created_warning_by_user_id')
            except Exception:
                try:
                    cert_created_warning_by_user_id = cert_info['created_warning_by_user_id']
                except Exception:
                    cert_created_warning_by_user_id = None

            try:
                cert_created_warning_by_user_name = getattr(cert_info, 'created_warning_by_user_name')
            except Exception:
                try:
                    cert_created_warning_by_user_name = cert_info['created_warning_by_user_name']
                except Exception:
                    cert_created_warning_by_user_name = None

            # Use parameterized query to avoid syntax errors and injection; COALESCE keeps existing values or defaults
            cursor.execute(
                """
                UPDATE certificates_managements_
                SET 
                    warning_id = %s,
                    note = %s,
                    created_at = COALESCE(%s, GETDATE()),
                    created_warning_by_user_id = COALESCE(%s, 78),
                    created_warning_by_user_name = COALESCE(%s, 'Adría Martínez'),
                    updated_at_warning = GETDATE(),
                    updated_warning_by_user_id = 78,
                    updated_warning_by_user_name = 'Adría Martínez'
                WHERE id = %s
                """,
                (
                    alert_id,
                    new_note,
                    cert_created_at,
                    cert_created_warning_by_user_id,
                    cert_created_warning_by_user_name,
                    certificate_id,
                ),
            )
            conn.commit()
            self.logger.info("ALTAS_DATABASE", cliente_id, "Success", f"Updated alert message for certificate {certificate_id}")
        except pymssql.Error as e:
            self.logger.error("ALTAS_DATABASE", cliente_id, "Failure", f"Error updating certificate alert: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def update_historico_alta(
        self,
        record: HistoricoAutomatizaciones,
        alta_record: Optional[AltasAutomatizaciones],
    ) -> None:
        """
        Update historico_automatizaciones and related altas_automatizaciones records.
        """
        # First update the historico record (may raise)
        self.update_historico(record)
        # If there's no alta record (e.g., the portal run produced no actionable alta),
        # we only needed to update the historico table above — nothing more to insert.
        if alta_record is None:
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Info",
                f"No altas_automatizaciones to insert for execution {record.execution_id}; historico updated only"
            )
            return

        conn = self.connect()
        cursor = conn.cursor()
        try:
            # Insert alta record (ensure no trailing comma in column list)
            cursor.execute(
                """
                INSERT INTO altas_automatizaciones (
                    id, execution_id, action, emails, downloads, notes
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    alta_record.id,
                    record.execution_id,
                    alta_record.action,
                    alta_record.emails,
                    int(bool(alta_record.downloads)),
                    alta_record.notes,
                )
            )

            # Commit once after all inserts
            conn.commit()
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Success",
                f"Inserted altas_automatizaciones for execution {record.execution_id}"
            )
            return None
        except pymssql.Error as e:
            conn.rollback()
            self.logger.error(
                self.cliente,
                record.execution_id,
                "Failure",
                f"Error inserting historico/alta records: {e}"
            )
            raise
        except Exception as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating altas_automatizaciones: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()



