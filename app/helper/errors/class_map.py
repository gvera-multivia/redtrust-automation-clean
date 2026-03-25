# This file is auto-generated to provide a dictionary of all classes in the app directory.
# The dictionary maps class names to their module paths and error log messages for generalizing log error messages.

CLASSES_IN_APP = {
    'RobotMatriculasYPuntos': {
        'module': 'robot_matriculas_y_puntos',
        'errors': [
            "No se pudo encontrar el botón de inicio de sesión",
            "Error element detected on the page.",
            "⚠️ Error al esperar el elemento de error",
            "Error frame detected on the page.",
            "⚠️ Error al esperar el frame de error",
            "No hay vehículos disponibles para el cliente.",
            "Attempt {attempts + 1} failed: {e}",
            "Max attempts reached. Returning null.",
            "Error esperando a cargar las matriculas del area de cliente: {e}",
            "⚠️ No se pudo configurar para mostrar 100 filas por página: {e}",
            "Error fetching data for matricula {matricula}: {e}",
            "⚠️ Error al extraer datos de vehículos: {e}",
            "Error leyendo las matriculas del cliente : {e}",
            "No hay vehículos disponibles en el selector."
        ]
    },
    'RobotDescargas': {
        'module': 'robot_descargas',
        'errors': [
            "⚠️ No result returned from portal robot for task {notification_id}",
            "⚠️ Error in portal robot for task {notification_id}: {e}",
            "⚠️ Error in certificate handler for task {notification_id}, attempt {retries}: {e}",
            "❌ Certificate handler for task {notification_id} failed after {retries} attempts",
            "⚠️ No result returned from portal robot for task {notification_ids}",
            "⚠️ Unknown sede for downloads: {notification['sede']}",
            "⚠️ Robot not initialized for sede: {sede}",
            "⚠️ Missing servicio in notification: {notification}",
            "⚠️ Invalid servicio: {notification.get('servicio', 'Unknown')}. Skipping task ID {notification['message_id']}",
            "⚠️ Missing key in notification: {e}"
        ]
    },
    'RobotAltas': {
        'module': 'robot_altas',
        'errors': [
            "⚠️ No result from portal robot for task {cliente}",
            "⚠️ Error in portal robot for task {cliente} : {e}",
            "Certificate handler for task {sede_id} failed. Retrying...",
            "⚠️ Error in certificate handler for task {sede_id}, attempt {retries}: {e}",
            "Max retries reached for task {sede_id}. Marking as failed.",
            "⚠️ Error updating alta status: {e}"
        ]
    },
    'CertificateManager': {
        'module': 'robot.handle_certificate',
        'errors': [
            "⚠️ No se encontró la ventana del certificado para {self.site_name}.",
            "⚠️ Error al procesar el certificado: {e}",
            "⚠️ Contenedor de elementos de certificados cargados no encontrada.",
            "⚠️ Ventana de selección de certificado no encontrada.",
            "⚠️ Error al manejar el certificado: {e}"
        ]
    },
    'RobotEnotum': {
        'module': 'robot.descargas.robotEnotum',
        'errors': [
            "No se encontró el elemento para {xpath}",
            "⚠️ Error en login: {e}",
            "⚠️ Error comprobando el nif/cif con {destinatari} - {nif_cif}, {e}",
            "⚠️ Error comprobando el nif/cif en la lista de empresas con {destinatari} - {nif_cif}, {e}",
            "⚠️ Error seleccionando el perfil de la descarga",
            "⚠️ Error en el paso 2: seleccionando la notificación",
            "⚠️ Error en la ejecución predeterminada de la notificación: {e}",
            "⚠️ Error abriendo notificación no descargada",
            "⚠️ Error en la ejecución de acceso a la notificacion: {e}",
            "⚠️ Error en recuperar notificaciones en {portalLink}: {e}"
        ]
    },
    'RobotDgt': {
        'module': 'robot.descargas.robotDgt',
        'errors': [
            "⚠️ Error switching to the new window: {e}",
            "⚠️ Error switching to the last window: {e}",
            "⚠️ No browser windows available to switch to.",
            "Error en login: Se ha producido un error en la página.",
            "⚠️ Error en login: {e}",
            "Error en login",
            "No se pudo hacer clic en ningún botón para continuar el proceso.",
            "Error al continuar el proceso de alta.",
            "Error: Verificando.",
            "Error al verificar el resultado: {e}",
            "Error al verificar el resultado.",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotDehu': {
        'module': 'robot.altas.robotDehu',
        'errors': [
            "Error en el botón de login",
            "⚠️ Error al recargar la página: {e}",
            "⚠️ Error al hacer clic en el botón de recarga: {e}",
            "Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "Error buscando el mail {mail}: {e}",
            "Error añadiendo campo email: {e}"
        ]
    },
    'RobotComunidadValenciana': {
        'module': 'robot.altas.robotComunidadValenciana',
        'errors': [
            "⚠️ Error en login: {e}",
            "Error en el menu de navegación: {e}",
            "Error añadiendo los datos de contacto {e}",
            "Error en la verificación: {e}",
            "Error en login",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotCeuta': {
        'module': 'robot.altas.robotCeuta',
        'errors': [
            "❌ Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "NIF/CIF no coincide. Encontrado: {nif_text}, Esperado: {nif_cif}",
            "⚠️ Error al buscar NIF/CIF en el portal",
            "Error en login",
            "⚠️ Error en el proceso de suscripción: {e}"
        ]
    },
    'RobotCastillaLeon': {
        'module': 'robot.altas.robotCastillaLeon',
        'errors': [
            "Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "Error introduciendo datos personales: {e}",
            "Error en login",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotCastillaLaMancha': {
        'module': 'robot.altas.robotCastillaLaMancha',
        'errors': [
            "Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "⚠️ Error en seleccionar buzón",
            "⚠️ Error en buscar el botón de alta",
            "⚠️ Error en ingresar los datos de contacto",
            "Error en login",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotBurgos': {
        'module': 'robot.altas.robotBurgos',
        'errors': [
            "⚠️ Error en login: {e}",
            "⚠️ Error al modificar la información de contacto: {e}",
            "⚠️ Error al verificar la información de contacto: {e}",
            "⚠️ Error al obtener la confirmación de contacto",
            "⚠️ Error al comprobar los medios de contacto: {e}",
            "⚠️ Error al verificar los medios de contacto: {e}",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotAtib': {
        'module': 'robot.altas.robotBaleares',
        'errors': [
            "⚠️ Error en login: {e}",
            "⚠️ Error accediendo al formulario de alta: {e}",
            "⚠️ Error al completar el formulario de datos personales: {e}",
            "Error en el login",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotBadajoz': {
        'module': 'robot.altas.robotBadajoz',
        'errors': [
            "Error al buscar el enlace 'notificaciones y comunicaciones': {e}",
            "Error al hacer login con Cl@ve: {e}",
            "⚠️ Error en login: {e}",
            "El valor del documento ({value}) no coincide con el NIF/CIF proporcionado ({nif_cif})",
            "Error al añadir el mail de MULTIVIA como secundario",
            "Error en el proceso de rellenar datos y continuar: {e}",
            "No se ha encontrado la verificación",
            "No se encontró el panel de éxito o texto incorrecto: {e}",
            "Error introduciendo los datos de contacto: {e}"
        ]
    },
    'RobotAtc': {
        'module': 'robot.altas.robotAtc',
        'errors': [
            "Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "El NIF no coincide. Esperado: {nif_cif}, Obtenido: {nif}",
            "⚠️ Error al obtener el NIF: {e}",
            "⚠️ Error al rellenar el campo de correo: {e}",
            "⚠️ Error al rellenar el campo de teléfono: {e}",
            "⚠️ Error rellenando los datos de contacto: {e}",
            "⚠️ Error al confirmar la suscripción: {e}",
            "⚠️ Error al actualizar el perfil: {e}"
        ]
    },
    'RobotAsturias': {
        'module': 'robot.altas.robotAsturias',
        'errors': [
            "⚠️ Error en login: {e}",
            "⚠️ Error al modificar la información de contacto: {e}",
            "⚠️ Error al verificar la información de contacto: {e}",
            "⚠️ Error al obtener la confirmación de contacto",
            "⚠️ Error al comprobar los medios de contacto: {e}",
            "⚠️ Error al verificar los medios de contacto: {e}",
            "Error en el login",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotAndalucia': {
        'module': 'robot.altas.robotAndalucia',
        'errors': [
            "Login fallido: No se encontraron los elementos esperados.",
            "⚠️ Error en login: {e}",
            "El texto del elemento no coincide con NIF o CIF {nif_cif}. Valor encontrado: {identificador}",
            "Error al rellenar el formulario: {e}",
            "Error al hacer submit del formulario: {e}",
            "Error Datos de contacto fallido: {e}",
            "⚠️ Error en darse de alta en {self.portal_link}: {e}"
        ]
    },
    'RobotExecutionModel': {
        'module': 'models.robot_execution_model',
        'errors': [
            "status must be one of {allowed}",
            "prevDescargado must be 'SI', 'NO', or None"
        ]
    },
    'ExtractionResponse': {
        'module': 'models.mailExtractionModel',
        'errors': []
    },
    'RedTrustManager': {
        'module': 'redtrust.redtrust_manager',
        'errors': [
            "RedTrust button not found.",
            "⚠️ Error automating RedTrust: {e}",
            "RedTrust icon not found in the system tray.",
            "⚠️ Error locating RedTrust icon: {e}",
            "Failed to locate the RedTrust icon.",
            "Certificate list box not found.",
            "⚠️ Error selecting certificate {certificate_id}: {e}"
        ]
    },
    'Settings': {
        'module': 'helper.config',
        'errors': []
    },
    'EmailFilter': {
        'module': 'mail.emailDehuFilter',
        'errors': [
            "Error selecting INBOX: {e}",
            "Error decoding email body: {e}"
        ]
    },
    'DatabaseManager': {
        'module': 'database.database_manager',
        'errors': [
            "Error connecting to the database: {e}",
            "Error updating descarga en el historico: {e}",
            "Error fetching tasks: {e}",
            "Error assigning notification: {e}",
            "Error updating el estado de la descarga: {e}",
            "Error fetching altas: {e}",
            "Error assigning certificate: {e}"
        ]
    },
    'WebDriverSetup': {
        'module': 'utils.setup',
        'errors': [
            "❌ Error al cargar {self.portal_link}: {e}",
            "⚠️ No se pudo cargar la página después de varios intentos."
        ]
    },
    'Error': {
        'module': 'utils.error',
        'errors': []
    },
    'ServiciosNEO': {
        'module': 'utils.utils',
        'errors': []
    },
    'ExecutionPath': {
        'module': 'robot.altas.robotEnotum',
        'errors': []
    }
}
