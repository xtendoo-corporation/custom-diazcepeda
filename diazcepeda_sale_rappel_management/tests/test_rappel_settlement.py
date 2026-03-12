# -*- coding: utf-8 -*-
"""
Tests para rappel.settlement y rappel.settlement.line.

Cubre:
  - Creación de liquidación con secuencia automática
  - _compute_totals: suma de base y rappel de las líneas
  - rappel_settlement_line._compute_rappel_amount
  - action_generate_credit_note: flujo completo
  - action_generate_credit_note: estado incorrecto → UserError
  - action_generate_credit_note: ya existe abono → UserError
  - action_generate_credit_note: sin líneas → UserError
  - action_reset_to_draft: reinicio correcto y liberación de líneas
  - action_reset_to_draft: con abono generado → UserError
  - El abono generado es de tipo out_refund
  - El abono se vincula correctamente a la liquidación
  - El estado cambia correctamente en cada transición
"""
from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError
from datetime import date, timedelta


class TestRappelSettlementLine(TransactionCase):
    """Tests de rappel.settlement.line — campo computado rappel_amount."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Settlement Line',
            'customer_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Producto SL',
            'is_rappel_applicable': True,
        })
        cls.settlement = cls.env['rappel.settlement'].create({
            'partner_id': cls.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })

    def _make_line(self, base_amount, rappel_percent):
        return self.env['rappel.settlement.line'].create({
            'settlement_id': self.settlement.id,
            'product_id': self.product.id,
            'quantity': 10.0,
            'base_amount': base_amount,
            'rappel_percent': rappel_percent,
        })

    def test_rappel_amount_basic_calculation(self):
        """5% sobre 1000 = 50."""
        line = self._make_line(1000.0, 5.0)
        self.assertAlmostEqual(line.rappel_amount, 50.0, places=2)

    def test_rappel_amount_zero_percent(self):
        """0% rappel → importe = 0."""
        line = self._make_line(500.0, 0.0)
        self.assertAlmostEqual(line.rappel_amount, 0.0, places=2)

    def test_rappel_amount_100_percent(self):
        """100% rappel → importe = base_amount completo."""
        line = self._make_line(250.0, 100.0)
        self.assertAlmostEqual(line.rappel_amount, 250.0, places=2)

    def test_rappel_amount_fractional(self):
        """2.5% sobre 400 = 10."""
        line = self._make_line(400.0, 2.5)
        self.assertAlmostEqual(line.rappel_amount, 10.0, places=2)

    def test_rappel_amount_updates_when_base_changes(self):
        """Al cambiar la base, rappel_amount se recalcula."""
        line = self._make_line(1000.0, 10.0)
        self.assertAlmostEqual(line.rappel_amount, 100.0, places=2)
        line.base_amount = 2000.0
        self.assertAlmostEqual(line.rappel_amount, 200.0, places=2)

    def test_rappel_amount_updates_when_percent_changes(self):
        """Al cambiar el porcentaje, rappel_amount se recalcula."""
        line = self._make_line(1000.0, 5.0)
        self.assertAlmostEqual(line.rappel_amount, 50.0, places=2)
        line.rappel_percent = 10.0
        self.assertAlmostEqual(line.rappel_amount, 100.0, places=2)

    def test_currency_id_inherits_from_settlement(self):
        """La moneda de la línea proviene de la liquidación."""
        line = self._make_line(100.0, 5.0)
        self.assertEqual(line.currency_id, self.settlement.currency_id)


class TestRappelSettlementCreate(TransactionCase):
    """Tests de creación y campos básicos de rappel.settlement."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Settlement',
            'customer_rank': 1,
        })

    def test_create_settlement_generates_sequence(self):
        """Al crear una liquidación se asigna referencia automática."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
        })
        self.assertNotEqual(settlement.name, 'Nuevo',
                            "La referencia debe generarse automáticamente")
        self.assertIn('RAP', settlement.name,
                      "La referencia debe contener el prefijo RAP")

    def test_initial_state_is_draft(self):
        """Estado inicial es 'draft'."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
        })
        self.assertEqual(settlement.state, 'draft')

    def test_default_company_and_currency(self):
        """Empresa y moneda se asignan por defecto."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
        })
        self.assertEqual(settlement.company_id, self.env.company)
        self.assertEqual(settlement.currency_id, self.env.company.currency_id)

    def test_total_amounts_zero_when_no_lines(self):
        """Sin líneas los totales son 0."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
        })
        self.assertAlmostEqual(settlement.total_base_amount, 0.0)
        self.assertAlmostEqual(settlement.total_rappel_amount, 0.0)


