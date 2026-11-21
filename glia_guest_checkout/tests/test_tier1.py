"""Guards for the tier-1 fixes: gifts without addresses, custom amounts, stock."""

import inspect
import unittest

import frappe

from glia_guest_checkout import api, cart, stock


class TestGuestCheckoutSignature(unittest.TestCase):
	def test_address_fields_are_optional(self):
		params = inspect.signature(api.guest_checkout).parameters
		for name in ("address_line1", "city", "country"):
			self.assertIn(name, params)
			self.assertIsNone(params[name].default, f"{name} must default to None")


class TestCustomAmount(unittest.TestCase):
	def test_base_variant_exists_for_donation_appeal(self):
		self.assertTrue(frappe.db.exists("Item", "donate-glia-project"))
		self.assertTrue(cart._base_variant("donate-glia-project"))

	def test_add_item_accepts_an_amount_override(self):
		import inspect

		self.assertIn("amount", inspect.signature(cart.add_item).parameters)


class TestStock(unittest.TestCase):
	def test_unseeded_stock_does_not_block_sales(self):
		avail = stock.availability("Stethoscope")
		self.assertTrue(avail["tracked"])
		self.assertEqual(avail["qty"], 0)
		self.assertFalse(avail["enforce"])

	def test_non_stock_item_is_not_enforced(self):
		self.assertFalse(stock.availability("donate-glia-project")["enforce"])
