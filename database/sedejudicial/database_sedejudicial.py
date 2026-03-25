from typing import Optional, List, Dict, Any
import pymssql
from database.database_manager import DatabaseManager
from app.models.database_models import ExpedienteJudicial, HistoricoAutomatizaciones, AltasAutomatizaciones, SedeJudicialAutomatizaciones, SeñalamientoJudicial


class SedeJudicialDatabase(DatabaseManager):
    """Database wrapper for 'sedejudicial' robot operations."""

    def __init__(self, db_config: Dict[str, Any], date: str, module: str, execution_id: str, filename: str = None):
        super().__init__(db_config=db_config, date=date, module=module, execution_id=execution_id, filename=filename, cliente="SEDEJUDICIAL_DATABASE")

    def fetch_sedejudicial(self, cliente: Optional[str], limit: str|int = 100) -> List[Dict[str, Any]]:
        """Fetch pending altas from the database, parametrized for sedes and cliente."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cliente_filter = " AND cm.customer_number = %s" if cliente is not None else ""
            query = f"""
                SELECT 
                    TOP {limit}
                    customer_number as id_cliente,
                    customer_number_type as tipo_cliente,
                    organization_name as nombre_cliente,
                    cif,
                    nif,
                    recipient_name,
                    'Seu Judicial Gencat' as sede

                FROM certificates_managements_ cm
                WHERE 1=1
                    AND cm.state in ('Completado')
                    AND cm.result in ('Vigente')
                    AND cm.valid_up_to > GETDATE()                                    
                    AND NOT EXISTS (
                    SELECT 1 FROM automations_assignment_log aal
                        WHERE aal.id = CAST(cm.customer_number AS VARCHAR(50)) + '_sedejudicial'
                        AND aal.robot_name = 'RobotConsulta'
                    )
                    {cliente_filter}
            """

            params = []
            if cliente is not None:
                params.append(cliente)
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]    
            sedejudicial = [dict(zip(columns, row)) for row in cursor.fetchall()]
            self.logger.info(self.cliente, "FETCH", "Success", f"Fetched {len(sedejudicial)} sedejudicial from database")
            return sedejudicial
            
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error fetching altas: {e}")
            raise
        finally:
            conn.close()
                    
    def update_historico_sedejudicial(
        self,
        record: HistoricoAutomatizaciones,
        sedejudicial_record: Optional[SedeJudicialAutomatizaciones],
        expedientes_judicial: Optional[List[ExpedienteJudicial]], 
        señalamientos_judicial: Optional[List[SeñalamientoJudicial]],
        justiciagratuita_judicial: Optional[List[Dict[str, Any]]] = []

    ) -> None:
        """
            Update historico_automatizaciones and related sede_judicial_automatizaciones records.
        """
        # First update the historico record (may raise)
        self.update_historico(record)
        # If there's no alta record (e.g., the portal run produced no actionable alta),
        # we only needed to update the historico table above — nothing more to insert.
        if sedejudicial_record is None:
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Info",
                f"No sedejudicial_automatizaciones to insert for execution {record.execution_id}; historico updated only"
            )
            return

        conn = self.connect()
        cursor = conn.cursor()
        try:
            # Insert sedejudicial record (ensure no trailing comma in column list)
            cursor.execute(
                """
                INSERT INTO sedejudicial_automatizaciones
                    (id, execution_id, num_expedientes, num_señalamientos, num_justicia_gratuita)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    sedejudicial_record.id,
                    record.execution_id,
                    sedejudicial_record.num_expedientes,
                    sedejudicial_record.num_señalamientos,
                    sedejudicial_record.num_justicia_gratuita,
                ),
            )

            # Commit once after all inserts
            conn.commit()
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Success",
                f"Inserted sedejudicial_automatizaciones for execution {record.execution_id}"
            )

            for justicia in justiciagratuita_judicial or []:
                # Insert justiciagratuita_judicial using fields from the JusticiaGratuitaJudicial model
                cursor.execute(
                    """
                    INSERT INTO justiciagratuita_judicial
                        (id, sedejudicial_id, codi_expedient, organ_judicial, procediment, n_act, 
                         estat, dictamen, sentit_resolucio_final, tipologia_resolucio)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(getattr(justicia, "id", None)) if getattr(justicia, "id", None) is not None else None,
                        str(getattr(justicia, "sedejudicial_id", None)) if getattr(justicia, "sedejudicial_id", None) is not None else None,
                        getattr(justicia, "codi_expedient", None),
                        getattr(justicia, "organ_judicial", None),
                        getattr(justicia, "procediment", None),
                        getattr(justicia, "n_act", None),
                        getattr(justicia, "estat", None),
                        getattr(justicia, "dictamen", None),
                        getattr(justicia, "sentit_resolucio_final", None),
                        getattr(justicia, "tipologia_resolucio", None),
                    ),
                )

                conn.commit()
                self.logger.info(
                    self.cliente,
                    record.execution_id,
                    "Success",
                    f"Inserted justiciagratuita_judicial {getattr(justicia, 'id', None)} for execution {record.execution_id}"
                )

            for expediente in expedientes_judicial or []:
                # Insert expediente_judicial using fields from the ExpedienteJudicial model
                cursor.execute(
                    """
                    INSERT INTO expediente_judicial
                        (id, sedejudicial_id, any_expediente, fecha_expediente, organo_judicial,
                         procedimiento, numero_any_seccion, nig, ambito, num_demanda, 
                         fecha_presentacion, fecha_registro, estado_expediente, juzgado, fecha_incoacion, 
                         fase, tipo_quantia, importe_principal)
                    VALUES (
                            %s, %s, %s, %s, %s,  
                            %s, %s, %s, %s, %s, 
                            %s, %s, %s, %s, %s, 
                            %s, %s, %s
                        )
                    """,
                    (
                        str(getattr(expediente, "id", None)) if getattr(expediente, "id", None) is not None else None,
                        str(getattr(expediente, "sedejudicial_id", None)) if getattr(expediente, "sedejudicial_id", None) is not None else None,
                        getattr(expediente, "any_expediente", None),
                        getattr(expediente, "fecha_expediente", None),
                        getattr(expediente, "organo_judicial", None),
                        getattr(expediente, "procedimiento", None),
                        getattr(expediente, "numero_any_seccion", None),
                        getattr(expediente, "nig", None),
                        getattr(expediente, "ambito", None),
                        getattr(expediente, "num_demanda", None),
                        getattr(expediente, "fecha_presentacion", None),
                        getattr(expediente, "fecha_registro", None),
                        getattr(expediente, "estado_expediente", None),
                        getattr(expediente, "juzgado", None),
                        getattr(expediente, "fecha_incoacion", None),
                        getattr(expediente, "fase", None),
                        getattr(expediente, "tipo_quantia", None),
                        getattr(expediente, "importe_principal", None),
                    ),
                )

                conn.commit()
                self.logger.info(
                    self.cliente,
                    record.execution_id,
                    "Success",
                    f"Inserted expediente_judicial {expediente.id} for execution {record.execution_id}"
                )

                for otro_procedimiento in expediente.otros_procedimientos or []:
                    cursor.execute(
                        """
                        INSERT INTO otros_procedimientos_expediente
                            (id, expediente_judicial_id, fecha_procedimiento, estado_procedimiento,
                                tipo_procedimiento, numero_año, organo_judicial)
                        VALUES (%s, %s, %s, %s, 
                                %s, %s, %s)
                        """,
                        (
                            str(getattr(otro_procedimiento, "id", None)) if getattr(otro_procedimiento, "id", None) is not None else None,
                            expediente.id,
                            getattr(otro_procedimiento, "fecha_procedimiento", None),
                            getattr(otro_procedimiento, "estado_procedimiento", None),
                            getattr(otro_procedimiento, "tipo_procedimiento", None),
                            getattr(otro_procedimiento, "numero_año", None),
                            getattr(otro_procedimiento, "organo_judicial", None),
                        ),
                    )

                    conn.commit()
                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted otros_procedimientos_expediente {getattr(otro_procedimiento, 'id', None)} for expediente {getattr(expediente, 'id', None)}"
                    )

                for interviniente in expediente.intervinientes or []:
                    cursor.execute(
                        """
                        INSERT INTO intervinientes_expediente
                            (id, expediente_judicial_id, nombre_interviniente, rol_interviniente,
                             correo_electronico, direccion, poblacion, municipio, 
                             provincia, pais, codigo_postal, telefono)
                        VALUES (%s, %s, %s, %s,
                                %s, %s, %s, %s, 
                                %s, %s, %s, %s)
                        """,
                        (
                            str(getattr(interviniente, "id", None)) if getattr(interviniente, "id", None) is not None else None,
                            expediente.id,
                            getattr(interviniente, "nombre_interviniente", None),
                            getattr(interviniente, "rol_interviniente", None),
                            getattr(interviniente, "correo_electronico", None),
                            getattr(interviniente, "direccion", None),
                            getattr(interviniente, "poblacion", None),
                            getattr(interviniente, "municipio", None),
                            getattr(interviniente, "provincia", None),
                            getattr(interviniente, "pais", None),
                            getattr(interviniente, "codigo_postal", None),
                            getattr(interviniente, "telefono", None),
                        ),
                    )

                    conn.commit()
                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted intervinientes_expediente {getattr(interviniente, 'id', None)} for expediente {getattr(expediente, 'id', None)}"
                    )
                
                for hito in expediente.hitos_procesales or []:
                    cursor.execute(
                        """
                        INSERT INTO hitos_expediente
                            (id, expediente_judicial_id, descripcion_hito, 
                            fecha_hito, fecha_resolucion, fecha_incoacion)
                        VALUES (%s, %s, %s, 
                                %s, %s, %s)
                        """,
                        (
                            str(getattr(hito, "id", None)) if getattr(hito, "id", None) is not None else None,
                            expediente.id,
                            getattr(hito, "descripcion_hito", None),
                            getattr(hito, "fecha_hito", None),
                            getattr(hito, "fecha_resolucion", None),
                            getattr(hito, "fecha_incoacion", None),
                        ),
                    )

                    conn.commit()
                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted hitos_expediente {getattr(hito, 'id', None)} for expediente {getattr(expediente, 'id', None)}"
                    )

            for señalamientos in señalamientos_judicial or []:
                cursor.execute(
                    """
                    INSERT INTO señalamiento_judicial
                        (id, sedejudicial_id, expediente_judicial_id, fecha_señalamiento, 
                        hora_inicio, hora_fin, sala, estado, 
                        motivo_anulacion, procedimiento)
                    VALUES (%s, %s, %s, %s, 
                            %s, %s, %s, %s, 
                            %s, %s)
                    """,
                    (
                        str(getattr(señalamientos, "id", None)) if getattr(señalamientos, "id", None) is not None else None,
                        str(getattr(señalamientos, "sedejudicial_id", None)) if getattr(señalamientos, "sedejudicial_id", None) is not None else None,
                        str(getattr(señalamientos, "expediente_judicial_id", None)) if getattr(señalamientos, "expediente_judicial_id", None) is not None else None,
                        getattr(señalamientos, "fecha_señalamiento", None),
                        getattr(señalamientos, "hora_inicio", None),
                        getattr(señalamientos, "hora_fin", None),
                        getattr(señalamientos, "sala", None),
                        getattr(señalamientos, "estado", None),
                        getattr(señalamientos, "motivo_anulacion", None),
                        getattr(señalamientos, "procedimiento", None),
                    ),
                )

                conn.commit()
                self.logger.info(
                    self.cliente,
                    record.execution_id,
                    "Success",
                    f"Inserted señalamientos_judicial {getattr(señalamientos, 'id', None)} for execution {record.execution_id}"
                )
                            

        except pymssql.Error as e:
            conn.rollback()
            self.logger.error(
                self.cliente,
                record.execution_id,
                "Failure",
                f"Error inserting historico/sedejudicial records: {e}"
            )
            raise
        except Exception as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating sedejudicial_automatizaciones: {e}")
            conn.rollback()
            raise
        finally:
            self.delete_assignment_log(id_value=f"{record.cliente}_sedejudicial", robot_name="RobotSedeJudicial")
            conn.close()



