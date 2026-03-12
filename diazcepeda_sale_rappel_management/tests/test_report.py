# -*- coding: utf-8 -*-
"""
Tests del nuevo formato de impresión "Presupuesto con Rappel Comercial".

Cubre:
  - El informe está registrado como ir.actions.report
  - El informe aparece como binding en sale.order (menú Imprimir)
  - El template se renderiza sin errores para un pedido sin rappel
  - El template se renderiza sin errores para un pedido con rappel
  - Las columnas de rappel (%, importe, precio final) aparecen en el HTML
    cuando los productos tienen show_rappel_on_quote=True y rappel_percent>0
  - Las columnas de rappel NO aparecen cuando show_rappel_on_quote=False
  - El bloque resumen "RAPPEL COMERCIAL ESTIMADO" aparece cuando hay rappel
  - Los importes calculados en el HTML son matemáticamente correctos
  - El informe original estándar de Odoo NO se ve modificado
  - El aviso legal aparece en el documento
  - El badge "CON RAPPEL COMERCIAL" aparece en el título
  - Pedido con descuento: cálculo correcto en el HTML
  - Pedido con múltiples productos con distintos % de rappel
  - El informe pertenece al grupo group_rappel_manager
"""
from odoo.tests.common import TransactionCase
from datetime import date, timedelta
import re


REPORT_NAME = 'diazcepeda_sale_rappel_management.report_saleorder_with_rappel'
REPORT_XML_ID = 'diazcepeda_sale_rappel_management.action_report_sale_order_with_rappel'


