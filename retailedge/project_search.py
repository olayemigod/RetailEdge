from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

MAX_RESULTS = 50


@frappe.whitelist()
def search_projects(
	txt: str | None = None,
	company: str | None = None,
	customer: str | None = None,
	status: str | None = None,
	limit: int = 20,
) -> list[dict[str, Any]]:
	"""Return bounded permission-aware ERPNext Project options for EdgeSuite."""
	if not frappe.has_permission("Project", "read"):
		frappe.throw(_("You do not have permission to read Projects."), frappe.PermissionError)

	filters: dict[str, Any] = {}
	if company:
		filters["company"] = company
	if customer:
		filters["customer"] = customer
	if status:
		filters["status"] = status

	or_filters = None
	text = str(txt or "").strip()
	if text:
		or_filters = {
			"name": ["like", f"%{text}%"],
			"project_name": ["like", f"%{text}%"],
		}

	rows = frappe.get_list(
		"Project",
		filters=filters,
		or_filters=or_filters,
		fields=["name", "project_name", "status", "company", "customer", "percent_complete"],
		order_by="modified desc",
		limit_page_length=max(1, min(cint(limit) or 20, MAX_RESULTS)),
	)
	return [
		{
			"value": row.name,
			"label": row.project_name or row.name,
			"description": " · ".join(part for part in [row.status, row.company, row.customer] if part),
			"status": row.status,
			"company": row.company,
			"customer": row.customer or "",
			"percent_complete": row.percent_complete or 0,
		}
		for row in rows
	]
