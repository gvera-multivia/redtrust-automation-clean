from .base import ErrorBase

class ErrorRedtrust(ErrorBase):
    LoginError = staticmethod(lambda e: RuntimeError(f"⚠️ Error logging into Redtrust: {e}"))
    CertificateNotFound = staticmethod(lambda cert_id: RuntimeError(f"⚠️ Certificate not found: {cert_id}"))
    PermissionDenied = staticmethod(lambda operation: RuntimeError(f"⚠️ Permission denied for operation: {operation}"))
    CertificateLoad = staticmethod(lambda cert_id: RuntimeError(f"⚠️ Error loading certificate {cert_id}."))
