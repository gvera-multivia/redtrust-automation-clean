from .base import ErrorBase

class ErrorHandleCertificate(ErrorBase):
    Default = staticmethod(lambda e: RuntimeError(f"⚠️ Error al manejar el certificado: {e}"))
    Procesado = staticmethod(lambda e: RuntimeError(f"⚠️ Error al procesar el certificado: {e}"))
    Contenedor = staticmethod(lambda: RuntimeError("⚠️ Contenedor de elementos de certificados cargados no encontrada."))
    Ventana = staticmethod(lambda: RuntimeError("⚠️ Ventana de selección de certificado no encontrada."))
