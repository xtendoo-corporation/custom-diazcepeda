from odoo import models, fields, api
# Markup necesario para t-out con HTML en Odoo 17+; t-raw fue eliminado
from markupsafe import Markup

class AccountMove(models.Model):
    _inherit = 'account.move'

    def _get_invoice_lines_to_report(self, lines):
        invoice_line = lines
        filtered_lines = invoice_line.filtered(lambda line: line.product_id.name != 'Gasto de gestión')
        return filtered_lines

    def _is_gasto_gestion(self):
        return self.invoice_line_ids.filtered(lambda line: line.product_id.name == 'Gasto de gestión').exists()

    def _get_footer_data(self):
        # Buscar la compañía cuyo nombre es 'Fernando Díaz Cepeda'
        fdc_company_id = self.env['res.company'].search([('name', '=', 'Fernando Díaz Cepeda')], limit=1)
        if self.company_id != fdc_company_id:
            param_obj = self.env['ir.config_parameter'].sudo()
            footer_data = param_obj.get_param('footer_data', default='')
            # Markup permite usar t-out en lugar del obsoleto t-raw (Odoo 18)
            return Markup(footer_data.replace('\n', '<br/>'))
        return Markup('')

    # ELIMINAR el override de tax_totals porque causa errores en otros modelos
    # Si necesitas el valor en el template, usa un método auxiliar o añade el valor en el contexto del informe.

    def get_tax_totals_with_green_point(self):
        self.ensure_one()
        tax_totals = self.tax_totals.copy() if self.tax_totals else {}
        tax_totals['amount_total_green_point'] = self.amount_total_green_point
        return tax_totals
