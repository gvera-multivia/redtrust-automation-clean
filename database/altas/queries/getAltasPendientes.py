getAltasPendientes = """          
	WITH AltasSedes AS (
		Select 
			*
		From
			certificates_sedes cs
		Where
			cs.sede IN ({sedes_placeholder})
			AND cs.action IS NULL			
			AND (cs.state IS NULL or cs.state = 1)
		
	)
	,AltasPendientes AS (
		SELECT 
			cm.customer_number AS cliente,
			cm.customer_number_type AS tipo_cliente,
			cs.certificate_id,
			(SELECT TOP 1 oferta FROM vstbeneficiarios_I vi WHERE vi.idbenef = cm.customer_number AND FechaFinContrato > GETDATE()) AS INFONEO,
			(SELECT TOP 1 oferta FROM vstbeneficiarios_M vm WHERE vm.idbenef = cm.customer_number AND FechaFinContrato > GETDATE()) AS MULTINEO,
			(SELECT TOP 1 oferta FROM vstbeneficiarios_N vn WHERE vn.idbenef = cm.customer_number AND FechaFinContrato > GETDATE()) AS NEO,
			(SELECT TOP 1 oferta FROM vstbeneficiarios_S vs WHERE vs.idbenef = cm.customer_number AND FechaFinContrato > GETDATE()) AS SUSCRIPCION,
			(SELECT TOP 1 'BLINDAJE' FROM info.BeneficiarioBonos WHERE idbenef = cm.customer_number AND servicio LIKE '%BLINDAJE%' AND situacion IN ('COBRADO','COBRADO (RECUPERADO)','PENDIENTE VT','ESPECIAL HP') AND fechafin > GETDATE()  ORDER BY fechafin DESC) AS BLINDAJE,
			(SELECT TOP 1 'GRATIS' FROM sin_servicio_contratado WHERE customer_number = cm.customer_number AND [TO] > GETDATE() AND (Oferta LIKE '%GRATIS%' OR Oferta LIKE '%SUSCRIPCION%' OR Oferta LIKE '%NEO%' OR Oferta LIKE '%BLINDAJE%') ORDER BY [TO] DESC) AS GRATIS,
			cm.organization_name AS name,
			cm.manager,
			cm.recipient_name AS recipient_name,
			lower(c.provincia) AS provincia,
			CASE
				WHEN lower(c.provincia) IN ('barcelona', 'girona', 'lleida', 'tarragona') THEN 1
				WHEN lower(c.provincia) = 'islas baleares' THEN 2
				ELSE 3
			END AS grupo,
			lower(c.poblacion) AS poblacion,
			c.Cpostal,
			c.calle,
			cm.cif AS CIF,
			cm.nif AS NIF,
			cm.state,
			lower(cs.sede) AS sede,
			cs.sedes_cat_id AS sede_id, 
			cs.url,
			cs.n_emails,
			CASE 
				WHEN cs.sede = 'CEUTA' THEN 
					CASE 
						WHEN c.suscremail IS NOT NULL THEN c.suscremail
						ELSE 'info@xvia-serviciosjuridicos.com'
					END
				WHEN c.suscremail IS NOT NULL THEN c.suscremail
				WHEN cme.emails IS NOT NULL THEN cme.emails
				ELSE 'notificaciones@xvia-serviciosjuridicos.com'
			END AS emails,
			cs.created_at,
			cm.valid_from,
			cm.valid_up_to
		FROM AltasSedes cs 
			INNER JOIN certificates_managements_ cm ON cm.id = cs.certificate_id
			LEFT JOIN clientes c ON c.numerocliente = cm.customer_number
			LEFT JOIN certificates_managements_emails cme ON cme.customer_number = cm.customer_number
		WHERE
        	--AND cm.asigned = 1 
			cm.result = 'Vigente' 
			AND cm.state = 'Completado'
			AND ((cm.UsuarioAsignado IS NULL AND cm.[user_id] is NULL AND cm.asigned IN (0, 1)) or (cm.[user_id] = 78 AND cm.UsuarioAsignado = 'Adría Martínez'))
			AND cm.valid_from <= GETDATE()
			AND cm.valid_up_to >= GETDATE()
			AND NOT (
				(lower(c.provincia) IN ('barcelona', 'girona', 'lleida', 'tarragona') AND lower(cs.sede) IN ('baleares', 'mahon'))
				OR (lower(c.provincia) = 'illes balears' AND lower(cs.sede) IN ('xaloc', 'oficina virtual ayuntamiento terrassa'))
				OR (lower(c.provincia) NOT IN ('barcelona', 'girona', 'lleida', 'tarragona', 'illes balears') AND lower(cs.sede) IN ('baleares', 'mahon', 'xaloc', 'oficina virtual ayuntamiento terrassa'))
			)
            AND NOT EXISTS (
				SELECT 1 FROM automations_assignment_log aal
				WHERE aal.id = 'alta_' + CAST(cm.customer_number AS VARCHAR(50)) + '_' + LOWER(cs.sede)
				AND aal.robot_name = 'RobotAltas'
			)
            AND c.Cpostal IS NOT NULL
            AND c.poblacion IS NOT NULL
			AND c.provincia IS NOT NULL
            AND c.calle IS NOT NULL
			{cliente_filter}
	)
    -- Aquí se seleccionan los certificate_id con más acciones pendientes
	-- y se limita a los primeros 5 para evitar sobrecargar la consulta
	,TopCertificates AS (
		SELECT TOP ({limit}) certificate_id
		FROM AltasPendientes
		WHERE
			NEO IS NOT NULL OR
			MULTINEO IS NOT NULL OR
			INFONEO IS NOT NULL OR
			SUSCRIPCION IS NOT NULL OR
			BLINDAJE IS NOT NULL OR
			GRATIS IS NOT NULL
		GROUP BY certificate_id
		ORDER BY COUNT(*) DESC
	)
	SELECT ap.*
	FROM AltasPendientes ap
	INNER JOIN TopCertificates tc
		ON ap.certificate_id = tc.certificate_id
	WHERE
		ap.NEO IS NOT NULL OR
		ap.MULTINEO IS NOT NULL OR
		ap.INFONEO IS NOT NULL OR
		ap.SUSCRIPCION IS NOT NULL OR
		ap.BLINDAJE IS NOT NULL OR
		ap.GRATIS IS NOT NULL
	ORDER BY ap.certificate_id, ap.cliente, ap.sede_id;
"""

