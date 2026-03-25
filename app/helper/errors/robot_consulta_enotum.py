from .base import ErrorBase

class ErrorRobotConsultaEnotum(ErrorBase):
    Fetch = staticmethod(lambda e: f"⚠️ Error fetching notifications: {e}")
    NoResult = staticmethod(lambda notification_id: f"⚠️ No result returned from portal robot for task {notification_id}")
    Error = staticmethod(lambda notification_id, e: f"⚠️ Error in portal robot for task {notification_id}: {e}")
    CertificateLoad = staticmethod(lambda cliente: f"⚠️ Error loading redtrust certificate for cliente {cliente}")
    CertificateHandlerError = staticmethod(lambda notification_id: f"⚠️ Error in certificate handler for task {notification_id}")
    UnknownSede = staticmethod(lambda sede: f"⚠️ Unknown sede for downloads: {sede}")
    RobotNotInitialized = staticmethod(lambda sede: f"⚠️ Robot not initialized for sede: {sede}")
    MissingServicio = staticmethod(lambda notification: f"⚠️ Missing servicio in notification: {notification}")
    MissingExpediente = staticmethod(lambda notification: f"⚠️ Missing expediente in notification: {notification}")
    InvalidServicio = staticmethod(lambda notification: f"⚠️ Invalid servicio: {notification.get('servicio', 'Unknown')}. Skipping task ID {notification['message_id']}")
    MissingKey = staticmethod(lambda e: f"⚠️ Missing key in notification: {e}")
    ProcessFile = staticmethod(lambda message_id, processed_results: f"Error al procesar archivos para {message_id}: {processed_results}")
    class ErrorAvisoEspecial(ErrorBase):
        def __init__(self, cliente, aviso):
            super().__init__(f"⚠️ Descargas para cliente {cliente} no realizadas por aviso especial: {aviso}.")
            self.cliente = cliente
            self.aviso = aviso
    NoNotifications = staticmethod(lambda notification_id: f"No notifications to process for {notification_id}")
    LoginError = staticmethod(lambda sede, e: f"⚠️ Login error for sede {sede}: {e}")

