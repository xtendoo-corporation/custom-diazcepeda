# -*- coding: utf-8 -*-
"""
Tests para el modelo rappel.rule.

Cubre:
  - Creación de reglas con datos válidos
  - Constraint: al menos producto o categoría es obligatorio
  - Constraint: fecha_inicio <= fecha_fin
  - Método _get_priority(): los 4 casos de prioridad
  - Método find_applicable_rule(): los 4 niveles de prioridad
  - Filtrado por fecha activa / inactiva
  - Filtrado por empresa
  - Reglas archivadas (active=False) no se aplican
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class TestRappelRuleConstraints(TransactionCase):
    """Tests de restricciones de integridad del modelo rappel.rule."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Test Rappel',
            'customer_rank': 1,
        })
        cls.category = cls.env['product.category'].create({
            'name': 'Categoría Test Rappel',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Test Rappel',
            'categ_id': cls.category.id,
        })

    def test_create_rule_with_product_only(self):
        """Se puede crear una regla con solo producto."""
        rule = self.env['rappel.rule'].create({
            'name': 'Regla Producto',
            'product_id': self.product.id,
            'rappel_percent': 5.0,
        })
        self.assertEqual(rule.rappel_percent, 5.0)
        self.assertTrue(rule.active)

    def test_create_rule_with_category_only(self):
        """Se puede crear una regla con solo categoría."""
        rule = self.env['rappel.rule'].create({
            'name': 'Regla Categoría',
            'product_category_id': self.category.id,
            'rappel_percent': 3.0,
        })
        self.assertEqual(rule.rappel_percent, 3.0)

    def test_create_rule_with_product_and_category(self):
        """Se puede crear una regla con producto y categoría simultáneamente."""
        rule = self.env['rappel.rule'].create({
            'name': 'Regla P+C',
            'product_id': self.product.id,
            'product_category_id': self.category.id,
            'rappel_percent': 7.0,
        })
        self.assertTrue(rule.id)

    def test_constraint_no_product_no_category_raises(self):
        """Sin producto ni categoría debe lanzar ValidationError."""
        with self.assertRaises(ValidationError):
            self.env['rappel.rule'].create({
                'name': 'Regla Inválida',
                'rappel_percent': 5.0,
            })

    def test_constraint_dates_start_after_end_raises(self):
        """Fecha inicio posterior a fecha fin debe lanzar ValidationError."""
        today = date.today()
        with self.assertRaises(ValidationError):
            self.env['rappel.rule'].create({
                'name': 'Fechas Inválidas',
                'product_id': self.product.id,
                'rappel_percent': 5.0,
                'date_start': today,
                'date_end': today - timedelta(days=1),
            })

    def test_constraint_dates_start_equals_end_ok(self):
        """Fecha inicio igual a fecha fin debe ser válida."""
        today = date.today()
        rule = self.env['rappel.rule'].create({
            'name': 'Fecha Igual',
            'product_id': self.product.id,
            'rappel_percent': 2.0,
            'date_start': today,
            'date_end': today,
        })
        self.assertTrue(rule.id)

    def test_constraint_dates_start_before_end_ok(self):
        """Fecha inicio anterior a fecha fin es válida."""
        today = date.today()
        rule = self.env['rappel.rule'].create({
            'name': 'Fechas Correctas',
            'product_id': self.product.id,
            'rappel_percent': 2.0,
            'date_start': today - timedelta(days=10),
            'date_end': today + timedelta(days=10),
        })
        self.assertTrue(rule.id)

    def test_default_active_is_true(self):
        """Las reglas nuevas están activas por defecto."""
        rule = self.env['rappel.rule'].create({
            'name': 'Activa por defecto',
            'product_id': self.product.id,
            'rappel_percent': 1.0,
        })
        self.assertTrue(rule.active)

    def test_default_company(self):
        """La empresa se asigna automáticamente a la empresa del entorno."""
        rule = self.env['rappel.rule'].create({
            'name': 'Empresa por defecto',
            'product_id': self.product.id,
            'rappel_percent': 1.0,
        })
        self.assertEqual(rule.company_id, self.env.company)


