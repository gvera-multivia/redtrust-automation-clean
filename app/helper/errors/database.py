from .base import ErrorBase

class ErrorDatabaseManager(ErrorBase):
    ConnectionError = staticmethod(lambda e: RuntimeError(f"⚠️ Error connecting to the database: {e}"))
    QueryError = staticmethod(lambda e: RuntimeError(f"⚠️ Error executing query: {e}"))
    NotFound = staticmethod(lambda query: RuntimeError(f"⚠️ No results found for query: {query}"))
