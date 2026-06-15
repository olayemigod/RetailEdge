from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, getdate, nowdate

from retailedge.branch_performance import get_bank_sales_total, get_branch_performance_debug_summary, get_branch_performance_rows


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_pos_invoices", 0)
	filters.setdefault("include_unattributed", 1)
	filters.setdefault("include_fallback_branch_resolution", 0)
	validate_filters(filters)
	data = get_data(filters)
	message = None
	if _rows_have_no_activity(data):
		debug_summary = get_branch_performance_debug_summary(filters)
		message = _build_no_data_message(debug_summary)
	return get_columns(), data, message, None, get_report_summary(data, message=message)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	if filters.get("from_date") and filters.get("to_date") and (getdate(filters.to_date) - getdate(filters.from_date)).days + 1 > 60:
		frappe.throw(_("Date range too wide for live report. Please use 60 days or less."))


def get_columns():
	return [
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Data", "width": 150},
		{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 150},
		{"label": _("Invoice Count"), "fieldname": "invoice_count", "fieldtype": "Int", "width": 100},
		{"label": _("Gross Sales"), "fieldname": "gross_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Cash Sales"), "fieldname": "cash_sales", "fieldtype": "Currency", "width": 110},
		{"label": _("Bank Sales"), "fieldname": "bank_sales", "fieldtype": "Currency", "width": 120},
		{"label": _("Credit / Outstanding"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 130},
		{"label": _("Cashier Expenses"), "fieldname": "cashier_expenses", "fieldtype": "Currency", "width": 130},
		{"label": _("Net Cash Expected"), "fieldname": "net_cash_expected", "fieldtype": "Currency", "width": 130},
		{"label": _("Audit Variance"), "fieldname": "audit_variance", "fieldtype": "Currency", "width": 120},
		{"label": _("Payment Issues"), "fieldname": "payment_issues", "fieldtype": "Int", "width": 100},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	rows = get_branch_performance_rows(filters)
	for row in rows:
		row["bank_sales"] = get_bank_sales_total(row)
		row["bank_card_mobile_sales"] = row["bank_sales"]
	return rows


def get_report_summary(rows, message=None):
	if not rows:
		return [{"value": message or _("No matching records found for the selected filters."), "label": _("Report Status"), "datatype": "Data", "indicator": "Orange"}]
	total_sales = sum(flt(row.get("gross_sales")) for row in rows)
	total_cash_sales = sum(flt(row.get("cash_sales")) for row in rows)
	total_bank_sales = sum(flt(row.get("bank_sales", get_bank_sales_total(row))) for row in rows)
	total_expenses = sum(flt(row.get("cashier_expenses")) for row in rows)
	has_ledger_expenses = any("ledger_expenses" in row for row in rows)
	total_ledger_expenses = sum(flt(row.get("ledger_expenses")) for row in rows) if has_ledger_expenses else 0
	total_expected_cash = sum(flt(row.get("expected_cash", row.get("net_cash_expected"))) for row in rows)
	total_actual_cash = sum(flt(row.get("actual_cash", row.get("actual_closing_cash"))) for row in rows)
	total_variance = sum(flt(row.get("audit_variance")) for row in rows)
	total_issues = sum(int(row.get("payment_issues") or 0) for row in rows)
	summary = [
		{"value": total_sales, "label": _("Gross Sales"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_cash_sales, "label": _("Cash Sales"), "datatype": "Currency", "indicator": "Green"},
		{"value": total_bank_sales, "label": _("Bank Sales"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_expenses, "label": _("Cashier Expenses"), "datatype": "Currency", "indicator": "Orange"},
	]
	if has_ledger_expenses:
		summary.append({"value": total_ledger_expenses, "label": _("Ledger Expenses"), "datatype": "Currency", "indicator": "Orange"})
	summary.extend([
		{"value": total_expected_cash, "label": _("Expected Cash"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_actual_cash, "label": _("Actual Cash"), "datatype": "Currency", "indicator": "Blue"},
		{"value": total_variance, "label": _("Audit Variance"), "datatype": "Currency", "indicator": "Red" if total_variance else "Green"},
		{"value": total_issues, "label": _("Payment Issues"), "datatype": "Int", "indicator": "Orange" if total_issues else "Green"},
	])
	return summary


def _build_no_data_message(debug_summary):
	submitted = int(debug_summary.get("submitted_sales_invoice_count") or 0)
	attributed = int(debug_summary.get("sales_invoice_with_retailedge_branch_count") or 0)
	expenses = int(debug_summary.get("cashier_expense_count") or 0)
	audits = int(debug_summary.get("daily_sales_audit_count") or 0)
	return _(
		"No matching records found for the selected filters. "
		"Submitted invoices: {0}, invoices with stored RetailEdge branch: {1}, "
		"cashier expenses: {2}, daily sales audits: {3}."
	).format(submitted, attributed, expenses, audits)


def _rows_have_no_activity(rows):
	if not rows:
		return True
	for row in rows:
		if any(
			flt(row.get(field))
			for field in (
				"invoice_count",
				"gross_sales",
				"cash_sales",
				"bank_card_mobile_sales",
				"cashier_expenses",
				"audit_variance",
				"daily_audit_count",
			)
		):
			return False
	return True
