from __future__ import annotations

import frappe
from frappe import _


MAX_COMPANY_OPTIONS = 100
MAX_BRANCH_OPTIONS = 100


@frappe.whitelist()
def get_branch_assignment_filter_options(company: str = "") -> dict:
	"""Return bounded permission-aware Company→Branch options for assignment history."""
	if not frappe.has_permission("RetailEdge Branch Assignment", "read"):
		frappe.throw(_("You do not have permission to view Branch Assignments."), frappe.PermissionError)

	companies = frappe.get_list(
		"Company",
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_COMPANY_OPTIONS,
	)
	company_names = [row.get("name") for row in companies if row.get("name")]
	selected_company = str(company or "").strip()
	branches = []
	if selected_company and selected_company in company_names:
		rows = frappe.get_list(
			"RetailEdge Branch Profile",
			filters={"company": selected_company, "enabled": 1},
			fields=["branch"],
			order_by="branch asc",
			limit_page_length=MAX_BRANCH_OPTIONS,
		)
		branches = list(dict.fromkeys(row.get("branch") for row in rows if row.get("branch")))

	return {
		"companies": company_names,
		"branches": branches,
		"selected_company": selected_company if selected_company in company_names else "",
	}
