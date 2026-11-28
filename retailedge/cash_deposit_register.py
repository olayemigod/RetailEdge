from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.cash_custody import (
	CASH_DEPOSIT_TYPE,
	PAYMENT_ENTRY_DOCTYPE,
	require_cash_custody_fields_installed,
)
from retailedge.payment_history import (
	_assert_read_permission,
	_clean,
	_normalise_docstatus,
	_page_size,
	_resolve_branch_condition,
	_validate_dates,
)
from retailedge.setup_roles import user_has_retailedge_role

REVIEW_ROLES = ("RetailEdgeManager", "RetailEdgeBranchManager", "RetailEdgeAuditor")
ACCOUNTING_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}
STATE_NAMES = {0: "draft", 1: "submitted", 2: "cancelled"}

REGISTER_FIELDS = [
	"name",
	"posting_date",
	"creation",
	"modified",
	"company",
	"retailedge_branch",
	"retailedge_cashier",
	"retailedge_pos_opening_shift",
	"paid_from",
	"paid_to",
	"bank_account",
	"reference_no",
	"paid_amount",
	"paid_from_account_currency",
	"docstatus",
]


def _build_register_filters(
	*,
	company: str,
	branch: str = "",
	cashier: str = "",
	opening_shift: str = "",
	bank_account: str = "",
	docstatus: str = "all",
	from_date: str = "",
	to_date: str = "",
) -> dict[str, Any]:
	"""Intersect native read authority with deposit identity and operational scope."""
	if not frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read"):
		frappe.throw(_("You do not have permission to view cash deposits."), frappe.PermissionError)

	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	reviewer = user == "Administrator" or bool(roles & ACCOUNTING_ROLES) or any(
		user_has_retailedge_role(role, user=user) for role in REVIEW_ROLES
	)
	is_cashier = user_has_retailedge_role("RetailEdgeCashier", user=user)
	if user == "Guest" or not (reviewer or is_cashier):
		frappe.throw(_("You do not have permission to view cash deposits."), frappe.PermissionError)

	company = _clean(company)
	if not company:
		frappe.throw(_("Company is required."))
	_assert_read_permission("Company", company)
	require_cash_custody_fields_installed()
	branch_field, condition, _scope = _resolve_branch_condition(company, _clean(branch))
	# Deposits carry an explicit RetailEdge Branch. Never silently fall back to
	# another dimension or widen a missing restricted attribution.
	if branch_field != "retailedge_branch":
		frappe.throw(_("Cash Deposit branch attribution is not ready. Contact your administrator."))

	filters: dict[str, Any] = {
		"company": company,
		"payment_type": "Internal Transfer",
		"retailedge_cash_custody_type": CASH_DEPOSIT_TYPE,
	}
	if condition is not None:
		filters[branch_field] = condition

	cashier = _clean(cashier)
	if not reviewer:
		if cashier and cashier != user:
			frappe.throw(_("You can only view your own cash deposits."), frappe.PermissionError)
		cashier = user
	if cashier:
		filters["retailedge_cashier"] = cashier
	if _clean(opening_shift):
		filters["retailedge_pos_opening_shift"] = _clean(opening_shift)
	if _clean(bank_account):
		filters["bank_account"] = _clean(bank_account)
	state = _normalise_docstatus(docstatus)
	if state is not None:
		filters["docstatus"] = state
	from_date, to_date = _validate_dates(from_date, to_date)
	if from_date and to_date:
		filters["posting_date"] = ["between", [from_date, to_date]]
	elif from_date:
		filters["posting_date"] = [">=", from_date]
	elif to_date:
		filters["posting_date"] = ["<=", to_date]
	return filters


@frappe.whitelist(methods=["GET"])
def list_cash_deposits(
	company: str,
	branch: str = "",
	cashier: str = "",
	opening_shift: str = "",
	bank_account: str = "",
	docstatus: str = "all",
	from_date: str = "",
	to_date: str = "",
	search: str = "",
	page: int | str = 1,
	page_size: int | str = 25,
) -> dict[str, Any]:
	"""Read existing Payment Entries only; no posting or privilege elevation."""
	filters = _build_register_filters(
		company=company, branch=branch, cashier=cashier, opening_shift=opening_shift,
		bank_account=bank_account, docstatus=docstatus, from_date=from_date, to_date=to_date,
	)
	search = _clean(search)
	or_filters = []
	if search:
		or_filters = [
			[field, "like", f"%{search}%"]
			for field in ("name", "reference_no", "retailedge_pos_opening_shift")
		]
	page = max(1, cint(page) or 1)
	page_size = _page_size(page_size)
	rows = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=REGISTER_FIELDS,
		order_by="posting_date desc, creation desc, name desc",
		start=(page - 1) * page_size,
		page_length=page_size + 1,
	)
	# The aggregate uses exactly the same native and product scope as the page.
	# Never present current-page amounts as complete register totals. Keep
	# currencies separate even if a historical entry violates the deposit policy.
	groups = frappe.get_list(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=[
			"docstatus",
			"paid_from_account_currency as currency",
			{"COUNT": "name", "as": "count"},
			{"SUM": "paid_amount", "as": "amount"},
		],
		group_by="docstatus, paid_from_account_currency",
		order_by="docstatus asc, paid_from_account_currency asc",
		page_length=0,
	)
	totals: dict[str, list[dict[str, Any]]] = {state: [] for state in STATE_NAMES.values()}
	for group in groups:
		state = STATE_NAMES.get(cint(group.get("docstatus")))
		if state is not None:
			totals[state].append({
				"currency": group.get("currency") or "",
				"count": cint(group.get("count")),
				"amount": flt(group.get("amount")),
			})
	return {
		"rows": rows[:page_size],
		"totals": totals,
		"pagination": {
			"page": page,
			"page_size": page_size,
			"has_previous": page > 1,
			"has_next": len(rows) > page_size,
		},
	}
