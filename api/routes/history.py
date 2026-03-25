# -*- coding: utf-8 -*-
from http.client import HTTPException
from uuid import uuid4
from fastapi import APIRouter, Request
import os
from dotenv import load_dotenv
from app.helper.loggerV2 import LoggerV2
from database.database_manager import DatabaseManager  # Adjust import as needed
from api.config.api_config import settings
from typing import List, Dict, Any

router = APIRouter(
    prefix="/history", 
    tags=["Historial y Auditoría"],
    responses={
        400: {"description": "Parámetros de fecha inválidos"},
        404: {"description": "No se encontraron registros"},
        500: {"description": "Error interno del servidor"}
    }
)
logger = LoggerV2(
    module="API",
    class_name=__name__, 
    log_dir=settings.LOG_DIR, 
    filename=settings.LOG_FILE
)


@router.get(
    "/by-date",
    summary="Obtener Historial por Fecha",
    description="""
    Obtiene el historial completo de actividades y procesos ejecutados en una fecha específica.
    
    ### Información del historial:
    
    * **Tareas ejecutadas**: Todas las automatizaciones ejecutadas
    * **Resultados**: Éxitos, errores y advertencias
    * **Tiempos de ejecución**: Duración de cada proceso
    * **Usuarios y workers**: Quién ejecutó cada tarea
    * **Detalles de error**: Información de diagnóstico
    
    ### Tipos de actividades registradas:
    
    * Automatizaciones de altas
    * Procesos de descarga de documentos
    * Consultas a sistemas externos
    * Generación de reportes
    * Mantenimiento del sistema
    
    ### Parámetro requerido:
    
    * **fecha_descarga**: Fecha a consultar en formato YYYY-MM-DD
    
    ### Casos de uso:
    
    * Auditoría de actividades del sistema
    * Diagnóstico de problemas en fecha específica
    * Análisis de rendimiento histórico
    * Verificación de ejecuciones pasadas
    
    ### Ejemplo de consulta:
    
    `GET /api/history/by-date?fecha_descarga=2024-01-15`
    """,
    responses={
        200: {
            "description": "Historial obtenido exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "HIST_001",
                                "fecha_ejecucion": "2024-01-15T09:30:00Z",
                                "tipo_tarea": "robot_descargas",
                                "estado": "completado",
                                "duracion_segundos": 1845,
                                "worker_id": "worker@hostname",
                                "cliente": "CLI001",
                                "documentos_procesados": 15,
                                "errores": 0,
                                "detalles": "Descarga exitosa de 15 documentos"
                            },
                            {
                                "id": "HIST_002",
                                "fecha_ejecucion": "2024-01-15T14:20:00Z",
                                "tipo_tarea": "robot_altas",
                                "estado": "fallido",
                                "duracion_segundos": 320,
                                "worker_id": "worker@hostname",
                                "cliente": "CLI002",
                                "error_mensaje": "Conexión timeout con sistema externo"
                            }
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Formato de fecha inválido",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Invalid date format. Use YYYY-MM-DD"
                    }
                }
            }
        },
        404: {
            "description": "No se encontraron registros para la fecha especificada",
            "content": {
                "application/json": {
                    "example": {
                        "data": [],
                        "message": "No records found for the specified date"
                    }
                }
            }
        },
        500: {
            "description": "Error interno del servidor",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Internal Server Error"
                    }
                }
            }
        }
    },
    tags=["Consulta", "Auditoría"]
)
async def get_history_by_date(
    fecha_descarga: str,
):
    try:
        load_dotenv(dotenv_path='.env', override=True)
        db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        execution_id = uuid4()
        db_manager = DatabaseManager(db_config=db_config, date=fecha_descarga, execution_id=execution_id,module="API", filename=settings.LOG_FILE)
        results: List[Dict[str, Any]] = db_manager.retrieve_historico(fecha_descarga)
        return {"data": results}
    except Exception as e:
        logger.error("API", "HistoryEndpoint", "Failure", str(e))
        raise HTTPException(status_code=500, detail="Internal Server Error")