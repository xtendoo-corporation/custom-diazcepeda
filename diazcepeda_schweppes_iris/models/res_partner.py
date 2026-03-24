from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    schweppes_customer_code = fields.Char(string="Código Cliente Schweppes")
    schweppes_delivery_type = fields.Selection([
        ('D', 'Directo'),
        ('I', 'Indirecto')
    ], string="Tipo Reparto Schweppes", default='D')
    schweppes_route = fields.Char(string="Ruta Schweppes", default="56")
