import json
import time
import os
import redis
from dotenv import load_dotenv
from api.routes.status import get_robot_tasks
from app.helper.loggerV2 import LoggerV2
from api.config.api_config import settings


def enqueue_task(
    task_name: str, 
    args: list = None, 
    kwargs: dict = None
) -> dict:
    """
    Enqueue a task to the Redis dispatcher queue.

    Parameters:
        task_name (str): Name of the task to enqueue. Must be one of the valid tasks.
        args (list, optional): Positional arguments for the task. Defaults to empty list.
        kwargs (dict, optional): Keyword arguments for the task. Defaults to empty dict.

    Returns:
        dict: Result of the enqueue operation, including status, message, and task data if successful.
    """
    load_dotenv()
    REDIS_HOST = os.getenv("REDIS_HOST")
    REDIS_PORT = int(os.getenv("REDIS_PORT"))
    # Create a logger instance for this function
    logger = LoggerV2(
        module="API", 
        class_name="enqueue_task", 
        log_dir=settings.LOG_DIR,
        filename=settings.LOG_FILE,
    )
    
    # valid_tasks = ['run_robot_altas', 'run_robot_descargas', 'run_robot_matriculas', 'run_benchmark', 'run_robot_consulta-enotum']
    valid_tasks = get_robot_tasks()
    
    if task_name not in valid_tasks:
        logger.warning("API", "enqueue_task", "Failure", 
                       f"Invalid task: {task_name}")
        return {'status': 'error', 'message': f'Invalid task: {task_name}'}
    
    try:
        r = redis.Redis(host=REDIS_HOST, 
                       port=REDIS_PORT, decode_responses=True)
        
        task_data = {
            'task': task_name,
            'args': args or [],
            'kwargs': kwargs or {},
            'timestamp': time.time(),
            'enqueued_by': 'api'
        }
        
        r.rpush('dispatcher_tasks_queue', json.dumps(task_data))
        
        logger.info("API", "enqueue_task", "Success", 
                    f"Task {task_name} enqueued successfully")
        
        return {
            'status': 'success',
            'message': f"Task {task_name} enqueued successfully",
            'task_data': task_data
        }
        
    except Exception as e:
        logger.error("API", "enqueue_task", "Failure", 
                     f"Error enqueuing task: {e}")
        return {'status': 'error', 'message': f'Error enqueuing task: {str(e)}'}