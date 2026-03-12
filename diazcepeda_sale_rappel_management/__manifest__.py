# -*- coding: utf-8 -*-
{
    'name': 'Diazcepeda - Gestión de Rappels Comerciales',
    'version': '17.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': 'Gestión de rappels comerciales y liquidaciones de rappel',
    'description': """
        Módulo para gestionar rappels comerciales para distribuidora de bebidas.

        Funcionalidades:
        - Reglas de rappel flexibles por cliente/producto/categoría con sistema de prioridades
        - Estimación de rappel en presupuestos (solo informativo, sin modificar precio real)
        - Cálculo de rappel real al final de un período
        - Generación automática de abonos al cliente
        - Seguridad por grupo de gestores de rappel
    """,
    'author': 'Xtendoo',
    'website': 'https://www.xtendoo.es',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'account',
        'product',
        'mail',
    ],
    'data': [
        # Seguridad
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        # Datos base
        'data/data.xml',
        # Vistas
        'views/product_template_views.xml',
        'views/rappel_rule_views.xml',
        'views/rappel_settlement_views.xml',
        'views/sale_order_views.xml',
        'views/rappel_settlement_wizard_views.xml',
        'views/menu_views.xml',
        # Informes
        'reports/sale_order_report.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}

