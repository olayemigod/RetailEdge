from __future__ import annotations

import frappe


SETUP_RESOURCES = (
	{
		"key": "settings",
		"label": "Settings",
		"description": "Configure RetailEdge controls, posting rules, cost visibility and operating defaults.",
		"doctype": "RetailEdge Settings",
		"singleton": True,
		"icon": "settings",
	},
	{
		"key": "branches",
		"label": "Branch Setup",
		"description": "Manage Branch operating defaults, Stock Locations, POS Profile, accounts and controls.",
		"doctype": "RetailEdge Branch Profile",
		"page": "branch-setup",
		"singleton": False,
		"icon": "building",
	},
	{
		"key": "branch-assignments",
		"label": "Branch Assignments",
		"description": "Assign users to Branches with effective dates and preserve transfer history between locations.",
		"doctype": "RetailEdge Branch Assignment",
		"page": "branch-assignments",
		"singleton": False,
		"icon": "users",
	},
	{
		"key": "expense-categories",
		"label": "Expense Categories",
		"description": "Maintain the controlled categories used by Cashier Expense and expense reporting.",
		"doctype": "RetailEdge Expense Category",
		"singleton": False,
		"icon": "file-text",
	},
	{
		"key": "statement-mapping",
		"label": "Bank Statement Mapping",
		"description": "Maintain reusable mappings for imported bank and payment-provider statements.",
		"doctype": "RetailEdge Statement Mapping Template",
		"singleton": False,
		"icon": "repeat",
	},
	{
		"key": "bank-accounts",
		"label": "Bank Accounts",
		"description": "Open ERPNext Bank Account records used by RetailEdge payments and reconciliation.",
		"doctype": "Bank Account",
		"singleton": False,
		"icon": "wallet",
	},
	{
		"key": "payment-methods",
		"label": "Payment Methods",
		"description": "Open ERPNext Mode of Payment records used by sales, collections and payments.",
		"doctype": "Mode of Payment",
		"singleton": False,
		"icon": "credit-card",
	},
)


def _doctype_available(doctype: str) -> bool:
	try:
		return bool(frappe.db.exists("DocType", doctype))
	except Exception:
		return False


def _has_permission(doctype: str, ptype: str) -> bool:
	try:
		return bool(frappe.has_permission(doctype, ptype=ptype))
	except Exception:
		return False


def _bounded_visible_count(doctype: str, *, limit: int = 101) -> dict[str, int | bool]:
	"""Return a permission-filtered bounded count without scanning the full master."""
	try:
		rows = frappe.get_list(doctype, fields=["name"], limit_page_length=limit)
	except Exception:
		return {"count": 0, "count_capped": False}
	count = len(rows)
	return {"count": min(count, limit - 1), "count_capped": count >= limit}


@frappe.whitelist()
def get_setup_context() -> dict:
	"""Return the permission-aware resources for the EdgeSuite Setup hub.

	The hub intentionally does not duplicate native DocType persistence. RetailEdge
	uses the existing Frappe/ERPNext forms as authoritative editors and advanced
	fallbacks, while this Page provides one coherent customer-facing setup entry.
	"""
	resources = []
	for definition in SETUP_RESOURCES:
		doctype = definition["doctype"]
		if not _doctype_available(doctype) or not _has_permission(doctype, "read"):
			continue
		resource = dict(definition)
		resource["can_create"] = False if definition["singleton"] else _has_permission(doctype, "create")
		if definition["singleton"]:
			resource["count"] = None
			resource["count_capped"] = False
		else:
			resource.update(_bounded_visible_count(doctype))
		resources.append(resource)

	return {
		"resources": resources,
		"user": frappe.session.user,
		"user_name": frappe.utils.get_fullname(frappe.session.user),
	}
