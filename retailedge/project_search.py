from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.branch_context import get_user_allowed_branches, user_has_global_branch_access

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


@frappe.whitelist()
def search_project_branches(txt: str | None = None, company: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
	"""Return bounded Branch options that respect the current user's branch access.

	ERPNext v16 Branch is not company-bound. Where RetailEdge Branch Setup records
	exist for the selected Project Company, they provide the company-specific option
	set. Otherwise normal Branch read permission and the established RetailEdge /
	CoreEdge branch-access resolver remain authoritative.
	"""
	if not frappe.has_permission("Branch", "read"):
		frappe.throw(_("You do not have permission to read Branches."), frappe.PermissionError)

	text = str(txt or "").strip()
	page_length = max(1, min(cint(limit) or 20, MAX_RESULTS))
	allowed_info = get_user_allowed_branches(user=frappe.session.user, company=company or None)
	allowed = list(allowed_info.get("branches") or [])
	global_access = user_has_global_branch_access(user=frappe.session.user)

	company_branches: list[str] = []
	if company and frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		# Branch Setup is operational context, not accounting truth. Use it only to
		# narrow options when the caller can read the setup records.
		if frappe.has_permission("RetailEdge Branch Profile", "read"):
			company_branches = list(
				frappe.get_list(
					"RetailEdge Branch Profile",
					filters={"company": company, "enabled": 1},
					pluck="branch",
					limit_page_length=MAX_RESULTS,
				)
				or []
			)

	filters: dict[str, Any] = {}
	candidate_names: list[str] = []
	if company_branches:
		candidate_names = company_branches if global_access or not allowed else [name for name in company_branches if name in allowed]
	elif allowed and not global_access:
		candidate_names = allowed
	if candidate_names:
		filters["name"] = ["in", candidate_names]
	if text:
		filters["name"] = ["like", f"%{text}%"] if not candidate_names else ["in", [name for name in candidate_names if text.lower() in name.lower()]]

	if candidate_names and text and not filters["name"][1]:
		return []

	rows = frappe.get_list(
		"Branch",
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=page_length,
	)
	return [
		{
			"value": row.name,
			"label": row.name,
			"description": company or "",
		}
		for row in rows
	]
