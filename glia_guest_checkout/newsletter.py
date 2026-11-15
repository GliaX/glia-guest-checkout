"""Newsletter signup with real validation.

The footer used to POST straight to `Newsletter Signup` via REST, so any string
was accepted ("notanemail" produced a thank-you). Anything that talks to donors
should validate server-side, not only in the browser: this endpoint validates the
address, de-duplicates, and records where the signup came from.
"""

from __future__ import annotations

import frappe
from frappe.utils import validate_email_address

DOCTYPE = "Newsletter Signup"


def subscribe(email: str, source: str = "Website footer"):
	email = (email or "").strip()
	# Raises a ValidationError with a friendly message for malformed addresses.
	validate_email_address(email, throw=True)
	email = email.lower()

	existing = None
	for name in frappe.get_all(DOCTYPE, filters={"email": ["like", email]}, pluck="name", limit=5):
		if (frappe.db.get_value(DOCTYPE, name, "email") or "").strip().lower() == email:
			existing = name
			break

	if existing:
		return {"status": "already", "message": "You are already on the list."}

	doc = frappe.new_doc(DOCTYPE)
	doc.update({"email": email, "source": source or "Website footer", "consent": 1})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return {"status": "subscribed", "message": "Thank you for joining Glia's mailing list!"}
