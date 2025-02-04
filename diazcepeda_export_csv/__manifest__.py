{
    "name": "Diaz Cepeda Export CSV",
    "summary": """Diaz Cepeda Export CSV""",
    "version": "17.0.1.0.0",
    "description": """Diaz Cepeda Export CSV""",
    "company": "Xtendoo",
    "author": "Manuel Calero Solís",
    "website": "https://xtendoo.es",
    "category": "Website",
    "license": "AGPL-3",
    "depends": [
        "account",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/account_move_view.xml",
        "wizard/csv_export.xml",
    ],
    "installable": True,
    'application': True,
}
