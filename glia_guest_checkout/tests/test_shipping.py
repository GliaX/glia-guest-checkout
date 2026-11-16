"""Packaging choice follows Glia's packing practice (Jen: max 2 stethoscopes in a #2)."""

import unittest

import frappe

from glia_guest_checkout.shipping import PACKAGING, parcel_estimate, parcel_weight_kg

STETH = "Stethoscope"            # 130 g
HOODIE = "glia-manifesto-premium-eco-hoodie-5248052-13107"  # ~530 g


def _items(*pairs):
    return [{"item_code": code, "qty": qty} for code, qty in pairs]


class TestPackaging(unittest.TestCase):
    def setUp(self):
        for code in (STETH, HOODIE):
            if not frappe.db.exists("Item", code):
                self.skipTest(f"missing item {code}")

    def test_single_stethoscope_goes_in_mailer2(self):
        est = parcel_estimate(_items((STETH, 1)))
        self.assertEqual(est["packaging"], "mailer2")
        self.assertAlmostEqual(est["content_g"], 130.0, places=1)
        self.assertAlmostEqual(est["weight_g"], 153.0, places=1)

    def test_two_stethoscopes_fit_mailer2(self):
        est = parcel_estimate(_items((STETH, 2)))
        self.assertEqual(est["packaging"], "mailer2")
        self.assertEqual(est["dimensions_cm"], [30.5, 21.6, 2.0])

    def test_three_stethoscopes_need_mailer5(self):
        est = parcel_estimate(_items((STETH, 3)))
        self.assertEqual(est["packaging"], "mailer5")

    def test_hoodie_uses_mailer5(self):
        est = parcel_estimate(_items((HOODIE, 1)))
        self.assertEqual(est["packaging"], "mailer5")

    def test_heavy_order_uses_large_box(self):
        est = parcel_estimate(_items((HOODIE, 3)))
        self.assertEqual(est["packaging"], "box_large")
        self.assertGreater(est["weight_g"], 1500)

    def test_packaging_weights_are_included(self):
        est = parcel_estimate(_items((STETH, 1)))
        self.assertAlmostEqual(est["weight_g"] - est["content_g"],
                               PACKAGING["mailer2"]["packaging_g"], places=1)

    def test_parcel_weight_kg(self):
        self.assertAlmostEqual(parcel_weight_kg(_items((STETH, 1))), 0.153, places=3)
