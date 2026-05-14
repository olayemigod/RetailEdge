from __future__ import annotations

import json
from types import SimpleNamespace

import frappe
from frappe.utils import flt, now_datetime

from retailedge.utils.settings import get_retailedge_settings


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


def get_effective_expense_status(doc) -> str:
	if isinstance(doc, dict):
		docstatus = doc.get("docstatus", 0)
		expense_status = doc.get("expense_status")
	else:
		docstatus = getattr(doc, "docstatus", 0)
		expense_status = getattr(doc, "expense_status", None)
	if docstatus == 2 or expense_status == "Cancelled":
		return "Cancelled"
	if docstatus == 1 and (not expense_status or expense_status == "Draft"):
		return "Submitted"
	return expense_status or "Draft"


def append_cashier_expense_action_log(
	doc_or_name,
	action,
	previous_status=None,
	new_status=None,
	remarks=None,
	context=None,
):
	doc = doc_or_name
	if getattr(doc_or_name, "doctype", None) != "RetailEdge Cashier Expense":
		doc = frappe.get_doc("RetailEdge Cashier Expense", doc_or_name)

	context_text = _serialise_log_context(context)
	next_idx = frappe.db.count(
		"RetailEdge Cashier Expense Action Log",
		{
			"parent": doc.name,
			"parenttype": "RetailEdge Cashier Expense",
			"parentfield": "action_logs",
		},
	) + 1
	log_row = frappe.get_doc(
		{
			"doctype": "RetailEdge Cashier Expense Action Log",
			"parent": doc.name,
			"parenttype": "RetailEdge Cashier Expense",
			"parentfield": "action_logs",
			"idx": next_idx,
			"action": action,
			"action_by": frappe.session.user,
			"action_on": now_datetime(),
			"previous_status": previous_status,
			"new_status": new_status,
			"remarks": remarks,
			"context": context_text,
		}
	)
	log_row.db_insert()
	return log_row


def submit_cashier_expense(expense_name):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	if doc.docstatus == 0:
		if not doc.has_permission("submit"):
			frappe.throw("You do not have permission to submit this cashier expense.", frappe.PermissionError)
		doc.submit()
	return _status_payload(doc)


def approve_cashier_expense(expense_name, remarks=None):
	doc = _get_reviewable_expense(expense_name, action="approve")
	user = frappe.session.user
	user_roles = set(frappe.get_roles(user))
	if user == doc.cashier and "System Manager" not in user_roles:
		frappe.throw("Cashiers cannot approve their own expense unless they are System Manager.")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to review this cashier expense.", frappe.PermissionError)

	previous_status = get_effective_expense_status(doc)
	doc.expense_status = "Pending Ledger"
	doc.ledger_status = "Pending Ledger"
	doc.approved_by = user
	doc.approved_on = now_datetime()
	doc.rejected_by = None
	doc.rejected_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	append_cashier_expense_action_log(
		doc,
		action="Approved",
		previous_status=previous_status,
		new_status=doc.expense_status,
		remarks=remarks,
		context={"ledger_status": doc.ledger_status},
	)
	return _status_payload(doc)


def reject_cashier_expense(expense_name, remarks=None):
	doc = _get_reviewable_expense(expense_name, action="reject")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to review this cashier expense.", frappe.PermissionError)

	previous_status = get_effective_expense_status(doc)
	doc.expense_status = "Rejected"
	doc.ledger_status = "Not Applicable"
	doc.rejected_by = frappe.session.user
	doc.rejected_on = now_datetime()
	doc.approved_by = None
	doc.approved_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	append_cashier_expense_action_log(
		doc,
		action="Rejected",
		previous_status=previous_status,
		new_status=doc.expense_status,
		remarks=remarks,
		context={"ledger_status": doc.ledger_status},
	)
	return _status_payload(doc)


def reopen_cashier_expense(expense_name, remarks=None):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	_assert_reviewer()
	_assert_mutable_review_status(doc, action="reopen")
	if doc.docstatus != 1:
		frappe.throw("Only submitted cashier expenses can be reopened.")
	current_status = get_effective_expense_status(doc)
	if current_status not in {"Rejected", "Pending Ledger"}:
		frappe.throw("Only rejected or pending ledger expenses can be reopened.")
	if not doc.has_permission("write"):
		frappe.throw("You do not have permission to reopen this cashier expense.", frappe.PermissionError)

	previous_status = current_status
	doc.expense_status = "Submitted"
	doc.ledger_status = "Not Applicable"
	doc.approved_by = None
	doc.approved_on = None
	doc.rejected_by = None
	doc.rejected_on = None
	if remarks is not None:
		doc.review_remarks = remarks
	doc.save(ignore_permissions=True)
	append_cashier_expense_action_log(
		doc,
		action="Reopened",
		previous_status=previous_status,
		new_status=doc.expense_status,
		remarks=remarks,
		context={"ledger_status": doc.ledger_status},
	)
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


