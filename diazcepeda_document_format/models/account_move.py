from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_invoice_lines_to_report(self, lines):
        invoice_line = lines
        filtered_lines = invoice_line.filtered(lambda line: line.product_id.name != 'Gasto de gestión')
        return filtered_lines

    def _is_gasto_gestion(self):
        return self.invoice_line_ids.filtered(lambda line: line.product_id.name == 'Gasto de gestión').exists()

    def _get_footer_data(self):
        param_obj = self.env['ir.config_parameter'].sudo()
        footer_data = param_obj.get_param('footer_data', default='')
        return footer_data.replace('\n', '<br/>')
