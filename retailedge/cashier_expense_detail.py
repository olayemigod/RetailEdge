from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.cashier_expense import get_effective_expense_status, user_has_any_role, user_is_reviewer
from retailedge.cashier_expense_accounting import CONTROLLED_POSTING_ROLES
from retailedge.cashier_expense_posting import POSTING_REFRESH_ROLES, get_cashier_expense_posting_settings
from retailedge.cashier_expense_read_scope import apply_cashier_expense_read_scope

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"


@frappe.whitelist()
def get_cashier_expense_detail(
	expense_name: str,
	company: str = "",
	branch: str = "",
) -> dict[str, Any]:
	"""Return one permission- and Branch-scoped Cashier Expense for EdgeSuite detail views."""
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

	expense = dict(rows[0])
	return {
		"expense": expense,
		"actions": _workflow_actions(expense),
	}


def _workflow_actions(expense: dict[str, Any]) -> dict[str, Any]:
	"""Expose only currently relevant EdgeSuite actions; mutation endpoints remain authoritative."""
	status = get_effective_expense_status(expense)
	docstatus = int(expense.get("docstatus") or 0)
	ledger_status = str(expense.get("ledger_status") or "").strip()
	user = frappe.session.user
	roles = set(frappe.get_roles(user) or [])
	reviewer = bool(user_is_reviewer(user))
	self_cashier = str(expense.get("cashier") or "").strip() == str(user or "").strip()
	is_system_manager = "System Manager" in roles

	can_write_expense = bool(
		frappe.has_permission(EXPENSE_DOCTYPE, "write", doc=str(expense.get("name") or ""))
	)
	can_review_submitted = reviewer and can_write_expense and docstatus == 1 and status == "Submitted"
	can_reopen = reviewer and can_write_expense and docstatus == 1 and status in {"Rejected", "Pending Ledger"}

	posting = get_cashier_expense_posting_settings()
	posting_enabled = bool(posting.get("enabled"))
	posting_role = bool(user_has_any_role(user=user, roles=CONTROLLED_POSTING_ROLES))
	can_post_permissions = bool(
		can_write_expense
		and frappe.has_permission("Journal Entry", "read")
		and frappe.has_permission("Journal Entry", "create")
		and frappe.has_permission("Journal Entry", "submit")
	)
	posting_status_allowed = (
		status == "Pending Ledger"
		if posting.get("require_approval_before_posting")
		else status in {"Submitted", "Pending Ledger"}
	)
	can_post = bool(
		docstatus == 1
		and status not in {"Cancelled", "Rejected", "Posted"}
		and ledger_status != "Posted"
		and posting_enabled
		and posting.get("posting_document_type") == "Journal Entry"
		and posting_role
		and can_post_permissions
		and posting_status_allowed
		and bool(expense.get("posting_ready"))
	)

	can_refresh = bool(
		docstatus == 1
		and status not in {"Cancelled", "Posted"}
		and ledger_status != "Posted"
		and user_has_any_role(user=user, roles=POSTING_REFRESH_ROLES)
	)

	return {
		"can_approve": bool(can_review_submitted and (not self_cashier or is_system_manager)),
		"can_reject": bool(can_review_submitted),
		"can_reopen": bool(can_reopen),
		"can_refresh_posting": can_refresh,
		"can_post_to_accounts": can_post,
		"posting_enabled": posting_enabled,
		"posting_mode": posting.get("posting_mode") or "",
		"posting_document_type": posting.get("posting_document_type") or "Journal Entry",
	}
