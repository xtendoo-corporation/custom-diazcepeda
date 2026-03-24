from odoo import models, fields

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    schweppes_product_code = fields.Char(string="Código Artículo Schweppes")
