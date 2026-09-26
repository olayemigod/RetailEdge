from __future__ import annotations

from typing import Any

import frappe
from frappe import _

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

	return {"expense": dict(rows[0])}
