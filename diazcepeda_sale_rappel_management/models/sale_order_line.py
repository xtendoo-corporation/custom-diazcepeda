# -*- coding: utf-8 -*-
from odoo import models, fields, api


class SaleOrderLine(models.Model):
    """
    Extensión de sale.order.line con campos de rappel estimado.

    IMPORTANTE: El rappel NO modifica el precio real de venta.
    Los campos son meramente informativos / comerciales.

    Cálculo:
      precio_neto = price_unit * (1 - descuento/100)
      rappel_estimado_unit = precio_neto * (rappel_percent / 100)
      precio_final_estimado = precio_neto - rappel_estimado_unit
      rappel_estimado_total = rappel_estimado_unit * cantidad
    """
    _inherit = 'sale.order.line'

    rappel_percent = fields.Float(
        string='% Rappel',
        digits=(5, 2),
        help='Porcentaje de rappel estimado para esta línea (solo informativo).',
    )
    rappel_rule_id = fields.Many2one(
        comodel_name='rappel.rule',
        string='Regla de Rappel',
        ondelete='set null',
        help='Regla de rappel que se ha aplicado a esta línea.',
    )
    rappel_estimated_amount = fields.Monetary(
        string='Rappel Estimado',
        compute='_compute_rappel',
        store=True,
        currency_field='currency_id',
        help='Importe total de rappel estimado para esta línea (solo informativo).',
    )
    rappel_estimated_unit_price = fields.Monetary(
        string='Precio Final Estimado',
        compute='_compute_rappel',
        store=True,
        currency_field='currency_id',
        help='Precio unitario neto estimado después de descontar el rappel (solo informativo).',
    )

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('price_unit', 'discount', 'product_uom_qty', 'rappel_percent')
    def _compute_rappel(self):
        for line in self:
            # Precio neto unitario (después del descuento comercial)
            net_price = line.price_unit * (1.0 - (line.discount or 0.0) / 100.0)
            # Rappel unitario estimado
            rappel_unit = net_price * (line.rappel_percent / 100.0)
            # Precio final estimado por unidad
            line.rappel_estimated_unit_price = net_price - rappel_unit
            # Rappel total estimado para toda la línea
            line.rappel_estimated_amount = rappel_unit * line.product_uom_qty

    # ── Onchange ─────────────────────────────────────────────────────────────

    @api.onchange('product_id')
    def _onchange_product_id_rappel(self):
        """Asigna automáticamente la regla de rappel cuando cambia el producto."""
        self._update_rappel_rule()

    # ── Business logic ───────────────────────────────────────────────────────

    def _update_rappel_rule(self):
        """
        Busca y aplica la regla de rappel más específica para cada línea.
        Se llama desde onchange y puede invocarse externamente si fuera necesario.
        """
        for line in self:
            if not line.product_id:
                line.rappel_rule_id = False
                line.rappel_percent = 0.0
                continue

            partner_id = line.order_id.partner_id.id if line.order_id else False
            date = (
                line.order_id.date_order.date()
                if line.order_id and line.order_id.date_order
                else fields.Date.today()
            )

            rule = self.env['rappel.rule'].find_applicable_rule(
                partner_id=partner_id,
                product_id=line.product_id.id,
                date=date,
            )

            if rule:
                line.rappel_rule_id = rule.id
                line.rappel_percent = rule.rappel_percent
            else:
                # Si no hay regla, intenta usar el porcentaje por defecto del producto
                product_tmpl = line.product_id.product_tmpl_id
                if product_tmpl.is_rappel_applicable and product_tmpl.default_rappel_percent:
                    line.rappel_rule_id = False
                    line.rappel_percent = product_tmpl.default_rappel_percent
                else:
                    line.rappel_rule_id = False
                    line.rappel_percent = 0.0

