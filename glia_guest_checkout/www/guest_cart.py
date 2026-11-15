import frappe

from glia_guest_checkout.cart import get_cart


def get_context(context):
	try:
		return _get_context(context)
	except Exception:
		frappe.log_error(frappe.get_traceback(), "guest-cart page")
		raise


def _get_context(context):
	if frappe.session.user != "Guest":
		frappe.local.flags.redirect_location = "/cart"
		raise frappe.Redirect

	context.no_cache = 1
	context.title = "Your Cart"
	context.cart = get_cart()
	context.body_class = "guest-checkout-page"
