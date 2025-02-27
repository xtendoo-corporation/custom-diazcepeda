import base64

import xlwt
import os
from odoo import models, fields, api


class DiazCepedaExportXLSContability(models.TransientModel):
    _name = "diazcepeda.export.xls.contability"
    _description = "Informe de contabilidad"

    start_date = fields.Date(string="Fecha inico", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Fecha fin", required=True, default=fields.Date.today)

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

            # Initialize VAT breakdown columns
            base_imponible = []
            porcentaje_iva = []
            total_iva = []
            porcentaje_recargo = []
            total_recargo = []
            codigo_retenciones = ''
            base_retenciones = 0
            porcentaje_retenciones = 0
            total_retenciones = 0

            for key, tax_total in invoice.tax_totals.items():
                if key == 'groups_by_subtotal':
                    groups = tax_total['Base imponible']
                    for group in groups:
                        tax_group = self.env['account.tax.group'].browse(group['tax_group_id'])
                        if tax_group:
                            account_taxes = self.env['account.tax'].search([('tax_group_id', '=', tax_group.id)])
                            if account_taxes:
                                account_tax = account_taxes[0]
                                group['tax_group_amount'] = account_tax.amount
                                group['tax_l10n_es_type'] = account_tax.l10n_es_type

                    for group in sorted(filter(lambda x: 'sujeto' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_amount']):
                        base_imponible.append(group['tax_group_base_amount'])
                        if group['tax_group_amount'] == 0:
                            porcentaje_iva.append(0)
                            total_iva.append(0)
                            porcentaje_recargo.append(0)
                            total_recargo.append(0)
                        else:
                            porcentaje_iva.append(group['tax_group_amount'])
                            total_iva.append(group['tax_group_base_amount'] * group['tax_group_amount'] / 100)

                    for group in sorted(filter(lambda x: 'recargo' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_amount']):
                        porcentaje_recargo.append(group['tax_group_amount'])
                        total_recargo.append(group['tax_group_base_amount'] * group['tax_group_amount'] / 100)

                    for group in sorted(filter(lambda x: 'retencion' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_amount']):
                        base_retenciones = group['tax_group_base_amount']
                        codigo_retenciones = group['tax_group_name']
                        porcentaje_retenciones += group['tax_group_amount']
                        total_retenciones += group['tax_group_base_amount'] * group['tax_group_amount'] / 100

            # Escribo los datos en el excel
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

            worksheet.write(row_num, 12, base_imponible[0] if len(base_imponible) > 0 else 0)
            worksheet.write(row_num, 13, porcentaje_iva[0] if len(porcentaje_iva) > 0 else 0)
            worksheet.write(row_num, 14, total_iva[0] if len(total_iva) > 0 else 0)
            worksheet.write(row_num, 15, porcentaje_recargo[0] if len(porcentaje_recargo) > 0 else 0)
            worksheet.write(row_num, 16, total_recargo[0] if len(total_recargo) > 0 else 0)
            worksheet.write(row_num, 17, codigo_retenciones)  # 'CodigoRetencion',
            worksheet.write(row_num, 18, base_retenciones)  # 'Base Ret',
            worksheet.write(row_num, 19, porcentaje_retenciones)  # 'PorRetencion',
            worksheet.write(row_num, 20, total_retenciones)  # 'Cuota Retención',
            worksheet.write(row_num, 21, base_imponible[1] if len(base_imponible) > 1 else 0)
            worksheet.write(row_num, 22, porcentaje_iva[1] if len(porcentaje_iva) > 1 else 0)
            worksheet.write(row_num, 23, total_iva[1] if len(total_iva) > 1 else 0)
            worksheet.write(row_num, 24, porcentaje_recargo[1] if len(porcentaje_recargo) > 1 else 0)
            worksheet.write(row_num, 25, total_recargo[1] if len(total_recargo) > 1 else 0)
            worksheet.write(row_num, 26, base_imponible[2] if len(base_imponible) > 2 else 0)
            worksheet.write(row_num, 27, porcentaje_iva[2] if len(porcentaje_iva) > 2 else 0)
            worksheet.write(row_num, 28, total_iva[2] if len(total_iva) > 2 else 0)
            worksheet.write(row_num, 29, porcentaje_recargo[2] if len(porcentaje_recargo) > 2 else 0)
            worksheet.write(row_num, 30, total_recargo[2] if len(total_recargo) > 2 else 0)
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
            worksheet.write(row_num, 50, porcentaje_iva[3] if len(porcentaje_iva) > 3 else 0)
            worksheet.write(row_num, 51, total_iva[3] if len(total_iva) > 3 else 0)
            worksheet.write(row_num, 52, porcentaje_recargo[3] if len(porcentaje_recargo) > 3 else 0)
            worksheet.write(row_num, 53, total_recargo[3] if len(total_recargo) > 3 else 0)

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
