"""Guest cart: cookie-scoped, database-backed cart for anonymous shoppers."""

from __future__ import annotations

import secrets

import frappe
from frappe.utils import cint, flt
from urllib.parse import unquote

CART_COOKIE = "guest_cart_id"
CART_MAX_AGE = 60 * 60 * 24 * 30


def _cookie_manager():
	return getattr(frappe.local, "cookie_manager", None)


def set_cart_cookie(cart_id, count=None):
	manager = _cookie_manager()
	if not manager:
		return
	manager.set_cookie(
		CART_COOKIE,
		cart_id,
		max_age=CART_MAX_AGE,
		httponly=True,
		secure=True,
		samesite="Lax",
	)
	if count is not None:
		manager.set_cookie(
			"cart_count",
			str(cint(count)),
			max_age=CART_MAX_AGE,
			httponly=False,
			secure=True,
			samesite="Lax",
		)


def get_cart_id(create=False):
	cart_id = frappe.request.cookies.get(CART_COOKIE) if frappe.request else None
	if cart_id:
		cart_id = unquote(cart_id)
	if not cart_id and create:
		cart_id = secrets.token_urlsafe(24)
		set_cart_cookie(cart_id, 0)
	return cart_id


def _cart_name(cart_id):
	return frappe.db.get_value("Guest Cart", {"cart_id": cart_id}, "name")


def _new_cart(cart_id):
	webshop = frappe.get_cached_doc("Webshop Settings")
	currency = frappe.db.get_value("Company", webshop.company, "default_currency") or "CAD"
	cart = frappe.get_doc(
		{
			"doctype": "Guest Cart",
			"cart_id": cart_id,
			"status": "Open",
			"currency": currency,
			"total": 0,
		}
	)
	cart.flags.ignore_permissions = True
	cart.insert(ignore_permissions=True)
	return cart


def _open_cart(create=False):
	cart_id = get_cart_id(create=False)
	if cart_id:
		name = _cart_name(cart_id)
		if name:
			cart = frappe.get_doc("Guest Cart", name)
			if cart.status == "Open":
				return cart
	if not create:
		return None
	cart_id = secrets.token_urlsafe(24)
	set_cart_cookie(cart_id, 0)
	return _new_cart(cart_id)


def _web_item(item_code):
	fields = ["name", "item_code", "item_name", "website_image", "route", "website_warehouse", "item_group"]
	web_item = frappe.db.get_value("Website Item", {"item_code": item_code}, fields, as_dict=True)
	if web_item:
		return web_item
	variant_of = frappe.db.get_value("Item", item_code, "variant_of")
	if variant_of:
		return frappe.db.get_value("Website Item", {"item_code": variant_of}, fields, as_dict=True)
	return None


def _currency():
	webshop = frappe.get_cached_doc("Webshop Settings")
	return frappe.db.get_value("Company", webshop.company, "default_currency") or "CAD"


def _price_list():
	webshop = frappe.get_cached_doc("Webshop Settings")
	return webshop.price_list or "Standard Selling"


def default_warehouse():
	webshop = frappe.get_cached_doc("Webshop Settings")
	preferred = "Finished Goods - Canada - Glia"
	if frappe.db.exists("Warehouse", preferred) and not frappe.db.get_value("Warehouse", preferred, "disabled"):
		return preferred
	for row in frappe.get_all(
		"Warehouse",
		filters={"company": webshop.company, "is_group": 0, "disabled": 0},
		pluck="name",
		limit_page_length=10,
	):
		return row
	return None


def valid_warehouse(warehouse):
	if warehouse and frappe.db.exists("Warehouse", warehouse):
		if not frappe.db.get_value("Warehouse", warehouse, "disabled") and not frappe.db.get_value("Warehouse", warehouse, "is_group"):
			return warehouse
	return default_warehouse()


def item_rate(item_code, currency=None):
	currency = currency or _currency()
	rate = frappe.db.get_value(
		"Item Price",
		{"item_code": item_code, "price_list": _price_list(), "currency": currency},
		"price_list_rate",
	)
	if rate is None:
		rate = frappe.db.get_value("Item", item_code, "standard_rate")
	return flt(rate or 0)


def _set_line(item, qty, rate):
	item.qty = flt(qty)
	item.rate = flt(rate)
	item.amount = flt(item.qty * item.rate, 2)


