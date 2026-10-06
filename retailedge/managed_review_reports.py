from __future__ import annotations

from copy import deepcopy
from typing import Any

import frappe
from frappe import _
from frappe.desk.query_report import run as run_query_report
from frappe.utils import get_first_day, today

from retailedge.operating_context import get_allowed_operating_branches, get_operating_context


MAX_VISIBLE_ROWS = 1000

SURFACES: dict[str, dict[str, Any]] = {
	"pos-closing-variance": {
		"title": "Shift Reconciliation",
		"eyebrow": "Cash Control",
		"subtitle": "Reconcile opening cash, cash sales, till expenses and cash deposits against counted closing cash, then focus on exceptions.",
		"report_name": "RetailEdge Cash Shift Verification",
		"action": {"label": "Open Sales Audit Review", "route": "daily-sales-audit"},
		"visible_columns": (
			"shift_date",
			"branch",
			"pos_profile",
			"cashier",
			"closing_shift",
			"opening_cash",
			"cash_sales",
			"included_cashier_expenses",
			"cash_deposits",
			"expected_cash",
			"actual_closing_cash",
			"cash_variance",
			"cash_status",
			"review_status",
		),
		"column_labels": {
			"closing_shift": "Shift",
			"included_cashier_expenses": "Till Expenses",
			"actual_closing_cash": "Counted Cash",
			"review_status": "Audit Status",
		},
		"summary_labels": {
			"Actual Closing Cash": "Counted Cash",
		},
		"filters": (
			{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "required": True},
			{"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch"},
			{"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
			{"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
			{"fieldname": "pos_profile", "label": "POS Profile", "fieldtype": "Link", "options": "POS Profile"},
			{"fieldname": "cashier", "label": "Cashier", "fieldtype": "Link", "options": "User"},
			{"fieldname": "cash_status", "label": "Cash Status", "fieldtype": "Select", "options": ("", "Balanced", "Shortage", "Overage", "Needs Review", "Missing Opening Shift", "Missing Closing Shift")},
			{"fieldname": "review_status", "label": "Audit Status", "fieldtype": "Data"},
			{"fieldname": "only_unsynced", "label": "Only Unsynced Cash Invoices", "fieldtype": "Check"},
		),
	},
	"unmatched-bank-transactions": {
		"title": "Unmatched Bank Transactions",
		"eyebrow": "Bank Review",
		"subtitle": "Find bank transactions that still need matching, account resolution or review before reconciliation.",
		"report_name": "RetailEdge Unmatched Bank Transactions",
		"action": {"label": "Bank Matching & Reconciliation", "route": "bank-matching-reconciliation"},
		"filters": (
			{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company"},
			{"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch"},
			{"fieldname": "bank_account", "label": "Bank Account", "fieldtype": "Link", "options": "Bank Account"},
			{"fieldname": "from_date", "label": "From Date", "fieldtype": "Date", "required": True},
			{"fieldname": "to_date", "label": "To Date", "fieldtype": "Date", "required": True},
			{"fieldname": "direction", "label": "Direction", "fieldtype": "Select", "options": ("All", "Inflow", "Outflow"), "default": "All"},
			{"fieldname": "amount_from", "label": "Amount From", "fieldtype": "Currency"},
			{"fieldname": "amount_to", "label": "Amount To", "fieldtype": "Currency"},
			{"fieldname": "match_status", "label": "Review Status", "fieldtype": "Data"},
			{"fieldname": "account_resolution_status", "label": "Account Resolution", "fieldtype": "Select", "options": ("", "Resolved", "Unresolved")},
			{"fieldname": "include_candidate_preview", "label": "Include Candidate Preview", "fieldtype": "Check"},
			{"fieldname": "include_already_reviewed", "label": "Include Already Reviewed", "fieldtype": "Check"},
			{"fieldname": "include_rejected", "label": "Include Rejected", "fieldtype": "Check"},
			{"fieldname": "include_reconciled", "label": "Include Reconciled", "fieldtype": "Check"},
		),
	},
	"unmatched-bank-payments": {
		"title": "Unmatched Bank Payments",
		"eyebrow": "Payment Review",
		"subtitle": "Review payment events that have not yet been matched to bank activity.",
		"report_name": "RetailEdge Unmatched Bank Payment Events",
		"action": {"label": "Bank Matching & Reconciliation", "route": "bank-matching-reconciliation"},
		"filters": (
			{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company"},
			{"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch"},
			{"fieldname": "from_date", "label": "From Date", "fieldtype": "Date", "required": True},
			{"fieldname": "to_date", "label": "To Date", "fieldtype": "Date", "required": True},
			{"fieldname": "payment_event_type", "label": "Payment Event Type", "fieldtype": "Select", "options": ("All", "Payment Entry", "Invoice Payment Row", "POS Payment Row"), "default": "All"},
			{"fieldname": "mode_of_payment", "label": "Mode of Payment", "fieldtype": "Link", "options": "Mode of Payment"},
			{"fieldname": "payment_account", "label": "Payment Account", "fieldtype": "Link", "options": "Account"},
			{"fieldname": "include_candidate_preview", "label": "Include Candidate Preview", "fieldtype": "Check"},
			{"fieldname": "include_already_matched", "label": "Include Already Matched", "fieldtype": "Check"},
		),
	},
	"reconciliation-handoff": {
		"title": "Reconciliation Handoff",
		"eyebrow": "Bank Review",
		"subtitle": "See which reviewed matches are ready for reconciliation and which still need attention.",
		"report_name": "RetailEdge Reconciliation Handoff",
		"action": {"label": "Bank Matching & Reconciliation", "route": "bank-matching-reconciliation"},
		"filters": (
			{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company"},
			{"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch"},
			{"fieldname": "bank_account", "label": "Bank Account", "fieldtype": "Link", "options": "Bank Account"},
			{"fieldname": "from_date", "label": "From Date", "fieldtype": "Date", "required": True},
			{"fieldname": "to_date", "label": "To Date", "fieldtype": "Date", "required": True},
			{"fieldname": "handoff_status", "label": "Handoff Status", "fieldtype": "Select", "options": ("", "Ready for ERPNext Reconciliation", "Needs Review Before Reconciliation", "Not Eligible for Reconciliation", "Already Reconciled", "Exception / Manual Investigation Required")},
			{"fieldname": "match_type", "label": "Match Type", "fieldtype": "Data"},
			{"fieldname": "match_status", "label": "Match Status", "fieldtype": "Data"},
			{"fieldname": "candidate_doctype", "label": "Candidate Type", "fieldtype": "Select", "options": ("", "Payment Entry", "Sales Invoice")},
			{"fieldname": "include_already_reconciled", "label": "Include Already Reconciled", "fieldtype": "Check"},
			{"fieldname": "include_exceptions", "label": "Include Exceptions", "fieldtype": "Check", "default": 1},
			{"fieldname": "include_rejected_cancelled", "label": "Include Rejected / Cancelled", "fieldtype": "Check"},
		),
	},
	"daily-sales-audit-register": {
		"title": "Daily Sales Audit Register",
		"eyebrow": "Audit Review",
		"subtitle": "Review daily sales audits, cash movement, variance and approval status across the permitted operating scope.",
		"report_name": "RetailEdge Daily Sales Audit Register",
		"action": {"label": "Daily Sales Audit", "route": "daily-sales-audit"},
		"filters": (
			{"fieldname": "company", "label": "Company", "fieldtype": "Link", "options": "Company", "required": True},
			{"fieldname": "branch", "label": "Branch", "fieldtype": "Link", "options": "Branch"},
			{"fieldname": "pos_profile", "label": "POS Profile", "fieldtype": "Link", "options": "POS Profile"},
			{"fieldname": "cashier", "label": "Cashier", "fieldtype": "Link", "options": "User"},
			{"fieldname": "audit_status", "label": "Audit Status", "fieldtype": "Select", "options": ("", "Draft", "Ready for Review", "In Review", "Variance Found", "Approved", "Rejected", "Cancelled")},
			{"fieldname": "audit_result", "label": "Audit Result", "fieldtype": "Select", "options": ("", "Not Checked", "Balanced", "Shortage", "Overage", "Mixed Variance", "Requires Clarification")},
			{"fieldname": "from_date", "label": "From Date", "fieldtype": "Date"},
			{"fieldname": "to_date", "label": "To Date", "fieldtype": "Date"},
		),
	},
}

ALLOWED_LINK_DOCTYPES = {
	field["options"]
	for surface in SURFACES.values()
	for field in surface["filters"]
	if field.get("fieldtype") == "Link" and field.get("options")
}


def _surface(key: str) -> dict[str, Any]:
	key = str(key or "").strip()
	surface = SURFACES.get(key)
	if not surface:
		frappe.throw(_("Unknown review workspace."))
	return surface


def _customer_copy(value: Any) -> str:
	return (
		str(value or "")
		.replace("RetailEdge ", "")
		.replace("RetailEdge", "")
		.replace("EdgeSuite UI", "the application")
		.replace("EdgeSuite", "the application")
		.replace("ERPNext ", "")
		.replace("ERPNext", "")
		.strip()
	)


def _format_columns(surface: dict[str, Any], raw_columns: list[Any]) -> list[dict[str, Any]]:
	visible_columns = tuple(surface.get("visible_columns") or ())
	visible_set = set(visible_columns)
	column_labels = dict(surface.get("column_labels") or {})
	columns: list[dict[str, Any]] = []
	for raw_column in raw_columns:
		if isinstance(raw_column, str):
			fieldname = raw_column
			if visible_set and fieldname not in visible_set:
				continue
			columns.append(
				{
					"label": _customer_copy(column_labels.get(fieldname) or raw_column),
					"fieldname": fieldname,
					"fieldtype": "Data",
				}
			)
			continue
		column = dict(raw_column)
		if column.get("hidden"):
			continue
		fieldname = str(column.get("fieldname") or "").strip()
		if visible_set and fieldname not in visible_set:
			continue
		column["label"] = _customer_copy(
			column_labels.get(fieldname) or column.get("label") or fieldname
		)
		columns.append(column)
	if visible_columns:
		position = {fieldname: index for index, fieldname in enumerate(visible_columns)}
		columns.sort(key=lambda column: position.get(column.get("fieldname"), len(position)))
	return columns


def _default_filters(surface: dict[str, Any]) -> dict[str, Any]:
	context = get_operating_context() or {}
	defaults = {
		"company": str(context.get("company") or frappe.defaults.get_user_default("Company") or "").strip(),
		"branch": str(context.get("branch") or "").strip(),
		"from_date": str(get_first_day(today())),
		"to_date": today(),
	}
	for field in surface["filters"]:
		if "default" in field:
			defaults[field["fieldname"]] = field["default"]
	return defaults


@frappe.whitelist()
def get_review_report_context(surface_key: str) -> dict[str, Any]:
	surface = _surface(surface_key)
	filters = []
	for definition in surface["filters"]:
		field = deepcopy(definition)
		field["label"] = _customer_copy(field.get("label"))
		field["options"] = list(field.get("options") or []) if isinstance(field.get("options"), tuple) else field.get("options")
		filters.append(field)
	return {
		"surface_key": surface_key,
		"title": surface["title"],
		"eyebrow": surface["eyebrow"],
		"subtitle": surface["subtitle"],
		"filters": filters,
		"default_filters": _default_filters(surface),
		"action": surface.get("action") or {},
		"max_visible_rows": MAX_VISIBLE_ROWS,
	}


@frappe.whitelist()
def run_review_report(surface_key: str, filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	surface = _surface(surface_key)
	if isinstance(filters, str):
		filters = frappe.parse_json(filters)
	filters = frappe._dict(filters or {})
	result = run_query_report(
		report_name=surface["report_name"],
		filters=filters,
		ignore_prepared_report=True,
		are_default_filters=False,
	)
	rows = list(result.get("result") or result.get("rows") or [])
	truncated = len(rows) > MAX_VISIBLE_ROWS
	rows = rows[:MAX_VISIBLE_ROWS]
	columns = _format_columns(surface, list(result.get("columns") or []))
	summary_labels = dict(surface.get("summary_labels") or {})
	summary = []
	for card in result.get("report_summary") or result.get("summary") or []:
		card = dict(card)
		label = str(card.get("label") or "")
		card["label"] = _customer_copy(summary_labels.get(label) or label)
		card["datatype"] = card.get("datatype") or card.get("type") or "Data"
		card["type"] = card.get("type") or card["datatype"]
		summary.append(card)
	return {
		"columns": columns,
		"rows": rows,
		"summary": summary,
		"message": _customer_copy(result.get("message")),
		"truncated": truncated,
		"max_visible_rows": MAX_VISIBLE_ROWS,
	}


@frappe.whitelist()
def search_review_report_options(
	doctype: str,
	txt: str = "",
	company: str = "",
	branch: str = "",
	pos_profile: str = "",
	surface_key: str = "",
) -> list[dict[str, str]]:
	doctype = str(doctype or "").strip()
	txt = str(txt or "").strip()
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	pos_profile = str(pos_profile or "").strip()
	surface_key = str(surface_key or "").strip()
	if doctype not in ALLOWED_LINK_DOCTYPES:
		frappe.throw(_("Unsupported review filter search."), frappe.PermissionError)

	if surface_key == "pos-closing-variance" and doctype in {"Branch", "POS Profile", "User"}:
		from retailedge.daily_sales_audit_page import search_daily_sales_audit_page_options

		kind = {"Branch": "branch", "POS Profile": "pos_profile", "User": "cashier"}[doctype]
		return search_daily_sales_audit_page_options(
			kind=kind,
			txt=txt,
			company=company,
			branch=branch,
			pos_profile=pos_profile,
		)

	if doctype == "Branch":
		branches = get_allowed_operating_branches(company=company) if company else []
		return [
			{"value": branch_name, "label": branch_name}
			for branch_name in branches
			if not txt or txt.lower() in branch_name.lower()
		][:20]
	filters: dict[str, Any] = {}
	if txt:
		filters["name"] = ["like", f"%{txt}%"]
	if company and doctype in {"Bank Account", "POS Profile", "Cost Center", "Account"}:
		meta = frappe.get_meta(doctype)
		if meta.has_field("company"):
			filters["company"] = company
	if doctype in {"Cost Center", "Account"}:
		filters["is_group"] = 0
	if doctype == "User":
		filters["enabled"] = 1

	response = frappe.get_list(
		doctype,
		filters=filters,
		fields=["name"],
		order_by="name asc",
		limit_page_length=20,
	)
	return [{"value": row.name, "label": row.name} for row in response]
