from .base import ErrorBase

class ErrorRobotAltas(ErrorBase):
    """
    Errors specific to RobotAltas
    """
    NoResult = staticmethod(lambda cliente: RuntimeError(f"⚠️ No result from portal robot for task {cliente}"))
    Error = staticmethod(lambda cliente, e: RuntimeError(f"⚠️ Error in portal robot for task {cliente} : {e}"))
    CertificateHandlerError = staticmethod(lambda sede_id: RuntimeError(f"⚠️ Error in certificate handler for task {sede_id}"))
    ErrorUpdateStatus = staticmethod(lambda e: RuntimeError(f"⚠️ Error updating alta status: {e}"))
