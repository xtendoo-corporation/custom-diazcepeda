# -*- coding: utf-8 -*-
from odoo import models, fields

class ProductCategory(models.Model):
    _inherit = 'product.category'

    show_discount_in_line = fields.Boolean(
        string='Descuento en línea',
        default=False,
        help="Si está marcado, el descuento se muestra en la línea de venta/factura. Si no, se incluye en el precio unitario."
    )
