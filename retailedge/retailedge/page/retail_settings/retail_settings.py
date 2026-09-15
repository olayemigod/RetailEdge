from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt


SETTINGS_DOCTYPE = "RetailEdge Settings"

SETTINGS_GROUPS = (
	{
		"key": "sales-operations",
		"label": "Sales & Operations",
		"description": "Sales entry, posting-date controls and cost visibility.",
		"sections": (
			{
				"label": "Sales Controls",
				"fields": (
					"enable_posting_date_control",
					"allow_pos_posting_date_override",
					"posting_date_allowed_roles",
					"allow_guided_sales_update_stock_edit",
				),
			},
			{
				"label": "Cost Visibility",
				"fields": (
					"hide_cost_price_for_selected_roles",
					"cost_price_hidden_roles",
					"enable_sales_payment_audit",
				),
			},
		),
	},
	{
		"key": "cashier-expenses",
		"label": "Cashier Expenses",
		"description": "Cashier expense capture, shift controls and accounting-posting readiness.",
		"sections": (
			{
				"label": "Cashier Expense Controls",
				"fields": (
					"enable_cashier_expense_workflow",
					"require_cashier_expense_attachment",
					"include_cashier_expenses_in_variance_report",
					"require_open_shift_for_cashier_expense",
					"allow_cashier_expense_date_edit",
					"include_draft_cashier_expenses_in_cash_check",
					"include_rejected_cashier_expenses_in_cash_check",
					"allow_cashier_expense_without_cash_account",
				),
			},
			{
				"label": "Accounting Posting",
				"fields": (
					"enable_cashier_expense_accounting_posting",
					"cashier_expense_posting_document_type",
					"default_cashier_expense_payable_account",
					"require_cashier_expense_approval_before_posting",
					"allow_rejected_cashier_expense_posting",
					"cashier_expense_posting_remark_template",
				),
			},
		),
	},
	{
		"key": "business-expenses",
		"label": "Business Expenses",
		"description": "Direct non-POS expense capture, evidence, approval and accounting posting.",
		"sections": (
			{
				"label": "Expense Controls",
				"fields": (
					"enable_business_expenses",
					"business_expense_process",
					"require_business_expense_attachment",
					"default_business_expense_payment_account",
				),
			},
			{
				"label": "Accounting Posting",
				"fields": (
					"enable_business_expense_accounting_posting",
					"business_expense_posting_document_type",
					"business_expense_posting_workflow_state",
				),
			},
		),
	},
	{
		"key": "audit-controls",
		"label": "Audit & Branch Controls",
		"description": "Daily audit readiness, sales-audit review and branch default behaviour.",
		"sections": (
			{
				"label": "Daily Audit Readiness",
				"fields": (
					"include_draft_cashier_expenses_in_daily_audit",
					"include_submitted_cashier_expenses_in_daily_audit",
					"include_pending_ledger_cashier_expenses_in_daily_audit",
					"include_rejected_cashier_expenses_in_daily_audit",
					"exclude_cancelled_cashier_expenses_from_daily_audit",
				),
			},
			{
				"label": "Daily Sales Audit",
				"fields": (
					"enable_daily_sales_audit",
					"require_pos_closing_shift_for_daily_audit",
					"include_cashier_expenses_in_daily_sales_audit_preview",
					"include_rejected_cashier_expenses_in_daily_sales_audit_preview",
					"daily_sales_audit_variance_tolerance",
					"daily_sales_audit_reviewer_roles",
					"allow_self_review_daily_sales_audit",
				),
			},
			{
				"label": "Branch Defaults",
				"fields": (
					"enable_branch_default_application",
					"apply_branch_default_warehouse",
					"apply_branch_default_cost_center",
					"apply_branch_default_accounts",
					"apply_branch_default_pos_profile",
				),
			},
		),
	},
	{
		"key": "banking-reconciliation",
		"label": "Banking & Reconciliation",
		"description": "Bank match safeguards and controlled reconciliation execution.",
		"sections": (
			{
				"label": "Bank Matching",
				"fields": (
					"bank_auto_match_mode",
					"bank_auto_match_guidance",
					"enable_bank_auto_match",
					"auto_prepare_exact_bank_matches",
					"auto_confirm_exact_bank_matches",
					"minimum_auto_match_score",
					"require_exact_reference_for_auto_match",
					"require_same_bank_account_for_auto_match",
					"require_same_branch_for_auto_match",
					"allow_auto_match_payment_entry",
					"allow_auto_match_sales_invoice",
					"require_no_duplicate_candidate_for_auto_match",
					"require_no_active_review_for_auto_match",
				),
			},
			{
				"label": "Reconciliation Execution",
				"fields": (
					"enable_bank_reconciliation_execution",
					"require_reconciliation_dry_run_before_execution",
					"minimum_reconciliation_readiness_status",
					"allowed_reconciliation_execution_roles",
					"require_second_approval_for_reconciliation_execution",
				),
			},
		),
	},
	{
		"key": "platform-integration",
		"label": "Platform Integration",
		"description": "Optional shared platform services for payments, notifications and branch context.",
		"sections": (
			{
				"label": "Platform Services",
				"fields": (
					"enable_coreedge_integration",
					"coreedge_required_for_portal",
					"enable_coreedge_payment_requests",
					"enable_coreedge_notifications",
					"enable_coreedge_branch_context",
				),
			},
		),
	},
)


