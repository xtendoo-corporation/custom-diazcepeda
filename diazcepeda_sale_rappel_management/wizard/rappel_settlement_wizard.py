# -*- coding: utf-8 -*-
from collections import defaultdict

from odoo import models, fields, api
from odoo.exceptions import UserError


class RappelSettlementWizard(models.TransientModel):
    """
    Asistente para calcular liquidaciones de rappel.

    Flujo de trabajo:
      1. Seleccionar cliente, período y filtros opcionales de producto/categoría.
      2. El asistente busca las facturas publicadas del cliente en el período.
      3. Filtra las líneas por producto/categoría y descarta las ya liquidadas.
      4. Agrega los totales por producto y aplica la regla de rappel correspondiente.
      5. Crea la liquidación con sus líneas de detalle.
      6. Opcionalmente genera el abono de forma automática.
    """
    _name = 'rappel.settlement.wizard'
    _description = 'Asistente de Liquidación de Rappel'

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True,
        domain=[('customer_rank', '>', 0)],
    )
    date_start = fields.Date(
        string='Fecha Inicio',
        required=True,
    )
    date_end = fields.Date(
        string='Fecha Fin',
        required=True,
    )
    product_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Categoría de Producto',
        help='Si se indica, solo se liquidan las líneas de esa categoría.',
    )
    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto',
        help='Si se indica, solo se liquida ese producto (tiene prioridad sobre la categoría).',
    )
    generate_credit_note = fields.Boolean(
        string='Generar Abono Automáticamente',
        default=False,
        help='Si está activo, se generará el abono (factura rectificativa) '
             'al finalizar el cálculo.',
    )

    # ── Constraints ──────────────────────────────────────────────────────────

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_start and wizard.date_end and wizard.date_start > wizard.date_end:
                raise UserError('La fecha de inicio no puede ser posterior a la fecha de fin.')

    # ── Action ───────────────────────────────────────────────────────────────

    def action_calculate(self):
        """
        Calcula la liquidación de rappel y crea el registro rappel.settlement.
        Devuelve una acción para abrir el resultado.
        """
        self.ensure_one()

        # ── 1. Buscar facturas publicadas del cliente en el período ──────────
        domain = [
            ('partner_id', 'child_of', self.partner_id.id),
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_start),
            ('invoice_date', '<=', self.date_end),
            ('company_id', '=', self.env.company.id),
        ]
        invoices = self.env['account.move'].search(domain)

        if not invoices:
            raise UserError(
                f'No se han encontrado facturas publicadas para el cliente '
                f'"{self.partner_id.name}" en el período {self.date_start} – {self.date_end}.'
            )

        # ── 2. Obtener líneas de producto (excluir secciones/notas y ya liquidadas) ──
        invoice_lines = invoices.mapped('invoice_line_ids').filtered(
            lambda l: l.product_id
            and l.display_type == 'product'
            and not l.rappel_settlement_line_id  # ya liquidada
        )

        # ── 3. Filtrar por producto o categoría ─────────────────────────────
        if self.product_id:
            invoice_lines = invoice_lines.filtered(
                lambda l: l.product_id.id == self.product_id.id
            )
        elif self.product_category_id:
            invoice_lines = invoice_lines.filtered(
                lambda l: l.product_id.categ_id.id == self.product_category_id.id
            )

        # Filtrar solo productos con rappel habilitado
        invoice_lines = invoice_lines.filtered(
            lambda l: l.product_id.product_tmpl_id.is_rappel_applicable
        )

        if not invoice_lines:
            raise UserError(
                'No se encontraron líneas de factura liquidables en el período indicado.\n'
                'Verifique que los productos tienen activo el campo "Aplica Rappel" '
                'y que no han sido incluidos ya en otra liquidación.'
            )

        # ── 4. Agregar totales por producto ──────────────────────────────────
        product_data = defaultdict(lambda: {'qty': 0.0, 'amount': 0.0, 'line_ids': []})
        for line in invoice_lines:
            pid = line.product_id.id
            product_data[pid]['qty'] += line.quantity
            product_data[pid]['amount'] += line.price_subtotal
            product_data[pid]['line_ids'].append(line.id)

        # ── 5. Crear liquidación ─────────────────────────────────────────────
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner_id.id,
            'date_start': self.date_start,
            'date_end': self.date_end,
            'company_id': self.env.company.id,
            'currency_id': self.env.company.currency_id.id,
            'state': 'calculated',
        })

        # ── 6. Aplicar regla y crear líneas de liquidación ──────────────────
        lines_created = 0
        for product_id, data in product_data.items():
            rule = self.env['rappel.rule'].find_applicable_rule(
                partner_id=self.partner_id.id,
                product_id=product_id,
                date=self.date_end,
            )

            if rule:
                rappel_percent = rule.rappel_percent
            else:
                # Fallback al porcentaje por defecto del producto
                product = self.env['product.product'].browse(product_id)
                rappel_percent = product.product_tmpl_id.default_rappel_percent or 0.0

            if rappel_percent <= 0.0:
                continue  # Sin rappel aplicable para este producto

            settlement_line = self.env['rappel.settlement.line'].create({
                'settlement_id': settlement.id,
                'product_id': product_id,
                'quantity': data['qty'],
                'base_amount': data['amount'],
                'rappel_percent': rappel_percent,
                'invoice_line_ids': [(6, 0, data['line_ids'])],
            })

            # Marcar líneas de factura como ya liquidadas (evita doble liquidación)
            self.env['account.move.line'].browse(data['line_ids']).write({
                'rappel_settlement_line_id': settlement_line.id,
            })

            lines_created += 1

        # Si no se generó ninguna línea, eliminar la liquidación vacía
        if lines_created == 0:
            settlement.unlink()
            raise UserError(
                'No se encontraron reglas de rappel aplicables para los productos del período. '
                'Compruebe que existen reglas de rappel activas y vigentes para el período indicado.'
            )

        # ── 7. Generar abono si se solicitó ─────────────────────────────────
        if self.generate_credit_note:
            settlement.action_generate_credit_note()

        # Abrir la liquidación creada
        return {
            'type': 'ir.actions.act_window',
            'name': 'Liquidación de Rappel',
            'res_model': 'rappel.settlement',
            'view_mode': 'form',
            'res_id': settlement.id,
            'target': 'current',
        }

