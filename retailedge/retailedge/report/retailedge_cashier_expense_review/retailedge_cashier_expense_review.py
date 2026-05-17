from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.branch_context import get_branch_query_filters
from retailedge.cashier_expense_audit import get_cashier_expenses_for_daily_audit


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_data(filters)
	return get_columns(), data, None, get_chart_data(data), get_report_summary(data)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Expense"), "fieldname": "name", "fieldtype": "Link", "options": "RetailEdge Cashier Expense", "width": 190},
		{"label": _("Expense Date"), "fieldname": "expense_date", "fieldtype": "Date", "width": 110},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 170},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 150},
		{"label": _("POS Profile"), "fieldname": "pos_profile", "fieldtype": "Link", "options": "POS Profile", "width": 160},
		{"label": _("Cashier"), "fieldname": "cashier", "fieldtype": "Link", "options": "User", "width": 170},
		{"label": _("Opening Shift"), "fieldname": "linked_pos_opening_shift", "fieldtype": "Link", "options": "POS Opening Shift", "width": 180},
		{"label": _("Closing Shift"), "fieldname": "linked_pos_closing_shift", "fieldtype": "Link", "options": "POS Closing Shift", "width": 180},
		{"label": _("Expense Category"), "fieldname": "expense_category", "fieldtype": "Link", "options": "RetailEdge Expense Category", "width": 170},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Expense Status"), "fieldname": "expense_status", "fieldtype": "Data", "width": 130},
		{"label": _("Ledger Status"), "fieldname": "ledger_status", "fieldtype": "Data", "width": 130},
		{"label": _("Posting Ready"), "fieldname": "posting_ready", "fieldtype": "Check", "width": 105},
		{"label": _("Posting Block Reason"), "fieldname": "posting_block_reason", "fieldtype": "Small Text", "width": 220},
		{"label": _("Daily Audit Include"), "fieldname": "include_in_daily_audit", "fieldtype": "Check", "width": 115},
		{"label": _("Daily Audit Inclusion Status"), "fieldname": "daily_audit_inclusion_status", "fieldtype": "Data", "width": 170},
		{"label": _("Daily Audit Classification"), "fieldname": "daily_audit_classification", "fieldtype": "Data", "width": 170},
		{"label": _("Daily Audit Note"), "fieldname": "daily_audit_note", "fieldtype": "Small Text", "width": 220},
		{"label": _("Daily Audit Exclusion Reason"), "fieldname": "daily_audit_exclusion_reason", "fieldtype": "Small Text", "width": 220},
		{"label": _("Payment Account"), "fieldname": "payment_account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Expense Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 170},
		{"label": _("Description"), "fieldname": "description", "fieldtype": "Small Text", "width": 240},
	]


