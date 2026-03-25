# -*- coding: utf-8 -*-
{
    'name': 'Diazcepeda Category Discounts',
    'version': '17.0.1.0.0',
    'category': 'Sales',
    'summary': 'Configure discount behavior per product category',
    'description': """
        This module adds a 'Descuento en línea' boolean to product categories.
        If unchecked, any discount applied to sales or invoices for products in this category 
        will be included in the unit price instead of showing in the discount field.
    """,
    'author': 'Xtendoo',
    'website': 'https://xtendoo.es',
    'depends': ['product', 'sale_management', 'account'],
    'data': [
        'views/product_category_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
