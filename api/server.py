import threading
import time
import uvicorn
from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from api.config.api_config import settings
from api.dispatcher import Dispatcher
from api.enqueuer import enqueue_task
from app.helper.loggerV2 import LoggerV2
from api.scheduler import Scheduler
from api.routes import altas, descargas, matriculas, reports, status, history, consultaenotum, database, logs
from api.routes.websocket_backend import router as ws_router

# Logger instance
logger = LoggerV2(
    module="API",
    class_name=__name__, 
    log_dir=settings.LOG_DIR, 
    filename=settings.LOG_FILE,
)

#  Global dispatcher instance
dispatcher = Dispatcher()
dispatcher_stop_event = threading.Event()
dispatcher_thread = None

scheduler = Scheduler()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("API", "Startup", "Success", "API Master Node starting...")
    
    global dispatcher_thread
    dispatcher_stop_event.clear()
    
    try:
        dispatcher_thread = threading.Thread(
            target=dispatcher.dispatch_tasks, 
            args=(dispatcher_stop_event,), 
            daemon=True
        )
        dispatcher_thread.start()
        
        # Verify thread started
        if dispatcher_thread.is_alive():
            logger.info("API", "Startup", "Success", "Dispatcher thread started and is alive")
        else:
            logger.error("API", "Startup", "Error", "Dispatcher thread failed to start")
            
    except Exception as e:
        logger.error("API", "Startup", "Error", f"Failed to start dispatcher thread: {e}")
    
    try:
        scheduler.start()
        logger.info("API", "Startup", "Success", "Scheduler started")
    except Exception as e:
        logger.error("API", "Startup", "Error", f"Failed to start scheduler: {e}")
    
    logger.info("API", "Startup", "Success", "API Master Node started successfully")
    
    yield
    
    # Shutdown
    logger.info("API", "Shutdown", "Info", "API Master Node shutting down...")
    
    try:
        dispatcher_stop_event.set()
        if dispatcher_thread and dispatcher_thread.is_alive():
            dispatcher_thread.join(timeout=10)
            logger.info("API", "Shutdown", "Success", "Dispatcher stopped")
        else:
            logger.warning("API", "Shutdown", "Warning", "Dispatcher thread was not alive during shutdown")
    except Exception as e:
        logger.error("API", "Shutdown", "Error", f"Error stopping dispatcher: {e}")
    
    try:
        scheduler.stop()
        logger.info("API", "Shutdown", "Success", "Scheduler stopped")
    except Exception as e:
        logger.error("API", "Shutdown", "Error", f"Error stopping scheduler: {e}")
    
    logger.info("API", "Shutdown", "Success", "API Master Node shutdown complete")

