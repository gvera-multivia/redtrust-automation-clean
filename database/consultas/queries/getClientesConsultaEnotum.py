getClientesConsultaEnotum_paquete = """
DECLARE @total_clientes INT;
DECLARE @paquete INT;
DECLARE @fecha_revision VARCHAR(10); 
SET @fecha_revision = NULL;  

WITH ConsultaEnotum AS (
  SELECT 
    cm.customer_number AS cliente,
    cm.customer_number_type AS tipo_cliente,
    cs.certificate_id,
	  dse.especial,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%SUSCRIPCION%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE() 
     ORDER BY fechafin DESC) AS SUSCRIPCION,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%NEO_CASH%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE() 
     ORDER BY fechafin DESC) AS NEOCASH,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%NEO_ESTATAL%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE() 
     ORDER BY fechafin DESC) AS NEOESTATAL,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%MULTI-NEO%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE() 
     ORDER BY fechafin DESC) AS MULTINEO,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%INFO_NEO%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE() 
     ORDER BY fechafin DESC) AS INFONEO,
    (SELECT TOP 1 fechafin 
     FROM info.BeneficiarioBonos 
     WHERE idbenef = cm.customer_number 
       AND servicio LIKE '%BLINDAJE%' 
       AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
       AND fechafin > GETDATE()
     ORDER BY fechafin DESC) AS BLINDAJE,
    (SELECT TOP 1 [TO] 
     FROM sin_servicio_contratado 
     WHERE customer_number = cm.customer_number 
       AND [TO] > GETDATE() 
       AND (Oferta LIKE '%GRATIS%' OR Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%')
     ORDER BY [TO] DESC) AS GRATIS,
    COALESCE(cm.organization_name, cm.manager) AS name,
    cm.recipient_name AS recipient_name,
    cm.cif AS cif,
    cm.nif AS nif,
    cm.state,
    lower(cs.sede) AS sede,
    cm.valid_from,
    cm.valid_up_to
  FROM certificates_sedes cs 
    INNER JOIN certificates_managements_ cm ON cm.id = cs.certificate_id
    LEFT JOIN clientes c ON c.numerocliente = cm.customer_number
    LEFT JOIN certificates_managements_emails cme ON cme.customer_number = cm.customer_number
	  LEFT JOIN descargaespecial dse ON dse.cliente = cm.customer_number
  WHERE 1=1
    AND cs.sede = 'ENOTUM'
    AND NOT EXISTS (
        SELECT 1 FROM automations_assignment_log aal
        WHERE aal.id = 'consulta_' + CAST(cm.customer_number AS VARCHAR(50)) + '_' + LOWER(cs.sede)
        AND aal.robot_name = 'RobotConsulta'
    )
    AND cm.result = 'Vigente' 
    AND cm.state = 'Completado'
    AND cm.valid_from <= GETDATE()
    AND cm.valid_up_to >= GETDATE()
),
CertificadosConAcciones AS (
  SELECT certificate_id, COUNT(*) AS acciones_pendientes
  FROM ConsultaEnotum
  WHERE 
    NEOESTATAL IS NOT NULL OR
    NEOCASH IS NOT NULL OR
    MULTINEO IS NOT NULL OR
    INFONEO IS NOT NULL OR
    SUSCRIPCION IS NOT NULL OR
    BLINDAJE IS NOT NULL OR
    GRATIS IS NOT NULL
  GROUP BY certificate_id
),
UltimoPasoRobot AS (
  SELECT 
    cliente as numcli,
    fechapaso,
    fecha_rueda,
    id AS idConsulta
    FROM (
        SELECT 
            id,
			cliente,
            fechapaso,
			      fecha_rueda,
            ROW_NUMBER() OVER (PARTITION BY cliente ORDER BY fechapaso DESC) as rn
        FROM controlpasorobot
    ) ranked
    WHERE rn = 1
),
ClientesConPrioridad AS (
  SELECT 
    upr.idConsulta,
    CASE 
      WHEN upr.fechapaso IS NULL THEN DATEADD(day, -30, GETDATE())
      WHEN upr.fechapaso < DATEADD(day, -30, GETDATE()) THEN DATEADD(day, -30, GETDATE())
      WHEN @fecha_revision IS NOT NULL AND CONVERT(DATE, @fecha_revision, 120) < CONVERT(DATE, upr.fechapaso, 120) THEN CONVERT(DATETIME,  @fecha_revision, 120)
      ELSE upr.fechapaso
    END AS fecha_revision,
    upr.fecha_rueda,
    ce.*,
    cca.acciones_pendientes,
    ROW_NUMBER() OVER (PARTITION BY ce.cliente ORDER BY cca.acciones_pendientes DESC, ce.certificate_id) AS rn
  FROM ConsultaEnotum ce
  JOIN CertificadosConAcciones cca ON ce.certificate_id = cca.certificate_id
  LEFT JOIN UltimoPasoRobot upr ON ce.cliente = upr.numcli
  WHERE 
    (ce.NEOESTATAL IS NOT NULL OR
    ce.NEOCASH IS NOT NULL OR
    ce.MULTINEO IS NOT NULL OR
    ce.INFONEO IS NOT NULL OR
    ce.SUSCRIPCION IS NOT NULL OR
    ce.BLINDAJE IS NOT NULL OR
    ce.GRATIS IS NOT NULL)
	AND idConsulta IS NOT NULL
)
  SELECT TOP (
    COALESCE(
      NULLIF((SELECT COUNT(*)/7 FROM ClientesConPrioridad WHERE rn = 1), 0),
      1
    )
  ) *,
  STUFF(
    CASE WHEN SUSCRIPCION IS NOT NULL THEN ';SUSCRIPCION' ELSE '' END +
    CASE WHEN NEOCASH IS NOT NULL THEN ';NEOCASH' ELSE '' END +
    CASE WHEN NEOESTATAL IS NOT NULL THEN ';NEOESTATAL' ELSE '' END +
    CASE WHEN MULTINEO IS NOT NULL THEN ';MULTINEO' ELSE '' END +
    CASE WHEN INFONEO IS NOT NULL THEN ';INFONEO' ELSE '' END +
    CASE WHEN BLINDAJE IS NOT NULL THEN ';BLINDAJE' ELSE '' END +
    CASE WHEN GRATIS IS NOT NULL THEN ';GRATIS' ELSE '' END
  , 1, 1, '') AS servicio
FROM ClientesConPrioridad
WHERE rn = 1
ORDER BY fecha_revision ASC, acciones_pendientes DESC, cliente, certificate_id;
"""