class TestRappelSettlementTotals(TransactionCase):
    """Tests del cómputo de totales (_compute_totals)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Totales',
            'customer_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Prod Totales',
            'is_rappel_applicable': True,
        })
        cls.product2 = cls.env['product.product'].create({
            'name': 'Prod Totales 2',
            'is_rappel_applicable': True,
        })

    def test_totals_with_multiple_lines(self):
        """Los totales son la suma de todas las líneas."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        # Línea 1: base=1000, 5% → rappel=50
        self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 10,
            'base_amount': 1000.0,
            'rappel_percent': 5.0,
        })
        # Línea 2: base=2000, 10% → rappel=200
        self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product2.id,
            'quantity': 20,
            'base_amount': 2000.0,
            'rappel_percent': 10.0,
        })
        self.assertAlmostEqual(settlement.total_base_amount, 3000.0, places=2)
        self.assertAlmostEqual(settlement.total_rappel_amount, 250.0, places=2)

    def test_totals_update_when_line_deleted(self):
        """Los totales se actualizan al borrar una línea."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        line = self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 5,
            'base_amount': 500.0,
            'rappel_percent': 5.0,
        })
        self.assertAlmostEqual(settlement.total_base_amount, 500.0, places=2)
        line.unlink()
        self.assertAlmostEqual(settlement.total_base_amount, 0.0, places=2)


class TestRappelSettlementCreditNote(TransactionCase):
    """Tests de generación de abono (action_generate_credit_note)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Abono',
            'customer_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Prod Abono',
            'is_rappel_applicable': True,
            'type': 'consu',
        })

    def _make_calculated_settlement(self):
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 10,
            'base_amount': 1000.0,
            'rappel_percent': 5.0,
        })
        return settlement

    def test_generate_credit_note_creates_out_refund(self):
        """Se genera un account.move de tipo out_refund."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        self.assertTrue(settlement.invoice_id,
                        "Debe crearse un abono vinculado")
        self.assertEqual(settlement.invoice_id.move_type, 'out_refund',
                         "El abono debe ser de tipo 'out_refund'")

    def test_generate_credit_note_changes_state_to_invoiced(self):
        """El estado cambia a 'invoiced' tras generar el abono."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        self.assertEqual(settlement.state, 'invoiced')

    def test_generate_credit_note_links_partner(self):
        """El abono se crea para el cliente correcto."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        self.assertEqual(settlement.invoice_id.partner_id, self.partner)

    def test_generate_credit_note_invoice_amount(self):
        """El importe del abono corresponde al rappel calculado (50.0)."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        # El importe del abono debe ser el total del rappel
        self.assertAlmostEqual(
            settlement.invoice_id.amount_untaxed,
            settlement.total_rappel_amount,
            places=2,
        )

    def test_generate_credit_note_wrong_state_raises(self):
        """Desde estado draft no se puede generar abono."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'draft',
        })
        with self.assertRaises(UserError):
            settlement.action_generate_credit_note()

    def test_generate_credit_note_already_exists_raises(self):
        """Si ya existe un abono, lanza UserError."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        # Segunda llamada
        with self.assertRaises(UserError):
            settlement.action_generate_credit_note()

    def test_generate_credit_note_no_lines_raises(self):
        """Sin líneas de liquidación lanza UserError."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        with self.assertRaises(UserError):
            settlement.action_generate_credit_note()

    def test_action_view_invoice_returns_action(self):
        """action_view_invoice devuelve una acción correcta."""
        settlement = self._make_calculated_settlement()
        settlement.action_generate_credit_note()
        action = settlement.action_view_invoice()
        self.assertEqual(action['res_model'], 'account.move')
        self.assertEqual(action['res_id'], settlement.invoice_id.id)

    def test_action_view_invoice_without_invoice_raises(self):
        """action_view_invoice sin abono generado lanza UserError."""
        settlement = self._make_calculated_settlement()
        with self.assertRaises(UserError):
            settlement.action_view_invoice()


class TestRappelSettlementResetToDraft(TransactionCase):
    """Tests de action_reset_to_draft."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Reset',
            'customer_rank': 1,
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Prod Reset',
            'is_rappel_applicable': True,
            'type': 'consu',
        })

    def test_reset_to_draft_removes_lines(self):
        """Al reiniciar se eliminan las líneas de liquidación."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 1,
            'base_amount': 100.0,
            'rappel_percent': 5.0,
        })
        self.assertEqual(len(settlement.settlement_line_ids), 1)
        settlement.action_reset_to_draft()
        self.assertEqual(len(settlement.settlement_line_ids), 0,
                         "Las líneas deben eliminarse al reiniciar")

    def test_reset_to_draft_changes_state(self):
        """El estado cambia a 'draft'."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        settlement.action_reset_to_draft()
        self.assertEqual(settlement.state, 'draft')

    def test_reset_to_draft_with_invoice_raises(self):
        """No se puede reiniciar si hay un abono generado."""
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 1,
            'base_amount': 100.0,
            'rappel_percent': 5.0,
        })
        settlement.action_generate_credit_note()
        with self.assertRaises(UserError):
            settlement.action_reset_to_draft()

    def test_reset_frees_invoice_lines(self):
        """Al reiniciar se liberan las líneas de factura para futura liquidación."""
        # Crear una factura y simular que sus líneas están liquidadas
        settlement = self.env['rappel.settlement'].create({
            'partner_id': self.partner.id,
            'date_start': date.today() - timedelta(days=30),
            'date_end': date.today(),
            'state': 'calculated',
        })
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date.today(),
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'name': 'Test línea factura',
                'quantity': 1.0,
                'price_unit': 100.0,
            })],
        })
        inv_line = invoice.invoice_line_ids.filtered(
            lambda l: l.display_type == 'product'
        )
        sl = self.env['rappel.settlement.line'].create({
            'settlement_id': settlement.id,
            'product_id': self.product.id,
            'quantity': 1,
            'base_amount': 100.0,
            'rappel_percent': 5.0,
            'invoice_line_ids': [(6, 0, inv_line.ids)],
        })
        inv_line.write({'rappel_settlement_line_id': sl.id})

        # Verificar que está marcada
        self.assertTrue(inv_line.rappel_settlement_line_id)

        settlement.action_reset_to_draft()

        # Verificar que se ha liberado
        self.assertFalse(inv_line.rappel_settlement_line_id,
                         "La línea de factura debe liberarse al reiniciar")

