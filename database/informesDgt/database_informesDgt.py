from datetime import datetime
from typing import Optional, List, Dict, Any
import pymssql
from database.database_manager import DatabaseManager, retry_on_deadlock
from app.models.database_models import HistoricoAutomatizaciones, InformesDgtAutomatizaciones, MatriculasExtraidas, SancionesExtraidas, AlertasExtraidas
import re


def _parse_date_field(val):
    """
    Parse date fields robustly: accept None, 'null', datetime objects, and different date formats.
    Handles DD/MM/YYYY, YYYY-MM-DD, YYYY-MM-DD HH:MM:SS formats.
    Returns datetime object or None.
    """
    if val is None:
        return None
    if isinstance(val, datetime):
        return val
    s = str(val).strip()
    if s == '' or s.lower() in ('none', 'null', 'n/a'):
        return None
    # Try common formats in order
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    # Try ISO fallback
    try:
        return datetime.fromisoformat(s)
    except (ValueError, TypeError):
        # Could not parse - return None
        return None


class InformesDgtDatabase(DatabaseManager):
    """Wrapper around DatabaseManager for 'informes DGT' robot-specific DB actions.

    Provides a small, well-typed surface for code that only needs informes-related
    database behavior without importing the large DatabaseManager directly.
    """

    def __init__(self, db_config: Dict[str, Any], date: str, module: str, execution_id: str, filename: str = None):
        super().__init__(db_config=db_config, date=date, module=module, execution_id=execution_id, filename=filename, cliente="INFORMES_DGT_DATABASE")

    def fetch_dev_clientes(self, clientes : Optional[List[int | str]] = None, limit: str | int = 300) -> List[Dict[str, Any]]:
        """Fetch clients from the DEV database"""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            # Build the conditional clause for clientes filtering
            clientes_clause = ""
            if clientes:
                # Convert all items to strings and format for SQL IN clause
                clientes_str = ", ".join(f"'{c}'" for c in clientes)
                clientes_clause = f"AND a.customer_number IN ({clientes_str})"

            cursor.execute(f"""
                SELECT TOP {limit} *
                    FROM (
                        SELECT
                            cert_sede_id,
                            customer_number,
                            certificate_id,
                            customer_number_type,
                            cif,
                            nif,
                            recipient_name,
                            sede,
                            created_at
                        FROM (
                            SELECT
                                b.id AS cert_sede_id,
                                a.customer_number,
                                b.certificate_id,
                                a.customer_number_type,
                                a.cif,
                                a.nif,
                                a.recipient_name,
                                b.sede,
                                med.created_at,
                                ROW_NUMBER() OVER (
                                    PARTITION BY b.id
                                    ORDER BY med.created_at DESC
                                ) AS rn
                            FROM certificates_managements_ a
                            INNER JOIN certificates_sedes b
                                ON a.id = b.certificate_id
                            LEFT JOIN (
                                SELECT
                                    ha.cliente,
                                    ha.created_at
                                FROM historico_automatizaciones ha
                                INNER JOIN informes_dgt_automatizaciones ida
                                    ON ida.execution_id = ha.execution_id
                                where ha.robot_name = 'RobotInformesDGT'
                                group by ha.cliente, ha.created_at
                            ) med
                                ON a.customer_number = med.cliente
                            WHERE b.sede = 'DEV'
                                AND a.result = 'Vigente'
                                AND a.state = 'Completado'
                                AND a.valid_from <= GETDATE()
                                AND a.valid_up_to >= GETDATE()
                                AND a.customer_number IS NOT NULL
                                AND a.customer_number <> ''
                                {clientes_clause}
                        ) AS o
                        WHERE rn = 1
                    ) AS t
                    ORDER BY created_at ASC;
            """)
            columns = [col[0] for col in cursor.description]
            clientes = [dict(zip(columns, row)) for row in cursor.fetchall()]
            self.logger.info(self.cliente, "FETCH", "Success", f"Fetched {len(clientes)} clients from DEV")
            return clientes
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error fetching clients from DEV: {e}")
            raise
        finally:
            conn.close()

    def ensure_column_exists(self, table: str, column: str, col_type: str = 'NVARCHAR(MAX)'):
        """Check if a column exists in the table, and create it if not."""
        conn = self.connect()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = %s AND COLUMN_NAME = %s
            """, (table, column))
            exists = cursor.fetchone()[0]
            if not exists:
                cursor.execute(f"ALTER TABLE {table} ADD {column} {col_type}")
                conn.commit()
        except Exception as e:
            self.logger.error(self.cliente, "SCHEMA", "Failure", f"Error ensuring column {column}: {e}")
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def insert_matriculas(self, cliente, matriculas: Dict[str, Any]) -> None:
        """Insert or update matriculas into the database, including all fields from 'detalles' if present. Crea columnas si no existen."""
        """
        {
        'fecha_extraccion': '2025-06-11 15:37:35', 
        'vehiculos': [
            MatriculasExtraidas(id=UUID('3ec360b2-c703-4720-b46d-f8f8aaeaa5a4'), informe_id=UUID('2b3ace94-3992-4731-b5cb-d9bbc544c1b2'), matricula='8299KBJ', matriculacion='29/06/2017', marca='PEUGEOT', modelo='PARTNER TEPEE STYLE 1.', combustible='DIESEL', situacion_administrativa=' ALTA', servicio_al_que_se_destina='SERVICIO PARTICULAR -B00 -SIN ESPECIFICAR', bastidor='VF37JBHZMHJ576549', cilindrada_cm='1560.0', distintivo_ambiental='etiqueta-c', num_identificacion_vehiculo_nive='BBD04F9A81A942EA9633781FCD1E2756', situacion_itv='FAVORABLE', caducidad_itv='08/11/2025', km_ultima_itv=148567, inicio_del_seguro='01/06/2025', aseguradora='OCCIDENT GCO, S.A. DE SGS. Y RSGS.', direccion='CALLE CARMEN AMAYA P GORNAL , NU: 33 , PLA: 10 , PTA: 4', codigo_postal='08902', municipio='L HOSPITALET DE LLOB', provincia='BARCELONA', created_at=datetime.datetime(2025, 11, 6, 15, 37, 44, 119659), updated_at=None),
            MatriculasExtraidas(id=UUID('dc48a56a-cbf6-4d0c-9d9d-57cf7c12bb89'), informe_id=UUID('2b3ace94-3992-4731-b5cb-d9bbc544c1b2'), matricula='9899GWS', matriculacion='28/05/2010', marca='HONDA', modelo='CR-V', combustible='DIESEL', situacion_administrativa=' ALTA', servicio_al_que_se_destina='SERVICIO PARTICULAR -B00 -SIN ESPECIFICAR', bastidor='SHSRE6870AU007598', cilindrada_cm='2199.0', distintivo_ambiental='etiqueta-b', num_identificacion_vehiculo_nive='No disponible por su antigüedad', situacion_itv='FAVORABLE', caducidad_itv='25/06/2026', km_ultima_itv=276418, inicio_del_seguro='15/05/2025', aseguradora='OCCIDENT GCO, S.A. DE SGS. Y RSGS.', direccion='CR CARMEN AMAYA 33 10 4', codigo_postal='08902', municipio='L HOSPITALET DE LLOB', provincia='BARCELONA', created_at=datetime.datetime(2025, 11, 6, 15, 37, 45, 414510), updated_at=None)
        ], 
        'alertas': [
            AlertasExtraidas(id=UUID('65b4e703-ee59-42a2-a48f-59b38f0f0aac'), matricula_id=UUID('3ec360b2-c703-4720-b46d-f8f8aaeaa5a4'), alertas_vehiculo='La ITV de tu vehículo con matrícula 8299KBJ está a punto de caducar.', created_at=datetime.datetime(2025, 11, 6, 15, 37, 44, 120002))
        ]}

        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error connecting to the database: {e}")
            raise
        except Exception as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error connecting to the database: {e}")
            raise

        try:
            fecha_extraccion = matriculas.get('fecha_extraccion', None)
            if not matriculas['vehiculos']:
                cursor.execute("""
                    MERGE matriculas_extracted_dev AS target
                    USING (SELECT %s AS cliente, NULL AS matricula) AS source
                    ON target.cliente = source.cliente AND target.matricula IS NULL
                    WHEN MATCHED THEN
                        UPDATE SET
                            nif = %s,
                            cif = %s,
                            tipo_cliente = %s,
                            fecha_extraccion = %s
                    WHEN NOT MATCHED THEN
                        INSERT (cliente, nif, cif, tipo_cliente, 
                               fecha_extraccion, matricula, matriculacion, marca, 
                               modelo, combustible, alertas_vehiculo, situacion_administrativa,
                               servicio_al_que_se_destina, bastidor, carburante, cilindrada_cm, 
                               distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv, caducidad_itv, 
                               km_ultima_itv, inicio_del_seguro, aseguradora, direccion, 
                               codigo_postal, municipio, provincia)
                        VALUES (%s, %s, %s, %s, 
                               %s, NULL, NULL, NULL, 
                               NULL, NULL, NULL, NULL, 
                               NULL, NULL, NULL, NULL, 
                               NULL, NULL, NULL, NULL, 
                               NULL, NULL, NULL, NULL, 
                               NULL, NULL, NULL);
                """,
                (
                    cliente['customer_number'],
                    cliente['nif'],
                    cliente['cif'],
                    cliente['customer_number_type'],
                    fecha_extraccion,
                    cliente['customer_number'],
                    cliente['nif'],
                    cliente['cif'],
                    cliente['customer_number_type'],
                    fecha_extraccion,
                ))
            else:
                for matricula in matriculas['vehiculos']:
                    alertas = matriculas.get('alertas', [])
                    situacion_administrativa = matricula.situacion_administrativa
                    servicio_al_que_se_destina = matricula.servicio_al_que_se_destina
                    bastidor = matricula.bastidor
                    carburante = matricula.combustible
                    cilindrada_cm = matricula.cilindrada_cm
                    distintivo_ambiental = matricula.distintivo_ambiental
                    num_identificacion_vehiculo_nive = matricula.num_identificacion_vehiculo_nive
                    situacion_itv = matricula.situacion_itv
                    
                    # Parse date fields using module-level helper
                    matriculacion_parsed = _parse_date_field(matricula.matriculacion)
                    caducidad_itv = _parse_date_field(matricula.caducidad_itv)
                    km_ultima_itv = matricula.km_ultima_itv
                    inicio_del_seguro = _parse_date_field(matricula.inicio_del_seguro)
                    aseguradora = matricula.aseguradora
                    direccion = matricula.direccion
                    codigo_postal = matricula.codigo_postal
                    municipio = matricula.municipio
                    provincia = matricula.provincia

                    if not alertas:
                        cursor.execute("""
                            MERGE matriculas_extracted_dev AS target
                            USING (SELECT %s AS cliente, %s AS matricula) AS source
                            ON target.cliente = source.cliente AND target.matricula = source.matricula
                            WHEN MATCHED THEN
                                UPDATE SET
                                    nif = %s,
                                    cif = %s,
                                    tipo_cliente = %s,
                                    fecha_extraccion = %s,
                                    matriculacion = %s,
                                    marca = %s,
                                    modelo = %s,
                                    combustible = %s,
                                    alertas_vehiculo = NULL,
                                    situacion_administrativa = %s,
                                    servicio_al_que_se_destina = %s,
                                    bastidor = %s,
                                    carburante = %s,
                                    cilindrada_cm = %s,
                                    distintivo_ambiental = %s,
                                    num_identificacion_vehiculo_nive = %s,
                                    situacion_itv = %s,
                                    caducidad_itv = %s,
                                    km_ultima_itv = %s,
                                    inicio_del_seguro = %s,
                                    aseguradora = %s,
                                    direccion = %s,
                                    codigo_postal = %s,
                                    municipio = %s,
                                    provincia = %s
                            WHEN NOT MATCHED THEN
                                INSERT (cliente, nif, cif, tipo_cliente, 
                                       fecha_extraccion, matricula, matriculacion, marca, 
                                       modelo, combustible, alertas_vehiculo, situacion_administrativa, servicio_al_que_se_destina, 
                                       bastidor, carburante, cilindrada_cm, distintivo_ambiental, 
                                       num_identificacion_vehiculo_nive, situacion_itv, caducidad_itv, km_ultima_itv, 
                                       inicio_del_seguro, aseguradora, direccion, codigo_postal, 
                                       municipio, provincia)
                                VALUES (%s, %s, %s, %s, 
                                       %s, %s, %s, %s, 
                                       %s, %s, NULL, %s, %s, 
                                       %s, %s, %s, %s, 
                                       %s, %s, %s, %s, 
                                       %s, %s, %s, %s, 
                                       %s, %s);
                        """,
                        (
                            cliente['customer_number'], matricula.matricula,
                            cliente['nif'], cliente['cif'], cliente['customer_number_type'], fecha_extraccion,
                            matriculacion_parsed, matricula.marca, matricula.modelo,
                            matricula.combustible,
                            situacion_administrativa, servicio_al_que_se_destina, bastidor, carburante, cilindrada_cm,
                            distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv, caducidad_itv,
                            km_ultima_itv, inicio_del_seguro, aseguradora, direccion, codigo_postal, municipio, provincia,
                            cliente['customer_number'], cliente['nif'], cliente['cif'], cliente['customer_number_type'],
                            fecha_extraccion, matricula.matricula, matriculacion_parsed,
                            matricula.marca, matricula.modelo, matricula.combustible,
                            situacion_administrativa, servicio_al_que_se_destina, bastidor, carburante, cilindrada_cm,
                            distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv, caducidad_itv,
                            km_ultima_itv, inicio_del_seguro, aseguradora, direccion, codigo_postal, municipio, provincia
                        ))
                    else:
                        for alerta in alertas:
                            cursor.execute("""
                                UPDATE matriculas_extracted_dev
                                SET alertas_vehiculo = %s,
                                    situacion_administrativa = %s,
                                    servicio_al_que_se_destina = %s,
                                    bastidor = %s,
                                    carburante = %s,
                                    cilindrada_cm = %s,
                                    distintivo_ambiental = %s,
                                    num_identificacion_vehiculo_nive = %s,
                                    situacion_itv = %s,
                                    caducidad_itv = %s,
                                    km_ultima_itv = %s,
                                    inicio_del_seguro = %s,
                                    aseguradora = %s,
                                    direccion = %s,
                                    codigo_postal = %s,
                                    municipio = %s,
                                    provincia = %s
                                WHERE cliente = %s AND matricula = %s AND alertas_vehiculo IS NULL
                            """,
                            (
                                alerta.alertas_vehiculo, situacion_administrativa, servicio_al_que_se_destina, bastidor, carburante,
                                cilindrada_cm, distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv,
                                caducidad_itv, km_ultima_itv, inicio_del_seguro, aseguradora, direccion, codigo_postal,
                                municipio, provincia, cliente['customer_number'], matricula.matricula
                            ))

                            if cursor.rowcount > 0:
                                continue

                            cursor.execute("""
                                MERGE matriculas_extracted_dev AS target
                                USING (
                                    SELECT %s AS cliente, %s AS matricula, %s AS alertas_vehiculo
                                ) AS source
                                ON target.cliente = source.cliente AND target.matricula = source.matricula AND target.alertas_vehiculo = source.alertas_vehiculo
                                WHEN NOT MATCHED THEN
                                    INSERT (cliente, nif, cif, tipo_cliente, 
                                           fecha_extraccion, matricula, matriculacion, marca, 
                                           modelo, combustible, alertas_vehiculo, situacion_administrativa, 
                                           servicio_al_que_se_destina, bastidor, carburante, cilindrada_cm, 
                                           distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv, caducidad_itv,
                                           km_ultima_itv, inicio_del_seguro, aseguradora, direccion, 
                                           codigo_postal, municipio, provincia)
                                    VALUES (%s, %s, %s, %s, 
                                           %s, %s, %s, %s, 
                                           %s, %s, %s, %s, 
                                           %s, %s, %s, %s, 
                                           %s, %s, %s, %s, 
                                           %s, %s, %s, %s, 
                                           %s, %s, %s);
                            """,
                            (
                                cliente['customer_number'], matricula.matricula, alerta.alertas_vehiculo,
                                cliente['customer_number'], cliente['nif'], cliente['cif'],
                                cliente['customer_number_type'], fecha_extraccion, matricula.matricula,
                                matriculacion_parsed, matricula.marca, matricula.modelo,
                                matricula.combustible, alerta.alertas_vehiculo, situacion_administrativa, servicio_al_que_se_destina,
                                bastidor, carburante, cilindrada_cm, distintivo_ambiental, num_identificacion_vehiculo_nive,
                                situacion_itv, caducidad_itv, km_ultima_itv, inicio_del_seguro, aseguradora,
                                direccion, codigo_postal, municipio, provincia
                            ))

            conn.commit()
            self.logger.info(self.cliente, "INSERT", "Success", f"Inserted or updated {len(matriculas['vehiculos'])} matriculas into the database")
        except pymssql.Error as e:
            self.logger.error(self.cliente, "INSERT", "Failure", f"Error inserting/updating matriculas: {e}")
            conn.rollback()
            raise
        except Exception as e:
            self.logger.error(self.cliente, "INSERT", "Failure", f"Error inserting/updating matriculas: {e}")
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def insert_puntos(self, cliente, puntos: Dict[str, Any]) -> None:
        """Insert puntos into the database"""
        """
            {
                'fecha_extraccion': '2025-07-11 08:27:41', 
                'NIF': '38042604', 
                'nombre': 'JUAN ANTONIO TEBA FRANCH', 
                'puntos': '14', 
                'sanciones': [
                    SancionesExtraidas(id=UUID('4edf3100-1602-4797-ab02-236c8a8dcaa1'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='BONIFICACION A 14', saldo_puntos_final=14, organismo_sancionador=None, created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 93349)), 
                    SancionesExtraidas(id=UUID('2e71b201-3c0e-45fb-8dc0-9a183d62fb5f'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='BONIFICACION A 15', saldo_puntos_final=15, organismo_sancionador=None, created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 180100)), 
                    SancionesExtraidas(id=UUID('2e8b2020-3f99-4efb-b645-12ba56f637b5'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='[Alta]:CIR Art. 50 Apdo. 1 Num.Exp. 88493530', saldo_puntos_final=13, organismo_sancionador='Viladecans', created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 259879)), 
                    SancionesExtraidas(id=UUID('485deeb5-2689-4ec6-8762-12f031ca50d7'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='[Alta]:CIR Art. 50 Apdo. 1 Num.Exp. 88497673', saldo_puntos_final=11, organismo_sancionador='Viladecans', created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 329696)), 
                    SancionesExtraidas(id=UUID('b4240344-205e-47eb-be05-bd6eca39ef97'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='Movimiento de Recuperación de puntos', saldo_puntos_final=12, organismo_sancionador=None, created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 432641)), 
                    SancionesExtraidas(id=UUID('651310d6-c3ae-494d-9c9d-4857139402fc'), informe_id=UUID('0b4fa253-6dbf-4f4d-b84d-047c0d013cf2'), fecha_sancion=None, puntos_sancion=None, sancion='Movimiento de Bonificación + 2 puntos', saldo_puntos_final=14, organismo_sancionador=None, created_at=datetime.datetime(2025, 11, 7, 8, 27, 42, 554251))
                ]
            }
        """
        try:
            conn = self.connect()
            cursor = conn.cursor()
        except pymssql.Error as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Error connecting to the database: {e}")
            raise
        except Exception as e:
            self.logger.error(self.cliente, "FETCH", "Failure", f"Unexpected error: {e}")
            raise

        try:
            sanciones = puntos.get('sanciones', [])
            if not sanciones:
                sanciones = [None]

            for sancion in sanciones:
                if sancion is None:
                    fecha_sancion = None
                    puntos_sancion = None
                    sancion_movimiento = None
                    saldo_puntos_final = None
                    organismo_sancionador = None
                else:
                    fecha_sancion = sancion.fecha_sancion
                    puntos_sancion = int(sancion.puntos_sancion) if sancion.puntos_sancion else None
                    sancion_movimiento = sancion.sancion
                    saldo_puntos_final = int(sancion.saldo_puntos_final) if sancion.saldo_puntos_final else None
                    organismo_sancionador = sancion.organismo_sancionador

                cursor.execute("""
                    MERGE puntos_extracted_dev AS target
                    USING (
                        SELECT %s AS cliente, %s AS nif_en_sede, %s AS fecha_sancion, %s AS sancion
                    ) AS source
                    ON target.cliente = source.cliente AND target.nif_en_sede = source.nif_en_sede
                       AND ((target.fecha_sancion IS NULL AND source.fecha_sancion IS NULL) OR target.fecha_sancion = source.fecha_sancion)
                       AND ((target.sancion IS NULL AND source.sancion IS NULL) OR target.sancion = source.sancion)
                    WHEN MATCHED THEN
                        UPDATE SET
                            nif = %s,
                            cif = %s,
                            tipo_cliente = %s,
                            fecha_extraccion = %s,
                            nombre_en_sede = %s,
                            puntos = %s,
                            puntos_sancion = %s,
                            saldo_puntos_final = %s,
                            organismo_sancionador = %s
                    WHEN NOT MATCHED THEN
                        INSERT (
                            cliente, nif, cif, tipo_cliente, fecha_extraccion, nif_en_sede, nombre_en_sede, puntos,
                            fecha_sancion, puntos_sancion, sancion, saldo_puntos_final, organismo_sancionador
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
                """, (
                    cliente['customer_number'], puntos.get('NIF'), fecha_sancion, sancion_movimiento,
                    cliente['nif'], cliente['cif'], cliente['customer_number_type'], puntos.get('fecha_extraccion'),
                    puntos.get('nombre'), int(puntos.get('puntos', 0)), puntos_sancion, saldo_puntos_final,
                    organismo_sancionador,
                    cliente['customer_number'], cliente['nif'], cliente['cif'], cliente['customer_number_type'],
                    puntos.get('fecha_extraccion'), puntos.get('NIF'), puntos.get('nombre'),
                    int(puntos.get('puntos', 0)), fecha_sancion, puntos_sancion, sancion_movimiento,
                    saldo_puntos_final, organismo_sancionador
                ))

            conn.commit()
            self.logger.info(self.cliente, "INSERT", "Success", f"Inserted puntos for cliente {cliente['customer_number']} into the database")
        except pymssql.Error as e:
            self.logger.error(self.cliente, "INSERT", "Failure", f"Error inserting puntos: {e}")
            conn.rollback()
            raise
        except Exception as e:
            self.logger.error(self.cliente, "INSERT", "Failure", f"Error inserting puntos: {e}")
            raise
        finally:
            conn.close()

    @retry_on_deadlock()
    def update_historico_informesDgt(
        self,
        record: HistoricoAutomatizaciones,
        informeDgt_record: Optional[InformesDgtAutomatizaciones] = None,
        matriculas_records:  Optional[List[MatriculasExtraidas]] = None,
        sanciones_records:  Optional[List[SancionesExtraidas]] = None,
        alertas_records:  Optional[List[AlertasExtraidas]] = None,
    ) -> None:
        """
        Update historico_automatizaciones and related informeDGT_automatizaciones records.
        """
        # First update the historico record (may raise)
        self.update_historico(record)

        conn = self.connect()
        cursor = conn.cursor()
        try:
            if informeDgt_record is None:
                raise ValueError("informeDgt_record must be provided")

            # Use informeDgt_record fields to populate informes_dgt_automatizaciones and keep a consulta_record alias
            # Insert into informes_dgt_automatizaciones using fields from the Pydantic model
            cursor.execute( 
                """
                INSERT INTO informes_dgt_automatizaciones (
                    id,
                    execution_id,
                    nif_en_sede,
                    nombre_en_sede,
                    matriculas,
                    puntos,
                    created_at,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, GETDATE(), NULL)
                """,
                (
                    informeDgt_record.id,
                    record.execution_id,
                    informeDgt_record.nif_en_sede,
                    informeDgt_record.nombre_en_sede,
                    informeDgt_record.matriculas,
                    informeDgt_record.puntos,
                ),
            )

            self.logger.info(
                self.cliente,
                record.execution_id,
                "Success",
                f"Inserted informeDGT automatizaciones {informeDgt_record.id} for execution {record.execution_id}"
            )

            if matriculas_records is None:
                matriculas_records = []

            for matricula in matriculas_records:
                try:
                    raw = matricula.matricula.strip().upper()
                    # Handle cases like "Matrícula P4339BCR P4339BCR" - extract only the plate
                    # Pattern: optional letter + 4 digits + 3 letters (e.g., P4339BCR or 6839DWC)
                    pattern = re.compile(r'\b([A-Z]?\d{4}[A-Z]{3})\b', re.I)
                    matches = pattern.findall(raw)
                    if matches:
                        # Remove duplicates while preserving order and normalize to uppercase
                        seen = set()
                        unique = []
                        for m in matches:
                            mu = m.upper()
                            if mu not in seen:
                                seen.add(mu)
                                unique.append(mu)
                        matricula_sanitized = unique[0]
                    else:
                        # Fallback: remove non-alphanumeric characters and normalize
                        cleaned = re.sub(r'[^A-Z0-9]', '', raw.upper())
                        matricula_sanitized = cleaned if cleaned else raw.strip().upper()

                except Exception:
                    matricula_sanitized = matricula.matricula.strip().upper()

                try:
                    # Parse date fields using helper function
                    matriculacion_parsed = _parse_date_field(matricula.matriculacion)
                    caducidad_itv_parsed = _parse_date_field(matricula.caducidad_itv)
                    inicio_del_seguro_parsed = _parse_date_field(matricula.inicio_del_seguro)
                    
                    cursor.execute(
                        """
                        INSERT INTO matriculas_extraidas (
                            id, informe_id, matricula, matriculacion, marca, modelo, combustible, bastidor,
                            cilindrada_cm, distintivo_ambiental, num_identificacion_vehiculo_nive, situacion_itv,
                            caducidad_itv, km_ultima_itv, inicio_del_seguro, aseguradora, direccion, codigo_postal,
                            municipio, provincia, situacion_administrativa, servicio_al_que_se_destina, created_at, updated_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, GETDATE(), NULL)
                        """,
                        (
                            matricula.id,
                            informeDgt_record.id,
                            matricula_sanitized,
                            matriculacion_parsed,
                            matricula.marca,
                            matricula.modelo,
                            matricula.combustible,
                            matricula.bastidor,
                            float(matricula.cilindrada_cm),
                            matricula.distintivo_ambiental,
                            matricula.num_identificacion_vehiculo_nive,
                            matricula.situacion_itv,
                            caducidad_itv_parsed,
                            matricula.km_ultima_itv,
                            inicio_del_seguro_parsed,
                            matricula.aseguradora,
                            matricula.direccion,
                            matricula.codigo_postal,
                            matricula.municipio,
                            matricula.provincia,
                            matricula.situacion_administrativa,
                            matricula.servicio_al_que_se_destina,
                        ),
                    )    

                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted matricula {matricula.id} for informe {informeDgt_record.id}"
                    )

                    if alertas_records is None:
                        alertas_records = []

                    for alerta in alertas_records:
                        if alerta.matricula_id != matricula.id:
                            break

                        try:
                            cursor.execute(
                                """
                                INSERT INTO alertas_extraidas (
                                    id, matricula_id, alertas_vehiculo, created_at
                                ) VALUES (%s, %s, %s, GETDATE())
                                """,
                                (
                                    alerta.id,
                                    matricula.id,
                                    alerta.alertas_vehiculo,
                                ),
                            )

                            self.logger.info(
                                self.cliente,
                                record.execution_id,
                                "Success",
                                f"Inserted alerta {alerta.id} for matricula {matricula.id} of informe {informeDgt_record.id}"
                            )
                        except pymssql.Error as e:
                            self.logger.error(
                                self.cliente,
                                record.execution_id,
                                "Failure",
                                f"Error inserting alerta {alerta.id} para la matricula {matricula.id} del informe {informeDgt_record.id} : {e}"
                            )
                            raise    
                        finally:
                            try:
                                alertas_records.remove(alerta)
                            except (ValueError, AttributeError):
                                pass


                
                except pymssql.Error as e:
                    self.logger.error(
                        self.cliente,
                        record.execution_id,
                        "Failure",
                        f"Error inserting matricula {matricula.id} para el informe {informeDgt_record.id} : {e}  : {matricula}"
                    )
                    continue  # Proceed to next matricula
                
            if sanciones_records is None:
                sanciones_records = []
            
            for sancion in sanciones_records:
                try:
                    cursor.execute(
                        """
                        INSERT INTO sanciones_extraidas (
                            id, informe_id, fecha_sancion, puntos_sancion, sancion, saldo_puntos_final,
                            organismo_sancionador, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, GETDATE())
                        """,
                        (
                            sancion.id,
                            informeDgt_record.id,
                            sancion.fecha_sancion,
                            sancion.puntos_sancion,
                            sancion.sancion,
                            sancion.saldo_puntos_final,
                            sancion.organismo_sancionador,
                        ),
                    )

                    self.logger.info(
                        self.cliente,
                        record.execution_id,
                        "Success",
                        f"Inserted sancion {sancion.id} for informe {informeDgt_record.id}"
                    )

                except pymssql.Error as e:
                    self.logger.error(
                        self.cliente,
                        record.execution_id,
                        "Failure",
                        f"Error inserting sancion {sancion.id} para el informe {informeDgt_record.id} : {e}"
                    )
                    raise

            # Commit all inserts at the end
            conn.commit()
            self.logger.info(
                self.cliente,
                record.execution_id,
                "Success",
                f"All records inserted successfully for execution {record.execution_id}"
            )

        except pymssql.Error as e:
            conn.rollback()
            self.logger.error(
                self.cliente,
                record.execution_id,
                "Failure",
                f"Error inserting historico/informesDgt records: {e}"
            )
            raise
        except Exception as e:
            self.logger.error(self.cliente, record.execution_id, "Failure", f"Error updating informes_dgt_automatizaciones: {e}")
            conn.rollback()
            raise
        finally:
            # self.delete_assignment_log(id_value=f"informedgt_{record.cliente}_dev", robot_name=str(record.robot_name))
            conn.close()
