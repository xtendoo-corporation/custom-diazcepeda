# -*- coding: utf-8 -*-
"""
Tests para el asistente rappel.settlement.wizard.

Cubre:
  - Flujo completo: facturas → liquidación con líneas correctas
  - Exclusión de líneas ya liquidadas (anti-doble liquidación)
  - Filtro por producto específico
  - Filtro por categoría de producto
  - Solo productos con is_rappel_applicable=True
  - Error si no hay facturas en el período
  - Error si no hay líneas aplicables
  - Error si no hay reglas aplicables
  - Las líneas de factura quedan marcadas como liquidadas
  - Generación automática de abono si generate_credit_note=True
  - Validación de fechas (inicio > fin → UserError)
  - Acumulación correcta de cantidades de múltiples facturas
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import date, timedelta


class TestRappelSettlementWizardBase(TransactionCase):
    """Base común para todos los tests del wizard."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Partner
        cls.partner = cls.env['res.partner'].create({
            'name': 'Distribuidora Test',
            'customer_rank': 1,
        })
        # Categorías
        cls.cat_beer = cls.env['product.category'].create({'name': 'Cervezas'})
        cls.cat_wine = cls.env['product.category'].create({'name': 'Vinos'})

        # Productos
        cls.beer = cls.env['product.product'].create({
            'name': 'Cerveza Artesana',
            'categ_id': cls.cat_beer.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 5.0,
            'list_price': 2.50,
            'type': 'consu',
        })
        cls.wine = cls.env['product.product'].create({
            'name': 'Vino Crianza',
            'categ_id': cls.cat_wine.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 3.0,
            'list_price': 8.00,
            'type': 'consu',
        })
        cls.box = cls.env['product.product'].create({
            'name': 'Caja de Cartón',
            'categ_id': cls.cat_beer.id,
            'is_rappel_applicable': False,
            'list_price': 0.50,
            'type': 'consu',
        })

        # Regla de rappel para cerveza (P3: todos los clientes + producto)
        cls.rule_beer = cls.env['rappel.rule'].create({
            'name': 'Rappel Cerveza',
            'product_id': cls.beer.id,
            'rappel_percent': 5.0,
        })
        # Regla de rappel para vinos por categoría (P4)
        cls.rule_wine_cat = cls.env['rappel.rule'].create({
            'name': 'Rappel Vinos',
            'product_category_id': cls.cat_wine.id,
            'rappel_percent': 3.0,
        })

        # Período estándar
        cls.date_start = date.today().replace(day=1) - timedelta(days=32)
        cls.date_start = cls.date_start.replace(day=1)
        cls.date_end = cls.date_start + timedelta(days=30)

    def _create_posted_invoice(self, partner=None, invoice_date=None, lines=None):
        """Helper: crea y confirma una factura de cliente."""
        if partner is None:
            partner = self.partner
        if invoice_date is None:
            invoice_date = self.date_start + timedelta(days=5)
        if lines is None:
            lines = [(self.beer, 10, 2.50)]

        invoice_lines = []
        for product, qty, price in lines:
            invoice_lines.append((0, 0, {
                'product_id': product.id,
                'name': product.name,
                'quantity': qty,
                'price_unit': price,
            }))

        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': partner.id,
            'invoice_date': invoice_date,
            'invoice_line_ids': invoice_lines,
        })
        invoice.action_post()
        return invoice

    def _make_wizard(self, partner=None, date_start=None, date_end=None,
                     product_id=False, category_id=False, credit_note=False):
        return self.env['rappel.settlement.wizard'].create({
            'partner_id': (partner or self.partner).id,
            'date_start': date_start or self.date_start,
            'date_end': date_end or self.date_end,
            'product_id': product_id,
            'product_category_id': category_id,
            'generate_credit_note': credit_note,
        })


class TestWizardValidation(TestRappelSettlementWizardBase):
    """Tests de validaciones del wizard."""

    def test_date_start_after_end_raises(self):
        """fecha_inicio > fecha_fin → UserError."""
        with self.assertRaises(UserError):
            self._make_wizard(
                date_start=date.today(),
                date_end=date.today() - timedelta(days=1),
            )

    def test_no_invoices_raises(self):
        """Sin facturas en el período → UserError."""
        wizard = self._make_wizard(
            date_start=date(2000, 1, 1),
            date_end=date(2000, 1, 31),
        )
        with self.assertRaises(UserError):
            wizard.action_calculate()

    def test_draft_invoice_not_included(self):
        """Facturas en borrador no se incluyen."""
        draft_invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': self.date_start + timedelta(days=5),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.beer.id,
                'name': 'Beer',
                'quantity': 10,
                'price_unit': 2.50,
            })],
        })
        # NO confirmamos la factura (queda en draft)
        wizard = self._make_wizard()
        with self.assertRaises(UserError):
            wizard.action_calculate()

    def test_invoice_outside_period_not_included(self):
        """Facturas fuera del período no se incluyen."""
        # Crear factura fuera del período
        self._create_posted_invoice(
            invoice_date=self.date_end + timedelta(days=10)
        )
        wizard = self._make_wizard()
        with self.assertRaises(UserError):
            wizard.action_calculate()

    def test_non_rappel_product_raises_no_lines(self):
        """Facturas solo con productos sin rappel → UserError (no hay líneas aplicables)."""
        self._create_posted_invoice(lines=[(self.box, 100, 0.50)])
        wizard = self._make_wizard()
        with self.assertRaises(UserError):
            wizard.action_calculate()