app = FastAPI(
    title="RedTrust Automation API",
    description="""
    <h2>Sistema de Automatización RedTrust - Master Node API</h2>

    <p>Esta API permite gestionar y coordinar las tareas de automatización del sistema RedTrust.
    El sistema está diseñado con una arquitectura Master-Slave donde:</p>

    <ul>
        <li><strong>Master Node (API)</strong>: Coordina tareas, gestiona colas y proporciona endpoints</li>
        <li><strong>Worker Nodes</strong>: Ejecutan tareas de automatización con interfaz gráfica</li>
    </ul>

    <h3>🚀 Funcionalidades principales:</h3>

    <ul>
        <li><strong>📋 Gestión de Tareas</strong>: Encolar y monitorear tareas de automatización</li>
        <li><strong>👥 Monitoreo de Workers</strong>: Estado en tiempo real de workers activos</li>
        <li><strong>📊 Sistema de Colas</strong>: Distribución inteligente basada en heartbeats</li>
        <li><strong>🔄 Scheduler</strong>: Tareas programadas automáticas</li>
        <li><strong>📈 Reportes</strong>: Generación y seguimiento de informes</li>
        <li><strong>💾 Base de Datos</strong>: Consultas y gestión de datos de clientes</li>
        <li><strong>🔌 WebSockets</strong>: Comunicación en tiempo real</li>
    </ul>

    <h3>📦 Módulos disponibles:</h3>

    <ul>
        <li><strong>Altas</strong>: Gestión de altas de clientes</li>
        <li><strong>Descargas</strong>: Automatización de descargas de documentos</li>
        <li><strong>Matrículas</strong>: Gestión de matrículas y puntos</li>
        <li><strong>Consultas E-Notum</strong>: Consultas automatizadas al sistema E-Notum</li>
        <li><strong>Reportes</strong>: Generación automática de informes</li>
        <li><strong>Certificados</strong>: Gestión de certificados digitales</li>
    </ul>

    <h3>🔍 Estado del Sistema:</h3>

    <p>
        Utiliza <code>/health</code> para verificar el estado del sistema y
        <code>/api/system/status</code> para obtener información detallada del estado
        de workers y colas.
    </p>

    <hr>

    <p><strong>📡 Endpoints principales:</strong></p>
    <ul>
        <li><code>GET /health</code> - Estado de salud del sistema</li>
        <li><code>POST /api/enqueue_task</code> - Encolar nueva tarea</li>
        <li><code>GET /api/system/status</code> - Estado completo del sistema</li>
        <li><code>WebSocket /api/ws</code> - Monitoreo en tiempo real</li>
    </ul>
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

router = APIRouter(
    prefix="/api", 
    tags=["Core API"],
    responses={
        404: {"description": "Endpoint not found"},
        500: {"description": "Internal server error"}
    }
)

# Include existing routes
router.include_router(ws_router)
router.include_router(altas.router)
router.include_router(descargas.router)
router.include_router(matriculas.router)
router.include_router(reports.router)
router.include_router(status.router)
router.include_router(history.router)
router.include_router(consultaenotum.router)
router.include_router(database.router)
router.include_router(logs.router)

@router.post(
    "/enqueue_task",
    summary="Encolar Nueva Tarea",
    description="""
    Encola una nueva tarea para ser ejecutada por un worker disponible.
    
    ### Tipos de tareas disponibles:
    
    * `robot_altas` - Automatización de altas de clientes
    * `robot_descargas` - Automatización de descargas de documentos  
    * `robot_matriculas` - Gestión de matrículas y puntos
    * `robot_consulta_enotum` - Consultas al sistema E-Notum
    * `robot_sede_judicial` - Procesos de sede judicial
    
    ### Parámetros:
    
    * **task_name**: Nombre de la tarea a ejecutar (requerido)
    * **args**: Lista de argumentos posicionales (opcional)
    * **kwargs**: Diccionario de argumentos con nombre (opcional)
    
    ### Ejemplo de uso:
    
    ```json
    {
        "task_name": "robot_descargas",
        "args": [],
        "kwargs": {
            "cliente_id": "12345",
            "fecha_inicio": "2024-01-01",
            "fecha_fin": "2024-01-31"
        }
    }
    ```
    """,
    responses={
        200: {
            "description": "Tarea encolada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "message": "Task enqueued successfully",
                        "task_id": "abc123",
                        "worker_id": "worker_001"
                    }
                }
            }
        },
        400: {
            "description": "Error en los parámetros de la tarea",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "task_name is required"
                    }
                }
            }
        },
        500: {
            "description": "Error interno del servidor"
        }
    },
    tags=["Gestión de Tareas"]
)
async def enqueue_task_endpoint(request: Request):
    """ endpoint for enqueuing tasks"""
    try:
        data = await request.json()
        task_name = data.get("task_name")
        args = data.get("args", [])
        kwargs = data.get("kwargs", {})
        
        if not task_name:
            raise HTTPException(status_code=400, detail="task_name is required")
        
        result = enqueue_task(task_name, args, kwargs)
        
        if result['status'] == 'success':
            return JSONResponse(content=result)
        else:
            raise HTTPException(status_code=400, detail=result['message'])
            
    except Exception as e:
        logger.error("API", "enqueue_task_endpoint", "Error", f"Error enqueuing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
app.include_router(router)

@app.get(
    "/",
    summary="Información General de la API",
    description="Endpoint principal que proporciona información sobre la API y sus funcionalidades.",
    response_description="Información general del sistema",
    tags=["Sistema"]
)
def root():
    return {
        "message": "RedTrust Automation Master Node API",
        "version": "2.0.0",
        "status": "operational",
        "features": [
            "Monitoreo de workers en tiempo real",
            "Distribución inteligente de tareas basada en heartbeats",
            "Terminación remota de tareas",
            "Vista general completa del sistema",
            "Seguimiento de progreso en tiempo real",
            "Scheduler de tareas automáticas",
            "Gestión de base de datos integrada",
            "WebSockets para comunicación en tiempo real"
        ],
        "modules": [
            "altas", "descargas", "matriculas", "consulta_enotum", 
            "reportes", "certificados", "sede_judicial"
        ],
        "documentation": "/docs",
        "health_check": "/health"
    }

@app.get(
    "/health",
    summary="Estado de Salud del Sistema",
    description="""
    Endpoint de verificación de salud del sistema utilizado por Docker HEALTHCHECK y monitoreo.
    
    ### Estados posibles:
    
    * **ok** (200): Todos los servicios funcionando correctamente
    * **degraded** (200): Algunos servicios con problemas pero sistema operativo
    * **down** (503): Sistema no operativo
    
    ### Componentes monitoreados:
    
    * **Dispatcher**: Hilo encargado de distribuir tareas a workers
    * **Scheduler**: Servicio de tareas programadas automáticas
    """,
    responses={
        200: {
            "description": "Sistema operativo (ok o degraded)",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok",
                        "dispatcher_running": True,
                        "scheduler_running": True,
                        "version": "2.0"
                    }
                }
            }
        },
        503: {
            "description": "Sistema no operativo",
            "content": {
                "application/json": {
                    "example": {
                        "status": "down",
                        "dispatcher_running": False,
                        "scheduler_running": False,
                        "version": "2.0"
                    }
                }
            }
        }
    },
    tags=["Sistema", "Monitoreo"]
)
def health():
    """Health check endpoint used by Docker HEALTHCHECK."""
    dispatcher_alive = False
    scheduler_running = False
    # Throttle expensive health check logging: cache result for 5 minutes
    global _last_health_check, _cached_health_result, _cached_status_code
    try:
        now = time.time()
    except Exception:
        now = 0

    CACHE_TTL = 300  # seconds (5 minutes)
    if '_last_health_check' in globals() and (now - _last_health_check) < CACHE_TTL and _cached_health_result is not None:
        # Return cached result without extra logging to avoid log spam
        return JSONResponse(content=_cached_health_result, status_code=_cached_status_code)
    
    # Check dispatcher status
    try:
        if dispatcher_thread is not None:
            dispatcher_alive = dispatcher_thread.is_alive()
        else:
            logger.warning("API", "Health", "Warning", "Dispatcher thread is None")
    except Exception as e:
        logger.error("API", "Health", "Error", f"Error checking dispatcher status: {e}")
        dispatcher_alive = False

    # Check scheduler status  
    try:
        # Prefer explicit thread liveliness check if available
        sched_thread = getattr(scheduler, 'thread', None)
        if sched_thread is not None and hasattr(sched_thread, 'is_alive'):
            scheduler_running = bool(sched_thread.is_alive())
        elif hasattr(scheduler, 'is_running'):
            if callable(scheduler.is_running):
                scheduler_running = scheduler.is_running()
            else:
                scheduler_running = bool(scheduler.is_running)
        elif hasattr(scheduler, 'running'):
            scheduler_running = bool(scheduler.running)
        elif hasattr(scheduler, '_scheduler') and hasattr(scheduler._scheduler, 'running'):
            # Some scheduler implementations store state in _scheduler
            scheduler_running = bool(scheduler._scheduler.running)
        else:
            # Unable to determine scheduler state reliably — mark as not running to avoid false positives
            scheduler_running = False
            logger.warning("API", "Health", "Warning", "Scheduler status unclear; marking as not running")
    except Exception as e:
        logger.error("API", "Health", "Error", f"Error checking scheduler status: {e}")
        scheduler_running = False

    # Determine overall status
    if dispatcher_alive and scheduler_running:
        status_text = "ok"
        status_code = 200
    elif dispatcher_alive or scheduler_running:
        status_text = "degraded"
        status_code = 200  # Changed from 503 to 200 for degraded state
    else:
        status_text = "down"
        status_code = 503

    result = {
        "status": status_text,
        "dispatcher_running": dispatcher_alive,
        "scheduler_running": scheduler_running,
        "version": "2.0",
    }
    
    # Log health check results for debugging (throttled)
    logger.info("API", "Health", "Info", f"Health check: {result}")
    _last_health_check = time.time()
    _cached_health_result = result
    _cached_status_code = status_code
    return JSONResponse(content=result, status_code=status_code)


if __name__ == "__main__":
    uvicorn.run("api.server:app", host='0.0.0.0', port=settings.PORT, reload=True)
