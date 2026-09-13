from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint

from retailedge.operating_context import get_operational_branch_scope

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
def search_project_branches(
	txt: str | None = None, company: str | None = None, limit: int = 20
) -> list[dict[str, Any]]:
	"""Return bounded Branch options that respect the current user's branch access.

	ERPNext v16 Branch is not company-bound. Where RetailEdge Branch Setup records
	exist for the selected Project Company, they provide the company-specific option
	set. Otherwise normal Branch read permission and the established RetailEdge /
	CoreEdge branch-access resolver remain authoritative.
	"""
	if not frappe.has_permission("Branch", "read"):
		frappe.throw(_("You do not have permission to read Branches."), frappe.PermissionError)

	company = str(company or "").strip()
	if not company:
		return []
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have permission to read this Company."), frappe.PermissionError)

	text = str(txt or "").strip()
	page_length = max(1, min(cint(limit) or 20, MAX_RESULTS))
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	restricted = bool(scope.get("restricted"))
	allowed = list(
		dict.fromkeys(
			str(name or "").strip() for name in scope.get("allowed_branches") or [] if str(name or "").strip()
		)
	)
	if restricted and not allowed:
		return []

	company_branches: list[str] = []
	if frappe.db.exists("DocType", "RetailEdge Branch Profile"):
		# Branch Setup is operational context, not accounting truth. Use it only to
		# narrow options when the caller can read the setup records.
		if frappe.has_permission("RetailEdge Branch Profile", "read"):
			profile_branches = (
				frappe.get_list(
					"RetailEdge Branch Profile",
					filters={"company": company, "enabled": 1},
					pluck="branch",
					limit_page_length=MAX_RESULTS,
				)
				or []
			)
			company_branches = list(
				dict.fromkeys(str(name or "").strip() for name in profile_branches if str(name or "").strip())
			)

	filters: dict[str, Any] = {}
	candidate_names: list[str] = []
	if company_branches:
		candidate_names = (
			[name for name in company_branches if name in allowed] if restricted else company_branches
		)
	elif restricted:
		candidate_names = allowed
	if restricted and not candidate_names:
		return []
	if candidate_names:
		filters["name"] = ["in", candidate_names]
	if text:
		filters["name"] = (
			["like", f"%{text}%"]
			if not candidate_names
			else ["in", [name for name in candidate_names if text.lower() in name.lower()]]
		)

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
			"description": company,
		}
		for row in rows
	]
