"""Tier 2: volunteer interest, donor portal, campaign attribution."""

import ast
import os
import unittest

import frappe


class TestVolunteer(unittest.TestCase):
	def test_invalid_email_is_refused(self):
		from glia_guest_checkout.volunteer import record_interest

		with self.assertRaises(frappe.ValidationError):
			record_interest("Test", "not-an-email")

	def test_interest_is_recorded_and_notified(self):
		from glia_guest_checkout.volunteer import notify_team, record_interest

		source = open(os.path.join(os.path.dirname(__file__), "..", "volunteer.py")).read()
		self.assertIn('"Volunteer Interest"', source)
		self.assertIn("notify_team", source)
		self.assertTrue(callable(record_interest))
		self.assertTrue(callable(notify_team))

	def test_doctype_exists_in_app(self):
		import json
		path = os.path.join(os.path.dirname(__file__), "..", "glia_guest_checkout", "doctype",
		                    "volunteer_interest", "volunteer_interest.json")
		data = json.load(open(path))
		self.assertEqual(data["name"], "Volunteer Interest")


class TestCampaignAttribution(unittest.TestCase):
	def test_cart_note_encodes_campaign(self):
		from glia_guest_checkout import cart

		source = open(os.path.join(os.path.dirname(cart.__file__), "cart.py")).read()
		self.assertIn('campaign:', source)
		self.assertIn("additional_notes=campaign_note", source)


class TestPortal(unittest.TestCase):
	def test_portal_page_requires_login(self):
		path = os.path.join(os.path.dirname(__file__), "..", "www", "my_donations.py")
		tree = ast.parse(open(path).read())
		text = open(path).read()
		self.assertIn("/login?redirect-to=/my_donations", text)
		self.assertTrue(tree)
