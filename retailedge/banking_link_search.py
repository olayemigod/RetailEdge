from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr


@frappe.whitelist()
def search_banking_branches(txt: str | None = None, company: str | None = None, limit: int = 20):
	"""Return Branch link options for the banking workspace without exposing Branch.company.

	The normal Desk link search validates frontend filter fields against the user's
	field-level permissions. Some RetailEdge users may validly use Branch records
	without having direct read access to Branch.company, so filtering Branch.company
	in the browser can raise a permission error. This server-side query keeps Company
	as a hard boundary, checks Company read permission, and lets frappe.get_list apply
	the user's Branch permissions/user-permission scope.
	"""
	company = cstr(company).strip()
	if not company:
		return []

	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("read")

	query = cstr(txt).strip()
	safe_limit = min(max(cint(limit) or 20, 1), 50)
	filters: dict[str, object] = {"company": company}
	if query:
		filters["name"] = ["like", f"%{query}%"]

	rows = frappe.get_list(
		"Branch",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=safe_limit,
	)
	return [
		{
			"value": row.name,
			"label": row.name,
			"description": company,
		}
		for row in rows
	]
