from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_bank_match_reconciliation_readiness_rows,
	get_operational_report_message,
)
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_rejected_cancelled", 0)
	rows = get_bank_match_reconciliation_readiness_rows(filters=filters, limit=filters.get("limit") or 500)
	message = get_operational_report_message() or (None if rows else _("No bank match readiness rows were found for the selected filters."))
	summary = append_report_metadata(
		get_report_summary(rows),
		get_edgesuite_metadata(filters, rows),
	)
	return get_columns(), rows, message, None, summary


def get_columns():
	return [
		{"label": _("Bank Match Review"), "fieldname": "bank_match_review", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 165},
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 165},
		{"label": _("Transaction Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
		{"label": _("Bank Amount"), "fieldname": "bank_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Bank Account"), "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account", "width": 170},
		{"label": _("Resolved Bank Account"), "fieldname": "resolved_bank_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Candidate Type"), "fieldname": "candidate_type", "fieldtype": "Data", "width": 150},
		{"label": _("Suggested Document Type"), "fieldname": "suggested_document_type", "fieldtype": "Data", "width": 130},
		{"label": _("Suggested Document"), "fieldname": "suggested_document", "fieldtype": "Dynamic Link", "options": "suggested_document_type", "width": 160},
		{"label": _("Payment Event Source"), "fieldname": "payment_event_source", "fieldtype": "Data", "width": 150},
		{"label": _("Payment Event Amount"), "fieldname": "payment_event_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Payment Account"), "fieldname": "payment_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Resolved Payment Account"), "fieldname": "resolved_payment_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
		{"label": _("Match Confidence"), "fieldname": "match_confidence", "fieldtype": "Data", "width": 110},
		{"label": _("Match Score"), "fieldname": "match_score", "fieldtype": "Int", "width": 80},
		{"label": _("Amount Scenario"), "fieldname": "amount_scenario", "fieldtype": "Data", "width": 160},
		{"label": _("Account Resolution Status"), "fieldname": "account_resolution_status", "fieldtype": "Data", "width": 150},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 110},
		{"label": _("Action Status"), "fieldname": "action_status", "fieldtype": "Data", "width": 120},
		{"label": _("Reconciliation Readiness Status"), "fieldname": "reconciliation_readiness_status", "fieldtype": "Data", "width": 180},
		{"label": _("Exception Reason"), "fieldname": "exception_reason", "fieldtype": "Small Text", "width": 260},
		{"label": _("Existing Reconciliation Status"), "fieldname": "existing_reconciliation_status", "fieldtype": "Data", "width": 160},
		{"label": _("Confirmed By"), "fieldname": "confirmed_by", "fieldtype": "Data", "width": 130},
		{"label": _("Confirmed On"), "fieldname": "confirmed_on", "fieldtype": "Datetime", "width": 145},
		{"label": _("Age / Days Since Confirmation"), "fieldname": "days_since_confirmation", "fieldtype": "Int", "width": 130},
	]


def get_report_summary(rows):
	return [
		{"label": _("Ready for Reconciliation"), "value": sum(1 for row in rows if row.get("reconciliation_readiness_status") == "Ready for Reconciliation"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Needs Review"), "value": sum(1 for row in rows if row.get("reconciliation_readiness_status") == "Needs Review"), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Exceptions / Not Ready"), "value": sum(1 for row in rows if row.get("reconciliation_readiness_status") in {"Not Ready", "Exception"}), "datatype": "Int", "indicator": "Red"},
	]


def get_edgesuite_metadata(filters, rows):
	ready_count = sum(1 for row in rows if row.get("reconciliation_readiness_status") == "Ready for Reconciliation")
	needs_review_count = sum(1 for row in rows if row.get("reconciliation_readiness_status") == "Needs Review")
	exception_count = sum(1 for row in rows if row.get("reconciliation_readiness_status") in {"Not Ready", "Exception"})
	account_gap_count = sum(
		1
		for row in rows
		if row.get("account_resolution_status") not in {"Resolved", "Fully Resolved"}
		or not row.get("resolved_bank_account")
		or not row.get("resolved_payment_account")
	)
	aged_confirmation_count = sum(
		1
		for row in rows
		if cint(row.get("days_since_confirmation")) >= 3
		and row.get("reconciliation_readiness_status") != "Ready for Reconciliation"
	)
	recommendations = []
	if exception_count:
		recommendations.append(
			recommendation(
				_("Resolve reconciliation exceptions"),
				_("Investigate the {0} row(s) marked Not Ready or Exception before any ERPNext reconciliation action.").format(exception_count),
				"danger",
			)
		)
	if needs_review_count:
		recommendations.append(
			recommendation(
				_("Complete review before handoff"),
				_("Complete evidence and approval review for {0} row(s) before they enter the reconciliation queue.").format(needs_review_count),
				"warning",
			)
		)
	if account_gap_count:
		recommendations.append(
			recommendation(
				_("Resolve account context"),
				_("Confirm the canonical bank and payment accounts for {0} row(s) so reconciliation does not post against the wrong ledger account.").format(account_gap_count),
				"danger",
			)
		)
	if aged_confirmation_count:
		recommendations.append(
			recommendation(
				_("Escalate aged confirmed matches"),
				_("Review {0} confirmed row(s) that have remained outside the ready queue for three days or more.").format(aged_confirmation_count),
				"warning",
			)
		)

	if exception_count or account_gap_count:
		status_label = _("Exceptions require attention")
		status_tone = "danger"
	elif needs_review_count or aged_confirmation_count:
		status_label = _("Review required before reconciliation")
		status_tone = "warning"
	elif ready_count:
		status_label = _("Ready queue available")
		status_tone = "success"
	else:
		status_label = _("No readiness rows in current view")
		status_tone = "neutral"

	return build_report_metadata(
		title=_("Reconciliation Readiness"),
		icon="check-circle",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("bank_account", _("Bank Account")),
			("review_status", _("Review Status")),
			("match_confidence", _("Match Confidence")),
			("reconciliation_readiness_status", _("Readiness Status")),
			("include_reconciled", _("Include Reconciled")),
			("include_rejected_cancelled", _("Include Rejected / Cancelled")),
		),
		row_count=len(rows),
		empty_message=_("No bank match readiness rows matched the selected filters."),
		empty_suggestions=(
			_("Choose another date, company, branch, bank account, confidence, or readiness status."),
			_("Confirm that bank match reviews have completed evidence, account resolution, confirmation, and approval information."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Ready for Reconciliation"),
			_("Needs Review"),
			_("Exceptions / Not Ready"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)
