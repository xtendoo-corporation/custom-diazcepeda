# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import ValidationError


class RappelRule(models.Model):
    """
    Reglas de rappel para distribuidora de bebidas.

    Sistema de prioridades al aplicar una regla:
      1. Cliente + Producto  (más específica)
      2. Cliente + Categoría
      3. Todos los clientes + Producto
      4. Todos los clientes + Categoría  (menos específica)
    """
    _name = 'rappel.rule'
    _description = 'Regla de Rappel'
    _order = 'sequence, id'

    name = fields.Char(
        string='Nombre',
        required=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        domain=[('customer_rank', '>', 0)],
        help='Si está vacío, la regla aplica a todos los clientes.',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        help='Producto específico al que aplica el rappel.',
    )
    product_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Categoría de Producto',
        help='Categoría de producto a la que aplica el rappel.',
    )
    rappel_percent = fields.Float(
        string='Porcentaje de Rappel (%)',
        digits=(5, 2),
        required=True,
    )
    date_start = fields.Date(
        string='Fecha Inicio',
        help='Fecha a partir de la cual aplica la regla (inclusive).',
    )
    date_end = fields.Date(
        string='Fecha Fin',
        help='Fecha hasta la que aplica la regla (inclusive).',
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        required=True,
    )
    active = fields.Boolean(
        string='Activo',
        default=True,
    )
    sequence = fields.Integer(
        string='Secuencia',
        default=10,
    )

    # ── Constraints ─────────────────────────────────────────────────────────

    # ── ORM overrides ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """Valida inmediatamente al crear que se indica producto o categoría."""
        for vals in vals_list:
            if not vals.get('product_id') and not vals.get('product_category_id'):
                raise ValidationError(
                    'Debe especificar al menos un Producto o una Categoría de Producto en la regla de rappel.'
                )
        return super().create(vals_list)

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains('product_id', 'product_category_id')
    def _check_product_or_category(self):
        """Al menos uno de los dos campos debe estar informado (también en write)."""
        for rule in self:
            if not rule.product_id and not rule.product_category_id:
                raise ValidationError(
                    'Debe especificar al menos un Producto o una Categoría de Producto en la regla de rappel.'
                )

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for rule in self:
            if rule.date_start and rule.date_end and rule.date_start > rule.date_end:
                raise ValidationError(
                    'La fecha de inicio no puede ser posterior a la fecha de fin.'
                )

    # ── Priority helpers ─────────────────────────────────────────────────────

    def _get_priority(self):
        """
        Devuelve la prioridad numérica de la regla (1 = más específica).
        """
        self.ensure_one()
        if self.partner_id and self.product_id:
            return 1
        if self.partner_id and self.product_category_id:
            return 2
        if not self.partner_id and self.product_id:
            return 3
        return 4  # All customers + Category

    # ── Rule lookup ──────────────────────────────────────────────────────────

    @api.model
    def find_applicable_rule(self, partner_id, product_id, date=None):
        """
        Encuentra la regla de rappel más específica para un cliente y producto dados.

        Orden de prioridad:
          1. Cliente + Producto
          2. Cliente + Categoría
          3. Todos los clientes + Producto
          4. Todos los clientes + Categoría

        :param partner_id: ID del cliente (res.partner)
        :param product_id: ID del producto (product.product)
        :param date: Fecha de referencia (date object). Si no se indica, no filtra por fecha.
        :return: Recordset rappel.rule (vacío si no se encuentra ninguna regla)
        """
        if not product_id:
            return self.browse()

        product = self.env['product.product'].browse(product_id)
        if not product.exists():
            return self.browse()

        category_id = product.categ_id.id

        # Dominio base
        domain = [('active', '=', True), ('company_id', '=', self.env.company.id)]
        if date:
            domain += [
                '|', ('date_start', '=', False), ('date_start', '<=', date),
                '|', ('date_end', '=', False), ('date_end', '>=', date),
            ]

        rules = self.search(domain)

        # Prioridad 1: Cliente + Producto
        if partner_id:
            match = rules.filtered(
                lambda r: r.partner_id.id == partner_id and r.product_id.id == product_id
            )
            if match:
                return match[0]

        # Prioridad 2: Cliente + Categoría
        if partner_id and category_id:
            match = rules.filtered(
                lambda r: r.partner_id.id == partner_id
                and not r.product_id
                and r.product_category_id.id == category_id
            )
            if match:
                return match[0]

        # Prioridad 3: Todos los clientes + Producto
        match = rules.filtered(
            lambda r: not r.partner_id and r.product_id.id == product_id
        )
        if match:
            return match[0]

        # Prioridad 4: Todos los clientes + Categoría
        if category_id:
            match = rules.filtered(
                lambda r: not r.partner_id
                and not r.product_id
                and r.product_category_id.id == category_id
            )
            if match:
                return match[0]

        return self.browse()

