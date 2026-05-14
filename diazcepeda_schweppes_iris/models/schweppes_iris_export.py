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
        ('generated', 'Generado'),
        ('sent', 'Enviado')
    ], string='Estado', default='draft', tracking=True, copy=False)

    file_data = fields.Binary(string='Archivo TXT', readonly=True)
    file_name = fields.Char(string='Nombre del Archivo', readonly=True)

    # Campos computados para la previsualización del archivo
    preview_file_data = fields.Binary(string='Archivo TXT Previsualización', readonly=True, compute='_compute_preview_file_data')
    preview_file_name = fields.Char(string='Nombre Archivo Previsualización', readonly=True, compute='_compute_preview_file_data')

    export_line_ids = fields.One2many(
        'schweppes.export.line',
        'export_id',
        string='Líneas a exportar',
        copy=False,
    )

    # Summary fields for UX
    sale_order_count = fields.Integer(string='Nº Pedidos', readonly=True, compute='_compute_summary_counts')
    partner_count = fields.Integer(string='Nº Clientes', readonly=True, compute='_compute_summary_counts')
    line_count = fields.Integer(string='Nº Líneas Venta', readonly=True, compute='_compute_summary_counts')

    sale_order_ids = fields.Many2many('sale.order', string='Pedidos Incluidos', readonly=True, compute='_compute_related_records')
    partner_ids = fields.Many2many('res.partner', string='Clientes Incluidos', readonly=True, compute='_compute_related_records')

    def _is_locked_for_edition(self):
        """Bloquea la edición cuando hay fichero generado o el envío ya es definitivo."""
        self.ensure_one()
        return self.state == 'sent' or bool(self.file_data)

    def _ensure_can_edit_export(self):
        for rec in self:
            if rec.state == 'sent':
                raise UserError(_("No puedes modificar una exportación ya enviada."))
            if rec.file_data:
                raise UserError(_("La exportación está bloqueada mientras exista un fichero generado. Pulsa Editar para eliminarlo y volver a borrador."))

    @api.model_create_multi
    def create(self, vals_list):
        # Odoo 18: create recibe una lista de dicts
        for vals in vals_list:
            if vals.get('name', _('Nuevo')) == _('Nuevo'):
                vals['name'] = self.env['ir.sequence'].next_by_code('schweppes.iris.export') or _('Nuevo')
        return super().create(vals_list)

    def init(self):
        self._cr.execute("""
            UPDATE schweppes_iris_export
               SET state = 'generated'
             WHERE state = 'done'
        """)
        self._cr.execute("""
            UPDATE schweppes_iris_export
               SET state = 'draft'
             WHERE state IS NULL
                OR state NOT IN ('draft', 'generated', 'sent')
        """)

    def write(self, vals):
        protected_fields = {'date_from', 'date_to', 'company_id', 'export_line_ids'}
        if not self.env.context.get('skip_export_lock') and protected_fields & set(vals):
            self._ensure_can_edit_export()
        should_invalidate = (
            not self.env.context.get('skip_export_invalidation')
            and bool({'date_from', 'date_to', 'company_id'} & set(vals))
        )
        res = super().write(vals)
        if should_invalidate:
            self._invalidate_generated_file()
        return res

    def _delete_generated_attachments(self):
        for rec in self:
            attachments = self.env['ir.attachment'].search([
                ('res_model', '=', rec._name),
                ('res_id', '=', rec.id),
                ('mimetype', '=', 'text/plain'),
            ])
            if attachments:
                attachments.unlink()

    def _invalidate_generated_file(self):
        for rec in self:
            rec._delete_generated_attachments()
            vals = {}
            if rec.file_data:
                vals['file_data'] = False
            if rec.file_name:
                vals['file_name'] = False
            if rec.state != 'draft':
                vals['state'] = 'draft'
            if vals:
                super(SchweppesIrisExport, rec.with_context(skip_export_invalidation=True)).write(vals)

    def action_delete_file(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_("No puedes eliminar el fichero de una exportación ya enviada."))
        if not self.file_data:
            raise UserError(_("No hay ningún fichero generado para eliminar."))

        self._invalidate_generated_file()
        self.message_post(
            body=_("Se ha eliminado el fichero generado y la exportación ha vuelto a borrador.")
        )
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_edit_file(self):
        # Compatibilidad hacia atrás: editar equivale a eliminar el fichero y volver a borrador.
        return self.action_delete_file()

    @api.depends('export_line_ids', 'export_line_ids.sale_order_id', 'export_line_ids.partner_id')
    def _compute_summary_counts(self):
        for rec in self:
            rec.line_count = len(rec.export_line_ids)
            rec.sale_order_count = len(rec.export_line_ids.mapped('sale_order_id'))
            rec.partner_count = len(rec.export_line_ids.mapped('partner_id'))

    @api.depends('export_line_ids.sale_order_id', 'export_line_ids.partner_id')
    def _compute_related_records(self):
        for rec in self:
            rec.sale_order_ids = rec.export_line_ids.mapped('sale_order_id')
            rec.partner_ids = rec.export_line_ids.mapped('partner_id')

    def _get_sale_order_line_domain(self):
        self.ensure_one()
        date_from_dt = datetime.combine(self.date_from, time.min)
        date_to_dt = datetime.combine(self.date_to, time.max).replace(microsecond=0)
        return [
            ('order_id.state', 'not in', ['draft', 'cancel']),
            ('order_id.date_order', '>=', fields.Datetime.to_string(date_from_dt)),
            ('order_id.date_order', '<=', fields.Datetime.to_string(date_to_dt)),
            ('order_id.company_id', '=', self.company_id.id),
            ('display_type', '=', False),
            ('product_id.schweppes_product_code', '!=', False),
        ]

    def _prepare_export_line_vals(self, sale_line, sequence):
        return {
            'sequence': sequence,
            'sale_order_id': sale_line.order_id.id,
            'sale_order_line_id': sale_line.id,
            'sale_order_name': sale_line.order_id.name or '',
            'client_order_ref': sale_line.order_id.client_order_ref or '',
            'date_order': sale_line.order_id.date_order,
            'partner_id': sale_line.order_id.partner_id.id,
            'product_id': sale_line.product_id.id,
            'name': sale_line.name,
            'currency_id': sale_line.order_id.currency_id.id,
            'product_uom_qty': sale_line.product_uom_qty,
            'price_unit': sale_line.price_unit,
            'discount': sale_line.discount,
            'schweppes_product_code': sale_line.product_id.schweppes_product_code or '',
        }

    def _reload_export_lines(self):
        self.ensure_one()
        self._ensure_can_edit_export()
        if not self.date_from or not self.date_to or not self.company_id:
            raise UserError(_("Debes indicar fecha desde, fecha hasta y compañía antes de cargar líneas."))

        sale_lines = self.env['sale.order.line'].search(
            self._get_sale_order_line_domain(),
            order='order_id, sequence, id',
        )
        if not sale_lines:
            raise UserError(_("No se han encontrado líneas de pedidos confirmados en este rango de fechas."))

        commands = [(5, 0, 0)]
        sequence = 10
        for sale_line in sale_lines:
            commands.append((0, 0, self._prepare_export_line_vals(sale_line, sequence)))
            sequence += 10

        self.with_context(skip_export_invalidation=True).write({'export_line_ids': commands})
        self._invalidate_generated_file()
        return self.export_line_ids

    def action_load_export_lines(self):
        self.ensure_one()
        self._reload_export_lines()
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def _get_lines_for_export(self):
        self.ensure_one()
        if not self.export_line_ids:
            raise UserError(_("Primero debes cargar las líneas a exportar."))

        export_lines = self.export_line_ids.sorted(
            lambda line: (
                line.date_order or datetime.min,
                line.sale_order_name or '',
                line.sequence,
                line.id,
            )
        )

        invalid_lines = export_lines.filtered(
            lambda line: (
                not line.sale_order_id
                or not line.partner_id
                or not line.product_id
                or not line.schweppes_product_code
            )
        )
        if invalid_lines:
            raise UserError(_("Todas las líneas a exportar deben tener pedido, cliente, producto y código Schweppes."))

        return export_lines

    def _build_iris_content_from_export_lines(self):
        self.ensure_one()
        export_lines = self._get_lines_for_export()

        lines = []
        partners_to_export = self.env['res.partner']

        now = datetime.now()
        date_tx = now.strftime('%Y%m%d')
        nn = "01"
        dist_code = self.company_id.schweppes_distributor_code or "1000026677"
        lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))

        grouped_lines = {}
        for export_line in export_lines:
            key = (
                export_line.sale_order_name or '',
                export_line.client_order_ref or '',
                export_line.date_order or datetime.min,
                export_line.partner_id.id,
            )
            grouped_lines.setdefault(key, self.env['schweppes.export.line'])
            grouped_lines[key] |= export_line

        header_count = 0

        for key in sorted(grouped_lines.keys(), key=lambda item: (item[2] or datetime.min, item[0], item[3])):
            order_lines = grouped_lines[key].sorted(lambda line: (line.sequence, line.id))
            first_line = order_lines[0]
            partner = first_line.partner_id
            partners_to_export |= partner
            header_count += 1
            route = partner.schweppes_route or "56"
            cust_code = partner.schweppes_customer_code or partner.ref or str(partner.id)
            date_order = first_line.date_order.strftime('%Y%m%d') if first_line.date_order else date_tx
            payment_type = 'CO'
            lines.append(iris_formatter.format_dicp(
                (first_line.sale_order_name or '')[-10:],
                route,
                cust_code,
                date_order,
                date_order,
                payment_type,
                first_line.client_order_ref or ""
            ))

            for export_line in order_lines:
                prod_code = export_line.schweppes_product_code
                qty = export_line.product_uom_qty
                lines.append(iris_formatter.format_didp(
                    (first_line.sale_order_name or '')[-10:],
                    prod_code,
                    qty,
                    0,
                    qty,
                    0,
                    export_line.price_unit
                ))
                if export_line.discount:
                    disc_amount = (export_line.price_unit * qty) * (export_line.discount / 100.0)
                    lines.append(iris_formatter.format_didd(
                        (first_line.sale_order_name or '')[-10:],
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
        lines.append(iris_formatter.format_ft(records_count, header_count))
        content = "\r\n".join(lines) + "\r\n"
        return content, header_count, partners_to_export, now

    def action_generate_file(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_("No puedes regenerar una exportación ya enviada."))
        if self.file_data:
            raise UserError(_("La exportación ya tiene un fichero generado. Pulsa Editar para eliminarlo antes de regenerar."))
        content, header_count, partners_to_export, now = self._build_iris_content_from_export_lines()
        file_name = f"{now.strftime('%d%m%Y')}SCHW_IRIS_VENTAS.txt"

        self._delete_generated_attachments()
        self.write({
            'file_data': base64.b64encode(content.encode('utf-8')),
            'file_name': file_name,
            'state': 'generated',
        })

        usuario = self.env.user.name
        self.message_post(
            body=_(
                "El usuario %s ha generado/regenerado el fichero IRIS (%s cabeceras, %s clientes, %s líneas)."
            ) % (usuario, header_count, len(partners_to_export), len(self.export_line_ids)),
        )

        # Recargar la vista formulario para reflejar cambios
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_send_file(self):
        self.ensure_one()
        if self.state == 'sent':
            raise UserError(_("La exportación ya fue enviada y no admite más cambios."))
        if self.state != 'generated':
            raise UserError(_("Primero debes generar el fichero para poder enviarlo."))
        if not self.file_data:
            raise UserError(_("Primero debes generar el fichero antes de enviarlo."))

        self._delete_generated_attachments()
        attachment = self.env['ir.attachment'].create({
            'name': self.file_name or f"{datetime.now().strftime('%d%m%Y')}SCHW_IRIS_VENTAS.txt",
            'datas': self.file_data,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
            'mimetype': 'text/plain',
            'public': True,
        })

        self.with_context(skip_export_invalidation=True).write({'state': 'sent'})

        usuario = self.env.user.name
        self.message_post(
            body=_(
                "El usuario %s ha enviado el fichero IRIS (%s pedidos, %s clientes, %s líneas)."
            ) % (usuario, self.sale_order_count, self.partner_count, self.line_count),
            attachment_ids=[attachment.id],
        )

        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_preview_file(self):
        self.ensure_one()
        self._build_iris_content_from_export_lines()
        return {
            'type': 'ir.actions.act_url',
            'url': f"/web/content/?model=schweppes.iris.export&id={self.id}&field=preview_file_data&filename_field=preview_file_name&download=true",
            'target': 'self',
        }

    @api.depends(
        'date_from',
        'date_to',
        'company_id',
        'export_line_ids',
        'export_line_ids.partner_id',
        'export_line_ids.sale_order_id',
        'export_line_ids.sale_order_name',
        'export_line_ids.client_order_ref',
        'export_line_ids.date_order',
        'export_line_ids.product_id',
        'export_line_ids.product_uom_qty',
        'export_line_ids.price_unit',
        'export_line_ids.discount',
        'export_line_ids.schweppes_product_code',
    )
    def _compute_preview_file_data(self):
        for rec in self:
            if not rec.date_from or not rec.date_to or not rec.company_id or not rec.export_line_ids:
                rec.preview_file_data = False
                rec.preview_file_name = False
                continue
            try:
                content, _, _, now = rec._build_iris_content_from_export_lines()
            except UserError:
                rec.preview_file_data = False
                rec.preview_file_name = False
                continue
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
        list_view = self.env.ref('diazcepeda_schweppes_iris.view_schweppes_export_line_tree', raise_if_not_found=False)
        form_view = self.env.ref('diazcepeda_schweppes_iris.view_schweppes_export_line_form', raise_if_not_found=False)
        action = {
            'name': _('Líneas de exportación Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'schweppes.export.line',
            'view_mode': 'list,form',
            'domain': [('export_id', '=', self.id)],
            'context': {'default_export_id': self.id},
        }
        if list_view or form_view:
            action['views'] = []
            if list_view:
                action['views'].append((list_view.id, 'list'))
            if form_view:
                action['views'].append((form_view.id, 'form'))
        return action

    def action_view_partners(self):
        self.ensure_one()
        return {
            'name': _('Clientes Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,list,form',  # Odoo 18: 'tree' renombrado a 'list'
            'domain': [('id', 'in', self.export_line_ids.mapped('partner_id').ids)],
            'context': {'create': False, 'delete': False},
        }
