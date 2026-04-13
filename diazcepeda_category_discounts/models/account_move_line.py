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
        # FIX: no mutar el dict `vals` compartido.
        # El break anterior solo evitaba el bucle, pero vals ya estaba contaminado con el
        # price_unit de la primera línea, afectando a todas las líneas del mismo batch.
        # Se construye un dict individual por línea para cada caso que requiere ajuste.
        if vals.get('discount') and vals['discount'] > 0:
            lines_need_fix = self.filtered(
                lambda l: l.product_id.categ_id and not l.product_id.categ_id.show_discount_in_line
            )
            lines_skip = self - lines_need_fix
            for line in lines_need_fix:
                product = self.env['product.product'].browse(
                    vals.get('product_id', line.product_id.id)
                )
                if product.categ_id and not product.categ_id.show_discount_in_line:
                    price_unit = vals.get('price_unit', line.price_unit)
                    line_vals = dict(vals)
                    line_vals['price_unit'] = price_unit * (1 - (vals['discount'] / 100.0))
                    line_vals['discount'] = 0.0
                    super(AccountMoveLine, line).write(line_vals)
            if lines_skip:
                super(AccountMoveLine, lines_skip).write(vals)
            return True
        return super().write(vals)
