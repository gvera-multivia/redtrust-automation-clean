# THIRD PARTY PACKAGES
from pydantic import BaseModel, Field, validator # type: ignore
from typing import Optional
from uuid import UUID


class RobotExecutionModel(BaseModel):
    execution_id: UUID
    cliente: int
    nif: Optional[str] = None
    cif: Optional[str] = None
    tipo_cliente: Optional[str] = None
    robot_name: str
    date: str 
    status: str
    sede: str
    result_robot: Optional[str] = None
    result_certificate: Optional[bool] = None
    execution_message: Optional[str] = None
    updated_by_user_id: int
    updated_by_user_name: str

    # DESCARGAS
    notification_id: Optional[str] = None
    message_id: Optional[str] = None
    fecha_descarga: Optional[str] = None
    expediente: Optional[str] = None
    prevDescargado: Optional[str] = Field(default=None)

    # ALTAS
    filename: Optional[str] = None
    action: Optional[str] = None
    emails: Optional[str] = None
    downloads: Optional[bool] = None

    # INFORMES DGT
    matriculas: Optional[int] = None
    puntos: Optional[int] = None

    @validator('status')
    def validate_status(cls, v):
        allowed = {'completed', 'pending', 'error'}
        if v not in allowed:
            raise ValueError(f'status must be one of {allowed}')
        return v

    @validator('prevDescargado')
    def validate_prevDescargado(cls, v):
        if v is not None and v not in {'SI', 'NO'}:
            raise ValueError("prevDescargado must be 'SI', 'NO', or None")
        return v
