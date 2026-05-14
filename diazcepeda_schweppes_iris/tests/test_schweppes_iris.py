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
        order.write({'date_order': date})
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
        """Cargar líneas lanza UserError si no hay pedidos confirmados en el rango"""
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2000-01-01',
            'date_to': '2000-01-31',
            'company_id': self.company.id,
        })
        with self.assertRaises(UserError,
                               msg="Debe lanzar UserError cuando no hay pedidos"):
            record.action_load_export_lines()

    def test_generate_file_sets_state_generated(self):
        """Generar crea el fichero y deja el estado en generado."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()
        self.assertEqual(record.state, 'generated')
        self.assertTrue(record.file_data)

    def test_generate_file_content_structure(self):
        """El fichero IRIS tiene la estructura correcta: CT al inicio y FT al final"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
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
        record.action_load_export_lines()
        record.action_generate_file()
        content = base64.b64decode(record.file_data).decode('utf-8')
        self.assertIn('DICP', content, "Debe contener registros DICP (cabecera de pedido)")
        self.assertIn('DIDP', content, "Debe contener registros DIDP (línea de producto)")
        self.assertIn('DIMC', content, "Debe contener registros DIMC (ficha de cliente)")

    def test_generate_file_does_not_create_attachment_automatically(self):
        """Generar no debe adjuntar automáticamente; eso se hace al enviar."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()
        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'schweppes.iris.export'),
            ('res_id', '=', record.id),
            ('mimetype', '=', 'text/plain'),
        ], limit=1)
        self.assertFalse(attachment, "No debe crearse adjunto hasta pulsar Enviar")
        self.assertTrue(record.file_name.endswith('.txt'))

    def test_send_file_marks_record_as_sent_and_creates_attachment(self):
        """Enviar debe crear el adjunto y pasar el registro a enviado."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()
        record.action_send_file()

        attachment = self.env['ir.attachment'].search([
            ('res_model', '=', 'schweppes.iris.export'),
            ('res_id', '=', record.id),
            ('mimetype', '=', 'text/plain'),
        ], limit=1)

        self.assertEqual(record.state, 'sent')
        self.assertTrue(attachment, "Debe crearse el adjunto al enviar")

    def test_delete_file_returns_record_to_draft(self):
        """Eliminar el fichero debe limpiar binario/nombre y volver a borrador."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()

        self.assertEqual(record.state, 'generated')
        self.assertTrue(record.file_data)

        record.action_delete_file()

        self.assertEqual(record.state, 'draft')
        self.assertFalse(record.file_data)
        self.assertFalse(record.file_name)

    def test_delete_file_raises_if_no_generated_file(self):
        """No debe poder eliminarse un fichero inexistente."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()

        with self.assertRaises(UserError):
            record.action_delete_file()

    def test_generated_export_is_blocked_until_deleting_file(self):
        """Mientras exista file_data, la exportación generada no debe admitir cambios directos."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()

        with self.assertRaises(UserError):
            record.write({'date_to': '2024-08-01'})

        with self.assertRaises(UserError):
            record.export_line_ids[0].write({'product_uom_qty': 321})

        record.action_delete_file()
        record.write({'date_to': '2024-08-01'})
        record.export_line_ids[0].write({'product_uom_qty': 321})

        self.assertEqual(record.state, 'draft')
        self.assertEqual(record.date_to.isoformat(), '2024-08-01')
        self.assertEqual(record.export_line_ids[0].product_uom_qty, 321)

    def test_sent_export_is_immutable(self):
        """Una exportación enviada no debe admitir recarga, regeneración ni cambios manuales."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()
        record.action_send_file()

        with self.assertRaises(UserError):
            record.write({'date_to': '2024-08-01'})

        with self.assertRaises(UserError):
            record.action_load_export_lines()

        with self.assertRaises(UserError):
            record.action_generate_file()

        with self.assertRaises(UserError):
            record.action_delete_file()

        with self.assertRaises(UserError):
            record.export_line_ids[0].write({'product_uom_qty': 321})

    def test_summary_counters_updated(self):
        """Los contadores de pedidos, clientes y líneas se actualizan correctamente"""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        record.action_generate_file()
        self.assertGreater(record.sale_order_count, 0, "sale_order_count debe ser > 0")
        self.assertGreater(record.partner_count, 0, "partner_count debe ser > 0")
        self.assertGreater(record.line_count, 0, "line_count debe ser > 0")
        self.assertEqual(record.line_count, len(record.export_line_ids),
                         "line_count debe coincidir con las líneas guardadas en la tabla snapshot")

    def test_load_export_lines_creates_snapshot_table_lines(self):
        """Las líneas origen se copian a la tabla schweppes_export_lines."""
        order = self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })

        record.action_load_export_lines()

        self.assertEqual(len(record.export_line_ids), 1)
        self.assertEqual(record.export_line_ids.sale_order_id, order)
        self.assertEqual(record.export_line_ids.partner_id, self.partner)
        self.assertEqual(record.export_line_ids.product_id, self.product)

    def test_generate_file_uses_snapshot_lines_not_live_sale_lines(self):
        """La exportación debe salir de la tabla nueva editable."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })

        record.action_load_export_lines()
        export_line = record.export_line_ids[0]
        export_line.write({
            'product_uom_qty': 99,
            'discount': 10.0,
        })

        record.action_generate_file()

        content = base64.b64decode(record.file_data).decode('utf-8')
        didp_lines = [line for line in content.split('\r\n') if line.startswith('DIDP')]
        didd_lines = [line for line in content.split('\r\n') if line.startswith('DIDD')]

        self.assertTrue(any('00000099' in line for line in didp_lines))
        self.assertTrue(didd_lines, "Debe generarse DIDD al editar descuento en la tabla snapshot")

    def test_generate_file_uses_edited_partner_from_snapshot(self):
        """Si se cambia el cliente en la snapshot, el fichero debe usar ese cliente."""
        new_partner = self.env['res.partner'].create({
            'name': 'Cliente Editado Snapshot',
            'schweppes_customer_code': 'CUST-EDIT',
            'schweppes_route': '77',
            'schweppes_delivery_type': 'D',
            'street': 'Calle Nueva 2',
            'city': 'Sevilla',
            'zip': '41001',
            'email': 'editado@schweppes.es',
            'phone': '954000111',
        })

        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })

        record.action_load_export_lines()
        record.export_line_ids[0].write({'partner_id': new_partner.id})

        record.action_generate_file()
        content = base64.b64decode(record.file_data).decode('utf-8')

        self.assertIn('CUST-EDIT', content, "Debe usarse el cliente editado en la tabla snapshot")
        self.assertNotIn('CUST-001', content, "No debe usarse el cliente original del pedido si se cambió en snapshot")

    def test_preview_uses_edited_partner_from_snapshot(self):
        """La previsualización también debe reflejar el cliente editado en snapshot."""
        new_partner = self.env['res.partner'].create({
            'name': 'Cliente Preview Snapshot',
            'schweppes_customer_code': 'CUST-PREVIEW',
            'schweppes_route': '88',
            'schweppes_delivery_type': 'D',
        })

        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })

        record.action_load_export_lines()
        record.export_line_ids[0].write({'partner_id': new_partner.id})
        record.invalidate_recordset(['preview_file_data', 'preview_file_name'])

        preview_content = base64.b64decode(record.preview_file_data).decode('utf-8')

        self.assertIn('CUST-PREVIEW', preview_content)
        self.assertNotIn('CUST-001', preview_content)

    def test_sale_order_lines_action_uses_custom_list_view(self):
        """El smart button de líneas abre la tabla snapshot de exportación."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()
        action = record.action_view_sale_order_lines()
        custom_view = self.env.ref('diazcepeda_schweppes_iris.view_schweppes_export_line_tree')
        self.assertEqual(action['res_model'], 'schweppes.export.line')
        self.assertEqual(action['views'][0], (custom_view.id, 'list'))

    def test_send_file_requires_generated_file(self):
        """No se puede enviar si antes no se ha generado el fichero."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })
        record.action_load_export_lines()

        with self.assertRaises(UserError):
            record.action_send_file()

    def test_sent_snapshot_cannot_be_edited(self):
        """Si la exportación está enviada, la snapshot no debe poder editarse."""
        self._create_confirmed_sale_order()
        record = self.env['schweppes.iris.export'].create({
            'date_from': '2024-07-01',
            'date_to': '2024-07-31',
            'company_id': self.company.id,
        })

        record.action_load_export_lines()
        record.action_generate_file()
        record.action_send_file()

        with self.assertRaises(UserError):
            record.export_line_ids[0].write({'product_uom_qty': 321})

        self.assertEqual(record.state, 'sent')
        self.assertTrue(record.file_data)

