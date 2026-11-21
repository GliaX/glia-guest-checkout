"""Stock availability for the storefront.

Most items have no seeded Bin quantities yet, so availability must never block a
sale just because stock data is missing: we only show/enforce a quantity when the
item actually has Bin rows (tracked), and enforce only when some warehouse holds
positive stock. That guards against overselling once stock is seeded without
freezing the shop before it is.
"""

from __future__ import annotations

import frappe


def bins(item_code: str):
	return frappe.get_all("Bin", filters={"item_code": item_code},
	                      fields=["warehouse", "actual_qty", "projected_qty"], limit_page_length=0)


def availability(item_code: str) -> dict:
	item = frappe.db.get_value("Item", item_code, ["is_stock_item", "stock_uom"], as_dict=True)
	if not item:
		return {"item_code": item_code, "tracked": False, "qty": 0, "label": ""}
	rows = bins(item_code) if item.is_stock_item else []
	qty = round(sum(float(r.actual_qty or 0) for r in rows), 2)
	tracked = bool(rows)
	if not item.is_stock_item:
		label = ""
	elif qty > 0:
		label = f"In stock: {qty:g} {item.stock_uom}"
	elif tracked:
		label = "Available to order"
	else:
		label = ""
	return {"item_code": item_code, "tracked": tracked, "qty": qty, "uom": item.stock_uom,
	        "label": label, "enforce": tracked and qty > 0}