def _recalculate(cart):
	total = 0.0
	count = 0
	for item in cart.get("items", []):
		_set_line(item, item.qty, item.rate)
		total += flt(item.amount)
		count += cint(item.qty)
	cart.total = flt(total, 2)
	return count


def cart_to_dict(cart):
	if not cart:
		return {"items": [], "total": 0, "currency": _currency(), "count": 0, "status": "Open"}
	return {
		"items": [
			{
				"item_code": item.item_code,
				"item_name": item.item_name or item.item_code,
				"qty": cint(item.qty),
				"rate": flt(item.rate),
				"amount": flt(item.amount),
				"image": item.image or "",
				"route": item.route or item.item_code,
				"notes": item.additional_notes or "",
			}
			for item in cart.get("items", [])
		],
		"total": flt(cart.total),
		"currency": cart.currency or _currency(),
		"count": sum(cint(item.qty) for item in cart.get("items", [])),
		"status": cart.status,
	}


def get_cart():
	cart = _open_cart(create=False)
	if not cart:
		return {"items": [], "total": 0, "currency": _currency(), "count": 0, "status": "Open"}
	return cart_to_dict(cart)


def add_item(item_code, qty=1, additional_notes=None):
	if not item_code or not frappe.db.exists("Item", item_code):
		frappe.throw("That product is no longer available.")
	item = frappe.get_cached_doc("Item", item_code)
	if item.disabled:
		frappe.throw("That product is no longer available.")
	# A variant template has no price of its own and must never be sold directly:
	# the shopper has to pick the size/colour/amount first, and the priced
	# document is the variant item.
	if item.get("has_variants") and not item.get("variant_of"):
		frappe.throw("Please choose the options (size, colour or amount) for this product first.")

	web_item = _web_item(item_code)
	if not web_item or not frappe.db.get_value("Website Item", web_item.name, "published"):
		frappe.throw("That product is not available in the shop.")

	qty = max(1, cint(qty))
	cart = _open_cart(create=True)
	rate = item_rate(item_code, cart.currency)
	if rate <= 0:
		frappe.throw("This product does not have a price yet. Please contact us to order it.")
	line = next((row for row in cart.items if row.item_code == item_code), None)
	if line:
		line.qty = cint(line.qty) + qty
		line.additional_notes = additional_notes or line.additional_notes
	else:
		line = cart.append(
			"items",
			{
				"item_code": item_code,
				"item_name": web_item.item_name or item.item_name,
				"qty": qty,
				"rate": rate,
				"warehouse": valid_warehouse(web_item.website_warehouse),
				"image": web_item.website_image,
				"route": web_item.route,
				"additional_notes": additional_notes,
			},
		)
	_set_line(line, line.qty, item_rate(item_code, cart.currency))

	count = _recalculate(cart)
	cart.flags.ignore_permissions = True
	cart.save(ignore_permissions=True)
	set_cart_cookie(cart.cart_id, count)
	return cart_to_dict(cart)


def update_item(item_code, qty):
	cart = _open_cart(create=False)
	if not cart:
		return get_cart()
	qty = cint(qty)
	if qty <= 0:
		return remove_item(item_code)
	line = next((row for row in cart.items if row.item_code == item_code), None)
	if not line:
		return cart_to_dict(cart)
	_set_line(line, qty, line.rate or item_rate(item_code, cart.currency))
	count = _recalculate(cart)
	cart.flags.ignore_permissions = True
	cart.save(ignore_permissions=True)
	set_cart_cookie(cart.cart_id, count)
	return cart_to_dict(cart)


def remove_item(item_code):
	cart = _open_cart(create=False)
	if not cart:
		return get_cart()
	removed = False
	for row in list(cart.items):
		if row.item_code == item_code:
			cart.remove(row)
			removed = True
	if not removed:
		return cart_to_dict(cart)
	count = _recalculate(cart)
	cart.flags.ignore_permissions = True
	cart.save(ignore_permissions=True)
	set_cart_cookie(cart.cart_id, count)
	return cart_to_dict(cart)


def clear_cart(cart):
	for row in list(cart.items):
		cart.remove(row)
	_recalculate(cart)
	cart.flags.ignore_permissions = True
	cart.save(ignore_permissions=True)
	set_cart_cookie(cart.cart_id, 0)
