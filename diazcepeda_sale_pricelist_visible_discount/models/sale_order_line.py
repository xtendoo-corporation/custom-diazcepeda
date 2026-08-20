# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0)
"""Extensión de sale.order.line para descuento visible en tarifas encadenadas.

Cuando una tarifa aplica una regla de tipo ``formula`` basada en otra tarifa
(``base = 'pricelist'``), Odoo absorbe el descuento dentro de ``price_unit``
y deja ``discount = 0``.

Este módulo actúa en los dos puntos de cálculo de Odoo 18:

- ``_get_display_price_ignore_combo``:  devuelve el precio base de la tarifa
  origen para que ``price_unit`` refleje el precio sin descuento.
- ``_compute_discount``:  calcula y persiste el porcentaje equivalente.

El precio final neto (price_unit × (1 − discount/100)) no cambia.
"""
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _get_price_unit_tax_included_before_discount(self):
        """Devuelve el precio unitario bruto con impuestos antes del descuento."""
        self.ensure_one()
        taxes_res = self.tax_id.compute_all(
            self.price_unit,
            currency=self.currency_id,
            quantity=1.0,
            product=self.product_id,
            partner=self.order_id.partner_id,
        )
        return taxes_res["total_included"]

    # ------------------------------------------------------------------
    # Hook 1: precio base visible (price_unit)
    # ------------------------------------------------------------------

    def _get_display_price_ignore_combo(self):
        """Devuelve el precio de la tarifa origen cuando la regla es segura.

        Para reglas formula+pricelist puras sustituye el precio final calculado
        por Odoo por el precio bruto de la tarifa base, de modo que
        ``price_unit`` refleje el precio antes del descuento.

        En cualquier otro caso delega en el comportamiento estándar.
        """
        result = super()._get_display_price_ignore_combo()

        discount_enabled = (
            self.env["product.pricelist.item"]._is_discount_feature_enabled()
        )
        if not discount_enabled:
            return result

        rule = self.pricelist_item_id
        if not self._xtd_can_convert_rule_to_visible_discount(rule):
            return result

        if not self._xtd_base_pricelist_rule_is_discount_based(rule):
            return result

        base_price = self._xtd_get_base_price_from_source_pricelist(rule)
        if base_price is None or base_price <= 0:
            return result

        # Solo actuamos si hay descuento real (final < base)
        if result >= base_price:
            return result

        return base_price

    # ------------------------------------------------------------------
    # Hook 2: descuento visible (discount)
    # ------------------------------------------------------------------

    @api.depends("product_id", "product_uom", "product_uom_qty")
    def _compute_discount(self):
        """Extiende el cálculo estándar para el caso formula+pricelist.

        Después de que el super() haya actuado, añade el descuento equivalente
        para líneas con una regla de tarifa encadenada pura.

        El super() solo activa descuento visible para reglas ``percentage``;
        para ``formula`` deja discount=0. Aquí corregimos ese caso concreto.
        """
        super()._compute_discount()

        discount_enabled = (
            self.env["product.pricelist.item"]._is_discount_feature_enabled()
        )
        if not discount_enabled:
            return

        for line in self:
            if not line.product_id or line.display_type:
                continue
            if not line.order_id.pricelist_id:
                continue
            if line.combo_item_id:
                continue

            rule = line.pricelist_item_id
            if not line._xtd_can_convert_rule_to_visible_discount(rule):
                continue

            if not line._xtd_base_pricelist_rule_is_discount_based(rule):
                continue

            base_price = line._xtd_get_base_price_from_source_pricelist(rule)
            if base_price is None:
                continue

            final_price = (
                line.with_company(line.company_id)._get_pricelist_price()
            )
            discount = line._xtd_compute_equivalent_discount(base_price, final_price)
            if discount is not None:
                line.discount = discount

    # ------------------------------------------------------------------
    # Validación de seguridad de la regla
    # ------------------------------------------------------------------

    @staticmethod
    def _xtd_can_convert_rule_to_visible_discount(rule):
        """Devuelve True solo si la regla es un descuento porcentual puro.

        Condiciones que deben cumplirse todas:
          - compute_price = 'formula'
          - base = 'pricelist'
          - base_pricelist_id informado
          - price_surcharge = 0
          - price_round = 0
          - price_min_margin = 0
          - price_max_margin = 0
        """
        if not rule:
            return False
        return (
            rule.compute_price == "formula"
            and rule.base == "pricelist"
            and rule.base_pricelist_id
            and not rule.price_surcharge
            and not rule.price_round
            and not rule.price_min_margin
            and not rule.price_max_margin
        )

    # ------------------------------------------------------------------
    # Resolución de la regla terminal en cadenas de tarifas encadenadas
    # ------------------------------------------------------------------

    def _xtd_resolve_terminal_rule(self, pricelist, max_depth=10):
        """Sigue la cadena de reglas 'formula + pricelist' puras (passthrough,
        price_discount=0 y sin surcharge/round/margins) hasta encontrar la
        regla real que fija el precio (percentage, fixed, o formula con
        descuento/margen propio).

        Soluciona el caso de tarifas con 2+ niveles de delegación (p.ej.
        ELISA -> TARIFA3 -> AGUA SOLAN Y FORMULAS), donde el nivel intermedio
        es también un passthrough puro y no debe confundirse con la regla
        terminal.
        """
        self.ensure_one()
        product = self.product_id
        if not pricelist or not product:
            return None, None
        seen = set()
        current_pricelist = pricelist
        for _ in range(max_depth):
            if current_pricelist.id in seen:
                return None, None
            seen.add(current_pricelist.id)
            try:
                qty = self.product_uom_qty or 1.0
                uom = self.product_uom
                date = self._get_order_date()
                _price, rule_id = current_pricelist._get_product_price_rule(
                    product.with_context(**self._get_product_price_context()),
                    qty,
                    uom=uom or False,
                    date=date,
                )
            except Exception:
                return None, None
            if not rule_id:
                return None, None
            rule = (
                self.env["product.pricelist.item"].browse(rule_id)
                if isinstance(rule_id, int)
                else rule_id
            )
            is_pure_passthrough = (
                rule.compute_price == "formula"
                and rule.base == "pricelist"
                and rule.base_pricelist_id
                and not rule.price_discount
                and not rule.price_surcharge
                and not rule.price_round
                and not rule.price_min_margin
                and not rule.price_max_margin
            )
            if is_pure_passthrough:
                current_pricelist = rule.base_pricelist_id
                continue
            return current_pricelist, rule
        return None, None

    # ------------------------------------------------------------------
    # Validación de la regla aplicable en la tarifa base
    # ------------------------------------------------------------------

    def _xtd_base_pricelist_rule_is_discount_based(self, rule):
        """Verifica que haya un descuento porcentual real que mostrar.

        Distingue dos situaciones:

        1. La regla ``formula`` tiene descuento propio (``price_discount > 0``):
           la tarifa activa aplica un porcentaje adicional sobre la tarifa base.
           En este caso siempre hay descuento visible independientemente del
           tipo de regla en la tarifa base.

        2. La regla es un **passthrough** (``price_discount = 0``): la tarifa
           delega completamente en la tarifa base (p.ej. INMACULADA → AGUA SOLAN).
           Solo se muestra descuento si la regla aplicable en la tarifa base
           es de tipo ``percentage`` o ``formula``.  Si la tarifa base tiene un
           precio fijo (``fixed``) para el producto, ese es el precio definitivo
           y no procede calcular ningún descuento visible contra ``list_price``.

        :returns: True si corresponde mostrar un descuento visible, False si no.
        """
        self.ensure_one()

        # Caso 1: la fórmula tiene descuento propio → siempre actuar
        if rule.price_discount:
            return True

        # Caso 2: passthrough → recorrer la cadena hasta la regla terminal real
        base_pricelist = rule.base_pricelist_id
        product = self.product_id
        if not base_pricelist or not product:
            return False
        _pl, base_rule = self._xtd_resolve_terminal_rule(base_pricelist)
        if not base_rule:
            return False
        return base_rule.compute_price in ("percentage", "formula")

    # ------------------------------------------------------------------
    # Obtención del precio base desde la tarifa origen
    # ------------------------------------------------------------------

    def _xtd_get_base_price_from_source_pricelist(self, rule):
        """Obtiene el precio base (antes de descuento) según el tipo de regla.

        Distingue dos situaciones para evitar depender de ``product.list_price``,
        cuyo valor puede verse afectado por impuestos o módulos personalizados:

        **Caso 1 — la fórmula tiene descuento propio** (``price_discount > 0``):
        Se obtiene el precio desde ``base_pricelist_id`` directamente
        (p.ej. precio fijo de 100 €), y el módulo calcula el descuento
        equivalente al ``price_discount`` configurado.

        **Caso 2 — passthrough** (``price_discount = 0``):
        La tarifa delega completamente en la tarifa base (p.ej. INMACULADA →
        AGUA SOLAN).  La tarifa base tiene una regla ``percentage`` con un
        porcentaje conocido.  Se reconstruye el precio anterior al descuento
        usando la fórmula inversa:
        ``base = final_price / (1 − percent / 100)``

        :returns: float con el precio base, o ``None`` si no se puede obtener.
        """
        self.ensure_one()
        product = self.product_id
        if not product:
            return None

        if rule.price_discount:
            # Caso 1: la fórmula tiene su propio descuento sobre la tarifa base.
            # Obtenemos el precio desde la tarifa base (p.ej. precio fijo).
            return self._xtd_get_price_from_base_pricelist(rule)

        # Caso 2: passthrough — el descuento está en la regla de la tarifa base.
        # Back-calculamos el precio anterior al descuento usando el percent_price.
        return self._xtd_get_base_price_via_percent_inversion(rule)

    def _xtd_get_price_from_base_pricelist(self, rule):
        """Devuelve el precio de ``base_pricelist_id`` para el producto.

        Usado cuando la fórmula tiene su propio ``price_discount``.

        :returns: float o ``None``.
        """
        self.ensure_one()
        base_pricelist = rule.base_pricelist_id
        product = self.product_id
        order = self.order_id
        qty = self.product_uom_qty or 1.0
        uom = self.product_uom
        date = self._get_order_date()
        currency = order.currency_id or base_pricelist.currency_id
        try:
            price = base_pricelist._get_product_price(
                product.with_context(**self._get_product_price_context()),
                qty,
                uom=uom or False,
                date=date,
                currency=currency,
            )
        except Exception:
            _logger.debug(
                "diazcepeda_sale_pricelist_visible_discount: "
                "error obteniendo precio de tarifa base para %s",
                product.display_name,
                exc_info=True,
            )
            return None
        if not isinstance(price, (int, float)) or price <= 0:
            return None
        return float(price)

    def _xtd_get_base_price_via_percent_inversion(self, rule):
        """Reconstruye el precio base desde el porcentaje de la regla base.

        Cuando la tarifa base tiene una regla ``percentage`` con ``percent_price``
        conocido, el precio antes del descuento se calcula como::

            base = final_price / (1 − percent_price / 100)

        :returns: float o ``None``.
        """
        self.ensure_one()
        base_pricelist = rule.base_pricelist_id
        product = self.product_id
        if not base_pricelist or not product:
            return None
        _pl, base_rule = self._xtd_resolve_terminal_rule(base_pricelist)
        if not base_rule or base_rule.compute_price != "percentage":
            return None
        percent = base_rule.percent_price
        if percent <= 0 or percent >= 100:
            return None
        try:
            final_price = float(
                self.with_company(self.company_id)._get_pricelist_price()
            )
        except Exception:
            return None
        if final_price <= 0:
            return None
        return round(final_price / (1.0 - percent / 100.0), 6)

    # ------------------------------------------------------------------
    # Cálculo del descuento equivalente
    # ------------------------------------------------------------------

    @staticmethod
    def _xtd_compute_equivalent_discount(base_price, final_price):
        """Calcula el descuento porcentual equivalente.

        :param base_price: precio bruto desde la tarifa origen.
        :param final_price: precio final calculado por Odoo.
        :returns: float con el descuento en %, redondeado a 2 decimales,
                  o ``None`` si la situación no es válida para actuar.
        """
        if not base_price or base_price <= 0:
            return None
        if final_price < 0:
            return None
        if final_price >= base_price:
            return None

        return round(100.0 * (1.0 - final_price / base_price), 2)