def _assert_permission(ptype: str) -> None:
	if not frappe.has_permission(SETTINGS_DOCTYPE, ptype=ptype):
		frappe.throw(_("You do not have permission to manage these settings."), frappe.PermissionError)


def _fieldnames() -> set[str]:
	return {
		fieldname
		for group in SETTINGS_GROUPS
		for section in group["sections"]
		for fieldname in section["fields"]
	}


def _customer_copy(value: Any) -> str:
	return (
		str(value or "")
		.replace("RetailEdge ", "")
		.replace("RetailEdge", "")
		.replace("EdgeSuite UI", "the application")
		.replace("EdgeSuite", "the application")
		.replace("ERPNext ", "")
		.replace("Frappe ", "")
		.strip()
	)


def _field_schema(df, value: Any) -> dict[str, Any]:
	fieldtype = df.fieldtype
	read_only = bool(cint(df.read_only))
	result = {
		"fieldname": df.fieldname,
		"label": _customer_copy(df.label or df.fieldname),
		"fieldtype": fieldtype,
		"description": _customer_copy(df.description or ""),
		"depends_on": df.depends_on or "",
		"read_only": read_only,
		"options": [],
		"link_doctype": "",
		"value": _customer_copy(value) if read_only and isinstance(value, str) else value,
	}
	if fieldtype == "Select":
		result["options"] = [line.strip() for line in str(df.options or "").splitlines() if line.strip()]
	elif fieldtype == "Link":
		result["link_doctype"] = str(df.options or "")
	elif fieldtype == "Table":
		result["fieldtype"] = "RoleList"
		result["link_doctype"] = "Role"
		result["value"] = [str(row.role) for row in (value or []) if getattr(row, "role", None)]
	return result


def _serialize_settings(doc) -> list[dict[str, Any]]:
	meta = frappe.get_meta(SETTINGS_DOCTYPE)
	groups = []
	for group in SETTINGS_GROUPS:
		sections = []
		for section in group["sections"]:
			fields = []
			for fieldname in section["fields"]:
				df = meta.get_field(fieldname)
				if not df:
					continue
				fields.append(_field_schema(df, doc.get(fieldname)))
			if fields:
				sections.append({"label": section["label"], "fields": fields})
		if sections:
			groups.append(
				{
					"key": group["key"],
					"label": group["label"],
					"description": group["description"],
					"sections": sections,
				}
			)
	return groups


@frappe.whitelist()
def get_settings_context() -> dict[str, Any]:
	_assert_permission("read")
	doc = frappe.get_single(SETTINGS_DOCTYPE)
	return {
		"title": _("Settings"),
		"groups": _serialize_settings(doc),
		"can_write": bool(frappe.has_permission(SETTINGS_DOCTYPE, ptype="write")),
	}


def _normalize_value(df, value: Any) -> Any:
	if df.fieldtype == "Check":
		return 1 if cint(value) else 0
	if df.fieldtype == "Int":
		return cint(value)
	if df.fieldtype in {"Currency", "Float", "Percent"}:
		return flt(value)
	if df.fieldtype == "Select":
		cleaned = str(value or "").strip()
		options = [line.strip() for line in str(df.options or "").splitlines() if line.strip()]
		if cleaned and cleaned not in options:
			frappe.throw(_("Invalid value for {0}.").format(df.label or df.fieldname))
		return cleaned
	if df.fieldtype in {"Data", "Small Text", "Text", "Link"}:
		return str(value or "").strip()
	return value


def _set_role_rows(doc, fieldname: str, values: Any) -> None:
	roles = []
	for value in values or []:
		role = str(value or "").strip()
		if not role or role in roles:
			continue
		if not frappe.db.exists("Role", role):
			frappe.throw(_("Role {0} does not exist.").format(role))
		roles.append(role)
	doc.set(fieldname, [{"role": role} for role in roles])


@frappe.whitelist()
def save_settings(values: dict[str, Any] | str) -> dict[str, Any]:
	_assert_permission("write")
	if isinstance(values, str):
		values = frappe.parse_json(values)
	if not isinstance(values, dict):
		frappe.throw(_("Settings values are required."))

	doc = frappe.get_single(SETTINGS_DOCTYPE)
	meta = frappe.get_meta(SETTINGS_DOCTYPE)
	allowed = _fieldnames()
	for fieldname, value in values.items():
		if fieldname not in allowed:
			continue
		df = meta.get_field(fieldname)
		if not df or cint(df.read_only):
			continue
		if df.fieldtype == "Table":
			_set_role_rows(doc, fieldname, value)
		else:
			doc.set(fieldname, _normalize_value(df, value))

	doc.save()
	return {
		"saved": True,
		"groups": _serialize_settings(doc),
		"can_write": True,
	}
