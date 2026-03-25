# -*- coding: utf-8 -*-
from http.client import HTTPException
from fastapi import APIRouter, Request
import os
from dotenv import load_dotenv
from app.helper.loggerV2 import LoggerV2
from database.database_manager import DatabaseManager, retry_on_deadlock  # Adjust import as needed
from api.config.api_config import settings
from typing import List, Dict, Any
from fastapi import Body
from fastapi.responses import JSONResponse
from datetime import datetime

router = APIRouter(
    prefix="/database", 
    tags=["Base de Datos"],
    responses={
        400: {"description": "Parámetros inválidos"},
        404: {"description": "Registro no encontrado"},
        500: {"description": "Error de base de datos"}
    }
)
logger = LoggerV2(
    module="API",
    class_name=__name__, 
    log_dir=settings.LOG_DIR, 
    filename=settings.LOG_FILE
)


@router.get(
    "/getDescargaEspecial",
    summary="Obtener Configuraciones de Descarga Especial",
    description="""
    Obtiene todas las configuraciones de descarga especial para clientes.
    
    ### Funcionalidad:
    
    Retorna la lista completa de clientes que tienen configuraciones especiales
    para el proceso de descarga de documentos, incluyendo avisos y configuraciones
    personalizadas.
    
    ### Información incluida:
    
    * **cliente**: Código único del cliente
    * **nombre**: Nombre del cliente
    * **especial**: Tipo de configuración especial o aviso
    
    ### Casos de uso:
    
    * Configurar procesos de descarga personalizados
    * Verificar avisos especiales antes de procesar
    * Obtener lista de clientes con tratamiento especial
    """,
    responses={
        200: {
            "description": "Configuraciones obtenidas exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": [
                            {
                                "cliente": "CLI001",
                                "nombre": "Cliente Ejemplo S.L.",
                                "especial": "Requiere validación manual"
                            },
                            {
                                "cliente": "CLI002",
                                "nombre": "Empresa Test",
                                "especial": "Descarga automática deshabilitada"
                            }
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Error de base de datos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error fetching descarga especial: [error details]"
                    }
                }
            }
        }
    },
    tags=["Configuración", "Clientes"]
)
async def get_descarga_especial():
    try:
        
        load_dotenv(dotenv_path='.env', override=True)
        db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        today = datetime.today().strftime('%Y-%m-%d')
        db_manager = DatabaseManager(db_config=db_config, date=today, module="API", filename=settings.LOG_FILE)
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()
            query = "SELECT cliente, nombre, especial FROM descargaespecial"
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.info("API", "DatabaseEndpoint", "Failure", f"Database query error: {e}")
            data = None
        finally:
            cursor.close()
            conn.close()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching descarga especial: {str(e)}"
        )


