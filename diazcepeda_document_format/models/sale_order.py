from odoo import models, fields, api
# Markup necesario para t-out con HTML en Odoo 17+; t-raw fue eliminado
from markupsafe import Markup

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    def _get_order_lines_to_report(self):
        order_lines = super(SaleOrder, self)._get_order_lines_to_report()
        filtered_lines = order_lines.filtered(lambda line: line.product_id.name != 'Gasto de gestión')
        return filtered_lines

    def _is_gasto_gestion(self):
        return self.order_line.filtered(lambda line: line.product_id.name == 'Gasto de gestión').exists()

    def _get_footer_data(self):
        param_obj = self.env['ir.config_parameter'].sudo()
        footer_data = param_obj.get_param('footer_data', default='')
        # Markup permite usar t-out en lugar del obsoleto t-raw (Odoo 18)
        return Markup(footer_data.replace('\n', '<br/>'))
