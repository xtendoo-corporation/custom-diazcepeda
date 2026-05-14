from odoo import api, fields, models


class SchweppesExportLine(models.Model):
    _name = 'schweppes.export.line'
    _description = 'Schweppes Export Line'
    _table = 'schweppes_export_lines'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    export_id = fields.Many2one(
        'schweppes.iris.export',
        string='Exportación',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Pedido',
        required=True,
    )
    sale_order_line_id = fields.Many2one(
        'sale.order.line',
        string='Línea origen',
        domain="[('order_id', '=', sale_order_id)]",
    )
    sale_order_name = fields.Char(string='Número pedido', required=True)
    client_order_ref = fields.Char(string='Ref. cliente')
    date_order = fields.Datetime(
        string='Fecha pedido',
        required=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Cliente',
        required=True,
    )
    product_id = fields.Many2one(
        'product.product',
        string='Producto',
        required=True,
        domain="[('schweppes_product_code', '!=', False)]",
    )
    name = fields.Char(string='Descripción')
    company_id = fields.Many2one(
        'res.company',
        related='export_id.company_id',
        store=True,
        readonly=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
    )
    product_uom_qty = fields.Float(
        string='Cantidad',
        digits='Product Unit of Measure',
        required=True,
        default=1.0,
    )
    price_unit = fields.Float(
        string='Precio unitario',
        digits='Product Price',
        required=True,
        default=0.0,
    )
    discount = fields.Float(
        string='Descuento (%)',
        digits=(16, 2),
        default=0.0,
    )
    discount_amount = fields.Monetary(
        string='Importe descuento',
        compute='_compute_discount_amount',
        store=True,
        currency_field='currency_id',
    )
    schweppes_product_code = fields.Char(string='Código Schweppes', required=True)

    @api.depends('product_uom_qty', 'price_unit', 'discount')
    def _compute_discount_amount(self):
        for rec in self:
            rec.discount_amount = (rec.price_unit * rec.product_uom_qty) * (rec.discount / 100.0)

    @api.onchange('sale_order_id')
    def _onchange_sale_order_id(self):
        for rec in self:
            if rec.sale_order_id:
                rec.partner_id = rec.sale_order_id.partner_id
                rec.sale_order_name = rec.sale_order_id.name or ''
                rec.client_order_ref = rec.sale_order_id.client_order_ref or ''
                rec.date_order = rec.sale_order_id.date_order
                rec.currency_id = rec.sale_order_id.currency_id

    @api.onchange('sale_order_line_id')
    def _onchange_sale_order_line_id(self):
        for rec in self:
            line = rec.sale_order_line_id
            if not line:
                continue
            rec.sale_order_id = line.order_id
            rec.partner_id = line.order_id.partner_id
            rec.sale_order_name = line.order_id.name or ''
            rec.client_order_ref = line.order_id.client_order_ref or ''
            rec.date_order = line.order_id.date_order
            rec.currency_id = line.order_id.currency_id
            rec.product_id = line.product_id
            rec.name = line.name
            rec.product_uom_qty = line.product_uom_qty
            rec.price_unit = line.price_unit
            rec.discount = line.discount
            rec.schweppes_product_code = line.product_id.schweppes_product_code or ''

    @api.onchange('product_id')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id and not rec.name:
                rec.name = rec.product_id.display_name
            rec.schweppes_product_code = rec.product_id.schweppes_product_code or False

