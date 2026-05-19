from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, getdate

from retailedge.branch_performance import get_branch_performance_summary, get_candidate_branches


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_data(filters)
	return get_columns(), data, None, None, get_report_summary(data)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date"):
		if getdate(filters.from_date) > getdate(filters.to_date):
			frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 150},
		{"label": _("Total Sales"), "fieldname": "total_sales_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Sales Invoice Count"), "fieldname": "sales_invoice_count", "fieldtype": "Int", "width": 120},
		{"label": _("Paid Invoice Count"), "fieldname": "paid_invoice_count", "fieldtype": "Int", "width": 120},
		{"label": _("Unpaid Invoice Count"), "fieldname": "unpaid_invoice_count", "fieldtype": "Int", "width": 130},
		{"label": _("Partially Paid Invoice Count"), "fieldname": "partially_paid_invoice_count", "fieldtype": "Int", "width": 145},
		{"label": _("Credit Sales Amount"), "fieldname": "credit_sales_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Cash Sales"), "fieldname": "cash_sales_amount", "fieldtype": "Currency", "width": 115},
		{"label": _("Bank Transfer"), "fieldname": "bank_transfer_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Card/POS"), "fieldname": "card_pos_amount", "fieldtype": "Currency", "width": 115},
		{"label": _("Mobile Money"), "fieldname": "mobile_money_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Other Payment"), "fieldname": "other_payment_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Cashier Expenses"), "fieldname": "cashier_expense_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Expected Cash"), "fieldname": "expected_cash_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Actual Closing Cash"), "fieldname": "actual_closing_cash_amount", "fieldtype": "Currency", "width": 145},
		{"label": _("Cash Variance"), "fieldname": "cash_variance_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Daily Audits"), "fieldname": "daily_audit_count", "fieldtype": "Int", "width": 100},
		{"label": _("Audits Pending"), "fieldname": "daily_audit_pending_count", "fieldtype": "Int", "width": 110},
		{"label": _("Audits Approved"), "fieldname": "daily_audit_approved_count", "fieldtype": "Int", "width": 120},
		{"label": _("Audits With Variance"), "fieldname": "daily_audit_variance_count", "fieldtype": "Int", "width": 130},
		{"label": _("Material Requests"), "fieldname": "material_request_count", "fieldtype": "Int", "width": 120},
		{"label": _("Stock Entries"), "fieldname": "stock_entry_count", "fieldtype": "Int", "width": 110},
		{"label": _("Exception Count"), "fieldname": "exception_count", "fieldtype": "Int", "width": 110},
	]


def get_data(filters):
	branches = get_candidate_branches(filters)
	if filters.get("branch"):
		branches = [filters.get("branch")]
	if not branches:
		summary = get_branch_performance_summary(filters)
		return [summary]

	rows = []
	for branch in branches:
		summary = get_branch_performance_summary({**filters, "branch": branch})
		if _has_visible_values(summary, explicit_branch=bool(filters.get("branch"))):
			rows.append(summary)
	return rows


def get_report_summary(rows):
	if not rows:
		return []
	total_sales = sum(flt(row.get("total_sales_amount")) for row in rows)
	total_expenses = sum(flt(row.get("cashier_expense_amount")) for row in rows)
	total_variance = sum(flt(row.get("cash_variance_amount")) for row in rows)
	total_pending_audits = sum(int(row.get("daily_audit_pending_count") or 0) for row in rows)
	return [
		{"value": total_sales, "label": _("Total Sales"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_expenses, "label": _("Cashier Expenses"), "datatype": "Currency", "indicator": "Orange"},
		{"value": total_variance, "label": _("Cash Variance"), "datatype": "Currency", "indicator": "Red" if total_variance else "Green"},
		{"value": total_pending_audits, "label": _("Pending Audits"), "datatype": "Int", "indicator": "Orange" if total_pending_audits else "Green"},
	]


def _has_visible_values(summary, explicit_branch=False):
	if explicit_branch:
		return True
	return any(
		flt(summary.get(fieldname))
		for fieldname in (
			"total_sales_amount",
			"cashier_expense_amount",
			"expected_cash_amount",
			"actual_closing_cash_amount",
			"cash_variance_amount",
		)
	) or any(
		int(summary.get(fieldname) or 0)
		for fieldname in (
			"sales_invoice_count",
			"daily_audit_count",
			"material_request_count",
			"stock_entry_count",
			"exception_count",
		)
	)
