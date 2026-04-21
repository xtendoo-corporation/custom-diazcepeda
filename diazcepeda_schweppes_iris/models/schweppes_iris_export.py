from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from datetime import datetime
from ..tools import iris_formatter

class SchweppesIrisExport(models.Model):
    _name = 'schweppes.iris.export'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = 'Schweppes IRIS Export'
    _order = 'create_date desc'

    name = fields.Char(string='Referencia', required=True, copy=False, readonly=True, default=lambda self: _('Nuevo'))
    date_from = fields.Date(string='Fecha Desde', required=True)
    date_to = fields.Date(string='Fecha Hasta', required=True)
    company_id = fields.Many2one('res.company', string='Compañía', default=lambda self: self.env.company)
    state = fields.Selection([
        ('draft', 'Borrador'),
        ('done', 'Generado')
    ], string='Estado', default='draft')

    file_data = fields.Binary(string='Archivo TXT', readonly=True)
    file_name = fields.Char(string='Nombre del Archivo', readonly=True)

    # Campos computados para la previsualización del archivo
    preview_file_data = fields.Binary(string='Archivo TXT Previsualización', readonly=True, compute='_compute_preview_file_data')
    preview_file_name = fields.Char(string='Nombre Archivo Previsualización', readonly=True, compute='_compute_preview_file_data')

    # Summary fields for UX
    invoice_count = fields.Integer(string='Nº Facturas', readonly=True, tracking=True)
    partner_count = fields.Integer(string='Nº Clientes', readonly=True, tracking=True)
    line_count = fields.Integer(string='Nº Líneas Venta', readonly=True, tracking=True)

    invoice_ids = fields.Many2many('account.move', string='Facturas Incluidas', readonly=True)
    partner_ids = fields.Many2many('res.partner', string='Clientes Incluidos', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 18: create recibe una lista de dicts
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('schweppes.iris.export') or _('Nuevo')
        return super().create(vals_list)

    def action_generate_file(self):
        self.ensure_one()

        # 1. Gather Invoices
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('invoice_line_ids.product_id.schweppes_product_code', '!=', False)
        ]
        invoices = self.env['account.move'].search(domain)

        if not invoices:
            raise UserError(_("No se han encontrado facturas publicadas en este rango de fechas."))

        # 2. Process Lines & Master Data
        lines = []
        orders_count = len(invoices)
        partners_to_export = self.env['res.partner']

        # CT (Header)
        now = datetime.now()
        date_tx = now.strftime('%Y%m%d')
        nn = "01"
        dist_code = self.company_id.schweppes_distributor_code or "1000026677"
        lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))

        for move in invoices:
            partners_to_export |= move.partner_id
            route = move.partner_id.schweppes_route or "56"
            cust_code = move.partner_id.schweppes_customer_code or move.partner_id.ref or str(move.partner_id.id)
            date_inv = move.invoice_date.strftime('%Y%m%d')
            payment_type = 'CO'
            lines.append(iris_formatter.format_dicp(
                move.name[-10:],
                route,
                cust_code,
                date_inv,
                date_inv,
                payment_type,
                move.ref or ""
            ))
            for line in move.invoice_line_ids:
                if not line.product_id or not line.product_id.schweppes_product_code:
                    continue
                prod_code = line.product_id.schweppes_product_code
                lines.append(iris_formatter.format_didp(
                    move.name[-10:],
                    prod_code,
                    line.quantity,
                    0,
                    line.quantity,
                    0,
                    line.price_unit
                ))
                if line.discount:
                    disc_amount = (line.price_unit * line.quantity) * (line.discount / 100.0)
                    lines.append(iris_formatter.format_didd(
                        move.name[-10:],
                        prod_code,
                        'ES',
                        disc_amount
                    ))

        for partner in partners_to_export:
            lines.append(iris_formatter.format_dimc(
                partner.schweppes_customer_code or partner.ref or str(partner.id),
                partner.schweppes_route or "56",
                partner.name,
                partner.commercial_partner_id.name,
                partner.street or "",
                partner.vat or "",
                partner.schweppes_delivery_type or "D",
                "01",
                "CO",
                "AC",
                "", "", "S", "SSSSSSS",
                "", "", "", "N",
                partner.email or "",
                partner.city or "",
                partner.state_id.name if partner.state_id else "",
                partner.zip or "",
                partner.phone or "",
                "",
                partner.schweppes_customer_code or "",
                ""
            ))

        records_count = len(lines) + 1
        lines.append(iris_formatter.format_ft(records_count, orders_count))

        content = "\r\n".join(lines) + "\r\n"
        file_name = f"{now.strftime('%d%m%Y')}SCHW_IRIS_VENTAS.txt"

        self.write({
            'file_data': base64.b64encode(content.encode('utf-8')),
            'file_name': file_name,
            'state': 'done',
            'invoice_count': len(invoices),
            'partner_count': len(partners_to_export),
            'line_count': sum([len(i.invoice_line_ids.filtered(lambda l: l.product_id.schweppes_product_code)) for i in invoices]),
            'invoice_ids': [(6, 0, invoices.ids)],
            'partner_ids': [(6, 0, partners_to_export.ids)],
        })

        # Eliminar adjuntos anteriores vinculados a este registro
        old_attachments = self.env['ir.attachment'].search([
            ('res_model', '=', self._name),
            ('res_id', '=', self.id),
            ('mimetype', '=', 'text/plain'),
        ])
        if old_attachments:
            old_attachments.unlink()

        # Crear el nuevo adjunto
        attachment = self.env['ir.attachment'].create({
            'name': file_name,
            'datas': base64.b64encode(content.encode('utf-8')),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'text/plain',
            'public': True,
        })

        usuario = self.env.user.name
        self.message_post(
            body=_("El usuario %s, ha generado/regenerado el fichero IRIS (%s facturas, %s clientes).") % (usuario, len(invoices), len(partners_to_export)),
            attachment_ids=[attachment.id]
        )

        # Recargar la vista formulario para reflejar cambios
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_preview_file(self):
        self.ensure_one()
        # Reutiliza la lógica de generación, pero solo genera el archivo y lo devuelve como descarga
        # No cambia el estado ni crea adjuntos ni mensajes
        domain = [
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', self.date_from),
            ('invoice_date', '<=', self.date_to),
            ('company_id', '=', self.company_id.id),
            ('invoice_line_ids.product_id.schweppes_product_code', '!=', False)
        ]
        invoices = self.env['account.move'].search(domain)
        if not invoices:
            raise UserError(_("No se han encontrado facturas publicadas en este rango de fechas."))
        lines = []
        orders_count = len(invoices)
        partners_to_export = self.env['res.partner']
        now = datetime.now()
        date_tx = now.strftime('%Y%m%d')
        nn = "01"
        dist_code = self.company_id.schweppes_distributor_code or "1000026677"
        lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))
        for move in invoices:
            partners_to_export |= move.partner_id
            route = move.partner_id.schweppes_route or "56"
            cust_code = move.partner_id.schweppes_customer_code or move.partner_id.ref or str(move.partner_id.id)
            date_inv = move.invoice_date.strftime('%Y%m%d')
            payment_type = 'CO'
            lines.append(iris_formatter.format_dicp(
                move.name[-10:],
                route,
                cust_code,
                date_inv,
                date_inv,
                payment_type,
                move.ref or ""
            ))
            for line in move.invoice_line_ids:
                if not line.product_id or not line.product_id.schweppes_product_code:
                    continue
                prod_code = line.product_id.schweppes_product_code
                lines.append(iris_formatter.format_didp(
                    move.name[-10:],
                    prod_code,
                    line.quantity,
                    0,
                    line.quantity,
                    0,
                    line.price_unit
                ))
                if line.discount:
                    disc_amount = (line.price_unit * line.quantity) * (line.discount / 100.0)
                    lines.append(iris_formatter.format_didd(
                        move.name[-10:],
                        prod_code,
                        'ES',
                        disc_amount
                    ))
        for partner in partners_to_export:
            lines.append(iris_formatter.format_dimc(
                partner.schweppes_customer_code or partner.ref or str(partner.id),
                partner.schweppes_route or "56",
                partner.name,
                partner.commercial_partner_id.name,
                partner.street or "",
                partner.vat or "",
                partner.schweppes_delivery_type or "D",
                "01",
                "CO",
                "AC",
                "", "", "S", "SSSSSSS",
                "", "", "", "N",
                partner.email or "",
                partner.city or "",
                partner.state_id.name if partner.state_id else "",
                partner.zip or "",
                partner.phone or "",
                "",
                partner.schweppes_customer_code or "",
                ""
            ))
        records_count = len(lines) + 1
        lines.append(iris_formatter.format_ft(records_count, orders_count))
        content = "\r\n".join(lines) + "\r\n"
        file_name = f"{now.strftime('%d%m%Y')}_PREVIEW_SCHW_IRIS_VENTAS.txt"
        # Devuelve una acción de descarga directa
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=schweppes.iris.export&id={self.id}&field=preview_file_data&filename_field=preview_file_name&download=true",
            'target': 'self',
        }

    def _compute_preview_file_data(self):
        for rec in self:
            domain = [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', rec.date_from),
                ('invoice_date', '<=', rec.date_to),
                ('company_id', '=', rec.company_id.id),
                ('invoice_line_ids.product_id.schweppes_product_code', '!=', False)
            ]
            invoices = rec.env['account.move'].search(domain)
            if not invoices:
                rec.preview_file_data = False
                rec.preview_file_name = False
                continue
            lines = []
            orders_count = len(invoices)
            partners_to_export = rec.env['res.partner']
            now = datetime.now()
            date_tx = now.strftime('%Y%m%d')
            nn = "01"
            dist_code = rec.company_id.schweppes_distributor_code or "1000026677"
            lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))
            for move in invoices:
                partners_to_export |= move.partner_id
                route = move.partner_id.schweppes_route or "56"
                cust_code = move.partner_id.schweppes_customer_code or move.partner_id.ref or str(move.partner_id.id)
                date_inv = move.invoice_date.strftime('%Y%m%d')
                payment_type = 'CO'
                lines.append(iris_formatter.format_dicp(
                    move.name[-10:],
                    route,
                    cust_code,
                    date_inv,
                    date_inv,
                    payment_type,
                    move.ref or ""
                ))
                for line in move.invoice_line_ids:
                    if not line.product_id or not line.product_id.schweppes_product_code:
                        continue
                    prod_code = line.product_id.schweppes_product_code
                    lines.append(iris_formatter.format_didp(
                        move.name[-10:],
                        prod_code,
                        line.quantity,
                        0,
                        line.quantity,
                        0,
                        line.price_unit
                    ))
                    if line.discount:
                        disc_amount = (line.price_unit * line.quantity) * (line.discount / 100.0)
                        lines.append(iris_formatter.format_didd(
                            move.name[-10:],
                            prod_code,
                            'ES',
                            disc_amount
                        ))
            for partner in partners_to_export:
                lines.append(iris_formatter.format_dimc(
                    partner.schweppes_customer_code or partner.ref or str(partner.id),
                    partner.schweppes_route or "56",
                    partner.name,
                    partner.commercial_partner_id.name,
                    partner.street or "",
                    partner.vat or "",
                    partner.schweppes_delivery_type or "D",
                    "01",
                    "CO",
                    "AC",
                    "", "", "S", "SSSSSSS",
                    "", "", "", "N",
                    partner.email or "",
                    partner.city or "",
                    partner.state_id.name if partner.state_id else "",
                    partner.zip or "",
                    partner.phone or "",
                    "",
                    partner.schweppes_customer_code or "",
                    ""
                ))
            records_count = len(lines) + 1
            lines.append(iris_formatter.format_ft(records_count, orders_count))
            content = "\r\n".join(lines) + "\r\n"
            rec.preview_file_data = base64.b64encode(content.encode('utf-8'))
            rec.preview_file_name = f"{now.strftime('%d%m%Y')}_PREVIEW_SCHW_IRIS_VENTAS.txt"

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _('Facturas Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'list,form',  # Odoo 18: 'tree' renombrado a 'list'
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'create': False, 'delete': False},
        }

    def action_view_partners(self):
        self.ensure_one()
        return {
            'name': _('Clientes Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,list,form',  # Odoo 18: 'tree' renombrado a 'list'
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {'create': False, 'delete': False},
        }
