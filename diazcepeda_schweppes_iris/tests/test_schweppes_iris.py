# -*- coding: utf-8 -*-
# Tests para diazcepeda_schweppes_iris — Odoo 18 Community
import base64

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase


class TestSchweppesIris(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.schweppes_distributor_code = '1000026677'

        cls.partner = cls.env['res.partner'].create({
            'name': 'Distribuidora Schweppes Test',
            'schweppes_customer_code': 'CUST-001',
            'schweppes_route': '56',
            'schweppes_delivery_type': 'D',
            'street': 'Avda. Schweppes 1',
            'city': 'Barcelona',
            'zip': '08001',
            'email': 'test@schweppes.es',
            'phone': '931234567',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Tónica Schweppes 33cl',
            'schweppes_product_code': 'SCHW-001',
            'list_price': 0.90,
            'taxes_id': [],
        })

    def _create_confirmed_sale_order(self, date='2024-07-10 10:00:00'):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'date_order': date,
            'company_id': self.company.id,
            'order_line': [(0, 0, {
                'product_id': self.product.id,
                'name': self.product.name,
                'product_uom_qty': 120,
                'price_unit': 0.90,
            })],
        })
        order.action_confirm()
        return order

    # ── Campos personalizados ─────────────────────────────────────────────────

    def test_partner_custom_fields_exist(self):
        """Los campos Schweppes en res.partner se crean y leen correctamente"""
        partner = self.env['res.partner'].create({
            'name': 'Partner Schweppes Test',
            'schweppes_customer_code': 'CUST-TEST',
            'schweppes_route': '99',
            'schweppes_delivery_type': 'I',
        })
        self.assertEqual(partner.schweppes_customer_code, 'CUST-TEST')
        self.assertEqual(partner.schweppes_route, '99')
        self.assertEqual(partner.schweppes_delivery_type, 'I')

    def test_product_schweppes_code_field_exists(self):
        """El campo schweppes_product_code existe en product.template"""
        tmpl = self.env['product.template'].create({
            'name': 'Producto IRIS Test',
            'schweppes_product_code': 'PROD-IRIS-99',
        })
        self.assertEqual(tmpl.schweppes_product_code, 'PROD-IRIS-99')

    def test_company_distributor_code_field_exists(self):
        """El campo schweppes_distributor_code existe en res.company"""
        self.company.write({'schweppes_distributor_code': '9999999999'})
        self.assertEqual(self.company.schweppes_distributor_code, '9999999999')

    # ── Secuencia ────────────────────────────────────────────────────────────

    def test_sequence_exists(self):
        """La secuencia schweppes.iris.export se ha creado desde los datos del módulo"""
        seq = self.env['ir.sequence'].search([('code', '=', 'schweppes.iris.export')])
        self.assertTrue(seq, "La secuencia 'schweppes.iris.export' debe existir")

    def test_new_record_gets_sequence_name(self):
        """Al crear un registro, se asigna automáticamente el nombre desde la secuencia"""
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        self.assertNotEqual(record.name, 'Nuevo',
                            "El nombre debe asignarse desde la secuencia, no quedar como 'Nuevo'")
        self.assertTrue(record.name.startswith('SCHW/IRIS/'),
                        f"El nombre debe seguir el prefijo SCHW/IRIS/: {record.name}")

    # ── Generación del fichero ────────────────────────────────────────────────

    def test_generate_file_raises_error_without_sale_orders(self):
        """action_generate_file lanza UserError si no hay pedidos confirmados en el rango"""
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2000-01-01',
            'date_to': '2000-01-31',
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError,
                               msg="Debe lanzar UserError cuando no hay pedidos"):
            record.action_generate_file()

    def test_generate_file_sets_state_done(self):
        """Tras generar el fichero, el estado cambia a 'done'"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_generate_file()
        self.assertEqual(record.state, 'done')

    def test_generate_file_content_structure(self):
        """El fichero IRIS tiene la estructura correcta: CT al inicio y FT al final"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_generate_file()
        self.assertTrue(record.file_data, "file_data debe contener datos binarios")
        content = base64.b64decode(record.file_data).decode('utf-8')
        lines = content.strip().split('\r\n')
        self.assertTrue(lines[0].startswith('CT'),
                        f"La primera línea debe empezar por 'CT': {lines[0]}")
        self.assertTrue(lines[-1].startswith('FT'),
                        f"La última línea debe empezar por 'FT': {lines[-1]}")

    def test_generate_file_contains_dicp_and_didp(self):
        """El fichero contiene registros DICP (cabecera pedido) y DIDP (línea producto)"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_generate_file()
        content = base64.b64decode(record.file_data).decode('utf-8')
        self.assertIn('DICP', content, "Debe contener registros DICP (cabecera de pedido)")
        self.assertIn('DIDP', content, "Debe contener registros DIDP (línea de producto)")
        self.assertIn('DIMC', content, "Debe contener registros DIMC (ficha de cliente)")

    def test_generate_file_creates_attachment(self):
        """La generación crea un adjunto .txt en el registro"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_generate_file()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'schweppes.iris.export'),
            ('res_id', '=', record.id),
            ('mimetype', '=', 'text/plain'),
        ], limit=1)
        self.assertTrue(attachment, "Debe crearse un adjunto de tipo text/plain")
        self.assertTrue(record.file_name.endswith('.txt'))

    def test_summary_counters_updated(self):
        """Los contadores de pedidos, clientes y líneas se actualizan correctamente"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_generate_file()
        self.assertGreater(record.sale_order_count, 0, "sale_order_count debe ser > 0")
        self.assertGreater(record.partner_count, 0, "partner_count debe ser > 0")
        self.assertGreater(record.line_count, 0, "line_count debe ser > 0")
        self.assertEqual(record.line_count, len(record.sale_order_line_ids),
                         "line_count debe coincidir con las líneas guardadas en el informe")

