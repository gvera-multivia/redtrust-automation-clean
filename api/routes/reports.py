from fastapi import APIRouter

router = APIRouter(
    prefix="/reports", 
    tags=["Reportes y Análisis"],
    responses={
        400: {"description": "Parámetros de reporte inválidos"},
        404: {"description": "Datos no encontrados"},
        500: {"description": "Error generando reporte"}
    }
)

@router.post(
    "/generate",
    summary="Generar Reporte Personalizado",
    description="""
    Genera reportes personalizados basados en los datos del sistema de automatización.
    
    ### Tipos de reportes disponibles:
    
    * **Resumen de actividad**: Estadísticas de tareas ejecutadas
    * **Rendimiento de workers**: Métricas de eficiencia de workers
    * **Análisis de descargas**: Volumen y tipo de documentos procesados
    * **Reporte de altas**: Estado y progreso de altas de clientes
    * **Errores y incidencias**: Análisis de fallos y problemas
    
    ### Formatos de salida:
    
    * JSON (por defecto)
    * PDF (próximamente)
    * Excel (próximamente)
    
    ### Períodos disponibles:
    
    * Diario, semanal, mensual, personalizado
    
    ### Ejemplo de uso:
    
    ```json
    {
        "tipo": "resumen_actividad",
        "fecha_inicio": "2024-01-01",
        "fecha_fin": "2024-01-31",
        "formato": "json",
        "incluir_detalle": true
    }
    ```
    """,
    responses={
        201: {
            "description": "Reporte generado exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "message": "Report generated successfully",
                        "report_id": "RPT_20240115_001",
                        "tipo": "resumen_actividad",
                        "fecha_generacion": "2024-01-15T10:30:00Z",
                        "total_registros": 1245,
                        "formato": "json",
                        "url_descarga": "/reports/download/RPT_20240115_001"
                    }
                }
            }
        },
        400: {
            "description": "Parámetros inválidos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Fecha de inicio debe ser anterior a fecha de fin"
                    }
                }
            }
        }
    },
    status_code=201,
    tags=["Generación", "Análisis"]
)
def generate_report():
    # Lógica para generar reportes
    return {"message": "Report generated"}
