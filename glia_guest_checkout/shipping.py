"""Packaging selection and parcel weights for the shop.

Packing practice comes from Jen Wilson (Nov 2026): a #2 bubble mailer holds at most
two stethoscopes (2 x 130 g = 260 g); #5 mailers and the large box are for bigger
orders. Shopify has no item dimensions, so packaging is chosen by weight/item count
rather than by measured volume — good enough for Canada Post rating, which mainly
needs parcel weight and dimensions.

All weights here are grams; dimensions are centimetres (Rating API convention).
"""

from __future__ import annotations

import frappe

# Uline packaging Glia actually uses (outside dimensions; packaging weight = the empty
# mailer/box). Uline SKUs are recorded in ACCESS.md and the WP.
PACKAGING = {
	"mailer2": {
		"label": "Bubble mailer #2 (8.5x12 in)",
		"uline_sku": "S-22456",
		"length_cm": 30.5, "width_cm": 21.6, "height_cm": 2.0,
		"packaging_g": 23,
	},
	"mailer5": {
		"label": "Bubble mailer #5 (10.5x16 in)",
		"uline_sku": "S-22457",
		"length_cm": 40.6, "width_cm": 26.7, "height_cm": 2.0,
		"packaging_g": 36,
	},
	"box_large": {
		"label": "Large box (22x12x8 in)",
		"uline_sku": "S-21050",
		"length_cm": 55.9, "width_cm": 30.5, "height_cm": 20.3,
		"packaging_g": 580,
	},
}

# Jen: "I can fit max 2 steths in a #2." A stethoscope is 130 g, so the mailer's
# practical capacity is ~260-300 g and two items.
MAILER2_MAX_G = 300
MAILER2_MAX_ITEMS = 2
MAILER5_MAX_G = 1500

WEIGHT_UOM_TO_G = {"Gram": 1.0, "Kg": 1000.0, "Pound": 453.59237, "Ounce": 28.349523125}


def item_weight_g(item_code: str) -> float:
	row = frappe.db.get_value("Item", item_code, ["weight_per_unit", "weight_uom"], as_dict=True)
	if not row or not row.weight_per_unit:
		return 0.0
	return float(row.weight_per_unit) * WEIGHT_UOM_TO_G.get(row.weight_uom or "Gram", 1.0)


def parcel_estimate(items) -> dict:
	"""Content weight, packaging choice and gross parcel weight for cart lines.

	`items` accepts dicts/rows with item_code and qty (or the guest-cart line shape).
	"""
	content_g = 0.0
	units = 0
	unweighted = []
	for row in items:
		code = row.get("item_code")
		qty = int(row.get("qty") or 1)
		g = item_weight_g(code)
		if g <= 0:
			unweighted.append(code)
		content_g += g * qty
		units += qty

	if units == 0:
		return {"packaging": None, "content_g": 0, "weight_g": 0, "unweighted": []}

	if content_g <= MAILER2_MAX_G and units <= MAILER2_MAX_ITEMS:
		key = "mailer2"
	elif content_g <= MAILER5_MAX_G:
		key = "mailer5"
	else:
		key = "box_large"

	pack = PACKAGING[key]
	return {
		"packaging": key,
		"packaging_label": pack["label"],
		"packaging_sku": pack["uline_sku"],
		"dimensions_cm": [pack["length_cm"], pack["width_cm"], pack["height_cm"]],
		"content_g": round(content_g, 1),
		"weight_g": round(content_g + pack["packaging_g"], 1),
		"unweighted": unweighted,
	}


def parcel_weight_kg(items) -> float:
	return round(parcel_estimate(items)["weight_g"] / 1000.0, 3)