@router.get(
    "/getDataCliente",
    summary="Obtener Datos Completos del Cliente",
    description="""
    Obtiene información detallada de un cliente específico incluyendo datos personales,
    asignaciones y avisos especiales.
    
    ### Información incluida:
    
    #### Datos personales:
    * **Nombre, Apellido1, Apellido2**: Datos personales
    * **Nombrecomercial**: Nombre comercial de la empresa
    * **Nombrefiscal**: Nombre fiscal oficial
    * **Nif**: Número de identificación fiscal
    
    #### Asignaciones:
    * **asesor**: Asesor asignado al cliente
    * **letradaasig**: Letrada asignada
    * **ComercialAsig**: Comercial asignado
    
    #### Clasificación y avisos:
    * **tipocliente**: Tipo/categoría del cliente
    * **aviso**: Avisos especiales para descarga
    
    ### Parámetro requerido:
    
    * **cliente_id**: Código único del cliente a consultar
    
    ### Casos de uso:
    
    * Verificar datos del cliente antes de procesos
    * Obtener información de contacto y asignaciones
    * Consultar avisos especiales para tratamiento
    """,
    responses={
        200: {
            "description": "Datos del cliente obtenidos exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": [
                            {
                                "Nombre": "Juan",
                                "Apellido1": "Pérez",
                                "Apellido2": "García",
                                "Nombrecomercial": "Empresa Ejemplo S.L.",
                                "Nombrefiscal": "Juan Pérez García",
                                "Nif": "12345678A",
                                "asesor": "Asesor Fiscal 1",
                                "letradaasig": "María López",
                                "ComercialAsig": "Carlos Ruiz",
                                "tipocliente": "EMPRESA",
                                "aviso": "Requiere validación especial"
                            }
                        ]
                    }
                }
            }
        },
        400: {
            "description": "Parámetro cliente_id requerido"
        },
        404: {
            "description": "Cliente no encontrado",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": []
                    }
                }
            }
        },
        500: {
            "description": "Error de base de datos"
        }
    },
    tags=["Clientes", "Consulta"]
)
async def get_aviso_cliente(cliente_id: str):
    try:        
        load_dotenv(dotenv_path='.env', override=True)
        db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        today = datetime.today().strftime('%Y-%m-%d')
        db_manager = DatabaseManager(db_config=db_config, date=today, module="API", filename=settings.LOG_FILE)
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()
            query = """SELECT 
                    c.Nombre,
                    c.Apellido1,
                    c.Apellido2,
                    c.Nombrecomercial,
                    c.Nombrefiscal, 
                    c.Nif,
                    c.asesor,
                    c.letradaasig,
                    c.ComercialAsig,
                    UPPER(t.concepto) as tipocliente, 
                    d.especial as aviso
                FROM clientes c
                INNER JOIN tblvTipoCliente t ON c.tipodecliente = t.idTipoCliente
                LEFT JOIN descargaespecial d ON c.numerocliente = d.cliente
                WHERE c.numerocliente = %s"""
            cursor.execute(query, (cliente_id,))
            columns = [col[0] for col in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.info("API", "DatabaseEndpoint", "Failure", f"Database query error: {e}")
            data = None
        finally:
            cursor.close()
            conn.close()

        return {"success": True, "data": data}
    except Exception as e:
        logger.error(f"Error fetching avisos para cliente {cliente_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching avisos para cliente {cliente_id}: {str(e)}"
        )


@router.get(
    "/getAvisos",
    summary="Obtener Lista de Avisos Disponibles",
    description="""
    Obtiene la lista completa de todos los tipos de avisos especiales disponibles en el sistema.
    
    ### Funcionalidad:
    
    Este endpoint retorna todos los valores únicos de avisos especiales que están
    configurados en la tabla de descarga especial, sin duplicados.
    
    ### Información proporcionada:
    
    * **Lista de avisos**: Todos los tipos de configuraciones especiales disponibles
    * **Sin duplicados**: Cada tipo de aviso aparece solo una vez
    * **Valores actuales**: Solo avisos actualmente en uso en el sistema
    
    ### Tipos de avisos comunes:
    
    * "Requiere validación manual"
    * "Descarga automática deshabilitada"
    * "Cliente prioritario"
    * "Revisión especial requerida"
    * "Documentos confidenciales"
    * "Proceso personalizado"
    
    ### Casos de uso:
    
    * **Interfaz de usuario**: Poblar listas desplegables de avisos
    * **Configuración**: Ver qué tipos de avisos están disponibles
    * **Mantenimiento**: Auditar configuraciones especiales activas
    * **Desarrollo**: Entender las categorías de tratamiento especial
    * **Reportes**: Generar estadísticas de tipos de configuraciones
    
    ### Integración:
    
    Los avisos obtenidos pueden usarse como valores válidos para
    el endpoint `POST /postDescargaEspecial` al crear nuevas configuraciones.
    """,
    responses={
        200: {
            "description": "Lista de avisos obtenida exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": [
                            {"especial": "Requiere validación manual"},
                            {"especial": "Descarga automática deshabilitada"},
                            {"especial": "Cliente prioritario"},
                            {"especial": "Revisión especial requerida"},
                            {"especial": "Documentos confidenciales"}
                        ]
                    }
                }
            }
        },
        500: {
            "description": "Error de base de datos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error fetching avisos: [database error]"
                    }
                }
            }
        }
    },
    tags=["Configuración", "Avisos"]
)
async def get_avisos():
    try:
        load_dotenv(dotenv_path='.env', override=True)
        db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        today = datetime.today().strftime('%Y-%m-%d')
        db_manager = DatabaseManager(db_config=db_config, date=today, module="API", filename=settings.LOG_FILE)
        try:
            conn = db_manager.connect()
            cursor = conn.cursor()
            query = "SELECT distinct especial FROM descargaespecial"
            cursor.execute(query)
            columns = [col[0] for col in cursor.description]
            data = [dict(zip(columns, row)) for row in cursor.fetchall()]
        except Exception as e:
            logger.info("API", "DatabaseEndpoint", "Failure", f"Database query error: {e}")
            data = None
        finally:
            cursor.close()
            conn.close()
        return {"success": True, "data": data}
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching avisos: {str(e)}"
        )
            
