"""Destination tax selection and taxability classification."""

import unittest

from glia_guest_checkout.taxes import (
	is_taxable,
	normalize_country,
	normalize_state,
	template_for,
)


class TestDestination(unittest.TestCase):
	def test_province_names_and_codes(self):
		self.assertEqual(normalize_state("ON"), "Ontario")
		self.assertEqual(normalize_state("  ontario "), "Ontario")
		self.assertEqual(normalize_state("Quebec"), "Quebec")
		self.assertEqual(normalize_state("PQ"), "Quebec")
		self.assertIsNone(normalize_state("Bavaria"))

	def test_country_aliases(self):
		self.assertEqual(normalize_country("CA"), "Canada")
		self.assertEqual(normalize_country("USA"), "United States")
		self.assertEqual(normalize_country(""), "Canada")

	def test_rates_by_province(self):
		self.assertEqual(template_for("Canada", "ON"), "Canada HST 13% - Glia")
		self.assertEqual(template_for("Canada", "NS"), "Canada HST 14% - Glia")
		self.assertEqual(template_for("Canada", "New Brunswick"), "Canada HST 15% - Glia")
		self.assertEqual(template_for("Canada", "BC"), "Canada GST+PST 12% - Glia")
		self.assertEqual(template_for("Canada", "MB"), "Canada GST+RST 12% - Glia")
		self.assertEqual(template_for("Canada", "SK"), "Canada GST+PST 11% - Glia")
		self.assertEqual(template_for("Canada", "QC"), "Canada GST+QST 14.975% - Glia")
		self.assertEqual(template_for("Canada", "AB"), "Canada GST 5% - Glia")

	def test_exports_are_zero_rated(self):
		self.assertIsNone(template_for("United States", "New York"))
		self.assertIsNone(template_for("Pakistan", None))

	def test_unknown_canadian_province_has_no_template(self):
		self.assertIsNone(template_for("Canada", None))
		self.assertIsNone(template_for("Canada", "Nowhere"))


class TestTaxability(unittest.TestCase):
	def test_donations_are_not_taxable(self):
		self.assertFalse(is_taxable("misc-monthly-donation"))

	def test_merch_is_taxable(self):
		import frappe

		merch = frappe.get_all("Item", filters={"item_group": "Merch"}, pluck="name", limit=1)
		if not merch:
			self.skipTest("no Merch items")
		self.assertTrue(is_taxable(merch[0]))
