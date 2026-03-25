class ErrorBase(Exception):
    """
    Base class with generic error messages
    """

    ErrorXpathElemento = staticmethod(lambda xpath: f"Error encontrando elemento {xpath}")
    ErrorElementError = "⚠️ Error al esperar el elemento de error"
    ErrorLoginSede = staticmethod(lambda sede, e: f"Error en el Login en {sede}, {e}")
    ErrorDarAltaSede = staticmethod(lambda portal_link, e: f"⚠️ Error en darse de alta en {portal_link}: {e}")
    ErrorNifCliente = staticmethod(lambda nif_cif_cliente, nif_encontrado: f"⚠️ Error comprobando NIF/CIF {nif_cif_cliente} con el encontrado en la sede {nif_encontrado}")
    ErrrDatosContacto = "⚠️ Error rellenando los datos de contacto"
    ErrorVerificandoAlta = "⚠️ Error verificando alta"
    ErrorDescargaEnSede = staticmethod(lambda portal_link, e: f"⚠️ Error en la descarga en {portal_link}: {e}")

    @classmethod
    def generic(cls):
        return [attr for attr in dir(cls) if not attr.startswith("__") and not callable(getattr(cls, attr))]
