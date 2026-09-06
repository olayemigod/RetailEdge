from __future__ import annotations

import frappe

CUSTOMER_PORTAL_ROUTE = "/customer_portal"
CUSTOMER_PORTAL_TITLE = "Customer Portal"


def ensure_customer_portal_menu() -> dict[str, int]:
	"""Add the Customer Portal menu item without replacing existing portal items."""
	result = {"created": 0, "updated": 0, "skipped": 0}
	if not frappe.db.exists("DocType", "Portal Settings") or not frappe.db.exists("DocType", "Portal Menu Item"):
		result["skipped"] += 1
		return result

	settings = frappe.get_single("Portal Settings")
	row = next((item for item in (settings.get("menu") or []) if str(item.route or "") == CUSTOMER_PORTAL_ROUTE), None)
	if row:
		changed = False
		for fieldname, value in {
			"title": CUSTOMER_PORTAL_TITLE,
			"enabled": 1,
			"role": "Customer",
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
			"title": CUSTOMER_PORTAL_TITLE,
			"enabled": 1,
			"route": CUSTOMER_PORTAL_ROUTE,
			"role": "Customer",
		},
	)
	settings.save(ignore_permissions=True)
	result["created"] += 1
	return result
