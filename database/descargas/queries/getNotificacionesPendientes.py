getNotificacionesPendientes = """
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
    UNION
    SELECT 
        customer_number,
        Oferta AS nombre_servicio,
        [TO] as fechafin
    FROM sin_servicio_contratado
    WHERE 
        [TO] > GETDATE()-1
        AND (Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%' OR Oferta LIKE '%GRATIS%')
),
servicios_activos AS (
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
),
consulta_base AS (
    SELECT 
        ea.email AS email_account,
        em.message_key,
        em.message_id,
        em.date,
        em.expired_date,
        cs.sede,
        em.customer_number AS client_id,
        dsce.especial AS aviso_especial,
        ssc.customer_number AS checkscc,
        cm.organization_name AS client_name,
        cm.recipient_name,
        c.provincia,
        sa.servicios_activos AS servicio,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%SUSCRIPCION%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS SUSCRIPCION,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%NEO_CASH%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS NEOCASH,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%NEO_ESTATAL%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS NEOESTATAL,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%MULTI-NEO%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS MULTINEO,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%INFO_NEO%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS INFONEO,
        (SELECT TOP 1 fechafin 
         FROM info.BeneficiarioBonos 
         WHERE idbenef = em.customer_number 
           AND servicio LIKE '%BLINDAJE%' 
           AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') 
           AND fechafin > em.[date] 
         ORDER BY fechafin DESC) AS BLINDAJE,
        (SELECT TOP 1 [TO] 
         FROM sin_servicio_contratado 
         WHERE customer_number = em.customer_number 
           AND [TO] > em.[date] 
           AND (Oferta LIKE '%GRATIS%' OR Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%')
         ORDER BY [TO] DESC) AS GRATIS,
        c.nif AS nif,
        c.nifempresa AS cif,
        tc.concepto AS tipo_cliente,
        es.name AS status,
        em.[from] AS mail,
        em.subject AS asunto,
        em.body_html
    FROM [dbo].[emails_messages] em
    INNER JOIN [dbo].[emails_accounts] ea 
        ON em.email_account_id = ea.id
    INNER JOIN [dbo].[certificates_sedes_cat] cs 
        ON em.sedes_cat_id = cs.id
    INNER JOIN [dbo].[clientes] c
        ON em.customer_number = c.numerocliente
    INNER JOIN [dbo].[emails_status] es
        ON em.status_id = es.id
    LEFT JOIN descargaespecial dsce
		ON dsce.cliente = em.customer_number
    LEFT JOIN sin_servicio_contratado ssc
        ON em.customer_number = ssc.customer_number
    LEFT JOIN servicios_activos sa 
        ON sa.idbenef = em.customer_number
    INNER JOIN certificates_managements_ cm
        ON cm.customer_number = em.customer_number
    LEFT JOIN tblvTipoCliente tc
        ON tc.idTipoCliente = c.tipodecliente
    WHERE 
        em.customer_number IS NOT NULL
        AND em.parent_id IS NULL
        /* DATE_FILTER_START */AND CONVERT(DATE, em.[date]) = 
            CASE 
                WHEN es.name = 'Pendiente' THEN %s
                WHEN es.name = 'Agencia Tributaria' THEN CONVERT(DATE, DATEADD(DAY, -8, %s))
            END    /* DATE_FILTER_END */
        AND LOWER(cs.sede) IN (%s, %s, %s) 
        AND em.body_html IS NOT NULL
        AND es.name IN ('Pendiente', 'Agencia Tributaria')
        AND (
            EXISTS (
                SELECT 1 FROM info.BeneficiarioBonos ibb_chk
                WHERE ibb_chk.idbenef = em.customer_number
                AND (
                    ibb_chk.servicio LIKE '%SEDES BIANUAL%' 
                    OR ibb_chk.servicio LIKE '%SUSCRIPCION SEDES%' 
                    OR ibb_chk.servicio LIKE '%NEO%' 
                    OR ibb_chk.servicio LIKE '%BLINDAJE%'
                )
            )
            OR (
                ssc.Oferta LIKE '%SEDES BIANUAL%' 
                OR ssc.Oferta LIKE '%SUSCRIPCION SEDES%' 
                OR ssc.Oferta LIKE '%NEO%' 
                OR ssc.Oferta LIKE '%BLINDAJE%'
            )
        )
        AND EXISTS (
            SELECT 1 FROM info.BeneficiarioBonos ibb_chk2
            WHERE ibb_chk2.idbenef = em.customer_number
            AND ibb_chk2.situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP')
        )
        AND c.baja = 0
        AND c.numerocliente > 0
        AND cm.result = 'Vigente'
        AND cm.[state] = 'Completado'
        AND cm.valid_from <= GETDATE()
        AND cm.valid_up_to >= GETDATE()
        AND (em.UsuarioAsignado IS NULL OR em.UsuarioAsignado = 'Adría Martínez')
        AND (
            (
                EXISTS (
                    SELECT 1 FROM info.BeneficiarioBonos ibb_dates
                    WHERE ibb_dates.idbenef = em.customer_number
                    AND ibb_dates.fechafin > em.[date]
                    AND ibb_dates.fechafin > GETDATE()
                )
            )
            OR (ssc.[to] > em.[date] AND ssc.[to] > GETDATE())
        )
)
SELECT TOP %s * 
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY message_id ORDER BY date ASC) AS rn
    FROM consulta_base
) t
WHERE t.rn = 1
ORDER BY t.date ASC
OPTION (RECOMPILE);
"""
