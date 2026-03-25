class ExtractionResponse:
    def __init__(self, client_name: str, expediente: str | None, identificador: str, link: str, org: str = None, date: str = None):
        self.client_name = client_name
        self.expediente = expediente
        self.org = org
        self.date = date
        self.identificador = identificador
        self.link = link

    def to_dict(self):
        return {
            "client_name": self.client_name,
            "expediente": self.expediente,
            "org": self.org,
            "date": self.date,
            "identificador": self.identificador,
            "link": self.link,
        }