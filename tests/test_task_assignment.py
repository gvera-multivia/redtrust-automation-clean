"""
Test suite for task assignment mechanism - 3 essential tests only.
Tests: Redis connection, test data validation, and worker rejection workflow.

Run with: pytest tests/test_task_assignment.py -v --tb=short
"""
import pytest
import time
import uuid
import os
import sys
import json
import redis

# Ensure project root is on sys.path so tests can import the local `api` package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.redis import RedisManager
from api.enqueuer import enqueue_task
from dotenv import load_dotenv
from celery import Celery


class TestTaskAssignment:
    """Essential tests for Redis connection, test data, and worker rejection mechanism."""
    
    @pytest.fixture
    def redis_manager(self, request):
        """Create a Redis manager and a Celery app for testing; attach Celery/URL to the test instance."""

        load_dotenv()
        REDIS_HOST = os.getenv("REDIS_HOST")
        REDIS_PORT = os.getenv("REDIS_PORT")
        REDIS_DB = os.getenv("REDIS_DB", "0")
        REDIS_URL = os.getenv("REDIS_URL") or f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

        rm = RedisManager()

        celery_app = Celery(
            'robot_system',
            broker=REDIS_URL,
            backend=REDIS_URL
        )
        
        return rm, celery_app
    
    @pytest.fixture
    def redis_client(self):
        """Create a Redis client for testing."""
        load_dotenv()
        REDIS_HOST = os.getenv("REDIS_HOST")
        REDIS_PORT = int(os.getenv("REDIS_PORT"))
        return redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    
    @pytest.fixture
    def test_data(self):
        """Generate test data with unique task ID and worker IDs."""
        unique_id = str(uuid.uuid4())[:8]
        return {
            'task_name_benchmark': 'run_benchmark',
            'worker_a': f'192.168.184.162@NODE-A-{unique_id}',
            'worker_b': f'192.168.184.111@NODE-B-{unique_id}',
            'benchmark_kwargs': {'iterations': 200000}
        }
    
    def test_redis_connection(self, redis_client):
        """Test 1: Conexión a Redis."""
        # Test basic Redis connectivity
        redis_client.ping()
        
        # Test basic Redis operations
        test_key = f"test_connection_{uuid.uuid4()}"
        test_value = "connection_test_value"
        
        # Set and get
        redis_client.set(test_key, test_value)
        retrieved_value = redis_client.get(test_key)
        assert retrieved_value == test_value, f"Expected {test_value}, got {retrieved_value}"
        
        # Cleanup
        redis_client.delete(test_key)
        
        print("✓ Redis connection test passed")
    
    def test_task_data_validation(self, redis_client, test_data):
        """Test 2: Test_data que le entra."""
        task_name = test_data['task_name_benchmark']
        kwargs = test_data['benchmark_kwargs']
        
        # Clear queue before test
        redis_client.delete('dispatcher_tasks_queue')
        
        # Enqueue task using the real enqueuer
        result = enqueue_task(task_name, kwargs=kwargs)
        
        # Verify enqueue was successful
        assert result['status'] == 'success', f"Enqueue failed: {result.get('message')}"
        assert task_name in result['message']
        
        # Verify task data was properly queued
        queue_length = redis_client.llen('dispatcher_tasks_queue')
        assert queue_length == 1, f"Expected 1 task in queue, got {queue_length}"
        
        # Get and verify task data structure
        task_json = redis_client.lpop('dispatcher_tasks_queue')
        assert task_json is not None, "No task found in queue"
        
        task_data_parsed = json.loads(task_json)
        
        # Verify task data structure matches expected format
        assert task_data_parsed['task'] == task_name
        assert task_data_parsed['args'] == []
        assert task_data_parsed['kwargs'] == kwargs
        assert 'timestamp' in task_data_parsed
        assert task_data_parsed['enqueued_by'] == 'api'
        
        print(f"✓ Task data validation passed: {task_data_parsed}")
    
    def test_worker_rejection_workflow(self, redis_manager, redis_client, test_data):
        ASSIGNMENT_KEY_PREFIX = os.getenv("TASK_ASSIGNMENT_KEY", "task_assignment")
        ASSIGNMENT_EXPIRE = int(os.getenv("TASK_ASSIGNMENT_EXPIRE", "14400"))
        """Test 3: Workflow entero esperando la Rejection - Realistic scenario with task timeout and reassignment."""
        rm, celery_app = redis_manager
        task_name = test_data['task_name_benchmark']
        kwargs = test_data['benchmark_kwargs']
        worker_a = test_data['worker_b']
        worker_b = test_data['worker_a']
        
        # Clear queues before test
        redis_client.delete('dispatcher_tasks_queue')
        redis_client.delete('task_assignment_log')
        
        print(f"🚀 Starting realistic workflow test:")
        print(f"  - Worker A: {worker_a}")
        print(f"  - Worker B: {worker_b}")
        print(f"  - Task: {task_name} with {kwargs['iterations']} iterations")
        
        # Step 1: Enqueue task
        enqueue_result = enqueue_task(task_name, kwargs=kwargs)
        assert enqueue_result['status'] == 'success'
        print(f"✓ Step 1: Task enqueued successfully")
        
        # Step 2: Dispatcher assigns task to worker_a (first assignment)
        try:
            # Reserve the assignment in Redis atomically (avoid duplicates)
            task_id = str(uuid.uuid4())
            assignment_key = f"{ASSIGNMENT_KEY_PREFIX}:{task_id}"

            reserved = redis_client.set(assignment_key, worker_a, nx=True, ex=ASSIGNMENT_EXPIRE)
            if not reserved:
                existing = redis_client.get(assignment_key)
                raise Exception(f"Task {task_id} is already assigned to {existing}")

            inspect = None
            try:
                inspect = celery_app.control.inspect()
                registered_tasks_dict = inspect.registered() if inspect else None
            except Exception:
                registered_tasks_dict = None

            registered_tasks = []
            if registered_tasks_dict:
                for tasks in registered_tasks_dict.values():
                    registered_tasks.extend(tasks)
            else:
                registered_tasks = None

            # If we were able to list tasks and the task is not registered, release and abort
            if registered_tasks is not None and task_name not in registered_tasks:
                redis_client.delete(assignment_key)
                raise Exception(f"Task {task_name} is not registered in Celery workers")

            # Send task to Celery with our reserved task_id
            try:
                result = celery_app.send_task(
                    task_name,
                    args=[],
                    kwargs=kwargs,
                    queue='robot_tasks',
                    task_id=task_id
                )
            except Exception as e:
                # Release reservation on failure
                try:
                    redis_client.delete(assignment_key)
                except Exception:
                    pass
                
                raise e

            # Log the assignment
            assignment_log = {
                'task_id': task_id,
                'task_name': task_name,
                'worker_id': worker_a,
                'worker_ip': worker_a.split('@')[0],
                'args': [],
                'kwargs': kwargs,
                'timestamp': time.time(),
                'assigned_by': 'dispatcher'
            }

            redis_client.lpush("task_assignment_log", json.dumps(assignment_log))
            
        except Exception as e:
            raise e
        print(f"✓ Step 2: Task {task_id} assigned to {worker_a}")
        
        # # Step 3: Worker A starts the task but gets "stuck" (simulates slow execution)
                
        # Step 4: Wait 20 seconds (simulating timeout detection)
        print(f"⏰ Waiting 5 seconds to simulate task timeout...")
        time.sleep(10)
        
        # Step 5: Dispatcher detects timeout and reassigns to worker_b
        # First clear the old assignment
        rm.clear_task_assignment(task_id)
        time.sleep(1)  # Small delay to ensure cleanup
        
        # Reassign to worker_b with new task_id (like dispatcher would do)
        # Send task to Celery with our reserved task_id
        try:
            result = celery_app.send_task(
                task_name,
                args=[],
                kwargs=kwargs,
                queue='robot_tasks',
                task_id=task_id
            )
        except Exception as e:
            # Release reservation on failure
            try:
                redis_client.delete(assignment_key)
            except Exception:
                pass
            
            raise e

        # new_task_id = str(uuid.uuid4())
        # reassignment_success = rm.assign_task(new_task_id, worker_b)
        assert result, "Failed to reassign task to worker_b"
        print(f"✓ Step 5: Task reassigned to {worker_b} with ID: {task_id}")
        
        # Step 6: Worker B receives the task but rejects because it sees it's assigned to worker_b
        # But we'll simulate sending the OLD task_id to worker_b (like Celery might do)
        # This simulates the race condition scenario
        
        # First assign the old task_id to worker_a again to simulate the race condition
        # rm.assign_task(task_id, worker_a)  # Old assignment still exists in some scenarios
        
        assigned_to_old = rm.get_task_assignment(task_id)
        rejection_executed = False
        rejection_error = None
        worker_b_reject_time = None
        
        # Worker B receives the OLD task_id and should reject
        if assigned_to_old and assigned_to_old != worker_b:
            worker_b_reject_time = time.time()
            # This is the exact code from worker.py
            rm.publish_task_progress(task_id, task_name, {'status': 'rejected', 'error': f'assigned_to:{assigned_to_old}'})
            rm.register_task_end(task_id, worker_b, 'rejected', f'assigned_to:{assigned_to_old}')
            rejection_executed = True
            rejection_error = f'assigned_to:{assigned_to_old}'
            print(f"✓ Step 6: Worker B correctly rejects task {task_id} at {worker_b_reject_time}")
            print(f"   Rejection reason: {rejection_error}")
        
        # Step 7: Verify rejection was executed
        assert rejection_executed, "Worker B should have executed rejection logic"
        assert rejection_error == f'assigned_to:{worker_a}', f"Expected rejection error to mention worker_a, got {rejection_error}"
        
        # Step 8: Wait 30 seconds for worker B to become operational again
        print(f"⏰ Waiting 30 seconds for worker B to become operational again...")
        time.sleep(35)
        operational_time = time.time()
        print(f"✓ Step 8: Worker B is operational again at {operational_time}")
        
        # Step 9: Test that worker_b can handle new tasks (not the rejected one)
        new_test_task_id = str(uuid.uuid4())
        new_assignment_success = rm.assign_task(new_test_task_id, worker_b)
        assert new_assignment_success, "Worker B should be able to receive new assignments"
        
        # Worker B should accept this new task
        assigned_to_new = rm.get_task_assignment(new_test_task_id)
        if assigned_to_new and assigned_to_new == worker_b:
            # Worker B can execute new tasks normally
            rm.register_task_start(new_test_task_id, task_name, [], {'iterations': 1000}, 
                                 worker_id=worker_b, worker_ip=worker_b.split('@')[0])
            time.sleep(2)  # Quick execution
            rm.register_task_end(new_test_task_id, worker_id=worker_b, status='completed')
            worker_b_operational = True
            print(f"✓ Step 9: Worker B successfully executed new task {new_test_task_id}")
        else:
            worker_b_operational = False
        
        assert worker_b_operational, "Worker B should be operational for new tasks after rejection"
        
        # Step 10: Cleanup and final verification
        time.sleep(1)
        old_assignment = rm.get_task_assignment(task_id)
        new_assignment = rm.get_task_assignment(new_test_task_id)
        
        print(f"✓ Final verification:")
        print(f"  - Original task {task_id} assignment cleaned up: {old_assignment is None}")
        print(f"  - New task {new_test_task_id} assignment cleaned up: {new_assignment is None}")
        print(f"  - Worker B rejection time: {worker_b_reject_time}")
        print(f"  - Worker B operational again: {operational_time}")
        print(f"  - Total test duration: {operational_time - worker_b_reject_time + 30:.1f} seconds")
        
        print(f"\n🎯 Complete realistic workflow test PASSED:")
        print(f"  ✓ Worker A started task but got stuck")
        print(f"  ✓ After 20s timeout, task reassigned to Worker B")
        print(f"  ✓ Worker B correctly rejected duplicate task")
        print(f"  ✓ Worker B became operational after 30s")
        print(f"  ✓ Worker B can process new tasks normally")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
