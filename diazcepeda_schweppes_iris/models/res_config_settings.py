from odoo import models, fields

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    schweppes_distributor_code = fields.Char(related='company_id.schweppes_distributor_code', readonly=False)
