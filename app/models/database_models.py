# THIRD PARTY PACKAGES
from pydantic import BaseModel, EmailStr, Field, validator # type: ignore
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from decimal import Decimal


# =================================================================
# TABLA PRINCIPAL: historico_automatizaciones
# =================================================================

class HistoricoAutomatizaciones(BaseModel):
    """Main table for all robot executions (historico_automatizaciones)"""
    execution_id: UUID
    cliente: int
    nif: Optional[str] = Field(None, max_length=20)
    cif: Optional[str] = Field(None, max_length=20)
    tipo_cliente: Optional[str] = Field(None, max_length=50)
    robot_name: str = Field(max_length=100)
    status: str = Field(max_length=20)
    sede: str = Field(max_length=100)
    result_robot: Optional[str] = None
    result_certificate: Optional[bool] = None
    execution_message: Optional[str] = None
    updated_by_user_id: int
    updated_by_user_name: str = Field(max_length=100)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('status')
    def validate_status(cls, v):
        allowed = {'completed', 'pending', 'error'}
        if v not in allowed:
            raise ValueError(f'status must be one of {allowed}')
        return v
    
    @validator('robot_name')
    def validate_robot_name(cls, v):
        allowed = {'RobotDescargas', 'RobotAltas', 'RobotInformesDGT', 'RobotConsulta', 'RobotActualizaciones', 'RobotSedeJudicial', 'SubidaRTCertificados'}
        if v not in allowed:
            raise ValueError(f'status must be one of {allowed}')
        return v


# =================================================================
# TABLAS DEPENDIENTES DE historico_automatizaciones
# =================================================================

class DescargasAutomatizaciones(BaseModel):
    """Child entity for Descargas automation (descargas_automatizaciones)"""
    id: UUID
    execution_id: UUID
    message_key: Optional[str] = Field(None, max_length=255)
    fecha_descarga: Optional[datetime] = None
    identificador: Optional[str] = Field(None, max_length=100)
    expediente: Optional[str] = Field(None, max_length=100)
    prev_desc: Optional[str] = Field(None, max_length=3)
    filename: Optional[str] = Field(None, max_length=1024)
    organismo: Optional[str] = Field(None, max_length=255)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @validator('prev_desc')
    def validate_prev_desc(cls, v):
        if v is not None and v not in {'SI', 'NO'}:
            raise ValueError("prev_desc must be 'SI', 'NO', or None")
        return v


class AltasAutomatizaciones(BaseModel):
    """Child entity for Altas automation (altas_automatizaciones)"""
    id: UUID
    execution_id: UUID
    action: Optional[str] = Field(None, max_length=100)
    emails: Optional[str] = None
    downloads: Optional[bool] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class InformesDgtAutomatizaciones(BaseModel):
    """Child entity for DGT Reports automation (informes_dgt_automatizaciones)"""
    id: UUID
    execution_id: UUID
    nif_en_sede: Optional[str] = Field(None, max_length=20)
    nombre_en_sede: Optional[str] = Field(None, max_length=200)
    matriculas: Optional[int] = None
    puntos: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConsultaAutomatizaciones(BaseModel):
    """Child entity for Consulta automation (consulta_automatizaciones)"""
    id: UUID
    execution_id: UUID
    resultado: Optional[str] = Field(None, max_length=100)
    notas: Optional[str] = None
    descarga: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ActualizacionesAutomatizaciones(BaseModel):
    """Child entity for Actualizaciones automation (actualizaciones_automatizaciones)"""
    id: UUID
    execution_id: UUID
    estado_actualizacion: Optional[str] = Field(None, max_length=50)
    notas: Optional[str] = None
    deuda: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2)
    expediente: Optional[str] = Field(None, max_length=255)
    archivo: Optional[str] = Field(None, max_length=255)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

class SedeJudicialAutomatizaciones(BaseModel):
    """Child entity for judicial seat data (sede_judicial_automatizaciones)"""
    id: UUID
    execution_id: UUID
    num_expedientes: Optional[int] = None
    num_señalamientos: Optional[int] = None
    num_justicia_gratuita: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    


# =================================================================
# TABLAS DEPENDIENTES DE informes_dgt_automatizaciones
# =================================================================

class MatriculasExtraidas(BaseModel):
    """Matriculas extracted from DGT reports (matriculas_extraidas)"""
    id: UUID
    informe_id: UUID
    matricula: str = Field(max_length=10)
    matriculacion: Optional[datetime] = None
    marca: Optional[str] = Field(None, max_length=50)
    modelo: Optional[str] = Field(None, max_length=100)
    combustible: Optional[str] = Field(None, max_length=50)
    situacion_administrativa: Optional[str] = Field(None, max_length=255)
    servicio_al_que_se_destina: Optional[str] = Field(None, max_length=255)
    bastidor: Optional[str] = Field(None, max_length=255)
    cilindrada_cm: Optional[int] = None
    distintivo_ambiental: Optional[str] = Field(None, max_length=255)
    num_identificacion_vehiculo_nive: Optional[str] = Field(None, max_length=255)
    situacion_itv: Optional[str] = Field(None, max_length=50)
    caducidad_itv: Optional[datetime] = None
    km_ultima_itv: Optional[int] = None
    inicio_del_seguro: Optional[datetime] = None
    aseguradora: Optional[str] = Field(None, max_length=255)
    direccion: Optional[str] = Field(None, max_length=255)
    codigo_postal: Optional[str] = Field(None, max_length=10)
    municipio: Optional[str] = Field(None, max_length=100)
    provincia: Optional[str] = Field(None, max_length=50)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class SancionesExtraidas(BaseModel):
    """Sanctions extracted from DGT reports (sanciones_extraidas)"""
    id: UUID
    informe_id: UUID
    fecha_sancion: Optional[datetime] = None
    puntos_sancion: Optional[int] = None
    sancion: Optional[str] = None
    saldo_puntos_final: Optional[int] = None
    organismo_sancionador: Optional[str] = Field(None, max_length=100)
    created_at: Optional[datetime] = None


