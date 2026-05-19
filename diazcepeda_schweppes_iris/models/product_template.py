from odoo import models, fields


SCHWEPPES_PRODUCT_TYPE_SELECTION = [
    ('ENVA', 'Envases'),
    ('FERT', 'Producto Terminado'),
    ('PLV', 'Publicidad en punto de venta'),
    ('TRLD', 'Trade Loader'),
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    schweppes_product_code = fields.Char(string="Código Artículo Schweppes")
    schweppes_brand = fields.Char(string="Marca IRIS")
    schweppes_class = fields.Char(string="Clase IRIS")
    schweppes_flavor = fields.Char(string="Sabor IRIS")
    schweppes_product_type = fields.Selection(
        selection=SCHWEPPES_PRODUCT_TYPE_SELECTION,
        string="Tipo de Producto IRIS",
        help="Valores IRIS actualmente admitidos por Schweppes.",
    )
