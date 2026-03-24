from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    schweppes_distributor_code = fields.Char(string="Código Distribuidor Schweppes", default="1000026677")
