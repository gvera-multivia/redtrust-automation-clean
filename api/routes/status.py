from datetime import datetime
import os
import json
from celery import Celery
from fastapi.responses import PlainTextResponse
import redis
import time
import paramiko
from dotenv import load_dotenv
from fastapi import APIRouter
from fastapi import HTTPException
from celery.app.control import Inspect
from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings


router = APIRouter(
    prefix="/system", 
    tags=["Sistema y Monitoreo"],
    responses={
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

load_dotenv()
REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = os.getenv("REDIS_PORT")
REDIS_URL = os.getenv("REDIS_URL", f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
WORKER_STATUS_KEY = os.getenv("WORKER_STATUS_KEY", "worker_status")
TASK_PROGRESS_KEY = os.getenv("TASK_PROGRESS_KEY", "task_progress")
TASK_REGISTRY_KEY = os.getenv("TASK_REGISTRY_KEY", "task_registry")



# Este módulo ahora solo simula información de nodos y consulta el estado real de los workers Celery
def get_nodes_status():
    celery_app = Celery(
        'robot_system',
        broker=REDIS_URL,
        backend=REDIS_URL
    )

    insp = Inspect(app=celery_app)
    active_workers = insp.active() or {}
    registered_workers = insp.registered() or {}
    stats = insp.stats() or {}
    all_workers = set(stats.keys()) | set(active_workers.keys()) | set(registered_workers.keys())
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    nodes = []
    for worker in all_workers:
        info = stats.get(worker, {})
        is_active = worker in stats
        is_busy = bool(active_workers.get(worker))
        # Recoge todos los datos publicados por CeleryManager
        try:
            meta = json.loads(r.get(f"{WORKER_STATUS_KEY}:{worker}") or "{}")
        except Exception:
            meta = {}
        nodes.append({
            "name": worker,
            "role": "slave" if not worker.startswith("master") else "master",
            "status": "busy" if is_busy else ("available" if is_active else "offline"),
            "tasks": len(active_workers.get(worker, [])),
            "hostname": meta.get("hostname", worker),
            "ip": meta.get("ip", meta.get("ip")),
            "cpu_percent": meta.get("cpu_percent"),
            "cpu_count": meta.get("cpu_count"),
            "memory_total": meta.get("memory_total"),
            "memory_used": meta.get("memory_used"),
            "memory_percent": meta.get("memory_percent"),
            "disk_total": meta.get("disk_total"),
            "disk_used": meta.get("disk_used"),
            "disk_percent": meta.get("disk_percent"),
            "network_bytes_sent": meta.get("network_bytes_sent"),
            "network_bytes_recv": meta.get("network_bytes_recv"),
            "process_pid": meta.get("process_pid"),
            "process_memory_percent": meta.get("process_memory_percent"),
            "process_cpu_percent": meta.get("process_cpu_percent"),
            "process_num_threads": meta.get("process_num_threads"),
            "uptime_seconds": meta.get("uptime_seconds"),
            "start_time": meta.get("start_time"),
            "timestamp": meta.get("timestamp"),
            "heartbeat": {
                'worker_id': meta.get("worker_id", worker),
                'ip': meta.get("ip"),
                'timestamp': meta.get("timestamp"),
                'uptime': meta.get("uptime_seconds"),
                'status': meta.get("status"),
                'current_task': meta.get("current_task"),
            },            
            "registered_tasks": registered_workers.get(worker, []),
            "conf": info.get("conf", {}),
            "stats": info,
        })
    return nodes

# Get tasks from Redis queues/logs for dashboard
def get_tasks():
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    pending = []
    running = []
    completed = []
    failed = []
    now = int(time.time())
    # Tareas pendientes: dispatcher_tasks_queue
    for idx, item in enumerate(r.lrange('dispatcher_tasks_queue', 0, -1)):
        try:
            t = json.loads(item)
            task_id = t.get('id') or t.get('task_id') or f"T{idx+1}"
            status = "pending"
            # Busca progreso si existe
            progress = r.get(f"task_progress:{task_id}")
            if progress:
                pdata = json.loads(progress)
                status = pdata.get("status", "pending")
            pending.append({
                "id": task_id,
                "type": t.get("task", "unknown"),
                "status": status,
                "created_at": int(t.get("timestamp", now-idx*10)),
                "progress": progress and json.loads(progress) or {},
                "args": t.get("args", []),
                "kwargs": t.get("kwargs", {}),                    
                "worker_ip": t.get("worker_ip") or None
            })
        except Exception:
            continue

    # Tareas en ejecución y completadas: task_registry por worker
    for key in r.scan_iter("task_registry:*"):
        worker_id = key.split(":", 1)[1]
        registry = r.hgetall(key)
        for task_id, task_info in registry.items():
            try:
                info = json.loads(task_info)
                status = info.get("status", "running")
                if status == "running":
                    running.append({
                        "id": task_id,
                        "type": info.get("task_name", "unknown"),
                        "status": status,
                        "worker_id": worker_id,
                        "progress": r.get(f"task_progress:{task_id}") and json.loads(r.get(f"task_progress:{task_id}")) or {},
                        "start_time": info.get("start_time"),
                        "pid": info.get("pid"),
                        "args": info.get("args"),
                        "kwargs": info.get("kwargs"),
                        "error": info.get("error"),
                    })
                elif status == "completed":
                    completed.append({
                        "id": task_id,
                        "type": info.get("task_name", "unknown"),
                        "status": status,
                        "worker_id": worker_id,
                        "progress": r.get(f"task_progress:{task_id}") and json.loads(r.get(f"task_progress:{task_id}")) or {},
                        "start_time": info.get("start_time"),
                        "end_time": info.get("end_time"),
                        "pid": info.get("pid"),
                        "args": info.get("args"),
                        "kwargs": info.get("kwargs"),
                        "error": info.get("error"),
                    })
                elif status == "failed":
                    failed.append({
                        "id": task_id,
                        "type": info.get("task_name", "unknown"),
                        "status": status,
                        "worker_id": worker_id,
                        "progress": r.get(f"task_progress:{task_id}") and json.loads(r.get(f"task_progress:{task_id}")) or {},
                        "start_time": info.get("start_time"),
                        "end_time": info.get("end_time"),
                        "pid": info.get("pid"),
                        "args": info.get("args"),
                        "kwargs": info.get("kwargs"),
                        "error": info.get("error"),
                    })
                elif status == "killed":
                    failed.append({
                        "id": task_id,
                        "type": info.get("task_name", "unknown"),
                        "status": status,
                        "worker_id": worker_id,
                        "progress": r.get(f"task_progress:{task_id}") and json.loads(r.get(f"task_progress:{task_id}")) or {},
                        "start_time": info.get("start_time"),
                        "end_time": info.get("end_time"),
                        "pid": info.get("pid"),
                        "args": info.get("args"),
                        "kwargs": info.get("kwargs"),
                        "error": info.get("error"),
                    })

            except Exception:
                continue
    all_tasks = pending + running + completed + failed
    all_tasks.sort(key=lambda x: x.get("created_at", 0) or 0, reverse=False)
    return all_tasks

"""
    Endpoint para obtener el estado del sistema, incluyendo nodos, tareas y colas.
    Devuelve un resumen de los nodos, tareas y colas de Redis.
    - GET /system/status/nodes: {"nodes": [...]}
    - GET /system/status/tasks: {"tasks": [...]}
    - GET /system/status/queues: {"queues": {...}}
    - GET /system/status/worker-progress: {"progress": {...}}
    - GET /system/status: {
          "nodes": [...],
          "tasks": [...],
          "stats": {
              "nodes": {...},
              "tasks": {...}
          },
          "last_update": ...
      }
    - GET /system/task-status/{task_id}: {"task_id": ..., "status": ..., "info": ...}
    - GET /system/progress/{task_id}: {"progress": ..., "error": ...}
    - GET /system/worker-stats: {"workers": {...}}
    - GET /system/inspect: {
            "celery": {...},
            "redis": {...},
            "dispatcher_queue": {...}
        }

    Endpoint para aplicar acciones sobre tareas:   
    - POST /system/kill-task/{task_id}: {"success": ..., "message": ...}

"""

@router.get(
    "/status",
    summary="Estado Completo del Sistema",
    description="""
    Obtiene el estado completo del sistema incluyendo workers, tareas y estadísticas.
    
    ### Información incluida:
    
    * **Nodes (Workers)**: Lista de workers disponibles con estado, recursos y heartbeats
    * **Tasks**: Tareas pendientes, en ejecución, completadas y fallidas
    * **Queue Info**: Estadísticas de las colas de tareas
    * **System Metrics**: Métricas generales del sistema
    
    ### Estados de Workers:
    * `available` - Worker activo y disponible
    * `busy` - Worker ejecutando tareas
    * `offline` - Worker no disponible
    
    ### Estados de Tareas:
    * `pending` - En cola esperando ejecución
    * `running` - En ejecución
    * `completed` - Completada exitosamente
    * `failed` - Falló durante la ejecución
    """,
    responses={
        200: {
            "description": "Estado del sistema obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "nodes": [
                            {
                                "name": "worker@hostname",
                                "role": "slave",
                                "status": "available",
                                "tasks": 0,
                                "hostname": "hostname",
                                "ip": "192.168.1.100",
                                "cpu_percent": 15.2,
                                "memory_percent": 45.8
                            }
                        ],
                        "tasks": {
                            "pending": [],
                            "running": [],
                            "completed": [],
                            "failed": []
                        },
                        "queue_info": {
                            "total_pending": 0,
                            "total_running": 0,
                            "total_completed": 5,
                            "total_failed": 1
                        }
                    }
                }
            }
        }
    },
    status_code=200,
    tags=["Monitoreo", "Workers", "Tareas"]
)
def get_full_system_status():
    """Endpoint principal que devuelve todo el estado del sistema"""
    nodes = get_nodes_status()
    tasks = get_tasks()
    
    # Estadísticas generales
    total_nodes = len(nodes)
    available_nodes = len([n for n in nodes if n["status"] == "available"])
    busy_nodes = len([n for n in nodes if n["status"] == "busy"])
    offline_nodes = len([n for n in nodes if n["status"] == "offline"])
    
    pending_tasks = len([t for t in tasks if t["status"] == "pending"])
    running_tasks = len([t for t in tasks if t["status"] == "running"])
    completed_tasks = len([t for t in tasks if t["status"] == "completed"])
    failed_tasks = len([t for t in tasks if t["status"] == "failed"])
    
    return {
        "nodes": nodes,
        "tasks": tasks,
        "stats": {
            "nodes": {
                "total": total_nodes,
                "available": available_nodes,
                "busy": busy_nodes,
                "offline": offline_nodes
            },
            "tasks": {
                "pending": pending_tasks,
                "running": running_tasks,
                "completed": completed_tasks,
                "failed": failed_tasks,
                "total": len(tasks)
            }
        },
        "last_update": time.time()
    }