def get_cashier_expense_totals(filters=None):
	query_filters = _coerce_cashier_expense_filters(filters)
	rows = frappe.get_list(
		"RetailEdge Cashier Expense",
		filters=query_filters,
		fields=["name", "amount", "expense_status", "ledger_status", "posting_ready", "docstatus"],
		limit_page_length=0,
		order_by="creation desc",
	)
	result = {
		"count": 0,
		"total_amount": 0.0,
		"by_status": {},
		"by_ledger_status": {},
		"posting_ready_count": 0,
		"posting_blocked_count": 0,
	}
	for row in rows:
		amount = flt(row.get("amount"))
		status = get_effective_expense_status(row)
		ledger_status = row.get("ledger_status") or "Not Applicable"
		result["count"] += 1
		result["total_amount"] += amount
		status_bucket = result["by_status"].setdefault(status, {"count": 0, "amount": 0.0})
		status_bucket["count"] += 1
		status_bucket["amount"] = flt(status_bucket["amount"]) + amount
		ledger_bucket = result["by_ledger_status"].setdefault(ledger_status, {"count": 0, "amount": 0.0})
		ledger_bucket["count"] += 1
		ledger_bucket["amount"] = flt(ledger_bucket["amount"]) + amount
		if row.get("posting_ready"):
			result["posting_ready_count"] += 1
		else:
			result["posting_blocked_count"] += 1
	return result


def get_cashier_expenses_for_variance(filters=None, include_rejected=True):
	filters = frappe.parse_json(filters) if filters else {}
	settings = _safe_variance_settings()
	if not getattr(settings, "include_cashier_expenses_in_variance_report", 1):
		return []

	include_draft = filters.get("include_draft")
	if include_draft is None:
		include_draft = bool(getattr(settings, "include_draft_cashier_expenses_in_cash_check", 1))

	include_rejected = filters.get("include_rejected", include_rejected)
	if "include_rejected" not in filters and include_rejected is True:
		include_rejected = bool(getattr(settings, "include_rejected_cashier_expenses_in_cash_check", include_rejected))

	query_filters = _build_variance_filters(
		filters,
		include_rejected=include_rejected,
		include_draft=include_draft,
	)
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


def _get_reviewable_expense(expense_name, action="review"):
	doc = frappe.get_doc("RetailEdge Cashier Expense", expense_name)
	_normalise_expense_status_for_submitted_doc(doc)
	_assert_reviewer()
	_assert_mutable_review_status(doc, action=action)
	if doc.docstatus != 1:
		if action == "approve":
			frappe.throw("Only submitted cashier expenses can be approved.")
		if action == "reject":
			frappe.throw("Only submitted cashier expenses can be rejected.")
		frappe.throw("Only submitted cashier expenses can be reviewed.")
	if get_effective_expense_status(doc) != "Submitted":
		if action == "approve":
			frappe.throw("Only submitted cashier expenses can be approved.")
		if action == "reject":
			frappe.throw("Only submitted cashier expenses can be rejected.")
		frappe.throw("Only cashier expenses in Submitted status can be reviewed.")
	return doc


def _assert_reviewer():
	if not user_is_reviewer():
		frappe.throw("You do not have reviewer access for cashier expenses.", frappe.PermissionError)


def _assert_mutable_review_status(doc, action="review"):
	if doc.docstatus == 2 or doc.expense_status == "Cancelled":
		frappe.throw("Cancelled cashier expenses cannot be changed.")
	if get_effective_expense_status(doc) == "Posted":
		frappe.throw("Posted cashier expenses are reserved for a future ledger phase.")


def _normalise_expense_status_for_submitted_doc(doc):
	effective_status = get_effective_expense_status(doc)
	if getattr(doc, "expense_status", None) == effective_status:
		return
	doc.expense_status = effective_status
	if getattr(doc, "name", None) and getattr(doc, "doctype", None) == "RetailEdge Cashier Expense":
		try:
			frappe.db.set_value(
				"RetailEdge Cashier Expense",
				doc.name,
				"expense_status",
				effective_status,
				update_modified=False,
			)
		except Exception:
			pass


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


def _coerce_cashier_expense_filters(filters):
	if not filters:
		return {}
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters
	if isinstance(parsed, list):
		return parsed
	if isinstance(parsed, frappe._dict):
		parsed = dict(parsed)
	if isinstance(parsed, dict):
		return _build_summary_filters(parsed)
	return {}


def _build_variance_filters(filters, include_rejected=True, include_draft=True):
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
	else:
		excluded_statuses = ["Cancelled"]
		if not include_draft:
			excluded_statuses.append("Draft")
		if not include_rejected:
			excluded_statuses.append("Rejected")
		if len(excluded_statuses) == 1:
			query_filters["expense_status"] = ["!=", "Cancelled"]
		else:
			query_filters["expense_status"] = ["not in", excluded_statuses]
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["expense_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["expense_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["expense_date"] = ["<=", filters["to_date"]]
	return query_filters


def _safe_variance_settings():
	try:
		return get_retailedge_settings()
	except Exception:
		return SimpleNamespace(
			include_cashier_expenses_in_variance_report=1,
			include_draft_cashier_expenses_in_cash_check=1,
			include_rejected_cashier_expenses_in_cash_check=1,
		)


def _serialise_log_context(context):
	if context is None:
		return None
	if isinstance(context, str):
		return context
	try:
		return json.dumps(context, default=str, sort_keys=True)
	except Exception:
		return str(context)
