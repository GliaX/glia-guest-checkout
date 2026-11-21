"""Convert a guest cart into an ERPNext Sales Order + Payment Request."""

from __future__ import annotations

import secrets

import frappe
from frappe.utils import flt, nowdate, validate_email_address
from erpnext.accounts.party import get_party_account
from erpnext.accounts.utils import get_account_currency
from erpnext.selling.doctype.quotation.quotation import _make_sales_order
from webshop.webshop.shopping_cart.cart import apply_cart_settings

from glia_guest_checkout.cart import _open_cart, set_cart_cookie, valid_warehouse
from glia_guest_checkout.taxes import apply_to_sales_order, normalize_country, normalize_state


def _website_email(customer_name, email):
	contact_name = frappe.db.get_value("Contact Email", {"email_id": email}, "parent")
	contact = frappe.get_doc("Contact", contact_name) if contact_name else None

	if contact:
		for link in contact.get("links", []):
			if link.link_doctype == "Customer":
				return frappe.get_doc("Customer", link.link_name), contact

	if frappe.get_meta("Customer").has_field("shopify_email"):
		customer_name_by_email = frappe.db.get_value("Customer", {"shopify_email": email}, "name")
		if customer_name_by_email:
			customer = frappe.get_doc("Customer", customer_name_by_email)
			if not contact:
				contact = _make_contact(customer, email)
			return customer, contact

	webshop = frappe.get_cached_doc("Webshop Settings")
	customer = frappe.new_doc("Customer")
	customer.update(
		{
			"customer_name": customer_name,
			"customer_type": "Individual",
			"customer_group": webshop.default_customer_group or "Individual",
			"territory": frappe.db.get_value("Territory", {"is_group": 0}, "name") or "All Territories",
		}
	)
	if frappe.get_meta("Customer").has_field("shopify_email"):
		customer.shopify_email = email
	customer.flags.ignore_permissions = True
	customer.insert(ignore_permissions=True)

	contact = _make_contact(customer, email)
	return customer, contact


def _make_contact(customer, email, full_name=None):
	contact = frappe.new_doc("Contact")
	contact.update(
		{
			"first_name": full_name or customer.customer_name or email.split("@")[0],
			"email_ids": [{"email_id": email, "is_primary": 1}],
			"links": [{"link_doctype": "Customer", "link_name": customer.name}],
		}
	)
	contact.flags.ignore_permissions = True
	contact.insert(ignore_permissions=True)
	return contact


def _make_address(customer, data):
	address = frappe.new_doc("Address")
	address.update(
		{
			"address_title": customer.customer_name,
			"address_type": "Shipping",
			"address_line1": data.address_line1,
			"address_line2": data.get("address_line2") or "",
			"city": data.city,
			"state": data.get("state") or "",
			"pincode": data.get("pincode") or "",
			"country": data.get("country") or "Canada",
			"phone": data.get("phone") or "",
			"email_id": data.email,
			"links": [{"link_doctype": "Customer", "link_name": customer.name}],
		}
	)
	address.flags.ignore_permissions = True
	address.insert(ignore_permissions=True)
	return address


def _payment_request(sales_order, customer, email):
	webshop = frappe.get_cached_doc("Webshop Settings")
	if not webshop.payment_gateway_account:
		frappe.throw("Online payment is not configured yet.")

	gateway = frappe.db.get_value(
		"Payment Gateway Account",
		webshop.payment_gateway_account,
		["name", "payment_gateway", "payment_account", "payment_channel", "message"],
		as_dict=True,
	)
	party_account = get_party_account("Customer", customer.name, sales_order.company)
	party_account_currency = get_account_currency(party_account)

	pr = frappe.new_doc("Payment Request")
	pr.update(
		{
			"payment_gateway_account": gateway.name,
			"payment_gateway": gateway.payment_gateway,
			"payment_account": gateway.payment_account,
			"payment_channel": gateway.payment_channel or "Email",
			"payment_request_type": "Inward",
			"currency": sales_order.currency,
			"party_account_currency": party_account_currency,
			"grand_total": sales_order.grand_total,
			"outstanding_amount": sales_order.grand_total,
			"email_to": email,
			"subject": f"Payment Request for {sales_order.name}",
			"message": f"Please complete payment for order {sales_order.name}.",
			"reference_doctype": "Sales Order",
			"reference_name": sales_order.name,
			"company": sales_order.company,
			"party_type": "Customer",
			"party": customer.name,
			"party_name": sales_order.customer_name,
			"make_sales_invoice": 1,
			"mute_email": 1,
		}
	)
	pr.flags.ignore_permissions = True
	pr.insert(ignore_permissions=True)
	pr.submit()
	pr.reload()
	if not pr.payment_url:
		pr.payment_url = pr.get_payment_url()
		pr.db_set("payment_url", pr.payment_url, update_modified=False)
	return pr


