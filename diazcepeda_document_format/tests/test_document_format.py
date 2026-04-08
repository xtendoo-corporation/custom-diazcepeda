# -*- coding: utf-8 -*-
# Tests para diazcepeda_document_format — Odoo 18 Community
from markupsafe import Markup
from odoo.tests.common import TransactionCase


class TestDocumentFormat(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Formato'})
        cls.product_normal = cls.env['product.product'].create({
            'name': 'Producto Normal Formato',
            'list_price': 50.0,
            'taxes_id': [],
        })
        cls.product_gasto = cls.env['product.product'].create({
            'name': 'Gasto de gestión',
            'list_price': 1.0,
            'taxes_id': [],
        })

    # ── sale.order ─────────────────────────────────────────────────────────────

    def test_is_gasto_gestion_true_when_product_present(self):
        """_is_gasto_gestion() devuelve True cuando hay una línea 'Gasto de gestión'"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_gasto.id,
            'product_uom_qty': 1,
            'price_unit': 1.0,
        })
        self.assertTrue(order._is_gasto_gestion())

    def test_is_gasto_gestion_false_when_not_present(self):
        """_is_gasto_gestion() devuelve False cuando no hay 'Gasto de gestión'"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_normal.id,
            'product_uom_qty': 1,
            'price_unit': 50.0,
        })
        self.assertFalse(order._is_gasto_gestion())

    def test_get_footer_data_returns_markup_instance(self):
        """_get_footer_data() devuelve siempre un objeto Markup (compatible con t-out)"""
        self.env['ir.config_parameter'].sudo().set_param('footer_data', 'Pie de página\nLínea 2')
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        result = order._get_footer_data()
        self.assertIsInstance(result, Markup,
                              "_get_footer_data debe devolver Markup, no str")

    def test_get_footer_data_replaces_newlines_with_br(self):
        """_get_footer_data() convierte saltos de línea en <br/> para el template HTML"""
        self.env['ir.config_parameter'].sudo().set_param('footer_data', 'Línea A\nLínea B')
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        result = order._get_footer_data()
        self.assertIn('<br/>', str(result))

    def test_get_order_lines_to_report_filters_gasto(self):
        """_get_order_lines_to_report() excluye las líneas de 'Gasto de gestión'"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_normal.id,
            'product_uom_qty': 2,
            'price_unit': 50.0,
        })
        self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product_gasto.id,
            'product_uom_qty': 1,
            'price_unit': 1.0,
        })
        lines = order._get_order_lines_to_report()
        product_names = lines.mapped('product_id.name')
        self.assertNotIn('Gasto de gestión', product_names,
                         "Las líneas de 'Gasto de gestión' deben filtrarse del informe")
        self.assertIn('Producto Normal Formato', product_names)

    # ── account.move ───────────────────────────────────────────────────────────

    def test_invoice_is_gasto_gestion_true(self):
        """_is_gasto_gestion() en account.move detecta el producto correctamente"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_gasto.id,
                'quantity': 1,
                'price_unit': 1.0,
            })],
        })
        self.assertTrue(move._is_gasto_gestion())

    def test_get_invoice_lines_to_report_excludes_gasto(self):
        """_get_invoice_lines_to_report() filtra las líneas de 'Gasto de gestión'"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [
                (0, 0, {'product_id': self.product_normal.id, 'quantity': 1, 'price_unit': 50.0}),
                (0, 0, {'product_id': self.product_gasto.id, 'quantity': 1, 'price_unit': 1.0}),
            ],
        })
        all_lines = move.invoice_line_ids
        filtered = move._get_invoice_lines_to_report(all_lines)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].product_id.name, 'Producto Normal Formato')

    def test_invoice_get_footer_data_markup(self):
        """_get_footer_data() en account.move devuelve Markup"""
        self.env['ir.config_parameter'].sudo().set_param('footer_data', 'Info empresa')
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
        })
        result = move._get_footer_data()
        self.assertIsInstance(result, Markup)

    # ── product.template campos personalizados ────────────────────────────────

    def test_product_template_custom_fields_created(self):
        """Los campos codigo_normalizado y referencia_auxiliar se crean y leen bien"""
        tmpl = self.env['product.template'].create({
            'name': 'Producto Custom Fields',
            'codigo_normalizado': 'COD-TEST-001',
            'referencia_auxiliar': 'REF-AUX-001',
        })
        self.assertEqual(tmpl.codigo_normalizado, 'COD-TEST-001')
        self.assertEqual(tmpl.referencia_auxiliar, 'REF-AUX-001')