class TestWizardFullWorkflow(TestRappelSettlementWizardBase):
    """Tests del flujo completo del wizard."""

    def test_calculate_creates_settlement(self):
        """El wizard crea una liquidación en estado 'calculated'."""
        self._create_posted_invoice()
        wizard = self._make_wizard()
        action = wizard.action_calculate()

        self.assertEqual(action['res_model'], 'rappel.settlement')
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertTrue(settlement.exists())
        self.assertEqual(settlement.state, 'calculated')

    def test_calculate_correct_partner(self):
        """La liquidación se crea para el cliente correcto."""
        self._create_posted_invoice()
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertEqual(settlement.partner_id, self.partner)

    def test_calculate_correct_dates(self):
        """La liquidación tiene las fechas del wizard."""
        self._create_posted_invoice()
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertEqual(settlement.date_start, self.date_start)
        self.assertEqual(settlement.date_end, self.date_end)

    def test_calculate_correct_base_amount(self):
        """La base imponible es correcta: qty * price_unit."""
        # 10 unidades × 2.50 = 25.0
        self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        beer_line = settlement.settlement_line_ids.filtered(
            lambda l: l.product_id.id == self.beer.id
        )
        self.assertTrue(beer_line, "Debe existir línea para la cerveza")
        self.assertAlmostEqual(beer_line.base_amount, 25.0, places=2)

    def test_calculate_correct_rappel_percent_from_rule(self):
        """El porcentaje de rappel proviene de la regla configurada."""
        self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        beer_line = settlement.settlement_line_ids.filtered(
            lambda l: l.product_id.id == self.beer.id
        )
        self.assertAlmostEqual(beer_line.rappel_percent, 5.0, places=2)

    def test_calculate_correct_rappel_amount(self):
        """El importe de rappel es correcto: base × pct/100."""
        # base=25.0, pct=5% → rappel=1.25
        self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        beer_line = settlement.settlement_line_ids.filtered(
            lambda l: l.product_id.id == self.beer.id
        )
        self.assertAlmostEqual(beer_line.rappel_amount, 1.25, places=2)

    def test_invoice_lines_marked_as_settled(self):
        """Las líneas de factura quedan marcadas con rappel_settlement_line_id."""
        invoice = self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])

        product_lines = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        )
        for inv_line in product_lines:
            if inv_line.product_id == self.beer:
                self.assertTrue(inv_line.rappel_settlement_line_id,
                                "La línea de factura debe estar marcada")

    def test_already_settled_lines_excluded(self):
        """Líneas ya liquidadas no se incluyen en una segunda liquidación."""
        invoice = self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])

        # Primera liquidación
        wizard1 = self._make_wizard()
        action1 = wizard1.action_calculate()

        # Segunda liquidación del mismo período → no debe haber líneas nuevas
        wizard2 = self._make_wizard()
        with self.assertRaises(UserError):
            wizard2.action_calculate()

    def test_multiple_invoices_aggregated(self):
        """Varias facturas del mismo producto se agregan en una línea."""
        # Factura 1: 10 unidades × 2.50
        self._create_posted_invoice(
            lines=[(self.beer, 10, 2.50)],
            invoice_date=self.date_start + timedelta(days=2),
        )
        # Factura 2: 5 unidades × 2.50
        self._create_posted_invoice(
            lines=[(self.beer, 5, 2.50)],
            invoice_date=self.date_start + timedelta(days=10),
        )

        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])

        beer_line = settlement.settlement_line_ids.filtered(
            lambda l: l.product_id.id == self.beer.id
        )
        # base = 25.0 + 12.5 = 37.5
        self.assertAlmostEqual(beer_line.base_amount, 37.5, places=2,
                               msg="Las bases deben agregarse de ambas facturas")
        self.assertAlmostEqual(beer_line.quantity, 15.0, places=2,
                               msg="Las cantidades deben agregarse")

    def test_multiple_products_generate_multiple_lines(self):
        """Una factura con varios productos genera una línea por producto."""
        self._create_posted_invoice(lines=[
            (self.beer, 10, 2.50),
            (self.wine, 5, 8.00),
        ])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertEqual(len(settlement.settlement_line_ids), 2,
                         "Debe haber una línea por producto")

    def test_filter_by_product(self):
        """Con filtro de producto solo se liquida ese producto."""
        self._create_posted_invoice(lines=[
            (self.beer, 10, 2.50),
            (self.wine, 5, 8.00),
        ])
        wizard = self._make_wizard(product_id=self.beer.id)
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        products = settlement.settlement_line_ids.mapped('product_id')
        self.assertIn(self.beer, products, "Debe incluir cerveza")
        self.assertNotIn(self.wine, products,
                         "No debe incluir vino con filtro de producto")

    def test_filter_by_category(self):
        """Con filtro de categoría solo se liquidan productos de esa categoría."""
        self._create_posted_invoice(lines=[
            (self.beer, 10, 2.50),
            (self.wine, 5, 8.00),
        ])
        wizard = self._make_wizard(category_id=self.cat_beer.id)
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        products = settlement.settlement_line_ids.mapped('product_id')
        self.assertIn(self.beer, products)
        self.assertNotIn(self.wine, products,
                         "El vino es de otra categoría")

    def test_non_rappel_products_excluded_automatically(self):
        """Productos con is_rappel_applicable=False se excluyen."""
        self._create_posted_invoice(lines=[
            (self.beer, 10, 2.50),
            (self.box, 50, 0.50),  # No tiene rappel
        ])
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        products = settlement.settlement_line_ids.mapped('product_id')
        self.assertNotIn(self.box, products,
                         "Productos sin rappel no deben incluirse")

    def test_generate_credit_note_automatically(self):
        """Con generate_credit_note=True se genera el abono al calcular."""
        self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        wizard = self._make_wizard(credit_note=True)
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertTrue(settlement.invoice_id,
                        "Debe generarse el abono automáticamente")
        self.assertEqual(settlement.state, 'invoiced')

    def test_settlement_sequence_name(self):
        """La liquidación creada tiene referencia con prefijo RAP."""
        self._create_posted_invoice()
        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        self.assertIn('RAP', settlement.name)

    def test_invoice_from_different_partner_not_included(self):
        """Facturas de otro cliente no se incluyen."""
        other_partner = self.env['res.partner'].create({
            'name': 'Otro Distribuidor',
            'customer_rank': 1,
        })
        # Solo creamos factura de otro cliente
        self._create_posted_invoice(partner=other_partner)
        wizard = self._make_wizard()  # Wizard para cls.partner
        with self.assertRaises(UserError):
            wizard.action_calculate()

    def test_credit_note_excluded_from_calculation(self):
        """Los abonos (out_refund) no se incluyen en el cálculo."""
        self._create_posted_invoice(lines=[(self.beer, 10, 2.50)])
        # Crear un abono (no debe incluirse)
        refund = self.env['account.move'].create({
            'move_type': 'out_refund',
            'partner_id': self.partner.id,
            'invoice_date': self.date_start + timedelta(days=5),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.beer.id,
                'name': 'Abono previo',
                'quantity': 2,
                'price_unit': 2.50,
            })],
        })
        refund.action_post()

        wizard = self._make_wizard()
        action = wizard.action_calculate()
        settlement = self.env['rappel.settlement'].browse(action['res_id'])
        # El abono no debe reducir la base ni contar como línea adicional
        beer_line = settlement.settlement_line_ids.filtered(
            lambda l: l.product_id.id == self.beer.id
        )
        # La base debe ser solo de la factura, no del abono
        self.assertAlmostEqual(beer_line.base_amount, 25.0, places=2,
                               msg="Los abonos no deben incluirse en la base")


class TestWizardNoRulesNoDefault(TestRappelSettlementWizardBase):
    """Tests cuando no hay reglas ni porcentaje por defecto."""

    def test_no_rule_no_default_raises(self):
        """Producto sin regla ni default_rappel_percent → no se genera línea → UserError."""
        # Producto sin regla y sin porcentaje por defecto
        product_no_rule = self.env['product.product'].create({
            'name': 'Producto Sin Regla',
            'categ_id': self.cat_beer.id,
            'is_rappel_applicable': True,
            'default_rappel_percent': 0.0,  # Sin porcentaje por defecto
            'type': 'consu',
        })
        # Categoría sin regla
        cat_empty = self.env['product.category'].create({'name': 'Cat Sin Regla'})
        product_no_rule.categ_id = cat_empty.id

        self._create_posted_invoice(lines=[(product_no_rule, 5, 10.0)])
        wizard = self._make_wizard()
        with self.assertRaises(UserError):
            wizard.action_calculate()

