from .class_map import CLASSES_IN_APP

class Error(Exception):
    """
    Custom Exception class that also collects and organizes error log messages by class/module.
    Usage:
        Error.log_error(class_name, message)
        Error.get_errors_by_class(class_name)
        Error.get_all_errors()
    """
    # Dictionary to store error messages for each class
    _errors_by_class = {class_name: [] for class_name in CLASSES_IN_APP.keys()}

    def __init__(self):
        # Generic error templates
        self.ErrorXpathElemento = lambda xpath: f"Error encontrando elemento {xpath}"
        self.ErrorElementError = "⚠️ Error al esperar el elemento de error"
        self.ErrorLoginSede = lambda sede: f"Error en el Login en {sede}"
        self.ErrorDarAltaSede = lambda portal_link, e: f"⚠️ Error en darse de alta en {portal_link}: {e}"
        self.ErrorNifCliente = lambda nif_cif_cliente, nif_encontrado: f"⚠️ Error comprobando NIF/CIF {nif_cif_cliente} con el encontrando en la sede {nif_encontrado}"
        self.ErrrDatosContacto = "⚠️ Error rellenando los datos de contacto"
        self.ErrorVerificandoAlta = "⚠️ Error verificando alta"
        self.ErrorDescargaEnSede = lambda portal_link, e: f"⚠️ Error en la descarga en {portal_link}: {e}"

        # Redtrust errors
        class ErrorRedtrust:
            ErrorSeleccionandoCertificado = staticmethod(lambda certificate_id, e: f"⚠️ Error selecting certificate {certificate_id}: {e}")
            ErrorIcon = staticmethod(lambda e: f"⚠️ Error locating RedTrust icon: {e}")
            ErrorAutomation = staticmethod(lambda e: f"⚠️ Error automating RedTrust: {e}")
        self.ErrorRedtrust = ErrorRedtrust

        # DatabaseManager errors
        class ErrorDatabaseManager:
            ErrorConexion = staticmethod(lambda e: f"Error connecting to the database: {e}")
            ErrorHistorico = staticmethod(lambda e: f"Error updating descarga en el historico: {e}")
            class ErrorFetch:
                Descargas = staticmethod(lambda e: f"Error fetching descargas: {e}")
                Altas = staticmethod(lambda e: f"Error fetching altas: {e}")
                MatriculasYPuntos = staticmethod(lambda e: f"Error fetching clientes en DEV: {e}")
            class ErrorUpdate:
                Descargas = staticmethod(lambda message_id, sede, e: f"Error actualizando descarga {message_id} en {sede}: {e}")
                Altas = staticmethod(lambda sede, cliente, e: f"Error actualizando altas en {sede} para {cliente}: {e}")
                Matriculas = staticmethod(lambda cliente, e: f"Error actualizando matriculas para cliente {cliente}: {e}")
                Puntos = staticmethod(lambda cliente, e: f"Error actualizando puntos para cliente {cliente}: {e}")
        self.ErrorDatabaseManager = ErrorDatabaseManager

        # HandleCertificate errors
        class ErrorHandleCertificate:
            Default = staticmethod(lambda e: f"⚠️ Error al manejar el certificado: {e}")
            Procesado = staticmethod(lambda e: f"⚠️ Error al procesar el certificado: {e}")
            Contenedor = "⚠️ Contenedor de elementos de certificados cargados no encontrada."
            Ventana = "⚠️ Ventana de selección de certificado no encontrada."
        self.ErrorHandleCertificate = ErrorHandleCertificate

        # WebDriver errors
        class ErrorWebDriver:
            Load = staticmethod(lambda portal_link, e: f"❌ Error al cargar {portal_link}: {e}")
            Setup = staticmethod(lambda e: f"Erron el setup del Webdriver: {e}")
        self.ErrorWebDriver = ErrorWebDriver

        # RobotDescargas errors
        class ErrorRobotDescargas:
            NoResult = "⚠️ No result returned from portal robot for task {notification_id}"
            Error = "⚠️ Error in portal robot for task {notification_id}: {e}"
            CertificateHandlerError = "⚠️ Error in certificate handler for task {notification_id}"
            UnknownSede = "⚠️ Unknown sede for downloads: {notification['sede']}"
            RobotNotInitialized = "⚠️ Robot not initialized for sede: {sede}"
            MissingServicio = "⚠️ Missing servicio in notification: {notification}"
            InvalidServicio = "⚠️ Invalid servicio: {notification.get('servicio', 'Unknown')}. Skipping task ID {notification['message_id']}"
            MissingKey = "⚠️ Missing key in notification: {e}"
        self.ErrorRobotDescargas = ErrorRobotDescargas

        # RobotAltas errors
        class ErrorRobotAltas:
            NoResult = "⚠️ No result from portal robot for task {cliente}"
            Error = "⚠️ Error in portal robot for task {cliente} : {e}"
            CertificateHandlerError = "⚠️ Error in certificate handler for task {sede_id}"
            ErrorUpdateStatus = "⚠️ Error updating alta status: {e}"
        self.ErrorRobotAltas = ErrorRobotAltas

        # RobotMatriculasYPuntos errors
        class ErrorRobotMatriculasYPuntos:
            ErrorElementDetected = "Error element detected on the page."
            ExtractVehicleData = "⚠️ Error al extraer datos de vehículos: {e}"
            ExtractPointsData = "⚠️ Error al extraer datos de puntos: {e}"
            ExtractClientData = "⚠️ Error al extraer datos del cliente: {e}"
        self.ErrorRobotMatriculasYPuntos = ErrorRobotMatriculasYPuntos

    # Example getter for a specific error
    def get_error(self, error_name, *args, **kwargs):
        if hasattr(self, error_name):
            attr = getattr(self, error_name)
            if callable(attr):
                return attr(*args, **kwargs)
            return attr
        raise AttributeError(f"Error type '{error_name}' not found.")

    @classmethod
    def log_error(cls, class_name, message):
        """Log an error message under a specific class/module name."""
        if class_name not in cls._errors_by_class:
            cls._errors_by_class[class_name] = []
        cls._errors_by_class[class_name].append(message)

    @classmethod
    def get_errors_by_class(cls, class_name):
        """Get all error messages for a specific class/module."""
        return cls._errors_by_class.get(class_name, [])

    @classmethod
    def get_all_errors(cls):
        """Get all error messages organized by class/module."""
        return cls._errors_by_class

    @classmethod
    def clear_errors(cls):
        """Clear all stored error messages."""
        cls._errors_by_class = {class_name: [] for class_name in CLASSES_IN_APP.keys()}