# =================================================================
# TABLAS DEPENDIENTES DE matriculas_extraidas
# =================================================================

class AlertasExtraidas(BaseModel):
    """Alerts extracted for vehicles (alertas_extraidas)"""
    id: UUID
    matricula_id: UUID
    alertas_vehiculo: Optional[str] = None
    created_at: Optional[datetime] = None


# =================================================================
# TABLAS DEPENDIENTES DE consulta_automatizaciones
# =================================================================

class DescargaConsulta(BaseModel):
    """Download data from consulta automation (descarga_consulta)"""
    id: UUID
    id_consulta: UUID
    url: Optional[str] = None
    id_notificacion: Optional[str] = Field(None, max_length=50)
    asunto_notificacion: Optional[str] = Field(None, max_length=50)
    organismo_notificacion: Optional[str] = Field(None, max_length=50)
    fecha_notificacion: Optional[str] = Field(None, max_length=50)
    descargada_notificacion: Optional[bool] = None
    expediente_notificacion: Optional[str] = Field(None, max_length=50)
    descarga_status: Optional[str] = Field(None, max_length=50)
    created_at: Optional[datetime] = None

# =====================================================
# Modelo: OtrosProcedimientosExpediente
# =====================================================
class OtrosProcedimientosExpediente(BaseModel):
    id: UUID
    expediente_judicial_id: UUID
    fecha_procedimiento: Optional[datetime] = None
    estado_procedimiento: Optional[str] = None
    tipo_procedimiento: Optional[str] = None
    numero_año: Optional[str] = None
    organo_judicial: Optional[str] = None

# =====================================================
# Modelo: IntervinientesExpediente
# =====================================================
class IntervinientesExpediente(BaseModel):
    id: UUID
    expediente_judicial_id: UUID
    nombre_interviniente: Optional[str] = None
    rol_interviniente: Optional[str] = None
    correo_electronico: Optional[EmailStr] = None
    direccion: Optional[str] = None
    poblacion: Optional[str] = None
    municipio: Optional[str] = None
    provincia: Optional[str] = None
    pais: Optional[str] = None
    codigo_postal: Optional[str] = None
    telefono: Optional[str] = None

# =====================================================
# Modelo: HitosProcesalesExpediente
# =====================================================
class HitosProcesalesExpediente(BaseModel):
    id: UUID
    expediente_judicial_id: UUID
    fecha_hito: Optional[datetime] = None
    descripcion_hito: Optional[str] = None
    fecha_resolucion: Optional[datetime] = None
    fecha_incoacion: Optional[datetime] = None

# =====================================================
# Modelo: SenalamientoJudicial
# =====================================================
class SeñalamientoJudicial(BaseModel):
    id: UUID
    sedejudicial_id: UUID
    expediente_judicial_id: Optional[UUID] = None
    fecha_señalamiento: Optional[datetime] = None
    hora_inicio: Optional[str] = None
    hora_fin: Optional[str] = None
    sala: Optional[str] = None
    estado: Optional[str] = None
    motivo_anulacion: Optional[str] = None
    procedimiento: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# =====================================================
# Modelo: ExpedienteJudicial
# =====================================================
class ExpedienteJudicial(BaseModel):
    id: UUID
    sedejudicial_id: UUID
    justiciagratuita_id: Optional[UUID] = None
    any_expediente: Optional[int] = None
    fecha_expediente: Optional[datetime] = None
    organo_judicial: Optional[str] = None
    procedimiento: Optional[str] = None
    numero_any_seccion: Optional[str] = None
    nig: Optional[str] = None
    ambito: Optional[str] = None
    num_demanda: Optional[str] = None
    fecha_presentacion: Optional[datetime] = None
    fecha_registro: Optional[datetime] = None
    estado_expediente: Optional[str] = None
    juzgado: Optional[str] = None
    fecha_incoacion: Optional[datetime] = None
    fase: Optional[str] = None
    tipo_quantia: Optional[str] = None
    importe_principal: Optional[Decimal] = None
    
    otros_procedimientos: Optional[List[OtrosProcedimientosExpediente]] = []
    intervinientes: Optional[List[IntervinientesExpediente]] = []
    hitos_procesales: Optional[List[HitosProcesalesExpediente]] = []
    
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# =====================================================
# Modelo: JusticiaGratuitaJudicial
# Representa la tabla `justiciagratuita_judicial` con FK a `sedejudicial_automatizaciones(id)`
# =====================================================
class JusticiaGratuitaJudicial(BaseModel):
    id: UUID
    sedejudicial_id: UUID
    codi_expedient: Optional[str] = Field(None, max_length=100)
    organ_judicial: Optional[str] = Field(None, max_length=255)
    procediment: Optional[str] = Field(None, max_length=255)
    n_act: Optional[str] = Field(None, max_length=100)
    estat: Optional[str] = Field(None, max_length=100)
    dictamen: Optional[str] = Field(None, max_length=255)
    sentit_resolucio_final: Optional[str] = Field(None, max_length=255)
    tipologia_resolucio: Optional[str] = Field(None, max_length=255)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

