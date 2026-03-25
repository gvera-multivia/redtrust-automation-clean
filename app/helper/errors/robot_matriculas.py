from .base import ErrorBase

class ErrorRobotMatriculasYPuntos(ErrorBase):
    NoResult = staticmethod(lambda matricula: RuntimeError(f"⚠️ No result from portal robot for task {matricula}"))
    Error = staticmethod(lambda matricula, e: RuntimeError(f"⚠️ Error in portal robot for task {matricula}: {e}"))
    CertificateHandlerError =staticmethod(lambda matricula: RuntimeError(f"⚠️ Error in certificate handler for task {matricula}"))
    ErrorUpdateStatus = staticmethod(lambda e: RuntimeError(f"⚠️ Error updating matricula status: {e}"))
