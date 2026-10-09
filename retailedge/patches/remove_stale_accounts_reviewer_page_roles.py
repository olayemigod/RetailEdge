from __future__ import annotations

import frappe


STALE_ROLE = "RetailEdge Accounts Reviewer"
PAGES = (
	"retailedge-business-hub",
	"reports-centre",
)


def execute():
	"""Remove stale Page role rows for a role that is not part of the RetailEdge role model."""
	for page_name in PAGES:
		frappe.db.delete(
			"Has Role",
			{
				"parent": page_name,
				"parenttype": "Page",
				"parentfield": "roles",
				"role": STALE_ROLE,
			},
		)
		if frappe.db.exists("Page", page_name):
			frappe.get_doc("Page", page_name).clear_cache()
