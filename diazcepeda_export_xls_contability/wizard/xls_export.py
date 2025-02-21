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


            # Initialize VAT breakdown columns
            base_imponible = [0,0,0]
            iva = []
            rec_eq = []
            ret_eq = []

            # for key, tax_total in invoice.tax_totals.items():
            #     print("*******tax_total (key):", key)
            #     print("*******tax_total (type):", type(tax_total))
            #     print("*******tax_total (content):", tax_total)

            for key, tax_total in invoice.tax_totals.items():
                if key == 'groups_by_subtotal':
                    for group in sorted(tax_total['Base imponible'], key=lambda x: x['tax_group_name']):
                        print("*******group:", group)
                        base_imponible.append(group['tax_group_base_amount'])
                        iva_percentage = group['tax_group_name']

                        tax_group = self.env['account.tax.group'].browse(group['tax_group_id'])
                        taxes = self.env['account.tax'].search([('tax_group_id', '=', tax_group.id)])
                        tax_details = [(tax.name, tax.amount, tax.l10n_es_type) for tax in taxes]
                        # print("Tax Details:", tax_details)

                        if 'tax_group_amount' in group:
                            if any(tax.l10n_es_type == 'recargo' for tax in tax_group.tax_ids):
                                    print("*******recargo:", group['tax_group_amount'])
                                    rec_eq.append(group['tax_group_amount'])
                            elif any(tax.l10n_es_type == 'retencion' for tax in tax_group.tax_ids):
                                    print("*******retencion:", group['tax_group_amount'])
                                    ret_eq.append(group['tax_group_amount'])
                            else:
                                    print("*******iva:", group['tax_group_amount'])
                                    iva.append(group['tax_group_amount'])

            print(f"Invoice: {invoice.name}")
            print("base_imponible:", base_imponible)
            print("iva:", iva)
            print("rec_eq:", rec_eq)
            print("ret_eq:", ret_eq)

            worksheet.write(row_num, 12, base_imponible[0] if len(base_imponible) > 0 else 0)
            worksheet.write(row_num, 13,
                            (iva[0] / base_imponible[0] * 100) if len(base_imponible) > 0 and base_imponible[0] != 0 and len(iva) > 0 else 0)
            worksheet.write(row_num, 14, iva[0] if len(iva) > 0 else 0)
            worksheet.write(row_num, 15,
                            (rec_eq[0] / base_imponible[0] * 100) if len(base_imponible) > 0 and base_imponible[0] != 0 and len(rec_eq) > 0 else 0)
            worksheet.write(row_num, 16, rec_eq[0] if len(rec_eq) > 0 else 0)
            worksheet.write(row_num, 17, "")  # 'CodigoRetencion',
            worksheet.write(row_num, 18, "")  # 'Base Ret',
            worksheet.write(row_num, 19, "")  # 'PorRetencion',
            worksheet.write(row_num, 20, "")  # 'Cuota Retención',
            worksheet.write(row_num, 21, base_imponible[1] if len(base_imponible) > 1 else 0)
            worksheet.write(row_num, 22,
                            (iva[1] / base_imponible[1] * 100) if len(base_imponible) > 1 and base_imponible[1] != 0 and len(iva) > 1 else 0)
            worksheet.write(row_num, 23, iva[1] if len(iva) > 1 else 0)
            worksheet.write(row_num, 24,
                            (rec_eq[1] / base_imponible[1] * 100) if len(base_imponible) > 1 and base_imponible[1] != 0 and len(rec_eq) > 1 else 0)
            worksheet.write(row_num, 25, rec_eq[1] if len(rec_eq) > 1 else 0)
            worksheet.write(row_num, 26, base_imponible[2] if len(base_imponible) > 2 else 0)
            worksheet.write(row_num, 27,
                            (iva[2] / base_imponible[2] * 100) if len(base_imponible) > 2 and base_imponible[2] != 0 and len(iva) > 2 else 0)
            worksheet.write(row_num, 28, iva[2] if len(iva) > 2 else 0)
            worksheet.write(row_num, 29,
                            (rec_eq[2] / base_imponible[2] * 100) if len(base_imponible) > 2 and base_imponible[2] != 0 and len(rec_eq) > 2 else 0)
            worksheet.write(row_num, 30, rec_eq[2] if len(rec_eq) > 2 else 0)
            worksheet.write(row_num, 31, "")  # 'TipoRectificativa',
            worksheet.write(row_num, 32, "")  # 'ClaseAbonoRectificativas',
            worksheet.write(row_num, 33, "")  # 'EjercicioFacturaRectificada',
            worksheet.write(row_num, 34, "")  # 'SerieFacturaRectificada',
            worksheet.write(row_num, 35, "")  # 'NumeroFacturaRectificada',
            worksheet.write(row_num, 36, "")  # 'FechaFacturaRectificada',
            worksheet.write(row_num, 37, "")  # 'BaseImponibleRectificada',
            worksheet.write(row_num, 38, "")  # 'CuotaIvaRectificada',
            worksheet.write(row_num, 39, "")  # 'RecargoEquiRectificada',
            worksheet.write(row_num, 40, "")  # 'NumeroFacturaInicial',
            worksheet.write(row_num, 41, "")  # 'NumeroFacturaFinal',
            worksheet.write(row_num, 42, "")  # 'IdFacturaExterno',
            worksheet.write(row_num, 43, invoice.partner_id.zip)  # 'Codigo Postal',
            worksheet.write(row_num, 44, "")  # 'Cod. Provincia',
            worksheet.write(row_num, 45, invoice.partner_id.state_id.name)  # 'Provincia',
            worksheet.write(row_num, 46, "")  # 'CodigoCanal',
            worksheet.write(row_num, 47, "")  # 'CodigoDelegación',
            worksheet.write(row_num, 48, "")  # 'CodDepartamento',
            worksheet.write(row_num, 49, base_imponible[3] if len(base_imponible) > 3 else 0)
            worksheet.write(row_num, 50,
                            (iva[3] / base_imponible[3] * 100) if len(base_imponible) > 3 and base_imponible[3] != 0 and len(iva) > 3 else 0)
            worksheet.write(row_num, 51, iva[3] if len(iva) > 3 else 0)
            worksheet.write(row_num, 52,
                            (rec_eq[3] / base_imponible[3] * 100) if len(base_imponible) > 3 and base_imponible[3] != 0 and len(rec_eq) > 3 else 0)
            worksheet.write(row_num, 53, rec_eq[3] if len(rec_eq) > 3 else 0)

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
