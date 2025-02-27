from odoo import models, fields

class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    order_id = fields.Many2one('sale.order', string='Pedido')
