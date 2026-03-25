# -*- coding: utf-8 -*-
from http.client import HTTPException
from fastapi import APIRouter, Request

from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings
from api.enqueuer import enqueue_task

router = APIRouter(
    prefix="/altas", 
    tags=["Automatización de Altas"],
    responses={
        400: {"description": "Datos inválidos en la solicitud"},
        404: {"description": "Recurso no encontrado"},
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
    summary="Endpoints Disponibles de Altas",
    description="""
    Lista todos los endpoints disponibles para la automatización de altas de clientes.
    
    ### Funcionalidades disponibles:
    
    * **Trigger general**: Ejecutar proceso de altas con parámetros personalizados
    * **Altas pendientes**: Procesar altas pendientes con filtros opcionales
    * **Filtros por cliente**: Procesar altas de un cliente específico
    * **Filtros por sede**: Procesar altas de una sede específica
    
    ### Parámetros de filtrado:
    
    * `default=true`: Usar configuración por defecto
    * `cliente=CODIGO`: Filtrar por código de cliente
    * `sede=CODIGO`: Filtrar por código de sede
    """,
    responses={
        200: {
            "description": "Lista de endpoints obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "available_endpoints": [
                            {"method": "POST", "path": "/altas/trigger"},
                            {"method": "POST", "path": "/altas/trigger/pendientes"}
                        ]
                    }
                }
            }
        }
    },
    status_code=200,
    tags=["Información"]
)
def get_endpoints():
    return {
        "available_endpoints": [
            {"method": "POST", "path": "/altas/trigger"},
            {"method": "POST", "path": "/altas/trigger/pendientes"},
            {"method": "POST", "path": "/altas/trigger/pendientes?default=true"},
            {"method": "POST", "path": "/altas/trigger/pendientes?cliente=CLIENTE1"},
            {"method": "POST", "path": "/altas/trigger/pendientes?sede=SEDE1"},
            {"method": "POST", "path": "/altas/trigger/pendientes?cliente=CLIENTE1&sede=SEDE1"}
        ]
    }

# @router.post("/trigger")
# def trigger_alta(cliente: str = Body(None), sedes: list = Body(None)):
#     result = run_robot_altas.apply_async(kwargs={"cliente": cliente, "sedes": sedes})
#     return {"msg": "Tarea de RobotAltas encolada", "task_id": result.id}

@router.post(
    "/trigger",
    summary="Ejecutar Automatización de Altas",
    description="""
    Inicia el proceso de automatización de altas de clientes con parámetros personalizables.
    
    ### Proceso de altas:
    
    1. **Validación de datos**: Verifica la información del cliente y sedes
    2. **Preparación de documentos**: Genera formularios y documentación necesaria
    3. **Envío automático**: Presenta altas en los sistemas correspondientes
    4. **Seguimiento**: Monitorea el estado del proceso
    
    ### Parámetros de entrada:
    
    * **cliente** (opcional): Código del cliente específico para procesar
    * **sedes** (opcional): Lista de códigos de sedes a procesar
    
    Si no se especifican parámetros, procesará todos los clientes pendientes.
    
    ### Ejemplo de uso:
    
    ```json
    {
        "cliente": "CLI001",
        "sedes": ["SEDE01", "SEDE02"]
    }
    ```
    
    ⚠️ **Importante**: Este proceso puede tardar varios minutos dependiendo del número de altas.
    """,
    responses={
        202: {
            "description": "Tarea de altas encolada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Task enqueued successfully",
                        "task_id": "alta_12345",
                        "status": "pending",
                        "estimated_duration": "15-30 minutos",
                        "parameters": {
                            "cliente": "CLI001",
                            "sedes": ["SEDE01", "SEDE02"]
                        }
                    }
                }
            }
        },
        400: {
            "description": "Datos inválidos en la solicitud",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "No data provided in the request body."
                    }
                }
            }
        },
        500: {
            "description": "Error interno del sistema"
        }
    },
    status_code=202,
    tags=["Ejecución", "Tareas"]
)
async def trigger_altas(request: Request):
    data = await request.json()

    if not data:
        raise HTTPException(status_code=400, detail="No data provided in the request body.")
    
    cliente = data.get("cliente", None)
    sedes = data.get("sedes")


    try:
        logger.info("API", "AltasTrigger", "Pending", f"Received request to trigger altas with cliente: {cliente}, sedes: {sedes}")
        enqueue_task('run_robot_altas', kwargs={
            'cliente': cliente, 
            'sedes': sedes
        })

        return {
            "msg": "Tarea de altas encolada (dispatcher)",
            "cliente": cliente, 
            "sedes": sedes
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error al encolar la tarea de altas: {str(e)}"
        )
