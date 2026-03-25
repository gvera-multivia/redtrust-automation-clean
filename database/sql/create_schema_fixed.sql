-- =================================================================
-- CREACIÓN DE BASE DE DATOS Y ESQUEMAS
-- =================================================================

-- Crear base de datos (opcional)
-- CREATE DATABASE RedTrustAutomation;
-- GO
-- USE RedTrustAutomation;
-- GO

-- =================================================================
-- TABLA PRINCIPAL: historico_automatizaciones
-- =================================================================
CREATE TABLE historico_automatizaciones (
    execution_id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    cliente INTEGER NOT NULL,
    nif VARCHAR(20) NULL,
    cif VARCHAR(20) NULL,
    tipo_cliente VARCHAR(50) NULL,
    robot_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) NOT NULL,
    sede VARCHAR(100) NOT NULL,
    result_robot NTEXT NULL,
    result_certificate BIT NULL,
    execution_message NTEXT NULL,
    updated_by_user_id INTEGER NOT NULL,
    updated_by_user_name VARCHAR(100) NOT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE()
);

-- =================================================================
-- TABLAS DEPENDIENTES DE historico_automatizaciones
-- =================================================================

-- Tabla descargas_automatizaciones
CREATE TABLE descargas_automatizaciones (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    execution_id UNIQUEIDENTIFIER NOT NULL,
    message_key VARCHAR(255) NULL,
    fecha_descarga DATETIME2 NULL,
    identificador VARCHAR(100) NULL,
    expediente VARCHAR(100) NULL,
    prev_desc VARCHAR(3) NULL,
    filename VARCHAR(255) NULL,
    organismo VARCHAR(100) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_descargas_execution FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE,
);

-- Tabla altas_automatizaciones
CREATE TABLE altas_automatizaciones (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    execution_id UNIQUEIDENTIFIER NOT NULL,
    action VARCHAR(100) NULL,
    emails NTEXT NULL,
    downloads BIT NULL,
    notes NTEXT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_altas_execution FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE
);

-- Tabla informes_dgt_automatizaciones
CREATE TABLE informes_dgt_automatizaciones (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    execution_id UNIQUEIDENTIFIER NOT NULL,
    nif_en_sede VARCHAR(20) NULL,
    nombre_en_sede VARCHAR(200) NULL,
    matriculas INTEGER NULL,
    puntos INTEGER NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_informes_dgt_execution FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE
);

-- Tabla consulta_automatizaciones
CREATE TABLE consulta_automatizaciones (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    execution_id UNIQUEIDENTIFIER NOT NULL,
    resultado VARCHAR(100) NULL,
    notas NTEXT NULL,
    descarga BIT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_consulta_execution FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE
);

-- Tabla actualizaciones_automatizaciones
CREATE TABLE actualizaciones_automatizaciones (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    execution_id UNIQUEIDENTIFIER NOT NULL,
    estado_actualizacion VARCHAR(50) NULL,
    notas NTEXT NULL,
    deuda DECIMAL(10,2) NULL,
    expediente VARCHAR(255) NULL,
    archivo VARCHAR(255) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_actualizaciones_execution FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE
);

-- =================================================================
-- TABLAS DEPENDIENTES DE informes_dgt_automatizaciones
-- =================================================================

-- Tabla matriculas_extraidas
CREATE TABLE matriculas_extraidas (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    informe_id UNIQUEIDENTIFIER NOT NULL,
    matricula VARCHAR(10) NOT NULL,
    matriculacion DATE NULL,
    marca VARCHAR(50) NULL,
    modelo VARCHAR(100) NULL,
	situacion_administrativa VARCHAR(255) NULL,
    servicio_al_que_se_destina VARCHAR(255) NULL,
    combustible VARCHAR(50) NULL,
    bastidor VARCHAR(255) NULL,
    cilindrada_cm INTEGER NULL,
    distintivo_ambiental VARCHAR(255) NULL,
    num_identificacion_vehiculo_nive VARCHAR(255) NULL,
    situacion_itv VARCHAR(50) NULL,
    caducidad_itv DATE NULL,
    km_ultima_itv INTEGER NULL,
    inicio_del_seguro DATE NULL,
    aseguradora VARCHAR(255) NULL,
    direccion VARCHAR(255) NULL,
    codigo_postal VARCHAR(10) NULL,
    municipio VARCHAR(100) NULL,
    provincia VARCHAR(50) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_matriculas_informe FOREIGN KEY (informe_id) 
        REFERENCES informes_dgt_automatizaciones(id) ON DELETE CASCADE
);