@router.get(
    "/progress/{task_id}",
    summary="Progreso de Tarea Específica",
    description="""
    Obtiene el progreso detallado y estado actual de una tarea específica.
    
    ### Información del progreso:
    
    * **status**: Estado actual (pending, running, completed, failed)
    * **progress**: Porcentaje de completitud (0-100)
    * **current_step**: Paso actual de la tarea
    * **total_steps**: Total de pasos de la tarea
    * **start_time**: Timestamp de inicio
    * **estimated_end**: Tiempo estimado de finalización
    * **details**: Información adicional específica de la tarea
    """,
    responses={
        200: {
            "description": "Progreso obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "task_id": "task_12345",
                        "status": "running",
                        "progress": 65,
                        "current_step": "Procesando documentos",
                        "total_steps": 5,
                        "start_time": 1642694400,
                        "estimated_end": 1642695000
                    }
                }
            }
        },
        404: {
            "description": "Tarea no encontrada",
            "content": {
                "application/json": {
                    "example": {"error": "Task not found or no progress data available"}
                }
            }
        }
    },
    status_code=200,
    tags=["Tareas", "Monitoreo"]
)
def get_task_progress(task_id: str):
    """Obtiene el progreso de una tarea específica"""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    try:
        progress_data = r.get(f"{TASK_PROGRESS_KEY}:{task_id}")
        if progress_data:
            return json.loads(progress_data)
        else:
            return {"error": "Task progress not found", "progress": 0}
    except Exception as e:
        return {"error": str(e), "progress": 0}

