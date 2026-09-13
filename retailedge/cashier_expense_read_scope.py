from __future__ import annotations

import frappe

from retailedge.branch_context import user_has_global_branch_access
from retailedge.operating_context import get_operational_branch_scope

CASHIER_EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
NO_BRANCH_SCOPE_SENTINEL = "__never__"
_EQUALITY_OPERATORS = {"=", "=="}


def apply_cashier_expense_read_scope(filters, *, user: str | None = None):
	"""Apply permission-aware Company/Branch scope to Cashier Expense read filters.

	Dictionary filters remain dictionaries. Supported Frappe list filters remain
	lists so existing callers keep their query shape, but Company/Branch predicates
	must be simple equality predicates before authoritative scope is appended.
	"""
	user = user or getattr(getattr(frappe, "session", None), "user", "Administrator")
	_assert_cashier_expense_read_access()

	if isinstance(filters, frappe._dict):
		filters = dict(filters)
	if isinstance(filters, dict):
		return _scope_dict_filters(dict(filters), user=user)
	if isinstance(filters, list):
		rows = [list(row) if isinstance(row, tuple) else row for row in filters]
		return _scope_list_filters(rows, user=user)

	frappe.throw(
		"RetailEdge Cashier Expense read filters must be a dictionary or a Frappe filter list.",
		frappe.ValidationError,
	)


def _scope_dict_filters(filters: dict, *, user: str):
	company = _clean_scalar_filter(filters.get("company"), fieldname="Company")
	branch = _clean_scalar_filter(filters.get("branch"), fieldname="Branch")
	company = company or str(frappe.defaults.get_user_default("Company") or "").strip()

	if not company:
		if user_has_global_branch_access(user=user):
			filters.pop("company", None)
			return filters
		frappe.throw(
			"Company is required before loading RetailEdge Cashier Expense reads.",
			frappe.ValidationError,
		)

	filters["company"] = company
	_scope_branch_filter(filters, company=company, branch=branch, user=user)
	return filters


def _scope_list_filters(filters: list, *, user: str):
	company = _extract_list_equality(filters, "company")
	branch = _extract_list_equality(filters, "branch")
	company = company or str(frappe.defaults.get_user_default("Company") or "").strip()

	if not company:
		if user_has_global_branch_access(user=user):
			return filters
		frappe.throw(
			"Company is required before loading RetailEdge Cashier Expense reads.",
			frappe.ValidationError,
		)

	if not _has_list_filter(filters, "company"):
		filters.append([CASHIER_EXPENSE_DOCTYPE, "company", "=", company])

	scope = get_operational_branch_scope(company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed_branches = _clean_allowed_branches(scope)

	if branch:
		if restricted and branch not in allowed_branches:
			_throw_branch_denied(branch)
		return filters

	if not restricted:
		return filters
	if len(allowed_branches) == 1:
		filters.append([CASHIER_EXPENSE_DOCTYPE, "branch", "=", allowed_branches[0]])
	elif allowed_branches:
		filters.append([CASHIER_EXPENSE_DOCTYPE, "branch", "in", allowed_branches])
	else:
		filters.append([CASHIER_EXPENSE_DOCTYPE, "branch", "=", NO_BRANCH_SCOPE_SENTINEL])
	return filters


def _scope_branch_filter(filters: dict, *, company: str, branch: str, user: str):
	scope = get_operational_branch_scope(company, user=user)
	restricted = bool(scope.get("restricted"))
	allowed_branches = _clean_allowed_branches(scope)

	if branch:
		if restricted and branch not in allowed_branches:
			_throw_branch_denied(branch)
		filters["branch"] = branch
		return

	if not restricted:
		filters.pop("branch", None)
	elif len(allowed_branches) == 1:
		filters["branch"] = allowed_branches[0]
	elif allowed_branches:
		filters["branch"] = ["in", allowed_branches]
	else:
		filters["branch"] = NO_BRANCH_SCOPE_SENTINEL


def _extract_list_equality(filters: list, fieldname: str) -> str:
	values: list[str] = []
	for row in filters:
		parsed = _parse_list_filter(row)
		if not parsed:
			continue
		doctype, row_fieldname, operator, value = parsed
		if row_fieldname != fieldname:
			continue
		if doctype and doctype != CASHIER_EXPENSE_DOCTYPE:
			continue
		if operator not in _EQUALITY_OPERATORS:
			frappe.throw(
				f"RetailEdge Cashier Expense {fieldname.title()} list filters must use equality before Branch scope is applied.",
				frappe.ValidationError,
			)
		cleaned = _clean_scalar_filter(value, fieldname=fieldname.title())
		if cleaned:
			values.append(cleaned)

	unique = list(dict.fromkeys(values))
	if len(unique) > 1:
		frappe.throw(
			f"RetailEdge Cashier Expense {fieldname.title()} list filters are ambiguous.",
			frappe.ValidationError,
		)
	return unique[0] if unique else ""


def _has_list_filter(filters: list, fieldname: str) -> bool:
	for row in filters:
		parsed = _parse_list_filter(row)
		if not parsed:
			continue
		doctype, row_fieldname, _operator, _value = parsed
		if row_fieldname == fieldname and (not doctype or doctype == CASHIER_EXPENSE_DOCTYPE):
			return True
	return False


def _parse_list_filter(row):
	if not isinstance(row, (list, tuple)):
		return None
	if len(row) == 4:
		doctype, fieldname, operator, value = row
		return (
			str(doctype or "").strip(),
			str(fieldname or "").strip(),
			str(operator or "").strip().lower(),
			value,
		)
	if len(row) == 3:
		fieldname, operator, value = row
		return "", str(fieldname or "").strip(), str(operator or "").strip().lower(), value
	return None


def _clean_scalar_filter(value, *, fieldname: str) -> str:
	if value in (None, ""):
		return ""
	if isinstance(value, (list, tuple, dict, set)):
		frappe.throw(
			f"RetailEdge Cashier Expense {fieldname} must be a single value.",
			frappe.ValidationError,
		)
	return str(value).strip()


def _clean_allowed_branches(scope: dict) -> list[str]:
	return [
		str(value).strip()
		for value in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(value or "").strip()
	]


def _assert_cashier_expense_read_access():
	if frappe.has_permission(CASHIER_EXPENSE_DOCTYPE, "read"):
		return
	frappe.throw(
		"You do not have permission to read RetailEdge Cashier Expense records.",
		frappe.PermissionError,
	)


def _throw_branch_denied(branch: str):
	frappe.throw(
		frappe._("You do not have active RetailEdge Branch access to Branch {0}.").format(branch),
		frappe.PermissionError,
	)
