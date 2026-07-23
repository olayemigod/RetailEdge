from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_operational_report_message,
	get_unmatched_bank_payment_event_rows,
)
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("payment_event_type", "All")
	filters.setdefault("include_already_matched", 0)
	filters.setdefault("include_cash", 0)
	filters.setdefault("include_candidate_preview", 0)
	rows = get_unmatched_bank_payment_event_rows(filters=filters, limit=filters.get("limit") or 500)
	message = get_operational_report_message() or (None if rows else _("No unmatched bank payment events were found for the selected filters."))
	summary = append_report_metadata(
		get_report_summary(rows),
		get_edgesuite_metadata(filters, rows),
	)
	return get_columns(), rows, message, None, summary


def get_columns():
	return [
		{"label": _("Payment Event Type"), "fieldname": "payment_event_type", "fieldtype": "Data", "width": 130},
		{"label": _("Payment Event Document"), "fieldname": "payment_event_document", "fieldtype": "Dynamic Link", "options": "suggested_document_type", "width": 170},
		{"label": _("Payment Row Reference / Index"), "fieldname": "payment_row_reference", "fieldtype": "Data", "width": 120},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": _("Customer / Supplier"), "fieldname": "customer_supplier", "fieldtype": "Data", "width": 160},
		{"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 130},
		{"label": _("Payment Account"), "fieldname": "payment_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Resolved Canonical Account"), "fieldname": "resolved_canonical_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 130},
		{"label": _("Linked Sales Invoice"), "fieldname": "linked_sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Linked Payment Entry"), "fieldname": "linked_payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
		{"label": _("Existing Bank Match"), "fieldname": "existing_bank_match", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 160},
		{"label": _("Match Status"), "fieldname": "match_status", "fieldtype": "Data", "width": 120},
		{"label": _("Candidate Bank Transaction"), "fieldname": "candidate_bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 165},
		{"label": _("Reason / Exception"), "fieldname": "reason_exception", "fieldtype": "Small Text", "width": 240},
		{"label": _("Days Outstanding"), "fieldname": "days_outstanding", "fieldtype": "Int", "width": 110},
	]


def get_report_summary(rows):
	return [
		{"label": _("Unmatched Payment Events"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Payment Entries"), "value": sum(1 for row in rows if row.get("payment_event_type") == "Payment Entry"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Invoice / POS Payment Rows"), "value": sum(1 for row in rows if row.get("payment_event_type") != "Payment Entry"), "datatype": "Int", "indicator": "Blue"},
	]


def get_edgesuite_metadata(filters, rows):
	account_gap_count = sum(
		1
		for row in rows
		if not row.get("resolved_canonical_account") or not row.get("payment_account")
	)
	without_candidate_count = sum(1 for row in rows if not row.get("candidate_bank_transaction"))
	aged_count = sum(1 for row in rows if cint(row.get("days_outstanding")) >= 7)
	exception_count = sum(1 for row in rows if row.get("reason_exception"))
	missing_reference_count = sum(
		1
		for row in rows
		if not row.get("reference_no") and not row.get("payment_row_reference")
	)
	recommendations = []
	if account_gap_count:
		recommendations.append(
			recommendation(
				_("Resolve payment-account context"),
				_("Confirm payment and canonical account context for {0} unmatched event(s) before candidate review.").format(account_gap_count),
				"danger",
			)
		)
	if without_candidate_count:
		recommendations.append(
			recommendation(
				_("Investigate events without bank candidates"),
				_("Review references, dates, amounts and bank-account scope for {0} event(s) without a candidate Bank Transaction.").format(without_candidate_count),
				"warning",
			)
		)
	if aged_count:
		recommendations.append(
			recommendation(
				_("Escalate aged unmatched payment events"),
				_("Review {0} event(s) that have remained unmatched for seven days or more.").format(aged_count),
				"warning",
			)
		)
	if exception_count:
		recommendations.append(
			recommendation(
				_("Resolve payment-event exceptions"),
				_("Investigate the reason or exception recorded on {0} event(s) before attempting a match.").format(exception_count),
				"danger",
			)
		)
	if missing_reference_count:
		recommendations.append(
			recommendation(
				_("Complete payment references"),
				_("Review source documents for {0} event(s) without a transaction or payment-row reference.").format(missing_reference_count),
				"warning",
			)
		)

	if account_gap_count or exception_count:
		status_label = _("Payment-event exceptions require attention")
		status_tone = "danger"
	elif rows:
		status_label = _("Unmatched payment-event queue requires review")
		status_tone = "warning"
	else:
		status_label = _("No unmatched payment events in current view")
		status_tone = "success"

	return build_report_metadata(
		title=_("Unmatched Bank Payment Events"),
		icon="credit-card",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("payment_event_type", _("Payment Event Type")),
			("mode_of_payment", _("Mode of Payment")),
			("payment_account", _("Payment Account")),
			("include_candidate_preview", _("Include Candidate Preview")),
			("include_already_matched", _("Include Already Matched")),
		),
		row_count=len(rows),
		empty_message=_("No unmatched bank payment events matched the selected filters."),
		empty_suggestions=(
			_("Choose another date range, company, branch, payment event type, mode of payment, or payment account."),
			_("Confirm that source payment documents contain correct references, posting dates, amounts and account context."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Unmatched Payment Events"),
			_("Payment Entries"),
			_("Invoice / POS Payment Rows"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)
