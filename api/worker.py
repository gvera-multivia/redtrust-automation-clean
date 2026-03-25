import os
import socket
import sys
import threading
import psutil
import json
import time
from celery import Celery
from celery.exceptions import Reject
from typing import Optional, List
from dotenv import load_dotenv
from datetime import datetime
from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings
from api.redis import RedisManager

# Robots
from app.robot_altas import RobotAltas
from app.robot_descargas import RobotDescargas
from app.robot_matriculas_y_puntos import RobotMatriculasYPuntos
from app.robot_consulta_enotum import RobotConsultaEnotum
from app.utils.validate_descargas import validate_downloads

load_dotenv()


class CeleryWorker:
    load_dotenv()
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    REDIS_URL = f'redis://{REDIS_HOST}:{REDIS_PORT}/0'

    WORKER_STATUS_KEY = os.getenv("WORKER_STATUS_KEY", "worker_status") 

    def __init__(self, main: bool= False):
        self.logger = LoggerV2(
            module="API", 
            class_name=self.__class__.__name__, 
            log_dir=settings.LOG_DIR,
            filename=settings.LOG_FILE,
        )
        
        self.celery_app = Celery(
            'robot_system',
            broker=self.REDIS_URL,
            backend=self.REDIS_URL
        )
        self.worker_id = self._get_worker_id()
        self.worker_ip = self._get_worker_ip()
        self.redis_manager = RedisManager()
        self.redis_client = self.redis_manager.redis_client
        self.start_time = datetime.now()
        self.current_task = None
        self.status = 'Free'
        self.rejection_recovery_active = False  # Flag to track recovery state
        
        self._configure_celery()
        self.register_tasks()
        
        # Log worker configuration
        self.logger.info("API", "CeleryManager", "Success", 
                    f"Worker {self.worker_id} config: "
                    f"task_acks_late={self.celery_app.conf.task_acks_late}, "
                    f"visibility_timeout={self.celery_app.conf.broker_transport_options.get('visibility_timeout', 'default')}, "
                    f"worker_prefetch_multiplier={self.celery_app.conf.worker_prefetch_multiplier}, "
                    f"task_reject_on_worker_lost={self.celery_app.conf.task_reject_on_worker_lost}, "
                    f"result_expires={self.celery_app.conf.result_expires}, "
                    f"task_default_queue={self.celery_app.conf.task_default_queue}, "
                    f"broker={self.REDIS_URL}")

        # Start background threads
        if not main: 
            self._start_worker_status_thread()
        
            self.logger.info("API", "CeleryManager", "Success", 
                        f"Celery Manager initialized for worker {self.worker_id}")


    def _get_worker_ip(self):
        """Get the local IP address of the worker"""
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            try:
                return socket.gethostbyname(socket.gethostname())
            except Exception:
                return 'unknown'

    def _get_worker_id(self):
        """Generate unique worker ID based on hostname and IP"""
        for arg in sys.argv:
            if arg.startswith('--hostname='):
                return arg.split('=', 1)[1]
        
        hostname = socket.gethostname()
        ip = self._get_worker_ip()
        return f"worker@{hostname}-{ip}"

    def _configure_celery(self):
        self.celery_app.conf.update(
            task_serializer='json',
            accept_content=['json'],
            result_serializer='json',
            timezone='UTC',
            enable_utc=True,
            task_track_started=True,
            worker_send_task_events=True,
            task_default_queue='robot_tasks',
            task_routes={'*': {'queue': 'robot_tasks'}},
            worker_prefetch_multiplier=1,
            task_acks_late=False,  # ACK immediately when task starts (prevents redelivery)
            task_reject_on_worker_lost=True,
            worker_disable_rate_limits=True,
            task_send_sent_event=True,
            result_expires=43200,  # 12 hours
            broker_transport_options={
                'visibility_timeout': 43200,  # 12 hours - MUST be longer than longest task
            },
        )
    
    def _start_worker_status_thread(self):
        """Start a single thread to publish worker status and maintain connection with master (heartbeat)"""
        def status_and_heartbeat_loop():            
            while True:
                try:
                    # Get system metrics
                    cpu_percent = psutil.cpu_percent(interval=1)
                    memory = psutil.virtual_memory()
                    disk = psutil.disk_usage('/')
                    network = psutil.net_io_counters()
                    process = psutil.Process()

                    status_data = {
                        'worker_id': self.worker_id,
                        'ip': self.worker_ip,
                        'hostname': socket.gethostname(),
                        'username': os.getenv('USERNAME') or os.getenv('USER') or 'unknown',
                        'status': self.status,
                        'current_task': self.current_task,
                        'rejection_recovery_active': self.rejection_recovery_active,
                        'start_time': self.start_time.isoformat(),
                        'uptime_seconds': (datetime.now() - self.start_time).total_seconds(),
                        'timestamp': datetime.now().isoformat(),

                        # Hardware metrics
                        'cpu_percent': cpu_percent,
                        'cpu_count': psutil.cpu_count(),
                        'memory_total': memory.total,
                        'memory_used': memory.used,
                        'memory_percent': memory.percent,
                        'disk_total': disk.total,
                        'disk_used': disk.used,
                        'disk_percent': disk.percent,

                        # Network metrics
                        'network_bytes_sent': network.bytes_sent,
                        'network_bytes_recv': network.bytes_recv,

                        # Process metrics
                        'process_pid': process.pid,
                        'process_memory_percent': process.memory_percent(),
                        'process_cpu_percent': process.cpu_percent(),
                        'process_num_threads': process.num_threads(),
                    }

                    # Store status and heartbeat in the same queue/key
                    self.redis_client.setex(f"{self.WORKER_STATUS_KEY}:{self.worker_id}", 30, json.dumps(status_data))

                    self.logger.debug("API", "CeleryManager", "Success", 
                                    f"Status/Heartbeat published for worker {self.worker_id}")

                except Exception as e:
                    self.logger.error("API", "CeleryManager", "Failure", 
                                    f"Error publishing status/heartbeat: {e}")

                time.sleep(10)  # Publish every 10 seconds

        thread = threading.Thread(target=status_and_heartbeat_loop, daemon=True)
        thread.start()

    def _schedule_post_rejection_recovery(self, task_id, task_name, assigned_to):
        """Schedule recovery after task rejection - wait 30 seconds then restart service"""
        def recovery_process():
            try:
                # Mark worker as in recovery mode
                self.rejection_recovery_active = True
                self.status = 'Recovering from rejection'
                
                self.logger.warning("API", "CeleryManager", "Recovery", 
                                  f"Worker entering 30-second recovery mode after rejecting task {task_id}")
                
                # Wait 30 seconds
                time.sleep(30)
                
                # Reset worker status and reinitialize service
                self.status = 'Free'
                self.current_task = None
                self.rejection_recovery_active = False
                
                # Update worker status to indicate it's operational again
                self.logger.info("API", "CeleryManager", "Success", 
                                f"Worker recovery completed - ready for new tasks")
                
                # Publish recovery status
                recovery_status = {
                    'worker_id': self.worker_id,
                    'status': 'recovered',
                    'recovery_completed_at': datetime.now().isoformat(),
                    'rejected_task_id': task_id,
                    'rejected_task_name': task_name,
                    'assigned_to': assigned_to,
                    'message': 'Worker recovered from rejection and ready for new tasks'
                }
                
                self.redis_client.setex(f"worker_recovery:{self.worker_id}:{task_id}", 300, json.dumps(recovery_status))
                
            except Exception as e:
                self.logger.error("API", "CeleryManager", "Recovery", 
                                f"Error during post-rejection recovery: {e}")
                self.rejection_recovery_active = False
                self.status = 'Free'
        
        # Start recovery in background thread
        recovery_thread = threading.Thread(target=recovery_process, daemon=True)
        recovery_thread.start()

    def register_tasks(self):
        manager = self

        @self.celery_app.task(bind=True, name='run_robot_altas')
        def run_robot_altas(self, cliente=None, sedes=None, limit: str | int = 10):
            task_id = self.request.id
            task_name = 'run_robot_altas'
            assigned_to = manager.redis_manager.get_task_assignment(task_id)
            if assigned_to and assigned_to != manager.worker_id:
                manager.redis_manager.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to}'})
                manager.redis_manager.register_task_end(task_id, manager.worker_id, 'rejected', f'assigned_to:{assigned_to}')
                # Schedule 30-second recovery before rejecting
                manager._schedule_post_rejection_recovery(task_id, task_name, assigned_to)
                raise Reject(requeue=False)

            manager.redis_manager.register_task_start(task_id, 'run_robot_altas', [cliente], {'sedes': sedes})
            try:
                if sedes is None or sedes == "" or sedes == [] or sedes == {}:
                    sedes = [
                        'andalucía', 
                        'asturias', 
                        'badajoz', 
                        # 'baleares', 
                        'burgos', 
                        'castilla la mancha', 
                        'castilla y león',
                        'ceuta', 
                        'comunidad valenciana', 
                        'la rioja', 
                        'melilla',
                        # 'mahon', 
                        'madrid',
                        'pais vasco', 
                        'enotum', 
                        'dev', 
                        'dehù',
                        'xaloc', 
                        # 'oficina virtual ayuntamiento terrassa', 
                        'agencia tributaria de catalunya',
                        'migjorn gran',
                        'ayuntamiento de málaga',
                    ]

                robot = RobotAltas(execution_id=task_id)

                def progress_hook():
                    manager.redis_manager.publish_task_progress(task_id, 'run_robot_altas', {
                        'progress': robot.progress,
                        'total_tasks': robot.total_tasks,
                        'completed_tasks': robot.completed_tasks,
                        'progress_by_task': robot.progress_by_task,
                        'status': 'running'
                    })

                # Override progress method
                original_method = robot.actualizar_progreso_fase
                robot.actualizar_progreso_fase = lambda *a, **k: (
                    original_method(*a, **k), 
                    progress_hook()
                )
                
                if cliente is None or cliente == "":
                    cliente = None

                robot.run(cliente=cliente, sedes=sedes, limit=limit)

                                
                # Final progress update
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_altas', {
                    'progress': 100,
                    'total_tasks': robot.total_tasks,
                    'completed_tasks': robot.completed_tasks,
                    'progress_by_task': robot.progress_by_task,
                    'status': 'completed'
                })
                
                manager.redis_manager.register_task_end(task_id, 'completed')
                return {'status': 'completed', 'robot': 'altas', 'task_id': task_id}

            except Exception as e:
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_altas', {'status': 'failed', 'error': str(e)})
                manager.redis_manager.register_task_end(task_id, 'failed', str(e))
                raise

        @self.celery_app.task(bind=True, name='run_robot_descargas')
        def run_robot_descargas(self, date=None, cliente=None, sedes=None, message_ids: Optional[List]=None, message_keys: Optional[List]=None, limit: str | int = 250):
            task_id = self.request.id
            task_name = 'run_robot_descargas'
            assigned_to = manager.redis_manager.get_task_assignment(task_id)
            if assigned_to and assigned_to != manager.worker_id:
                manager.redis_manager.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to}'})
                manager.redis_manager.register_task_end(task_id, manager.worker_id, 'rejected', f'assigned_to:{assigned_to}')
                # Schedule 30-second recovery before rejecting
                manager._schedule_post_rejection_recovery(task_id, task_name, assigned_to)
                raise Reject(requeue=False)

            manager.redis_manager.register_task_start(task_id, 'run_robot_descargas', 
                                      [date, cliente], {'sedes': sedes, 'message_id': message_ids, 'message_key': message_keys})

            try:
                robot = RobotDescargas(date=date or None, execution_id=task_id)
                
                def progress_hook():
                    manager.redis_manager.publish_task_progress(task_id, 'run_robot_descargas', {
                        'progress': robot.progress,
                        'total_tasks': robot.total_tasks,
                        'completed_tasks': robot.completed_tasks,
                        'progress_by_task': robot.progress_by_task,
                        'status': 'running'
                    })
                
                original_method = robot.actualizar_progreso_fase
                robot.actualizar_progreso_fase = lambda *a, **k: (
                    original_method(*a, **k), 
                    progress_hook()
                )
                
                if cliente is None or (isinstance(cliente, str) and cliente.strip() == ""):
                    cliente = None
                if sedes is None or sedes == "" or sedes == [] or sedes == {}:
                    sedes = [ 'enotum', 'dev', 'dehù']
                if message_ids is None or message_ids == "":
                    message_ids = None
                if message_keys is None or message_keys == "":
                    message_keys = None

                robot.run(cliente=cliente, sedes=sedes, message_ids=message_ids, message_keys=message_keys, limit=limit)
                
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_descargas', {
                    'progress': 100,
                    'total_tasks': robot.total_tasks,
                    'completed_tasks': robot.completed_tasks,
                    'progress_by_task': robot.progress_by_task,
                    'status': 'completed'
                })
                
                validate_downloads(robot.logger, date or None)
                manager.redis_manager.register_task_end(task_id, 'completed')
                return {'status': 'completed', 'robot': 'descargas', 'task_id': task_id}
                
            except Exception as e:
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_descargas', {
                    'status': 'failed',
                    'error': str(e)
                })
                manager.redis_manager.register_task_end(task_id, 'failed', str(e))
                raise

        @self.celery_app.task(bind=True, name='run_robot_matriculas')
        def run_robot_matriculas(self, date=None, clientes=None, limit: str | int = 100):
            task_id = self.request.id
            task_name = 'run_robot_matriculas'
            assigned_to = manager.redis_manager.get_task_assignment(task_id)
            if assigned_to and assigned_to != manager.worker_id:
                manager.redis_manager.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to}'})
                manager.redis_manager.register_task_end(task_id, manager.worker_id, 'rejected', f'assigned_to:{assigned_to}')
                # Schedule 30-second recovery before rejecting
                manager._schedule_post_rejection_recovery(task_id, task_name, assigned_to)
                raise Reject(requeue=False)

            manager.redis_manager.register_task_start(task_id, 'run_robot_matriculas', [date, clientes], {})

            try:
                robot = RobotMatriculasYPuntos(date=date or time.strftime('%Y%m%d'), execution_id=task_id)
                
                def progress_hook():
                    manager.redis_manager.publish_task_progress(task_id, 'run_robot_matriculas', {
                        'progress': robot.progress,
                        'total_tasks': robot.total_tasks,
                        'completed_tasks': robot.completed_tasks,
                        'progress_by_task': robot.progress_by_task,
                        'status': 'running'
                    })
                
                original_method = robot.actualizar_progreso_fase
                robot.actualizar_progreso_fase = lambda *a, **k: (
                    original_method(*a, **k), 
                    progress_hook()
                )

                if clientes is None or clientes == "" or clientes == [] or clientes == {}:
                    clientes = None
                
                robot.run(clientes=clientes or None, limit=limit)
                
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_matriculas', {
                    'progress': 100,
                    'total_tasks': robot.total_tasks,
                    'completed_tasks': robot.completed_tasks,
                    'progress_by_task': robot.progress_by_task,
                    'status': 'completed'
                })
                
                manager.redis_manager.register_task_end(task_id, 'completed')
                return {'status': 'completed', 'robot': 'matriculas', 'task_id': task_id}
                
            except Exception as e:
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_matriculas', {
                    'status': 'failed',
                    'error': str(e)
                })
                manager.redis_manager.register_task_end(task_id, 'failed', str(e))
                raise

        @self.celery_app.task(bind=True, name='run_robot_consulta_enotum')
        def run_robot_consultaenotum(self, cliente=None, fecha_a_revisar=None, limit: str | int = 150):
            task_id = self.request.id
            task_name = 'run_robot_consulta_enotum'
            assigned_to = manager.redis_manager.get_task_assignment(task_id)
            if assigned_to and assigned_to != manager.worker_id:
                manager.redis_manager.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to}'})
                manager.redis_manager.register_task_end(task_id, manager.worker_id, 'rejected', f'assigned_to:{assigned_to}')
                # Schedule 30-second recovery before rejecting
                manager._schedule_post_rejection_recovery(task_id, task_name, assigned_to)
                raise Reject(requeue=False)

            manager.redis_manager.register_task_start(task_id, 'run_robot_consulta_enotum', [cliente, fecha_a_revisar], {})

            try:
                robot = RobotConsultaEnotum(fecha_a_revisar=fecha_a_revisar or None, execution_id=task_id)
                def progress_hook():
                    manager.redis_manager.publish_task_progress(task_id, 'run_robot_consulta_enotum', {
                        'progress': robot.progress,
                        'total_tasks': getattr(robot, 'total_tasks', None),
                        'completed_tasks': getattr(robot, 'completed_tasks', None),
                        'progress_by_task': getattr(robot, 'progress_by_task', None),
                        'status': 'running'
                    })

                original_method = getattr(robot, 'actualizar_progreso_fase', None)
                if original_method:
                    robot.actualizar_progreso_fase = lambda *a, **k: (
                        original_method(*a, **k),
                        progress_hook()
                    )
                    
                robot.run(cliente=cliente, fecha_a_revisar=fecha_a_revisar, limit=limit)

                manager.redis_manager.publish_task_progress(task_id, 'run_robot_consulta_enotum', {
                    'progress': 100,
                    'total_tasks': getattr(robot, 'total_tasks', None),
                    'completed_tasks': getattr(robot, 'completed_tasks', None),
                    'progress_by_task': getattr(robot, 'progress_by_task', None),
                    'status': 'completed'
                })

                manager.redis_manager.register_task_end(task_id, 'completed')
                return {'status': 'completed', 'robot': 'enotum', 'task_id': task_id}

            except Exception as e:
                manager.redis_manager.publish_task_progress(task_id, 'run_robot_consulta_enotum', {
                    'status': 'failed',
                    'error': str(e)
                })
                manager.redis_manager.register_task_end(task_id, 'failed', str(e))
                raise
        
        @self.celery_app.task(bind=True, name='run_benchmark')
        def run_benchmark(self, **kwargs):
            import math
            task_id = self.request.id
            task_name = 'run_benchmark'
            assigned_to = manager.redis_manager.get_task_assignment(task_id)
            if assigned_to and assigned_to != manager.worker_id:
                manager.redis_manager.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to}'})
                manager.redis_manager.register_task_end(task_id, manager.worker_id, 'rejected', f'assigned_to:{assigned_to}')
                # Schedule 30-second recovery before rejecting
                manager._schedule_post_rejection_recovery(task_id, task_name, assigned_to)
                raise Reject(requeue=False)

            manager.redis_manager.register_task_start(task_id, 'run_benchmark', [], kwargs)

            try:
                logger = LoggerV2(
                    execution_id=task_id,
                    module="Benchmark",
                    class_name="Benchmark",
                    log_dir='logs/benchmark',
                    filename='benchmark',
                )
                logger.info("Benchmark", "run_benchmark", "Pending",
                            f"Starting benchmark with parameters: {kwargs}")
                iterations = kwargs.get('iterations', 10000)
                start_time = time.time()
                
                for i in range(1, iterations + 1):
                    result = sum(math.sqrt(j) for j in range(1, 1000))
                    
                    
                    if i % 100 == 0:
                        progress = int((i / iterations) * 100)
                        manager.redis_manager.publish_task_progress(task_id, 'run_benchmark', {
                            'progress': progress,
                            'current_iteration': i,
                            'total_iterations': iterations,
                            'partial_result': result,
                            'status': 'running'
                        })
                        logger.info("Benchmark", "run_benchmark", "Success",
                                f"Iteration {i}/{iterations} - Result: {result}")
                
                duration = time.time() - start_time
                
                manager.redis_manager.publish_task_progress(task_id, 'run_benchmark', {
                    'progress': 100,
                    'duration': duration,
                    'final_result': result,
                    'status': 'completed'
                })
                
                manager.redis_manager.register_task_end(task_id, 'completed')
                return {
                    'status': 'completed',
                    'task': 'benchmark',
                    'duration': duration,
                    'result': result,
                    'task_id': task_id
                }
                
            except Exception as e:
                manager.redis_manager.publish_task_progress(task_id, 'run_benchmark', {
                    'status': 'failed',
                    'error': str(e)
                })
                manager.redis_manager.register_task_end(task_id, 'failed', str(e))
                raise

# Expose the Celery application under the conventional names the
# `celery` CLI expects when using `-A module` (it looks for `app`)
# Keep `celery_app` for backward compatibility with imports in the codebase.
app = CeleryWorker().celery_app
# Backwards compatibility aliases
celery_app = app
celery = app
