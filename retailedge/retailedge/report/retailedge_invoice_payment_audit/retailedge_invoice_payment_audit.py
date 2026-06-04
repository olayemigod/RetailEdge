from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from retailedge.invoice_payment_audit import get_invoice_payment_audit_list, get_invoice_payment_audit_summary


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_invoice_payment_audit_list(filters=filters, limit=filters.get("limit") or 500)
	return get_columns(), data, None, None, get_report_summary(filters)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	if filters.get("from_date") and filters.get("to_date") and (getdate(filters.to_date) - getdate(filters.from_date)).days + 1 > 60:
		frappe.throw(_("Date range too wide for live report. Please use 60 days or less."))


def get_columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 155},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 160},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 110},
		{"label": _("Paid Amount"), "fieldname": "paid_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Outstanding Amount"), "fieldname": "outstanding_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Payment Row Amount"), "fieldname": "payment_row_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Payment Entry Amount"), "fieldname": "payment_entry_amount", "fieldtype": "Currency", "width": 125},
		{"label": _("Difference"), "fieldname": "difference", "fieldtype": "Currency", "width": 95},
		{"label": _("ERP Status"), "fieldname": "erp_status", "fieldtype": "Data", "width": 110},
		{"label": _("Audit Status"), "fieldname": "payment_audit_status", "fieldtype": "Data", "width": 150},
		{"label": _("Risk Level"), "fieldname": "payment_risk_level", "fieldtype": "Data", "width": 95},
		{"label": _("Payment Classification"), "fieldname": "payment_classification", "fieldtype": "Data", "width": 155},
		{"label": _("Payment Methods"), "fieldname": "payment_methods", "fieldtype": "Data", "width": 160},
		{"label": _("Accounts Used"), "fieldname": "accounts_used", "fieldtype": "Data", "width": 180},
		{"label": _("Expected Accounts"), "fieldname": "expected_accounts", "fieldtype": "Data", "width": 180},
		{"label": _("Issues"), "fieldname": "issues", "fieldtype": "Small Text", "width": 250},
		{"label": _("Branch Source"), "fieldname": "branch_source", "fieldtype": "Data", "width": 150},
	]


def get_report_summary(filters):
	summary = get_invoice_payment_audit_summary(filters=filters)
	return [
		{"value": summary.get("total_invoice_count"), "label": _("Invoices"), "datatype": "Int", "indicator": "Blue"},
		{"value": summary.get("payment_rows_missing_count"), "label": _("Missing Payment Rows"), "datatype": "Int", "indicator": "Orange" if summary.get("payment_rows_missing_count") else "Green"},
		{"value": summary.get("payment_account_mismatch_count"), "label": _("Account Mismatches"), "datatype": "Int", "indicator": "Red" if summary.get("payment_account_mismatch_count") else "Green"},
		{"value": summary.get("high_risk_count"), "label": _("High Risk"), "datatype": "Int", "indicator": "Red" if summary.get("high_risk_count") else "Green"},
	]
