from multiprocessing import Process, Queue
from uuid import uuid4
from dotenv import load_dotenv

# PERSONAL PACKAGES - UTILS
import os, time

import pymssql

from app.helper.loggerV2 import LoggerV2
from database.database_manager import DatabaseManager
from app.robot_descargas import extract_and_validate_service_info, log_listener
import json


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

def main():
    default_date = '2026-02-09'
    execution_id = str(uuid4())
    database_manager = DatabaseManager(
        db_config=db_config,
        date=default_date,
        module='Playground',
        execution_id=execution_id
    )

    query = """
        SELECT 
            ea.email AS email_account,
            em.message_key,
            em.message_id,
            em.date,
            em.expired_date,
            cs.sede,
            em.customer_number AS client_id,
            dsce.especial AS aviso_especial,
            ssc.customer_number AS checkscc,
            'MULTINEO' AS servicio,
            c.provincia,
            (SELECT TOP 1 fechafin 
            FROM info.BeneficiarioBonos 
            WHERE idbenef = em.customer_number 
            AND servicio LIKE '%SUSCRIPCION%' 
            AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
            AND fechafin > em.[date] 
            ORDER BY fechafin DESC) AS SUSCRIPCION,
            (SELECT TOP 1 fechafin 
            FROM info.BeneficiarioBonos 
            WHERE idbenef = em.customer_number 
            AND servicio LIKE '%NEO_CASH%' 
            AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
            AND fechafin > em.[date] 
            ORDER BY fechafin DESC) AS NEOCASH,
            (SELECT TOP 1 fechafin 
            FROM info.BeneficiarioBonos 
            WHERE idbenef = em.customer_number 
            AND servicio LIKE '%NEO_ESTATAL%' 
            AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
            AND fechafin > em.[date] 
            ORDER BY fechafin DESC) AS NEOESTATAL,            
            (SELECT TOP 1 fechafin 
            FROM info.BeneficiarioBonos 
            WHERE idbenef = em.customer_number 
            AND servicio LIKE '%INFO_NEO%' 
            AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
            AND fechafin > em.[date] 
            ORDER BY fechafin DESC) AS INFONEO,
            (SELECT TOP 1 fechafin 
            FROM info.BeneficiarioBonos 
            WHERE idbenef = em.customer_number 
            AND servicio LIKE '%BLINDAJE%' 
            AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
            AND fechafin > em.[date] 
            ORDER BY fechafin DESC) AS BLINDAJE,
            (SELECT TOP 1 [TO] 
            FROM sin_servicio_contratado 
            WHERE customer_number = em.customer_number 
            AND [TO] > em.[date] 
            AND (Oferta LIKE '%GRATIS%' OR Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%')
            ORDER BY [TO] DESC) AS MULTINEO,
            c.nif AS nif,
            c.nifempresa AS cif,
            tc.concepto AS tipo_cliente,
            es.name AS status,
            em.[from] AS mail,
            em.subject AS asunto,
            em.body_html
        FROM [dbo].[emails_messages] em
        INNER JOIN [dbo].[emails_accounts] ea 
            ON em.email_account_id = ea.id
        INNER JOIN [dbo].[certificates_sedes_cat] cs 
            ON em.sedes_cat_id = cs.id
        INNER JOIN [dbo].[clientes] c
            ON em.customer_number = c.numerocliente
        INNER JOIN [dbo].[emails_status] es
            ON em.status_id = es.id
        LEFT JOIN descargaespecial dsce
            ON dsce.cliente = em.customer_number
        LEFT JOIN sin_servicio_contratado ssc
            ON em.customer_number = ssc.customer_number
        LEFT JOIN tblvTipoCliente tc
            ON tc.idTipoCliente = c.tipodecliente
        WHERE 
            em.customer_number IS NOT NULL
            AND em.parent_id IS NULL
            AND LOWER(cs.sede) IN ('dehù', 'enotum') 
            AND em.body_html IS NOT NULL
            AND em.date > GETDATE()-9 AND em.date <= GETDATE()-2
			AND es.name in ('Pendiente', 'Agencia Tributaria')
            AND (
                EXISTS (
                    SELECT 1 FROM info.BeneficiarioBonos ibb_chk
                    WHERE ibb_chk.idbenef = em.customer_number
                    AND (
                        ibb_chk.servicio LIKE '%SEDES BIANUAL%' 
                        OR ibb_chk.servicio LIKE '%SUSCRIPCION SEDES%' 
                        OR ibb_chk.servicio LIKE '%NEO%' 
                        OR ibb_chk.servicio LIKE '%BLINDAJE%'
                    )
                )
                OR (
                    ssc.Oferta LIKE '%SEDES BIANUAL%' 
                    OR ssc.Oferta LIKE '%SUSCRIPCION SEDES%' 
                    OR ssc.Oferta LIKE '%NEO%' 
                    OR ssc.Oferta LIKE '%BLINDAJE%'
                )
            )
            AND EXISTS (
                SELECT 1 FROM info.BeneficiarioBonos ibb_chk2
                WHERE ibb_chk2.idbenef = em.customer_number
                AND ibb_chk2.situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP')
            )
            AND c.baja = 0
            AND c.numerocliente > 0
            AND (
                (
                    EXISTS (
                        SELECT 1 FROM info.BeneficiarioBonos ibb_dates
                        WHERE ibb_dates.idbenef = em.customer_number
                        AND ibb_dates.fechafin > em.[date]
                        AND ibb_dates.fechafin > GETDATE()
                    )
                )
                OR (ssc.[to] > em.[date] AND ssc.[to] > GETDATE())
            )
    """

    # Inicializa el logger
    logger = LoggerV2(
        module="Playground",
        class_name="playground",
        log_dir="logs/playground",
        filename=f"playground_{default_date}"
    )

    log_queue = Queue()
    listener = Process(target=log_listener, args=(log_queue, default_date, execution_id))
    listener.start()

    try:
        conn = database_manager.connect()
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [col[0] for col in cursor.description]
        notifications = [dict(zip(columns, row)) for row in cursor.fetchall()]

        print(f"[INFO] - Retrieved {len(notifications)} records from the database.")
    except pymssql.Error as e:
        print(f"[ERROR] - Database error: {e}")
        if 'conn' in locals() and conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()

    try:
        # Mapa de identificador -> lista de message_key
        id_to_message_keys = {}
        organismos_list = {}
        

        for notification in notifications:
            notification_to_save = {
                "message_key": notification.get('message_key'),
                "message_id": notification.get('message_id'),
                "sede": notification.get('sede'),
                "client_id": notification.get('client_id'),
                "mail": notification.get('mail'),
                "status": notification.get('status'),
                "date" : notification.get('date'),
            }

            print(f"[INFO] - Processing email ID: {notification.get('message_key')}, Customer Number: {notification.get('client_id')}")

            parsed = extract_and_validate_service_info(
                logger=logger,
                execution_id=execution_id,
                notification=notification,
                date=default_date,
                database_manager=database_manager,
                log_queue=log_queue,
            )

            if parsed:
                sede, body_data, date, valid_services = parsed

                if body_data:
                    # print(f"[INFO] - Extracted Service Info: {body_data}")

                    # Extrae el identificador del body y agrupa message_key por identificador
                    identificador = body_data.get('identificador')
                    if identificador:
                        id_to_message_keys.setdefault(str(identificador), []).append(notification_to_save)
                    else:
                        print(f"[WARNING] - 'identificador' not found in body_data for message_key: {notification.get('message_key')}")

                    organismo = body_data.get('organismo') or body_data.get('org')
                    if organismo:
                        if organismo not in organismos_list:
                            organismos_list[organismo] = []
                        organismos_list[organismo].append(notification.get('client_id'))

            else:
                print(f"[WARNING] - No valid service info found for message_key: {notification.get('message_key')}")
    except Exception as e:
        print(f"[ERROR] - An error occurred: {e}")
        raise

    try:
        json_path = os.path.join("files", "playground", f"organismos_list_{default_date}_{execution_id}.json")
        os.makedirs(os.path.dirname(json_path), exist_ok=True)
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(organismos_list, f, ensure_ascii=False, indent=2)
        print(f"[INFO] - Saved organismos_list to {json_path}")
    except Exception as e:
        print(f"[ERROR] - Could not save organismos_list: {e}")
    
    # try:
    #     updated_message_keys = set()
    #     # Determine the status_id for the 'Descargado' status
    #     conn = database_manager.connect()
    #     cursor = conn.cursor()
    #     status_name = 'Descargado'
    #     # cursor.execute("SELECT id FROM emails_status WHERE LOWER(name) = %s", (status_name.lower(),))
    #     # row = cursor.fetchone()
    #     # if not row:
    #         # print(f"[WARNING] - Could not find status id for '{status_name}', skipping updates.")
    #     # else:
    #         # status_id = row[0]

    #     update_query = """
    #             UPDATE em
    #             SET 
    #                 em.updated_at = GETDATE(),
    #                 em.status_id = %s
    #             FROM emails_messages em
    #             WHERE em.message_key = %s 
    #                 AND em.customer_number = %s 
    #         """

    #     for identificador, messages in id_to_message_keys.items():
    #         if len(messages) < 2:
    #             continue
    #         # print(f"[INFO] - Identificador: {identificador} has {len(messages)} associated message(s).")

    #         # If any message for this identificador is already marked 'Descargado', update the rest
    #         already_descargado = any(
    #             (m.get('status') or '').lower() == 'descargado' for m in messages
    #         )

    #         if already_descargado:
    #             for m in messages:
    #                 try:
    #                     if (m.get('status') or '').lower() != 'descargado':
    #                         message_key = m.get('message_key')
    #                         cliente = m.get('client_id')
    #                         print(f"[INFO] - Updating message_key {message_key} for cliente {cliente} to '{status_name}' (status_id=2)")
    #                         cursor.execute(update_query, (2, message_key, cliente))
    #                         updated_message_keys.add(message_key)
    #                 except Exception as e:
    #                     print(f"[ERROR] - Failed to update message {m.get('message_key')}: {e}")

    #             try:
    #                 conn.commit()
    #             except Exception as e:
    #                 print(f"[ERROR] - Commit failed: {e}")
    #     # Close the connection used for updates
    #     try:
    #         conn.close()
    #     except Exception:
    #         pass
    # except Exception as e:
    #     print(f"[ERROR] - An error occurred while processing notifications: {e}")
    #     raise


    # print(f"[INFO] - Updated {updated_message_keys} messages to '{status_name}' status.")
    # try:
    #     json_path = os.path.join("files", "playground", f"updated_message_keys_{default_date}_{execution_id}.json")
    #     os.makedirs(os.path.dirname(json_path), exist_ok=True)
    #     with open(json_path, "w", encoding="utf-8") as f:
    #         json.dump(list(updated_message_keys), f, ensure_ascii=False, indent=2)
    #     print(f"[INFO] - Saved updated_message_keys to {json_path}")
    # except Exception as e:
    #     print(f"[ERROR] - Could not save updated_message_keys: {e}")

    # try:
    #     json_path = os.path.join("files", "playground", f"id_to_message_keys_{default_date}_{execution_id}.json")
    #     os.makedirs(os.path.dirname(json_path), exist_ok=True)

    #     try:
    #         with open(json_path, "w", encoding="utf-8") as f:
    #             json.dump(id_to_message_keys, f, ensure_ascii=False, indent=2, default=str)
    #         print(f"[INFO] - Saved id_to_message_keys to {json_path}")
    #     except Exception as e:
    #         print(f"[ERROR] - Could not save id_to_message_keys: {e}")

    # except Exception as e:
    #     print(f"[ERROR] - An error occurred while setting up JSON saving: {e}")
    #     raise

    listener.terminate()



if __name__ == "__main__":
    main()