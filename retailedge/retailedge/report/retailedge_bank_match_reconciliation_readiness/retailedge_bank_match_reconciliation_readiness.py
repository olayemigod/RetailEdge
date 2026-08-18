from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cstr, flt, get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_bank_match_reconciliation_readiness_rows,
	get_operational_report_message,
)
from retailedge.reconciliation_bridge import get_reconciliation_preflight


PREFLIGHT_TO_REPORT_STATUS = {
	"Ready": "Ready for Reconciliation",
	"Needs Review": "Needs Review",
	"Already Reconciled": "Already Reconciled",
	"Exception": "Exception",
	"Target Ambiguous": "Not Ready",
	"Not Ready": "Not Ready",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("direction", "All")
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_rejected_cancelled", 0)

	# The legacy operational report still contains historical Inflow-only readiness assumptions.
	# Load its bounded row set without applying readiness first, then correct only the unsafe
	# Outflow/Journal Entry rows through the canonical reconciliation bridge.
	requested_readiness = cstr(filters.get("reconciliation_readiness_status")).strip()
	legacy_filters = frappe._dict(filters.copy())
	legacy_filters.pop("reconciliation_readiness_status", None)
	legacy_filters.pop("direction", None)
	rows = get_bank_match_reconciliation_readiness_rows(
		filters=legacy_filters,
		limit=filters.get("limit") or 500,
	)
	rows = _apply_direction_aware_readiness(rows, filters)
	if requested_readiness:
		rows = [
			row
			for row in rows
			if cstr(row.get("reconciliation_readiness_status")).strip() == requested_readiness
		]
	message = get_operational_report_message() or (
		None if rows else _("No bank match readiness rows were found for the selected filters.")
	)
	return get_columns(), rows, message, None, get_report_summary(rows)


def _apply_direction_aware_readiness(rows, filters):
	rows = [frappe._dict(row or {}) for row in rows or []]
	bank_transaction_names = list(
		dict.fromkeys(
			cstr(row.get("bank_transaction")).strip()
			for row in rows
			if cstr(row.get("bank_transaction")).strip()
		)
	)
	direction_by_transaction = {}
	if bank_transaction_names:
		for bank_row in frappe.get_all(
			"Bank Transaction",
			filters={"name": ["in", bank_transaction_names]},
			fields=["name", "deposit", "withdrawal"],
			limit_page_length=len(bank_transaction_names),
		):
			direction = "Unknown"
			if flt(bank_row.get("deposit")) > 0:
				direction = "Inflow"
			elif flt(bank_row.get("withdrawal")) > 0:
				direction = "Outflow"
			direction_by_transaction[bank_row.get("name")] = direction

	requested_direction = cstr(filters.get("direction") or "All").strip() or "All"
	results = []
	for row in rows:
		direction = direction_by_transaction.get(row.get("bank_transaction"), "Unknown")
		row["direction"] = direction
		if requested_direction != "All" and direction != requested_direction:
			continue

		# Legacy readiness is retained for ordinary Inflow SI/PE rows. Outflows and Journal
		# Entries use the canonical bridge because those are the historical blind spots.
		if direction == "Outflow" or cstr(row.get("suggested_document_type")).strip() == "Journal Entry":
			preflight = get_reconciliation_preflight(row.get("bank_match_review"))
			row["reconciliation_readiness_status"] = PREFLIGHT_TO_REPORT_STATUS.get(
				cstr(preflight.get("status")).strip(),
				"Not Ready",
			)
			row["exception_reason"] = preflight.get("blocking_reason") or ""
			row["resolved_bank_account"] = (
				preflight.get("canonical_bank_account") or row.get("resolved_bank_account")
			)
			row["resolved_payment_account"] = (
				preflight.get("canonical_payment_account") or row.get("resolved_payment_account")
			)
			row["payment_event_source"] = (
				preflight.get("payment_event_source") or row.get("payment_event_source")
			)
			row["payment_event_amount"] = (
				preflight.get("payment_event_amount") or row.get("payment_event_amount")
			)
			row["payment_account"] = preflight.get("candidate_account") or row.get("payment_account")
			row["account_resolution_status"] = (
				preflight.get("account_resolution_status") or row.get("account_resolution_status")
			)
			if preflight.get("status") == "Already Reconciled":
				row["existing_reconciliation_status"] = "Reconciled"
		results.append(row)
	return results


def get_columns():
	return [
		{"label": _("Bank Match Review"), "fieldname": "bank_match_review", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 165},
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 165},
		{"label": _("Direction"), "fieldname": "direction", "fieldtype": "Data", "width": 90},
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
