"""Module-level smoke test: a broken import in the checkout path would only show
up when a shopper tries to pay, so import everything here instead."""

import unittest


class TestImports(unittest.TestCase):
	def test_public_modules_import(self):
		import glia_guest_checkout.api  # noqa: F401
		import glia_guest_checkout.cart  # noqa: F401
		import glia_guest_checkout.checkout  # noqa: F401
		import glia_guest_checkout.newsletter  # noqa: F401
		import glia_guest_checkout.taxes  # noqa: F401
