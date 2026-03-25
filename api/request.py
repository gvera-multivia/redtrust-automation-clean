import json
import paramiko
import redis
import argparse
import requests


def request():
    url = "http://localhost:8008/api/enqueue_task"
    payload = {
        "task_name": "run_benchmark",
        "kwargs": {"iterations": 10000}
    }

    response = requests.post(url, json=payload)
    print("Status code:", response.status_code)
    print("Response:", response.text)

    
def inspect():
    from celery import Celery

    app = Celery('robot_system', broker='redis://localhost:6380/0', backend='redis://localhost:6380/0')

    inspect = app.control.inspect()

    # Get list of active workers (nodes)
    active_nodes = inspect.ping()
    if not active_nodes:
        print("No active workers found.")
        return
    
    for node, status in active_nodes.items():
        print(f"Node: {node}, Status: {status}")

    # Get detailed stats for each node
    stats = inspect.stats()
    for stats_key, stats_value in stats.items():
        print(f"Node: {stats_key}")
        for key, value in stats_value.items():
            print(f"  {key}: {value}")

    # Get registered tasks per node
    # registered = inspect.registered()
    # for node, tasks in registered.items():
    #     print(f"Node: {node}, Registered Tasks: {len(tasks)}")
    #     for task in tasks:
    #         print(f"  Task: {task}")



def vaciar_cola(redis_host, redis_port, nombre_cola):
    # Conectar a Redis
    r = redis.Redis(host=redis_host, port=redis_port)

    # Borrar la cola (key) específica
    resultado = r.delete(nombre_cola)

    if resultado == 1:
        print(f"La cola '{nombre_cola}' fue vaciada correctamente.")
    else:
        print(f"La cola '{nombre_cola}' no existía o ya estaba vacía.")

def kill_task(worker_ip, pid=None, username='Maria Miró', password='1234'):
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(str(worker_ip), username=username, password=password)


        if pid:
            # Matar un PID específico
            cmd = f'taskkill /PID {pid} /F'
            _, stdout, _ = client.exec_command(cmd)
            output = stdout.read().decode(errors='ignore').strip()
            client.close()
            if any(word in output.upper() for word in ["SUCCESS", "CORRECTO", "TERMINADO", "COMPLETED"]):
                print("API", "StatusEndpoint", "Success", f"✅ Proceso con PID {pid} en {worker_ip} ha sido terminado.")
                return {"success": True, "message": f"✅ Proceso con PID {pid} en {worker_ip} ha sido terminado."}
            else:
                print("API", "StatusEndpoint", "Failure", f"⚠️ Error al matar el proceso con PID {pid} en {worker_ip}: {output}")
        else:
            # Listar procesos python o celery
            # cmd = 'cmd.exe /c "tasklist | findstr /I \"python celery\""'
            cmd = 'powershell.exe "Get-Process | Where-Object { $_.ProcessName -match \'celery|python\' } | Select-Object ProcessName, Id"'
            _, stdout, _ = client.exec_command(cmd)
            output = stdout.read().decode(errors='ignore').strip()
            print(output)
            client.close()

            if not output:
                print("API", "StatusEndpoint", "Failure", f"⚠️ No se encontraron procesos python/celery en {worker_ip}.")

            procesos = {}
            for line in output.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    nombre_proceso = parts[0].split('.')[0]
                    pid_proceso = int(parts[1])
                    procesos.setdefault(nombre_proceso, []).append(pid_proceso)

            print("API", "StatusEndpoint", "Pending", f"Procesos encontrados: {procesos}")

            celery_pid = procesos.get('celery', [None])[0]
            if not celery_pid:
                print("API", "StatusEndpoint", "Failure", f"⚠️ No se encontró proceso celery para matar en {worker_ip}.")

            # Matar el proceso celery
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            client.connect(worker_ip, username=username, password=password)
            kill_cmd = f'powershell.exe "Stop-Process -Id {celery_pid} -Force"'
            _, stdout_kill, _ = client.exec_command(kill_cmd)
            result = stdout_kill.read().decode(errors='ignore').strip()
            client.close()
            if any(word in result.upper() for word in ["SUCCESS", "CORRECTO", "TERMINADO", "COMPLETED"]):
                print("API", "StatusEndpoint", "Success", f"✅ Proceso celery con PID {celery_pid} en {worker_ip} ha sido terminado.")
                return {"success": True, "message": f"✅ Proceso celery con PID {celery_pid} en {worker_ip} ha sido terminado."}
            else:
                print("API", "StatusEndpoint", "Failure", f"⚠️ Error al matar el proceso celery con PID {celery_pid} en {worker_ip}: {result}")

    except paramiko.AuthenticationException:
        print("API", "StatusEndpoint", "Failure", f"Error de autenticación en {worker_ip} con usuario {username}")
    except Exception as e:
        print("API", "StatusEndpoint", "Failure", f"Error al conectar o ejecutar comandos en {worker_ip}: {e}")
     
        
def listar_task_ids(redis_host, redis_port, nombre_cola):
    r = redis.Redis(host=redis_host, port=redis_port)
    tareas = r.lrange(nombre_cola, 0, -1)
    for tarea_bytes in tareas:
        tarea_str = tarea_bytes.decode('utf-8')
        try:
            tarea_json = json.loads(tarea_str)
            task_id = tarea_json.get("id") or tarea_json.get("task_id")
            if task_id:
                print(task_id)
        except json.JSONDecodeError:
            continue

def get_celery_tasks():
    from celery import Celery

    app = Celery('robot_system', broker='redis://localhost:6380/0', backend='redis://localhost:6380/0')

    inspect = app.control.inspect()
    registered = inspect.registered()
    for node, tasks in registered.items():
        print(f"Node: {node}, Registered Tasks: {len(tasks)}")
        for task in tasks:
            print(f"  Task: {task}")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Celery utility script")
    parser.add_argument('--request', action='store_true', help='Send a request to enqueue a task')
    parser.add_argument('--inspect', action='store_true', help='Inspect celery workers')
    parser.add_argument('--kill', action='store_true', help='Kill a celery worker process')
    parser.add_argument('--emptyqueue', nargs=3, metavar=('REDIS_HOST', 'REDIS_PORT', 'QUEUE_NAME'), help='Empty a Redis queue')
    parser.add_argument('--list-tasks', action='store_true', help='List all registered Celery tasks')

    args = parser.parse_args()

    if args.request:
        request()
    elif args.inspect:
        inspect()
    elif args.kill:
        kill_task(
            worker_ip='192.168.184.133',
            pid=None,  # You can specify a PID if needed
            username='Maria Miró',
            password='1234'            
        )
    elif args.emptyqueue:
        redis_host, redis_port, queue_name = args.emptyqueue
        vaciar_cola(redis_host, int(redis_port), queue_name)
    elif args.list_tasks:
        get_celery_tasks()
    else:
        parser.print_help()