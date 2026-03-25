# -*- coding: utf-8 -*-
from odoo import models, fields, api

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _get_display_price(self):
        """Override to force base price if category demands showing discount."""
        self.ensure_one()
        pricelist_price = self._get_pricelist_price()
        
        # If no setting or marked to NOT show discount, use discounted price as unit price
        if not self.product_id.categ_id.show_discount_in_line:
            return pricelist_price

        # We WANT to show the discount (show_discount_in_line is True)
        if not self.pricelist_item_id:
            return pricelist_price

        base_price = self._get_pricelist_price_before_discount()
        return max(base_price, pricelist_price)

    @api.depends('product_id', 'product_uom', 'product_uom_qty')
    def _compute_discount(self):
        """Override to force discount calculation based on category setting."""
        super()._compute_discount()
        for line in self:
            if not line.product_id or line.display_type or not line.order_id.pricelist_id:
                continue

            show_discount = line.product_id.categ_id.show_discount_in_line
            if not show_discount:
                # We enforce no discount on the line in UI
                line.discount = 0.0
            else:
                # We enforce showing the discount, even if pricelist is 'with_discount'
                if not line.pricelist_item_id:
                    continue
                
                line_company = line.with_company(line.company_id)
                pricelist_price = line_company._get_pricelist_price()
                base_price = line_company._get_pricelist_price_before_discount()

                if base_price != 0:
                    discount = (base_price - pricelist_price) / base_price * 100
                    if (discount > 0 and base_price > 0) or (discount < 0 and base_price < 0):
                        line.discount = discount

    @api.onchange('discount', 'product_id', 'price_unit')
    def _onchange_category_discount(self):
        for line in self:
            if line.product_id and line.product_id.categ_id:
                if not line.product_id.categ_id.show_discount_in_line:
                    if line.discount:
                        # Include manually entered discount in price_unit and set discount to 0
                        line.price_unit = line.price_unit * (1 - (line.discount / 100.0))
                        line.discount = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'discount' in vals and vals.get('discount') and vals['discount'] > 0:
                product_id = vals.get('product_id')
                if product_id:
                    product = self.env['product.product'].browse(product_id)
                    if product.categ_id and not product.categ_id.show_discount_in_line:
                        price_unit = vals.get('price_unit', 0.0)
                        vals['price_unit'] = price_unit * (1 - (vals['discount'] / 100.0))
                        vals['discount'] = 0.0
        return super().create(vals_list)

    def write(self, vals):
        if 'discount' in vals and vals.get('discount') and vals['discount'] > 0:
            for line in self:
                product = self.env['product.product'].browse(vals.get('product_id', line.product_id.id))
                if product.categ_id and not product.categ_id.show_discount_in_line:
                    price_unit = vals.get('price_unit', line.price_unit)
                    vals['price_unit'] = price_unit * (1 - (vals['discount'] / 100.0))
                    vals['discount'] = 0.0
        return super().write(vals)


