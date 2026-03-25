from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class Sede(BaseModel):
    sede: str
    sede_id: int
    link: str
    n_emails: int
    emails: str
    certificate_id: int
    created_at: datetime


class Alta(BaseModel):
    tipo_cliente: str
    certificate_id: int
    name: str
    manager: str
    recipient_name: str
    provincia: str
    poblacion: str
    codigo_postal: str
    calle: str
    CIF: str
    NIF: str
    state: str
    valid_from: datetime
    valid_up_to: datetime
    sedes: List[Sede] = Field(default_factory=list)