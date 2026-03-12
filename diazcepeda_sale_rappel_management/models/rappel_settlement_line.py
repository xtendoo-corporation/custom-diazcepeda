# -*- coding: utf-8 -*-
from odoo import models, fields, api


class RappelSettlementLine(models.Model):
    """
    Línea de liquidación de rappel.

    Cada línea representa el agregado de ventas de un producto en el período
    cubierto por la liquidación, con el porcentaje y el importe de rappel calculados.
    """
    _name = 'rappel.settlement.line'
    _description = 'Línea de Liquidación de Rappel'
    _order = 'settlement_id, product_id'

    settlement_id = fields.Many2one(
        comodel_name='rappel.settlement',
        string='Liquidación',
        required=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        required=True,
    )
    quantity = fields.Float(
        string='Cantidad Vendida',
        digits='Product Unit of Measure',
    )
    base_amount = fields.Monetary(
        string='Base Imponible',
        currency_field='currency_id',
        help='Importe total vendido del producto en el período (sin rappel).',
    )
    rappel_percent = fields.Float(
        string='% Rappel',
        digits=(5, 2),
    )
    rappel_amount = fields.Monetary(
        string='Importe Rappel',
        currency_field='currency_id',
        compute='_compute_rappel_amount',
        store=True,
        help='Importe de rappel = Base Imponible × Porcentaje Rappel.',
    )
    invoice_line_ids = fields.Many2many(
        comodel_name='account.move.line',
        relation='rappel_settlement_line_invoice_line_rel',
        column1='settlement_line_id',
        column2='invoice_line_id',
        string='Líneas de Factura',
        help='Líneas de factura incluidas en el cálculo de este rappel.',
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        related='settlement_id.currency_id',
        store=True,
        string='Moneda',
    )

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('base_amount', 'rappel_percent')
    def _compute_rappel_amount(self):
        for line in self:
            line.rappel_amount = line.base_amount * (line.rappel_percent / 100.0)

