from odoo import api, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('quantity')
    def _onchange_quantity_sin_valoracion(self):
        for line in self:
            if (
                line.product_id.sin_valoracion_cantidad_negativa
                and line.quantity < 0
            ):
                line.price_unit = 0.0