class TestRappelRulePriority(TransactionCase):
    """Tests del método _get_priority()."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner Prioridad',
            'customer_rank': 1,
        })
        cls.category = cls.env['product.category'].create({
            'name': 'Categoría Prioridad',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Producto Prioridad',
            'categ_id': cls.category.id,
        })

    def _make_rule(self, partner=None, product=None, category=None, pct=5.0):
        vals = {'name': 'Test', 'rappel_percent': pct}
        if partner:
            vals['partner_id'] = partner.id
        if product:
            vals['product_id'] = product.id
        if category:
            vals['product_category_id'] = category.id
        return self.env['rappel.rule'].create(vals)

    def test_priority_1_partner_and_product(self):
        """Prioridad 1: Cliente + Producto."""
        rule = self._make_rule(partner=self.partner, product=self.product)
        self.assertEqual(rule._get_priority(), 1)

    def test_priority_2_partner_and_category(self):
        """Prioridad 2: Cliente + Categoría."""
        rule = self._make_rule(partner=self.partner, category=self.category)
        self.assertEqual(rule._get_priority(), 2)

    def test_priority_3_all_customers_and_product(self):
        """Prioridad 3: Todos los clientes + Producto."""
        rule = self._make_rule(product=self.product)
        self.assertEqual(rule._get_priority(), 3)

    def test_priority_4_all_customers_and_category(self):
        """Prioridad 4: Todos los clientes + Categoría (menos específica)."""
        rule = self._make_rule(category=self.category)
        self.assertEqual(rule._get_priority(), 4)


class TestRappelRuleFindApplicable(TransactionCase):
    """Tests del método find_applicable_rule() — sistema completo de prioridades."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_a = cls.env['res.partner'].create({
            'name': 'Cliente A', 'customer_rank': 1,
        })
        cls.partner_b = cls.env['res.partner'].create({
            'name': 'Cliente B', 'customer_rank': 1,
        })
        cls.category = cls.env['product.category'].create({
            'name': 'Cat. Bebidas',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Cerveza Premium',
            'categ_id': cls.category.id,
        })
        cls.product2 = cls.env['product.product'].create({
            'name': 'Cerveza Lager',
            'categ_id': cls.category.id,
        })

    def _rule(self, partner=None, product=None, category=None, pct=5.0, **kwargs):
        vals = {'name': f'Regla {pct}%', 'rappel_percent': pct}
        if partner:
            vals['partner_id'] = partner.id
        if product:
            vals['product_id'] = product.id
        if category:
            vals['product_category_id'] = category.id
        vals.update(kwargs)
        return self.env['rappel.rule'].create(vals)

    def test_find_returns_empty_when_no_rules(self):
        """Sin reglas activas devuelve recordset vacío."""
        # Desactivar todas las reglas existentes para este test
        self.env['rappel.rule'].search([]).write({'active': False})
        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertFalse(result)

    def test_find_returns_empty_without_product(self):
        """Sin product_id devuelve recordset vacío."""
        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, False
        )
        self.assertFalse(result)

    def test_priority1_wins_over_all_others(self):
        """P1 (cliente+producto) gana a P2, P3 y P4."""
        self.env['rappel.rule'].search([]).write({'active': False})
        r4 = self._rule(category=self.category, pct=1.0)
        r3 = self._rule(product=self.product, pct=2.0)
        r2 = self._rule(partner=self.partner_a, category=self.category, pct=3.0)
        r1 = self._rule(partner=self.partner_a, product=self.product, pct=10.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertEqual(result.id, r1.id,
                         "P1 (Cliente+Producto) debe ganar")

    def test_priority2_wins_over_p3_and_p4(self):
        """P2 (cliente+categoría) gana a P3 y P4 cuando no hay P1."""
        self.env['rappel.rule'].search([]).write({'active': False})
        r4 = self._rule(category=self.category, pct=1.0)
        r3 = self._rule(product=self.product, pct=2.0)
        r2 = self._rule(partner=self.partner_a, category=self.category, pct=8.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertEqual(result.id, r2.id,
                         "P2 (Cliente+Categoría) debe ganar sobre P3 y P4")

    def test_priority3_wins_over_p4(self):
        """P3 (todos+producto) gana a P4 cuando no hay P1 ni P2."""
        self.env['rappel.rule'].search([]).write({'active': False})
        r4 = self._rule(category=self.category, pct=1.0)
        r3 = self._rule(product=self.product, pct=6.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertEqual(result.id, r3.id,
                         "P3 (Todos+Producto) debe ganar sobre P4")

    def test_priority4_used_as_fallback(self):
        """P4 (todos+categoría) se usa como último recurso."""
        self.env['rappel.rule'].search([]).write({'active': False})
        r4 = self._rule(category=self.category, pct=4.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertEqual(result.id, r4.id,
                         "P4 (Todos+Categoría) se usa como fallback")

    def test_inactive_rule_not_returned(self):
        """Reglas inactivas no se devuelven."""
        self.env['rappel.rule'].search([]).write({'active': False})
        self._rule(product=self.product, pct=5.0, active=False)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        self.assertFalse(result, "Reglas inactivas no deben aplicarse")

    def test_rule_not_matching_partner_used_for_other_partner(self):
        """Una regla P1 de cliente_A no se aplica a cliente_B."""
        self.env['rappel.rule'].search([]).write({'active': False})
        r1_a = self._rule(partner=self.partner_a, product=self.product, pct=10.0)
        r4 = self._rule(category=self.category, pct=2.0)

        result_a = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id
        )
        result_b = self.env['rappel.rule'].find_applicable_rule(
            self.partner_b.id, self.product.id
        )
        self.assertEqual(result_a.id, r1_a.id)
        self.assertEqual(result_b.id, r4.id,
                         "cliente_B debe usar la regla más genérica disponible")

    def test_date_filter_excludes_expired_rule(self):
        """Regla expirada no se devuelve al buscar con fecha posterior."""
        self.env['rappel.rule'].search([]).write({'active': False})
        past_end = date.today() - timedelta(days=1)
        expired_rule = self._rule(
            product=self.product, pct=5.0,
            date_start=date.today() - timedelta(days=30),
            date_end=past_end,
        )

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id, date=date.today()
        )
        self.assertFalse(result, "Regla expirada no debe aplicarse")

    def test_date_filter_excludes_future_rule(self):
        """Regla que aún no ha comenzado no se devuelve."""
        self.env['rappel.rule'].search([]).write({'active': False})
        future_start = date.today() + timedelta(days=1)
        self._rule(
            product=self.product, pct=5.0,
            date_start=future_start,
        )

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id, date=date.today()
        )
        self.assertFalse(result, "Regla futura no debe aplicarse")

    def test_date_filter_includes_current_rule(self):
        """Regla vigente hoy se devuelve."""
        self.env['rappel.rule'].search([]).write({'active': False})
        today = date.today()
        rule = self._rule(
            product=self.product, pct=5.0,
            date_start=today - timedelta(days=10),
            date_end=today + timedelta(days=10),
        )

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id, date=today
        )
        self.assertEqual(result.id, rule.id, "Regla vigente debe aplicarse")

    def test_rule_without_dates_always_applies(self):
        """Regla sin fechas aplica siempre."""
        self.env['rappel.rule'].search([]).write({'active': False})
        rule = self._rule(product=self.product, pct=5.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, self.product.id,
            date=date.today() + timedelta(days=3650),  # 10 años en el futuro
        )
        self.assertEqual(result.id, rule.id)

    def test_product_not_in_category_does_not_match_category_rule(self):
        """Un producto de otra categoría no coincide con regla de categoría."""
        self.env['rappel.rule'].search([]).write({'active': False})
        other_category = self.env['product.category'].create({
            'name': 'Otra Categoría',
        })
        other_product = self.env['product.product'].create({
            'name': 'Producto Otra Cat',
            'categ_id': other_category.id,
        })
        # Regla solo para self.category
        self._rule(category=self.category, pct=5.0)

        result = self.env['rappel.rule'].find_applicable_rule(
            self.partner_a.id, other_product.id
        )
        self.assertFalse(result, "Producto de otra categoría no debe coincidir")

