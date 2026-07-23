from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from retailedge.invoice_payment_audit import get_invoice_payment_audit_list, get_invoice_payment_audit_summary
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_invoice_payment_audit_list(filters=filters, limit=filters.get("limit") or 500)
	summary_data = get_invoice_payment_audit_summary(filters=filters)
	summary = append_report_metadata(
		get_report_summary(filters, summary=summary_data),
		get_edgesuite_metadata(filters, data, summary_data),
	)
	return get_columns(), data, None, None, summary


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


def get_report_summary(filters, summary=None):
	summary = summary or get_invoice_payment_audit_summary(filters=filters)
	return [
		{"value": summary.get("total_invoice_count"), "label": _("Invoices"), "datatype": "Int", "indicator": "Blue"},
		{"value": summary.get("payment_rows_missing_count"), "label": _("Missing Payment Rows"), "datatype": "Int", "indicator": "Orange" if summary.get("payment_rows_missing_count") else "Green"},
		{"value": summary.get("payment_account_mismatch_count"), "label": _("Account Mismatches"), "datatype": "Int", "indicator": "Red" if summary.get("payment_account_mismatch_count") else "Green"},
		{"value": summary.get("high_risk_count"), "label": _("High Risk"), "datatype": "Int", "indicator": "Red" if summary.get("high_risk_count") else "Green"},
	]


def get_edgesuite_metadata(filters, rows, summary):
	missing_rows = int(summary.get("payment_rows_missing_count") or 0)
	account_mismatches = int(summary.get("payment_account_mismatch_count") or 0)
	high_risk = int(summary.get("high_risk_count") or 0)
	recommendations = []
	if high_risk:
		recommendations.append(
			recommendation(
				_("Review high-risk invoices"),
				_("Open the {0} high-risk invoice(s) and confirm payment evidence before verification or collection follow-up.").format(high_risk),
				"danger",
			)
		)
	if account_mismatches:
		recommendations.append(
			recommendation(
				_("Resolve payment account mismatches"),
				_("Confirm the payment methods and accounts used on {0} invoice(s) against the expected company and branch accounts.").format(account_mismatches),
				"danger",
			)
		)
	if missing_rows:
		recommendations.append(
			recommendation(
				_("Complete missing payment evidence"),
				_("Review {0} invoice(s) with missing payment rows before daily audit or reconciliation sign-off.").format(missing_rows),
				"warning",
			)
		)

	if high_risk or account_mismatches:
		status_label = _("Material payment exceptions")
		status_tone = "danger"
	elif missing_rows:
		status_label = _("Payment evidence incomplete")
		status_tone = "warning"
	else:
		status_label = _("No material payment exception in current view")
		status_tone = "success"

	return build_report_metadata(
		title=_("Invoice Payment Audit"),
		icon="receipt",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("customer", _("Customer")),
			("pos_profile", _("POS Profile")),
			("cashier", _("Cashier")),
			("audit_status", _("Audit Status")),
			("risk_level", _("Risk Level")),
			("payment_category", _("Payment Category")),
			("only_issues", _("Only Issues")),
		),
		row_count=len(rows),
		empty_message=_("No invoices matched the selected payment-audit filters."),
		empty_suggestions=(
			_("Choose another date range, company, branch, customer, audit status, or risk level."),
			_("Confirm that submitted invoices and payment evidence are available within the selected operational context."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Invoices"),
			_("Missing Payment Rows"),
			_("Account Mismatches"),
			_("High Risk"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)