def place_order(data):
	data = frappe._dict(data)
	cart = _open_cart(create=False)
	if not cart or not cart.get("items"):
		frappe.throw("Your cart is empty.")

	email = (data.email or "").strip()
	full_name = (data.full_name or "").strip()
	validate_email_address(email, throw=True)
	if not full_name:
		full_name = email.split("@")[0]
	# Gifts need no shipping address at all; merchandise does, because it also
	# decides the tax province.
	needs_address = any(is_taxable(line.item_code) for line in cart.get("items", []))
	if needs_address:
		if not (data.address_line1 or "").strip():
			frappe.throw("Please enter a shipping address.")
		if not (data.city or "").strip():
			frappe.throw("Please enter a city.")
		if not (data.country or "").strip():
			data.country = "Canada"
		data.country = normalize_country(data.country)
		data.state = normalize_state(data.get("state"), data.country) or ""
		if data.country == "Canada" and not data.state:
			frappe.throw("Please choose your province so we can apply the correct tax.")
	else:
		data.country = normalize_country(data.get("country")) if data.get("country") else None
		data.state = normalize_state(data.get("state"), data.country) if data.get("state") else None

	webshop = frappe.get_cached_doc("Webshop Settings")
	currency = cart.currency or frappe.db.get_value("Company", webshop.company, "default_currency") or "CAD"

	original_user = frappe.session.user
	frappe.set_user("Administrator")
	try:
		customer, contact = _website_email(full_name, email)
		if not contact:
			contact = _make_contact(customer, email, full_name)
		address = _make_address(customer, data) if needs_address else None
		quotation = frappe.new_doc("Quotation")
		quotation.update(
			{
				"quotation_to": "Customer",
				"party_name": customer.name,
				"company": webshop.company,
				"order_type": "Shopping Cart",
				"transaction_date": nowdate(),
				"currency": currency,
				"selling_price_list": webshop.price_list or "Standard Selling",
				"contact_person": contact.name,
				"contact_email": email,
			}
		)
		if address:
			quotation.customer_address = address.name
			quotation.shipping_address_name = address.name
		for line in cart.get("items", []):
			quotation.append(
				"items",
				{
					"item_code": line.item_code,
					"item_name": line.item_name,
					"qty": line.qty,
					"rate": flt(line.rate),
					"price_list_rate": flt(line.rate),
					"warehouse": valid_warehouse(line.warehouse),
					"additional_notes": line.additional_notes,
				},
			)

		quotation.flags.ignore_permissions = True
		apply_cart_settings(customer, quotation)
		quotation.insert(ignore_permissions=True)
		# Never let an unpriced line through to a payment: the shopper would be
		# asked to pay 0 CAD for a real product.
		unpriced = [row.item_code for row in quotation.get("items") if flt(row.rate) <= 0]
		if unpriced:
			frappe.throw(
				"These products do not have a price yet, so the order cannot be placed: "
				+ ", ".join(unpriced)
			)
		quotation.submit()

		sales_order = frappe.get_doc(_make_sales_order(quotation.name, ignore_permissions=True))
		sales_order.order_type = "Shopping Cart"
		sales_order.flags.ignore_permissions = True
		# Canadian merchandise is taxed at the destination province; donations and
		# exports get no tax rows. NOTE: when shipping is charged it must be added to
		# the taxable base (as a taxable line), not left outside the tax rows.
		apply_to_sales_order(sales_order, data.country, data.state)
		sales_order.insert(ignore_permissions=True)
		sales_order.submit()

		payment_request = _payment_request(sales_order, customer, email)

	finally:
		frappe.set_user(original_user)

	cart.update(
		{
			"email": email,
			"customer": customer.name,
			"contact": contact.name,
			"status": "Converted",
			"sales_order": sales_order.name,
			"payment_request": payment_request.name,
			"order_token": secrets.token_urlsafe(24),
			"total": sales_order.grand_total,
		}
	)
	cart.flags.ignore_permissions = True
	cart.save(ignore_permissions=True)
	set_cart_cookie(cart.cart_id, 0)

	return {
		"payment_url": payment_request.payment_url,
		"order_token": cart.order_token,
		"sales_order": sales_order.name,
		"grand_total": sales_order.grand_total,
		"currency": sales_order.currency,
	}
