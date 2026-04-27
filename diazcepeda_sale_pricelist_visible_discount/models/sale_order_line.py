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

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

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
    # Validación de la regla aplicable en la tarifa base
    # ------------------------------------------------------------------

    def _xtd_base_pricelist_rule_is_discount_based(self, rule):
        """Verifica que la regla aplicable en ``base_pricelist_id`` NO sea precio fijo.

        Cuando la tarifa base (p.ej. AGUA SOLAN) tiene un precio fijo para el
        producto, el precio final es ese importe concreto, no un descuento
        porcentual sobre el precio de lista.  En ese caso no tiene sentido
        mostrar un descuento visible calculado contra ``list_price``.

        Devuelve True si la regla de la tarifa base es ``percentage`` o
        ``formula`` (es decir, basada en porcentaje), False si es ``fixed``
        o si no se puede determinar.
        """
        self.ensure_one()
        base_pricelist = rule.base_pricelist_id
        product = self.product_id
        if not base_pricelist or not product:
            return False
        try:
            qty = self.product_uom_qty or 1.0
            uom = self.product_uom
            date = self._get_order_date()
            _price, base_rule = base_pricelist._get_product_price_rule(
                product.with_context(**self._get_product_price_context()),
                qty,
                uom=uom or False,
                date=date,
            )
        except Exception:
            return False
        if not base_rule:
            return False
        return base_rule.compute_price in ("percentage", "formula")

    # ------------------------------------------------------------------
    # Obtención del precio base desde la tarifa origen
    # ------------------------------------------------------------------

    def _xtd_get_base_price_from_source_pricelist(self, rule):
        """Obtiene el ``list_price`` del producto como precio bruto real.

        El precio de lista del producto (``product.list_price``) es el precio
        antes de aplicar cualquier tarifa, independientemente de cuántos niveles
        de encadenamiento tenga la tarifa activa.  Esto permite calcular el
        descuento equivalente total cuando la cadena de tarifas incluye reglas
        de descuento en niveles intermedios (p.ej. INMACULADA → AGUA SOLAN
        que ya tiene 65 % de descuento sobre el precio de venta).

        Convierte el importe a la moneda del pedido y a la UOM de la línea.

        :returns: float con el precio base, o ``None`` si no se puede obtener.
        """
        self.ensure_one()
        product = self.product_id
        if not product:
            return None

        order = self.order_id
        uom = self.product_uom
        date = self._get_order_date()
        order_currency = order.currency_id or rule.base_pricelist_id.currency_id
        company = order.company_id or self.env.company

        try:
            # list_price está siempre en la moneda de la compañía
            price = product.list_price

            # Conversión de UOM si la línea usa una unidad diferente
            if uom and uom != product.uom_id:
                price = product.uom_id._compute_price(price, uom)

            # Conversión de moneda si el pedido usa moneda distinta
            company_currency = company.currency_id
            if company_currency and order_currency and company_currency != order_currency:
                price = company_currency._convert(
                    price, order_currency, company, date or fields.Date.today()
                )
        except Exception:
            _logger.debug(
                "diazcepeda_sale_pricelist_visible_discount: "
                "error obteniendo list_price para %s",
                product.display_name,
                exc_info=True,
            )
            return None

        if not isinstance(price, (int, float)) or price <= 0:
            return None

        return float(price)

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
