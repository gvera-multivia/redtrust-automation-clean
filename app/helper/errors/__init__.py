from .robot_altas import ErrorRobotAltas
from .robot_descargas import ErrorRobotDescargas
from .robot_matriculas import ErrorRobotMatriculasYPuntos
from .database import ErrorDatabaseManager
from .webdriver import ErrorWebDriver
from .redtrust import ErrorRedtrust
from .handle_cert import ErrorHandleCertificate
from .base import ErrorBase

__all__ = [
    "ErrorBase",
    "ErrorRobotAltas",
    "ErrorRobotDescargas",
    "ErrorRobotMatriculasYPuntos",
    "ErrorDatabaseManager",
    "ErrorWebDriver",
    "ErrorRedtrust",
    "ErrorHandleCertificate",
]
