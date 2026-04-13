import base64
import logging

import openpyxl  # Odoo 18: xlwt no soporta Python 3.10+; se usa openpyxl para .xlsx

from odoo import models, fields, api

_logger = logging.getLogger(__name__)


class DiazCepedaExportXLSContability(models.TransientModel):
    _name = "diazcepeda.export.xls.contability"
    _description = "Informe de contabilidad"

    start_date = fields.Date(string="Fecha inicio", required=True, default=fields.Date.today)
    end_date = fields.Date(string="Fecha fin", required=True, default=fields.Date.today)
    providers_check = fields.Boolean(string="Proveedores")
    customers_check = fields.Boolean(string="Clientes")

    generate_xls_file = fields.Binary(
        "Generated file",
        help="Campo técnico para almacenar el fichero XLSX generado antes de la descarga."
    )

    def export_file(self):
        """Genera el fichero XLSX con el desglose contable de las facturas del período."""
        self.ensure_one()

        domain = [('invoice_date', '>=', self.start_date), ('invoice_date', '<=', self.end_date)]

        if self.providers_check and not self.customers_check:
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund']))
        elif self.customers_check and not self.providers_check:
            domain.append(('move_type', 'in', ['out_invoice', 'out_refund']))
        else:
            # FIX: sin filtro se incluirían asientos de diario (move_type='entry') con
            # invoice_date=None → AttributeError en .year/.month o partner_id vacío.
            domain.append(('move_type', 'in', ['in_invoice', 'in_refund', 'out_invoice', 'out_refund']))

        invoices = self.env['account.move'].search(domain)

        file_path = '/tmp/contabilidad.xlsx'

        # Crear libro Excel con openpyxl (1-indexado, compatible Python 3.10+)
        workbook = openpyxl.Workbook()
        worksheet = workbook.active
        worksheet.title = 'Contabilidad'

        headers = [
            'Serie', 'Factura', 'Fecha', 'FechaOperacion', 'CodigoCuenta',
            'CIFEUROPEO', 'Cliente', 'Comentario', 'Contrapartida', 'Cod.Transacion',
            'ClaveOperaciónFact', 'Importe Factura', 'Base Imponible1', '%Iva1',
            'Cuota Iva1', '%RecEq1', 'Cuota Rec1', 'CodigoRetencion', 'Base Ret',
            'PorRetencion', 'Cuota Retención', 'Base Imponible2', '%Iva2', 'Cuota Iva2',
            '%RecEq2', 'Cuota Rec2', 'Base Imponible3', '%Iva3', 'Cuota Iva3',
            '%RecEq3', 'Cuota Rec3', 'TipoRectificativa', 'ClaseAbonoRectificativas',
            'EjercicioFacturaRectificada', 'SerieFacturaRectificada',
            'NumeroFacturaRectificada', 'FechaFacturaRectificada',
            'BaseImponibleRectificada', 'CuotaIvaRectificada', 'RecargoEquiRectificada',
            'NumeroFacturaInicial', 'NumeroFacturaFinal', 'IdFacturaExterno',
            'Codigo Postal', 'Cod. Provincia', 'Provincia', 'CodigoCanal',
            'CodigoDelegación', 'CodDepartamento', 'Base Imponible4', '%Iva4',
            'Cuota Iva4', '%RecEq4', 'Cuota Rec4',
        ]
        # openpyxl: filas y columnas son 1-indexadas
        for col_idx, header in enumerate(headers, start=1):
            worksheet.cell(row=1, column=col_idx, value=header)

        for row_idx, invoice in enumerate(invoices, start=2):
            # FIX: saltar facturas sin fecha (evita AttributeError en .year/.month/.day)
            if not invoice.invoice_date:
                _logger.warning("Factura omitida en XLS: id=%s sin invoice_date", invoice.id)
                continue

            is_refound = invoice.move_type in ['out_refund', 'in_refund']
            sign = -1 if is_refound else 1

            # ── Desglose de impuestos desde líneas de factura (compatible Odoo 18) ──────
            # En Odoo 18 tax_totals cambió de estructura; se leen las líneas directamente.
            iva_groups = {}      # {tasa: {'base': X, 'iva': Y}}
            recargo_groups = {}  # {tasa: cantidad}
            codigo_retenciones = ''
            base_retenciones = 0.0
            porcentaje_retenciones = 0.0
            total_retenciones = 0.0

            for tax_line in invoice.line_ids.filtered(lambda l: l.tax_line_id):
                tax = tax_line.tax_line_id
                es_type = getattr(tax, 'l10n_es_type', '') or ''
                rate = float(tax.amount)
                # balance < 0 en facturas (crédito); usamos valor absoluto y aplicamos signo
                tax_amount = sign * abs(float(tax_line.balance))
                base_amount = sign * abs(float(tax_line.tax_base_amount))

                if 'recargo' in es_type:
                    recargo_groups[rate] = recargo_groups.get(rate, 0.0) + tax_amount
                elif 'retencion' in es_type:
                    codigo_retenciones = tax.name
                    base_retenciones = base_amount
                    porcentaje_retenciones += rate
                    total_retenciones += tax_amount
                else:
                    # IVA sujeto (sujeto_comun, sujeto_exento, etc.)
                    if rate not in iva_groups:
                        iva_groups[rate] = {'base': base_amount, 'iva': 0.0}
                    iva_groups[rate]['iva'] += tax_amount

            # Ordenar por tasa ascendente para mantener consistencia de índices
            sorted_iva_rates = sorted(iva_groups.keys())
            sorted_recargo_rates = sorted(recargo_groups.keys())

            base_imponible = [iva_groups[r]['base'] for r in sorted_iva_rates]
            porcentaje_iva = list(sorted_iva_rates)
            total_iva = [iva_groups[r]['iva'] for r in sorted_iva_rates]
            # Parear recargos con IVA por posición (mismo orden ascendente de tasa)
            porcentaje_recargo = sorted_recargo_rates + [0] * (len(sorted_iva_rates) - len(sorted_recargo_rates))
            total_recargo = [recargo_groups[r] for r in sorted_recargo_rates] + [0] * (len(iva_groups) - len(sorted_recargo_rates))

            # ── Formateo del número de factura ────────────────────────────────────────
            invoice_name = invoice.name or ''
            if invoice_name.startswith("RFAC"):
                invoice_name = "9" + invoice_name.replace("RFAC", "")
            if invoice_name.startswith("FAC"):
                invoice_name = invoice_name.replace("FAC", "")
            invoice_name = invoice_name.replace("2025", "25").replace("/", "")

            invoice_vat = invoice.partner_id.vat or ''
            if invoice_vat:
                invoice_vat = invoice_vat.replace("ES", "")

            # ── Escritura de columnas (openpyxl: row y column son 1-indexados) ────────
            def w(col, value):
                """Alias para worksheet.cell con offset de columna 1-indexado."""
                worksheet.cell(row=row_idx, column=col + 1, value=value)

            w(0, str(invoice.invoice_date.year))   # Serie
            w(1, invoice_name)                      # Factura
            fecha = f"{invoice.invoice_date.day}/{invoice.invoice_date.month}/{invoice.invoice_date.year}"
            w(2, fecha)                             # Fecha
            w(3, fecha)                             # FechaOperacion
            w(4, "")                                # CodigoCuenta
            w(5, invoice_vat)                       # CIFEUROPEO
            w(6, invoice.partner_id.name)           # Cliente
            w(7, f"FRA. Nº. {invoice_name} - {invoice.partner_id.name}")  # Comentario
            w(8, "")                                # Contrapartida
            w(9, "")                                # Cod.Transacion
            w(10, "")                               # ClaveOperaciónFact
            w(11, invoice.amount_total if not is_refound else -invoice.amount_total)  # Importe Factura

            # Columnas IVA 21%
            idx_21 = porcentaje_iva.index(21.0) if 21.0 in porcentaje_iva else -1
            if idx_21 >= 0:
                _logger.debug("IVA 21%% base=%s cuota=%s", base_imponible[idx_21], total_iva[idx_21])
                w(12, base_imponible[idx_21])
                w(13, porcentaje_iva[idx_21])
                w(14, total_iva[idx_21])
                w(15, porcentaje_recargo[idx_21] if idx_21 < len(porcentaje_recargo) else 0)
                w(16, total_recargo[idx_21] if idx_21 < len(total_recargo) else 0)
            else:
                for c in range(12, 17):
                    w(c, 0)

            w(17, codigo_retenciones)  # CodigoRetencion
            w(18, base_retenciones)    # Base Ret
            w(19, porcentaje_retenciones)  # PorRetencion
            w(20, total_retenciones)   # Cuota Retención

            # Columnas IVA 10%
            idx_10 = porcentaje_iva.index(10.0) if 10.0 in porcentaje_iva else (
                porcentaje_iva.index(10) if 10 in porcentaje_iva else -1)
            if idx_10 >= 0:
                w(21, base_imponible[idx_10])
                w(22, porcentaje_iva[idx_10])
                w(23, total_iva[idx_10])
                w(24, porcentaje_recargo[idx_10] if idx_10 < len(porcentaje_recargo) else 0)
                w(25, total_recargo[idx_10] if idx_10 < len(total_recargo) else 0)
            else:
                for c in range(21, 26):
                    w(c, 0)

            # Columnas IVA 4%
            idx_4 = porcentaje_iva.index(4.0) if 4.0 in porcentaje_iva else (
                porcentaje_iva.index(4) if 4 in porcentaje_iva else -1)
            if idx_4 >= 0:
                w(26, base_imponible[idx_4])
                w(27, porcentaje_iva[idx_4])
                w(28, total_iva[idx_4])
                w(29, porcentaje_recargo[idx_4] if idx_4 < len(porcentaje_recargo) else 0)
                w(30, total_recargo[idx_4] if idx_4 < len(total_recargo) else 0)
            else:
                for c in range(26, 31):
                    w(c, 0)

            # Columnas de rectificativas y datos adicionales
            for c in range(31, 43):
                w(c, "")

            w(43, invoice.partner_id.zip or "")      # Codigo Postal
            w(44, "")                                 # Cod. Provincia
            w(45, invoice.partner_id.state_id.name if invoice.partner_id.state_id else "")  # Provincia
            w(46, "")                                 # CodigoCanal
            w(47, "")                                 # CodigoDelegación
            w(48, "")                                 # CodDepartamento

            # Columnas IVA 0%
            idx_0 = porcentaje_iva.index(0.0) if 0.0 in porcentaje_iva else (
                porcentaje_iva.index(0) if 0 in porcentaje_iva else -1)
            if idx_0 >= 0:
                w(49, base_imponible[idx_0])
                w(50, porcentaje_iva[idx_0])
                w(51, total_iva[idx_0])
                w(52, porcentaje_recargo[idx_0] if idx_0 < len(porcentaje_recargo) else 0)
                w(53, total_recargo[idx_0] if idx_0 < len(total_recargo) else 0)
            else:
                for c in range(49, 54):
                    w(c, 0)

        workbook.save(file_path)

        with open(file_path, 'rb') as f:
            encoded_file_data = base64.b64encode(f.read())

        attachment = self.env['ir.attachment'].create({
            'name': 'contabilidad.xlsx',
            'type': 'binary',
            'datas': encoded_file_data,
            # store_fname es campo interno de Odoo; no se pasa en create()
            'mimetype': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }
