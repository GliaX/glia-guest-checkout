"""Whitelisted guest-cart and checkout endpoints (no login required)."""

from __future__ import annotations

import frappe

from frappe.rate_limiter import rate_limit

from glia_guest_checkout.accounts import claim
from glia_guest_checkout.cart import (
	add_item,
	get_cart,
	remove_item,
	start_donation,
	update_item,
)
from glia_guest_checkout.checkout import place_order
from glia_guest_checkout.newsletter import subscribe


def _require_guest():
	if frappe.session.user != "Guest":
		frappe.throw("Guest checkout is only available when signed out.")


@frappe.whitelist(allow_guest=True)
def get_guest_cart():
	_require_guest()
	return get_cart()


@frappe.whitelist(allow_guest=True)
def add_to_cart(item_code, qty=1):
	_require_guest()
	return add_item(item_code, qty)


@frappe.whitelist(allow_guest=True)
def update_guest_cart(item_code, qty=1):
	_require_guest()
	return update_item(item_code, qty)


@frappe.whitelist(allow_guest=True)
def remove_from_cart(item_code):
	_require_guest()
	return remove_item(item_code)


@frappe.whitelist(allow_guest=True)
def start_one_time_donation(amount, campaign=None, currency=None):
	"""Add a one-time gift to the guest cart (donation bar "One-time")."""
	_require_guest()
	return start_donation(amount, campaign, currency)


@frappe.whitelist(allow_guest=True)
@rate_limit(key="email", ip_based=False, limit=3, seconds=3600, methods=["POST"])
def subscribe_newsletter(email, source="Website footer"):
	"""Validated newsletter signup; the footer used to post raw REST."""
	return subscribe(email, source)


@frappe.whitelist(allow_guest=True)
# Limit per address, not per IP: behind the ingress every request looks like an
# ingress-pod IP, so an IP limit is split across replicas and barely applies.
@rate_limit(key="email", ip_based=False, limit=3, seconds=3600, methods=["POST"])
def request_account_claim(email):
	"""Email a password-reset (claim) link to an imported customer's address."""
	return claim(email)


@frappe.whitelist(allow_guest=True)
def guest_checkout(email, full_name, address_line1, city, country, address_line2=None,
                   state=None, pincode=None, phone=None):
	_require_guest()
	try:
		return place_order(
			{
				"email": email,
			"full_name": full_name,
			"address_line1": address_line1,
			"address_line2": address_line2,
			"city": city,
			"state": state,
			"pincode": pincode,
			"country": country,
				"phone": phone,
			}
		)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "guest checkout api")
		raise
