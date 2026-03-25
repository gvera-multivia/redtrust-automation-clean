import os
import time
import json
import threading
import uuid
from celery import Celery
from celery.app.control import Inspect

from dotenv import load_dotenv
import redis
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings


class Dispatcher:
    """Dispatcher class to manage task distribution and worker management"""
    load_dotenv()
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
    WORKER_STATUS_KEY = os.getenv("WORKER_STATUS_KEY", "worker_status")
    TASK_PROGRESS_KEY = os.getenv("TASK_PROGRESS_KEY", "task_progress")
    ASSIGNMENT_KEY_PREFIX = os.getenv("TASK_ASSIGNMENT_KEY", "task_assignment")
    ASSIGNMENT_EXPIRE = int(os.getenv("TASK_ASSIGNMENT_EXPIRE", "14400"))

    def __init__(self):
        self.running = False
        self.queue_lock = threading.Lock()
        
        # Initialize Redis connection - we'll get the connection details from celery_manager if available
        self.redis_client = redis.Redis(
            host=self.REDIS_HOST, 
            port=self.REDIS_PORT, 
            decode_responses=True
        )
                    
        self.logger = LoggerV2(
            module="API", 
            class_name=self.__class__.__name__, 
            log_dir=settings.LOG_DIR,
            filename=settings.LOG_FILE,
        )
        
        # Worker management
        self.worker_timeout = 30  # seconds
        self.task_assignment_history = {}
        
    def get_alive_workers(self) -> List[Dict]:
        """Get list of workers that are sending heartbeats"""
        try:
            alive_workers = []
            current_time = datetime.now()

            celery_app = Celery(
                'robot_system',
                broker=self.REDIS_URL,
                backend=self.REDIS_URL
            )

            insp = Inspect(app=celery_app)
            active_workers = insp.active() or {}

            for worker, tasks in active_workers.items():
                try:
                    status_key = f"{self.WORKER_STATUS_KEY}:{worker}"
                    status_data = self.redis_client.get(status_key)
                    
                    if status_data:
                        status = json.loads(status_data)
                        last_heartbeat = datetime.fromisoformat(status.get('timestamp'))
                        
                        if (current_time - last_heartbeat).total_seconds() <= self.worker_timeout:
                            alive_workers.append({
                                'worker_id': worker,
                                'ip': status.get('ip'),
                                'status': status.get('status'),
                                'last_heartbeat': status.get('last_heartbeat'),
                                'cpu_percent': status.get('cpu_percent'),
                                'memory_percent': status.get('memory_percent'),
                                'tasks': tasks
                            })
                        
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    self.logger.error("API", "Dispatcher", "Failure", 
                                    f"Error parsing worker heartbeat: {e}")
            
            return alive_workers
            
        except Exception as e:
            self.logger.error("API", "Dispatcher", "Failure", 
                            f"Error getting alive workers: {e}")
            return []

    def get_available_workers(self) -> List[Dict]:
        """Get workers that are alive and available for new tasks"""
        alive_workers = self.get_alive_workers()
        available_workers = []        
        
        for worker in alive_workers:
            if worker.get('status') == 'Free':
                # Get detailed worker status
                status_key = f"{self.WORKER_STATUS_KEY}:{worker['worker_id']}"
                status_data = self.redis_client.get(status_key)
                
                if status_data:
                    try:
                        detailed_status = json.loads(status_data)
                        worker.update(detailed_status)
                        available_workers.append(worker)
                    except json.JSONDecodeError:
                        continue
        
        return available_workers

    def select_best_worker(self, available_workers: List[Dict], task_name: str) -> Optional[Dict]:
        """Select the best worker for a task based on various criteria"""
        if not available_workers:
            return None
        
        # Simple selection criteria (can be enhanced)
        # 1. Prefer workers with lower CPU usage
        # 2. Prefer workers with more available memory
        # 3. Consider task assignment history for load balancing
        
        scored_workers = []
        
        for worker in available_workers:
            score = 0
            
            # CPU score (lower is better)
            cpu_percent = worker.get('cpu_percent', 100)
            score += (100 - cpu_percent) * 0.4
            
            # Memory score (lower usage is better)
            memory_percent = worker.get('memory_percent', 100)
            score += (100 - memory_percent) * 0.3
            
            # Load balancing score
            worker_id = worker.get('worker_id')
            recent_tasks = self.task_assignment_history.get(worker_id, 0)
            score += max(0, 10 - recent_tasks) * 0.3
            
            scored_workers.append((score, worker))
        
        # Sort by score (highest first)
        scored_workers.sort(key=lambda x: x[0], reverse=True)
        
        selected_worker = scored_workers[0][1]
        
        # Update assignment history
        worker_id = selected_worker.get('worker_id')
        self.task_assignment_history[worker_id] = self.task_assignment_history.get(worker_id, 0) + 1
        
        return selected_worker

    def dispatch_task_to_worker(self, task_data: Dict, worker: Dict) -> bool:
        """Dispatch a specific task to a specific worker"""
        try:
            task_name = task_data['task']
            args = task_data.get('args', [])
            kwargs = task_data.get('kwargs', {})

            # Reserve the assignment in Redis atomically (avoid duplicates)
            task_id = task_data.get('task_id') or str(uuid.uuid4())
            assignment_key = f"{self.ASSIGNMENT_KEY_PREFIX}:{task_id}"            

            # Create Celery app and check registered tasks (best-effort)
            celery_app = Celery(
                'robot_system',
                broker=self.REDIS_URL,
                backend=self.REDIS_URL
            )

            inspect = None
            try:
                inspect = celery_app.control.inspect()
                registered_tasks_dict = inspect.registered() if inspect else None
            except Exception:
                registered_tasks_dict = None

            registered_tasks = None
            if registered_tasks_dict:
                # Deduplicate tasks reported by workers
                registered_tasks = set()
                for tasks in registered_tasks_dict.values():
                    if tasks:
                        registered_tasks.update(tasks)

            # If we were able to list tasks and the task is not registered, release and abort
            if registered_tasks is not None and task_name not in registered_tasks:
                self.redis_client.delete(assignment_key)
                self.logger.error("API", "Dispatcher", "Failure", f"Task {task_name} not found in Celery tasks")
                return False            
            
            # Esperar hasta que arranque (STARTED) o falle
            timeout = 30  # segundos
            poll_interval = 3
            elapsed = 0

            while elapsed < timeout:
                # Send task to Celery with our reserved task_id
                try:
                    reserved = self.redis_client.set(assignment_key, worker['worker_id'], nx=True, ex=self.ASSIGNMENT_EXPIRE)
                    if not reserved:
                        existing = self.redis_client.get(assignment_key)
                        self.logger.warning("API", "Dispatcher", "Failure",
                                            f"Task {task_id} already assigned to {existing}; skipping dispatch to {worker['worker_id']}")
                        return False
                    
                    result = celery_app.send_task(
                        task_name,
                        args=args,
                        kwargs=kwargs,
                        queue='robot_tasks',
                        task_id=task_id
                    )
                except Exception as e:
                    # Release reservation on failure
                    try:
                        self.redis_client.delete(assignment_key)
                    except Exception:
                        pass
                    self.logger.error("API", "Dispatcher", "Failure", f"Error sending task {task_id}: {e}")
                
                result_state = result.state

                if result_state == 'STARTED':
                    self.logger.info(
                        "API", "Dispatcher", "Success",
                        f"Task {task_id} has STARTED on worker {result.info.get('hostname')}" 
                    )
                    break
                elif result_state in ('FAILURE', 'REVOKED'):
                    self.redis_client.delete(assignment_key)
                    self.logger.error(
                        "API", "Dispatcher", "Failure",
                        f"Task {task_id} failed before start: {result_state}"
                    )                    
                else:
                    self.redis_client.delete(assignment_key)
                    
                time.sleep(poll_interval)
                elapsed += poll_interval

            else:
                # Nunca pasó de PENDING
                self.logger.warning(
                    "API", "Dispatcher", "Warning",
                    f"Task {task_id} never left PENDING state"
                )

                raise TimeoutError(f"Task {task_id} did not start within timeout period")

            # Log the assignment
            assignment_log = {
                'task_id': task_id,
                'task_name': task_name,
                'worker_id': worker['worker_id'],
                'worker_ip': worker['ip'],
                'args': args,
                'kwargs': kwargs,
                'timestamp': time.time(),
                'assigned_by': 'dispatcher'
            }

            self.redis_client.lpush("task_assignment_log", json.dumps(assignment_log))

            self.logger.info("API", "Dispatcher", "Success",
                        f"Task {task_name} ({task_id}) assigned to worker {worker['worker_id']}")

            return True
            
        except (Exception, TimeoutError) as e:
            self.logger.error("API", "Dispatcher", "Failure", 
                            f"Error dispatching task to worker: {e}")
            return False

    def cleanup_expired_data(self):
        """Clean up expired worker data and task assignment history"""
        try:
            # Clean up old task assignment history (keep last hour)
            current_time = time.time()
            cutoff_time = current_time - 3600  # 1 hour ago
            
            # Reset assignment history periodically
            if hasattr(self, '_last_cleanup') and current_time - self._last_cleanup > 3600:
                self.task_assignment_history.clear()
                self._last_cleanup = current_time
            elif not hasattr(self, '_last_cleanup'):
                self._last_cleanup = current_time
            
            # Clean up old logs (keep last 1000 entries)
            log_length = self.redis_client.llen("task_assignment_log")
            if log_length > 1000:
                self.redis_client.ltrim("task_assignment_log", 0, 999)
            
        except Exception as e:
            self.logger.error("API", "Dispatcher", "Error", 
                            f"Error during cleanup: {e}")

    def dispatch_tasks(self, stop_event):
        """Task dispatcher with heartbeat monitoring"""
        self.running = True
        self.logger.info("API", "Dispatcher", "Info", "Dispatcher started")
        
        while not stop_event.is_set():
            try:
                # Check queue length
                queue_length = self.redis_client.llen('dispatcher_tasks_queue')
                
                if queue_length > 0:
                    self.logger.info("API", "Dispatcher", "Info", 
                                    f"Tasks pending in queue: {queue_length}")
                    
                self.logger.debug("API", "Dispatcher", "Pending", 
                               f"Tasks pending in queue: {queue_length}")
                
                # Get next task
                task_json = self.redis_client.lpop('dispatcher_tasks_queue')
                
                if task_json:
                    try:
                        self.logger.info("API", "Dispatcher", "Pending", f"Tarea encontrada en entrada_queue: {task_json}")
                        task_data = json.loads(task_json)
                        task_name = task_data['task']

                        # Get available workers
                        available_workers = self.get_available_workers()
                        
                        if available_workers:
                            # Select best worker
                            selected_worker = self.select_best_worker(available_workers, task_name)
                            
                            if selected_worker:
                                # Dispatch task
                                success = self.dispatch_task_to_worker(task_data, selected_worker)
                                
                                retries = 0
                                max_retries = 3
                                while retries < max_retries and not success:
                                    self.logger.info("API", "Dispatcher", "Retry", 
                                                    f"Retrying dispatch of task {task_name} (attempt {retries + 1})")
                                    time.sleep(2)
                                    success = self.dispatch_task_to_worker(task_data, selected_worker)
                                    retries += 1

                                if not success:
                                    self.logger.error("API", "Dispatcher", "Failure", 
                                                    f"Failed to dispatch task {task_name} after {max_retries} attempts")                                    
                                    time.sleep(5)
                            else:
                                self.logger.warning("API", "Dispatcher", "Failure", 
                                                  "No suitable worker selected")
                                self.redis_client.rpush('dispatcher_tasks_queue', task_json)
                                time.sleep(5)
                        else:
                            self.logger.warning("API", "Dispatcher", "Failure", 
                                              "No available workers found")
                            # Put task back in queue
                            self.redis_client.rpush('dispatcher_tasks_queue', task_json)
                            time.sleep(10)
                            
                    except json.JSONDecodeError as e:
                        self.logger.error("API", "Dispatcher", "Failure", 
                                        f"Invalid task JSON: {e}")
                        continue
                        
                    except Exception as e:
                        self.logger.error("API", "Dispatcher", "Failure", 
                                        f"Error processing task: {e}")
                        # Put task back in queue
                        self.redis_client.rpush('dispatcher_tasks_queue', task_json)
                        time.sleep(5)
                else:
                    # No tasks, wait a bit
                    time.sleep(2)
                
                # Periodic cleanup
                if int(time.time()) % 300 == 0:  # Every 5 minutes
                    self.cleanup_expired_data()
                    
            except Exception as e:
                self.logger.error("API", "Dispatcher", "Failure", 
                                f"Dispatcher error: {e}")
                time.sleep(5)
        
        self.logger.info("API", "Dispatcher", "Info", "Dispatcher stopped")
        self.running = False

    def get_dispatcher_status(self) -> Dict:
        """Get current dispatcher status"""
        try:
            alive_workers = self.get_alive_workers()
            available_workers = self.get_available_workers()
            queue_length = self.redis_client.llen('dispatcher_tasks_queue')
            
            return {
                'running': self.running,
                'queue_length': queue_length,
                'total_workers': len(alive_workers),
                'available_workers': len(available_workers),
                'workers': alive_workers,
                'task_assignment_history': self.task_assignment_history,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error("API", "Dispatcher", "Failure", 
                            f"Error getting dispatcher status: {e}")
            return {
                'running': self.running,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
