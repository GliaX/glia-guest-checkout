import frappe


def get_context(context):
	token = frappe.form_dict.get("token")
	if not token:
		frappe.throw("Order not found", frappe.DoesNotExistError)

	name = frappe.db.get_value("Guest Cart", {"order_token": token}, "name")
	if not name:
		frappe.throw("Order not found", frappe.DoesNotExistError)

	cart = frappe.get_doc("Guest Cart", name)
	sales_order = frappe.get_doc("Sales Order", cart.sales_order) if cart.sales_order else None
	payment_request = frappe.get_doc("Payment Request", cart.payment_request) if cart.payment_request else None

	context.no_cache = 1
	context.title = "Order"
	context.cart = cart
	context.sales_order = sales_order
	context.payment_request = payment_request
	context.payment_url = payment_request.payment_url if payment_request else None
	context.items = [
		{"item_name": row.item_name or row.item_code, "qty": row.qty, "amount": row.amount}
		for row in cart.get("items", [])
	]
	context.body_class = "guest-checkout-page"
