from pydantic_settings import BaseSettings

class DatabaseSettings(BaseSettings):
    DB_USER: str = "Xvia-Grupo"
    DB_PASSWORD: str = "Xvia_Grupo_Multivia_20180806"
    DB_SERVER: str = "192.168.184.229"
    DB_NAME: str = "MULTIVIA"
    DB_ENCRYPT: bool = False
    DB_ENABLE_ARITH_ABORT: bool = True

database_settings = DatabaseSettings()

