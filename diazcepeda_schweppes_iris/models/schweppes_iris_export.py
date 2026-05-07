from odoo import models, fields, api, _
from odoo.exceptions import UserError
import base64
from datetime import datetime, time
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
    sale_order_count = fields.Integer(string='Nº Pedidos', readonly=True, tracking=True)
    partner_count = fields.Integer(string='Nº Clientes', readonly=True, tracking=True)
    line_count = fields.Integer(string='Nº Líneas Venta', readonly=True, tracking=True)

    sale_order_ids = fields.Many2many('sale.order', string='Pedidos Incluidos', readonly=True)
    sale_order_line_ids = fields.Many2many('sale.order.line', string='Líneas Incluidas', readonly=True)
    partner_ids = fields.Many2many('res.partner', string='Clientes Incluidos', readonly=True)

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 18: create recibe una lista de dicts
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('schweppes.iris.export') or _('Nuevo')
        return super().create(vals_list)

    def _get_sale_order_domain(self):
        self.ensure_one()
        date_from_dt = datetime.combine(self.date_from, time.min)
        date_to_dt = datetime.combine(self.date_to, time.max).replace(microsecond=0)
        return [
            ('state', 'not in', ['draft', 'cancel']),
            ('date_order', '>=', fields.Datetime.to_string(date_from_dt)),
            ('date_order', '<=', fields.Datetime.to_string(date_to_dt)),
            ('company_id', '=', self.company_id.id),
            ('order_line.product_id.schweppes_product_code', '!=', False),
        ]

    def _build_iris_content_from_sale_orders(self):
        self.ensure_one()
        sale_orders = self.env['sale.order'].search(self._get_sale_order_domain())
        if not sale_orders:
            raise UserError(_("No se han encontrado pedidos confirmados en este rango de fechas."))

        lines = []
        partners_to_export = self.env['res.partner']
        line_count = 0
        sale_order_lines_to_export = self.env['sale.order.line']

        now = datetime.now()
        date_tx = now.strftime('%Y%m%d')
        nn = "01"
        dist_code = self.company_id.schweppes_distributor_code or "1000026677"
        lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))

        for order in sale_orders:
            partners_to_export |= order.partner_id
            route = order.partner_id.schweppes_route or "56"
            cust_code = order.partner_id.schweppes_customer_code or order.partner_id.ref or str(order.partner_id.id)
            date_order = order.date_order.strftime('%Y%m%d') if order.date_order else date_tx
            payment_type = 'CO'
            lines.append(iris_formatter.format_dicp(
                (order.name or '')[-10:],
                route,
                cust_code,
                date_order,
                date_order,
                payment_type,
                order.client_order_ref or ""
            ))

            for line in order.order_line:
                if line.display_type or not line.product_id or not line.product_id.schweppes_product_code:
                    continue
                sale_order_lines_to_export |= line
                prod_code = line.product_id.schweppes_product_code
                qty = line.product_uom_qty
                line_count += 1
                lines.append(iris_formatter.format_didp(
                    (order.name or '')[-10:],
                    prod_code,
                    qty,
                    0,
                    qty,
                    0,
                    line.price_unit
                ))
                if line.discount:
                    disc_amount = (line.price_unit * qty) * (line.discount / 100.0)
                    lines.append(iris_formatter.format_didd(
                        (order.name or '')[-10:],
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
        lines.append(iris_formatter.format_ft(records_count, len(sale_orders)))
        content = "\r\n".join(lines) + "\r\n"
        return content, sale_orders, sale_order_lines_to_export, partners_to_export, line_count, now

    def action_generate_file(self):
        self.ensure_one()
        content, sale_orders, sale_order_lines_to_export, partners_to_export, line_count, now = self._build_iris_content_from_sale_orders()
        file_name = f"{now.strftime('%d%m%Y')}SCHW_IRIS_VENTAS.txt"

        self.write({
            'file_data': base64.b64encode(content.encode('utf-8')),
            'file_name': file_name,
            'state': 'done',
            'sale_order_count': len(sale_orders),
            'partner_count': len(partners_to_export),
            'line_count': line_count,
            'sale_order_ids': [(6, 0, sale_orders.ids)],
            'sale_order_line_ids': [(6, 0, sale_order_lines_to_export.ids)],
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
            body=_("El usuario %s, ha generado/regenerado el fichero IRIS (%s pedidos, %s clientes).") % (usuario, len(sale_orders), len(partners_to_export)),
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
        # Reutiliza la lógica de generación, pero solo devuelve la descarga.
        self._build_iris_content_from_sale_orders()
        # Devuelve una acción de descarga directa
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=schweppes.iris.export&id={self.id}&field=preview_file_data&filename_field=preview_file_name&download=true",
            'target': 'self',
        }

    def _compute_preview_file_data(self):
        for rec in self:
            if not rec.date_from or not rec.date_to or not rec.company_id:
                rec.preview_file_data = False
                rec.preview_file_name = False
                continue
            sale_orders = rec.env['sale.order'].search(rec._get_sale_order_domain())
            if not sale_orders:
                rec.preview_file_data = False
                rec.preview_file_name = False
                continue
            content, _, _, _, _, now = rec._build_iris_content_from_sale_orders()
            rec.preview_file_data = base64.b64encode(content.encode('utf-8'))
            rec.preview_file_name = f"{now.strftime('%d%m%Y')}_PREVIEW_SCHW_IRIS_VENTAS.txt"

    def action_view_sale_orders(self):
        self.ensure_one()
        return {
            'name': _('Pedidos Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',  # Odoo 18: 'tree' renombrado a 'list'
            'domain': [('id', 'in', self.sale_order_ids.ids)],
            'context': {'create': False, 'delete': False},
        }

    def action_view_sale_order_lines(self):
        self.ensure_one()
        return {
            'name': _('Líneas de pedido Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.sale_order_line_ids.ids)],
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
