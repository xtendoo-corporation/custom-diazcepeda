from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sin_valoracion_cantidad_negativa = fields.Boolean(
        string='Sin valoración en cantidad negativa',
        help='Si se marca, en las líneas de venta y factura de este producto '
             'con cantidad negativa el precio unitario será 0 (no se valora).',
    )
