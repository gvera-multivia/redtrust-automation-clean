# Organization-specific expediente patterns
ORG_EXPEDIENTE_PATTERNS = {
    # Agencia Tributaria
    "Agencia Tributaria": [
        (r"\(Expediente/Referencia\):\s*([A-Za-z0-9]{15,20})", "(Expediente/Referencia)"),  # Matches first code only
        (r"Número de expediente:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Número de expediente"),
        (r"expediente\s*([A-Za-z0-9\-\/\. ]{4,20})", "expediente"),
        (r"Referencia:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Referencia"),
        (r"Nº\s*Certificado\s*:?\s*([A-Za-z0-9\-\/]{10,15})", "Nº Certificado"),
        (r"N\*\s*Certificado\s*:?\s*([A-Za-z0-9\-\/]{10,15})", "N* Certificado"),
        (r"Ne Comunicación:\s*([0-9]{13})", "Ne Comunicación"),
        (r"CIP:\s*(ES\d{5}[A-Z]{2}\d{3}[A-Z])", "CIP"),
        (r"Número de acuerdo de compensación:\s*([A-Za-z0-9]{13})", "Número de acuerdo de compensación"),
    ],
    # Agencia Tributaria Catalunya
    "Agencia Tributaria Catalunya": [
        (r"EXP\s{1,2}(DIL)\d{4}", "EXP DILxxxx"),
        (r"EXP\s{1,2}(945)\d{4}", "EXP 945xxxx"),
        (r"EXP\s{1,2}(939)\d{4}", "EXP 939xxxx"),
    ],
    # Ajuntament de Barcelona
    "Ajuntament de Barcelona": [
        (r"\b(DH\d{10,15})\b", "DH Pattern"),
        (r"\b(EB\d{10,15})\b", "EB Pattern"),
        (r"\b(EI\d{10,15})\b", "EI Pattern"),
        (r"Núm\. expediente:\s*[\s]*([A-Za-z0-9]{4,20})", "Núm. expediente"),
        (r"Núm\. d'expedient:\s*[\s]*([A-Za-z0-9]{4,20})", "Num. d'expedient"),
        (r"Expedient:\s*([A-Za-z0-9]{4,20})", "Expedient"),
    ],
    # Ajuntament de Manresa
    "Ajuntament de Manresa": [],
    # Ajuntament de Parets del Vallès
    "Ajuntament de Parets del Vallès": [],
    # Ajuntaments de Catalunya
    "Ajuntaments de Catalunya": [
        (r"Expedient núm\.:\s*([A-Za-z0-9]{4,20})", "Expedient núm."),
        (r"Expedient:\s*([A-Za-z0-9]{4,20})", "Expedient"),
    ],
    # Ayuntamientos (genéricos)
    "Ayuntamientos Varios": {        
        "Begur": [
            (r"Expedient:\s*([\w\-/]+)", "Expedient Begur"),
        ],
        "Baix Empordà": [
            (r"Expedient\s*(\d{4}\s*/\s*\d{4})", "Expedient Baix Empordà"),
        ]
    },
    # Ayuntamiento de Gijon
    "Ayuntamiento de Gijon": [],
    # Ayuntamiento de Terrassa
    "Ayuntamiento de Terrassa": [],
    # Ayuntaminto de Madrid
    "Ayuntaminto de Madrid": [],
    # Ayuntamiento de Peñíscola
    "Ayuntamiento de Peñíscola": [
        (r"Expediente\s+Agente/Controlador Matrícula Marca y modelo\s*([0-9]{4}/[A-Za-z0-9]+)", "Expediente numérico/letras"),
        (r"^([0-9]{4}/[0-9]+[A-Z]?)", "Expediente clásico"),
    ],
    "Ayuntamiento de Sant Adria de Besos": [            
        (r"resoluci[oó]\s*n[º°]?\s*([0-9]{10})", "Resolució número"),
        (r"Número de registre:\s*([0-9]{10})", "Número de registre"),
        (r"EXPEDIENT NÚM\.CM\s*([0-9]{2}/[0-9]{4})", "EXPEDIENT NÚM.CM"),
    ],
    "Ayuntamiento de Valencia": [
        # (r"(MU\s*\d{4}\s*\w{2}\s*\w{4,8}\s*\w{1,2})", "Expediente MU"),
        (r"(MU\s*\d{4}\s*\d{2}\s*\d{8}\s*\d{1})", "Expediente MU"),
        (r"PROCEDIX DE L'EXPEDIENT:\s*(MU\s*\d{4}\s*\w{2}\s*\w{4,8}\s*\w{1,2})", "PROCEDIX DE L'EXPEDIENT MU"),
        (r"PROCEDE DEL EXPEDIENTE:\s*(MU\s*\d{4}\s*\w{2}\s*\w{4,8}\s*\w{1,2})", "PROCEDE DEL EXPEDIENTE MU"),
    ],
    "Consell Comarcal La Selva": [    
        (r"Expedient executiu:\s*([A-Za-z0-9/\-_.]{4,15})", "Expedient executiu"),
        (r"l'expedient administratiu de constrenyiment núm\.?\s*([0-9]+)", "Expedient constrenyiment núm."),
        (r"expedient administratiu.{0,30}?n[uú]m\.?\s*([A-Za-z0-9\-\/\. ]{4,20})", "Expedient administratiu núm."),
    ],
    # Departament d'Empresa i Treball
    "Departament d'Empresa i Treball": [
        (r"REFERÈNCIA:?\s*([\d/]+)", "REFERÈNCIA"),
    ],
    # Diputació de Valencia
    "Diputació de Valencia": [
        (r"Nº EXPEDIENTE\s*([\w\-/]{8,15})", "Nº EXPEDIENTE"),
    ],
    # Diputación de Barcelona
    "Diputación de Barcelona": [
        (r"Número expedient\s*([A-Za-z0-9/\-_.]{4,15})", "Numero expedient"),
        (r"Expedient executiu\s*([A-Za-z0-9/\-_.]{4,15})", "Expedient executiu"),
        (r"Expedient sancionador\s*([A-Za-z0-9]{8,12})", "Expedient sancionador"),
    ],
    # Diputació de Tarragona
    "Diputació de Tarragona": [
        (r"EXPEDIENT:\s*\+?\s*([\d\-]+/\d+-[A-Z]{3})", "EXPEDIENT"),
        (r"Expedient:\s*\+?\s*([\d\-]+/\d+-[A-Z]{3})", "Expedient"),
    ],
    # Infracciones Administrativas
    "Infracciones Administrativas": [],
    # Kit digital
    "Kit digital": [
        (r"Código de Acuerdo\s*(KD/\w{8,12})", "Código de Acuerdo"),
        (r"Código de Acuerdo W\s*(KC/\d{10,12})", "Código de Acuerdo W KC"),
    ],
    # Madrid (casos específicos)
    "Multas Madrid": [
        (r"REFERENCIA DEL EXPEDIENTE\s*([\w\-/\.]+)", "REFERENCIA DEL EXPEDIENTE"),
        (r"REFERENCIA DEL EXPEDIENTE\s*(\d{3}/\d{9}\.\d)", "REFERENCIA DEL EXPEDIENTE numérica"),
    ],
    # Multas DGT
    "Multas DGT": [
        (r"Nº EXPEDIENTE:\s*([\d\-\.]+)", "Nº EXPEDIENTE"),
        (r"EXPEDIENTE\s*\|\s*([\d\-\.]+)", "EXPEDIENTE | numérico"),
        (r"N\*\s*EXPEDIENTE:\s*([\d\-\.]+)", "N* EXPEDIENTE"),
        (r"N\.?\s*EXPEDIENTE\s*[-:]?\s*([\d\-\.]+)", "N. EXPEDIENTE"),
        (r"Nº expediente\s*(\d{2}-\d{3}-\d{3}\.\d{3}-\d)", "Nº expediente"),
    ],
    # Ministerio del interior
    "Ministerio del interior": [
        (r"N\.?\s*EXPEDIENTE\s*[-:]?\s*([\d\-\.]+)", "N. EXPEDIENTE"),
        (r"([\d]{2}-[\d]{3}-[\d]{3}\.[\d]{3}-[\d])", "Expediente numérico"),
        (r"([\d]{2}-[\d]{3}-[\d]{3}\.[\d]{3}-[\d])", "Expediente numérico punto"),
    ],
    # Ministerio del Interior
    "Ministerio del Sanidad": [
        (r"PR/\s*\d{5}/\d{4}/M", "PR expediente Ministerio de Sanidad"),
    ],
    # Puertos Baleares
    "Puertos Baleares" : [
        (r"Código de expediente:\s*(EO\d{4,8}A)", "Código de expediente EOxxxxxA"),
    ], 
    # Registro Marítimo Español
    "Organismo Estatal Inspección de Trabajo y Seguridad Social": [
        (r"N/REF\s*(I\d{14})", "N/REF Inspección de Trabajo"),
    ],
    "Registro Marítimo Español": [],
    # Servei Catala de Transit
    "Servei Catala de Transit": [
        (r"Núm\. d'expedient:?\s*([A-Z0-9]+)", "Núm. d'expedient"),
        (r"Número d'expedient:\s*(\d{2}/\d{8}-\d)", "Número d'expedient"),
    ],
    # TEAR/HACIENDA
    "TEAR/HACIENDA": [
        (r"Liquidaci[oó]n\s*([A-Za-z0-9\-\/]{10,20})", "Liquidación"),
    ],
    # Tesoreria General de la Seguridad Social
    "Tesoreria General de la Seguridad Social": [
        (r"Número Expediente:\s*([0-9]{2}\s?[0-9]{2}\s?[0-9]{2}\s?[0-9]{8})", "Número Expediente"),
        (r"Expediente:\s*([0-9]{2}\s?[0-9]{2}\s?[0-9]{2}\s?[0-9]{8})", "Expediente"),
        (r"Nº Documento\s*([A-Z0-9\-\/\. ]{15,25})", "Nº Documento"),
        (r"CCC[:\s]*([0-9]{2}\s?[0-9]{8,10})", "CCC"),
    ],
    "Common Rules": [
        (r"Expediente:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Expediente genérico"),
        (r"Expediente\s*([A-Za-z0-9\-\/\. ]{4,20})", "Expediente genérico"),
        (r"Número de expediente:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Número de expediente genérico"),
        (r"Referencia:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Referencia genérica"),
        (r"Referencia del expediente:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Referencia del expediente genérica"),
        (r"Expediente\s*([A-Za-z0-9\-\/\. ]{4,20})", "Expediente genérico"),
        (r"Núm\. d'expedient:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Num. d'expedient genérico"),
        (r"Expedient:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Expedient genérico"),
        (r"Núm\. expediente:\s*([A-Za-z0-9\-\/\. ]{4,20})", "Num. expediente genérico"),
        (r"EXPEDIENTE:\s*([A-Za-z0-9\-\/\. ]{4,20})", "EXPEDIENTE genérico"),
        (r"EXPEDIENTE\s*([A-Za-z0-9\-\/\. ]{4,20})", "EXPEDIENTE genérico"),
        (r"NÚMERO DE EXPEDIENTE:\s*([A-Za-z0-9\-\/\. ]{4,20})", "NÚMERO DE EXPEDIENTE genérico"),
        (r"REFERENCIA:\s*([A-Za-z0-9\-\/\. ]{4,20})", "REFERENCIA genérica"),
        (r"REFERENCIA DEL EXPEDIENTE:\s*([A-Za-z0-9\-\/\. ]{4,20})", "REFERENCIA DEL EXPEDIENTE genérica"),
        (r"NÚM\. D'EXPEDIENT:\s*([A-Za-z0-9\-\/\. ]{4,20})", "NÚM. D'EXPEDIENT genérico"),
    ]
}
