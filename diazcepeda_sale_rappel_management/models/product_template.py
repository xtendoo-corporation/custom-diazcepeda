# -*- coding: utf-8 -*-
from odoo import models, fields


class ProductTemplate(models.Model):
    """
    Extensión de product.template con campos de rappel.
    Estos campos determinan si el producto participa en el sistema de rappels.
    """
    _inherit = 'product.template'

    is_rappel_applicable = fields.Boolean(
        string='Aplica Rappel',
        default=False,
        help='Indica si el producto participa en el sistema de rappels comerciales.',
    )
    rappel_category_id = fields.Many2one(
        comodel_name='product.category',
        string='Categoría de Rappel',
        help='Categoría usada para la asignación de reglas de rappel cuando no se define una regla por producto.',
    )
    default_rappel_percent = fields.Float(
        string='Rappel por Defecto (%)',
        digits=(5, 2),
        help='Porcentaje de rappel por defecto para este producto '
             'cuando no existe ninguna regla de rappel aplicable.',
    )
    show_rappel_on_quote = fields.Boolean(
        string='Mostrar Rappel en Presupuesto',
        default=False,
        help='Si está activo, el rappel estimado se mostrará en el presupuesto de venta.',
    )

