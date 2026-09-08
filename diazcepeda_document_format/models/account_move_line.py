from odoo import fields, models
from odoo.tools import float_compare, float_is_zero
from odoo.tools.misc import formatLang


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    order_id = fields.Many2one('sale.order', string='Pedido')

    def _get_line_lot_values(self):
        self.ensure_one()

        if (
            self.display_type != 'product'
            or not self.product_id
            or self.product_id.type != 'consu'
            or float_compare(
                self.quantity,
                0,
                precision_rounding=self.product_uom_id.rounding,
            ) <= 0
        ):
            return []

        stock_move_lines = self.sale_line_ids.move_ids.move_line_ids.filtered(
            lambda move_line: (
                move_line.state == 'done'
                and move_line.lot_id
                and move_line.product_id == self.product_id
            )
        ).sorted(lambda move_line: (move_line.date, move_line.id))

        quantities_by_lot = {}
        lots_by_id = {}
        for move_line in stock_move_lines:
            quantity = move_line.product_uom_id._compute_quantity(
                move_line.quantity,
                self.product_uom_id,
            )
            if float_is_zero(
                quantity,
                precision_rounding=self.product_uom_id.rounding,
            ):
                continue
            lot_id = move_line.lot_id.id
            lots_by_id[lot_id] = move_line.lot_id
            quantities_by_lot[lot_id] = (
                quantities_by_lot.get(lot_id, 0.0) + quantity
            )

        remaining_quantity = self.quantity
        lot_values = []
        for lot_id, quantity in quantities_by_lot.items():
            if float_is_zero(
                remaining_quantity,
                precision_rounding=self.product_uom_id.rounding,
            ):
                break
            quantity = min(quantity, remaining_quantity)
            if float_compare(
                quantity,
                0,
                precision_rounding=self.product_uom_id.rounding,
            ) <= 0:
                continue
            lot_values.append({
                'lot_name': lots_by_id[lot_id].sudo().name,
                'quantity': formatLang(
                    self.env,
                    quantity,
                    dp='Product Unit of Measure',
                ),
            })
            remaining_quantity -= quantity

        return lot_values
