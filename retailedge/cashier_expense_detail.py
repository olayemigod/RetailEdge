from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.cashier_expense import (
	approve_cashier_expense,
	get_effective_expense_status,
	reject_cashier_expense,
	reopen_cashier_expense,
	submit_cashier_expense,
	user_has_any_role,
	user_is_reviewer,
)
from retailedge.cashier_expense_accounting import (
	CONTROLLED_POSTING_ROLES,
	post_cashier_expense_to_accounts,
)
from retailedge.cashier_expense_posting import (
	POSTING_REFRESH_ROLES,
	build_cashier_expense_posting_preview,
	get_cashier_expense_posting_settings,
	refresh_cashier_expense_posting_readiness,
)
from retailedge.cashier_expense_read_scope import apply_cashier_expense_read_scope

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"


def _scoped_expense_row(
	expense_name: str,
	company: str = "",
	branch: str = "",
) -> dict[str, Any]:
	expense_name = str(expense_name or "").strip()
	company = str(company or "").strip()
	branch = str(branch or "").strip()
	if not expense_name:
		frappe.throw(_("Cashier Expense is required."), frappe.ValidationError)

	filters: dict[str, Any] = {"name": expense_name}
	if company:
		filters["company"] = company
	if branch:
		filters["branch"] = branch
	filters = apply_cashier_expense_read_scope(filters)

	fields = [
		"name",
		"company",
		"branch",
		"cashier",
		"pos_profile",
		"expense_date",
		"expense_category",
		"amount",
		"description",
		"attachment",
		"expense_account",
		"cost_center",
		"payment_account",
		"shift_opening_cash_amount",
		"shift_cash_sales_amount",
		"prior_shift_expense_amount",
		"available_shift_cash_before_expense",
		"available_shift_cash_after_expense",
		"cash_balance_source",
		"cash_control_message",
		"expense_status",
		"ledger_status",
		"entry_source",
		"cash_source",
		"cash_movement_status",
		"posting_mode_applied",
		"linked_pos_opening_shift",
		"linked_pos_closing_shift",
		"linked_daily_sales_audit",
		"approved_by",
		"approved_on",
		"rejected_by",
		"rejected_on",
		"review_remarks",
		"posting_reference_type",
		"posting_reference",
		"posting_ready",
		"posting_block_reason",
		"resolved_debit_account",
		"resolved_credit_account",
		"resolved_posting_cost_center",
		"review_required",
		"user_message",
		"daily_audit_inclusion_status",
		"daily_audit_classification",
		"daily_audit_note",
		"daily_audit_reviewed_by",
		"daily_audit_reviewed_on",
		"daily_audit_exclusion_reason",
		"docstatus",
		"modified",
	]

	rows = frappe.get_list(
		EXPENSE_DOCTYPE,
		filters=filters,
		fields=fields,
		limit_page_length=1,
	)
	if not rows:
		frappe.throw(
			_("Cashier Expense {0} was not found or is outside your permitted business scope.").format(
				expense_name
			),
			frappe.DoesNotExistError,
		)
	return dict(rows[0])


def _workflow_capabilities(doc, preview: dict[str, Any], settings: dict[str, Any]) -> dict[str, bool]:
	status = get_effective_expense_status(doc)
	roles = set(frappe.get_roles(frappe.session.user))
	can_write = bool(doc.has_permission("write"))
	is_reviewer = bool(user_is_reviewer())
	is_self = frappe.session.user == getattr(doc, "cashier", None)
	can_approve = (
		is_reviewer
		and can_write
		and doc.docstatus == 1
		and status == "Submitted"
		and (not is_self or "System Manager" in roles)
	)
	can_reject = is_reviewer and can_write and doc.docstatus == 1 and status == "Submitted"
	can_reopen = (
		is_reviewer
		and can_write
		and doc.docstatus == 1
		and status in {"Rejected", "Pending Ledger"}
	)
	can_submit = doc.docstatus == 0 and bool(doc.has_permission("submit"))
	can_refresh = user_has_any_role(roles=POSTING_REFRESH_ROLES)
	can_post = (
		bool(settings.get("enabled"))
		and settings.get("posting_document_type") == "Journal Entry"
		and bool(preview.get("posting_ready"))
		and can_write
		and user_has_any_role(roles=CONTROLLED_POSTING_ROLES)
		and all(
			frappe.has_permission("Journal Entry", ptype)
			for ptype in ("read", "create", "submit")
		)
	)
	return {
		"can_submit": can_submit,
		"can_approve": can_approve,
		"can_reject": can_reject,
		"can_reopen": can_reopen,
		"can_refresh_posting": can_refresh,
		"can_post_accounts": can_post,
	}


