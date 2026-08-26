from __future__ import annotations

import frappe
from frappe.utils import cint, cstr


@frappe.whitelist()
def search_banking_branches(txt: str | None = None, company: str | None = None, limit: int = 20):
	"""Return permission-visible Branch options inside a hard Company boundary.

	Frappe validates Link-search filter fields against field-level permissions. Some
	RetailEdge users can validly read/use Branch records without direct read access to
	``Branch.company``. Filtering ``company`` through ``frappe.get_list`` therefore
	still raises ``You do not have permission to access field: Branch.company``.

	To preserve both permission scope and company isolation, this method first asks
	Frappe for Branch *names only* using the current user's normal permissions. It then
	intersects those already-authorized names with Company using ``frappe.get_all``.
	The unrestricted lookup never expands the user's visible Branch set; it is used
	only to enforce the server-side Company boundary without exposing the restricted
	field to the browser or Frappe's field-permission validator.
	"""
	company = cstr(company).strip()
	if not company:
		return []

	company_doc = frappe.get_doc("Company", company)
	company_doc.check_permission("read")

	query = cstr(txt).strip()
	safe_limit = min(max(cint(limit) or 20, 1), 50)
	visible_filters: dict[str, object] = {}
	if query:
		visible_filters["name"] = ["like", f"%{query}%"]

	results: list[dict[str, str]] = []
	start = 0
	page_length = 100
	max_scan = 1000

	while len(results) < safe_limit and start < max_scan:
		visible_rows = frappe.get_list(
			"Branch",
			filters=visible_filters,
			fields=["name"],
			order_by="name asc",
			limit_start=start,
			limit_page_length=page_length,
		)
		if not visible_rows:
			break

		visible_names = [cstr(row.name).strip() for row in visible_rows if row.name]
		eligible_names = {
			cstr(row.name).strip()
			for row in frappe.get_all(
				"Branch",
				filters={"name": ["in", visible_names], "company": company},
				fields=["name"],
			)
			if row.name
		}

		for name in visible_names:
			if name not in eligible_names:
				continue
			results.append(
				{
					"value": name,
					"label": name,
					"description": company,
				}
			)
			if len(results) >= safe_limit:
				break

		start += len(visible_rows)
		if len(visible_rows) < page_length:
			break

	return results
