from fastapi import APIRouter, Request
from datetime import datetime

from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings
from api.enqueuer import enqueue_task

router = APIRouter(
    prefix="/matriculas-y-puntos", 
    tags=["Matrículas y Puntos"],
    responses={
        400: {"description": "Parámetros inválidos"},
        404: {"description": "Datos no encontrados"},
        500: {"description": "Error en el sistema de matrículas"}
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
    summary="Endpoints de Matrículas y Puntos",
    description="""
    Lista todos los endpoints disponibles para la gestión automatizada de matrículas y puntos.
    
    ### Funcionalidades del módulo:
    
    * **Consulta de matrículas**: Verificación de estado de matrículas activas
    * **Gestión de puntos**: Control y seguimiento de puntos del carnét
    * **Actualizaciones automáticas**: Sincronización con sistemas oficiales
    * **Alertas y notificaciones**: Avisos sobre vencimientos y cambios
    
    ### Parámetros de filtrado:
    
    * `cliente`: Código del cliente específico
    * `fecha`: Fecha de consulta (YYYY-MM-DD)
    * `default=true`: Configuración por defecto del sistema
    
    ### Procesos automatizados:
    
    * Verificación de vigencia de matrículas
    * Control de puntos del permiso de conducir
    * Actualización de datos desde fuentes oficiales
    * Generación de reportes de estado
    """,
    responses={
        200: {
            "description": "Lista de endpoints obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "available_endpoints": [
                            {"method": "POST", "path": "/matriculas-y-puntos/trigger"},
                            {"method": "POST", "path": "/matriculas-y-puntos/trigger?cliente=CLI001"}
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
            {"method": "GET", "path": "/matriculas"},
            {"method": "POST", "path": "/matriculas/trigger"},
            {"method": "POST", "path": "/matriculas/trigger?default=true"},
            {"method": "POST", "path": "/matriculas/trigger?cliente=CLIENTE1"},
            {"method": "POST", "path": "/matriculas/trigger?fecha=YYYY-MM-DD"}
        ]
    }

@router.post(
    "/trigger",
    summary="Ejecutar Automatización de Matrículas y Puntos",
    description="""
    Inicia el proceso de automatización para la gestión de matrículas y puntos de conducir.
    
    ### Proceso automatizado:
    
    1. **Conexión a sistemas oficiales**: Acceso a DGT y organismos competentes
    2. **Verificación de matrículas**: Control de vigencia y estado
    3. **Consulta de puntos**: Estado actual del permiso de conducir
    4. **Detección de cambios**: Identificación de modificaciones
    5. **Actualización de registros**: Sincronización con base de datos local
    6. **Generación de alertas**: Notificaciones sobre vencimientos
    
    ### Parámetros de entrada:
    
    * **cliente** (opcional): Código del cliente específico a procesar
    * **fecha** (opcional): Fecha de referencia para la consulta
    * **tipo_consulta** (opcional): Tipo específico de verificación
    
    ### Tipos de consulta disponibles:
    
    * `matriculas`: Solo verificación de matrículas
    * `puntos`: Solo consulta de puntos de conducir
    * `completa`: Verificación integral (por defecto)
    
    ### Ejemplos de uso:
    
    **Consulta completa por cliente:**
    ```json
    {
        "cliente": "CLI001",
        "tipo_consulta": "completa"
    }
    ```
    
    **Consulta específica de puntos:**
    ```json
    {
        "tipo_consulta": "puntos",
        "fecha": "2024-01-15"
    }
    ```
    
    ### Alertas generadas:
    
    * Matrículas próximas a vencer
    * Pérdida de puntos del permiso
    * Cambios en el estado de vehiculos
    * Nuevas sanciones o infracciones
    
    ⚠️ **Importante**: Este proceso puede tardar varios minutos según el volumen de datos.
    """,
    responses={
        202: {
            "description": "Proceso de matrículas y puntos iniciado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Task enqueued successfully",
                        "task_id": "matriculas_12345",
                        "status": "pending",
                        "estimated_duration": "5-15 minutos",
                        "parameters": {
                            "cliente": "CLI001",
                            "tipo_consulta": "completa",
                            "fecha": "2024-01-15"
                        },
                        "checks_programados": {
                            "matriculas": True,
                            "puntos_carnet": True,
                            "alertas": True
                        }
                    }
                }
            }
        },
        400: {
            "description": "Parámetros inválidos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid client code or date format"
                    }
                }
            }
        },
        500: {
            "description": "Error en el sistema de matrículas"
        }
    },
    status_code=202,
    tags=["Ejecución", "DGT"]
)
async def trigger_matriculas(request: Request):
    data = await request.json()
    date = data.get("date")
    try:
        if date:
            enqueue_task('run_robot_matriculas', kwargs={'date': date})
            return {"message": "Tarea de matrículas encolada (dispatcher)", "date": date}
        else:
            today = datetime.now().strftime('%Y-%m-%d')
            enqueue_task('run_robot_matriculas', kwargs={'date': today})
            return {"message": "Tarea de matrículas encolada (dispatcher)", "date": today}
    except Exception as e:
        return {"error": f"Error al encolar tarea de matrículas: {str(e)}"}

