from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.cash_custody import CASH_DEPOSIT_TYPE, CUSTODY_FIELD_DEFS, PAYMENT_ENTRY_DOCTYPE
from retailedge.branch_context import has_field
from retailedge.operating_context import get_operating_context
from retailedge.payment_history import (
	_assert_read_permission,
	_normalise_docstatus,
	_page_size,
	_resolve_branch_condition,
	_validate_dates,
)
from retailedge.setup_roles import user_has_retailedge_role

PAGE = "cash-deposits"
BRANCH_FIELD = "retailedge_branch"


def can_view_cash_deposits() -> bool:
	"""Native Page and Payment Entry read permission remain mandatory."""
	return bool(
		frappe.session.user not in ("Guest", "")
		and frappe.db.exists("Page", PAGE)
		and frappe.get_doc("Page", PAGE).is_permitted()
		and frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read")
	)


def _scope() -> tuple[str, Any, bool]:
	if not can_view_cash_deposits():
		frappe.throw(_("You do not have permission to view Cash Deposits."), frappe.PermissionError)
	if not all(has_field(PAYMENT_ENTRY_DOCTYPE, field) for field in (*CUSTODY_FIELD_DEFS, BRANCH_FIELD)):
		frappe.throw(_("Cash Deposits are not ready. Contact your administrator."))
	context = get_operating_context() or {}
	company = str(context.get("company") or "").strip()
	branch = str(context.get("branch") or "").strip()
	if not company:
		frappe.throw(_("Choose your working Company to view Cash Deposits."))
	_assert_read_permission("Company", company)
	own_only = user_has_retailedge_role("RetailEdgeCashier", user=frappe.session.user)
	if own_only and not branch:
		frappe.throw(_("Choose your working Branch to view your Cash Deposits."))
	field, condition, scope = _resolve_branch_condition(company, branch)
	if field != BRANCH_FIELD or (scope.get("restricted") and not scope.get("allowed_branches")):
		frappe.throw(_("Cash Deposits are not available for your current branch access."), frappe.PermissionError)
	return company, condition, own_only


@frappe.whitelist()
def list_cash_deposits(
	docstatus: str = "all",
	from_date: str = "",
	to_date: str = "",
	page: int = 1,
	page_size: int = 25,
) -> dict[str, Any]:
	"""Read native cash-deposit Payment Entries, including unsubmitted drafts.

	The caller cannot supply another cashier, company, branch or custody type.
	The current working context and native document permissions constrain every row.
	"""
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view Cash Deposits."), frappe.PermissionError)
	company, branch, own_only = _scope()
	resolved_status = _normalise_docstatus(docstatus)
	from_date, to_date = _validate_dates(from_date, to_date)
	filters: dict[str, Any] = {
		"company": company,
		"payment_type": "Internal Transfer",
		"retailedge_cash_custody_type": CASH_DEPOSIT_TYPE,
	}
	if branch is not None:
		filters[BRANCH_FIELD] = branch
	if own_only:
		filters["retailedge_cashier"] = frappe.session.user
	if resolved_status is not None:
		filters["docstatus"] = resolved_status
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]

	page_size = _page_size(page_size)
	page = max(1, cint(page))
	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		fields=[
			"name", "posting_date", "docstatus", "reference_no", "bank_account",
			"paid_from", "paid_to", "paid_amount", "paid_from_account_currency",
			BRANCH_FIELD, "retailedge_cashier", "retailedge_pos_opening_shift",
		],
		order_by="posting_date desc, creation desc, name desc",
		start=(page - 1) * page_size,
		page_length=page_size + 1,
	)
	return {
		"rows": [
			{
				"payment_entry": row.name,
				"posting_date": row.posting_date,
				"docstatus": cint(row.docstatus),
				"status": {0: "Draft", 1: "Submitted", 2: "Cancelled"}.get(cint(row.docstatus), "Unknown"),
				"reference_no": row.reference_no or "",
				"bank_account": row.bank_account or "",
				"from_account": row.paid_from or "",
				"to_account": row.paid_to or "",
				"amount": flt(row.paid_amount),
				"currency": row.paid_from_account_currency or "",
				"branch": row.get(BRANCH_FIELD) or "",
				"cashier": row.retailedge_cashier or "",
				"opening_shift": row.retailedge_pos_opening_shift or "",
				"can_print": bool(frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "print", doc=row.name)),
			}
			for row in rows[:page_size]
		],
		"company": company,
		"own_only": own_only,
		"pagination": {
			"page": page,
			"page_size": page_size,
			"has_previous": page > 1,
			"has_next": len(rows) > page_size,
		},
	}
