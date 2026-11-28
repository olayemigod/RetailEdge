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
from retailedge.operating_context import validate_operating_branch

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


# Own-deposit history is an operational projection, not general accounting read.
# Exclude internal timestamps and ledger-account links from this exception.
OWN_REGISTER_FIELDS = [
	field for field in REGISTER_FIELDS
	if field not in {"creation", "modified", "paid_from", "paid_to"}
]


def _register_access_mode() -> str:
	user = frappe.session.user
	if not user or user == "Guest":
		return ""
	roles = set(frappe.get_roles(user))
	cashier = "RetailEdgeCashier" in roles
	reviewer = user == "Administrator" or bool(roles & ACCOUNTING_ROLES) or bool(roles.intersection(REVIEW_ROLES))
	if not (cashier or reviewer):
		return ""
	if frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "read"):
		return "native"
	# The canonical cashier intentionally lacks generic Payment Entry authority.
	# Allow only the source-bound read projection below, never native CRUD.
	return "own" if cashier else ""


def _own_shift_names(company: str, opening_shift: str) -> list[str]:
	if not frappe.db.exists("DocType", "POS Opening Shift"):
		return []
	if not frappe.has_permission("POS Opening Shift", "read"):
		return []
	filters: dict[str, Any] = {
		"company": company, "user": frappe.session.user, "docstatus": ["in", [1, 2]],
	}
	if opening_shift:
		filters["name"] = opening_shift
	# Use native shift permissions; a deposit marker alone is not proof of identity.
	rows = frappe.get_list("POS Opening Shift", filters=filters, fields=["name"], page_length=0)
	return [row.name for row in rows]


def _own_branch_condition(company: str, condition: Any) -> Any:
	if condition is not None:
		return condition
	# An unrestricted legacy operating scope is not itself a grant to all
	# accounting branches. Validate every permission-visible Branch instead.
	rows = frappe.get_list("Branch", fields=["name"], page_length=0)
	allowed = [
		row.name for row in rows
		if validate_operating_branch(company=company, branch=row.name, user=frappe.session.user, throw=False).get("allowed")
	]
	return ["in", allowed]


def _empty_own_scope(filters: dict[str, Any]) -> bool:
	return any(filters.get(field) == ["in", []] for field in ("retailedge_pos_opening_shift", "retailedge_branch"))


def _register_reader(mode: str):
	# Private dispatch only: both public callers construct and validate the
	# complete fixed deposit scope before any query. No client-selected fields.
	if mode == "native":
		return frappe.get_list
	if mode == "own":
		return frappe.get_all
	frappe.throw(_("You do not have permission to view cash deposits."), frappe.PermissionError)


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
	"""Intersect native read or own-deposit operational authority with verified scope."""
	mode = _register_access_mode()
	if not mode:
		frappe.throw(_("You do not have permission to view cash deposits."), frappe.PermissionError)

	user = frappe.session.user
	roles = set(frappe.get_roles(user))
	reviewer = mode == "native" and (
		user == "Administrator" or bool(roles & ACCOUNTING_ROLES) or bool(roles.intersection(REVIEW_ROLES))
	)

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
	if mode == "own":
		condition = _own_branch_condition(company, condition)
	if condition is not None:
		filters[branch_field] = condition

	cashier = _clean(cashier)
	if not reviewer:
		if cashier and cashier != user:
			frappe.throw(_("You can only view your own cash deposits."), frappe.PermissionError)
		cashier = user
	if cashier:
		filters["retailedge_cashier"] = cashier
	if mode == "own":
		filters["retailedge_pos_opening_shift"] = ["in", _own_shift_names(company, _clean(opening_shift))]
	elif _clean(opening_shift):
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
def search_cash_deposit_options(
	company: str, branch: str = "", kind: str = "", txt: str = "",
	cashier: str = "", opening_shift: str = "", bank_account: str = "",
) -> list[dict[str, str]]:
	"""Return selectable values from the same permission-visible deposit population."""
	fields = {"cashier": "retailedge_cashier", "shift": "retailedge_pos_opening_shift", "bank": "bank_account"}
	field = fields.get(kind)
	if not field:
		frappe.throw(_("Choose a supported cash deposit filter."))
	filters = _build_register_filters(
		company=company, branch=branch,
		cashier=cashier if kind != "cashier" else "",
		opening_shift=opening_shift if kind != "shift" else "",
		bank_account=bank_account if kind != "bank" else "",
	)
	# AND the search with (rather than overwrite) mandatory ownership scope.
	if _empty_own_scope(filters):
		return []
	rows = _register_reader(_register_access_mode())(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		or_filters=[[field, "like", f"%{_clean(txt)}%"]],
		fields=[field], group_by=field, order_by=f"{field} asc", page_length=25,
	)
	return [
		{"value": str(row[field]), "label": str(row[field])}
		for row in rows if row.get(field)
	]


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
	"""Read existing deposits only; no accounting permission grant or posting."""
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
	mode = _register_access_mode()
	if _empty_own_scope(filters):
		return {
			"rows": [], "totals": {state: [] for state in STATE_NAMES.values()},
			"native_review": mode == "native",
			"pagination": {"page": page, "page_size": page_size, "has_previous": page > 1, "has_next": False},
		}
	reader = _register_reader(mode)
	rows = reader(
		PAYMENT_ENTRY_DOCTYPE,
		filters=filters,
		or_filters=or_filters,
		fields=REGISTER_FIELDS if mode == "native" else OWN_REGISTER_FIELDS,
		order_by="posting_date desc, creation desc, name desc",
		start=(page - 1) * page_size,
		page_length=page_size + 1,
	)
	# The aggregate uses exactly the same native and product scope as the page.
	# Never present current-page amounts as complete register totals. Keep
	# currencies separate even if a historical entry violates the deposit policy.
	groups = reader(
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
		"native_review": mode == "native",
		"pagination": {
			"page": page,
			"page_size": page_size,
			"has_previous": page > 1,
			"has_next": len(rows) > page_size,
		},
	}
