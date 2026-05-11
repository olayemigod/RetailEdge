from __future__ import annotations

import frappe
from frappe.utils import flt, now_datetime


def get_reviewer_roles() -> set[str]:
	return {
		"System Manager",
		"Accounts Manager",
		"RetailEdge Manager",
		"RetailEdge Branch Manager",
		"RetailEdge Auditor",
		"RetailEdgeManager",
		"RetailEdgeBranchManager",
		"RetailEdgeAuditor",
	}


def get_cashier_roles() -> set[str]:
	return {
		"RetailEdge Cashier",
		"RetailEdgeCashier",
	}


def user_has_any_role(user: str | None = None, roles: set[str] | None = None) -> bool:
	user = user or frappe.session.user
	if user == "Guest":
		return False
	roles = roles or set()
	return bool(set(frappe.get_roles(user)).intersection(set(roles)))


def user_is_reviewer(user: str | None = None) -> bool:
	return user_has_any_role(user=user, roles=get_reviewer_roles())


def submit_cashier_expense(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if doc.docstatus == 0:
		if not doc.has_permission("submit"):
			frappe.throw("You do not have permission to submit this cashier expense.", frappe.PermissionError)
		doc.submit()
	return _status_payload(doc)


def approve_cashier_expense(expense_name, remarks=None):
	doc = _get_reviewable_expense(expense_name)
	user = frappe.session.user
	user_roles = set(frappe.get_roles(user))
	if user == doc.cashier and "System Manager" not in user_roles:
		frappe.throw("Cashiers cannot approve their own expense unless they are System Manager.")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to review this cashier expense.", frappe.PermissionError)

	doc.expense_status = "Pending Ledger"
	doc.ledger_status = "Pending Ledger"
	doc.approved_by = user
	doc.approved_on = now_datetime()
	doc.rejected_by = None
	doc.rejected_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	return _status_payload(doc)


def reject_cashier_expense(expense_name, remarks=None):
	doc = _get_reviewable_expense(expense_name)
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to review this cashier expense.", frappe.PermissionError)

	doc.expense_status = "Rejected"
	doc.ledger_status = "Not Applicable"
	doc.rejected_by = frappe.session.user
	doc.rejected_on = now_datetime()
	doc.approved_by = None
	doc.approved_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	return _status_payload(doc)


def reopen_cashier_expense(expense_name, remarks=None):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	_assert_reviewer()
	if doc.docstatus != 1:
		frappe.throw("Only submitted cashier expenses can be reopened for review.")
	if doc.expense_status not in {"Rejected", "Pending Ledger"}:
		frappe.throw("Only Rejected or Pending Ledger expenses can be reopened.")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to reopen this cashier expense.", frappe.PermissionError)

	doc.expense_status = "Submitted"
	doc.ledger_status = "Not Applicable"
	doc.approved_by = None
	doc.approved_on = None
	doc.rejected_by = None
	doc.rejected_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	return _status_payload(doc)


def get_cashier_expense_summary(filters=None):
	filters = frappe.parse_json(filters) if filters else {}
	query_filters = _build_summary_filters(filters)
	rows = frappe.get_all(
		"RetailEdge Cashier Expense",
		filters=query_filters,
		fields=["expense_status", "amount"],
		limit_page_length=0,
	)
	summary = {}
	for row in rows:
		status = row.expense_status or "Draft"
		bucket = summary.setdefault(status, {"count": 0, "total_amount": 0.0})
		bucket["count"] += 1
		bucket["total_amount"] = flt(bucket["total_amount"]) + flt(row.amount)
	return summary


def get_cashier_expenses_for_variance(filters=None):
	filters = frappe.parse_json(filters) if filters else {}
	query_filters = _build_variance_filters(filters)
	return frappe.get_all(
		"RetailEdge Cashier Expense",
		filters=query_filters,
		fields=[
			"name",
			"expense_date",
			"company",
			"branch",
			"pos_profile",
			"cashier",
			"linked_pos_opening_shift",
			"linked_pos_closing_shift",
			"expense_category",
			"expense_account",
			"payment_account",
			"amount",
			"expense_status",
			"ledger_status",
			"description",
		],
		limit_page_length=0,
		order_by="expense_date asc, creation asc",
	)


def get_cashier_expense_totals_for_variance(filters=None):
	rows = get_cashier_expenses_for_variance(filters=filters)
	result = {
		"total_expense_amount": 0.0,
		"count": 0,
		"by_status": {
			"Draft": {"count": 0, "amount": 0.0},
			"Submitted": {"count": 0, "amount": 0.0},
			"Pending Ledger": {"count": 0, "amount": 0.0},
			"Rejected": {"count": 0, "amount": 0.0},
			"Posted": {"count": 0, "amount": 0.0},
		},
		"by_category": {},
	}
	for row in rows:
		amount = flt(row.get("amount"))
		status = row.get("expense_status") or "Draft"
		category = row.get("expense_category") or "Uncategorised"
		result["total_expense_amount"] = flt(result["total_expense_amount"]) + amount
		result["count"] += 1
		status_bucket = result["by_status"].setdefault(status, {"count": 0, "amount": 0.0})
		status_bucket["count"] += 1
		status_bucket["amount"] = flt(status_bucket["amount"]) + amount
		category_bucket = result["by_category"].setdefault(category, {"count": 0, "amount": 0.0})
		category_bucket["count"] += 1
		category_bucket["amount"] = flt(category_bucket["amount"]) + amount
	return result


def _get_reviewable_expense(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	_assert_reviewer()
	if doc.docstatus != 1:
		frappe.throw("Only submitted cashier expenses can be reviewed.")
	if doc.expense_status != "Submitted":
		frappe.throw("Only cashier expenses in Submitted status can be reviewed.")
	return doc


def _assert_reviewer():
	if not user_is_reviewer():
		frappe.throw("You do not have reviewer access for cashier expenses.", frappe.PermissionError)


def _status_payload(doc):
	return {
		"name": doc.name,
		"expense_status": doc.expense_status,
		"ledger_status": doc.ledger_status,
		"docstatus": doc.docstatus,
	}


def _build_summary_filters(filters):
	query_filters = {}
	for fieldname in ("company", "branch", "pos_profile", "cashier", "linked_pos_opening_shift", "expense_category", "expense_status"):
		value = filters.get(fieldname)
		if value:
			query_filters[fieldname] = value
	if filters.get("from_date"):
		query_filters["expense_date"] = [">=", filters["from_date"]]
	if filters.get("to_date"):
		if "expense_date" in query_filters and isinstance(query_filters["expense_date"], list):
			query_filters["expense_date"] = ["between", [filters["from_date"], filters["to_date"]]]
		else:
			query_filters["expense_date"] = ["<=", filters["to_date"]]
	return query_filters


def _build_variance_filters(filters):
	query_filters = {"docstatus": ["!=", 2], "expense_status": ["!=", "Cancelled"]}
	for fieldname in (
		"company",
		"branch",
		"pos_profile",
		"cashier",
		"linked_pos_opening_shift",
		"linked_pos_closing_shift",
		"expense_category",
	):
		value = filters.get(fieldname)
		if value:
			query_filters[fieldname] = value
	if filters.get("expense_status"):
		if isinstance(filters["expense_status"], (list, tuple)):
			query_filters["expense_status"] = ["in", list(filters["expense_status"])]
		else:
			query_filters["expense_status"] = filters["expense_status"]
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["expense_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["expense_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["expense_date"] = ["<=", filters["to_date"]]
	return query_filters
