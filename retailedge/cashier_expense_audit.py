from __future__ import annotations

from types import SimpleNamespace

import frappe
from frappe.utils import flt, now_datetime

from retailedge.cashier_expense import append_cashier_expense_action_log, user_is_reviewer
from retailedge.utils.settings import get_retailedge_settings


def get_cashier_expense_daily_audit_settings():
	settings = _safe_settings()
	return {
		"include_draft": bool(getattr(settings, "include_draft_cashier_expenses_in_daily_audit", 1)),
		"include_submitted": bool(getattr(settings, "include_submitted_cashier_expenses_in_daily_audit", 1)),
		"include_pending_ledger": bool(
			getattr(settings, "include_pending_ledger_cashier_expenses_in_daily_audit", 1)
		),
		"include_rejected": bool(getattr(settings, "include_rejected_cashier_expenses_in_daily_audit", 1)),
		"exclude_cancelled": bool(
			getattr(settings, "exclude_cancelled_cashier_expenses_from_daily_audit", 1)
		),
	}


def should_include_cashier_expense_in_daily_audit(expense, settings=None):
	settings = settings or get_cashier_expense_daily_audit_settings()
	doc = _coerce_expense(expense)
	status = getattr(doc, "expense_status", None) or ("Cancelled" if getattr(doc, "docstatus", 0) == 2 else "Draft")

	if getattr(doc, "docstatus", 0) == 2 or status == "Cancelled":
		if settings["exclude_cancelled"]:
			return {"include": False, "reason": "Cancelled expenses are excluded from Daily Audit readiness.", "status": status}
		return {"include": True, "reason": "Cancelled expenses are explicitly allowed by settings.", "status": status}

	if not cint_bool(getattr(doc, "include_in_daily_audit", 1)):
		return {"include": False, "reason": "This expense has been marked not to include in Daily Audit.", "status": status}

	status_map = {
		"Draft": settings["include_draft"],
		"Submitted": settings["include_submitted"],
		"Pending Ledger": settings["include_pending_ledger"],
		"Rejected": settings["include_rejected"],
		"Posted": True,
	}
	if not status_map.get(status, True):
		return {"include": False, "reason": f"{status} expenses are excluded by Daily Audit settings.", "status": status}

	return {"include": True, "reason": f"{status} expenses are included in Daily Audit readiness.", "status": status}


def get_cashier_expenses_for_daily_audit(filters=None):
	filters = frappe.parse_json(filters) if filters else {}
	settings = get_cashier_expense_daily_audit_settings()
	query_filters = _build_daily_audit_filters(filters, settings)
	rows = frappe.get_all(
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
			"amount",
			"expense_status",
			"ledger_status",
			"include_in_daily_audit",
			"daily_audit_inclusion_status",
			"daily_audit_classification",
			"daily_audit_note",
			"daily_audit_exclusion_reason",
			"docstatus",
		],
		limit_page_length=0,
		order_by="expense_date asc, creation asc",
	)
	for row in rows:
		decision = should_include_cashier_expense_in_daily_audit(row, settings=settings)
		row["daily_audit_should_include"] = 1 if decision["include"] else 0
		row["daily_audit_rule_reason"] = decision["reason"]
	return rows


def get_cashier_expense_daily_audit_totals(filters=None):
	rows = get_cashier_expenses_for_daily_audit(filters=filters)
	result = {
		"total_amount": 0.0,
		"count": 0,
		"included_amount": 0.0,
		"included_count": 0,
		"excluded_amount": 0.0,
		"excluded_count": 0,
		"by_status": {},
		"by_classification": {},
		"by_inclusion_status": {},
	}
	for row in rows:
		amount = flt(row.get("amount"))
		status = row.get("expense_status") or "Draft"
		classification = row.get("daily_audit_classification") or "Cash Expense"
		inclusion_status = row.get("daily_audit_inclusion_status") or "Pending Review"
		result["total_amount"] += amount
		result["count"] += 1
		if row.get("daily_audit_should_include"):
			result["included_amount"] += amount
			result["included_count"] += 1
		else:
			result["excluded_amount"] += amount
			result["excluded_count"] += 1
		_accumulate_bucket(result["by_status"], status, amount)
		_accumulate_bucket(result["by_classification"], classification, amount)
		_accumulate_bucket(result["by_inclusion_status"], inclusion_status, amount)

	return result