-- Tabla sanciones_extraidas
CREATE TABLE sanciones_extraidas (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    informe_id UNIQUEIDENTIFIER NOT NULL,
    fecha_sancion DATE NULL,
    puntos_sancion INTEGER NULL,
    sancion NTEXT NULL,
    saldo_puntos_final INTEGER NULL,
    organismo_sancionador VARCHAR(100) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_sanciones_informe FOREIGN KEY (informe_id) 
        REFERENCES informes_dgt_automatizaciones(id) ON DELETE CASCADE
);

-- =================================================================
-- TABLAS DEPENDIENTES DE matriculas_extraidas
-- =================================================================

-- Tabla alertas_extraidas
CREATE TABLE alertas_extraidas (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    matricula_id UNIQUEIDENTIFIER NOT NULL,
    alertas_vehiculo NTEXT NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_alertas_matricula FOREIGN KEY (matricula_id) 
        REFERENCES matriculas_extraidas(id) ON DELETE CASCADE
);

-- =================================================================
-- TABLAS DEPENDIENTES DE consulta_automatizaciones
-- =================================================================

-- Tabla descarga_consulta
CREATE TABLE descarga_consulta (
    id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    id_consulta UNIQUEIDENTIFIER NOT NULL,
    url NTEXT NULL,
    id_notificacion VARCHAR(50) NULL,
    asunto_notificacion VARCHAR(50) NULL,
    organismo_notificacion VARCHAR(50) NULL,
    fecha_notificacion VARCHAR(50) NULL,
    descargada_notificacion BIT NULL,
    expediente_notificacion VARCHAR(50) NULL,
    descarga_status VARCHAR(50) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    
    -- Clave foránea
    CONSTRAINT FK_descarga_consulta FOREIGN KEY (id_consulta) 
        REFERENCES consulta_automatizaciones(id) ON DELETE CASCADE
);

-- ===========================================
-- TABLA: sedejudicial_automatizaciones
-- ===========================================
CREATE TABLE sedejudicial_automatizaciones (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    execution_id UNIQUEIDENTIFIER NOT NULL,
    num_expedientes INT NOT NULL DEFAULT 0,
    num_señalamientos INT NOT NULL DEFAULT 0,
    num_justicia_gratuita INT NOT NULL DEFAULT 0,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE()

	-- Clave foránea
    CONSTRAINT FK_sedejudicial_automatizaciones FOREIGN KEY (execution_id) 
        REFERENCES historico_automatizaciones(execution_id) ON DELETE CASCADE
);

-- ===========================================
-- TABLA: expediente_judicial
-- ===========================================
CREATE TABLE expediente_judicial (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    sedejudicial_id UNIQUEIDENTIFIER NOT NULL,
    any_expediente INT NULL,
    fecha_expediente DATETIME2 NULL,
    organo_judicial VARCHAR(255) NULL,
    procedimiento VARCHAR(255) NULL,
    numero_any_seccion VARCHAR(50) NULL,
    nig VARCHAR(50) NULL,
    ambito VARCHAR(50) NULL,
    num_demanda VARCHAR(50) NULL,
    fecha_presentacion DATETIME2 NULL,
    fecha_registro DATETIME2 NULL,
    estado_expediente VARCHAR(100) NULL,
    juzgado VARCHAR(255) NULL,
    fecha_incoacion DATETIME2 NULL,
    fase VARCHAR(100) NULL,
    tipo_quantia VARCHAR(100) NULL,
    importe_principal DECIMAL(14,2) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_expediente_sede FOREIGN KEY (sedejudicial_id)
        REFERENCES sedejudicial_automatizaciones(id)
        ON DELETE CASCADE
);