@router.post(
    "/kill-task/{task_id}",
    summary="Terminar Tarea",
    description="""
    Termina forzosamente una tarea en ejecución o elimina una tarea pendiente.
    
    ### Comportamiento:
    
    * **Tarea en ejecución**: Envía señal de terminación al worker
    * **Tarea pendiente**: Elimina la tarea de la cola
    * **Tarea completada**: No se puede terminar, devuelve error
    
    ### Casos de uso:
    
    * Cancelar tareas que están tardando demasiado
    * Liberar workers bloqueados
    * Limpiar cola de tareas pendientes
    
    ⚠️ **Advertencia**: Esta acción es irreversible y puede interrumpir procesos importantes.
    """,
    responses={
        200: {
            "description": "Tarea terminada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Task killed successfully",
                        "task_id": "task_12345",
                        "previous_status": "running"
                    }
                }
            }
        },
        400: {
            "description": "No se puede terminar la tarea",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Cannot kill completed task"
                    }
                }
            }
        },
        404: {
            "description": "Tarea no encontrada",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "message": "Task not found"
                    }
                }
            }
        }
    },
    status_code=200,
    tags=["Tareas", "Gestión"]
)
def kill_task(task_id: str):
    from api.redis import RedisManager

    try:
        redis_manager = RedisManager()
        r = redis_manager.redis_client
        """Mata una tarea en ejecución, vacía la cola del worker y la marca como 'killed' en el progreso."""
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

        # Buscar el worker que tiene la tarea activa
        task_data = r.get(f"{TASK_PROGRESS_KEY}:{task_id}")
        if not task_data:
            raise HTTPException(status_code=404, detail="Tarea no encontrada o no está en progreso")

        try:
            task = json.loads(task_data)
        except Exception:
            raise HTTPException(status_code=500, detail="Error al parsear los datos de la tarea")

        worker_ip = task.get("worker_ip")
        pid = task.get("pid")
        worker_id = task.get("worker_id")
        logger.debug("API", "StatutsEndpoint", "Pending", f"Worker ID: {worker_id}, Worker IP: {worker_ip}, PID: {pid}")

        if not worker_ip:
            raise HTTPException(status_code=404, detail="No se encontró el worker ejecutando la tarea")

        # Obtener credenciales del worker
        worker_status_key = f"{WORKER_STATUS_KEY}:{worker_id}"
        worker_data = r.get(worker_status_key)
        try:
            worker = json.loads(worker_data)
        except Exception:
            raise HTTPException(status_code=500, detail="Error al parsear los datos de la tarea")

        logger.debug("API", "StatutsEndpoint", "Pending", f"Worker data: {worker}")
        username = worker.get("username") if worker else None
        password = os.getenv("WORKER_PASSWORD") if username in ["Admin", "Administrador"] else "1234"
        # print(f"Worker IP: {worker_ip}, Username: {username}, Password: {password}")


        if not username or not password:
            raise HTTPException(status_code=500, detail="Credenciales de worker no configuradas en .env")

        try:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(str(worker_ip), username=username, password=password)

            def publish_killed():
                redis_manager.publish_task_progress(
                    task_id,
                    task.get('task_name'),
                    {
                        'progress': task.get('progress'),
                        'total_tasks': task.get('total_tasks'),
                        'completed_tasks': task.get('completed_tasks'),
                        'progress_by_task': task.get('progress_by_task'),
                        'status': 'killed'
                    }
                )

                redis_manager.register_task_end(
                    task_id=task_id,
                    worker_id=worker_id,
                    status='killed', 
                    error=None)

            if pid:
                # Matar un PID específico
                cmd = f'powershell.exe "Stop-Process -Id {pid}"'

                _, stdout, _ = client.exec_command(cmd)
                output = stdout.read().decode(errors='ignore').strip()
                client.close()
                

                if output:
                    logger.error("API", "StatusEndpoint", "Failure", f"⚠️ Error al matar el proceso con PID {pid} en {worker_ip}: {output}")
                    raise HTTPException(status_code=500, detail=f"Error al matar el proceso con PID {pid} en {worker_ip}: {output}")
                else:
                    logger.info("API", "StatusEndpoint", "Success", f"✅ Proceso con PID {pid} en {worker_ip} ha sido terminado.")
                    publish_killed()
                    return {"success": True, "message": f"✅ Proceso con PID {pid} en {worker_ip} ha sido terminado."}
            else:
                # Listar procesos python o celery
                cmd = 'powershell.exe "Get-Process | Where-Object { $_.ProcessName -match \'celery|python\' } | Select-Object ProcessName, Id"'
                _, stdout, _ = client.exec_command(cmd)
                output = stdout.read().decode(errors='ignore').strip()
                client.close()

                if not output:
                    logger.error("API", "StatusEndpoint", "Failure", f"⚠️ No se encontraron procesos python/celery en {worker_ip}.")
                    raise HTTPException(status_code=404, detail=f"No se encontraron procesos python/celery en {worker_ip}.")

                procesos = {}
                for line in output.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and parts[1].isdigit():
                        nombre_proceso = parts[0].split('.')[0]
                        pid_proceso = int(parts[1])
                        procesos.setdefault(nombre_proceso, []).append(pid_proceso)

                logger.info("API", "StatusEndpoint", "Pending", f"Procesos encontrados: {procesos}")

                celery_pid = procesos.get('celery', [None])[0]
                if not celery_pid:
                    raise HTTPException(status_code=404, detail="No se encontró proceso celery para matar.")

                # Matar el proceso celery
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect(worker_ip, username=username, password=password)
                kill_cmd = f'powershell.exe "Stop-Process -Id {celery_pid}"'
                _, stdout_kill, _ = client.exec_command(kill_cmd)
                result = stdout_kill.read().decode(errors='ignore').strip()
                client.close()
                if result:
                    logger.error("API", "StatusEndpoint", "Failure", f"⚠️ Error al matar el proceso celery con PID {celery_pid} en {worker_ip}: {result}")
                    raise HTTPException(status_code=500, detail=f"Error al matar el proceso celery con PID {celery_pid} en {worker_ip}: {result}")
                else:
                    logger.info("API", "StatusEndpoint", "Success", f"✅ Proceso celery con PID {celery_pid} en {worker_ip} ha sido terminado.")
                    publish_killed()
                    return {"success": True, "message": f"✅ Proceso celery con PID {celery_pid} en {worker_ip} ha sido terminado."}

        except paramiko.AuthenticationException:
            logger.error("API", "StatusEndpoint", "Failure", f"Error de autenticación en {worker_ip} con usuario {username}")
            raise HTTPException(status_code=401, detail="Error de autenticación SSH")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error("API", "StatusEndpoint", "Failure", f"Error killing task {task_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
        
@router.get(
    "/task-logs/{task_id}",
    summary="Obtener Logs de Tarea",
    description="""
    Obtiene los logs completos de una tarea específica en formato de texto plano.
    
    ### Información de logs:
    
    * **Logs de ejecución**: Registro detallado de la ejecución de la tarea
    * **Mensajes de error**: Detalles de errores y excepciones
    * **Progreso paso a paso**: Seguimiento de cada fase del proceso
    * **Timestamps**: Marcas de tiempo de cada evento
    * **Contexto del worker**: Información del worker que ejecutó la tarea
    
    ### Formato de salida:
    
    Los logs se devuelven en formato de texto plano, facilitando la lectura
    y análisis directo. Ideal para debugging y diagnóstico de problemas.
    
    ### Casos de uso:
    
    * **Debugging**: Diagnóstico de tareas fallidas
    * **Auditoría**: Revisión de procesos ejecutados
    * **Optimización**: Análisis de rendimiento
    * **Soporte técnico**: Información para resolución de incidencias
    
    ### Ejemplo de logs:
    
    ```
    2024-01-15 10:30:15 - INFO - Iniciando tarea robot_descargas
    2024-01-15 10:30:16 - INFO - Conectando a sistema externo
    2024-01-15 10:30:18 - INFO - Descargando documento 1/15
    2024-01-15 10:31:20 - ERROR - Timeout en descarga del documento
    2024-01-15 10:31:21 - INFO - Reintentando descarga...
    ```
    """,
    responses={
        200: {
            "description": "Logs obtenidos exitosamente (texto plano)",
            "content": {
                "text/plain": {
                    "example": "2024-01-15 10:30:15 - INFO - Iniciando tarea...\n2024-01-15 10:30:16 - INFO - Proceso completado"
                }
            }
        },
        404: {
            "description": "Tarea no encontrada o sin logs",
            "content": {
                "text/plain": {
                    "example": "No logs found for task: task_12345"
                }
            }
        }
    },
    response_class=PlainTextResponse,
    tags=["Logs", "Debugging"]
)
def get_task_logs(task_id: str):
    """Devuelve los logs de una tarea específica en base a sus metadatos."""
    import os
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    logger.info("API", "StatusEndpoint", "Pending", f"Buscando logs para la tarea {task_id}")

    task = None
    
    task_logs = r.lrange('task_assigment_log', 0, -1)
    for item in task_logs:
        try:
            t = json.loads(item)
            tid = t.get('id') or t.get('task_id')
            if tid == task_id:
                task = t
                worker = t.get('worker_id')
                break
        except Exception:
            continue

    if not task:
        logger.info("API", "StatusEndpoint", "Failure", f"Tarea {task_id} no encontrada")
        raise HTTPException(status_code=404, detail="Tarea no encontrada")
    
    # Buscar el estado actual de la tarea en el registro de tareas
    task_registry_key = f"{TASK_REGISTRY_KEY}:{task.get('worker_id')}"
    task_data = r.hget(task_registry_key, task_id)
    task = json.loads(task_data)

    task_type = task.get('task_name', task.get('type', 'unknown'))
    kwargs = task.get('kwargs', {})
    created_at = int(task.get('created_at', 0))
    # Determinar ruta de log
    log_root = r"\\192.168.184.162\c$\Users\Adria Martinez\Documents\workspace\redtrust-automation\logs"
    log_lines = []
    if 'descargas' in task_type:
        date = kwargs.get('date')
        if not date:
            logger.info("API", "StatusEndpoint", "Failure", f"No se encontró la fecha en los kwargs de la tarea {task_id}")
            raise HTTPException(status_code=400, detail="No se encontró la fecha en los kwargs de la tarea")
        date = date.replace('-', '')
        log_path = os.path.join(log_root, 'descargas', f"log_descargas_{date}.log")
        if not os.path.exists(log_path):
            logger.info("API", "StatusEndpoint", "Failure", f"No existe el log: {log_path}")
            raise HTTPException(status_code=404, detail=f"No existe el log: {log_path}")
        with open(log_path, encoding='utf-8') as f:
            log_lines = f.readlines()
        logger.info("API", "StatusEndpoint", "Success", f"Log de descargas encontrado para la tarea {task_id}")
    elif 'altas' in task_type:
        log_path = os.path.join(log_root, 'altas', "log_altas.log")
        if not os.path.exists(log_path):
            logger.info("API", "StatusEndpoint", "Failure", f"No existe el log: {log_path}")
            raise HTTPException(status_code=404, detail=f"No existe el log: {log_path}")
        if created_at:
            exec_date = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d')
        else:
            exec_date = None
        import re
        with open(log_path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r"[^-]+ - (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", line)
                if m and exec_date and m.group(1) == exec_date:
                    log_time = m.group(2)
                    # Convert log_time and created_at to comparable integers (HHMM)
                    log_hhmm = int(log_time.replace(":", ""))
                    created_hhmm = int(datetime.fromtimestamp(created_at).strftime('%H%M'))
                    if log_hhmm >= created_hhmm:
                        log_lines.append(line)
                
        logger.info("API", "StatusEndpoint", "Success", f"Log de altas filtrado por fecha para la tarea {task_id}")
    elif 'benchmark' in task_type:  
        log_path = os.path.join(log_root, 'benchmark', "log_benchmark.log")
        if not os.path.exists(log_path):
            logger.info("API", "StatusEndpoint", "Failure", f"No existe el log: {log_path}")
            raise HTTPException(status_code=404, detail=f"No existe el log: {log_path}")
        if created_at:
            exec_date = datetime.fromtimestamp(created_at).strftime('%Y-%m-%d')
        else:
            exec_date = None

        import re
        with open(log_path, encoding='utf-8') as f:
            for line in f:
                m = re.match(r"[^-]+ - (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})", line)
                if m and exec_date and m.group(1) == exec_date:
                    log_time = m.group(2)
                    # Convert log_time and created_at to comparable integers (HHMM)
                    log_hhmm = int(log_time.replace(":", ""))
                    created_hhmm = int(datetime.fromtimestamp(created_at).strftime('%H%M'))
                    if log_hhmm >= created_hhmm:
                        log_lines.append(line)
                
        logger.info("API", "StatusEndpoint", "Success", f"Log de benchmark filtrado por fecha para la tarea {task_id}")
    else:
        logger.info("API", "StatusEndpoint", "Failure", f"Tipo de tarea no soportado para logs: {task_type}")
        raise HTTPException(status_code=400, detail="Tipo de tarea no soportado para logs")
    if not log_lines:
        logger.info("API", "StatusEndpoint", "Success", f"No hay logs para la tarea {task_id}")
        return "No hay logs para esta tarea."
    logger.info("API", "StatusEndpoint", "Success", f"Logs devueltos para la tarea {task_id}")
    return ''.join(log_lines)

@router.post(
    "/clear-completed",
    summary="Limpiar Tareas Completadas",
    description="""
    Elimina todas las tareas completadas y fallidas del registro en Redis para mantener limpio el sistema.
    
    ### Funcionalidad:
    
    * **Limpieza automática**: Elimina tareas con estado completado, fallido o eliminado
    * **Optimización de memoria**: Libera espacio en Redis
    * **Mantenimiento**: Evita acumulación de registros obsoletos
    * **Contador de eliminaciones**: Retorna el número de tareas eliminadas
    
    ### Estados de tareas eliminadas:
    
    * `completed` - Tareas completadas exitosamente
    * `failed` - Tareas que fallaron durante la ejecución
    * `killed` - Tareas terminadas manualmente
    
    ### Casos de uso:
    
    * **Mantenimiento programado**: Limpieza periódica del sistema
    * **Optimización de rendimiento**: Mejora de velocidad de consultas
    * **Gestión de espacio**: Liberación de memoria en Redis
    * **Preparación de reportes**: Limpieza antes de generar estadísticas
    
    ⚠️ **Advertencia**: Esta acción es irreversible. Los datos de tareas eliminadas no se pueden recuperar.
    """,
    responses={
        200: {
            "description": "Limpieza completada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "removed": 25,
                        "message": "25 tareas completadas/fallidas eliminadas del registro"
                    }
                }
            }
        },
        500: {
            "description": "Error durante la limpieza"
        }
    },
    status_code=200,
    tags=["Mantenimiento", "Limpieza"]
)
def clear_completed_tasks():
    """Elimina todas las tareas completadas y fallidas del registro en Redis."""
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    removed = 0
    for key in r.scan_iter(f"{TASK_REGISTRY_KEY}:*"):
        registry = r.hgetall(key)
        for task_id, task_info in registry.items():
            try:
                info = json.loads(task_info)
                if info.get("status") in ["completed", "failed", "killed"]:
                    r.hdel(key, task_id)
                    removed += 1
            except Exception:
                continue
    return {"success": True, "removed": removed}

