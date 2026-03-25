from fastapi import APIRouter, Request
from datetime import date, timedelta

from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings
from api.enqueuer import enqueue_task
from fastapi import HTTPException

router = APIRouter(
    prefix="/descargas", 
    tags=["Automatización de Descargas"],
    responses={
        400: {"description": "Parámetros inválidos"},
        404: {"description": "Documentos no encontrados"},
        500: {"description": "Error interno del servidor"}
    }
)
logger = LoggerV2(
    module="API",
    class_name=__name__, 
    log_dir=settings.LOG_DIR, 
    filename=settings.LOG_FILE
)

@router.get(
    "",
    summary="Endpoints de Automatización de Descargas",
    description="""
    Lista todos los endpoints disponibles para la automatización de descargas de documentos.
    
    ### Funcionalidades de descarga:
    
    * **Descargas automáticas**: Descarga documentos según criterios configurados
    * **Filtros múltiples**: Por cliente, sede, fecha y message_id
    * **Descarga selectiva**: Documentos específicos o por rangos de fecha
    * **Monitoreo en tiempo real**: Seguimiento del progreso de descarga
    
    ### Parámetros de filtrado disponibles:
    
    * `cliente`: Código del cliente
    * `sede`: Código de la sede judicial
    * `fecha`: Fecha específica (YYYY-MM-DD)
    * `message_id`: ID del mensaje específico
    * `default=true`: Configuración por defecto
    
    ### Combinaciones de filtros:
    
    Los filtros se pueden combinar para mayor precisión en las descargas.
    """,
    responses={
        200: {
            "description": "Lista de endpoints obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "available_endpoints": [
                            {"method": "POST", "path": "/descargas/trigger"},
                            {"method": "POST", "path": "/descargas/trigger?cliente=CLI001"}
                        ]
                    }
                }
            }
        }
    },
    status_code=200,
    tags=["Información"]
)
def get_enpoints():
    return {
        "available_endpoints": [
            {"method": "GET", "path": "/descargas"},
            {"method": "POST", "path": "/descargas/trigger"},
            {"method": "POST", "path": "/descargas/trigger?default=true"},
            {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1"},
            {"method": "POST", "path": "/descargas/trigger?sede=SEDE1"},
            {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1"},
            {"method": "POST", "path": "/descargas/trigger?fecha=YYYY-MM-DD"},
            {"method": "POST", "path": "/descargas/trigger?message_id=ID_MENSAJE"},
            {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1&fecha=YYYY-MM-DD"},
            {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1&message_id=ID_MENSAJE"},
            {"method": "POST", "path": "/descargas/trigger?fecha=YYYY-MM-DD&message_id=ID_MENSAJE"},
            {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&fecha=YYYY-MM-DD&message_id=ID_MENSAJE"}
        ]
    }



# @router.post("/trigger")
# def trigger_descarga(date: str = Body(None), cliente: str = Body(None), sede: str = Body(None), message_id: str = Body(None)):
#     result = run_robot_descargas.apply_async(kwargs={"date": date, "cliente": cliente, "sede": sede, "message_id": message_id})
#     return {"msg": "Tarea de RobotDescargas encolada", "task_id": result.id}


@router.post(
    "/trigger",
    summary="Ejecutar Automatización de Descargas",
    description="""
    Inicia el proceso de automatización de descargas de documentos judiciales.
    
    ### Proceso de descarga:
    
    1. **Conexión a sistemas**: Acceso a plataformas judiciales
    2. **Búsqueda de documentos**: Según los criterios especificados
    3. **Descarga automatizada**: Descarga y organización de archivos
    4. **Validación**: Verificación de integridad de documentos
    5. **Notificación**: Reporte de resultados
    
    ### Parámetros de entrada:
    
    * **cliente** (opcional): Código del cliente específico
    * **fecha/date** (opcional): Fecha específica en formato YYYY-MM-DD
    * **sede** (opcional): Código de sede judicial
    * **message_id** (opcional): ID específico del mensaje/documento
    * **download_path** (opcional): Ruta personalizada de descarga
    
    ### Comportamiento por defecto:
    
    Si no se especifican parámetros, descargará documentos del día anterior.
    
    ### Ejemplos de uso:
    
    **Descarga por fecha:**
    ```json
    {
        "fecha": "2024-01-15",
        "cliente": "CLI001"
    }
    ```
    
    **Descarga específica:**
    ```json
    {
        "message_id": "MSG12345",
        "download_path": "/custom/path"
    }
    ```
    
    ⚠️ **Nota**: El tiempo de ejecución varía según el volumen de documentos.
    """,
    responses={
        202: {
            "description": "Tarea de descarga encolada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Task enqueued successfully",
                        "task_id": "descarga_12345",
                        "status": "pending",
                        "estimated_duration": "10-45 minutos",
                        "parameters": {
                            "cliente": "CLI001",
                            "fecha": "2024-01-15",
                            "sede": "SEDE01"
                        },
                        "expected_documents": "Estimado: 15-25 documentos"
                    }
                }
            }
        },
        400: {
            "description": "Parámetros inválidos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid date format. Use YYYY-MM-DD"
                    }
                }
            }
        },
        500: {
            "description": "Error interno del sistema"
        }
    },
    status_code=202,
    tags=["Ejecución", "Documentos"]
)
async def trigger_descargas(request: Request):
    data = await request.json()
    cliente = data.get("cliente")
    fecha = data.get("fecha") or data.get("date")  # Acepta ambos nombres

    # message_id/message_key may be provided as a single string, comma-separated, or a list.
    def _normalize_to_list(val):
        if val is None:
            return None
        if isinstance(val, list):
            return [str(x) for x in val if x is not None and str(x).strip()]
        if isinstance(val, str):
            # allow comma separated strings
            if "," in val:
                items = [s.strip() for s in val.split(",") if s.strip()]
                return items if items else None
            return [val] if val.strip() else None
        # fallback: try to coerce to string list
        try:
            return [str(val)]
        except Exception:
            return None

    message_ids = _normalize_to_list(data.get("message_id") or data.get("message_ids"))
    message_keys = _normalize_to_list(data.get("message_key") or data.get("message_keys"))
    sedes = data.get("sede")

    if not fecha:
        raise HTTPException(status_code=400, detail="Fecha es un parámetro obligatorio. Formato esperado: YYYY-MM-DD")

    # If none of the actionable filters are provided (cliente, sedes, message ids/keys), return help
    if not fecha and not cliente and not sedes and not message_ids and not message_keys:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No se han proporcionado parámetros. Consulta las opciones de uso.",
                "options": [
                    {"method": "GET", "path": "/descargas"},
                    {"method": "POST", "path": "/descargas/trigger"},
                    {"method": "POST", "path": "/descargas/trigger?default=true"},
                    {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1"},
                    {"method": "POST", "path": "/descargas/trigger?sede=SEDE1"},
                    {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1"},
                    {"method": "POST", "path": "/descargas/trigger?fecha=YYYY-MM-DD"},
                    {"method": "POST", "path": "/descargas/trigger?message_id=ID_MENSAJE"},
                    {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1&fecha=YYYY-MM-DD"},
                    {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&sede=SEDE1&message_id=ID_MENSAJE"},
                    {"method": "POST", "path": "/descargas/trigger?fecha=YYYY-MM-DD&message_id=ID_MENSAJE"},
                    {"method": "POST", "path": "/descargas/trigger?cliente=CLIENTE1&fecha=YYYY-MM-DD&message_id=ID_MENSAJE"}
                ]
            }
        )
    
    try:
        logger.info("API", "DescargasTrigger", "Pending", f"Encolando tarea run_robot_descargas con cliente={cliente}, sedes={sedes}, fecha={fecha}, message_id={message_ids}, message_key={message_keys}")
        enqueue_task('run_robot_descargas', kwargs={
            'date': fecha,
            'cliente': cliente,
            'sedes': sedes,
            'message_ids': message_ids,
            'message_keys': message_keys
        })
        return {
            "message": "Tarea de descargas encolada (dispatcher)",
            "cliente": cliente,
            "sedes": sedes,
            "fecha": fecha,
            "message_ids": message_ids,
            "message_keys": message_keys
        }
    except Exception as e:
        return {"error": f"Error al encolar descargas para {cliente} en la sede {sedes}: {str(e)}"}
