# -*- coding: utf-8 -*-
# Tests para diazcepeda_administration — Odoo 18 Community
from odoo.tests.common import TransactionCase


class TestDiazcepedaAdministration(TransactionCase):

    def test_menu_diazcepeda_config_exists(self):
        """Verifica que el menú 'Díaz Cepeda' se crea bajo facturación"""
        menu = self.env.ref(
            'diazcepeda_administration.menu_diazcepeda_config',
            raise_if_not_found=False,
        )
        self.assertTrue(menu, "El menú menu_diazcepeda_config no se ha creado")

    def test_partner_ref_field_readable(self):
        """El campo ref de res.partner es accesible sin errores"""
        partner = self.env['res.partner'].create({
            'name': 'Test Díaz Cepeda Partner',
            'ref': 'TEST001',
        })
        self.assertEqual(partner.ref, 'TEST001')

    def test_partner_tree_view_complete_name_field(self):
        """La vista lista de contactos incluye el campo complete_name (localizador del XPath)"""
        view = self.env.ref('base.view_partner_tree', raise_if_not_found=False)
        self.assertTrue(view, "base.view_partner_tree debe existir")
        self.assertIn('complete_name', view.arch)

    def test_partner_search_view_ref_field(self):
        """La vista búsqueda heredada añade el campo ref sin errores"""
        view = self.env.ref(
            'diazcepeda_administration.view_res_partner_filter_inherit_ref',
            raise_if_not_found=False,
        )
        self.assertTrue(view, "La vista de búsqueda heredada debe existir")

