from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_operational_report_message,
	get_unmatched_bank_transaction_rows,
)
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("direction", "All")
	filters.setdefault("include_already_reviewed", 0)
	filters.setdefault("include_rejected", 0)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_candidate_preview", 0)
	rows = get_unmatched_bank_transaction_rows(filters=filters, limit=filters.get("limit") or 500)
	message = get_operational_report_message() or (
		None if rows else _("No unmatched bank transactions were found for the selected filters.")
	)
	summary = append_report_metadata(
		get_report_summary(rows),
		get_edgesuite_metadata(filters, rows),
	)
	return get_columns(), rows, message, None, summary


def get_columns():
	return [
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 165},
		{"label": _("Transaction Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Bank Account"), "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account", "width": 180},
		{"label": _("Resolved Canonical Account"), "fieldname": "resolved_canonical_account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Account Resolution"), "fieldname": "account_resolution_status", "fieldtype": "Data", "width": 120},
		{"label": _("Direction"), "fieldname": "direction", "fieldtype": "Data", "width": 90},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 130},
		{"label": _("Narration / Description"), "fieldname": "narration", "fieldtype": "Small Text", "width": 220},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 160},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 140},
		{"label": _("Existing Match"), "fieldname": "existing_match", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 160},
		{"label": _("Suggested Candidate Count"), "fieldname": "suggested_candidate_count", "fieldtype": "Int", "width": 110},
		{"label": _("Best Candidate"), "fieldname": "best_candidate", "fieldtype": "Dynamic Link", "options": "best_candidate_type", "width": 170},
		{"label": _("Best Candidate Type"), "fieldname": "best_candidate_type", "fieldtype": "Data", "width": 120},
		{"label": _("Candidate Category"), "fieldname": "best_candidate_category", "fieldtype": "Data", "width": 160},
		{"label": _("Blocked / Reason"), "fieldname": "blocked_reason", "fieldtype": "Small Text", "width": 260},
		{"label": _("Reconciliation Status"), "fieldname": "reconciliation_status", "fieldtype": "Data", "width": 140},
		{"label": _("Age / Days Outstanding"), "fieldname": "days_outstanding", "fieldtype": "Int", "width": 110},
	]


def get_report_summary(rows):
	return [
		{"label": _("Unmatched Bank Transactions"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("With Suggested Candidate"), "value": sum(1 for row in rows if row.get("best_candidate")), "datatype": "Int", "indicator": "Green"},
		{"label": _("Without Candidate"), "value": sum(1 for row in rows if not row.get("best_candidate")), "datatype": "Int", "indicator": "Orange"},
	]


def get_edgesuite_metadata(filters, rows):
	with_candidate = sum(1 for row in rows if row.get("best_candidate"))
	without_candidate = len(rows) - with_candidate
	unresolved_accounts = sum(
		1
		for row in rows
		if row.get("account_resolution_status") == "Unresolved"
		or (row.get("bank_account") and not row.get("resolved_canonical_account"))
	)
	blocked_rows = sum(1 for row in rows if str(row.get("blocked_reason") or "").strip())
	aged_without_candidate = sum(
		1
		for row in rows
		if not row.get("best_candidate") and cint(row.get("days_outstanding")) >= 7
	)
	recommendations = []
	if unresolved_accounts:
		recommendations.append(
			recommendation(
				_("Resolve bank-account context"),
				_("{0} unmatched transaction(s) do not have a resolved canonical account. Correct the account context before candidate review.").format(unresolved_accounts),
				"danger",
			)
		)
	if aged_without_candidate:
		recommendations.append(
			recommendation(
				_("Escalate aged unmatched transactions"),
				_("{0} transaction(s) have remained unmatched for at least seven days without a suggested candidate.").format(aged_without_candidate),
				"danger",
			)
		)
	if without_candidate:
		recommendations.append(
			recommendation(
				_("Investigate transactions without candidates"),
				_("Review references, narrations, amounts and expected accounts for {0} transaction(s) without a candidate.").format(without_candidate),
				"warning",
			)
		)
	if blocked_rows:
		recommendations.append(
			recommendation(
				_("Resolve candidate blockers"),
				_("{0} transaction(s) contain a blocking reason. Address the reason before creating or confirming any review-layer match.").format(blocked_rows),
				"warning",
			)
		)

	if unresolved_accounts or aged_without_candidate:
		status_label = _("Priority unmatched transactions require action")
		status_tone = "danger"
	elif rows:
		status_label = _("Unmatched queue requires review")
		status_tone = "warning"
	else:
		status_label = _("No unmatched transactions in current view")
		status_tone = "success"

	return build_report_metadata(
		title=_("Unmatched Bank Transactions"),
		icon="bank",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("bank_account", _("Bank Account")),
			("direction", _("Direction")),
			("amount_from", _("Amount From")),
			("amount_to", _("Amount To")),
			("match_status", _("Review Status")),
			("account_resolution_status", _("Account Resolution Status")),
			("include_candidate_preview", _("Include Candidate Preview")),
			("include_already_reviewed", _("Include Already Reviewed")),
			("include_rejected", _("Include Rejected")),
			("include_reconciled", _("Include Reconciled")),
		),
		row_count=len(rows),
		empty_message=_("No unmatched bank transactions matched the selected filters."),
		empty_suggestions=(
			_("Choose another date range, company, branch, bank account, direction, or review status."),
			_("Confirm that imported Bank Transactions have the expected company and account context."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Unmatched Bank Transactions"),
			_("With Suggested Candidate"),
			_("Without Candidate"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)
