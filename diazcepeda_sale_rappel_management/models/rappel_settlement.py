# -*- coding: utf-8 -*-
from odoo import models, fields, api
from odoo.exceptions import UserError


class RappelSettlement(models.Model):
    """
    Liquidación de rappel para un cliente y período determinados.

    Estados:
      - draft:      Borrador (recién creada o reiniciada)
      - calculated: Calculada con líneas de liquidación
      - invoiced:   Abono generado y vinculado
    """
    _name = 'rappel.settlement'
    _description = 'Liquidación de Rappel'
    _order = 'date_start desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        string='Referencia',
        required=True,
        copy=False,
        default='Nuevo',
        tracking=True,
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Cliente',
        required=True,
        tracking=True,
    )
    date_start = fields.Date(
        string='Fecha Inicio',
        required=True,
        tracking=True,
    )
    date_end = fields.Date(
        string='Fecha Fin',
        required=True,
        tracking=True,
    )
    state = fields.Selection(
        selection=[
            ('draft', 'Borrador'),
            ('calculated', 'Calculado'),
            ('invoiced', 'Facturado'),
        ],
        string='Estado',
        default='draft',
        tracking=True,
        copy=False,
    )
    currency_id = fields.Many2one(
        comodel_name='res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )
    company_id = fields.Many2one(
        comodel_name='res.company',
        string='Empresa',
        default=lambda self: self.env.company,
        required=True,
    )
    total_base_amount = fields.Monetary(
        string='Base Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    total_rappel_amount = fields.Monetary(
        string='Rappel Total',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
    )
    invoice_id = fields.Many2one(
        comodel_name='account.move',
        string='Abono Generado',
        readonly=True,
        copy=False,
        tracking=True,
    )
    settlement_line_ids = fields.One2many(
        comodel_name='rappel.settlement.line',
        inverse_name='settlement_id',
        string='Líneas de Liquidación',
    )

    # ── ORM overrides ────────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nuevo') == 'Nuevo':
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('rappel.settlement') or 'Nuevo'
                )
        return super().create(vals_list)

    # ── Compute ──────────────────────────────────────────────────────────────

    @api.depends('settlement_line_ids.base_amount', 'settlement_line_ids.rappel_amount')
    def _compute_totals(self):
        for settlement in self:
            lines = settlement.settlement_line_ids
            settlement.total_base_amount = sum(lines.mapped('base_amount'))
            settlement.total_rappel_amount = sum(lines.mapped('rappel_amount'))

    # ── Actions ──────────────────────────────────────────────────────────────

    def action_generate_credit_note(self):
        """
        Genera un abono (out_refund) con el importe total del rappel calculado.
        El abono queda vinculado a la liquidación y el estado pasa a 'invoiced'.
        """
        self.ensure_one()

        if self.state != 'calculated':
            raise UserError('Solo se puede generar un abono desde el estado "Calculado".')
        if self.invoice_id:
            raise UserError('Ya existe un abono generado para esta liquidación.')
        if not self.settlement_line_ids:
            raise UserError('No hay líneas de liquidación. Calcule el rappel primero.')

        # Construir líneas del abono agrupadas por producto
        invoice_lines = []
        for line in self.settlement_line_ids:
            invoice_lines.append((0, 0, {
                'name': f'Liquidación rappel anual - {line.product_id.name}',
                'product_id': line.product_id.id,
                'quantity': 1.0,
                'price_unit': line.rappel_amount,
            }))

        # Crear el abono
        credit_note = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.today(),
            'ref': f'Rappel - {self.name}',
            'company_id': self.company_id.id,
            'currency_id': self.currency_id.id,
            'invoice_line_ids': invoice_lines,
            'narration': (
                f'Liquidación de rappel del {self.date_start} al {self.date_end}. '
                f'Base total: {self.total_base_amount:.2f} {self.currency_id.name}.'
            ),
        })

        self.invoice_id = credit_note.id
        self.state = 'invoiced'

        # Abrir el abono generado
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': credit_note.id,
            'target': 'current',
        }

    def action_view_invoice(self):
        """Abrir el abono vinculado."""
        self.ensure_one()
        if not self.invoice_id:
            raise UserError('No existe ningún abono vinculado a esta liquidación.')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'form',
            'res_id': self.invoice_id.id,
            'target': 'current',
        }

    def action_reset_to_draft(self):
        """
        Reinicia la liquidación a estado borrador.
        Solo es posible si no existe abono generado.
        Al reiniciar se eliminan todas las líneas de liquidación
        y se liberan las líneas de factura para poder volver a liquidarse.
        """
        for settlement in self:
            if settlement.invoice_id:
                raise UserError(
                    'No se puede reiniciar una liquidación que ya tiene un abono generado. '
                    'Cancele primero el abono desde el módulo de contabilidad.'
                )
            # Liberar líneas de factura vinculadas
            for sl in settlement.settlement_line_ids:
                sl.invoice_line_ids.write({'rappel_settlement_line_id': False})
            settlement.settlement_line_ids.unlink()
            settlement.state = 'draft'

