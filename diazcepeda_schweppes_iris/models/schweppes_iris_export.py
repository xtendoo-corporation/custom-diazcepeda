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

    # Summary fields for UX
    invoice_count = fields.Integer(string='Nº Facturas', readonly=True, tracking=True)
    partner_count = fields.Integer(string='Nº Clientes', readonly=True, tracking=True)
    line_count = fields.Integer(string='Nº Líneas Venta', readonly=True, tracking=True)
    
    invoice_ids = fields.Many2many('account.move', string='Facturas Incluidas', readonly=True)
    partner_ids = fields.Many2many('res.partner', string='Clientes Incluidos', readonly=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('Nuevo')) == _('Nuevo'):
            vals['name'] = self.env['ir.sequence'].next_by_code('schweppes.iris.export') or _('Nuevo')
        return super(SchweppesIrisExport, self).create(vals)

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
        # Get sequence for the day or simple incremental? The requirement says NN (2 digits)
        # We can use a simple day-based sequence or just 01 for now as a placeholder
        nn = "01" 
        dist_code = self.company_id.schweppes_distributor_code or "1000026677"
        lines.append(iris_formatter.format_ct(date_tx, 'G', nn, dist_code))

        for move in invoices:
            partners_to_export |= move.partner_id
            
            # DICP (Order Header)
            # Route and codes from partner extension
            route = move.partner_id.schweppes_route or "56"
            cust_code = move.partner_id.schweppes_customer_code or move.partner_id.ref or str(move.partner_id.id)
            date_inv = move.invoice_date.strftime('%Y%m%d')
            payment_type = 'CO' # Simplified: mapping needed from account.payment.term?
            # In specification: CO (contado) o CR (crédito)
            # Defaulting to CO if not specified
            
            lines.append(iris_formatter.format_dicp(
                move.name[-10:], # Last 10 chars of invoice name
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
                
                # DIDP (Product Detail)
                prod_code = line.product_id.schweppes_product_code
                lines.append(iris_formatter.format_didp(
                    move.name[-10:],
                    prod_code,
                    line.quantity,
                    0, # Return expected
                    line.quantity,
                    0, # Returned
                    line.price_unit
                ))
                
                # DIDD (Discount Detail) - If any
                if line.discount:
                    disc_amount = (line.price_unit * line.quantity) * (line.discount / 100.0)
                    lines.append(iris_formatter.format_didd(
                        move.name[-10:],
                        prod_code,
                        'ES', # ES for promotional/special
                        disc_amount
                    ))

        # DIMC (Master Clients)
        for partner in partners_to_export:
            lines.append(iris_formatter.format_dimc(
                partner.schweppes_customer_code or partner.ref or str(partner.id),
                partner.schweppes_route or "56",
                partner.name,
                partner.commercial_partner_id.name,
                partner.street or "",
                partner.vat or "",
                partner.schweppes_delivery_type or "D",
                "01", # Establishment type placeholder
                "CO", # Payment type placeholder
                "AC", # Status Active
                "", "", "S", "SSSSSSS", # Defaults
                "", "", "", "N", # Defaults
                partner.email or "",
                partner.city or "",
                partner.state_id.name if partner.state_id else "",
                partner.zip or "",
                partner.phone or "",
                "", # Fax
                partner.schweppes_customer_code or "",
                "" # Sequence
            ))

        # FT (Footer)
        records_count = len(lines) + 1 # +1 for FT itself
        lines.append(iris_formatter.format_ft(records_count, orders_count))

        # Final String
        content = "\r\n".join(lines) + "\r\n"
        
        # File Name: DDMMYYYYSCHW_IRIS_VENTAS.txt
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
        
        self.message_post(body=_("Fichero IRIS generado con %s facturas y %s clientes.") % (len(invoices), len(partners_to_export)))

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=schweppes.iris.export&id={self.id}&field=file_data&filename={file_name}&download=true',
            'target': 'self',
        }

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'name': _('Facturas Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'view_mode': 'tree,form',
            'domain': [('id', 'in', self.invoice_ids.ids)],
            'context': {'create': False, 'delete': False},
        }

    def action_view_partners(self):
        self.ensure_one()
        return {
            'name': _('Clientes Schweppes'),
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'kanban,tree,form',
            'domain': [('id', 'in', self.partner_ids.ids)],
            'context': {'create': False, 'delete': False},
        }
