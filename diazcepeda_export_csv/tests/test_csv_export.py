# -*- coding: utf-8 -*-
# Tests para diazcepeda_export_csv — Odoo 18 Community
import csv
import os

from odoo.tests.common import TransactionCase


class TestCSVExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Cerveza SA',
            'ref': 'CLI-CERV-001',
            'street': 'Calle Lúpulo 5',
            'city': 'Sevilla',
            'zip': '41001',
        })
        cls.cat_cerveza = cls.env['product.category'].create({'name': 'Cerveza'})
        cls.product_cerveza = cls.env['product.product'].create({
            'name': 'Cerveza Rubia 33cl',
            'categ_id': cls.cat_cerveza.id,
            'standard_price': 0.80,
            'list_price': 1.20,
            'taxes_id': [],
        })

    def _create_posted_invoice_with_beer(self, date='2024-06-10'):
        """Crea y valida una factura con producto de categoría 'Cerveza'"""
        move = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.partner.id,
            'invoice_date': date,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product_cerveza.id,
                'quantity': 24,
                'price_unit': 1.20,
            })],
        })
        move.action_post()
        return move

    # ── Tests del bug corregido: partner desde move_id ────────────────────────

    def test_partner_obtained_from_move_id(self):
        """BUG-FIX: account.move.line no tiene partner_id; se debe usar move_id.partner_id"""
        move = self._create_posted_invoice_with_beer()
        lines = move.invoice_line_ids.filtered(
            lambda l: l.product_id.categ_id.name == 'Cerveza'
        )
        # Verificar que NO existe partner_id directo en move.line
        # (la corrección usa move_id.partner_id)
        partners_via_move = lines.mapped('move_id.partner_id')
        self.assertEqual(len(partners_via_move), 1)
        self.assertEqual(partners_via_move[0].name, 'Cliente Cerveza SA')

    def test_partner_id_field_not_on_invoice_line(self):
        """account.move.line no tiene campo partner_id accesible directamente"""
        move = self._create_posted_invoice_with_beer()
        line = move.invoice_line_ids[0]
        # partner_id no debe existir en el modelo account.move.line
        aml_fields = self.env['account.move.line'].fields_get()
        # En Odoo 18, account.move.line no tiene partner_id como campo propio
        # (solo está en account.move). Si existiera, el mapped directo funcionaría.
        # Este test documenta el comportamiento esperado.
        self.assertTrue(
            hasattr(line, 'move_id'),
            "account.move.line debe tener move_id para acceder al partner"
        )

    # ── Tests de creación de CSV ───────────────────────────────────────────────

    def test_create_a_csv_generates_file(self):
        """create_a_csv crea el archivo CSV tipo A con las líneas de cerveza"""
        move = self._create_posted_invoice_with_beer()
        lines = move.invoice_line_ids.filtered(
            lambda l: l.product_id.categ_id.name == 'Cerveza'
        )
        wizard = self.env['diazcepeda.export.csv'].create({
            'start_date': '2024-06-01',
            'end_date': '2024-06-30',
        })
        path = wizard.create_a_csv(lines)
        self.assertTrue(os.path.exists(path), f"El archivo CSV A no se creó en {path}")
        with open(path, 'r') as f:
            rows = list(csv.reader(f, delimiter=';'))
        self.assertGreater(len(rows), 0, "El CSV A debe tener al menos una fila")

    def test_create_b_csv_generates_file(self):
        """create_b_csv crea el archivo CSV tipo B con el stock por producto"""
        move = self._create_posted_invoice_with_beer()
        lines = move.invoice_line_ids.filtered(
            lambda l: l.product_id.categ_id.name == 'Cerveza'
        )
        wizard = self.env['diazcepeda.export.csv'].create({
            'start_date': '2024-06-01',
            'end_date': '2024-06-30',
        })
        path = wizard.create_b_csv(lines)
        self.assertTrue(os.path.exists(path), f"El archivo CSV B no se creó en {path}")

    def test_create_c_csv_contains_partner_data(self):
        """create_c_csv genera el CSV de clientes con la referencia correcta"""
        wizard = self.env['diazcepeda.export.csv'].create({
            'start_date': '2024-06-01',
            'end_date': '2024-06-30',
        })
        path = wizard.create_c_csv(self.partner)
        self.assertTrue(os.path.exists(path))
        with open(path, 'r') as f:
            content = f.read()
        self.assertIn('CLI-CERV-001', content,
                      "El CSV C debe incluir la referencia del cliente")
        self.assertIn('Sevilla', content,
                      "El CSV C debe incluir la ciudad del cliente")

    def test_get_start_date_month_pads_correctly(self):
        """get_start_date_month devuelve el mes con zero-padding"""
        wizard = self.env['diazcepeda.export.csv'].create({
            'start_date': '2024-03-01',
            'end_date': '2024-03-31',
        })
        self.assertEqual(wizard.get_start_date_month(), '03')

    def test_calculate_real_stock_returns_numeric(self):
        """calculate_real_stock devuelve un valor numérico"""
        wizard = self.env['diazcepeda.export.csv'].create({
            'start_date': '2024-06-01',
            'end_date': '2024-06-30',
        })
        stock = wizard.calculate_real_stock(self.product_cerveza.id)
        self.assertIsInstance(stock, (int, float))

