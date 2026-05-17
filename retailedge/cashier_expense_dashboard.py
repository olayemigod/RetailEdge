from __future__ import annotations

import frappe
from frappe.utils import flt

from retailedge.branch_context import get_branch_query_filters
from retailedge.cashier_expense import get_effective_expense_status, user_has_any_role


def get_cashier_expense_dashboard_roles() -> set[str]:
	return {
		"System Manager",
		"Accounts Manager",
		"Accounts User",
		"RetailEdge Manager",
		"RetailEdgeManager",
		"RetailEdge Branch Manager",
		"RetailEdgeBranchManager",
		"RetailEdge Auditor",
		"RetailEdgeAuditor",
	}


def assert_can_access_cashier_expense_dashboard(user: str | None = None):
	if user_has_any_role(user=user, roles=get_cashier_expense_dashboard_roles()):
		return
	frappe.throw(
		"You do not have permission to access the RetailEdge Cashier Expense dashboard summary.",
		frappe.PermissionError,
	)


def get_cashier_expense_dashboard_summary(filters=None):
	query_filters = _build_dashboard_filters(filters)
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
			"expense_category",
			"amount",
			"expense_status",
			"ledger_status",
			"posting_ready",
			"daily_audit_inclusion_status",
			"description",
			"docstatus",
		],
		limit_page_length=0,
		order_by="expense_date desc, creation desc",
	)

	summary = {
		"total_expenses": 0.0,
		"expense_count": 0,
		"draft_count": 0,
		"submitted_count": 0,
		"pending_ledger_count": 0,
		"rejected_count": 0,
		"cancelled_count": 0,
		"posting_ready_count": 0,
		"posting_blocked_count": 0,
		"daily_audit_pending_review_count": 0,
		"daily_audit_included_count": 0,
		"daily_audit_excluded_count": 0,
		"daily_audit_needs_clarification_count": 0,
		"top_cashiers": [],
		"top_categories": [],
		"recent_expenses": [],
	}

	cashier_totals = {}
	category_totals = {}

	for row in rows:
		status = get_effective_expense_status(row)
		amount = flt(row.get("amount"))
		inclusion_status = row.get("daily_audit_inclusion_status") or "Pending Review"
		posting_ready = cint_bool(row.get("posting_ready"))

		if status == "Cancelled":
			summary["cancelled_count"] += 1
		else:
			summary["total_expenses"] += amount
			summary["expense_count"] += 1
			if posting_ready:
				summary["posting_ready_count"] += 1
			else:
				summary["posting_blocked_count"] += 1

			if inclusion_status == "Pending Review":
				summary["daily_audit_pending_review_count"] += 1
			elif inclusion_status == "Included":
				summary["daily_audit_included_count"] += 1
			elif inclusion_status == "Excluded":
				summary["daily_audit_excluded_count"] += 1
			elif inclusion_status == "Needs Clarification":
				summary["daily_audit_needs_clarification_count"] += 1

			_accumulate(cashier_totals, row.get("cashier") or "Unassigned", amount)
			_accumulate(category_totals, row.get("expense_category") or "Uncategorised", amount)

		status_key = _status_key(status)
		if status_key and not (status == "Cancelled"):
			summary[status_key] += 1

		summary["recent_expenses"].append(
			{
				"name": row.get("name"),
				"expense_date": row.get("expense_date"),
				"company": row.get("company"),
				"branch": row.get("branch"),
				"pos_profile": row.get("pos_profile"),
				"cashier": row.get("cashier"),
				"expense_category": row.get("expense_category"),
				"amount": amount,
				"expense_status": status,
				"ledger_status": row.get("ledger_status"),
				"daily_audit_inclusion_status": inclusion_status,
				"posting_ready": posting_ready,
				"description": row.get("description"),
			}
		)

	summary["top_cashiers"] = _top_buckets(cashier_totals)
	summary["top_categories"] = _top_buckets(category_totals)
	summary["recent_expenses"] = summary["recent_expenses"][:5]
	return summary


def _build_dashboard_filters(filters):
	filters = frappe.parse_json(filters) if filters else {}
	if isinstance(filters, frappe._dict):
		filters = dict(filters)
	if not isinstance(filters, dict):
		return {}

	query_filters = {}
	query_filters.update(
		(get_branch_query_filters(
			"RetailEdge Cashier Expense",
			user=getattr(getattr(frappe, "session", None), "user", "Administrator"),
			company=filters.get("company"),
			branch=filters.get("branch"),
		).get("filters") or {})
	)
	for fieldname in ("company", "branch", "pos_profile", "cashier"):
		value = filters.get(fieldname)
		if value and fieldname not in query_filters:
			query_filters[fieldname] = value

	if filters.get("from_date") and filters.get("to_date"):
		query_filters["expense_date"] = ["between", [filters["from_date"], filters["to_date"]]]
	elif filters.get("from_date"):
		query_filters["expense_date"] = [">=", filters["from_date"]]
	elif filters.get("to_date"):
		query_filters["expense_date"] = ["<=", filters["to_date"]]

	return query_filters


def _status_key(status: str) -> str | None:
	return {
		"Draft": "draft_count",
		"Submitted": "submitted_count",
		"Pending Ledger": "pending_ledger_count",
		"Rejected": "rejected_count",
		"Cancelled": "cancelled_count",
	}.get(status)


def _accumulate(buckets, key, amount):
	bucket = buckets.setdefault(key, {"name": key, "count": 0, "amount": 0.0})
	bucket["count"] += 1
	bucket["amount"] = flt(bucket["amount"]) + flt(amount)


def _top_buckets(buckets):
	return sorted(
		buckets.values(),
		key=lambda row: (-flt(row.get("amount")), -int(row.get("count", 0)), row.get("name") or ""),
	)[:5]


def cint_bool(value):
	return 1 if str(value) in {"1", "true", "True"} or value is True else 0
