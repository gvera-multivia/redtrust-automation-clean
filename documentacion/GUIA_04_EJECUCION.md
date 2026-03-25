# Guía 04: Ejecución y Robots (Workers)

Los Workers son el brazo ejecutor. Combinan automatización GUI (Desktop) con automatización Web (Selenium).

---

## 1. Anatomía de un Worker

Cada Worker (`api/worker.py`) corre sobre Windows y mantiene:
- Un cliente Celery escuchando tareas.
- Un hilo de **Heartbeat** enviando métricas a Redis cada 10s.
- Un pool de ejecución (normalmente concurrencia 1, ya que los portales web y RedTrust suelen bloquear múltiples sesiones simultáneas).

---

## 2. El Puente de Certificados (RedTrust)

Antes de cualquier navegación, el robot debe asegurar la identidad digital:
1. **RedTrust Manager (`app/redtrust/redtrust_manager.py`)**:
   - Interactúa con el agente de escritorio RedTrust usando `pywinauto`.
   - Hace click derecho en el icono de la bandeja -> Seleccionar Certificado.
   - Introduce el ID del certificado (NIF o ID interno) en el buscador de RedTrust.
   - Presiona 'Aceptar' para cargar el certificado en el almacén de Windows.

2. **Handle Certificate (`app/robot/handle_certificate.py`)**:
   - Durante la navegación Selenium, si aparece el popup nativo de Windows para elegir certificado, este componente toma el control.
   - Usa `pywinauto` para detectar la ventana de "Seleccionar Certificado" de Chrome y presiona 'Enter'.

---

## 3. Lógica del Robot de Portal (Selenium)

Los robots deben seguir un patrón robusto:
1. **Setup**: Iniciar Chromedriver con el perfil de usuario o extensiones necesarias.
2. **Login**: Navegar al portal. La mayoría usará el certificado ya cargado (SSO/Clave).
3. **Acción**:
   - Buscar por expediente/identificador.
   - Validar que el elemento está presente (`WebDriverWait`).
   - Manejar errores comunes (Timeout, portal caído, sesión expirada).
4. **Descarga**: Guardar el archivo en una ruta predecible.
5. **Validación**: Leer el PDF (vía `PyMuPDF` o similar) para confirmar que no es un error del portal disfrazado de PDF.

---

## 4. Reporte de Resultados y Limpieza

Al finalizar el ciclo del robot:
- **Éxito**: Mover archivos a la carpeta final y actualizar la DB con el nombre del archivo.
- **Error**: Tomar una captura de pantalla (`driver.save_screenshot()`) para depuración.
- **Cleanup**: Cerrar el navegador (`driver.quit()`) y liberar el certificado en RedTrust si es necesario.
