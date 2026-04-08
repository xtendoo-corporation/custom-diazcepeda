# -*- coding: utf-8 -*-
# Tests para diazcepeda_show_delivery_address — Odoo 18 Community
# post_install + -at_install garantiza que sale_stock ya esté cargado
# (sale_stock añade el campo picking_policy a sale.order)
from odoo.tests.common import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestShowDeliveryAddress(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_main = cls.env['res.partner'].create({
            'name': 'Cliente Principal Entrega',
        })
        cls.partner_delivery = cls.env['res.partner'].create({
            'name': 'Dirección de Entrega Test',
            'parent_id': cls.partner_main.id,
            'type': 'delivery',
            'street': 'Calle Almacén 10',
            'city': 'Valencia',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Entrega Test',
            'list_price': 25.0,
            'taxes_id': [],
        })

    # ── Campo price_bruto en sale.order.line ──────────────────────────────────

    def test_price_bruto_equals_price_unit(self):
        """price_bruto se computa igual al price_unit de la línea"""
        order = self.env['sale.order'].create({'partner_id': self.partner_main.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'product_uom_qty': 5,
            'price_unit': 30.0,
        })
        self.assertAlmostEqual(
            line.price_bruto, 30.0, places=2,
            msg="price_bruto debe ser igual a price_unit (precio sin descuento)"
        )

    def test_price_bruto_updates_when_price_unit_changes(self):
        """price_bruto se recalcula cuando cambia price_unit"""
        order = self.env['sale.order'].create({'partner_id': self.partner_main.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 50.0,
        })
        self.assertAlmostEqual(line.price_bruto, 50.0, places=2)
        line.write({'price_unit': 75.0})
        self.assertAlmostEqual(line.price_bruto, 75.0, places=2,
                               msg="price_bruto debe actualizarse al cambiar price_unit")

    def test_price_bruto_with_zero_price(self):
        """price_bruto es 0 cuando price_unit es 0 (líneas de regalo)"""
        order = self.env['sale.order'].create({'partner_id': self.partner_main.id, 'picking_policy': 'direct'})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1,
            'price_unit': 0.0,
        })
        self.assertAlmostEqual(line.price_bruto, 0.0, places=2)

    # ── partner_shipping_id en sale.order ────────────────────────────────────

    def test_partner_shipping_id_field_exists_on_sale_order(self):
        """sale.order tiene el campo partner_shipping_id (estándar Odoo 18)"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner_main.id,
            'picking_policy': 'direct',
        })
        # El campo se asigna automáticamente por el compute
        self.assertTrue(
            hasattr(order, 'partner_shipping_id'),
            "sale.order debe tener el campo partner_shipping_id"
        )

    def test_partner_shipping_id_can_be_set_explicitly(self):
        """Se puede asignar una dirección de entrega diferente al pedido"""
        order = self.env['sale.order'].create({
            'partner_id': self.partner_main.id,
            'picking_policy': 'direct',
            'partner_shipping_id': self.partner_delivery.id,
        })
        self.assertEqual(
            order.partner_shipping_id.id, self.partner_delivery.id,
            "partner_shipping_id debe poderse asignar explícitamente"
        )

    # ── partner_shipping_id en account.move ──────────────────────────────────

    def test_partner_shipping_id_field_exists_on_account_move(self):
        """account.move tiene el campo partner_shipping_id (confirmado Odoo 18)"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_main.id,
        })
        self.assertTrue(
            hasattr(move, 'partner_shipping_id'),
            "account.move debe tener partner_shipping_id en Odoo 18"
        )

    def test_account_move_partner_shipping_can_be_set(self):
        """Se puede asignar partner_shipping_id en una factura"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner_main.id,
            'partner_shipping_id': self.partner_delivery.id,
        })
        self.assertEqual(
            move.partner_shipping_id.id, self.partner_delivery.id,
            "account.move.partner_shipping_id debe poderse asignar"
        )

    # ── Vistas heredadas ─────────────────────────────────────────────────────

    def test_sale_order_list_view_inherits_correctly(self):
        """La vista lista de pedidos heredada existe sin errores de XPath"""
        view = self.env.ref(
            'diazcepeda_show_delivery_address.view_order_tree_inherit_delivery_address',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "La vista lista heredada de pedidos debe existir")

    def test_sale_order_quotation_list_view_inherits_correctly(self):
        """La vista lista de presupuestos heredada existe sin errores de XPath"""
        view = self.env.ref(
            'diazcepeda_show_delivery_address.view_order_quotation_tree_inherit_delivery_address',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "La vista lista heredada de presupuestos debe existir")

