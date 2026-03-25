# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    @api.onchange('discount', 'product_id', 'price_unit')
    def _onchange_category_discount(self):
        for line in self:
            if line.product_id and line.product_id.categ_id:
                if not line.product_id.categ_id.show_discount_in_line:
                    if line.discount:
                        # Include discount in price_unit and set discount to 0
                        # Standard Odoo will hit other computes to recalculate balance and taxes
                        line.price_unit = line.price_unit * (1 - (line.discount / 100.0))
                        line.discount = 0.0