def _workflow_payload(doc) -> dict[str, Any]:
	settings = get_cashier_expense_posting_settings()
	preview = build_cashier_expense_posting_preview(doc)
	return {
		"capabilities": _workflow_capabilities(doc, preview, settings),
		"effective_status": get_effective_expense_status(doc),
		"posting_enabled": bool(settings.get("enabled")),
		"posting_mode": settings.get("posting_mode"),
		"posting_document_type": settings.get("posting_document_type"),
		"posting_ready": bool(preview.get("posting_ready")),
		"posting_block_reason": preview.get("posting_block_reason"),
		"posting_preview": preview.get("posting_preview"),
	}


@frappe.whitelist()
def get_cashier_expense_detail(
	expense_name: str,
	company: str = "",
	branch: str = "",
) -> dict[str, Any]:
	"""Return one permission- and Branch-scoped Cashier Expense for EdgeSuite workflow views."""
	row = _scoped_expense_row(expense_name, company=company, branch=branch)
	doc = frappe.get_doc(EXPENSE_DOCTYPE, row["name"])
	return {
		"expense": row,
		"workflow": _workflow_payload(doc),
	}


@frappe.whitelist(methods=["POST"])
def apply_cashier_expense_workflow_action(
	expense_name: str,
	action: str,
	remarks: str = "",
	expected_modified: str | None = None,
	company: str = "",
	branch: str = "",
) -> dict[str, Any]:
	"""Apply one governed Cashier Expense lifecycle action and return refreshed EdgeSuite detail."""
	row = _scoped_expense_row(expense_name, company=company, branch=branch)
	doc = frappe.get_doc(EXPENSE_DOCTYPE, row["name"])
	if expected_modified and str(doc.modified or "") != str(expected_modified):
		frappe.throw(_("This Cashier Expense changed after you opened it. Refresh before continuing."))

	action = str(action or "").strip().lower().replace("-", "_")
	remarks = str(remarks or "").strip()
	settings = get_cashier_expense_posting_settings()
	preview = build_cashier_expense_posting_preview(doc)
	capabilities = _workflow_capabilities(doc, preview, settings)
	capability_by_action = {
		"submit": "can_submit",
		"approve": "can_approve",
		"reject": "can_reject",
		"reopen": "can_reopen",
		"refresh_posting": "can_refresh_posting",
		"post_accounts": "can_post_accounts",
	}
	capability = capability_by_action.get(action)
	if not capability:
		frappe.throw(_("Unsupported Cashier Expense workflow action."), frappe.ValidationError)
	if not capabilities.get(capability):
		frappe.throw(
			_("You do not have permission or the Cashier Expense is not eligible for this action."),
			frappe.PermissionError,
		)

	if action == "submit":
		submit_cashier_expense(doc.name)
	elif action == "approve":
		approve_cashier_expense(doc.name, remarks=remarks or None)
	elif action == "reject":
		reject_cashier_expense(doc.name, remarks=remarks or None)
	elif action == "reopen":
		reopen_cashier_expense(doc.name, remarks=remarks or None)
	elif action == "refresh_posting":
		refresh_cashier_expense_posting_readiness(doc.name)
	elif action == "post_accounts":
		post_cashier_expense_to_accounts(
			doc.name,
			expected_modified=expected_modified,
		)

	return get_cashier_expense_detail(
		doc.name,
		company=company,
		branch=branch,
	)
