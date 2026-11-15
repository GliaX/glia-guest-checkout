"""Account claim page: request a login link for an imported Shopify customer."""

import frappe


def get_context(context):
	context.no_cache = 1
	context.show_sidebar = False
	context.page_title = "Your Glia account"
	return context
