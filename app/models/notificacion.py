import datetime
from typing import List, Optional
from pydantic import BaseModel, EmailStr

class Notificacion(BaseModel):
    message_key: str | int
    date: datetime.datetime | str  # Consider using datetime if you want to parse/validate dates
    sede: str
    status: str
    mail: EmailStr
    asunto: str
    expediente: Optional[str] = None
    org: Optional[str] = None
    body_date: Optional[str] = None
    identificador: Optional[str] = None
    link: Optional[str] = None


class Descarga(BaseModel):
    client_id: int
    recipient_name: str
    servicio: List[str]
    nif: str
    cif: Optional[str] = None
    tipo_cliente: str
    client_name: Optional[str] = None
    aviso_especial: Optional[str] = None
    notificaciones: dict[str, List[Notificacion]]
		