@router.post(
    "/clear-running",
    summary="Limpiar Tareas en Ejecución",
    description="""
    Elimina todas las tareas marcadas como en ejecución o pendientes del registro en Redis.
    
    ### ⚠️ **ATENCIÓN**: Endpoint de emergencia para casos extremos
    
    Este endpoint debe usarse solo en situaciones excepcionales donde el sistema
    tiene tareas "fantasma" que aparecen como en ejecución pero no están realmente activas.
    
    ### Funcionalidad:
    
    * **Limpieza de emergencia**: Elimina tareas zombi o huérfanas
    * **Recuperación del sistema**: Restaura estado consistente del registro
    * **Resolver inconsistencias**: Corrige problemas de sincronización
    * **Liberar workers**: Permite reasignación de workers bloqueados
    
    ### Estados de tareas eliminadas:
    
    * `running` - Tareas marcadas como en ejecución
    * `pending` - Tareas marcadas como pendientes
    
    ### ¿Cuándo usar este endpoint?
    
    * Workers desconectados abruptamente sin actualizar estado
    * Inconsistencias en el registro de Redis
    * Tareas que no responden a señales de terminación
    * Recuperación después de caídas del sistema
    
    ### Proceso recomendado:
    
    1. **Verificar workers reales**: Confirmar que no hay workers ejecutando tareas
    2. **Intentar terminación normal**: Usar `/kill-task/{id}` primero
    3. **Como último recurso**: Usar este endpoint si lo anterior falla
    4. **Verificar estado**: Comprobar que el sistema funciona correctamente
    
    ⚠️ **PELIGRO**: 
    - Puede interrumpir tareas realmente activas
    - Use solo cuando esté seguro de que las tareas no están ejecutándose
    - Recomendado tener backup del estado antes de usar
    """,
    responses={
        200: {
            "description": "Limpieza de emergencia completada",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "removed": 5,
                        "warning": "Se eliminaron 5 tareas en ejecución/pendientes. Verifique el estado del sistema."
                    }
                }
            }
        },
        500: {
            "description": "Error durante la limpieza de emergencia"
        }
    },
    status_code=200,
    tags=["Emergencia", "Recuperación"]
)
def clear_running_tasks():    
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

    removed = 0
    for key in r.scan_iter(f"{TASK_REGISTRY_KEY}:*"):
        registry = r.hgetall(key)
        for task_id, task_info in registry.items():
            try:
                info = json.loads(task_info)
                if info.get("status") in ["running", "pending"]:
                    r.hdel(key, task_id)
                    removed += 1
            except Exception:
                continue
    return {"success": True, "removed": removed}

