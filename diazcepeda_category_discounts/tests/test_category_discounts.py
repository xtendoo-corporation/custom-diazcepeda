# -*- coding: utf-8 -*-
# Tests para diazcepeda_category_discounts — Odoo 18 Community
from odoo.tests.common import TransactionCase


class TestCategoryDiscounts(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Categorías
        cls.cat_no_disc = cls.env['product.category'].create({
            'name': 'Categoría Sin Descuento en Línea',
            'show_discount_in_line': False,
        })
        cls.cat_with_disc = cls.env['product.category'].create({
            'name': 'Categoría Con Descuento en Línea',
            'show_discount_in_line': True,
        })
        # Productos
        cls.prod_no_disc = cls.env['product.product'].create({
            'name': 'Producto Sin Descuento',
            'categ_id': cls.cat_no_disc.id,
            'list_price': 100.0,
            'taxes_id': [],
        })
        cls.prod_disc = cls.env['product.product'].create({
            'name': 'Producto Con Descuento',
            'categ_id': cls.cat_with_disc.id,
            'list_price': 100.0,
            'taxes_id': [],
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test'})

    # ── Campo en modelo ────────────────────────────────────────────────────────

    def test_field_show_discount_in_line_default_false(self):
        """show_discount_in_line se crea en False por defecto"""
        cat = self.env['product.category'].create({'name': 'Cat Test Default'})
        self.assertFalse(cat.show_discount_in_line)

    def test_field_show_discount_in_line_toggle(self):
        """El campo booleano se puede cambiar a True"""
        cat = self.env['product.category'].create({
            'name': 'Cat Toggle',
            'show_discount_in_line': True,
        })
        self.assertTrue(cat.show_discount_in_line)

    # ── Creación de líneas de venta ────────────────────────────────────────────

    def test_sale_line_create_absorbs_discount_when_false(self):
        """Al crear línea de venta con descuento y show_discount_in_line=False,
        el descuento se absorbe en price_unit y discount queda a 0"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.prod_no_disc.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'discount': 10.0,
        })
        self.assertAlmostEqual(line.discount, 0.0, places=2,
                               msg="El descuento debe ser 0 cuando show_discount_in_line=False")
        self.assertAlmostEqual(line.price_unit, 90.0, places=2,
                               msg="El precio unitario debe absorber el descuento (100 * 0.9 = 90)")

    def test_sale_line_create_keeps_discount_when_true(self):
        """Al crear línea con descuento y show_discount_in_line=True, el descuento se conserva"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.prod_disc.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
            'discount': 15.0,
        })
        self.assertAlmostEqual(line.discount, 15.0, places=2,
                               msg="El descuento debe conservarse cuando show_discount_in_line=True")
        self.assertAlmostEqual(line.price_unit, 100.0, places=2,
                               msg="El precio unitario no debe modificarse")

    def test_sale_line_write_absorbs_discount_when_false(self):
        """Al escribir un descuento en línea con show_discount_in_line=False, se absorbe"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.prod_no_disc.id,
            'product_uom_qty': 1,
            'price_unit': 100.0,
        })
        line.write({'discount': 20.0, 'price_unit': 100.0})
        self.assertAlmostEqual(line.discount, 0.0, places=2)
        self.assertAlmostEqual(line.price_unit, 80.0, places=2)

    def test_sale_line_no_discount_no_change(self):
        """Si discount=0, no hay modificación del precio"""
        order = self.env['sale.order'].create({'partner_id': self.partner.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.prod_no_disc.id,
            'product_uom_qty': 1,
            'price_unit': 50.0,
            'discount': 0.0,
        })
        self.assertAlmostEqual(line.price_unit, 50.0, places=2)

    # ── Creación de líneas de factura ──────────────────────────────────────────

    def test_invoice_line_create_absorbs_discount_when_false(self):
        """En facturas, el descuento también se absorbe cuando show_discount_in_line=False"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.prod_no_disc.id,
                'quantity': 1,
                'price_unit': 100.0,
                'discount': 10.0,
            })],
        })
        line = move.invoice_line_ids[0]
        self.assertAlmostEqual(line.discount, 0.0, places=2)
        self.assertAlmostEqual(line.price_unit, 90.0, places=2)

    def test_invoice_line_create_keeps_discount_when_true(self):
        """En facturas, el descuento se conserva cuando show_discount_in_line=True"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.prod_disc.id,
                'quantity': 1,
                'price_unit': 100.0,
                'discount': 10.0,
            })],
        })
        line = move.invoice_line_ids[0]
        self.assertAlmostEqual(line.discount, 10.0, places=2)

