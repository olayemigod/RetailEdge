from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.desk.search import search_link
from frappe.utils import cint


ASSIGNMENT_DOCTYPE = "RetailEdge Branch Assignment"
MAX_LINK_RESULTS = 20


@frappe.whitelist()
def search_branch_assignment_options(
	fieldname: str,
	txt: str = "",
	values=None,
	limit: int = MAX_LINK_RESULTS,
) -> list[dict[str, Any]]:
	if not frappe.has_permission(ASSIGNMENT_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Branch Assignments."), frappe.PermissionError)
	values = frappe.parse_json(values) if isinstance(values, str) else (values or {})
	limit = min(max(cint(limit) or MAX_LINK_RESULTS, 1), MAX_LINK_RESULTS)
	company = str(values.get("company") or "").strip()

	if fieldname == "user":
		return search_link(
			"User",
			txt or "",
			filters={"enabled": 1, "user_type": "System User"},
			page_length=limit,
			reference_doctype=ASSIGNMENT_DOCTYPE,
			link_fieldname="user",
		)
	if fieldname == "company":
		return search_link(
			"Company",
			txt or "",
			page_length=limit,
			reference_doctype=ASSIGNMENT_DOCTYPE,
			link_fieldname="company",
		)
	if fieldname in {"branch", "filter_branch"}:
		if not company:
			return []
		return search_link(
			"Branch",
			txt or "",
			query="retailedge.branch_profile_queries.search_configured_company_branches",
			filters={"company": company},
			page_length=limit,
			reference_doctype=ASSIGNMENT_DOCTYPE,
			link_fieldname="branch",
		)
	frappe.throw(_("Unsupported Branch Assignment search field: {0}").format(fieldname))
	return []