@router.get(
    "/robot-tasks",
    summary="Obtener Lista de Tareas Disponibles",
    description="""
    Obtiene la lista de todas las tareas de robot registradas y disponibles en los workers activos.
    
    ### Funcionalidad:
    
    * **Inventario de tareas**: Lista completa de automatizaciones disponibles
    * **Verificación de capacidades**: Qué tareas puede ejecutar el sistema
    * **Diagnóstico**: Verificar que workers tienen las tareas registradas
    * **Desarrollo**: Útil para debugging y desarrollo de nuevas funciones
    
    ### Tipos de tareas esperadas:
    
    * `run_robot_altas` - Automatización de altas de clientes
    * `run_robot_descargas` - Automatización de descargas de documentos
    * `run_robot_matriculas` - Gestión de matrículas y puntos
    * `run_robot_consulta_enotum` - Consultas al sistema E-Notum
    * `run_robot_sede_judicial` - Procesos de sede judicial
    
    ### Información proporcionada:
    
    * **Nombres de tareas**: Lista de identificadores de tareas
    * **Disponibilidad**: Solo tareas actualmente registradas en workers
    * **Sin duplicados**: Lista única sin repeticiones
    
    ### Casos de uso:
    
    * **Validación previa**: Verificar disponibilidad antes de encolar tareas
    * **Monitoreo de workers**: Confirmar que workers tienen tareas registradas
    * **Interfaz de usuario**: Poblar listas desplegables de tareas disponibles
    * **Testing**: Verificar configuración de workers en entornos de prueba
    * **Documentación**: Generar inventario de capacidades del sistema
    
    ### Estado del sistema:
    
    Si la lista está vacía, indica que:
    - No hay workers conectados
    - Workers no tienen tareas registradas
    - Problemas de conectividad con Celery/Redis
    """,
    responses={
        200: {
            "description": "Lista de tareas obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": [
                        "run_robot_altas",
                        "run_robot_descargas", 
                        "run_robot_matriculas",
                        "run_robot_consulta_enotum",
                        "run_robot_sede_judicial"
                    ]
                }
            }
        },
        200: {
            "description": "No hay tareas registradas (lista vacía)",
            "content": {
                "application/json": {
                    "example": []
                }
            }
        },
        500: {
            "description": "Error consultando el registro de tareas"
        }
    },
    status_code=200,
    tags=["Inventario", "Capacidades"]
)
def get_robot_tasks():
    """Obtiene solo la lista de nombres de tareas registradas en los workers."""
    celery_app = Celery(
        'robot_system',
        broker=REDIS_URL,
        backend=REDIS_URL
    )

    insp = Inspect(app=celery_app)
    registered_tasks = insp.registered() or {}
    task_names = set()
    for task_list in registered_tasks.values():
        task_names.update(task_list)
    return list(task_names)
