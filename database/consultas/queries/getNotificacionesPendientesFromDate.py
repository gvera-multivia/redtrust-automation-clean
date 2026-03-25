getNotificacionesPendientesFromDate = """
SET LANGUAGE English;

WITH servicios_union AS (
    SELECT 
        idbenef AS customer_number,
        servicio AS nombre_servicio,
        fechafin
    FROM info.beneficiariobonos 
    WHERE 
        (servicio LIKE '%SUSCRIPCION%' OR servicio LIKE '%NEO%' OR servicio LIKE '%BLINDAJE%')
        AND fechafin > GETDATE()-1
        AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP')
		AND idbenef = %s
    UNION
    SELECT 
        customer_number,
        Oferta AS nombre_servicio,
        [TO] as fechafin
    FROM sin_servicio_contratado
    WHERE 
        [TO] > GETDATE()-1
        AND (Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%' OR Oferta LIKE '%GRATIS%')
		AND customer_number = %s
)
,servicios_activos AS (
    SELECT 
        su.customer_number AS idbenef,
        STUFF((
            SELECT DISTINCT '; ' + su2.nombre_servicio
            FROM servicios_union su2
            WHERE su2.customer_number = su.customer_number
            FOR XML PATH(''), TYPE
        ).value('.', 'NVARCHAR(MAX)'), 1, 2, '') AS servicios_activos,
        su.fechafin
    FROM servicios_union su
    GROUP BY su.customer_number, su.fechafin
)
,consulta_base AS (
    SELECT 
		em.customer_number,
        em.message_id,
		em.message_key,
		sa.servicios_activos as servicio,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%SUSCRIPCION%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE() 
         ORDER BY fechafin DESC) AS SUSCRIPCION,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%NEO_CASH%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE() 
         ORDER BY fechafin DESC) AS NEOCASH,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%NEO_ESTATAL%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE() 
         ORDER BY fechafin DESC) AS NEOESTATAL,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%MULTI-NEO%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE() 
         ORDER BY fechafin DESC) AS MULTINEO,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%INFO_NEO%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE() 
         ORDER BY fechafin DESC) AS INFONEO,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%BLINDAJE%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > GETDATE()
         ORDER BY fechafin DESC) AS BLINDAJE,
        (SELECT TOP 1 [TO] 
         FROM sin_servicio_contratado 
         WHERE customer_number = em.customer_number 
           AND [TO] > GETDATE() 
           AND (Oferta LIKE '%GRATIS%' OR Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%')
         ORDER BY [TO] DESC) AS GRATIS,
        em.date,
        em.expired_date,
        cs.sede,
        em.customer_number AS client_id,
        c.nif AS nif,
		es.id as status_id,
		es.name AS status,
		dsc.especial as aviso_especial,
        em.[from] AS mail,
        em.subject AS asunto,
        em.body_html
    FROM [dbo].[emails_messages] em
	INNER JOIN servicios_activos sa
		ON sa.idbenef = em.customer_number
    INNER JOIN [dbo].[clientes] c
        ON em.customer_number = c.numerocliente
    LEFT JOIN [dbo].[certificates_sedes_cat] cs 
        ON em.sedes_cat_id = cs.id
    LEFT JOIN [dbo].[emails_status] es
        ON em.status_id = es.id
	LEFT JOIN descargaespecial dsc 
		ON dsc.cliente = em.customer_number
    WHERE 
        LOWER(cs.sede) IN (%s , %s) 
		AND em.customer_number IS NOT NULL
        AND em.body_html IS NOT NULL
		AND em.[date] >= CONVERT(DATE, %s)
)
SELECT *
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY message_id ORDER BY date ASC) AS rn
    FROM consulta_base
) t
WHERE t.rn = 1
ORDER BY t.date ASC
OPTION (RECOMPILE);

"""
