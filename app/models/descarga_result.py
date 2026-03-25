from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class DescargaResult:
    class StatusEnum(str, Enum):
        SUCCESS = "Success"
        PENDING = "Pending"
        ERROR = "Error"

    def __init__(
        self,
        org: Optional[str] = None,
        title: Optional[str] = None,
        expediente: Optional[str] = None,
        disposition_date: Optional[str] = None,
        desc: Optional[str] = None,
        file: Optional[str] = None,
        status: Optional["DescargaResult.StatusEnum"] = None,
        message: Optional[str] = None,
        url: Optional[str] = None,
        identificador: Optional[str] = None,
    ):
        self.org = org
        self.title = title
        self.expediente = expediente
        self.disposition_date = disposition_date
        if desc is not None and desc not in ("SI", "NO"):
            raise ValueError("desc must be 'SI' or 'NO'")
        self.desc = desc
        self.file = file
        if status is not None and status not in self.StatusEnum:
            raise ValueError("status must be StatusEnum.SUCCESS, StatusEnum.PENDING or StatusEnum.ERROR")
        self.status = status
        self.message = message
        self.url = url
        self.identificador = identificador

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DescargaResult":
        return cls(
            org=data.get("org"),
            title=data.get("title"),
            expediente=data.get("expediente"),
            disposition_date=data.get("disposition_date"),
            desc=data.get("desc"),
            file=data.get("file"),
            status=data.get("status"),
            message=data.get("message"),
            url=data.get("url"),
            identificador=data.get("identificador"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "org": self.org,
            "title": self.title,
            "expediente": self.expediente,
            "disposition_date": self.disposition_date,
            "desc": self.desc,
            "file": self.file,
            "status": self.status,
            "message": self.message,
            "url": self.url,
            "identificador": self.identificador,
        }