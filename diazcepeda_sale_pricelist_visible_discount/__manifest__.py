{
    'name': 'Sale Pricelist Visible Discount',
    'version': '18.0.1.0.0',
    'category': 'Sales/Sales',
    'summary': (
        'Muestra el descuento visible en líneas de venta cuando la tarifa '
        'aplica una fórmula porcentual encadenada sobre otra tarifa base.'
    ),
    'description': '''
        Cuando una tarifa de venta usa una regla de tipo fórmula (compute_price=formula)
        basada en otra tarifa (base=pricelist), Odoo calcula el precio final absorbiendo
        el descuento en price_unit sin reflejarlo en el campo discount.

        Este módulo reconstruye de forma segura y conservadora el descuento visible en
        la línea de pedido de venta, siempre que la regla sea un descuento porcentual
        puro (sin recargos, redondeos ni márgenes).

        Resultado: price_unit = precio base, discount = % equivalente.
        El precio final neto no cambia.
    ''',
    'author': 'Diazcepeda',
    'website': 'https://www.diazcepeda.es',
    'license': 'AGPL-3',
    'depends': [
        'sale',
        'product',
    ],
    'installable': True,
    'auto_install': False,
    'application': False,
}
