from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_bank_match_reconciliation_readiness_rows,
	get_operational_report_message,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_rejected_cancelled", 0)
	rows = get_bank_match_reconciliation_readiness_rows(filters=filters, limit=filters.get("limit") or 500)
	message = get_operational_report_message() or (None if rows else _("No bank match readiness rows were found for the selected filters."))
	return get_columns(), rows, message, None, get_report_summary(rows)


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
