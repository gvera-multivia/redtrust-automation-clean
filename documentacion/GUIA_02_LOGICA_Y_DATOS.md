# Guía 02: Lógica de Negocio y Motor de Datos

El sistema no procesa "todo lo que llega", sino que aplica un filtrado quirúrgico en la base de datos. Esta guía explica cómo implementar ese "Cerebro SQL".

---

## 1. El Scheduler: El Motor de Disparo

El componente `api/scheduler.py` debe ser un proceso ligero que:
1. Se despierte cada minuto.
2. Compare la hora actual con su lista de tareas programadas.
3. Para cada tarea (ej. Descargas, Altas, Matrículas), ejecute un **Query de Prospección**.

### Pseudocódigo del Scheduler:
```python
def run_loop():
    while True:
        now = datetime.now()
        for hour, minute, task_func in schedule:
            if now.hour == hour and now.minute == minute:
                task_func() # Lanza la consulta a la DB
        sleep(60)
```

---

## 2. Las Queries de Prospección (El Corazón del Sistema)

Las consultas SQL (ej. `database/descargas/queries/getNotificacionesPendientes.py`) deben usar **CTEs (Common Table Expressions)** para filtrar la información en capas:

### Capa A: Filtro de Clientes Aptos
- Buscar en `BeneficiarioBonos` donde `fechafin > GETDATE()`.
- Situación IN ('COBRADO', 'PENDIENTE VT', etc.).
- `baja = 0` en tabla clientes.

### Capa B: Filtro de Disponibilidad Técnica
- El certificado del cliente debe estar `Vigente` en `certificates_managements_`.
- El certificado debe ser válido para la fecha actual (`valid_up_to >= GETDATE()`).

### Capa C: Filtro de Pendientes
- Unir con `emails_messages` donde `status_id = 1` (Pendiente).
- Importante: Solo seleccionar notificaciones de las sedes (Dehú, e-Notum, DGT) que el sistema soporta actualmente.

---

## 3. Normalización del Body (Pre-procesamiento)

Antes de enviar la tarea al robot, el sistema (en `app/robot_descargas.py` o similar) debe pre-procesar el `body_html` de la notificación para extraer:
1. **El Número de Expediente**: Es lo que el robot buscará en el portal.
2. **El Organismo**: Para decidir si aplica algún "Aviso Especial" (ej. "no descargar seguridad social").

---

## 4. Gestión de Batches (Lotes)

Para evitar saturar a un solo worker o crear tareas infinitas:
- El Scheduler debe agrupar los resultados de la DB en lotes (ej. 150 notificaciones).
- Cada lote se convierte en una sola tarea en Redis.
- Esto optimiza el tiempo de carga del certificado (se carga una vez para 150 descargas).
