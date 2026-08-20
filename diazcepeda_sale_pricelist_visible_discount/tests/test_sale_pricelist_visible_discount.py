# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)
"""Tests para diazcepeda_sale_pricelist_visible_discount.

Cubre los 7 escenarios definidos en la especificación funcional:
  1. Descuento puro 10% → price_unit=100, discount=10
  2. Descuento puro 25% → price_unit=100, discount=25
  3. Regla con recargo → sin conversión
  4. Regla con margen → sin conversión
  5. Precio base cero → sin conversión
  6. Cambio de cantidad → comportamiento estable
  7. Sin regla válida → comportamiento estándar
"""
from unittest.mock import MagicMock, patch

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSalePricelistVisibleDiscount(TransactionCase):
    """Tests de integración para descuento visible en tarifas encadenadas."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Activar la característica de descuentos visibles en líneas de venta
        # mediante res.config.settings, que gestiona correctamente el grupo
        # 'sale.group_discount_per_so_line' y sus cachés internas.
        cls.env["res.config.settings"].create(
            {"group_discount_per_so_line": True}
        ).execute()

        # Moneda
        cls.currency_eur = cls.env.ref("base.EUR")

        # Compañía y partner
        cls.company = cls.env.ref("base.main_company")
        cls.partner = cls.env["res.partner"].create({"name": "Test Partner Diazcepeda"})

        # Producto con precio de tarifa 100 €
        cls.product = cls.env["product.product"].create(
            {
                "name": "Producto Test Descuento Visible",
                "type": "consu",
                "list_price": 100.0,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "uom_po_id": cls.env.ref("uom.product_uom_unit").id,
            }
        )

        # Tarifa base: precio fijo 100 para el producto
        cls.pricelist_base = cls.env["product.pricelist"].create(
            {
                "name": "Tarifa Base Test",
                "currency_id": cls.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "0_product_variant",
                            "product_id": cls.product.id,
                            "compute_price": "fixed",
                            "fixed_price": 100.0,
                        },
                    )
                ],
            }
        )

    # ------------------------------------------------------------------
    # Helpers internos de los tests
    # ------------------------------------------------------------------

    def _make_chained_pricelist(
        self,
        discount_percent,
        surcharge=0.0,
        price_round=0.0,
        min_margin=0.0,
        max_margin=0.0,
    ):
        """Crea una tarifa derivada con regla formula sobre pricelist_base."""
        return self.env["product.pricelist"].create(
            {
                "name": f"Tarifa Derivada {discount_percent}%",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": self.pricelist_base.id,
                            "price_discount": discount_percent,
                            "price_surcharge": surcharge,
                            "price_round": price_round,
                            "price_min_margin": min_margin,
                            "price_max_margin": max_margin,
                        },
                    )
                ],
            }
        )

    def _make_sale_order(self, pricelist, qty=1.0):
        """Crea un pedido de venta con el producto y la tarifa indicados."""
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": pricelist.id,
            }
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "product_uom_qty": qty,
                "product_uom": self.env.ref("uom.product_uom_unit").id,
            }
        )
        return order, line

    # ------------------------------------------------------------------
    # Helper para comparar floats con tolerancia
    # ------------------------------------------------------------------

    def _assertAlmostEqual(self, a, b, places=2, msg=None):
        self.assertAlmostEqual(a, b, places=places, msg=msg)

    # ------------------------------------------------------------------
    # Caso 1: descuento puro 10%
    # ------------------------------------------------------------------

    def test_01_pure_discount_10_percent(self):
        """Tarifa base 100, descuento puro 10% → price_unit=100, discount=10."""
        pricelist = self._make_chained_pricelist(discount_percent=10.0)
        _order, line = self._make_sale_order(pricelist)
        # El precio final neto debe seguir siendo 90
        net_price = line.price_unit * (1.0 - line.discount / 100.0)
        self._assertAlmostEqual(line.price_unit, 100.0, msg="price_unit debe ser 100")
        self._assertAlmostEqual(line.discount, 10.0, msg="discount debe ser 10")
        self._assertAlmostEqual(net_price, 90.0, msg="precio neto debe ser 90")

    # ------------------------------------------------------------------
    # Caso 2: descuento puro 25%
    # ------------------------------------------------------------------

    def test_02_pure_discount_25_percent(self):
        """Tarifa base 100, descuento puro 25% → price_unit=100, discount=25."""
        pricelist = self._make_chained_pricelist(discount_percent=25.0)
        _order, line = self._make_sale_order(pricelist)
        net_price = line.price_unit * (1.0 - line.discount / 100.0)
        self._assertAlmostEqual(line.price_unit, 100.0, msg="price_unit debe ser 100")
        self._assertAlmostEqual(line.discount, 25.0, msg="discount debe ser 25")
        self._assertAlmostEqual(net_price, 75.0, msg="precio neto debe ser 75")

    # ------------------------------------------------------------------
    # Caso 3: regla con recargo → no debe convertir
    # ------------------------------------------------------------------

    def test_03_rule_with_surcharge_no_conversion(self):
        """Regla con recargo: el módulo NO debe convertir a descuento visible."""
        pricelist = self._make_chained_pricelist(
            discount_percent=10.0, surcharge=5.0
        )
        _order, line = self._make_sale_order(pricelist)
        # Con recargo no debería tener price_unit=100 + discount=10
        # El comportamiento debe ser el estándar de Odoo (discount=0 o mínimo)
        # Lo que validamos es que no se haya hecho la reconstrucción ingenua
        self.assertEqual(
            line.discount,
            0.0,
            msg="Con recargo no debe haber descuento visible reconstruido",
        )

    # ------------------------------------------------------------------
    # Caso 4: regla con margen mínimo → no debe convertir
    # ------------------------------------------------------------------

    def test_04_rule_with_margin_no_conversion(self):
        """Regla con margen mínimo: NO debe convertir.

        Nota: la constraint de Odoo exige price_max_margin >= price_min_margin,
        por eso se pasa max_margin=5.0 junto con min_margin=2.0.
        """
        pricelist = self._make_chained_pricelist(
            discount_percent=10.0, min_margin=2.0, max_margin=5.0
        )
        _order, line = self._make_sale_order(pricelist)
        self.assertEqual(
            line.discount,
            0.0,
            msg="Con margen mínimo no debe haber descuento visible reconstruido",
        )

    # ------------------------------------------------------------------
    # Caso 5: precio base cero → no debe convertir
    # ------------------------------------------------------------------

    def test_05_base_price_zero_no_conversion(self):
        """Si el precio base es cero, no debe actuar."""
        # Producto con precio 0
        product_zero = self.env["product.product"].create(
            {
                "name": "Producto Precio Cero",
                "type": "consu",
                "list_price": 0.0,
                "uom_id": self.env.ref("uom.product_uom_unit").id,
                "uom_po_id": self.env.ref("uom.product_uom_unit").id,
            }
        )
        pricelist_base_zero = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Base Cero",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "0_product_variant",
                            "product_id": product_zero.id,
                            "compute_price": "fixed",
                            "fixed_price": 0.0,
                        },
                    )
                ],
            }
        )
        pricelist_derived = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Derivada Sobre Cero",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": pricelist_base_zero.id,
                            "price_discount": 10.0,
                        },
                    )
                ],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": pricelist_derived.id,
            }
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product_zero.id,
                "product_uom_qty": 1.0,
                "product_uom": self.env.ref("uom.product_uom_unit").id,
            }
        )
        # No debe lanzar excepción y discount debe ser 0
        self.assertEqual(
            line.discount,
            0.0,
            msg="Con precio base cero no debe reconstruirse el descuento",
        )

    # ------------------------------------------------------------------
    # Caso 6: cambio de cantidad → comportamiento estable
    # ------------------------------------------------------------------

    def test_06_quantity_change_stable_behavior(self):
        """Al cambiar la cantidad, price_unit y discount deben seguir siendo coherentes."""
        pricelist = self._make_chained_pricelist(discount_percent=10.0)
        order, line = self._make_sale_order(pricelist, qty=1.0)

        self._assertAlmostEqual(line.price_unit, 100.0)
        self._assertAlmostEqual(line.discount, 10.0)
        net_1 = line.price_unit * (1.0 - line.discount / 100.0)

        # Cambiar la cantidad
        line.product_uom_qty = 5.0
        line._compute_price_unit()

        self._assertAlmostEqual(
            line.price_unit, 100.0, msg="price_unit debe seguir siendo 100 con qty=5"
        )
        self._assertAlmostEqual(
            line.discount, 10.0, msg="discount debe seguir siendo 10 con qty=5"
        )
        net_5 = line.price_unit * (1.0 - line.discount / 100.0)
        self._assertAlmostEqual(
            net_1, net_5, msg="El precio neto unitario no debe cambiar al cambiar qty"
        )

    # ------------------------------------------------------------------
    # Caso 7: sin regla válida → comportamiento estándar
    # ------------------------------------------------------------------

    def test_07_no_valid_rule_standard_behavior(self):
        """Si no hay regla formula+pricelist, Odoo mantiene su comportamiento."""
        # Tarifa simple de precio fijo, sin encadenamiento
        pricelist_fixed = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Fija Simple",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "0_product_variant",
                            "product_id": self.product.id,
                            "compute_price": "fixed",
                            "fixed_price": 85.0,
                        },
                    )
                ],
            }
        )
        _order, line = self._make_sale_order(pricelist_fixed)
        # Comportamiento estándar: price_unit = 85, discount = 0
        self._assertAlmostEqual(
            line.price_unit, 85.0, msg="Tarifa fija debe dar price_unit=85"
        )
        self.assertEqual(
            line.discount,
            0.0,
            msg="Tarifa fija sin encadenamiento no debe generar discount visible",
        )

    def test_07b_gross_tax_included_price_before_discount(self):
        """El helper devuelve el precio unitario con IVA antes del descuento."""
        tax = self.env["account.tax"].create(
            {
                "name": "IVA 21 Visible Discount",
                "amount": 21.0,
                "amount_type": "percent",
                "type_tax_use": "sale",
            }
        )
        self.product.taxes_id = [(6, 0, tax.ids)]
        pricelist = self._make_chained_pricelist(discount_percent=10.0)
        _order, line = self._make_sale_order(pricelist)

        self.assertAlmostEqual(
            line._get_price_unit_tax_included_before_discount(),
            121.0,
            places=2,
        )

    # ------------------------------------------------------------------
    # Caso 8: cadena real — tarifa intermedia con descuento porcentual
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Caso 9: tarifa base con precio fijo → NO debe mostrar descuento
    # ------------------------------------------------------------------

    def test_09_base_pricelist_fixed_price_no_discount(self):
        """Tarifa base con precio fijo: no se debe calcular descuento visible.

        Reproduce el caso INMACULADA → AGUA SOLAN donde AGUA SOLAN tiene
        un precio FIJO para el producto (p.ej. [265] Cocacola a 7.69€).
        El módulo NO debe comparar ese precio fijo contra list_price y
        mostrar un descuento incorrecto.
        Resultado esperado: price_unit = 7.69, discount = 0.
        """
        # Producto con list_price diferente al precio fijo en la tarifa base
        product_fixed = self.env["product.product"].create(
            {
                "name": "Producto Precio Fijo En Tarifa Base",
                "type": "consu",
                "list_price": 12.00,
                "uom_id": self.env.ref("uom.product_uom_unit").id,
                "uom_po_id": self.env.ref("uom.product_uom_unit").id,
            }
        )
        # Tarifa base (AGUA SOLAN) con precio fijo para el producto
        pricelist_base_fixed = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Base Precio Fijo",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "0_product_variant",
                            "product_id": product_fixed.id,
                            "compute_price": "fixed",
                            "fixed_price": 7.69,
                        },
                    )
                ],
            }
        )
        # Tarifa derivada (INMACULADA) que delega en la tarifa base via fórmula
        pricelist_derived = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Derivada Sobre Precio Fijo",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": pricelist_base_fixed.id,
                            "price_discount": 0.0,
                        },
                    )
                ],
            }
        )
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "pricelist_id": pricelist_derived.id,
            }
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": product_fixed.id,
                "product_uom_qty": 1.0,
                "product_uom": self.env.ref("uom.product_uom_unit").id,
            }
        )
        # Cuando la tarifa base usa precio fijo, NO debe haber descuento visible
        self.assertEqual(
            line.discount,
            0.0,
            msg="Con precio fijo en tarifa base no debe calcularse descuento visible",
        )
        self._assertAlmostEqual(
            line.price_unit,
            7.69,
            msg="price_unit debe ser el precio fijo de la tarifa base (7.69)",
        )

    def test_08_chained_pricelist_intermediate_discount(self):
        """Escenario real: tarifa A → tarifa B (65% descuento porcentual).

        Reproduce el caso INMACULADA → AGUA SOLAN:
          - Tarifa intermedia tiene regla 'percentage' con 65% de descuento.
          - Tarifa derivada tiene regla 'formula' con 0% adicional sobre
            la tarifa intermedia (passthrough).
          - Resultado clave: discount = 65% y el precio neto calculado
            por la tarifa coincide con price_unit × (1 − discount/100).

        Nota: price_unit puede incluir o no impuestos según la configuración
        de la empresa (B2B/B2C), por eso no se comprueba su valor absoluto.
        """
        # Tarifa intermedia con 65% de descuento porcentual sobre el producto
        pricelist_intermediate = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Intermedia 65%",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "percentage",
                            "percent_price": 65.0,
                        },
                    )
                ],
            }
        )
        # Tarifa derivada: 0% adicional sobre la tarifa intermedia (igual al
        # escenario INMACULADA que delega a AGUA SOLAN cuando no hay regla propia)
        pricelist_derived = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Derivada Sobre Intermedia",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": pricelist_intermediate.id,
                            "price_discount": 0.0,
                        },
                    )
                ],
            }
        )
        _order, line = self._make_sale_order(pricelist_derived)

        # El descuento visible debe ser 65% (requisito funcional principal)
        self._assertAlmostEqual(
            line.discount, 65.0,
            msg="discount debe ser 65 (descuento total de la cadena)"
        )
        # El precio neto (price_unit tras descuento) debe ser coherente con
        # el precio que devuelve la tarifa (tax-exclusive)
        pricelist_price = float(
            line.with_company(line.company_id)._get_pricelist_price()
        )
        self.assertGreater(line.price_unit, 0.0, "price_unit debe ser positivo")
        self.assertGreater(
            line.price_unit, pricelist_price,
            "price_unit debe ser mayor que el precio final de la tarifa"
        )

    def test_08b_chained_pricelist_two_level_passthrough(self):
        """Cadena con dos niveles de passthrough puro (bug ELISA → TARIFA3 →
        AGUA SOLAN).

        Estructura:
          - Tarifa terminal: regla 'percentage' con 32% de descuento.
          - Tarifa intermedia: 'formula' + 'pricelist' con 0% que delega en
            la terminal (passthrough puro).
          - Tarifa activa: 'formula' + 'pricelist' con 0% que delega en la
            intermedia (passthrough puro).

        Antes del fix, el descuento visible quedaba en 0 porque solo se
        inspeccionaba un nivel de delegación. Ahora debe resolverse la regla
        terminal recorriendo la cadena completa y mostrar discount = 32%.
        """
        pricelist_terminal = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Terminal 32%",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "percentage",
                            "percent_price": 32.0,
                        },
                    )
                ],
            }
        )
        pricelist_intermediate = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Intermedia Passthrough",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": pricelist_terminal.id,
                            "price_discount": 0.0,
                        },
                    )
                ],
            }
        )
        pricelist_active = self.env["product.pricelist"].create(
            {
                "name": "Tarifa Activa Passthrough",
                "currency_id": self.currency_eur.id,
                "item_ids": [
                    (
                        0,
                        0,
                        {
                            "applied_on": "3_global",
                            "compute_price": "formula",
                            "base": "pricelist",
                            "base_pricelist_id": pricelist_intermediate.id,
                            "price_discount": 0.0,
                        },
                    )
                ],
            }
        )
        _order, line = self._make_sale_order(pricelist_active)

        self._assertAlmostEqual(
            line.discount, 32.0,
            msg="discount debe ser 32 recorriendo dos niveles de passthrough"
        )
        pricelist_price = float(
            line.with_company(line.company_id)._get_pricelist_price()
        )
        self.assertGreater(line.price_unit, 0.0, "price_unit debe ser positivo")
        self.assertGreater(
            line.price_unit, pricelist_price,
            "price_unit debe ser mayor que el precio final de la tarifa"
        )

    # ------------------------------------------------------------------
    # Caso 10: feature de descuentos desactivada → sin inflar el precio
    # ------------------------------------------------------------------

    def test_10_discount_feature_disabled_no_price_inflation(self):
        """Si 'sale.group_discount_per_so_line' está desactivado, el módulo
        no debe sustituir price_unit por el precio base sin compensarlo
        con el descuento, porque discount se queda a 0 y el subtotal
        quedaría inflado (se cobraría de más al cliente).
        """
        self.env["res.config.settings"].create(
            {"group_discount_per_so_line": False}
        ).execute()
        self.assertFalse(
            self.env["product.pricelist.item"]._is_discount_feature_enabled(),
            msg="Precondición: feature de descuentos debe estar desactivada",
        )

        pricelist = self._make_chained_pricelist(discount_percent=10.0)
        _order, line = self._make_sale_order(pricelist)

        self.assertEqual(
            line.discount,
            0.0,
            msg="Sin la feature activa, Odoo no muestra descuento visible",
        )
        self._assertAlmostEqual(
            line.price_unit,
            90.0,
            msg=(
                "Sin la feature de descuentos, price_unit debe ser el precio "
                "neto final (90), no el precio base sin descontar (100), "
                "para no inflar el subtotal"
            ),
        )
        self._assertAlmostEqual(
            line.price_subtotal,
            90.0,
            msg="price_subtotal no debe quedar inflado por encima del precio neto",
        )

    # ------------------------------------------------------------------
    # Test de integridad: flujo interno paso a paso
    # ------------------------------------------------------------------

    def test_00_internal_flow_integrity(self):
        """Verifica cada helper intermedio de forma aislada.

        Permite detectar regressions en helpers sin que fallen los tests
        principales con mensajes crípticos.
        """
        pricelist = self._make_chained_pricelist(discount_percent=10.0)
        order, line = self._make_sale_order(pricelist)

        rule = line.pricelist_item_id
        self.assertTrue(rule, "pricelist_item_id debe estar establecido")

        self.assertTrue(
            line._xtd_can_convert_rule_to_visible_discount(rule),
            f"_xtd_can_convert debe ser True (compute_price={rule.compute_price}, "
            f"base={rule.base}, surcharge={rule.price_surcharge})",
        )

        base_price = line._xtd_get_base_price_from_source_pricelist(rule)
        self.assertIsNotNone(base_price, "base_price no debe ser None")
        self.assertAlmostEqual(base_price, 100.0, places=2)

        final_price = line.with_company(line.company_id)._get_pricelist_price()
        self.assertAlmostEqual(final_price, 90.0, places=2)

        discount_calc = line._xtd_compute_equivalent_discount(base_price, final_price)
        self.assertAlmostEqual(discount_calc, 10.0, places=2)

    # ------------------------------------------------------------------
    # Tests unitarios de los helpers estáticos
    # ------------------------------------------------------------------

    def test_unit_compute_equivalent_discount_valid(self):
        """Helper _xtd_compute_equivalent_discount: caso válido 10%."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        result = SaleOrderLine._xtd_compute_equivalent_discount(100.0, 90.0)
        self.assertAlmostEqual(result, 10.0, places=2)

    def test_unit_compute_equivalent_discount_zero_base(self):
        """Helper _xtd_compute_equivalent_discount: base cero → None."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        self.assertIsNone(SaleOrderLine._xtd_compute_equivalent_discount(0.0, 0.0))

    def test_unit_compute_equivalent_discount_no_discount(self):
        """Helper _xtd_compute_equivalent_discount: final >= base → None."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        self.assertIsNone(SaleOrderLine._xtd_compute_equivalent_discount(100.0, 100.0))
        self.assertIsNone(SaleOrderLine._xtd_compute_equivalent_discount(100.0, 110.0))

    def test_unit_can_convert_rule_valid(self):
        """Helper _xtd_can_convert_rule_to_visible_discount: regla válida."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        rule = MagicMock()
        rule.compute_price = "formula"
        rule.base = "pricelist"
        rule.base_pricelist_id = MagicMock()
        rule.price_surcharge = 0.0
        rule.price_round = 0.0
        rule.price_min_margin = 0.0
        rule.price_max_margin = 0.0

        self.assertTrue(SaleOrderLine._xtd_can_convert_rule_to_visible_discount(rule))

    def test_unit_can_convert_rule_with_surcharge(self):
        """Helper _xtd_can_convert_rule_to_visible_discount: recargo → False."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        rule = MagicMock()
        rule.compute_price = "formula"
        rule.base = "pricelist"
        rule.base_pricelist_id = MagicMock()
        rule.price_surcharge = 5.0
        rule.price_round = 0.0
        rule.price_min_margin = 0.0
        rule.price_max_margin = 0.0

        self.assertFalse(SaleOrderLine._xtd_can_convert_rule_to_visible_discount(rule))

    def test_unit_can_convert_rule_not_formula(self):
        """Helper _xtd_can_convert_rule_to_visible_discount: no formula → False."""
        from odoo.addons.diazcepeda_sale_pricelist_visible_discount.models.sale_order_line import (
            SaleOrderLine,
        )

        rule = MagicMock()
        rule.compute_price = "fixed"
        rule.base = "pricelist"
        rule.base_pricelist_id = MagicMock()
        rule.price_surcharge = 0.0
        rule.price_round = 0.0
        rule.price_min_margin = 0.0
        rule.price_max_margin = 0.0

        self.assertFalse(SaleOrderLine._xtd_can_convert_rule_to_visible_discount(rule))
