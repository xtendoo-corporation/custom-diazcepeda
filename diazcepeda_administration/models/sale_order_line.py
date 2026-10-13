from odoo import models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _reset_price_unit(self):
        super()._reset_price_unit()
        self.ensure_one()
        if (
            self.product_id.sin_valoracion_cantidad_negativa
            and self.product_uom_qty < 0
        ):
            self.update({'price_unit': 0.0, 'technical_price_unit': 0.0})
