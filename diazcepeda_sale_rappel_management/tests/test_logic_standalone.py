#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests de lógica pura — NO requieren Odoo ni base de datos.

Se ejecutan directamente con:
    python3 -m pytest tests/test_logic_standalone.py -v
  o:
    python3 tests/test_logic_standalone.py

Cubren las fórmulas matemáticas y el algoritmo de prioridad
de forma completamente aislada del framework Odoo.
"""
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock


# ═══════════════════════════════════════════════════════════════════════════
#  Copia de las fórmulas de cómputo (extraídas de sale_order_line.py)
#  para test sin dependencias Odoo
# ═══════════════════════════════════════════════════════════════════════════

def compute_rappel(price_unit: float, discount: float,
                   qty: float, rappel_percent: float) -> dict:
    """
    Replica la lógica de _compute_rappel de sale.order.line.

    Returns:
        dict con 'estimated_amount' y 'estimated_unit_price'
    """
    net_price = price_unit * (1.0 - (discount or 0.0) / 100.0)
    rappel_unit = net_price * (rappel_percent / 100.0)
    return {
        'estimated_unit_price': net_price - rappel_unit,
        'estimated_amount': rappel_unit * qty,
    }


def compute_rappel_amount(base_amount: float, rappel_percent: float) -> float:
    """
    Replica la lógica de _compute_rappel_amount de rappel.settlement.line.
    """
    return base_amount * (rappel_percent / 100.0)


# ═══════════════════════════════════════════════════════════════════════════
#  Clase mock para simular reglas de rappel
# ═══════════════════════════════════════════════════════════════════════════

class MockRule:
    """Regla de rappel simulada para tests de prioridad."""

    def __init__(self, partner_id=None, product_id=None,
                 category_id=None, rappel_percent=5.0, active=True,
                 date_start=None, date_end=None):
        self.partner_id = partner_id
        self.product_id = product_id
        self.product_category_id = category_id
        self.rappel_percent = rappel_percent
        self.active = active
        self.date_start = date_start
        self.date_end = date_end

    def get_priority(self) -> int:
        """Replica RappelRule._get_priority()."""
        if self.partner_id and self.product_id:
            return 1
        if self.partner_id and self.product_category_id:
            return 2
        if not self.partner_id and self.product_id:
            return 3
        return 4

    def is_valid_for_date(self, check_date) -> bool:
        """Verifica si la regla es válida para una fecha dada."""
        if self.date_start and check_date < self.date_start:
            return False
        if self.date_end and check_date > self.date_end:
            return False
        return True


def find_applicable_rule_pure(rules: list, partner_id, product_id,
                               category_id, check_date=None) -> MockRule:
    """
    Replica RappelRule.find_applicable_rule() en Python puro.
    Permite probar el algoritmo de prioridad sin Odoo.
    """
    if not product_id:
        return None

    # Filtrar reglas activas y válidas por fecha
    active_rules = [
        r for r in rules
        if r.active and (check_date is None or r.is_valid_for_date(check_date))
    ]

    # P1: cliente + producto
    if partner_id:
        for r in active_rules:
            if r.partner_id == partner_id and r.product_id == product_id:
                return r

    # P2: cliente + categoría
    if partner_id and category_id:
        for r in active_rules:
            if (r.partner_id == partner_id
                    and not r.product_id
                    and r.product_category_id == category_id):
                return r

    # P3: todos los clientes + producto
    for r in active_rules:
        if not r.partner_id and r.product_id == product_id:
            return r

    # P4: todos los clientes + categoría
    if category_id:
        for r in active_rules:
            if (not r.partner_id
                    and not r.product_id
                    and r.product_category_id == category_id):
                return r

    return None


# ═══════════════════════════════════════════════════════════════════════════
#  Tests de fórmulas de cómputo
# ═══════════════════════════════════════════════════════════════════════════

class TestRappelComputeFormulas(unittest.TestCase):
    """Tests unitarios de las fórmulas matemáticas de rappel."""

    def test_basic_10_percent_no_discount(self):
        """price=100, qty=1, disc=0, rappel=10% → amount=10, final=90."""
        r = compute_rappel(100.0, 0.0, 1.0, 10.0)
        self.assertAlmostEqual(r['estimated_amount'], 10.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 90.0, places=2)

    def test_zero_rappel_gives_net_price(self):
        """rappel=0% → amount=0, final=precio_neto."""
        r = compute_rappel(50.0, 0.0, 3.0, 0.0)
        self.assertAlmostEqual(r['estimated_amount'], 0.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 50.0, places=2)

    def test_discount_affects_base(self):
        """
        price=100, disc=20% → net=80
        rappel=5% → rappel_unit=4, total=4*2=8, final=76
        """
        r = compute_rappel(100.0, 20.0, 2.0, 5.0)
        self.assertAlmostEqual(r['estimated_amount'], 8.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 76.0, places=2)

    def test_100_discount_gives_zero(self):
        """Con 100% descuento el precio neto es 0."""
        r = compute_rappel(100.0, 100.0, 5.0, 10.0)
        self.assertAlmostEqual(r['estimated_amount'], 0.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 0.0, places=2)

    def test_100_rappel_gives_zero_final(self):
        """Con 100% rappel el precio final es 0."""
        r = compute_rappel(100.0, 0.0, 1.0, 100.0)
        self.assertAlmostEqual(r['estimated_unit_price'], 0.0, places=2)
        self.assertAlmostEqual(r['estimated_amount'], 100.0, places=2)

    def test_quantity_multiplier(self):
        """El importe total escala con la cantidad."""
        r1 = compute_rappel(10.0, 0.0, 1.0, 10.0)
        r10 = compute_rappel(10.0, 0.0, 10.0, 10.0)
        self.assertAlmostEqual(r10['estimated_amount'],
                               r1['estimated_amount'] * 10, places=2)

    def test_unit_price_not_affected_by_quantity(self):
        """El precio unitario estimado NO depende de la cantidad."""
        r1 = compute_rappel(20.0, 0.0, 1.0, 5.0)
        r100 = compute_rappel(20.0, 0.0, 100.0, 5.0)
        self.assertAlmostEqual(r1['estimated_unit_price'],
                               r100['estimated_unit_price'], places=2)

    def test_fractional_percent(self):
        """2.5% sobre 200 = 5.0 de rappel, final = 195."""
        r = compute_rappel(200.0, 0.0, 1.0, 2.5)
        self.assertAlmostEqual(r['estimated_amount'], 5.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 195.0, places=2)

    def test_combined_discount_and_rappel(self):
        """
        price=1000, disc=10%, qty=5, rappel=8%
        net = 1000 * 0.9 = 900
        rappel_unit = 900 * 0.08 = 72
        total = 72 * 5 = 360
        final = 900 - 72 = 828
        """
        r = compute_rappel(1000.0, 10.0, 5.0, 8.0)
        self.assertAlmostEqual(r['estimated_amount'], 360.0, places=2)
        self.assertAlmostEqual(r['estimated_unit_price'], 828.0, places=2)

    def test_settlement_line_rappel_amount(self):
        """base=1000, 5% → 50."""
        self.assertAlmostEqual(compute_rappel_amount(1000.0, 5.0), 50.0, places=2)

    def test_settlement_line_zero(self):
        """0% → 0."""
        self.assertAlmostEqual(compute_rappel_amount(500.0, 0.0), 0.0, places=2)

    def test_settlement_line_full(self):
        """100% → igual a base."""
        self.assertAlmostEqual(compute_rappel_amount(300.0, 100.0), 300.0, places=2)


# ═══════════════════════════════════════════════════════════════════════════
#  Tests del algoritmo de prioridad
# ═══════════════════════════════════════════════════════════════════════════

class TestPriorityAlgorithm(unittest.TestCase):
    """Tests del algoritmo de búsqueda de reglas por prioridad."""

    P = 'partner_1'      # ID partner
    PROD = 'product_1'   # ID producto
    CAT = 'category_1'   # ID categoría

    def test_p1_wins_over_all(self):
        """P1 (cliente+producto) gana a P2, P3 y P4."""
        rules = [
            MockRule(category_id=self.CAT, rappel_percent=1.0),             # P4
            MockRule(product_id=self.PROD, rappel_percent=2.0),              # P3
            MockRule(partner_id=self.P, category_id=self.CAT, rappel_percent=3.0),  # P2
            MockRule(partner_id=self.P, product_id=self.PROD, rappel_percent=10.0), # P1
        ]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.rappel_percent, 10.0)
        self.assertEqual(result.get_priority(), 1)

    def test_p2_wins_over_p3_and_p4(self):
        """P2 gana a P3 y P4 cuando no hay P1."""
        rules = [
            MockRule(category_id=self.CAT, rappel_percent=1.0),
            MockRule(product_id=self.PROD, rappel_percent=2.0),
            MockRule(partner_id=self.P, category_id=self.CAT, rappel_percent=8.0),
        ]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.rappel_percent, 8.0)
        self.assertEqual(result.get_priority(), 2)

    def test_p3_wins_over_p4(self):
        """P3 gana a P4 cuando no hay P1 ni P2."""
        rules = [
            MockRule(category_id=self.CAT, rappel_percent=1.0),
            MockRule(product_id=self.PROD, rappel_percent=6.0),
        ]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.rappel_percent, 6.0)
        self.assertEqual(result.get_priority(), 3)

    def test_p4_is_last_resort(self):
        """P4 se usa como último recurso."""
        rules = [
            MockRule(category_id=self.CAT, rappel_percent=4.0),
        ]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.rappel_percent, 4.0)
        self.assertEqual(result.get_priority(), 4)

    def test_no_rules_returns_none(self):
        """Sin reglas devuelve None."""
        result = find_applicable_rule_pure([], self.P, self.PROD, self.CAT)
        self.assertIsNone(result)

    def test_no_product_id_returns_none(self):
        """Sin product_id devuelve None."""
        rules = [MockRule(product_id=self.PROD, rappel_percent=5.0)]
        result = find_applicable_rule_pure(rules, self.P, None, self.CAT)
        self.assertIsNone(result)

    def test_inactive_rule_ignored(self):
        """Reglas inactivas no se usan."""
        rules = [MockRule(product_id=self.PROD, rappel_percent=5.0, active=False)]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNone(result)

    def test_partner_specific_rule_not_used_for_other_partner(self):
        """Regla de cliente_A no se aplica a cliente_B."""
        other_partner = 'partner_2'
        rules = [
            MockRule(partner_id=self.P, product_id=self.PROD, rappel_percent=10.0),
        ]
        result = find_applicable_rule_pure(rules, other_partner, self.PROD, self.CAT)
        self.assertIsNone(result, "Regla de cliente_A no debe aplicarse a cliente_B")

    def test_date_expired_rule_ignored(self):
        """Regla expirada no se devuelve."""
        yesterday = date.today() - timedelta(days=1)
        rules = [
            MockRule(
                product_id=self.PROD, rappel_percent=5.0,
                date_start=date.today() - timedelta(days=30),
                date_end=yesterday,
            )
        ]
        result = find_applicable_rule_pure(
            rules, self.P, self.PROD, self.CAT, check_date=date.today()
        )
        self.assertIsNone(result, "Regla expirada no debe aplicarse")

    def test_date_future_rule_ignored(self):
        """Regla que aún no ha empezado no se devuelve."""
        tomorrow = date.today() + timedelta(days=1)
        rules = [
            MockRule(product_id=self.PROD, rappel_percent=5.0, date_start=tomorrow)
        ]
        result = find_applicable_rule_pure(
            rules, self.P, self.PROD, self.CAT, check_date=date.today()
        )
        self.assertIsNone(result, "Regla futura no debe aplicarse")

    def test_date_valid_rule_returned(self):
        """Regla vigente hoy se devuelve correctamente."""
        today = date.today()
        rules = [
            MockRule(
                product_id=self.PROD, rappel_percent=5.0,
                date_start=today - timedelta(days=10),
                date_end=today + timedelta(days=10),
            )
        ]
        result = find_applicable_rule_pure(
            rules, self.P, self.PROD, self.CAT, check_date=today
        )
        self.assertIsNotNone(result)

    def test_rule_without_dates_always_valid(self):
        """Regla sin fechas siempre es válida."""
        rules = [MockRule(product_id=self.PROD, rappel_percent=5.0)]
        # Comprobar en el pasado
        result = find_applicable_rule_pure(
            rules, self.P, self.PROD, self.CAT,
            check_date=date(2000, 1, 1)
        )
        self.assertIsNotNone(result)
        # Comprobar en el futuro
        result2 = find_applicable_rule_pure(
            rules, self.P, self.PROD, self.CAT,
            check_date=date(2050, 12, 31)
        )
        self.assertIsNotNone(result2)

    def test_category_rule_not_matched_for_wrong_category(self):
        """Regla de categoría A no aplica a producto de categoría B."""
        other_cat = 'category_other'
        rules = [MockRule(category_id=self.CAT, rappel_percent=5.0)]
        result = find_applicable_rule_pure(
            rules, self.P, self.PROD, other_cat
        )
        self.assertIsNone(result,
                          "Regla de categoría A no debe aplicar a categoría B")

    def test_p1_rule_for_same_partner_different_product_not_used(self):
        """Regla P1 para otro producto no se aplica."""
        other_product = 'product_other'
        rules = [
            MockRule(partner_id=self.P, product_id=other_product, rappel_percent=10.0),
        ]
        result = find_applicable_rule_pure(rules, self.P, self.PROD, self.CAT)
        self.assertIsNone(result)


# ═══════════════════════════════════════════════════════════════════════════
#  Tests de validación de fechas (lógica pura)
# ═══════════════════════════════════════════════════════════════════════════

class TestDateValidation(unittest.TestCase):
    """Tests de validación de fechas de reglas."""

    def test_rule_on_exact_start_date(self):
        """Regla con date_start = hoy es válida hoy."""
        today = date.today()
        rule = MockRule(product_id='p', date_start=today)
        self.assertTrue(rule.is_valid_for_date(today))

    def test_rule_on_exact_end_date(self):
        """Regla con date_end = hoy es válida hoy."""
        today = date.today()
        rule = MockRule(product_id='p', date_end=today)
        self.assertTrue(rule.is_valid_for_date(today))

    def test_rule_day_before_start(self):
        """El día antes de date_start la regla NO es válida."""
        start = date.today()
        rule = MockRule(product_id='p', date_start=start)
        self.assertFalse(rule.is_valid_for_date(start - timedelta(days=1)))

    def test_rule_day_after_end(self):
        """El día después de date_end la regla NO es válida."""
        end = date.today()
        rule = MockRule(product_id='p', date_end=end)
        self.assertFalse(rule.is_valid_for_date(end + timedelta(days=1)))


# ═══════════════════════════════════════════════════════════════════════════
#  Tests de get_priority()
# ═══════════════════════════════════════════════════════════════════════════

class TestGetPriority(unittest.TestCase):
    """Tests del método get_priority de MockRule (equivalente a _get_priority)."""

    def test_partner_and_product_is_1(self):
        rule = MockRule(partner_id='p', product_id='prod')
        self.assertEqual(rule.get_priority(), 1)

    def test_partner_and_category_is_2(self):
        rule = MockRule(partner_id='p', category_id='cat')
        self.assertEqual(rule.get_priority(), 2)

    def test_all_and_product_is_3(self):
        rule = MockRule(product_id='prod')
        self.assertEqual(rule.get_priority(), 3)

    def test_all_and_category_is_4(self):
        rule = MockRule(category_id='cat')
        self.assertEqual(rule.get_priority(), 4)

    def test_partner_product_more_specific_than_partner_category(self):
        self.assertLess(
            MockRule(partner_id='p', product_id='prod').get_priority(),
            MockRule(partner_id='p', category_id='cat').get_priority()
        )

    def test_partner_category_more_specific_than_all_product(self):
        self.assertLess(
            MockRule(partner_id='p', category_id='cat').get_priority(),
            MockRule(product_id='prod').get_priority()
        )

    def test_all_product_more_specific_than_all_category(self):
        self.assertLess(
            MockRule(product_id='prod').get_priority(),
            MockRule(category_id='cat').get_priority()
        )


if __name__ == '__main__':
    # Ejecutar con: python3 tests/test_logic_standalone.py -v
    import sys
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(TestRappelComputeFormulas))
    suite.addTests(loader.loadTestsFromTestCase(TestPriorityAlgorithm))
    suite.addTests(loader.loadTestsFromTestCase(TestDateValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestGetPriority))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)

