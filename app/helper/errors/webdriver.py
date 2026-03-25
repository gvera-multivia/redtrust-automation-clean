from .base import ErrorBase

class ErrorWebDriver(ErrorBase):
    DriverNotFound = staticmethod(lambda driver_path: RuntimeError(f"⚠️ WebDriver not found: {driver_path}"))
    DriverInitError = staticmethod(lambda e: RuntimeError(f"⚠️ Error initializing WebDriver: {e}"))
    Timeout = staticmethod(lambda element: RuntimeError(f"⚠️ WebDriver timeout waiting for element: {element}"))