ALTER TABLE expediente_judicial
ADD justiciagratuita_id UNIQUEIDENTIFIER NULL;


ALTER TABLE expediente_judicial
ADD CONSTRAINT FK_expediente_justiciagratuita
    FOREIGN KEY (justiciagratuita_id)
    REFERENCES justiciagratuita_judicial(id)
    ON DELETE NO ACTION;


-- ===========================================
-- TABLA: otros_procedimientos_expediente
-- ===========================================
CREATE TABLE otros_procedimientos_expediente (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    expediente_judicial_id UNIQUEIDENTIFIER NOT NULL,
    fecha_procedimiento DATETIME2 NULL,
    estado_procedimiento VARCHAR(100) NULL,
    tipo_procedimiento VARCHAR(255) NULL,
    numero_año VARCHAR(50) NULL,
    organo_judicial VARCHAR(255) NULL,
    CONSTRAINT FK_otrosproc_expediente FOREIGN KEY (expediente_judicial_id)
        REFERENCES expediente_judicial(id)
        ON DELETE CASCADE
);



-- ===========================================
-- TABLA: intervinientes_expediente
-- ===========================================
CREATE TABLE intervinientes_expediente (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    expediente_judicial_id UNIQUEIDENTIFIER NOT NULL,
    nombre_interviniente VARCHAR(255) NULL,
    rol_interviniente VARCHAR(100) NULL,
    correo_electronico VARCHAR(255) NULL,
    direccion VARCHAR(255) NULL,
    poblacion VARCHAR(100) NULL,
    municipio VARCHAR(100) NULL,
    provincia VARCHAR(100) NULL,
    pais VARCHAR(100) NULL,
    codigo_postal VARCHAR(20) NULL,
    telefono VARCHAR(50) NULL,
    CONSTRAINT FK_interviniente_expediente FOREIGN KEY (expediente_judicial_id)
        REFERENCES expediente_judicial(id)
        ON DELETE CASCADE
);

-- ===========================================
-- TABLA: hitos_procesales_expediente
-- ===========================================
CREATE TABLE hitos_procesales_expediente (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    expediente_judicial_id UNIQUEIDENTIFIER NOT NULL,
    fecha_hito DATETIME2 NULL,
    descripcion_hito NTEXT NULL,
    fecha_resolucion DATETIME2 NULL,
    fecha_incoacion DATETIME2 NULL,
    CONSTRAINT FK_hito_expediente FOREIGN KEY (expediente_judicial_id)
        REFERENCES expediente_judicial(id)
        ON DELETE CASCADE
);

-- ===========================================
-- TABLA: señalamiento_judicial
-- ===========================================
CREATE TABLE señalamiento_judicial (
    id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
    sedejudicial_id UNIQUEIDENTIFIER NOT NULL,
    expediente_judicial_id UNIQUEIDENTIFIER NULL, -- puede ser NULL
    fecha_señalamiento DATETIME2 NULL,
    hora_inicio VARCHAR(10) NULL,
    hora_fin VARCHAR(10) NULL,
    sala VARCHAR(255) NULL,
    estado VARCHAR(100) NULL,
    motivo_anulacion NTEXT NULL,
    procedimiento VARCHAR(500) NULL,
    created_at DATETIME2 DEFAULT GETDATE(),
    updated_at DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT FK_senalamiento_sede FOREIGN KEY (sedejudicial_id)
        REFERENCES sedejudicial_automatizaciones(id)
        ON DELETE NO ACTION,  -- ⚠️ Evita ciclo de cascada
    CONSTRAINT FK_senalamiento_expediente FOREIGN KEY (expediente_judicial_id)
        REFERENCES expediente_judicial(id)
        ON DELETE SET NULL   -- mantiene la lógica opcional
);


