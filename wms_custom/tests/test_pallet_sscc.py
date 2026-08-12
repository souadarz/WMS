# -*- coding: utf-8 -*-
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools.barcode import check_barcode_encoding


@tagged('post_install', '-at_install')
class TestPalletSscc(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.company.gs1_company_prefix = '0123456'
        cls.company.sscc_extension_digit = '3'

        cls.stock_location = cls.env.ref('stock.stock_location_stock')
        cls.customer_location = cls.env.ref('stock.stock_location_customers')

        # `is_storable` n'est retenu que si `type == 'consu'` : la contrainte de calcul
        # (stock/models/product.py) le remet à False sinon. On l'explicite plutôt que de
        # dépendre de la valeur par défaut.
        cls.product = cls.env['product.product'].create({
            'name': 'Écrou M8 inox',
            'type': 'consu',
            'is_storable': True,
            'default_code': 'EM8-INOX',
            'barcode': '8712345678901',
        })

    # ------------------------------------------------------------------
    # Génération du SSCC
    # ------------------------------------------------------------------
    def _make_package(self, quantity=48.0):
        package = self.env['stock.quant.package'].create({})
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, quantity, package_id=package,
        )
        return package

    def test_sscc_is_18_digits_with_valid_check_digit(self):
        package = self._make_package()
        package.action_wms_assign_sscc()

        self.assertEqual(len(package.name), 18, "Un SSCC compte exactement 18 chiffres.")
        self.assertTrue(package.name.isdigit())
        self.assertTrue(
            check_barcode_encoding(package.name, 'sscc'),
            "La clé de contrôle doit être valide selon l'algorithme GS1.",
        )
        self.assertTrue(package.valid_sscc)
        self.assertTrue(
            package.name.startswith('3' + '0123456'),
            "Le SSCC doit commencer par le chiffre d'extension puis le préfixe GS1.",
        )

    def test_sscc_snapshot_is_frozen(self):
        """La quantité à l'emballage est un fait historique : elle ne bouge plus."""
        package = self._make_package(quantity=48.0)
        package.action_wms_assign_sscc()
        self.assertEqual(package.wms_packed_quantity, 48.0)
        self.assertTrue(package.wms_packed_date)

        # On prélève 3 unités.
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, -3.0, package_id=package,
        )
        package.invalidate_recordset()

        self.assertEqual(package.wms_packed_quantity, 48.0,
                         "L'étiquette papier annonce toujours 48.")
        self.assertEqual(package.wms_current_quantity, 45.0,
                         "La base, elle, sait qu'il en reste 45.")

    def test_sscc_is_never_reassigned(self):
        package = self._make_package()
        package.action_wms_assign_sscc()
        with self.assertRaises(UserError):
            package.action_wms_assign_sscc()

    def test_sscc_requires_gs1_prefix(self):
        self.company.gs1_company_prefix = False
        package = self._make_package()
        with self.assertRaises(UserError):
            package.action_wms_assign_sscc()

    def test_sscc_refused_on_empty_package(self):
        package = self.env['stock.quant.package'].create({})
        with self.assertRaises(UserError):
            package.action_wms_assign_sscc()

    def test_sscc_uniqueness_across_packages(self):
        first = self._make_package()
        second = self._make_package()
        first.action_wms_assign_sscc()
        second.action_wms_assign_sscc()
        self.assertNotEqual(first.name, second.name)

    # ------------------------------------------------------------------
    # Charge utile imprimée
    # ------------------------------------------------------------------
    def test_label_payload_carries_only_immutable_data(self):
        package = self._make_package()
        package.action_wms_assign_sscc()
        payload = package._wms_gs1_label_payload()

        self.assertTrue(payload.startswith('00' + package.name))
        self.assertIn('02' + '8712345678901'.rjust(14, '0'), payload,
                      "Le GTIN doit figurer sur une charge homogène.")
        self.assertNotIn('37', payload.replace('00' + package.name, ''),
                         "La quantité ne doit jamais être encodée : elle devient fausse.")

    def test_label_payload_skips_gtin_on_mixed_load(self):
        other = self.env['product.product'].create({
            'name': 'Vis M6', 'type': 'consu', 'is_storable': True,
            'barcode': '8712345678918',
        })
        package = self._make_package()
        self.env['stock.quant']._update_available_quantity(
            other, self.stock_location, 10.0, package_id=package,
        )
        package.invalidate_recordset()

        self.assertFalse(package.wms_is_homogeneous)
        package.action_wms_assign_sscc()
        payload = package._wms_gs1_label_payload()
        self.assertEqual(payload, '00' + package.name,
                         "Une charge mixte ne peut porter qu'un SSCC.")

    # ------------------------------------------------------------------
    # Lecture au scan
    # ------------------------------------------------------------------
    def test_resolve_bare_sscc(self):
        package = self._make_package()
        package.action_wms_assign_sscc()
        Package = self.env['stock.quant.package']
        self.assertEqual(Package._wms_resolve_scan(package.name), package)

    def test_resolve_gs1_string(self):
        package = self._make_package()
        package.action_wms_assign_sscc()
        Package = self.env['stock.quant.package']
        self.assertEqual(Package._wms_resolve_scan('00' + package.name), package)

    def test_resolve_unknown_code_returns_not_found(self):
        result = self.env['stock.quant.package'].wms_scan('999999999999999999')
        self.assertFalse(result['found'])

    def test_payload_exposes_content_and_delta(self):
        package = self._make_package(quantity=48.0)
        package.action_wms_assign_sscc()
        self.env['stock.quant']._update_available_quantity(
            self.product, self.stock_location, -3.0, package_id=package,
        )
        package.invalidate_recordset()

        payload = package.wms_scan(package.name)
        self.assertTrue(payload['found'])
        self.assertEqual(payload['quantities']['packed'], 48.0)
        self.assertEqual(payload['quantities']['current'], 45.0)
        self.assertEqual(payload['quantities']['delta'], -3.0)
        self.assertEqual(len(payload['content']), 1)
        self.assertEqual(payload['content'][0]['sku'], 'EM8-INOX')

    def test_history_survives_an_emptied_pallet(self):
        """Une palette vidée n'a plus de quant, mais garde tout son historique."""
        package = self._make_package(quantity=10.0)
        package.action_wms_assign_sscc()

        picking = self.env['stock.picking'].create({
            'picking_type_id': self.env.ref('stock.picking_type_out').id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
        })
        move = self.env['stock.move'].create({
            'name': self.product.name,
            'product_id': self.product.id,
            'product_uom_qty': 10.0,
            'product_uom': self.product.uom_id.id,
            'picking_id': picking.id,
            'location_id': self.stock_location.id,
            'location_dest_id': self.customer_location.id,
        })
        picking.action_confirm()
        picking.action_assign()
        move.move_line_ids.write({'quantity': 10.0, 'package_id': package.id})
        picking.button_validate()

        package.invalidate_recordset()
        self.assertFalse(package.quant_ids, "La palette est vidée.")

        history = package._wms_history()
        self.assertTrue(history, "L'historique doit survivre au vidage de la palette.")
        self.assertEqual(history[0]['direction'], 'out')
        self.assertEqual(history[0]['quantity'], 10.0)
