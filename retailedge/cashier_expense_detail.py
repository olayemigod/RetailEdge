from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.cashier_expense import get_effective_expense_status, user_has_any_role, user_is_reviewer
from retailedge.cashier_expense_accounting import (
	attempt_direct_cashier_expense_posting,
	get_cashier_expense_posting_permissions,
)
from retailedge.cashier_expense_posting import (
	POSTING_REFRESH_ROLES,
	get_cashier_expense_posting_settings,
	get_effective_cashier_expense_posting_settings,
	refresh_cashier_expense_posting_readiness,
)
from retailedge.workflow_actions import apply_document_workflow_action
from retailedge.workflow_readiness import get_workflow_readiness
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
	doc = frappe.get_doc(EXPENSE_DOCTYPE, expense["name"])
	workflow_readiness = get_workflow_readiness(doctype=EXPENSE_DOCTYPE, doc=doc)
	return {
		"expense": expense,
		"workflow_readiness": workflow_readiness,
		"actions": _workflow_actions(expense, doc=doc, workflow_readiness=workflow_readiness),
	}


def _workflow_actions(
	expense: dict[str, Any],
	*,
	doc=None,
	workflow_readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
	"""Expose only currently relevant EdgeSuite actions; mutation endpoints remain authoritative."""
	status = get_effective_expense_status(expense)
	docstatus = int(expense.get("docstatus") or 0)
	ledger_status = str(expense.get("ledger_status") or "").strip()
	user = frappe.session.user
	roles = set(frappe.get_roles(user) or [])
	reviewer = bool(user_is_reviewer(user))
	workflow_readiness = workflow_readiness or {}
	workflow_controlled = str(workflow_readiness.get("source") or "") == "frappe"
	workflow_actions = list(workflow_readiness.get("available_actions") or []) if workflow_controlled else []
	self_cashier = str(expense.get("cashier") or "").strip() == str(user or "").strip()
	is_system_manager = "System Manager" in roles
	doc = doc or frappe.get_doc(EXPENSE_DOCTYPE, expense["name"])

	posting = get_effective_cashier_expense_posting_settings(
		doc,
		settings=get_cashier_expense_posting_settings(),
	)
	posting_enabled = bool(posting.get("enabled"))
	controlled_posting = posting.get("posting_mode") == "Controlled Posting"

	can_write_expense = bool(
		frappe.has_permission(EXPENSE_DOCTYPE, "write", doc=str(expense.get("name") or ""))
	)
	can_submit_for_review = bool(
		not workflow_controlled
		and docstatus == 0
		and can_write_expense
		and frappe.has_permission(EXPENSE_DOCTYPE, "submit", doc=str(expense.get("name") or ""))
	)
	can_review_submitted = bool(
		not workflow_controlled
		and controlled_posting
		and reviewer
		and can_write_expense
		and docstatus == 1
		and status == "Submitted"
	)
	can_reopen = bool(
		not workflow_controlled
		and controlled_posting
		and reviewer
		and can_write_expense
		and docstatus == 1
		and status in {"Rejected", "Pending Ledger"}
	)

	posting_permissions = get_cashier_expense_posting_permissions(
		doc,
		settings=posting,
		automatic=False,
	)
	can_post_permissions = bool(posting_permissions.get("can_post"))
	can_post = bool(
		docstatus == 1
		and status not in {"Cancelled", "Rejected", "Posted"}
		and ledger_status != "Posted"
		and posting_enabled
		and posting.get("posting_document_type") == "Journal Entry"
		and can_post_permissions
		and bool(expense.get("posting_ready"))
	)

	can_refresh = bool(
		docstatus == 1
		and status not in {"Cancelled", "Posted"}
		and ledger_status != "Posted"
		and user_has_any_role(user=user, roles=POSTING_REFRESH_ROLES)
	)

	reasons: list[str] = []
	if workflow_controlled:
		if not workflow_actions:
			reasons.append(
				str(workflow_readiness.get("message") or "").strip()
				or _("No Cashier Expense workflow action is currently available to this user.")
			)
	elif docstatus == 0 and not can_submit_for_review:
		reasons.append(_("This draft requires submit permission before it can be submitted."))
	elif controlled_posting and docstatus == 1 and status == "Submitted" and not reviewer:
		reasons.append(_("This submitted expense requires a RetailEdge reviewer role before approval or rejection."))
	elif (not controlled_posting) and docstatus == 1 and ledger_status == "Pending Ledger" and not can_post:
		reasons.append(
			expense.get("posting_block_reason")
			or _("Accounting posting is pending an authorised poster with the required Journal Entry permissions.")
		)
	elif docstatus == 1 and status == "Pending Ledger" and not can_post:
		reasons.append(expense.get("posting_block_reason") or _("Posting requirements are not yet satisfied."))

	return {
		"can_submit_for_review": can_submit_for_review,
		"can_approve": bool(can_review_submitted and (not self_cashier or is_system_manager)),
		"can_reject": bool(can_review_submitted),
		"can_reopen": bool(can_reopen),
		"can_refresh_posting": can_refresh,
		"can_post_to_accounts": can_post,
		"workflow_controlled": workflow_controlled,
		"workflow_actions": workflow_actions,
		"posting_enabled": posting_enabled,
		"posting_mode": posting.get("posting_mode") or "",
		"posting_document_type": posting.get("posting_document_type") or "Journal Entry",
		"reasons": reasons,
	}


@frappe.whitelist(methods=["POST"])
def apply_cashier_expense_workflow_action(
	expense_name: str,
	action: str,
	expected_modified: str | None = None,
	expected_workflow_state: str | None = None,
) -> dict[str, Any]:
	"""Apply one active Frappe Workflow action, then refresh posting readiness.

	When Direct Posting is selected, reaching the configured submitted posting
	state may auto-post only if the acting user's merchant-configured role and
	normal Journal Entry permissions allow it. Otherwise the expense remains
	Pending Ledger for an authorised poster.
	"""
	scoped = get_cashier_expense_detail(expense_name)
	expense = scoped.get("expense") or {}
	workflow = scoped.get("workflow_readiness") or {}
	if str(workflow.get("source") or "") != "frappe":
		frappe.throw(_("Cashier Expense is not controlled by an active Frappe Workflow."))
	result = apply_document_workflow_action(
		doctype=EXPENSE_DOCTYPE,
		name=str(expense.get("name") or expense_name),
		action=str(action or "").strip(),
		expected_modified=str(expected_modified or ""),
		expected_state=str(expected_workflow_state or ""),
	)
	refresh_cashier_expense_posting_readiness(expense_name)
	doc = frappe.get_doc(EXPENSE_DOCTYPE, expense_name)
	posting_result = attempt_direct_cashier_expense_posting(doc)
	return {
		"workflow_result": result,
		"posting_result": posting_result,
		"detail": get_cashier_expense_detail(expense_name),
	}


@frappe.whitelist(methods=["POST"])
def submit_cashier_expense_for_review(
	expense_name: str,
	expected_modified: str | None = None,
) -> dict[str, Any]:
	"""Submit one draft Cashier Expense through native Frappe document submission."""
	expense_name = str(expense_name or "").strip()
	if not expense_name:
		frappe.throw(_("Cashier Expense is required."), frappe.ValidationError)

	# Reuse the scoped detail read first so branch/read containment is identical
	# to the EdgeSuite detail surface.
	scoped = get_cashier_expense_detail(expense_name)
	expense = scoped.get("expense") or {}
	if int(expense.get("docstatus") or 0) != 0:
		frappe.throw(_("Only a draft Cashier Expense can be submitted."), frappe.ValidationError)
	if expected_modified and str(expense.get("modified") or "") != str(expected_modified):
		frappe.throw(
			_("This Cashier Expense changed after you opened it. Refresh before submitting."),
			frappe.ValidationError,
		)

	doc = frappe.get_doc(EXPENSE_DOCTYPE, expense_name)
	if not doc.has_permission("write"):
		frappe.throw(_("You do not have permission to update this Cashier Expense."), frappe.PermissionError)
	if not doc.has_permission("submit"):
		frappe.throw(_("You do not have permission to submit this Cashier Expense."), frappe.PermissionError)

	# Native submit owns validation and the Draft → Submitted/Pending Ledger state.
	doc.submit()
	doc.reload()
	refresh_cashier_expense_posting_readiness(doc.name, log_action=False)
	result = get_cashier_expense_detail(doc.name)
	result["persistence"] = "native_submit"
	return result
