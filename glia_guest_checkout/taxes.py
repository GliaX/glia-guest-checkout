"""Canadian sales tax for the shop checkout.

Rules implemented here (decided 2026-11-15):

* Glia is GST/HST registered (BN 807831391); merchandise is taxed at the rate of
  the **destination province** and prices are tax-exclusive.
* Donations, contributions and internal "Gray Area" items are never taxed.
* Outside Canada nothing is charged (export, zero-rated).
* Shipping is taxable — i.e. once shipping is charged, it must be part of the
  taxable base, so it is added as a taxable line rather than left out.

ERPNext cannot vary rates by destination *and* exempt individual lines within one
document, so the cart refuses to mix taxable goods with donations: each order is
either a taxable merchandise order or an untaxed donation order.
"""

from __future__ import annotations

import frappe
from frappe.utils import flt

# Item groups that must never be taxed (gifts and GL/fee buckets)
NON_TAXABLE_GROUPS = {"Donation", "Contribution", "Gray Area"}

# Destination province -> template (created by the tax setup on the site)
PROVINCE_TEMPLATES = {
	"Ontario": "Canada HST 13% - Glia",
	"Nova Scotia": "Canada HST 14% - Glia",
	"New Brunswick": "Canada HST 15% - Glia",
	"Newfoundland and Labrador": "Canada HST 15% - Glia",
	"Prince Edward Island": "Canada HST 15% - Glia",
	"Alberta": "Canada GST 5% - Glia",
	"Yukon": "Canada GST 5% - Glia",
	"Northwest Territories": "Canada GST 5% - Glia",
	"Nunavut": "Canada GST 5% - Glia",
	"British Columbia": "Canada GST+PST 12% - Glia",
	"Manitoba": "Canada GST+RST 12% - Glia",
	"Saskatchewan": "Canada GST+PST 11% - Glia",
	"Quebec": "Canada GST+QST 14.975% - Glia",
}

PROVINCE_ALIASES = {
	"ON": "Ontario", "ONT": "Ontario", "ONTARIO": "Ontario",
	"NS": "Nova Scotia", "NOVA SCOTIA": "Nova Scotia",
	"NB": "New Brunswick", "NEW BRUNSWICK": "New Brunswick",
	"NL": "Newfoundland and Labrador", "NF": "Newfoundland and Labrador",
	"NEWFOUNDLAND AND LABRADOR": "Newfoundland and Labrador",
	"NEWFOUNDLAND": "Newfoundland and Labrador", "LABRADOR": "Newfoundland and Labrador",
	"PE": "Prince Edward Island", "PEI": "Prince Edward Island",
	"PRINCE EDWARD ISLAND": "Prince Edward Island",
	"AB": "Alberta", "ALBERTA": "Alberta",
	"YT": "Yukon", "YUKON": "Yukon",
	"NT": "Northwest Territories", "NORTHWEST TERRITORIES": "Northwest Territories",
	"NU": "Nunavut", "NUNAVUT": "Nunavut",
	"BC": "British Columbia", "BRITISH COLUMBIA": "British Columbia",
	"MB": "Manitoba", "MANITOBA": "Manitoba",
	"SK": "Saskatchewan", "SASKATCHEWAN": "Saskatchewan",
	"QC": "Quebec", "PQ": "Quebec", "QUEBEC": "Quebec", "QUÉBEC": "Quebec",
}

COUNTRY_ALIASES = {
	"CA": "Canada", "CAN": "Canada", "CANADA": "Canada",
	"US": "United States", "USA": "United States", "UNITED STATES": "United States",
	"UNITED STATES OF AMERICA": "United States",
}


def normalize_country(country: str | None) -> str:
	country = (country or "").strip()
	if not country:
		return "Canada"
	return COUNTRY_ALIASES.get(country.upper(), country)


def normalize_state(state: str | None, country: str | None = None) -> str | None:
	"""Return the canonical province name, or None if it cannot be resolved."""
	state = (state or "").strip()
	if not state:
		return None
	key = state.upper().replace("  ", " ")
	if key in PROVINCE_ALIASES:
		return PROVINCE_ALIASES[key]
	# already a canonical name?
	for name in PROVINCE_TEMPLATES:
		if name.upper() == key:
			return name
	return None


def item_group(item_code: str) -> str | None:
	return frappe.get_cached_value("Item", item_code, "item_group")


def is_taxable(item_code: str) -> bool:
	group = item_group(item_code)
	if not group:
		return False
	return group not in NON_TAXABLE_GROUPS


def cart_taxability(item_codes) -> set[bool]:
	"""The set of taxability classes present (True = taxable)."""
	return {is_taxable(code) for code in item_codes if code}


def template_for(country: str | None, state: str | None) -> str | None:
	"""Tax template for a destination, or None when nothing is charged."""
	country = normalize_country(country)
	if country != "Canada":
		return None  # exports are zero-rated
	province = normalize_state(state, country)
	if not province:
		return None
	return PROVINCE_TEMPLATES.get(province)


def tax_total(template: str, net_total: float) -> float:
	"""Sum of the template's rates applied to a net total (for previews/tests)."""
	if not template:
		return 0.0
	rows = frappe.get_all(
		"Sales Taxes and Charges",
		filters={"parent": template, "parenttype": "Sales Taxes and Charges Template"},
		fields=["rate", "charge_type"],
	)
	total = 0.0
	for row in rows:
		if (row.charge_type or "On Net Total") == "On Net Total":
			total += flt(net_total) * flt(row.rate) / 100.0
	return round(total, 2)


def apply_to_sales_order(sales_order, country: str | None, state: str | None) -> str | None:
	"""Set the destination tax template on a Sales Order about to be inserted."""
	taxable = [row.item_code for row in sales_order.get("items", []) if is_taxable(row.item_code)]
	if not taxable:
		return None  # donation-only order: no tax rows at all

	country = normalize_country(country)
	province = normalize_state(state, country)
	if country == "Canada" and not province:
		frappe.throw("Please choose your province so we can apply the correct tax.")

	template = template_for(country, province)
	if not template:
		return None  # outside Canada

	sales_order.taxes_and_charges = template
	sales_order.set_taxes()
	return template
