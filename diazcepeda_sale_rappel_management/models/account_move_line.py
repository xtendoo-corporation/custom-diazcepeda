# -*- coding: utf-8 -*-
from odoo import models, fields


class AccountMoveLine(models.Model):
    """
    Extensión de account.move.line para prevenir la doble liquidación.
    Una línea de factura solo puede estar incluida en una liquidación de rappel.
    """
    _inherit = 'account.move.line'

    rappel_settlement_line_id = fields.Many2one(
        comodel_name='rappel.settlement.line',
        string='Línea de Liquidación de Rappel',
        ondelete='set null',
        copy=False,
        index=True,
        help='Indica la liquidación de rappel en la que se ha incluido esta línea de factura. '
             'Las líneas ya liquidadas no se vuelven a incluir en nuevas liquidaciones.',
    )

