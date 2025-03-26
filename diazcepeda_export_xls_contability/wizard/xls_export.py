import base64

import xlwt
import os

from dateutil.rrule import YEARLY

from odoo import models, fields, api


class DiazCepedaExportXLSContability(models.TransientModel):
    _name = "diazcepeda.export.xls.contability"
    _description = "Informe de contabilidad"

    start_date = fields.Date(string="Fecha inicio", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Fecha fin", required=True, default=fields.Date.today)
    providers_check = fields.Boolean(string="Proveedores")
    customers_check = fields.Boolean(string="Clientes")

    generate_xls_file = fields.Binary(
        "Generated file",
        help="Technical field used to temporarily hold the generated XLS file before its downloaded."
    )

    def export_file(self, xlsxwriter=None):
        """ Process the file chosen in the wizard, create bank statement(s) and go to reconciliation. """
        self.ensure_one()

        domain = [('invoice_date', '>=', self.start_date), ('invoice_date', '<=', self.end_date)]

        if self.providers_check and not self.customers_check:
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        elif self.customers_check and not self.providers_check:
            domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))
        elif self.providers_check and self.customers_check:
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']))

        invoices = self.env['account.move'].search(domain)

        # print("*******INVOICES:", invoices)
        # print("*******start_date:", self.start_date)
        # print("*******end_date:", self.end_date)

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
            is_refound = invoice.move_type in ['out_refund', 'in_refund']

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

                print("*"*80)
                print("key:", key)
                print("tax_total:", tax_total)

                if key == 'groups_by_subtotal':
                    groups = tax_total['Base imponible']
                    for group in groups:

                        print("-"*80)
                        print("group:", group)

                        tax_group = self.env['account.tax.group'].browse(group['tax_group_id'])
                        if tax_group:
                            account_taxes = self.env['account.tax'].search([('tax_group_id', '=', tax_group.id)])
                            if account_taxes:
                                account_tax = account_taxes[0]

                                print("tax_group_amount antesssssssssssssssssssss:", group['tax_group_amount'])
                                group['tax_group_percentage'] = account_tax.amount
                                print("tax_group_amount despuesssssssssssssssssss", group['tax_group_amount'])
                                print("group despuesssssssssssssssssssss:", group)

                                group['tax_l10n_es_type'] = account_tax.l10n_es_type

                    for group in sorted(filter(lambda x: 'sujeto' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_percentage']):
                        base_imponible.append(group['tax_group_base_amount'] if not is_refound else -group['tax_group_base_amount'])
                        if group['tax_group_percentage'] == 0:
                            porcentaje_iva.append(0)
                            total_iva.append(0)
                            porcentaje_recargo.append(0)
                            total_recargo.append(0)
                        else:

                            print("#"*80)
                            print("group['tax_group_amount']:", group['tax_group_amount'])
                            print("group['tax_group_base_amount']:", group['tax_group_base_amount'])

                            porcentaje_iva.append(group['tax_group_percentage'])
                            total_iva.append(group['tax_group_amount'] if not is_refound else -group['tax_group_amount'])

                    for group in sorted(filter(lambda x: 'recargo' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_percentage']):
                        porcentaje_recargo.append(group['tax_group_percentage'])
                        total_recargo.append(group['tax_group_amount'] if not is_refound else -group['tax_group_amount'])

                    for group in sorted(filter(lambda x: 'retencion' in x['tax_l10n_es_type'], groups), key=lambda x: x['tax_group_percentage']):
                        base_retenciones = group['tax_group_base_amount']
                        codigo_retenciones = group['tax_group_name']
                        porcentaje_retenciones += group['tax_group_percentage']
                        total_retenciones += group['tax_group_amount']

            # Escribo los datos en el excel
            worksheet.write(row_num, 0, str(invoice.invoice_date.year))  # 'Serie',
            worksheet.write(row_num, 1, invoice.name.replace("/","")) # 'Factura',
            worksheet.write(row_num, 2, str(invoice.invoice_date.day) + "/" + str(invoice.invoice_date.month) + "/" + str(invoice.invoice_date.year))  # 'Fecha',
            worksheet.write(row_num, 3, str(invoice.invoice_date.day) + "/" + str(invoice.invoice_date.month) + "/" + str(invoice.invoice_date.year))  # 'FechaOperacion',
            worksheet.write(row_num, 4, "")  # 'CodigoCuenta',mu
            worksheet.write(row_num, 5, invoice.partner_id.vat)  # 'CIFEUROPEO',
            worksheet.write(row_num, 6, invoice.partner_id.name)  # 'Cliente',
            worksheet.write(row_num, 7, "FRA. Nº. " + invoice.name + " - " + invoice.partner_id.name)  # 'Comentario',
            worksheet.write(row_num, 8, "")  # 'Contrapartida',
            worksheet.write(row_num, 9, "")  # 'Cod.Transacion',
            worksheet.write(row_num, 10, "") # 'ClaveOperaciónFact',
            worksheet.write(row_num, 11, invoice.amount_total if not is_refound else -invoice.amount_total) # 'Importe Factura'

            # Buscamos el indice del 21% en porcentaje_iva *
            indice_porcentaje_iva_21 = porcentaje_iva.index(21.0) if 21.0 in porcentaje_iva else -1
            if indice_porcentaje_iva_21 >= 0:

                print("base_imponible:", base_imponible)
                print("porcentaje_iva:", porcentaje_iva)
                print("total_iva:", total_iva)
                print("porcentaje_recargo:", porcentaje_recargo)
                print("total_recargo:", total_recargo)
                print("indice_porcentaje_iva_21:", indice_porcentaje_iva_21)

                worksheet.write(row_num, 12, base_imponible[indice_porcentaje_iva_21])
                worksheet.write(row_num, 13, porcentaje_iva[indice_porcentaje_iva_21])
                worksheet.write(row_num, 14, total_iva[indice_porcentaje_iva_21])
                worksheet.write(row_num, 15, porcentaje_recargo[indice_porcentaje_iva_21] if indice_porcentaje_iva_21 < len(porcentaje_recargo) else 0)
                worksheet.write(row_num, 16, total_recargo[indice_porcentaje_iva_21] if indice_porcentaje_iva_21 < len(porcentaje_recargo) > 0 else 0)
            else:
                worksheet.write(row_num, 12, 0)
                worksheet.write(row_num, 13, 0)
                worksheet.write(row_num, 14, 0)
                worksheet.write(row_num, 15, 0)
                worksheet.write(row_num, 16, 0)

            worksheet.write(row_num, 17, codigo_retenciones)  # 'CodigoRetencion',
            worksheet.write(row_num, 18, base_retenciones)  # 'Base Ret',
            worksheet.write(row_num, 19, porcentaje_retenciones)  # 'PorRetencion',
            worksheet.write(row_num, 20, total_retenciones)  # 'Cuota Retención',

            # Buscamos el indice del 10% en porcentaje_iva
            indice_porcentaje_iva_10 = porcentaje_iva.index(10) if 10 in porcentaje_iva else -1

            if indice_porcentaje_iva_10 >= 0:

                print("base_imponible:", base_imponible)
                print("porcentaje_iva:", porcentaje_iva)
                print("total_iva:", total_iva)
                print("porcentaje_recargo:", porcentaje_recargo)
                print("total_recargo:", total_recargo)
                print("indice_porcentaje_iva_10:", indice_porcentaje_iva_10)
                print("len(porcentaje_recargo):", len(porcentaje_recargo) )

                worksheet.write(row_num, 21, base_imponible[indice_porcentaje_iva_10])
                worksheet.write(row_num, 22, porcentaje_iva[indice_porcentaje_iva_10])
                worksheet.write(row_num, 23, total_iva[indice_porcentaje_iva_10])
                worksheet.write(row_num, 24, porcentaje_recargo[indice_porcentaje_iva_10] if indice_porcentaje_iva_10 < len(porcentaje_recargo) else 0)
                worksheet.write(row_num, 25, total_recargo[indice_porcentaje_iva_10] if indice_porcentaje_iva_10 < len(porcentaje_recargo) else 0)
            else:
                worksheet.write(row_num, 21, 0)
                worksheet.write(row_num, 22, 0)
                worksheet.write(row_num, 23, 0)
                worksheet.write(row_num, 24, 0)
                worksheet.write(row_num, 25, 0)

            # Buscamos el indice del 4% en porcentaje_iva
            indice_porcentaje_iva_4 = porcentaje_iva.index(4) if 4 in porcentaje_iva else -1

            if indice_porcentaje_iva_4 >= 0:

                print("base_imponible:", base_imponible)
                print("porcentaje_iva:", porcentaje_iva)
                print("total_iva:", total_iva)
                print("porcentaje_recargo:", porcentaje_recargo)
                print("total_recargo:", total_recargo)
                print("indice_porcentaje_iva_4:", indice_porcentaje_iva_4)

                worksheet.write(row_num, 26, base_imponible[indice_porcentaje_iva_4])
                worksheet.write(row_num, 27, porcentaje_iva[indice_porcentaje_iva_4])
                worksheet.write(row_num, 28, total_iva[indice_porcentaje_iva_4])
                worksheet.write(row_num, 29, porcentaje_recargo[indice_porcentaje_iva_4] if indice_porcentaje_iva_4 < len(porcentaje_recargo) else 0)
                worksheet.write(row_num, 30, total_recargo[indice_porcentaje_iva_4] if indice_porcentaje_iva_4 < len(porcentaje_recargo) else 0)
            else:
                worksheet.write(row_num, 26, 0)
                worksheet.write(row_num, 27, 0)
                worksheet.write(row_num, 28, 0)
                worksheet.write(row_num, 29, 0)
                worksheet.write(row_num, 30, 0)

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

            # Buscamos el indice del 0% en porcentaje_iva
            indice_porcentaje_iva_0 = porcentaje_iva.index(0) if 0 in porcentaje_iva else -1
            if indice_porcentaje_iva_0 >= 0:

                print("base_imponible:", base_imponible)
                print("porcentaje_iva:", porcentaje_iva)
                print("total_iva:", total_iva)
                print("porcentaje_recargo:", porcentaje_recargo)
                print("total_recargo:", total_recargo)
                print("indice_porcentaje_iva_0:", indice_porcentaje_iva_0)
                print("len(porcentaje_recargo):", len(porcentaje_recargo) )

                worksheet.write(row_num, 49, base_imponible[indice_porcentaje_iva_0])
                worksheet.write(row_num, 50, porcentaje_iva[indice_porcentaje_iva_0])
                worksheet.write(row_num, 51, total_iva[indice_porcentaje_iva_0])
                worksheet.write(row_num, 52, porcentaje_recargo[indice_porcentaje_iva_0] if indice_porcentaje_iva_0 < len(porcentaje_recargo) else 0)
                worksheet.write(row_num, 53, total_recargo[indice_porcentaje_iva_0] if indice_porcentaje_iva_0 < len(porcentaje_recargo) else 0)
            else:
                worksheet.write(row_num, 49, 0)
                worksheet.write(row_num, 50, 0)
                worksheet.write(row_num, 51, 0)
                worksheet.write(row_num, 52, 0)
                worksheet.write(row_num, 53, 0)

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
