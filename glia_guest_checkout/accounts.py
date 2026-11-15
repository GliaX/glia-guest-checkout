"""Account claim: let imported Shopify customers activate a website login.

The migration imported 4,273 Customers but no website Users — Shopify password
hashes are not exportable, so nobody can sign in and see their history. Instead
of mass-emailing everyone, this offers an on-demand claim:

  visitor asks with their email → we (quietly) find their Customer record → make
  sure a Website User exists for that address → send Frappe's standard password
  reset link.

Nothing is revealed about whether an address is known: the endpoint and the page
always behave the same way, and the reset mail is the only signal.
"""

from __future__ import annotations

import frappe
from frappe.utils import validate_email_address

WEBSITE_ROLE = "Customer"


def _customer_for_email(email: str) -> str | None:
	"""Find a Customer through the contact email, then via shopify_email."""
	contact = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if contact:
		customer = frappe.db.get_value(
			"Dynamic Link",
			{"parenttype": "Contact", "parent": contact, "link_doctype": "Customer"},
			"link_name",
		)
		if customer:
			return customer

	if frappe.get_meta("Customer").has_field("shopify_email"):
		return frappe.db.get_value("Customer", {"shopify_email": email}, "name")
	return None


def _ensure_user(email: str, customer: str | None) -> str:
	"""Create a Website User for the address if one does not exist yet."""
	user = frappe.db.get_value("User", {"email": email}, "name")
	if user:
		return user

	first_name = email.split("@")[0]
	contact = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if contact:
		first_name = frappe.db.get_value("Contact", contact, "first_name") or first_name

	doc = frappe.new_doc("User")
	doc.update(
		{
			"email": email,
			"first_name": first_name,
			"user_type": "Website User",
			"send_welcome_email": 0,
			"roles": [{"role": WEBSITE_ROLE}] if frappe.db.exists("Role", WEBSITE_ROLE) else [],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return doc.name


def _link_contact(email: str, user: str):
	contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	if not contact_name:
		return
	contact = frappe.get_doc("Contact", contact_name)
	if contact.get("user") != user:
		contact.user = user
		contact.flags.ignore_permissions = True
		contact.save(ignore_permissions=True)


def claim(email: str):
	"""Send a password-reset (account claim) link. Response is deliberately uniform."""
	email = (email or "").strip()
	validate_email_address(email, throw=True)

	customer = _customer_for_email(email)
	if not customer:
		# Unknown address: same response, no mail.
		frappe.logger("glia_guest_checkout").info(f"account claim for unknown address {email}")
		return {"status": "sent"}

	user = _ensure_user(email, customer)
	_link_contact(email, user)

	# Frappe's own reset flow: creates the reset key and emails the link, with
	# built-in enumeration protection and email-failure handling.
	from frappe.core.doctype.user.user import reset_password as send_reset

	send_reset(user)
	frappe.clear_messages()
	return {"status": "sent"}
