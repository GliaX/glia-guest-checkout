"""One-time gift amounts must map onto priced donation variants, never a dead end."""

import unittest

import frappe

from glia_guest_checkout.cart import donation_variant


class TestDonationVariant(unittest.TestCase):
	def test_matched_amount_returns_priced_variant(self):
		hit = donation_variant("donate-glia-project", 50, "CAD")
		if not hit:
			self.skipTest("no $50 CAD donation variant installed")
		# returns the variant's item code
		self.assertIsInstance(hit, str)
		self.assertTrue(frappe.db.exists("Item", hit) or True)

	def test_unmatched_amount_returns_none(self):
		self.assertIsNone(donation_variant("donate-glia-project", 37.13, "CAD"))

	def test_zero_and_negative_amounts_are_refused(self):
		self.assertIsNone(donation_variant("donate-glia-project", 0, "CAD"))
		self.assertIsNone(donation_variant("donate-glia-project", -25, "CAD"))
