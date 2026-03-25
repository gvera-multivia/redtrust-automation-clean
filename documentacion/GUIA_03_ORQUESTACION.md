# Guía 03: Orquestación y Dispatcher

El Dispatcher es el árbitro que asegura que las tareas se repartan de forma inteligente y sin colisiones. Esta guía detalla su ciclo de vida.

---

## 1. El Ciclo de Vida del Dispatcher

El Dispatcher (`api/dispatcher.py`) debe correr como un hilo o proceso independiente en el Nodo Maestro. Su flujo es:

1. **Escucha**: Hace un `LPOP` de `dispatcher_tasks_queue`.
2. **Descubrimiento**: Lee todas las claves `worker_status:*` en Redis.
3. **Filtro**: Ignora workers que no han enviado heartbeat en los últimos 30s o que están en estado `Busy`.
4. **Scoring**: Calcula el mejor worker:
   - `Score = (100 - CPU%) * 0.4 + (100 - Mem%) * 0.3 + (Afinidad) * 0.3`.
5. **Reserva**: Escribe en Redis `SET task_assignment:{task_id} {worker_id} NX EX 14400`.
   - El `NX` es crítico: si ya existe, alguien más tomó la tarea.
6. **Publicación**: Envía la tarea a Celery (o el broker elegido) dirigida a una cola general.

---

## 2. El Protocolo de "Aceptación de Tarea" (Workers)

Para evitar que dos workers ejecuten lo mismo (condición de carrera), el Worker debe:
1. Recibir el mensaje de Celery.
2. Antes de abrir el navegador, consultar Redis: `GET task_assignment:{task_id}`.
3. **¿Soy yo el elegido?**:
   - Si el valor coincide con mi `worker_id`: Procedo a ejecutar.
   - Si NO coincide o no existe: Rechazo la tarea (`Reject(requeue=False)`).

---

## 3. Gestión de Progreso y Logs

El Dispatcher y los Workers deben comunicarse mediante Redis para que la API pueda mostrar el estado en tiempo real:

### Registro de Progreso:
- Clave: `task_progress:{task_id}`.
- Contenido: `{"progress": 45, "status": "Downloading PDF", "current_item": "EXP-2023-001"}`.

### Registro de Fin:
- Al terminar (éxito o error), el Worker debe llamar a `register_task_end` en el `RedisManager` para:
  1. Actualizar el `historico_automatizaciones` en SQL Server.
  2. Borrar la reserva `task_assignment:{task_id}`.
  3. Borrar el progreso temporal en Redis.

---

## 4. Manejo de Reintentos y Errores

- **Fallo del Dispatcher**: Si el Dispatcher saca una tarea y muere antes de enviarla a Celery, la tarea se pierde. *Mejora*: Usar `RPOPLPUSH` para mover la tarea a una "cola de procesamiento" temporal.
- **Worker No Disponible**: Si el Dispatcher no encuentra workers vivos, debe hacer `RPUSH` de la tarea de vuelta a la cola de entrada y esperar (ej. 10 segundos).
