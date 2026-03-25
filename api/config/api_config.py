import os
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    load_dotenv(dotenv_path='.env', override=True)
    HOST: str = "0.0.0.0"
    PORT: int = 8008
    ALTAS_INTERVAL: int = 6  # horas
    DESCARGAS_INTERVAL: int = 3  # horas
    REPORTES_INTERVAL: int = 24  # horas
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "logs/api"
    LOG_FILE: str = "api"
    DB_CONFIG: dict = {
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
        "server": os.getenv("DB_SERVER"),
        "database": os.getenv("DB_NAME"),
        "options": {
            "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
            "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
        }
    }
    
settings = Settings()

# Tareas predefinidas para el dashboard
PREDEFINED_TASKS = {
    "robot_altas": {
        "name": "Procesamiento de Altas",
        "description": "Orquesta el proceso completo de altas, incluyendo obtención de datos, asignación de certificados y ejecución en portales.",
        "parameters": {
            "fecha": {"type": "string", "format": "YYYYMMDD", "default": "hoy"},
            "cliente": {"type": "string", "default": "todos"}
        },
        "estimated_duration": 1200
    },
    "robot_descargas": {
        "name": "Descarga de Notificaciones",
        "description": "Automatiza la descarga y validación de notificaciones desde portales oficiales.",
        "parameters": {
            "fecha": {"type": "string", "format": "YYYYMMDD", "default": "hoy"},
            "servicio": {"type": "string", "default": "todos"}
        },
        "estimated_duration": 2000
    },
    "robot_matriculasypuntos": {
        "name": "Consulta de Matrículas y Puntos",
        "description": "Consulta y procesa información de matrículas y puntos de clientes.",
        "parameters": {
            "fecha": {"type": "string", "format": "YYYYMMDD", "default": "hoy"},
            "cliente": {"type": "string", "default": "todos"}
        },
        "estimated_duration": 172800
    }
}

