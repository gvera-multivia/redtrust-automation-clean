import os
import json
import time
from typing import Optional
import redis
import socket
from datetime import datetime
from dotenv import load_dotenv
from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings

load_dotenv()

class RedisManager:
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))

    WORKER_STATUS_KEY = os.getenv("WORKER_STATUS_KEY", "worker_status")
    TASK_PROGRESS_KEY = os.getenv("TASK_PROGRESS_KEY", "task_progress")
    TASK_REGISTRY_KEY = os.getenv("TASK_REGISTRY_KEY", "task_registry")
    TASK_ASSIGNMENT_KEY = os.getenv("TASK_ASSIGNMENT_KEY", "task_assignment")
    TASK_ASSIGNMENT_EXPIRE = int(os.getenv("TASK_ASSIGNMENT_EXPIRE", "14400"))

    def __init__(self):
        self.redis_client = redis.Redis(host=self.REDIS_HOST, port=self.REDIS_PORT, decode_responses=True)
        self.logger = LoggerV2(module="API", class_name=self.__class__.__name__,
                               log_dir=settings.LOG_DIR, filename=settings.LOG_FILE)

    def _now(self):
        return datetime.utcnow().isoformat()
    
    def _get_hostname(self) -> str:
        return socket.gethostname()

    def _get_ip_address(self) -> str:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "127.0.0.1"
    
    def register_task_start(
        self,
        task_id: str,
        task_name: str,
        args: Optional[list],
        kwargs: Optional[dict],
        worker_id: Optional[str] = None,
        worker_ip: Optional[str] = None
    ):
        try:
            if not worker_ip:
                worker_ip = self._get_ip_address()

            if not worker_id:
                computer_name = self._get_hostname()
                worker_id = f"{worker_ip}@{computer_name}"


            task_info = {
                'task_id': task_id,
                'task_name': task_name,
                'worker_id': worker_id,
                'worker_ip': worker_ip,
                'pid': os.getpid(),
                'status': 'running',
                'args': args,
                'kwargs': kwargs,
                'start_time': self._now(),
                'created_at': self._now(),
                'updated_at': self._now(),
                'end_time': None,
                'progress': 0,
                'final_result': None,
                'error': None
            }
            
            self.redis_client.hset(f"{self.TASK_REGISTRY_KEY}:{worker_id}", task_id, json.dumps(task_info))
            self.logger.info("API", "RedisManager", "Success", f"Task {task_name} started")
        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"Error: {e}")

    def publish_task_progress(
        self,
        task_id: str,
        task_name: str,
        progress_data: dict,
        worker_id: Optional[str] = None,
        worker_ip: Optional[str] = None
    ):
        try:
            if not worker_ip:
                worker_ip = self._get_ip_address()

            if not worker_id:
                computer_name = self._get_hostname()
                worker_id = f"{worker_ip}@{computer_name}"
                
            timestamp = self._now()
            progress_info = {
                'task_id': task_id,
                'task_name': task_name,
                'worker_id': worker_id,
                'worker_ip': worker_ip,
                'pid': os.getpid(),
                'timestamp': timestamp,
                **progress_data
            }
            # Store live progress (short-term storage)
            self.redis_client.setex(f"{self.TASK_PROGRESS_KEY}:{task_id}", 600, json.dumps(progress_info))

            # Update only status + timestamp in registry
            registry_key = f"{self.TASK_REGISTRY_KEY}:{worker_id}"
            task_entry = self.redis_client.hget(registry_key, task_id)

            if task_entry:
                task_data = json.loads(task_entry)
                task_data.update({
                    'status': progress_data.get('status', task_data.get('status', 'running')),
                    'updated_at': timestamp
                })
                self.redis_client.hset(registry_key, task_id, json.dumps(task_data))

        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"Error: {e}")

    def register_task_end(
        self,
        task_id: str,
        worker_id: Optional[str] = None,
        status: str = 'completed',
        error: Optional[str] = None
    ) -> None:
        try:
            timestamp = self._now()
            if not worker_id:
                worker_ip = self._get_ip_address()
                computer_name = self._get_hostname()
                worker_id = f"{worker_ip}@{computer_name}"

            registry_key = f"{self.TASK_REGISTRY_KEY}:{worker_id}"
            progress_key = f"{self.TASK_PROGRESS_KEY}:{task_id}"
            
            task_entry = self.redis_client.hget(registry_key, task_id)
            progress_entry = self.redis_client.get(progress_key)
            print(f"Task ID: {task_id}, Registry Key: {registry_key}, Progress Key: {progress_key}")


            if task_entry:
                task_data = json.loads(task_entry)
                progress_data = json.loads(progress_entry) if progress_entry else {}
                task_data.update({
                    'end_time': timestamp,
                    'status': status,
                    'error': error,
                    'updated_at': timestamp,
                    'progress': progress_data.get('progress'),
                    'final_result': None if status != 'completed' else task_data.get('final_result')
                })
                self.redis_client.hset(registry_key, task_id, json.dumps(task_data))

            if progress_entry:
                print(f"Progress Entry: {json.loads(progress_entry)}")
                self.redis_client.delete(progress_key)
                self.redis_client.delete(f'celery-task-meta-{task_id}')

            # Clear assignment marker if exists
            try:
                self.clear_task_assignment(task_id)
            except Exception:
                pass

            self.logger.info("API", "CeleryManager", "Success",
                            f"Task {task_id} ended with status: {status}")
        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"Error: {e}")

    def assign_task(self, task_id: str, worker_id: str, ex: Optional[int] = None) -> bool:
        try:
            ex = ex or self.TASK_ASSIGNMENT_EXPIRE
            key = f"{self.TASK_ASSIGNMENT_KEY}:{task_id}"
            # NX ensures atomic set-if-not-exists
            return self.redis_client.set(key, worker_id, nx=True, ex=ex) is True
        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"assign_task error: {e}")
            return False

    def get_task_assignment(self, task_id: str) -> Optional[str]:
        try:
            return self.redis_client.get(f"{self.TASK_ASSIGNMENT_KEY}:{task_id}")
        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"get_task_assignment error: {e}")
            return None

    def clear_task_assignment(self, task_id: str) -> None:
        try:
            self.redis_client.delete(f"{self.TASK_ASSIGNMENT_KEY}:{task_id}")
        except Exception as e:
            self.logger.error("API", "RedisManager", "Failure", f"clear_task_assignment error: {e}")
