IF OBJECT_ID('dbo.rueda_consultas_job_proc', 'P') IS NOT NULL
    DROP PROCEDURE dbo.rueda_consultas_job_proc;
GO

CREATE PROCEDURE dbo.rueda_consultas_job_proc
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

    ;WITH clientes_neo AS (
        SELECT DISTINCT
            c.numerocliente,
            COALESCE(
				c.NombreComercial, 
				COALESCE(c.NombreFiscal,
				NULLIF(LTRIM(RTRIM(
					ISNULL(NULLIF(Nombre,''),'')
					+ CASE WHEN ISNULL(Apellido1,'') = '' THEN '' ELSE ' ' + Apellido1 END
					+ CASE WHEN ISNULL(Apellido2,'') = '' THEN '' ELSE ' ' + Apellido2 END
				  )), ''))
			) AS nombre_cliente,
			cm.valid_from,
			cm.valid_up_to,
			cm.[state],
			cm.result AS cm_result
		FROM dbo.clientes c
		LEFT JOIN certificates_managements_ cm
			ON cm.customer_number = c.numerocliente
		WHERE c.numerocliente > 0
		  AND c.baja = 0
		  AND (
				EXISTS (
					SELECT 1
					FROM info.BeneficiarioBonos ibb
					WHERE ibb.idbenef = c.numerocliente
					  AND ibb.situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP')
					  AND ibb.fechafin >= DATEADD(DAY,-3,GETDATE())
					  AND (
							ibb.servicio LIKE '%SUSCRIPCION%'
						 OR ibb.servicio LIKE '%NEO%'
						 OR ibb.servicio LIKE '%BLINDAJE%'
					  )
				)
				OR EXISTS (
					SELECT 1
					FROM sin_servicio_contratado ssc
					WHERE ssc.customer_number = c.numerocliente
					  AND ssc.[TO] >= DATEADD(DAY,-3,GETDATE())
					  AND (
							ssc.Oferta LIKE '%GRATIS%'
						 OR ssc.Oferta LIKE '%SUSCRIPCION%'
						 OR ssc.Oferta LIKE '%NEO%'
						 OR ssc.Oferta LIKE '%BLINDAJE%'
					  )
				)
		  )
    )

    MERGE dbo.controlpasorobot WITH (HOLDLOCK) AS tgt
	USING clientes_neo AS src
	   ON tgt.cliente = src.numerocliente
	  AND ISNULL(tgt.sede,'') = 'enotum'

	WHEN MATCHED THEN
		UPDATE SET
			tgt.fecha_rueda = GETDATE(),
			tgt.resultado =
				CASE
					WHEN src.numerocliente IS NULL
					  OR (src.valid_from IS NULL
						  AND src.valid_up_to IS NULL
						  AND src.[state] IS NULL
						  AND src.cm_result IS NULL)
					  OR src.valid_from > GETDATE()
					  OR src.valid_up_to < GETDATE()
					  OR ISNULL(src.[state],'') <> 'Completado'
					  OR ISNULL(src.cm_result,'') <> 'Vigente'
					THEN 'No hay certificado vigente'
					ELSE tgt.resultado
				END

	WHEN NOT MATCHED BY TARGET THEN
		INSERT (
			id,
			cliente,
			nombre_cliente,
			sede,
			resultado,
			fechapaso,
			notas,
			usuario,
			fecha_rueda
		)
		VALUES (
			NEWID(),
			src.numerocliente,
			src.nombre_cliente,
			'enotum',
			'No hay certificado vigente',
			NULL,
			NULL,
			NULL,
			GETDATE()
		);


    COMMIT TRANSACTION;
END
GO

EXEC msdb.dbo.sp_add_job
    @job_name = N'rueda_consultas_weekly',
    @enabled = 1;

EXEC msdb.dbo.sp_add_jobstep
    @job_name = N'rueda_consultas_weekly',
    @step_name = N'Ejecutar procedimiento',
    @subsystem = N'TSQL',
    @command = N'EXEC dbo.rueda_consultas_job_proc;';

EXEC msdb.dbo.sp_add_schedule
    @schedule_name = N'rueda_consultas_weekly_schedule',
    @freq_type = 8,
    @freq_interval = 2,          -- Monday
    @freq_recurrence_factor = 1,
    @active_start_time = 010000;

EXEC msdb.dbo.sp_attach_schedule
    @job_name = N'rueda_consultas_weekly',
    @schedule_name = N'rueda_consultas_weekly_schedule';

EXEC msdb.dbo.sp_add_jobserver
    @job_name = N'rueda_consultas_weekly';


SELECT 
    j.name AS JobName,
    s.name AS ScheduleName,
    s.freq_type,
    s.freq_interval,
    s.freq_recurrence_factor,
    s.active_start_time
FROM msdb.dbo.sysjobs j
JOIN msdb.dbo.sysjobschedules js ON j.job_id = js.job_id
JOIN msdb.dbo.sysschedules s ON js.schedule_id = s.schedule_id
WHERE j.name = 'rueda_consultas_weekly';