def mark_cashier_expense_included_for_daily_audit(expense_name, note=None):
	doc = _get_reviewable_expense(expense_name)
	values = {
		"include_in_daily_audit": 1,
		"daily_audit_inclusion_status": "Included",
		"daily_audit_note": note if note is not None else doc.get("daily_audit_note"),
		"daily_audit_exclusion_reason": None,
		"daily_audit_reviewed_by": frappe.session.user,
		"daily_audit_reviewed_on": now_datetime(),
	}
	frappe.db.set_value("RetailEdge Cashier Expense", doc.name, values, update_modified=True)
	append_cashier_expense_action_log(
		doc.name,
		action="Daily Audit Included",
		previous_status=doc.expense_status,
		new_status=doc.expense_status,
		remarks=note,
		context={"daily_audit_inclusion_status": "Included"},
	)
	return _review_payload(doc.name)


def mark_cashier_expense_excluded_from_daily_audit(expense_name, reason=None):
	if not reason:
		frappe.throw("Reason is required to exclude a cashier expense from Daily Audit.")
	doc = _get_reviewable_expense(expense_name)
	values = {
		"include_in_daily_audit": 0,
		"daily_audit_inclusion_status": "Excluded",
		"daily_audit_exclusion_reason": reason,
		"daily_audit_reviewed_by": frappe.session.user,
		"daily_audit_reviewed_on": now_datetime(),
	}
	frappe.db.set_value("RetailEdge Cashier Expense", doc.name, values, update_modified=True)
	append_cashier_expense_action_log(
		doc.name,
		action="Daily Audit Excluded",
		previous_status=doc.expense_status,
		new_status=doc.expense_status,
		remarks=reason,
		context={"daily_audit_inclusion_status": "Excluded"},
	)
	return _review_payload(doc.name)


def mark_cashier_expense_needs_clarification(expense_name, note=None):
	doc = _get_reviewable_expense(expense_name)
	values = {
		"include_in_daily_audit": 1,
		"daily_audit_inclusion_status": "Needs Clarification",
		"daily_audit_note": note if note is not None else doc.get("daily_audit_note"),
		"daily_audit_exclusion_reason": None,
		"daily_audit_reviewed_by": frappe.session.user,
		"daily_audit_reviewed_on": now_datetime(),
	}
	frappe.db.set_value("RetailEdge Cashier Expense", doc.name, values, update_modified=True)
	append_cashier_expense_action_log(
		doc.name,
		action="Daily Audit Needs Clarification",
		previous_status=doc.expense_status,
		new_status=doc.expense_status,
		remarks=note,
		context={"daily_audit_inclusion_status": "Needs Clarification"},
	)
	return _review_payload(doc.name)


def _build_daily_audit_filters(filters, settings):
	query_filters = {}
	if settings["exclude_cancelled"] and not filters.get("expense_status"):
		query_filters["docstatus"] = ["!=", 2]
		query_filters["expense_status"] = ["!=", "Cancelled"]
	for fieldname in (
		"company",
		"branch",
		"pos_profile",
		"cashier",
		"linked_pos_opening_shift",
		"linked_pos_closing_shift",
		"expense_category",
		"expense_status",
		"daily_audit_inclusion_status",
	):
		value = filters.get(fieldname)
		if value:
			query_filters[fieldname] = value
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["expense_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["expense_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["expense_date"] = ["<=", filters["to_date"]]
	return query_filters


def _coerce_expense(expense):
	if getattr(expense, "doctype", None) == "RetailEdge Cashier Expense":
		return expense
	if isinstance(expense, str):
		return frappe.get_doc("RetailEdge Cashier Expense", expense)
	if isinstance(expense, dict):
		return frappe._dict(expense)
	return expense


def _get_reviewable_expense(expense_name):
	if not user_is_reviewer():
		frappe.throw("You do not have reviewer access for Daily Audit cashier expense actions.", frappe.PermissionError)
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if doc.docstatus == 2 or doc.expense_status == "Cancelled":
		frappe.throw("Cancelled cashier expenses cannot be updated for Daily Audit readiness.")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to update this cashier expense.", frappe.PermissionError)
	return doc


def _review_payload(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	return {
		"name": doc.name,
		"include_in_daily_audit": doc.include_in_daily_audit,
		"daily_audit_inclusion_status": doc.daily_audit_inclusion_status,
		"daily_audit_reviewed_by": doc.daily_audit_reviewed_by,
		"daily_audit_reviewed_on": doc.daily_audit_reviewed_on,
	}


def _accumulate_bucket(buckets, key, amount):
	bucket = buckets.setdefault(key, {"count": 0, "amount": 0.0})
	bucket["count"] += 1
	bucket["amount"] = flt(bucket["amount"]) + flt(amount)


def _safe_settings():
	try:
		return get_retailedge_settings()
	except Exception:
		return SimpleNamespace()


def cint_bool(value):
	return 1 if str(value) in {"1", "True", "true"} or value is True else 0
