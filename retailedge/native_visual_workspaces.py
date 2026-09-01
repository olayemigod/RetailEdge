from __future__ import annotations

from typing import Any

import frappe
from frappe import _

RECENT_LIMIT = 12

WORKSPACES: dict[str, dict[str, Any]] = {
	"service-warranty": {
		"page_route": "service-warranty-control",
		"title": "Service & Warranty",
		"eyebrow": "After-sales Control",
		"description": "Review warranty and maintenance activity in EdgeSuite, then use ERPNext for authoritative creation, editing, submission, scheduling, and lifecycle actions.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Warranty Claims",
				"target": "Warranty Claim",
				"description": "Customer warranty cases, serial eligibility, complaint status, and ERPNext resolution lifecycle.",
				"fields": ("customer", "serial_no", "complaint_date", "status"),
			},
			{
				"kind": "doctype",
				"label": "Maintenance Schedules",
				"target": "Maintenance Schedule",
				"description": "Authoritative ERPNext schedules and planned after-sales service visits.",
				"fields": ("customer", "transaction_date", "status"),
			},
			{
				"kind": "doctype",
				"label": "Maintenance Visits",
				"target": "Maintenance Visit",
				"description": "Recorded maintenance visits and their native ERPNext document status.",
				"fields": ("customer", "mntc_date", "completion_status", "status"),
			},
		),
	},
	"sales-team": {
		"page_route": "sales-team-control",
		"title": "Sales Team, Targets & Commissions",
		"eyebrow": "Sales Performance Control",
		"description": "Keep the RetailEdge sales-team experience in EdgeSuite while ERPNext remains authoritative for Sales Person, Sales Partner, targets, and commission reports.",
		"sources": (
			{
				"kind": "page",
				"label": "Salesperson Performance",
				"target": "salesperson-performance-dashboard",
				"description": "Open the existing RetailEdge EdgeSuite salesperson performance dashboard.",
			},
			{
				"kind": "doctype",
				"label": "Sales People",
				"target": "Sales Person",
				"description": "ERPNext Sales Person hierarchy and target ownership.",
				"fields": ("sales_person_name", "parent_sales_person", "is_group", "enabled"),
			},
			{
				"kind": "doctype",
				"label": "Sales Partners",
				"target": "Sales Partner",
				"description": "ERPNext partner master data used by selling and commission reporting.",
				"fields": ("partner_name", "commission_rate", "territory"),
			},
			{
				"kind": "report",
				"label": "Sales Person Commissions",
				"target": "Sales Person Commission Summary",
				"description": "Open ERPNext's authoritative Sales Person commission summary.",
			},
			{
				"kind": "report",
				"label": "Sales Partner Commissions",
				"target": "Sales Partner Commission Summary",
				"description": "Open ERPNext's authoritative Sales Partner commission summary.",
			},
			{
				"kind": "report",
				"label": "Sales Person Targets",
				"target": "Sales Person Target Variance Based On Item Group",
				"description": "Review ERPNext target variance by item group for Sales People.",
			},
			{
				"kind": "report",
				"label": "Sales Partner Targets",
				"target": "Sales Partner Target Variance based on Item Group",
				"description": "Review ERPNext target variance by item group for Sales Partners.",
			},
		),
	},
	"budget-control": {
		"page_route": "budget-control",
		"title": "Budgeting & Cost Control",
		"eyebrow": "Accounting Control",
		"description": "Review budgets and cost-centre structure in EdgeSuite while ERPNext remains authoritative for budget rules, enforcement, submission, and variance calculations.",
		"sources": (
			{
				"kind": "doctype",
				"label": "Budgets",
				"target": "Budget",
				"description": "ERPNext budgets against Cost Center or Project, including fiscal period and control settings.",
				"fields": ("company", "budget_against", "from_fiscal_year", "to_fiscal_year"),
			},
			{
				"kind": "report",
				"label": "Budget Variance",
				"target": "Budget Variance Report",
				"description": "Open ERPNext's authoritative budget-versus-actual report with its native filters and accounting dimensions.",
			},
			{
				"kind": "doctype",
				"label": "Cost Centers",
				"target": "Cost Center",
				"description": "ERPNext cost-centre hierarchy used for accounting classification and budget control.",
				"fields": ("company", "parent_cost_center", "is_group", "disabled"),
			},
		),
	},
}