@router.post(
    "/postDescargaEspecial",
    summary="Crear/Actualizar Configuración de Descarga Especial",
    description="""
    Crea una nueva configuración de descarga especial o actualiza una existente para un cliente.
    
    ### Funcionalidad:
    
    Este endpoint permite configurar tratamientos especiales para clientes específicos
    durante el proceso de descarga de documentos.
    
    ### Comportamiento inteligente:
    
    * **Cliente existente**: Actualiza la configuración especial existente
    * **Cliente nuevo**: Crea una nueva entrada en la configuración
    * **Protección contra deadlock**: Implementa reintentos automáticos
    * **Auditoría**: Registra quién y cuándo se hizo la modificación
    
    ### Parámetros requeridos:
    
    * **cliente**: Código único del cliente (requerido)
    * **nombre**: Nombre del cliente para referencia (requerido)
    * **aviso**: Tipo de configuración especial a aplicar (requerido)
    
    ### Tipos de configuraciones disponibles:
    
    Puede usar cualquier valor obtenido del endpoint `/getAvisos` o crear nuevos:
    
    * "Requiere validación manual"
    * "Descarga automática deshabilitada"
    * "Cliente prioritario"
    * "Revisión especial requerida"
    * "Documentos confidenciales"
    * "Proceso personalizado"
    
    ### Efectos de las configuraciones:
    
    * **Validación manual**: Pausa el proceso para revisión humana
    * **Descarga deshabilitada**: Excluye al cliente de descargas automáticas
    * **Prioritario**: Procesa al cliente antes que otros
    * **Revisión especial**: Aplica filtros adicionales de calidad
    * **Confidencial**: Usa protocolos de seguridad adicionales
    
    ### Ejemplo de uso:
    
    ```json
    {
        "cliente": "CLI001",
        "nombre": "Empresa Importante S.L.",
        "aviso": "Cliente prioritario"
    }
    ```
    
    ### Auditoría y trazabilidad:
    
    * **create_date**: Timestamp automático de creación/modificación
    * **created_by**: Usuario que realizó la operación
    * **Historial**: Se mantiene registro de cambios
    """,
    responses={
        200: {
            "description": "Configuración creada/actualizada exitosamente",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "message": "Configuración de descarga especial actualizada",
                        "cliente": "CLI001",
                        "aviso_anterior": "Requiere validación manual",
                        "aviso_nuevo": "Cliente prioritario",
                        "fecha_actualizacion": "2024-01-15T10:30:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Datos requeridos faltantes",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Missing required fields: cliente, nombre, aviso"
                    }
                }
            }
        },
        500: {
            "description": "Error de base de datos",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Error posting descarga especial: Database connection failed"
                    }
                }
            }
        }
    },
    tags=["Configuración", "Gestión"]
)
async def post_descarga_especial(payload: Dict[str, Any] = Body(...)):
    try:
        cliente: str = payload.get("cliente")
        nombre: str = payload.get("nombre")
        aviso: str = payload.get("aviso")
        load_dotenv(dotenv_path='.env', override=True)
        db_config = {
            "user": os.getenv("DB_USER"),
            "password": os.getenv("DB_PASSWORD"),
            "server": os.getenv("DB_SERVER"),
            "database": os.getenv("DB_NAME"),
            "options": {
                "encrypt": os.getenv("DB_ENCRYPT", "False").lower() == "true",
                "enableArithAbort": os.getenv("DB_ENABLE_ARITH_ABORT", "True").lower() == "true",
            }
        }
        today = datetime.today().strftime('%Y-%m-%d')
        db_manager = DatabaseManager(db_config=db_config, date=today, module="API", filename=settings.LOG_FILE)

        try:
                @retry_on_deadlock()
                def _post_descarga_especial_db_op():
                    conn = db_manager.connect()
                    cursor = conn.cursor()
                    # Check if the cliente already exists
                    check_query = "SELECT COUNT(*) FROM descargaespecial WHERE cliente = %s"
                    cursor.execute(check_query, (cliente,))
                    exists = cursor.fetchone()[0]

                    if exists:
                        # Update the 'especial' field for existing cliente
                        query = "UPDATE descargaespecial SET especial = %s WHERE cliente = %s"
                        cursor.execute(query, (aviso, cliente))
                    else:
                        # Insert new row
                        query = "INSERT INTO descargaespecial (cliente, nombre, especial, create_date, created_by) VALUES (%s, %s, %s, %s, %s)"
                        cursor.execute(query, (cliente, nombre, nombre, datetime.now(), "Adría Martínez"))
                    conn.commit()
                    cursor.close()
                    conn.close()

                # execute the DB op with retry-on-deadlock
                _post_descarga_especial_db_op()

        except Exception as e:
            logger.info("API", "DatabaseEndpoint", "Failure", f"Database query error: {e}")
            raise e

        return {"success": True}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error posting descarga especial: {str(e)}"
        )
