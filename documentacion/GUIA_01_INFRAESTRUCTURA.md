# Guía 01: Infraestructura y Entorno

Esta guía detalla los cimientos necesarios para replicar el sistema RedTrust Automation. Sin estos componentes correctamente configurados, la lógica superior no podrá funcionar.

---

## 1. El Almacén de Estado: Redis

Redis no se usa solo como caché, sino como un **Bus de Estado en Tiempo Real**. Se requieren tres áreas lógicas (pueden ser bases de datos separadas en Redis o prefijos de claves):

### A. Cola de Entrada (`dispatcher_tasks_queue`)
- **Tipo**: Lista (List).
- **Rol**: Almacena los JSON de tareas pendientes que aún no han sido procesadas por el dispatcher.
- **Operación**: `RPUSH` (productor) y `LPOP` (consumidor).

### B. Registro de Salud (`worker_status:*`)
- **Tipo**: String (JSON).
- **Rol**: Almacena el heartbeat de cada worker (CPU, RAM, Estado).
- **TTL**: Muy importante (ej. 30 segundos) para detectar caídas automáticamente.

### C. Sistema de Reservas (`task_assignment:*`)
- **Tipo**: String.
- **Rol**: Mapea un `task_id` a un `worker_id` específico antes de que Celery lo reciba.
- **TTL**: Suficiente para la duración máxima de una tarea (ej. 4 horas).

---

## 2. El Cerebro de Datos: SQL Server

El sistema depende de una base de datos relacional robusta (SQL Server) con el siguiente esquema lógico mínimo:

### Tablas Críticas:
1.  **`info.BeneficiarioBonos`**: Almacena los contratos activos, fechas de fin y situación de cobro. Es el filtro principal de "quién es apto".
2.  **`clientes`**: Datos maestros (NIF, CIF, Nombre, Provincia, Estado de baja).
3.  **`certificates_managements_`**: Estado de los certificados digitales (Vigencia, Recipient Name). Esencial para la automatización RedTrust.
4.  **`emails_messages`**: Registro de notificaciones recibidas (Metadata, Body HTML, Status ID).
5.  **`historico_automatizaciones`**: Log de cada ejecución (ID, Robot, Status, Mensaje de error).
6.  **`automations_assignment_log`**: Histórico de qué worker tomó qué tarea (para auditoría y scoring).

---

## 3. Entorno Gráfico (Execution Environment)

A diferencia de los microservicios backend estándar, los **Workers** requieren:
- **Windows OS**: Debido a la dependencia de RedTrust Agent (Desktop App) y popup nativos de certificados.
- **Chrome/Chromedriver**: Alineado con la versión del navegador.
- **RedTrust Agent instalado**: Debe estar corriendo en la bandeja del sistema (System Tray).
- **Acceso a Red (Network Path)**: Para guardar logs centralizados y archivos descargados que luego se validarán.

---

## 4. Variables de Entorno Clave

Configurar un archivo `.env` o secreto con:
- `REDIS_HOST`, `REDIS_PORT`: Conexión al bus.
- `DB_SERVER`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`: Conexión a SQL Server.
- `REDTRUST_USERNAME`, `REDTRUST_PASSWORD`: Credenciales para loguearse en el agente.
- `DOWNLOAD_DIR`: Ruta absoluta donde los robots dejarán los PDFs.
