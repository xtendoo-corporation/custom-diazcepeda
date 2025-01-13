from odoo import models, fields, api

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_invoice_lines_to_report(self, lines):
        print("*"*80)
        invoice_line = lines
        print("invoice_line", invoice_line)
        filtered_lines = invoice_line.filtered(lambda line: line.product_id.name != 'Gasto de gestión')
        print("filtered_lines", filtered_lines)
        print("*"*80)
        return filtered_lines

    def _is_gasto_gestion(self):
        return self.invoice_line_ids.filtered(lambda line: line.product_id.name == 'Gasto de gestión').exists()
