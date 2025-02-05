from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    price_bruto = fields.Float(
        string='Precio Bruto',
        compute='_compute_price_bruto',
    )

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_price_bruto(self):
        for line in self:
            line.price_bruto = line.price_unit
