# -*- coding: utf-8 -*-
# Tests para diazcepeda_pricelist_extend_view — Odoo 18 Community
from odoo.tests.common import TransactionCase


class TestPricelistExtendView(TransactionCase):

    def test_inherited_view_exists_and_loads(self):
        """La vista heredada de tarifa se crea sin errores de XPath"""
        view = self.env.ref(
            'diazcepeda_pricelist_extend_view.product_pricelist_view_inherit',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "La vista product_pricelist_view_inherit debe existir")

    def test_pricelist_item_has_required_fields(self):
        """Los campos referenciados en la vista existen en product.pricelist.item (Odoo 18)"""
        required_fields = [
            'base', 'applied_on', 'compute_price',
            'price_discount', 'percent_price', 'base_pricelist_id',
        ]
        available = self.env['product.pricelist.item'].fields_get(required_fields)
        for field_name in required_fields:
            self.assertIn(field_name, available,
                          f"El campo '{field_name}' debe existir en product.pricelist.item")

    def test_pricelist_view_arch_contains_custom_fields(self):
        """La vista heredada incluye los campos personalizados en el arch"""
        view = self.env.ref(
            'diazcepeda_pricelist_extend_view.product_pricelist_view_inherit',
            raise_if_not_found=False,
        )
        if view:
            self.assertIn('percent_price', view.arch,
                          "percent_price debe estar en el arch de la vista")
            self.assertIn('base_pricelist_id', view.arch,
                          "base_pricelist_id debe estar en el arch de la vista")

    def test_compute_price_values_available(self):
        """compute_price tiene los valores fixed/percentage/formula en Odoo 18"""
        field_def = self.env['product.pricelist.item'].fields_get(['compute_price'])
        selections = dict(field_def['compute_price'].get('selection', []))
        self.assertIn('fixed', selections)
        self.assertIn('percentage', selections)
        self.assertIn('formula', selections)

    def test_create_pricelist_with_formula_rule(self):
        """Se puede crear una tarifa con regla de tipo fórmula sin errores"""
        pricelist = self.env['product.pricelist'].create({
            'name': 'Tarifa Test Fórmula',
            'currency_id': self.env.ref('base.EUR').id,
            'item_ids': [(0, 0, {
                'compute_price': 'formula',
                'applied_on': '3_global',
                'price_discount': 10.0,
                'base': 'list_price',
            })],
        })
        self.assertEqual(pricelist.item_ids[0].compute_price, 'formula')
        self.assertAlmostEqual(pricelist.item_ids[0].price_discount, 10.0)

    def test_create_pricelist_with_percentage_rule(self):
        """Se puede crear una tarifa con regla de tipo porcentaje"""
        pricelist = self.env['product.pricelist'].create({
            'name': 'Tarifa Test Porcentaje',
            'currency_id': self.env.ref('base.EUR').id,
            'item_ids': [(0, 0, {
                'compute_price': 'percentage',
                'applied_on': '3_global',
                'percent_price': 15.0,
            })],
        })
        self.assertEqual(pricelist.item_ids[0].compute_price, 'percentage')
        self.assertAlmostEqual(pricelist.item_ids[0].percent_price, 15.0)

