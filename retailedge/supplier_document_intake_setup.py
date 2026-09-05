from __future__ import annotations

import frappe

SUPPLIER_DOCUMENTS_ROUTE = "/supplier_documents"
SUPPLIER_DOCUMENTS_TITLE = "Supplier Documents"


def ensure_supplier_documents_menu() -> dict[str, int]:
	"""Add Supplier Documents without replacing existing portal menu items."""
	result = {"created": 0, "updated": 0, "skipped": 0}
	if not frappe.db.exists("DocType", "Portal Settings") or not frappe.db.exists(
		"DocType", "Portal Menu Item"
	):
		result["skipped"] += 1
		return result

	settings = frappe.get_single("Portal Settings")
	row = next(
		(
			item
			for item in (settings.get("menu") or [])
			if str(item.route or "") == SUPPLIER_DOCUMENTS_ROUTE
		),
		None,
	)
	if row:
		changed = False
		for fieldname, value in {
			"title": SUPPLIER_DOCUMENTS_TITLE,
			"enabled": 1,
			"role": "Supplier",
		}.items():
			if getattr(row, fieldname, None) != value:
				setattr(row, fieldname, value)
				changed = True
		if changed:
			settings.save(ignore_permissions=True)
			result["updated"] += 1
		else:
			result["skipped"] += 1
		return result

	settings.append(
		"menu",
		{
			"title": SUPPLIER_DOCUMENTS_TITLE,
			"enabled": 1,
			"route": SUPPLIER_DOCUMENTS_ROUTE,
			"role": "Supplier",
		},
	)
	settings.save(ignore_permissions=True)
	result["created"] += 1
	return result
