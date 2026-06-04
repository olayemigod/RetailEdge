from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_operational_report_message,
	get_unmatched_bank_transaction_rows,
)


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
	message = get_operational_report_message() or (None if rows else _("No unmatched bank transactions were found for the selected filters."))
	return get_columns(), rows, message, None, get_report_summary(rows)


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