-- ===========================================
-- TABLA: justiciagratuita_judicial
-- ===========================================
CREATE TABLE justiciagratuita_judicial (
	id UNIQUEIDENTIFIER DEFAULT NEWID() PRIMARY KEY,
	sedejudicial_id UNIQUEIDENTIFIER NOT NULL,
	codi_expedient NVARCHAR(100),
	organ_judicial NVARCHAR(255),
	procediment NVARCHAR(255),
	n_act NVARCHAR(100),
	estat NVARCHAR(100),
	dictamen NVARCHAR(255),
	sentit_resolucio_final NVARCHAR(255),
	tipologia_resolucio NVARCHAR(255),
	created_at DATETIME2 DEFAULT GETDATE(),
	updated_at DATETIME2 DEFAULT GETDATE(),
	CONSTRAINT FK_justiciagratuita_sede FOREIGN KEY (sedejudicial_id)
		REFERENCES sedejudicial_automatizaciones(id)
		ON DELETE CASCADE
);

-- ===========================================
-- RELACIÓN: sedejudicial_automatizaciones con historico_automatizaciones
-- (no incluida la tabla "historico_automatizaciones", se asume externa)
-- ===========================================
-- ALTER TABLE sedejudicial_automatizaciones
-- ADD CONSTRAINT FK_sede_historico FOREIGN KEY (execution_id)
-- REFERENCES historico_automatizaciones(id)
-- ON DELETE CASCADE;


-- =================================================================
-- ÍNDICES ADICIONALES PARA MEJORAR RENDIMIENTO
-- =================================================================

-- Índices en claves foráneas
CREATE INDEX IX_descargas_execution_id ON descargas_automatizaciones(execution_id);
CREATE INDEX IX_altas_execution_id ON altas_automatizaciones(execution_id);
CREATE INDEX IX_informes_execution_id ON informes_dgt_automatizaciones(execution_id);
CREATE INDEX IX_consulta_execution_id ON consulta_automatizaciones(execution_id);
CREATE INDEX IX_actualizaciones_execution_id ON actualizaciones_automatizaciones(execution_id);
CREATE INDEX IX_matriculas_informe_id ON matriculas_extraidas(informe_id);
CREATE INDEX IX_sanciones_informe_id ON sanciones_extraidas(informe_id);
CREATE INDEX IX_alertas_matricula_id ON alertas_extraidas(matricula_id);
CREATE INDEX IX_descarga_consulta_id ON descarga_consulta(id_consulta);
CREATE INDEX IX_sedejudicial_execution_id ON sedejudicial_automatizaciones (execution_id);
CREATE INDEX IX_expediente_sedejudicial_id ON expediente_judicial (sedejudicial_id);
CREATE INDEX IX_otrosproc_expediente_id ON otros_procedimientos_expediente (expediente_judicial_id);
CREATE INDEX IX_interviniente_expediente_id ON intervinientes_expediente (expediente_judicial_id);
CREATE INDEX IX_hito_expediente_id ON hitos_procesales_expediente (expediente_judicial_id);
CREATE INDEX IX_senalamiento_sede_id ON señalamiento_judicial (sedejudicial_id);
CREATE INDEX IX_senalamiento_expediente_id ON señalamiento_judicial (expediente_judicial_id);


-- Índices en campos de búsqueda frecuente
CREATE INDEX IX_historico_cliente ON historico_automatizaciones(cliente);
CREATE INDEX IX_historico_date ON historico_automatizaciones(created_at);
CREATE INDEX IX_historico_status ON historico_automatizaciones(status);
CREATE INDEX IX_historico_robot_name ON historico_automatizaciones(robot_name);
CREATE INDEX IX_matriculas_matricula ON matriculas_extraidas(matricula);
CREATE INDEX IX_otrosproc_tipo_estado ON otros_procedimientos_expediente (tipo_procedimiento, estado_procedimiento);

