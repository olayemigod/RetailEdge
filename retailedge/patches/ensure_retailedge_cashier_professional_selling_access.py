from __future__ import annotations

import frappe


CASHIER_ROLES = (
	"RetailEdgeCashier",
	"RetailEdge Cashier",
)
PROFESSIONAL_SELLING_PAGE = "professional-selling"


def _ensure_page_role(role: str) -> None:
	if not frappe.db.exists("Page", PROFESSIONAL_SELLING_PAGE):
		return
	page = frappe.get_doc("Page", PROFESSIONAL_SELLING_PAGE)
	if any(str(row.role or "").strip() == role for row in page.roles or []):
		return
	page.append("roles", {"role": role})
	page.flags.ignore_permissions = True
	page.flags.do_not_update_json = True
	page.save(ignore_permissions=True)
	page.clear_cache()


def execute():
	"""Reconcile existing sites so cashier Page access matches the permission-aware workspace contract."""
	for role in CASHIER_ROLES:
		if not frappe.db.exists("Role", role):
			continue
		_ensure_page_role(role)

	frappe.clear_cache()
