{
    "name": "Diaz Cepeda Export CSV",
    "summary": """Diaz Cepeda Export CSV""",
    "version": "18.0.1.1.0",
    "description": """Diaz Cepeda Export CSV""",
    "company": "Xtendoo",
    "author": "Manuel Calero Solís",
    "website": "https://xtendoo.es",
    "category": "Website",
    "license": "AGPL-3",
    "depends": [
        "account",
        "diazcepeda_export_xls_contability",
        "diazcepeda_document_format",  # Necesario para los campos referencia_auxiliar y codigo_normalizado
    ],
    "data": [
        "security/ir.model.access.csv",
        "wizard/csv_export.xml",
    ],
    "installable": True,
    'application': True,
}
