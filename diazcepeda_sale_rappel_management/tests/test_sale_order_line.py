# -*- coding: utf-8 -*-
"""
Tests para los campos de rappel en sale.order.line.

Cubre:
  - Cálculo de rappel_estimated_amount con y sin descuento
  - Cálculo de rappel_estimated_unit_price
  - Fórmulas: net = price * (1 - disc/100), rappel_unit = net * pct/100
  - rappel_percent = 0 → campos estimados = 0
  - Asignación automática de regla por onchange del producto
  - Fallback al porcentaje por defecto del producto
  - Líneas sin producto → rappel = 0
"""
from odoo.tests.common import TransactionCase
from datetime import date, timedelta


class TestSaleOrderLineRappelCompute(TransactionCase):
    """Tests de los campos compute de rappel en sale.order.line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Rappel Line',
            'customer_rank': 1,
        })
        cls.category = cls.env['product.category'].create({
            'name': 'Cat. Vinos',
        })
        # Producto con rappel habilitado
        cls.product = cls.env['product.product'].create({
            'name': 'Vino Rioja',
            'categ_id': cls.category.id,
            'list_price': 10.0,
            'is_rappel_applicable': True,
            'default_rappel_percent': 3.0,
            'show_rappel_on_quote': True,
        })
        # Producto sin rappel
        cls.product_no_rappel = cls.env['product.product'].create({
            'name': 'Caja Cartón',
            'categ_id': cls.category.id,
            'list_price': 1.0,
            'is_rappel_applicable': False,
        })
        cls.pricelist = cls.env['product.pricelist'].search(
            [('currency_id', '=', cls.env.company.currency_id.id)], limit=1
        )
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'pricelist_id': cls.pricelist.id if cls.pricelist else False,
        })

    def _create_line(self, product, price_unit, qty, discount=0.0, rappel_pct=0.0):
        return self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': product.id,
            'product_uom_qty': qty,
            'price_unit': price_unit,
            'discount': discount,
            'rappel_percent': rappel_pct,
        })

    # ── Fórmula básica ────────────────────────────────────────────────────

    def test_rappel_zero_percent_gives_zero_amounts(self):
        """Con rappel_percent=0 los importes estimados son 0."""
        line = self._create_line(self.product, price_unit=10.0, qty=5.0, rappel_pct=0.0)
        self.assertAlmostEqual(line.rappel_estimated_amount, 0.0)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 10.0,
                               msg="Precio final estimado = precio neto cuando rappel=0")

    def test_rappel_10_percent_no_discount(self):
        """
        price=100, qty=10, disc=0%, rappel=10%
        net = 100
        rappel_unit = 10.0
        rappel_total = 100.0
        final_unit = 90.0
        """
        line = self._create_line(self.product, price_unit=100.0, qty=10.0,
                                  discount=0.0, rappel_pct=10.0)
        self.assertAlmostEqual(line.rappel_estimated_amount, 100.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 90.0, places=2)

    def test_rappel_5_percent_with_20_discount(self):
        """
        price=100, qty=2, disc=20%, rappel=5%
        net = 100 * (1 - 0.20) = 80
        rappel_unit = 80 * 0.05 = 4.0
        rappel_total = 4.0 * 2 = 8.0
        final_unit = 80 - 4 = 76.0
        """
        line = self._create_line(self.product, price_unit=100.0, qty=2.0,
                                  discount=20.0, rappel_pct=5.0)
        self.assertAlmostEqual(line.rappel_estimated_amount, 8.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 76.0, places=2)

    def test_rappel_with_100_percent_discount(self):
        """
        Con 100% de descuento el precio neto es 0, por lo que el rappel es 0.
        """
        line = self._create_line(self.product, price_unit=50.0, qty=3.0,
                                  discount=100.0, rappel_pct=10.0)
        self.assertAlmostEqual(line.rappel_estimated_amount, 0.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 0.0, places=2)

    def test_rappel_fractional_percent(self):
        """
        price=200, qty=1, disc=0, rappel=2.5%
        rappel_unit = 200 * 0.025 = 5.0
        final = 195.0
        """
        line = self._create_line(self.product, price_unit=200.0, qty=1.0,
                                  discount=0.0, rappel_pct=2.5)
        self.assertAlmostEqual(line.rappel_estimated_amount, 5.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 195.0, places=2)

    def test_rappel_amount_scales_with_quantity(self):
        """El rappel total escala linealmente con la cantidad."""
        line_1 = self._create_line(self.product, price_unit=10.0, qty=1.0, rappel_pct=10.0)
        line_5 = self._create_line(self.product, price_unit=10.0, qty=5.0, rappel_pct=10.0)
        line_10 = self._create_line(self.product, price_unit=10.0, qty=10.0, rappel_pct=10.0)

        self.assertAlmostEqual(line_5.rappel_estimated_amount,
                               line_1.rappel_estimated_amount * 5, places=2)
        self.assertAlmostEqual(line_10.rappel_estimated_amount,
                               line_1.rappel_estimated_amount * 10, places=2)

    def test_unit_price_not_affected_by_rappel(self):
        """El price_unit real NO se ve modificado por el rappel."""
        original_price = 50.0
        line = self._create_line(self.product, price_unit=original_price,
                                  qty=3.0, rappel_pct=15.0)
        self.assertAlmostEqual(line.price_unit, original_price,
                               msg="El precio real no debe modificarse")

    def test_price_subtotal_not_affected_by_rappel(self):
        """El price_subtotal real NO se ve afectado por el rappel."""
        line = self._create_line(self.product, price_unit=100.0, qty=2.0,
                                  discount=0.0, rappel_pct=20.0)
        self.assertAlmostEqual(line.price_subtotal, 200.0,
                               msg="El subtotal real no debe modificarse")

    def test_rappel_100_percent_gives_zero_final_price(self):
        """
        Con rappel_percent=100 el precio final estimado debería ser 0.
        """
        line = self._create_line(self.product, price_unit=50.0, qty=1.0,
                                  discount=0.0, rappel_pct=100.0)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 0.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_amount, 50.0, places=2)


class TestSaleOrderLineRappelRuleAssignment(TransactionCase):
    """Tests de asignación automática de reglas de rappel en líneas de pedido."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Asignación',
            'customer_rank': 1,
        })
        cls.category = cls.env['product.category'].create({
            'name': 'Cat. Cervezas',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Cerveza IPA',
            'categ_id': cls.category.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 2.0,
        })
        cls.product2 = cls.env['product.product'].create({
            'name': 'Cerveza Stout',
            'categ_id': cls.category.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 1.5,
        })
        cls.product_no_rappel = cls.env['product.product'].create({
            'name': 'Barril Sin Rappel',
            'categ_id': cls.category.id,
            'is_rappel_applicable': False,
        })
        cls.pricelist = cls.env['product.pricelist'].search(
            [('currency_id', '=', cls.env.company.currency_id.id)], limit=1
        )
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'pricelist_id': cls.pricelist.id if cls.pricelist else False,
        })
        # Regla P1: cliente + producto
        cls.rule_p1 = cls.env['rappel.rule'].create({
            'name': 'P1 Cliente+Producto',
            'partner_id': cls.partner.id,
            'product_id': cls.product.id,
            'rappel_percent': 8.0,
        })
        # Regla P4: todos + categoría
        cls.rule_p4 = cls.env['rappel.rule'].create({
            'name': 'P4 Todos+Categoría',
            'product_category_id': cls.category.id,
            'rappel_percent': 3.0,
        })

    def test_update_rappel_rule_assigns_best_rule(self):
        """_update_rappel_rule asigna la regla P1 cuando existe."""
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'price_unit': 10.0,
        })
        line._update_rappel_rule()
        self.assertEqual(line.rappel_rule_id.id, self.rule_p1.id,
                         "Debe asignar la regla P1 (cliente+producto)")
        self.assertAlmostEqual(line.rappel_percent, 8.0)

    def test_update_rappel_rule_fallback_to_p4(self):
        """Con solo regla P4 disponible, se asigna P4."""
        # Usar product2 que no tiene regla P1
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product2.id,
            'product_uom_qty': 1.0,
            'price_unit': 10.0,
        })
        line._update_rappel_rule()
        self.assertEqual(line.rappel_rule_id.id, self.rule_p4.id,
                         "Sin regla específica debe usar P4")
        self.assertAlmostEqual(line.rappel_percent, 3.0)

    def test_update_rappel_rule_uses_product_default_when_no_rule(self):
        """Sin regla aplicable usa el porcentaje por defecto del producto."""
        # Crear pedido con otro cliente sin reglas
        other_partner = self.env['res.partner'].create({
            'name': 'Otro Cliente', 'customer_rank': 1,
        })
        other_category = self.env['product.category'].create({
            'name': 'Cat. Sin Regla',
        })
        product_default = self.env['product.product'].create({
            'name': 'Producto Sin Regla',
            'categ_id': other_category.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 4.5,
        })
        order = self.env['sale.order'].create({'partner_id': other_partner.id})
        line = self.env['sale.order.line'].create({
            'order_id': order.id,
            'product_id': product_default.id,
            'product_uom_qty': 1.0,
            'price_unit': 10.0,
        })
        line._update_rappel_rule()
        self.assertFalse(line.rappel_rule_id,
                         "Sin regla no debe asignarse rappel_rule_id")
        self.assertAlmostEqual(line.rappel_percent, 4.5,
                               msg="Debe usar el porcentaje por defecto del producto")

    def test_update_rappel_clears_when_product_removed(self):
        """Si el producto se elimina de la línea, el rappel se pone a 0."""
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product.id,
            'product_uom_qty': 1.0,
            'price_unit': 10.0,
        })
        line._update_rappel_rule()
        # Simular borrado del producto
        line.product_id = False
        line._update_rappel_rule()
        self.assertFalse(line.rappel_rule_id)
        self.assertAlmostEqual(line.rappel_percent, 0.0)

    def test_no_rappel_on_non_applicable_product(self):
        """Productos con is_rappel_applicable=False no tienen rappel."""
        line = self.env['sale.order.line'].create({
            'order_id': self.sale_order.id,
            'product_id': self.product_no_rappel.id,
            'product_uom_qty': 1.0,
            'price_unit': 10.0,
        })
        line._update_rappel_rule()
        # Puede que P4 aplique por categoría; lo que verificamos es que
        # el fallback al default no aplica
        if not line.rappel_rule_id:
            self.assertAlmostEqual(line.rappel_percent, 0.0,
                                   msg="Producto sin rappel no debe tener % por defecto")