-- =================================================================
-- TRIGGERS PARA ACTUALIZAR updated_at AUTOMÁTICAMENTE
-- =================================================================

-- =============================================
-- TRIGGERS ACTUALIZADOS (INSERT y UPDATE)
-- =============================================

-- Trigger para historico_automatizaciones
IF OBJECT_ID('dbo.trg_historico_timestamps', 'TR') IS NOT NULL
    DROP TRIGGER dbo.trg_historico_timestamps;
GO
CREATE TRIGGER dbo.trg_historico_timestamps
ON dbo.historico_automatizaciones
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE h
    SET 
        updated_at = GETDATE(),
        created_at = ISNULL(h.created_at, GETDATE())
    FROM dbo.historico_automatizaciones h
    INNER JOIN inserted i ON h.execution_id = i.execution_id;
END;
GO


-- Trigger para descargas_automatizaciones
IF OBJECT_ID('dbo.trg_descargas_timestamps', 'TR') IS NOT NULL
    DROP TRIGGER dbo.trg_descargas_timestamps;
GO
CREATE TRIGGER dbo.trg_descargas_timestamps
ON dbo.descargas_automatizaciones
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE d
    SET 
        updated_at = GETDATE(),
        created_at = ISNULL(d.created_at, GETDATE())
    FROM dbo.descargas_automatizaciones d
    INNER JOIN inserted i ON d.id = i.id;
END;
GO


-- Trigger para altas_automatizaciones
IF OBJECT_ID('dbo.trg_altas_timestamps', 'TR') IS NOT NULL
    DROP TRIGGER dbo.trg_altas_timestamps;
GO
CREATE TRIGGER dbo.trg_altas_timestamps
ON dbo.altas_automatizaciones
AFTER INSERT, UPDATE
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE a
    SET 
        updated_at = GETDATE(),
        created_at = ISNULL(a.created_at, GETDATE())
    FROM dbo.altas_automatizaciones a
    INNER JOIN inserted i ON a.id = i.id;
END;
GO


-- =================================================================
-- COMENTARIOS EN TABLAS Y COLUMNAS (OPCIONAL)
-- =================================================================

-- Agregar descripciones a las tablas
EXEC sp_addextendedproperty 
    'MS_Description', 'Tabla principal que almacena el histórico de todas las automatizaciones ejecutadas',
    'SCHEMA', 'dbo', 'TABLE', 'historico_automatizaciones';

EXEC sp_addextendedproperty 
    'MS_Description', 'Almacena detalles específicos de las automatizaciones de descarga',
    'SCHEMA', 'dbo', 'TABLE', 'descargas_automatizaciones';

EXEC sp_addextendedproperty 
    'MS_Description', 'Almacena detalles específicos de las automatizaciones de altas',
    'SCHEMA', 'dbo', 'TABLE', 'altas_automatizaciones';

-- =============================================
-- SELECT TOP 1 DE CADA TABLA
-- =============================================

	-- Tabla principal
	SELECT TOP 1 * FROM historico_automatizaciones ORDER BY created_at DESC;

	-- Tablas dependientes directas
	SELECT TOP 1 * FROM descargas_automatizaciones ORDER BY created_at DESC;
	SELECT TOP 1 * FROM altas_automatizaciones ORDER BY created_at DESC;
	SELECT TOP 1 * FROM informes_dgt_automatizaciones ORDER BY created_at DESC;
	SELECT TOP 1 * FROM consulta_automatizaciones ORDER BY created_at DESC;
	SELECT TOP 1 * FROM actualizaciones_automatizaciones ORDER BY created_at DESC;
	SELECT TOP 1 * FROM sedejudicial_automatizaciones ORDER BY created_at DESC;

	-- Tablas dependientes de informes_dgt_automatizaciones
	SELECT TOP 1 * FROM matriculas_extraidas ORDER BY created_at DESC;
	SELECT TOP 1 * FROM sanciones_extraidas ORDER BY created_at DESC;

	-- Tablas dependientes de matriculas_extraidas
	SELECT TOP 1 * FROM alertas_extraidas ORDER BY created_at DESC;

	-- Tablas dependientes de consulta_automatizaciones
	SELECT TOP 1 * FROM descarga_consulta ORDER BY created_at DESC;

	-- Tablas dependientes de sedejudicial_automatizaciones
	SELECT TOP 1 * FROM expediente_judicial ORDER BY created_at DESC;
	SELECT TOP 1 * FROM otros_procedimientos_expediente;
	SELECT TOP 1 * FROM intervinientes_expediente;
	SELECT TOP 1 * FROM hitos_procesales_expediente;
	SELECT TOP 1 * FROM señalamiento_judicial ORDER BY created_at DESC;


