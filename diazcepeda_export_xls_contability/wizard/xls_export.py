import base64

import xlwt
import os
from odoo import models, fields, api

class DiazCepedaExportXLSContability(models.TransientModel):
    _name = "diazcepeda.export.xls.contability"
    _description = "Informe de contabilidad"

    start_date = fields.Date(string="Fecha inico", required=True)
    end_date = fields.Date(string="Fecha fin", required=True)

    generate_xls_file = fields.Binary(
        "Generated file",
        help="Technical field used to temporarily hold the generated XLS file before its downloaded."
    )

    def export_file(self, xlsxwriter=None):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()

        # SACO LOS DATOS QUE NECESITO Y SE LO PASO A LA FUNCION QUE CREA EL CSV
        invoices = self.env['account.move'].search([
            ('invoice_date', '>=', self.start_date),
            ('invoice_date', '<=', self.end_date)]
        )

        print("*******INVOICES:", invoices)
        print("*******start_date:", self.start_date)
        print("*******end_date:", self.end_date)

        # Define the path for the XLSX file
        file_path = '/tmp/contabilidad.xls'

        # Create an XLS file
        workbook = xlwt.Workbook()
        worksheet = workbook.add_sheet('Contabilidad')

        # Write headers
        headers = ['Serie',
                   'Factura',
                   'Fecha',
                   'FechaOperacion',
                   'CodigoCuenta',
                   'CIFEUROPEO',
                   'Cliente',
                   'Comentario',
                   'Contrapartida',
                   'Cod.Transacion',
                   'ClaveOperaciónFact',
                   'Importe Factura',
                   'Base Imponible1',
                   '%Iva1',
                   'Cuota Iva1',
                   '%RecEq1',
                   'Cuota Rec1',
                   'CodigoRetencion',
                   'Base Ret',
                   'PorRetencion',
                   'Cuota Retención',
                   'Base Imponible2',
                   '%Iva2',
                   'Cuota Iva2',
                   '%RecEq2',
                   'Cuota Rec2',
                   'Base Imponible3',
                   '%Iva3',
                   'Cuota Iva3',
                   '%RecEq3',
                   'Cuota Rec3',
                   'TipoRectificativa',
                   'ClaseAbonoRectificativas',
                   'EjercicioFacturaRectificada',
                   'SerieFacturaRectificada',
                   'NumeroFacturaRectificada',
                   'FechaFacturaRectificada',
                   'BaseImponibleRectificada',
                   'CuotaIvaRectificada',
                   'RecargoEquiRectificada',
                   'NumeroFacturaInicial',
                   'NumeroFacturaFinal',
                   'IdFacturaExterno',
                   'Codigo Postal',
                   'Cod. Provincia',
                   'Provincia',
                   'CodigoCanal',
                   'CodigoDelegación',
                   'CodDepartamento',
                   'Base Imponible4',
                   '%Iva4',
                   'Cuota Iva4',
                   '%RecEq4',
                   'Cuota Rec4']
        for col_num, header in enumerate(headers):
            worksheet.write(0, col_num, header)

        # Write data
        for row_num, invoice in enumerate(invoices, start=1):
            worksheet.write(row_num, 0, "SERIE NO")  # 'Serie',
            worksheet.write(row_num, 1, invoice.name)  # 'Factura',
            worksheet.write(row_num, 2, str(invoice.invoice_date))  # 'Fecha',
            worksheet.write(row_num, 3, str(invoice.invoice_date))  # 'FechaOperacion',
            worksheet.write(row_num, 4, "")  # 'CodigoCuenta',
            worksheet.write(row_num, 5, invoice.partner_id.vat)  # 'CIFEUROPEO',
            worksheet.write(row_num, 6, invoice.partner_id.name)  # 'Cliente',
            worksheet.write(row_num, 7, "N/ FRA. Nº. " + invoice.name + " - " + invoice.partner_id.name)  # 'Comentario',
            worksheet.write(row_num, 8, "")  # 'Contrapartida',
            worksheet.write(row_num, 9, "")  # 'Cod.Transacion',
            worksheet.write(row_num, 10, "") # 'ClaveOperaciónFact',
            worksheet.write(row_num, 11, invoice.amount_total) # 'Importe Factura'


            base_imponible = [0, 0, 0, 0]
            iva = [0, 0, 0, 0]
            rec_eq = [0, 0, 0, 0]

            # Initialize VAT breakdown columns
            base_imponible = [0, 0, 0, 0]
            iva = [0, 0, 0, 0]
            rec_eq = [0, 0, 0, 0]
            index = 0

            # for key, tax_total in invoice.tax_totals.items():
            #     print("*******tax_total (key):", key)
            #     print("*******tax_total (type):", type(tax_total))
            #     print("*******tax_total (content):", tax_total)

            for key, tax_total in invoice.tax_totals.items():
                if key == 'groups_by_subtotal':
                    for group in tax_total['Base imponible']:
                        base_imponible[0] = group['tax_group_base_amount']
                        iva_percentage = group['tax_group_name']
                        iva[0] = group['tax_group_amount']
                        print("Base Imponible:", base_imponible[0])
                        print("% IVA:", iva_percentage)
                        print("Cuota IVA:", iva[0])

            # for tax_total in invoice.amount_by_group:
            #     if tax_total['tax_group_id'] == self.env.ref('l10n_es.tax_group_iva'):
            #         base_imponible[index] += tax_total['base']
            #         iva[index] += tax_total['amount']
            #     elif tax_total['tax_group_id'] == self.env.ref('l10n_es.tax_group_recargo_equivalencia'):
            #         rec_eq[index] += tax_total['amount']
            #
            #     print("*******tax_total:", tax_total)
            #     print("*******base_imponible:", base_imponible[index])
            #     print("*******iva:", iva[index])
            #     print("*******rec:", rec_eq[index])
            #
            #     index += 1

            # # Calculate VAT breakdown
            # for line in invoice.invoice_line_ids:
            #     for tax in line.tax_ids:
            #         if tax.tax_group_id.name == 'IVA':
            #             index = 0
            #             if base_imponible[index] != 0:
            #                 index += 1
            #             base_imponible[index] += line.price_subtotal
            #             iva[index] += line.price_subtotal * tax.amount / 100
            #         elif tax.tax_group_id.name == 'Recargo de Equivalencia':
            #             rec_eq[index] += line.price_subtotal * tax.amount / 100

            # for line in invoice.invoice_line_ids:
            #     print("**********LINE:", line)
            #     print("**********tax_ids:", line.tax_ids)
            #     # for tax in line.tax_ids:
            #     #     print("**********TAX:", tax)
            #         # tax_amount = \
            #         # tax.compute_all(line.price_unit, invoice.currency_id, line.quantity, product=line.product_id,
            #         #                 partner=invoice.partner_id)['taxes'][0]['amount']
            #
            #         # print("**********TAX AMOUNT:", tax_amount)
            #
            #         # if tax.amount == 21:
            #         #     base_imponible[0] += line.price_subtotal
            #         #     iva[0] += tax_amount
            #         # elif tax.amount == 10:
            #         #     base_imponible[1] += line.price_subtotal
            #         #     iva[1] += tax_amount
            #         # elif tax.amount == 4:
            #         #     base_imponible[2] += line.price_subtotal
            #         #     iva[2] += tax_amount
            #         # else:
            #         #     base_imponible[3] += line.price_subtotal
            #         #     iva[3] += tax_amount

            worksheet.write(row_num, 12, base_imponible[0])
            worksheet.write(row_num, 13, iva[0] / base_imponible[0] * 100 if base_imponible[0] != 0 else 0)
            worksheet.write(row_num, 14, iva[0])
            worksheet.write(row_num, 15, rec_eq[0] / base_imponible[0] * 100 if base_imponible[0] != 0 else 0)
            worksheet.write(row_num, 16, rec_eq[0])
            worksheet.write(row_num, 17, "") # 'CodigoRetencion',
            worksheet.write(row_num, 18, "") # 'Base Ret',
            worksheet.write(row_num, 19, "") # 'PorRetencion',
            worksheet.write(row_num, 20, "") # 'Cuota Retención',
            worksheet.write(row_num, 21, base_imponible[1])
            worksheet.write(row_num, 22, iva[1] / base_imponible[1] * 100 if base_imponible[1] != 0 else 0)
            worksheet.write(row_num, 23, iva[1])
            worksheet.write(row_num, 24, rec_eq[1] / base_imponible[1] * 100 if base_imponible[1] != 0 else 0)
            worksheet.write(row_num, 25, rec_eq[1])
            worksheet.write(row_num, 26, base_imponible[2])
            worksheet.write(row_num, 27, iva[2] / base_imponible[2] * 100 if base_imponible[2] != 0 else 0)
            worksheet.write(row_num, 28, iva[2])
            worksheet.write(row_num, 29, rec_eq[2] / base_imponible[2] * 100 if base_imponible[2] != 0 else 0)
            worksheet.write(row_num, 30, rec_eq[2])
            worksheet.write(row_num, 31, "") # 'TipoRectificativa',
            worksheet.write(row_num, 32, "") # 'ClaseAbonoRectificativas',
            worksheet.write(row_num, 33, "") # 'EjercicioFacturaRectificada',
            worksheet.write(row_num, 34, "") # 'SerieFacturaRectificada',
            worksheet.write(row_num, 35, "") # 'NumeroFacturaRectificada',
            worksheet.write(row_num, 36, "") # 'FechaFacturaRectificada',
            worksheet.write(row_num, 37, "") # 'BaseImponibleRectificada',
            worksheet.write(row_num, 38, "") # 'CuotaIvaRectificada',
            worksheet.write(row_num, 39, "") # 'RecargoEquiRectificada',
            worksheet.write(row_num, 40, "") # 'NumeroFacturaInicial',
            worksheet.write(row_num, 41, "") # 'NumeroFacturaFinal',
            worksheet.write(row_num, 42, "") # 'IdFacturaExterno',
            worksheet.write(row_num, 43, invoice.partner_id.zip) # 'Codigo Postal',
            worksheet.write(row_num, 44, "") # 'Cod. Provincia',
            worksheet.write(row_num, 45, invoice.partner_id.state_id.name) # 'Provincia',
            worksheet.write(row_num, 46, "") # 'CodigoCanal',
            worksheet.write(row_num, 47, "") # 'CodigoDelegación',
            worksheet.write(row_num, 48, "") # 'CodDepartamento',
            worksheet.write(row_num, 49, base_imponible[2])
            worksheet.write(row_num, 50, iva[2] / base_imponible[2] * 100 if base_imponible[2] != 0 else 0)
            worksheet.write(row_num, 51, iva[2])
            worksheet.write(row_num, 52, rec_eq[2] / base_imponible[2] * 100 if base_imponible[2] != 0 else 0)
            worksheet.write(row_num, 53, rec_eq[2])

        workbook.save(file_path)

        # Read the file content and encode it in base64
        with open(file_path, 'rb') as file:
            file_data = file.read()
            encoded_file_data = base64.b64encode(file_data)

        # Create an attachment
        attachment = self.env['ir.attachment'].create({
            'name': 'contabilidad.xls',
            'type': 'binary',
            'datas': encoded_file_data,
            'store_fname': 'contabilidad.xls',
            'mimetype': 'application/vnd.ms-excel'
        })

        # Return an action to download the attachment
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
