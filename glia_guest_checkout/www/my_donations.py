"""Donor portal: the gifts and orders tied to the signed-in account.

Customers imported from Shopify can claim an account from /claim_account; this page
then shows what they have given and bought, which the old store never offered.
"""

import frappe


def get_context(context):
	context.no_cache = 1
	context.title = "My account"
	user = frappe.session.user
	if user in ("Guest", None):
		frappe.local.flags.redirect_location = "/login?redirect-to=/my_donations"
		raise frappe.Redirect
	email = user
	context.email = email
	context.donations = frappe.get_all(
		"Donation",
		filters={"donor_email": email},
		fields=["name", "donation_date", "amount", "currency", "campaign", "donation_type"],
		order_by="donation_date desc",
		limit_page_length=100,
		ignore_permissions=True,
	)
	context.donation_total = round(sum(float(d.amount or 0) for d in context.donations), 2)
	context.orders = frappe.get_all(
		"Sales Order",
		filters={"contact_email": email, "docstatus": ["<", 2]},
		fields=["name", "transaction_date", "grand_total", "currency", "status"],
		order_by="transaction_date desc",
		limit_page_length=50,
		ignore_permissions=True,
	)