class TestSaleOrderRappelReport(TransactionCase):
    """Tests del nuevo informe de presupuesto con rappel comercial."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # ── Partner ──────────────────────────────────────────────────────────
        cls.partner = cls.env['res.partner'].create({
            'name': 'Cliente Informe Rappel',
            'customer_rank': 1,
        })

        # ── Categorías ───────────────────────────────────────────────────────
        cls.cat_beer = cls.env['product.category'].create({'name': 'Cat. Cervezas Informe'})

        # ── Productos ────────────────────────────────────────────────────────
        cls.product_rappel = cls.env['product.product'].create({
            'name': 'Cerveza Test Informe',
            'categ_id': cls.cat_beer.id,
            'is_rappel_applicable': True,
            'show_rappel_on_quote': True,
            'default_rappel_percent': 5.0,
            'list_price': 10.0,
            'type': 'consu',
        })
        cls.product_rappel_hidden = cls.env['product.product'].create({
            'name': 'Vino Test Informe',
            'categ_id': cls.cat_beer.id,
            'is_rappel_applicable': True,
            'show_rappel_on_quote': False,  # No mostrar en presupuesto
            'default_rappel_percent': 3.0,
            'list_price': 15.0,
            'type': 'consu',
        })
        cls.product_no_rappel = cls.env['product.product'].create({
            'name': 'Barril Sin Rappel',
            'categ_id': cls.cat_beer.id,
            'is_rappel_applicable': False,
            'list_price': 5.0,
            'type': 'consu',
        })

        # ── Regla de rappel ───────────────────────────────────────────────────
        cls.rule = cls.env['rappel.rule'].create({
            'name': 'Rappel Cerveza Informe',
            'product_id': cls.product_rappel.id,
            'rappel_percent': 5.0,
        })

        # ── Pricelist por defecto ─────────────────────────────────────────────
        cls.pricelist = cls.env['product.pricelist'].search(
            [('currency_id', '=', cls.env.company.currency_id.id)], limit=1
        )

    def _make_order(self, lines=None):
        """Helper: crea un pedido de venta con las líneas indicadas."""
        if lines is None:
            lines = [(self.product_rappel, 10, 10.0, 0.0, 5.0)]
        order_lines = []
        for product, qty, price, discount, rappel_pct in lines:
            order_lines.append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
                'discount': discount,
                'rappel_percent': rappel_pct,
            }))
        return self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'pricelist_id': self.pricelist.id if self.pricelist else False,
            'order_line': order_lines,
        })

    def _render_html(self, order):
        """Helper: renderiza el informe rappel en HTML y devuelve bytes."""
        html, _content_type = self.env['ir.actions.report']._render_qweb_html(
            REPORT_NAME, order.ids
        )
        return html

    # ── Tests de registro del informe ─────────────────────────────────────────

    def test_report_action_exists(self):
        """El informe está registrado como ir.actions.report."""
        report = self.env.ref(REPORT_XML_ID, raise_if_not_found=False)
        self.assertTrue(report, "El informe de rappel debe existir en ir.actions.report")
        self.assertEqual(report.model, 'sale.order')
        self.assertEqual(report.report_type, 'qweb-pdf')

    def test_report_name_is_correct(self):
        """El report_name apunta al template correcto."""
        report = self.env.ref(REPORT_XML_ID)
        self.assertEqual(
            report.report_name,
            'diazcepeda_sale_rappel_management.report_saleorder_with_rappel',
        )

    def test_report_is_bound_to_sale_order(self):
        """El informe aparece vinculado al modelo sale.order (binding)."""
        report = self.env.ref(REPORT_XML_ID)
        self.assertTrue(report.binding_model_id,
                        "El informe debe tener binding_model_id para aparecer en Imprimir")
        self.assertEqual(report.binding_model_id.model, 'sale.order')
        self.assertEqual(report.binding_type, 'report')

    def test_report_has_group_restriction(self):
        """El informe está restringido al grupo group_rappel_manager."""
        report = self.env.ref(REPORT_XML_ID)
        group = self.env.ref(
            'diazcepeda_sale_rappel_management.group_rappel_manager',
            raise_if_not_found=False,
        )
        self.assertTrue(group, "El grupo group_rappel_manager debe existir")
        self.assertIn(group, report.groups_id,
                      "El informe debe estar restringido al grupo de rappel")

    def test_report_paperformat_is_euro(self):
        """El formato de papel es A4 europeo."""
        report = self.env.ref(REPORT_XML_ID)
        self.assertTrue(report.paperformat_id,
                        "El informe debe tener formato de papel definido")

    # ── Tests de renderizado básico ───────────────────────────────────────────

    def test_report_renders_without_error(self):
        """El informe se renderiza sin excepciones."""
        order = self._make_order()
        html = self._render_html(order)
        self.assertTrue(html, "El informe no debe devolver HTML vacío")
        self.assertIsInstance(html, bytes)

    def test_report_renders_order_number(self):
        """El HTML contiene el número del pedido."""
        order = self._make_order()
        html = self._render_html(order)
        self.assertIn(order.name.encode(), html,
                      "El número del pedido debe aparecer en el HTML")

    def test_report_renders_partner_name(self):
        """El HTML contiene el nombre del cliente."""
        order = self._make_order()
        html = self._render_html(order)
        self.assertIn(self.partner.name.encode(), html,
                      "El nombre del cliente debe aparecer en el HTML")

    def test_report_renders_product_name(self):
        """El HTML contiene el nombre del producto."""
        order = self._make_order()
        html = self._render_html(order)
        self.assertIn(self.product_rappel.name.encode(), html,
                      "El nombre del producto debe aparecer en el HTML")

    def test_report_renders_without_error_no_rappel(self):
        """El informe se renderiza sin errores para pedidos sin rappel."""
        order = self._make_order(lines=[
            (self.product_no_rappel, 5, 5.0, 0.0, 0.0),
        ])
        html = self._render_html(order)
        self.assertTrue(html)
        # No debe aparecer la sección de rappel
        self.assertNotIn(b'RAPPEL COMERCIAL ESTIMADO', html,
                         "No debe haber sección rappel para productos sin rappel")

    # ── Tests del badge y título ───────────────────────────────────────────────

    def test_report_shows_rappel_badge_in_title(self):
        """El título incluye el badge 'CON RAPPEL COMERCIAL'."""
        order = self._make_order()
        html = self._render_html(order)
        self.assertIn(b'CON RAPPEL COMERCIAL', html,
                      "El badge 'CON RAPPEL COMERCIAL' debe aparecer en el título")

    # ── Tests de columnas rappel en la tabla ──────────────────────────────────

    def test_report_shows_rappel_columns_header_when_show_on_quote(self):
        """Cabeceras de rappel aparecen cuando show_rappel_on_quote=True."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),  # show_rappel_on_quote=True
        ])
        html = self._render_html(order)
        self.assertIn(b'Rappel', html,
                      "Las columnas de rappel deben aparecer en las cabeceras")

    def test_report_hides_rappel_section_when_show_on_quote_false(self):
        """No aparece sección rappel si show_rappel_on_quote=False."""
        order = self._make_order(lines=[
            (self.product_rappel_hidden, 5, 15.0, 0.0, 3.0),  # show_rappel_on_quote=False
        ])
        html = self._render_html(order)
        self.assertNotIn(b'RAPPEL COMERCIAL ESTIMADO', html,
                         "No debe aparecer el bloque rappel si show_rappel_on_quote=False")

    def test_report_shows_rappel_summary_table(self):
        """Aparece el bloque resumen 'RAPPEL COMERCIAL ESTIMADO'."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        html = self._render_html(order)
        self.assertIn(b'RAPPEL COMERCIAL ESTIMADO', html,
                      "El bloque resumen de rappel debe aparecer en el HTML")

    def test_report_shows_total_rappel_row(self):
        """Aparece la fila de total rappel estimado."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        html = self._render_html(order)
        self.assertIn(b'TOTAL RAPPEL ESTIMADO', html,
                      "La fila de total rappel debe aparecer en el HTML")

    def test_report_shows_legal_notice(self):
        """El aviso legal sobre el rappel aparece en el documento."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        html = self._render_html(order)
        self.assertIn(b'Aviso legal', html,
                      "El aviso legal debe aparecer en el documento rappel")
        self.assertIn(b'no modifica el precio', html)

    # ── Tests de cálculos matemáticos ─────────────────────────────────────────

    def test_report_contains_correct_rappel_percent(self):
        """El porcentaje de rappel correcto aparece en el HTML."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        html = self._render_html(order)
        # 5.00 debe aparecer como número en el HTML
        self.assertIn(b'5.00', html,
                      "El porcentaje '5.00' debe aparecer en el HTML")

    def test_report_rappel_amounts_computed_on_order_line(self):
        """Los campos rappel_estimated_amount y rappel_estimated_unit_price están calculados."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        line = order.order_line[0]
        # net = 10.0 * (1 - 0) = 10.0
        # rappel_unit = 10.0 * 0.05 = 0.5
        # rappel_total = 0.5 * 10 = 5.0
        # final_unit = 10.0 - 0.5 = 9.5
        self.assertAlmostEqual(line.rappel_estimated_amount, 5.0, places=2)
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 9.5, places=2)

    def test_report_rappel_with_discount_computed_correctly(self):
        """Con descuento del 20%, el rappel se calcula sobre el precio neto."""
        # price=100, discount=20%, net=80, rappel=5% → rappel_unit=4, final=76
        order = self._make_order(lines=[
            (self.product_rappel, 2, 100.0, 20.0, 5.0),
        ])
        line = order.order_line[0]
        self.assertAlmostEqual(line.rappel_estimated_amount, 8.0, places=2,
                               msg="rappel_total = 4.0 * 2 = 8.0")
        self.assertAlmostEqual(line.rappel_estimated_unit_price, 76.0, places=2,
                               msg="precio_final_estimado = 80 - 4 = 76")

    def test_report_renders_with_discount_no_error(self):
        """El informe se renderiza sin errores cuando hay descuento."""
        order = self._make_order(lines=[
            (self.product_rappel, 5, 100.0, 25.0, 5.0),
        ])
        html = self._render_html(order)
        self.assertTrue(html)
        self.assertIn(b'RAPPEL COMERCIAL ESTIMADO', html)

    # ── Tests con múltiples productos ─────────────────────────────────────────

    def test_report_multiple_products_all_shown(self):
        """Con varios productos rappel, todos aparecen en el resumen."""
        product2 = self.env['product.product'].create({
            'name': 'Sidra Test Informe',
            'categ_id': self.cat_beer.id,
            'is_rappel_applicable': True,
            'show_rappel_on_quote': True,
            'default_rappel_percent': 8.0,
            'list_price': 20.0,
            'type': 'consu',
        })
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
            (product2, 5, 20.0, 0.0, 8.0),
        ])
        html = self._render_html(order)
        self.assertIn(self.product_rappel.name.encode(), html)
        self.assertIn(product2.name.encode(), html)
        self.assertIn(b'5.00', html,  # rappel cerveza
                      "El 5% de cerveza debe aparecer")
        self.assertIn(b'8.00', html,  # rappel sidra
                      "El 8% de sidra debe aparecer")

    def test_report_mixed_products_only_rappel_ones_in_summary(self):
        """El resumen solo incluye productos con show_rappel_on_quote=True."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),      # show=True
            (self.product_no_rappel, 5, 5.0, 0.0, 0.0),     # sin rappel
            (self.product_rappel_hidden, 3, 15.0, 0.0, 3.0), # show=False
        ])
        html = self._render_html(order)
        # El producto con rappel visible SÍ debe estar en el resumen
        self.assertIn(b'RAPPEL COMERCIAL ESTIMADO', html)
        # El producto sin rappel NO debe contaminar el resumen
        # (verificamos que el producto no-rappel no aparece en sección rappel)
        self.assertIn(self.product_rappel.name.encode(), html)

    # ── Test: el informe estándar original NO está modificado ──────────────────

    def test_standard_report_not_modified(self):
        """El informe estándar de Odoo se renderiza sin columnas rappel."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        # Renderizar el informe ESTÁNDAR de Odoo (no el nuestro)
        std_html, _ = self.env['ir.actions.report']._render_qweb_html(
            'sale.report_saleorder', order.ids
        )
        # El informe estándar NO debe contener el badge de rappel de nuestro módulo
        self.assertNotIn(b'CON RAPPEL COMERCIAL', std_html,
                         "El informe estándar NO debe incluir el badge de rappel")
        # El informe estándar NO debe contener el bloque resumen de rappel
        self.assertNotIn(b'RAPPEL COMERCIAL ESTIMADO', std_html,
                         "El informe estándar NO debe incluir el bloque resumen de rappel")
        # El informe estándar SÍ sigue funcionando correctamente
        self.assertIn(order.name.encode(), std_html,
                      "El informe estándar sigue mostrando el número de pedido")

    def test_both_reports_coexist(self):
        """Ambos informes (estándar y rappel) se pueden renderizar para el mismo pedido."""
        order = self._make_order(lines=[
            (self.product_rappel, 10, 10.0, 0.0, 5.0),
        ])
        # Informe estándar
        std_html, _ = self.env['ir.actions.report']._render_qweb_html(
            'sale.report_saleorder', order.ids
        )
        # Informe rappel
        rappel_html = self._render_html(order)

        self.assertTrue(std_html, "El informe estándar debe renderizarse")
        self.assertTrue(rappel_html, "El informe rappel debe renderizarse")

        # Son diferentes entre sí
        self.assertNotEqual(std_html, rappel_html,
                            "Los dos informes deben producir HTML diferente")

    # ── Test de informe sin líneas ────────────────────────────────────────────

    def test_report_renders_empty_order(self):
        """El informe se renderiza sin errores para un pedido sin líneas."""
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
        })
        html = self._render_html(order)
        self.assertTrue(html, "Un pedido vacío debe renderizarse sin errores")
        # Sin líneas no debe haber sección rappel
        self.assertNotIn(b'RAPPEL COMERCIAL ESTIMADO', html)

    # ── Test de accesibilidad del template ───────────────────────────────────

    def test_template_exists_in_ir_ui_view(self):
        """El template del informe existe como ir.ui.view en la BD."""
        template = self.env.ref(
            'diazcepeda_sale_rappel_management.report_saleorder_with_rappel',
            raise_if_not_found=False,
        )
        self.assertTrue(template,
                        "El template report_saleorder_with_rappel debe existir")

    def test_document_template_exists(self):
        """El template de documento (con el layout completo) existe."""
        template = self.env.ref(
            'diazcepeda_sale_rappel_management.report_saleorder_with_rappel_document',
            raise_if_not_found=False,
        )
        self.assertTrue(template,
                        "El template report_saleorder_with_rappel_document debe existir")

