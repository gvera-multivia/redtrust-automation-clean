import asyncio
from api.routes.status import get_full_system_status
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(
    tags=["WebSockets en Tiempo Real"],
    responses={
        500: {"description": "Error en la conexión WebSocket"}
    }
)

@router.websocket("/ws")
async def websocket_dashboard(websocket: WebSocket):
    """
    Conexión WebSocket para monitoreo en tiempo real del estado del sistema.
    
    Proporciona actualizaciones en tiempo real del estado completo del sistema,
    incluyendo workers, tareas en ejecución, métricas de rendimiento y estadísticas.
    
    Datos transmitidos:
    - Workers activos: Estado de todos los workers (disponible, ocupado, offline)
    - Tareas en tiempo real: Pendientes, en ejecución, completadas y fallidas
    - Métricas del sistema: CPU, memoria, disco de cada worker
    - Estadísticas generales: Resumen de actividad y rendimiento
    - Heartbeats: Estado de conectividad de workers
    
    Frecuencia de actualización: Cada 2 segundos
    Formato: JSON estructurado
    
    Ejemplo de conexión JavaScript:
    
    const ws = new WebSocket('ws://localhost:8008/api/ws');
    
    ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('Sistema:', data.stats);
        console.log('Workers:', data.nodes);
        console.log('Tareas:', data.tasks);
    };
    
    ws.onclose = function() {
        console.log('Conexión WebSocket cerrada');
        // Implementar lógica de reconexión
    };
    
    Advertencia: 
    - La conexión se mantiene abierta continuamente
    - Consume ancho de banda con actualizaciones cada 2 segundos
    - Considerar implementar autenticación para uso en producción
    """
    await websocket.accept()
    try:
        while True:
            data = get_full_system_status()
            await websocket.send_json(data)
            await asyncio.sleep(2)  # Actualizar cada 2 segundos
    except WebSocketDisconnect:
        pass