-- =============================================
-- DROP DE CADA TABLA
-- =============================================
/*
-- Tablas Sede Judicial
IF OBJECT_ID('señalamiento_judicial', 'U') IS NOT NULL
    DROP TABLE señalamiento_judicial;

IF OBJECT_ID('hitos_procesales_expediente', 'U') IS NOT NULL
    DROP TABLE hitos_procesales_expediente;

IF OBJECT_ID('intervinientes_expediente', 'U') IS NOT NULL
    DROP TABLE intervinientes_expediente;

IF OBJECT_ID('otros_procedimientos_expediente', 'U') IS NOT NULL
    DROP TABLE otros_procedimientos_expediente;

IF OBJECT_ID('expediente_judicial', 'U') IS NOT NULL
    DROP TABLE expediente_judicial;

IF OBJECT_ID('sedejudicial_automatizaciones', 'U') IS NOT NULL
    DROP TABLE sedejudicial_automatizaciones;



-- Tablas dependientes de consulta_automatizaciones
IF OBJECT_ID('descarga_consulta', 'U') IS NOT NULL
    DROP TABLE descarga_consulta;

-- Tablas dependientes de matriculas_extraidas
IF OBJECT_ID('alertas_extraidas', 'U') IS NOT NULL
    DROP TABLE alertas_extraidas;

-- Tablas dependientes de informes_dgt_automatizaciones
IF OBJECT_ID('matriculas_extraidas', 'U') IS NOT NULL
    DROP TABLE matriculas_extraidas;

IF OBJECT_ID('sanciones_extraidas', 'U') IS NOT NULL
    DROP TABLE sanciones_extraidas;

-- Tablas dependientes directas
IF OBJECT_ID('descargas_automatizaciones', 'U') IS NOT NULL
    DROP TABLE descargas_automatizaciones;

IF OBJECT_ID('altas_automatizaciones', 'U') IS NOT NULL
    DROP TABLE altas_automatizaciones;

IF OBJECT_ID('informes_dgt_automatizaciones', 'U') IS NOT NULL
    DROP TABLE informes_dgt_automatizaciones;

IF OBJECT_ID('consulta_automatizaciones', 'U') IS NOT NULL
    DROP TABLE consulta_automatizaciones;

IF OBJECT_ID('actualizaciones_automatizaciones', 'U') IS NOT NULL
    DROP TABLE actualizaciones_automatizaciones;

-- Tabla principal
IF OBJECT_ID('historico_automatizaciones', 'U') IS NOT NULL
    DROP TABLE historico_automatizaciones;
*/

-- =================================================================
-- TABLA: automations_assignment_log
-- =================================================================
CREATE TABLE automations_assignment_log (
    id VARCHAR(255) PRIMARY KEY,
    cliente VARCHAR(255) NULL,
    sede VARCHAR(255) NULL,
    robot_name VARCHAR(100) NOT NULL,
    assigned_at DATETIME2 DEFAULT GETDATE(),
    assigned_by VARCHAR(100) NOT NULL
);

CREATE INDEX IX_automations_assignment_robot ON automations_assignment_log(robot_name);
CREATE INDEX IX_automations_assignment_by ON automations_assignment_log(assigned_by);