def get_data(filters):
	branch_scope = get_branch_query_filters(
		"RetailEdge Cashier Expense",
		user=frappe.session.user,
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	if branch_scope.get("branch") and not filters.get("branch"):
		filters.branch = branch_scope["branch"]
	rows = get_cashier_expenses_for_daily_audit(filters=filters)
	if filters.get("posting_ready") is not None and str(filters.get("posting_ready")) != "":
		expected = 1 if str(filters.get("posting_ready")) in {"1", "true", "True"} else 0
		rows = [row for row in rows if cint_bool(row.get("posting_ready")) == expected]
	return append_totals_row(rows)


def get_report_summary(rows):
	summary = build_review_summary(get_visible_rows(rows))
	return [
		{
			"value": summary["total_amount"],
			"label": _("Total Expenses"),
			"datatype": "Currency",
			"indicator": "Blue",
		},
		{
			"value": summary["count"],
			"label": _("Expense Count"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": summary["pending_review_count"],
			"label": _("Pending Review Count"),
			"datatype": "Int",
			"indicator": "Orange" if summary["pending_review_count"] else "Green",
		},
		{
			"value": summary["included_amount"],
			"label": _("Included for Daily Audit Amount"),
			"datatype": "Currency",
			"indicator": "Green" if summary["included_amount"] else "Grey",
		},
		{
			"value": summary["excluded_amount"],
			"label": _("Excluded Amount"),
			"datatype": "Currency",
			"indicator": "Red" if summary["excluded_amount"] else "Grey",
		},
		{
			"value": summary["needs_clarification_count"],
			"label": _("Needs Clarification Count"),
			"datatype": "Int",
			"indicator": "Orange" if summary["needs_clarification_count"] else "Green",
		},
		{
			"value": summary["pending_ledger_amount"],
			"label": _("Pending Ledger Amount"),
			"datatype": "Currency",
			"indicator": "Orange" if summary["pending_ledger_amount"] else "Grey",
		},
		{
			"value": summary["rejected_amount"],
			"label": _("Rejected Amount"),
			"datatype": "Currency",
			"indicator": "Red" if summary["rejected_amount"] else "Grey",
		},
		{
			"value": summary["posting_ready_count"],
			"label": _("Posting Ready Count"),
			"datatype": "Int",
			"indicator": "Green" if summary["posting_ready_count"] else "Grey",
		},
		{
			"value": summary["posting_blocked_count"],
			"label": _("Posting Blocked Count"),
			"datatype": "Int",
			"indicator": "Red" if summary["posting_blocked_count"] else "Green",
		},
	]


def build_review_summary(rows):
	summary = {
		"total_amount": 0.0,
		"count": 0,
		"pending_review_count": 0,
		"included_amount": 0.0,
		"excluded_amount": 0.0,
		"needs_clarification_count": 0,
		"pending_ledger_amount": 0.0,
		"rejected_amount": 0.0,
		"posting_ready_count": 0,
		"posting_blocked_count": 0,
	}
	for row in rows:
		amount = flt(row.get("amount"))
		status = row.get("expense_status") or "Draft"
		inclusion_status = row.get("daily_audit_inclusion_status") or "Pending Review"
		posting_ready = cint_bool(row.get("posting_ready"))
		summary["total_amount"] += amount
		summary["count"] += 1
		if inclusion_status == "Pending Review":
			summary["pending_review_count"] += 1
		elif inclusion_status == "Included":
			summary["included_amount"] += amount
		elif inclusion_status == "Excluded":
			summary["excluded_amount"] += amount
		elif inclusion_status == "Needs Clarification":
			summary["needs_clarification_count"] += 1
		if status == "Pending Ledger":
			summary["pending_ledger_amount"] += amount
		if status == "Rejected":
			summary["rejected_amount"] += amount
		if posting_ready:
			summary["posting_ready_count"] += 1
		else:
			summary["posting_blocked_count"] += 1
	return summary


def append_totals_row(rows):
	if not rows:
		return rows
	summary = build_review_summary(rows)
	totals_row = {
		"_is_totals_row": 1,
		"name": _("Totals"),
		"expense_category": _("All Visible Expenses"),
		"amount": summary["total_amount"],
		"expense_status": _("Count: {0}").format(summary["count"]),
		"ledger_status": _("Posting Ready: {0} / Blocked: {1}").format(
			summary["posting_ready_count"], summary["posting_blocked_count"]
		),
		"daily_audit_inclusion_status": _("Pending Review: {0}").format(summary["pending_review_count"]),
		"daily_audit_classification": _("Needs Clarification: {0}").format(summary["needs_clarification_count"]),
		"daily_audit_note": _("Included Amount: {0}").format(frappe.format_value(summary["included_amount"], {"fieldtype": "Currency"})),
		"daily_audit_exclusion_reason": _("Excluded Amount: {0}").format(
			frappe.format_value(summary["excluded_amount"], {"fieldtype": "Currency"})
		),
	}
	return rows + [totals_row]


def get_chart_data(rows):
	rows = get_visible_rows(rows)
	if not rows:
		return None
	status_counts = {}
	for row in rows:
		status = row.get("expense_status") or "Draft"
		status_counts[status] = status_counts.get(status, 0) + 1
	return {
		"data": {
			"labels": list(status_counts.keys()),
			"datasets": [{"name": _("By Expense Status"), "values": list(status_counts.values())}],
		},
		"type": "bar",
		"height": 260,
	}


def cint_bool(value):
	return 1 if str(value) in {"1", "true", "True"} or value is True else 0


def get_visible_rows(rows):
	return [row for row in rows if not row.get("_is_totals_row")]
