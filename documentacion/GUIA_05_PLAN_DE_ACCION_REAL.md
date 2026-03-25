# Guía 05: Plan de Acción Real (Roadmap)

Este es el camino crítico para construir el sistema desde cero, dividido por fases lógicas.

---

## Fase 1: Cimientos (Semana 1)
1. **Setup Redis**: Configurar instancia y probar persistencia de listas.
2. **Setup DB**: Crear tablas de `clientes`, `certificates` e `historico`.
3. **API Core**: Crear FastAPI con el endpoint `/enqueue_task` que simplemente haga un `RPUSH` a Redis.
4. **Dockerización (Opcional)**: Dockerizar Redis y la API para consistencia.

---

## Fase 2: Orquestación Inteligente (Semana 2)
1. **Dispatcher V1**: Implementar el loop de lectura de Redis.
2. **Heartbeat System**: Crear un script simple que envíe CPU/RAM a Redis y probar que el Dispatcher lo detecta.
3. **Lógica de Asignación**: Implementar el scoring y la reserva de `task_id`.
4. **Integración Celery**: Configurar Celery para que reciba las órdenes del Dispatcher.

---

## Fase 3: El Brazo Ejecutor (Semana 3)
1. **Setup Windows Worker**: Configurar una VM con Python y las librerías `pywinauto` y `selenium`.
2. **Módulo RedTrust**: Implementar la carga de certificados automatizada.
3. **Primer Robot (Ej. Dehú)**: Crear el flujo de navegación, búsqueda y descarga.
4. **Validación de Identidad**: Implementar `handle_certificate.py` para los popups de Windows.

---

## Fase 4: Inteligencia y Automatización (Semana 4)
1. **Scheduler**: Implementar el proceso cron que consulta la DB y genera tareas.
2. **Queries Complejas**: Escribir los CTEs de SQL que filtran qué clientes deben procesarse cada día.
3. **Logs Centralizados**: Implementar el `LoggerV2` que escriba tanto en archivos locales como en la DB para auditoría.

---

## Fase 5: Robustez y Auditoría (Semana 5)
1. **Validación de PDFs**: Añadir la capa de lectura de metadatos de archivos descargados.
2. **Control de Errores**: Implementar la captura de pantallas en fallos y el sistema de reintentos.
3. **Dashboard de Estado**: (Opcional) Crear una pequeña interfaz web que lea de Redis para ver el estado de los workers.

---

## Puntos Críticos de Vigilancia (Checklist)
- [ ] ¿El Worker verifica en Redis antes de empezar? (Evita duplicidad).
- [ ] ¿El certificado se carga ANTES de abrir el navegador? (Evita fallos de auth).
- [ ] ¿Los logs de los procesos hijos (multiprocessing) llegan al logger principal?
- [ ] ¿El SQL Server tiene índices en `customer_number` y `status_id`? (Optimización).
