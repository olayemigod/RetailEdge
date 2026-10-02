from __future__ import annotations

import frappe


PRODUCT_DESCRIPTOR = {
	"key": "retailedge",
	"product_key": "retailedge",
	"label": "PEdge Retail",
	"product": "PEdge Retail",
	"icon": "shopping-cart",
	"home_route": "/app/retailedge-business-hub",
	"route_patterns": [
		"/app/retailedge*",
		"/app/make-sale*",
		"/app/professional-selling*",
		"/app/document-output-sharing*",
		"/app/transaction-workspace*",
		"/app/query-report/RetailEdge*",
	],
	"order": 20,
}


def get_product_availability() -> dict | None:
	"""Expose RetailEdge only when the current Desk user may open the product home page."""

	user = frappe.session.user
	if not user or user == "Guest":
		return None
	if user != "Administrator" and frappe.db.get_value("User", user, "user_type") != "System User":
		return None
	if not frappe.db.exists("Page", "retailedge-business-hub"):
		return None
	try:
		if not frappe.get_doc("Page", "retailedge-business-hub").is_permitted():
			return None
	except Exception:
		return None
	return dict(PRODUCT_DESCRIPTOR)
