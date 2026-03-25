getNotificacionesDehu = """
    SELECT 
        em.message_key
    FROM [dbo].[emails_messages] em
    INNER JOIN [dbo].[certificates_sedes_cat] cs 
        ON em.sedes_cat_id = cs.id
    INNER JOIN [dbo].[emails_status] es
        ON em.status_id = es.id
    WHERE 
        em.customer_number IS NOT NULL
        AND em.parent_id IS NULL
        AND em.date >= GETDATE() - %s AND em.date < GETDATE()-1
        AND LOWER(cs.sede) IN (%SEDES_PLACEHOLDER%)
        AND em.body_html IS NOT NULL
        AND es.name IN ('Pendiente')
        AND (em.UsuarioAsignado IS NULL OR em.UsuarioAsignado = 'Adría Martínez')
"""
