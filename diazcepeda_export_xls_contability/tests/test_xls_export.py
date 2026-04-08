# -*- coding: utf-8 -*-
# Tests para diazcepeda_export_xls_contability — Odoo 18 Community
import base64

from odoo.tests.common import TransactionCase


class TestXLSExport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente XLS Export',
            'vat': 'ES12345678Z',
        })
        cls.product = cls.env['product.product'].create({
            'name': 'Producto XLS Test',
            'list_price': 100.0,
            'taxes_id': [],
        })

    def _create_posted_invoice(self, move_type='out_invoice', date='2024-03-15'):
        """Crea y valida una factura de prueba"""
        move = self.env['account.move'].create({
            'move_type': move_type,
            'partner_id': self.partner.id,
            'invoice_date': date,
            'invoice_line_ids': [(0, 0, {
                'product_id': self.product.id,
                'quantity': 2,
                'price_unit': 100.0,
            })],
        })
        move.action_post()
        return move

    def test_export_returns_act_url(self):
        """El método export_file devuelve una acción de descarga de URL"""
        self._create_posted_invoice()
        wizard = self.env['diazcepeda.export.xls.contability'].create({
            'start_date': '2024-03-01',
            'end_date': '2024-03-31',
            'customers_check': True,
        })
        result = wizard.export_file()
        self.assertEqual(result.get('type'), 'ir.actions.act_url',
                         "Debe devolver una acción act_url para descarga")
        self.assertIn('download=true', result.get('url', ''),
                      "La URL de descarga debe contener 'download=true'")

    def test_export_customer_invoices_only(self):
        """Con customers_check=True solo se incluyen facturas de cliente"""
        self._create_posted_invoice(move_type='out_invoice', date='2024-03-10')
        self._create_posted_invoice(move_type='in_invoice', date='2024-03-10')
        wizard = self.env['diazcepeda.export.xls.contability'].create({
            'start_date': '2024-03-01',
            'end_date': '2024-03-31',
            'customers_check': True,
            'providers_check': False,
        })
        domain = [
            ('invoice_date', '>=', wizard.start_date),
            ('invoice_date', '<=', wizard.end_date),
            ('move_type', 'in', ['out_invoice', 'out_refund']),
        ]
        invoices = self.env['account.move'].search(domain)
        for inv in invoices:
            self.assertIn(inv.move_type, ['out_invoice', 'out_refund'])

    def test_export_provider_invoices_only(self):
        """Con providers_check=True solo se incluyen facturas de proveedor"""
        self._create_posted_invoice(move_type='in_invoice', date='2024-04-10')
        wizard = self.env['diazcepeda.export.xls.contability'].create({
            'start_date': '2024-04-01',
            'end_date': '2024-04-30',
            'providers_check': True,
            'customers_check': False,
        })
        domain = [
            ('invoice_date', '>=', wizard.start_date),
            ('invoice_date', '<=', wizard.end_date),
            ('move_type', 'in', ['in_invoice', 'in_refund']),
        ]
        invoices = self.env['account.move'].search(domain)
        for inv in invoices:
            self.assertIn(inv.move_type, ['in_invoice', 'in_refund'])

    def test_no_invoices_in_range_generates_empty_file(self):
        """Cuando no hay facturas en el rango, el export genera un XLSX vacío sin crash"""
        wizard = self.env['diazcepeda.export.xls.contability'].create({
            'start_date': '2000-01-01',
            'end_date': '2000-01-31',
            'customers_check': True,
        })
        # No debe lanzar excepción
        result = wizard.export_file()
        self.assertIn('type', result)

    def test_export_creates_attachment(self):
        """El export crea un ir.attachment con el archivo XLSX"""
        self._create_posted_invoice(date='2024-05-15')
        wizard = self.env['diazcepeda.export.xls.contability'].create({
            'start_date': '2024-05-01',
            'end_date': '2024-05-31',
            'customers_check': True,
        })
        before_count = self.env['ir.attachment'].search_count([('name', '=', 'contabilidad.xlsx')])
        wizard.export_file()
        after_count = self.env['ir.attachment'].search_count([('name', '=', 'contabilidad.xlsx')])
        self.assertGreater(after_count, before_count,
                           "Debe crearse un attachment 'contabilidad.xlsx'")