@frappe.whitelist()
def get_native_visual_workspace(workspace: str) -> dict[str, Any]:
	"""Return a bounded, permission-aware EdgeSuite overview over native ERPNext capabilities."""
	_assert_authenticated()
	workspace = str(workspace or "").strip()
	config = WORKSPACES.get(workspace)
	if not config:
		frappe.throw(_("Unsupported RetailEdge control workspace."))

	sources: list[dict[str, Any]] = []
	for source in config["sources"]:
		resolved = _resolve_source(source)
		if resolved:
			sources.append(resolved)

	if not sources:
		frappe.throw(
			_("You do not have permission to open any of the ERPNext capabilities in this workspace."),
			frappe.PermissionError,
		)

	company = str(frappe.defaults.get_user_default("Company") or "")
	branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	)
	return {
		"workspace": workspace,
		"page_route": config["page_route"],
		"title": _(config["title"]),
		"eyebrow": _(config["eyebrow"]),
		"description": _(config["description"]),
		"company": company,
		"branch": branch,
		"user_name": frappe.utils.get_fullname(frappe.session.user),
		"sources": sources,
		"recent_limit": RECENT_LIMIT,
		"source_of_truth": "ERPNext",
		"read_only_overview": 1,
		"native_handoff": 1,
	}


def _resolve_source(source: dict[str, Any]) -> dict[str, Any] | None:
	kind = source["kind"]
	if kind == "doctype":
		return _resolve_doctype_source(source)
	if kind == "report":
		return _resolve_report_source(source)
	if kind == "page":
		return _resolve_page_source(source)
	return None


def _resolve_doctype_source(source: dict[str, Any]) -> dict[str, Any] | None:
	doctype = source["target"]
	if not frappe.db.exists("DocType", doctype) or not frappe.has_permission(doctype, "read"):
		return None

	meta = frappe.get_meta(doctype)
	candidate_fields = [field for field in source.get("fields", ()) if meta.has_field(field)]
	fields = ["name", "modified", "docstatus", *candidate_fields]
	rows = frappe.get_list(
		doctype,
		fields=fields,
		order_by="modified desc",
		limit_page_length=RECENT_LIMIT,
	)
	columns = [
		{"fieldname": "name", "label": _("ID")},
		*[
			{
				"fieldname": fieldname,
				"label": _(meta.get_field(fieldname).label or fieldname.replace("_", " ").title()),
			}
			for fieldname in candidate_fields
		],
		{"fieldname": "modified", "label": _("Modified")},
	]
	return {
		"kind": "doctype",
		"label": _(source["label"]),
		"target": doctype,
		"description": _(source["description"]),
		"can_create": int(bool(frappe.has_permission(doctype, "create"))),
		"columns": columns,
		"rows": [dict(row) for row in rows],
		"preview_label": _("Recent {0}").format(min(len(rows), RECENT_LIMIT)),
	}


def _resolve_report_source(source: dict[str, Any]) -> dict[str, Any] | None:
	try:
		from frappe.desk.query_report import get_report_doc

		get_report_doc(source["target"])
	except frappe.PermissionError:
		return None
	except Exception:
		return None
	return {
		"kind": "report",
		"label": _(source["label"]),
		"target": source["target"],
		"description": _(source["description"]),
		"can_create": 0,
		"columns": [],
		"rows": [],
	}


def _resolve_page_source(source: dict[str, Any]) -> dict[str, Any] | None:
	if not frappe.db.exists("Page", source["target"]):
		return None
	return {
		"kind": "page",
		"label": _(source["label"]),
		"target": source["target"],
		"description": _(source["description"]),
		"can_create": 0,
		"columns": [],
		"rows": [],
	}


def _assert_authenticated() -> None:
	if not frappe.session.user or frappe.session.user == "Guest":
		frappe.throw(_("Sign in to open this RetailEdge control workspace."), frappe.PermissionError)
