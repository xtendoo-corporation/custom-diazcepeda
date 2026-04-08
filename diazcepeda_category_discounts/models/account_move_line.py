# -*- coding: utf-8 -*-
from odoo import models, fields, api

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    # En Odoo 18, @api.onchange no es fiable para account.move.line porque
    # las líneas de factura se editan/guardan en batch desde el formulario del asiento.
    # Se sobreescriben create y write para garantizar el comportamiento correcto.

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('discount') and vals['discount'] > 0:
                product_id = vals.get('product_id')
                if product_id:
                    product = self.env['product.product'].browse(product_id)
                    if product.categ_id and not product.categ_id.show_discount_in_line:
                        price_unit = vals.get('price_unit', 0.0)
                        vals['price_unit'] = price_unit * (1 - (vals['discount'] / 100.0))
                        vals['discount'] = 0.0
        return super().create(vals_list)

    def write(self, vals):
        if vals.get('discount') and vals['discount'] > 0:
            for line in self:
                product = self.env['product.product'].browse(
                    vals.get('product_id', line.product_id.id)
                )
                if product.categ_id and not product.categ_id.show_discount_in_line:
                    price_unit = vals.get('price_unit', line.price_unit)
                    vals['price_unit'] = price_unit * (1 - (vals['discount'] / 100.0))
                    vals['discount'] = 0.0
                    break  # vals es compartido para todas las líneas; se aplica una vez
        return super().write(vals)
