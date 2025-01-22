from odoo import models, fields, api

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    codigo_normalizado = fields.Char(
        string='Código normalizado',
    )
    referencia_auxiliar = fields.Char(
        string='Referencia auxiliar',
    )
