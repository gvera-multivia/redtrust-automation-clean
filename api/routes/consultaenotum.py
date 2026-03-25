# -*- coding: utf-8 -*-
from http.client import HTTPException
from fastapi import APIRouter, Request

from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings
from api.enqueuer import enqueue_task

router = APIRouter(
    prefix="/consulta-enotum", 
    tags=["Consulta E-Notum"],
    responses={
        400: {"description": "Parámetros de consulta inválidos"},
        404: {"description": "No se encontraron notificaciones"},
        500: {"description": "Error conectando con E-Notum"}
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
    summary="Endpoints de Consulta E-Notum",
    description="""
    Lista todos los endpoints disponibles para la automatización de consultas al sistema E-Notum.
    
    ### Sistema E-Notum:
    
    E-Notum es la plataforma oficial para la gestión electrónica de notificaciones judiciales.
    Este módulo automatiza la consulta y descarga de notificaciones pendientes.
    
    ### Funcionalidades disponibles:
    
    * **Consulta automática**: Verificación periódica de nuevas notificaciones
    * **Filtros por cliente**: Consultas específicas por código de cliente
    * **Filtros por fecha**: Revisión de notificaciones en fechas específicas
    * **Descarga automatizada**: Obtención de documentos asociados
    * **Procesamiento inteligente**: Clasificación y organización de notificaciones
    
    ### Parámetros de consulta:
    
    * `cliente`: Código del cliente específico a consultar
    * `fecha_a_revisar`: Fecha específica para revisar (YYYY-MM-DD)
    * `default=true`: Usar configuración por defecto del sistema
    
    ### Proceso automatizado:
    
    1. Conexión segura al sistema E-Notum
    2. Autenticación con certificados digitales
    3. Búsqueda de notificaciones pendientes
    4. Descarga y clasificación de documentos
    5. Actualización del estado en base de datos
    6. Generación de alertas y reportes
    """,
    responses={
        200: {
            "description": "Lista de endpoints obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "available_endpoints": [
                            {"method": "POST", "path": "/consulta-enotum/trigger"},
                            {"method": "POST", "path": "/consulta-enotum/trigger/?cliente=CLI001"}
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
            {"method": "POST", "path": "/consulta-enotum/trigger"},
            {"method": "POST", "path": "/consulta-enotum/trigger/?cliente=CLIENTE1"},
            {"method": "POST", "path": "/consulta-enotum/trigger/?fecha_a_revisar=2023-10-01?default=true"},
            {"method": "POST", "path": "/consulta-enotum/trigger/?cliente=CLIENTE1&fecha_a_revisar=2023-10-01"},
        ]
    }

# @router.post("/trigger")
# def trigger_alta(cliente: str = Body(None), sedes: list = Body(None)):
#     result = run_robot_altas.apply_async(kwargs={"cliente": cliente, "sedes": sedes})
#     return {"msg": "Tarea de RobotAltas encolada", "task_id": result.id}

@router.post(
    "/trigger",
    summary="Ejecutar Consulta Automatizada E-Notum",
    description="""
    Inicia el proceso de consulta automatizada al sistema E-Notum para verificar y descargar nuevas notificaciones judiciales.
    
    ### Proceso de consulta E-Notum:
    
    1. **Autenticación**: Conexión segura con certificados digitales
    2. **Consulta de bandeja**: Revisión de notificaciones pendientes
    3. **Filtrado inteligente**: Aplicación de criterios de búsqueda
    4. **Descarga de documentos**: Obtención de archivos PDF y anexos
    5. **Procesamiento**: Extracción de metadatos y clasificación
    6. **Almacenamiento**: Organización en estructura de carpetas
    7. **Notificación**: Alertas sobre nuevas notificaciones importantes
    
    ### Parámetros de entrada:
    
    * **cliente** (opcional): Código del cliente específico a consultar
    * **fecha_a_revisar** (opcional): Fecha específica a revisar (YYYY-MM-DD)
    
    ### Comportamiento por defecto:
    
    Si no se especifican parámetros, el sistema:
    - Consultará todos los clientes activos
    - Revisará notificaciones de los últimos 7 días
    - Aplicará filtros de configuración por defecto
    
    ### Tipos de notificaciones procesadas:
    
    * **Citaciones**: Citaciones judiciales y administrativas
    * **Resoluciones**: Sentencias, autos y resoluciones
    * **Emplazamientos**: Requerimientos procesales
    * **Notificaciones**: Comunicaciones oficiales
    * **Traslados**: Traslados de escritos y documentos
    
    ### Ejemplos de uso:
    
    **Consulta por cliente específico:**
    ```json
    {
        "cliente": "CLI001",
        "fecha_a_revisar": "2024-01-15"
    }
    ```
    
    **Consulta general (sin parámetros):**
    ```json
    {}
    ```
    
    **Consulta por fecha:**
    ```json
    {
        "fecha_a_revisar": "2024-01-10"
    }
    ```
    
    ### Resultados esperados:
    
    * Nuevas notificaciones descargadas y clasificadas
    * Actualización del estado en base de datos
    * Generación de alertas para notificaciones urgentes
    * Reporte detallado de la sesión de consulta
    
    ⚠️ **Importante**: 
    - Requiere certificados digitales válidos
    - El proceso puede tardar 5-20 minutos según volumen
    - Se recomienda ejecutar en horarios de menor carga del sistema E-Notum
    """,
    responses={
        202: {
            "description": "Consulta E-Notum iniciada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "msg": "Tarea de consulta-enotum encolada (dispatcher)",
                        "task_id": "enotum_12345",
                        "status": "pending",
                        "estimated_duration": "5-20 minutos",
                        "cliente": "CLI001",
                        "fecha_a_revisar": "2024-01-15",
                        "session_info": {
                            "certificados_verificados": True,
                            "conexion_enotum": "establecida",
                            "filtros_aplicados": ["cliente", "fecha"]
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
                        "detail": "Invalid date format. Use YYYY-MM-DD"
                    }
                }
            }
        },
        500: {
            "description": "Error conectando con E-Notum",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error al encolar la tarea de consultaenotum: Certificado digital no válido"
                    }
                }
            }
        }
    },
    status_code=202,
    tags=["Ejecución", "Notificaciones"]
)
async def trigger_consultaenotum(request: Request):
    data = await request.json()
    print(data)
    if not data:
        try:
            logger.info("API", "ConsultaEnotumTrigger", "Pending", f"Received request to trigger consulta-enotum with no parameters. Using defaults.")
            enqueue_task('run_robot_consulta_enotum', kwargs={
                'cliente': None, 
                'fecha_a_revisar': None
            })

            return {
                "msg": "Tarea de consulta-enotum encolada (dispatcher)",
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Error al encolar la tarea de consultaenotum: {str(e)}"
            )
    else:
        try:
            logger.info("API", "ConsultaEnotumTrigger", "Pending", f"Received request to trigger consulta-enotum with cliente: {data.get('cliente', None)}, fecha_a_revisar: {data.get('fecha_a_revisar', None)}")
            enqueue_task('run_robot_consulta_enotum', kwargs={
                'cliente': data.get('cliente', None),
                'fecha_a_revisar': data.get('fecha_a_revisar', None)
            })

            return {
                "msg": "Tarea de consulta-enotum encolada (dispatcher)",
                "cliente": data.get('cliente', None),
                "fecha_a_revisar": data.get('fecha_a_revisar', None)
            }
        except Exception as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Error al encolar la tarea de consultaenotum: {str(e)}"
            )
