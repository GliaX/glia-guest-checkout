"""Landing page Stripe returns to after checkout.

Frappe/payments redirects here with `doctype`/`docname` params; our guest carts add
a `token`. Whatever the donor sees must never be a server error, so every lookup
here is best-effort: unknown references fall back to a plain thank-you page.
"""

import frappe
from frappe.utils import flt


def _donation_summary(donation):
	return {
		"kind": "donation",
		"amount": flt(donation.get("amount")),
		"currency": donation.get("currency") or "CAD",
		"reference": donation.name,
		"date": donation.get("donation_date"),
		"recurring": bool(donation.get("recurring_donation")),
	}


def _order_summary(order):
	return {
		"kind": "order",
		"amount": flt(order.get("grand_total")),
		"currency": order.get("currency") or "CAD",
		"reference": order.name,
		"date": order.get("transaction_date"),
		"order_token": frappe.db.get_value("Guest Cart", {"sales_order": order.name}, "order_token"),
	}


def get_context(context):
	context.no_cache = 1
	context.title = "Thank you"
	context.summary = None
	context.search_ok = True
	doctype = frappe.form_dict.get("doctype")
	docname = frappe.form_dict.get("docname")
	token = frappe.form_dict.get("token")
	try:
		if token:
			cart = frappe.get_all("Guest Cart", filters={"order_token": token}, fields=["sales_order"], limit=1)
			if cart and cart[0].sales_order:
				context.summary = _order_summary(frappe.get_doc("Sales Order", cart[0].sales_order))
		elif doctype and docname and frappe.db.exists(doctype, docname):
			doc = frappe.get_doc(doctype, docname)
			if doctype == "Donation":
				context.summary = _donation_summary(doc)
			elif doctype in ("Sales Order", "Sales Invoice"):
				context.summary = _order_summary(doc)
			elif doctype == "Payment Request":
				target = doc.reference_name
				if doc.reference_doctype == "Sales Order" and frappe.db.exists("Sales Order", target):
					context.summary = _order_summary(frappe.get_doc("Sales Order", target))
				elif doc.reference_doctype == "Sales Invoice" and frappe.db.exists("Sales Invoice", target):
					context.summary = _order_summary(frappe.get_doc("Sales Invoice", target))
	except Exception:
		frappe.log_error(frappe.get_traceback(), "payment-success page")
		context.summary = None
