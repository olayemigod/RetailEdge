from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import get_operational_report_message
from retailedge.reconciliation_handoff import get_reconciliation_handoff_summary


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_already_reconciled", 0)
	filters.setdefault("include_exceptions", 1)
	filters.setdefault("include_rejected_cancelled", 0)
	result = get_reconciliation_handoff_summary(filters=filters, limit=filters.get("limit") or 500)
	rows = result.get("rows") or []
	message = get_operational_report_message() or (None if rows else _("No reconciliation handoff rows were found for the selected filters."))
	return get_columns(), rows, message, None, get_report_summary(result.get("summary") or {})


def get_columns():
	return [
		{"label": _("Handoff Status"), "fieldname": "handoff_status", "fieldtype": "Data", "width": 180},
		{"label": _("Priority"), "fieldname": "handoff_priority", "fieldtype": "Data", "width": 90},
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 170},
		{"label": _("Bank Date"), "fieldname": "bank_transaction_date", "fieldtype": "Date", "width": 100},
		{"label": _("Bank Account"), "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account", "width": 180},
		{"label": _("Bank Amount"), "fieldname": "bank_transaction_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Candidate Type"), "fieldname": "candidate_doctype", "fieldtype": "Data", "width": 120},
		{"label": _("Candidate"), "fieldname": "candidate_name", "fieldtype": "Dynamic Link", "options": "candidate_doctype", "width": 170},
		{"label": _("Candidate Date"), "fieldname": "candidate_date", "fieldtype": "Date", "width": 100},
		{"label": _("Candidate Account"), "fieldname": "candidate_account", "fieldtype": "Data", "width": 180},
		{"label": _("Candidate Amount"), "fieldname": "candidate_amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Match Type"), "fieldname": "match_type", "fieldtype": "Data", "width": 150},
		{"label": _("Match Status"), "fieldname": "match_status", "fieldtype": "Data", "width": 120},
		{"label": _("Recommended Action"), "fieldname": "recommended_action", "fieldtype": "Small Text", "width": 260},
		{"label": _("Blocking Reason"), "fieldname": "blocking_reason", "fieldtype": "Small Text", "width": 220},
		{"label": _("Notes"), "fieldname": "erpnext_reconciliation_notes", "fieldtype": "Small Text", "width": 260},
	]


def get_report_summary(summary):
	return [
		{"label": _("Ready for ERPNext Reconciliation"), "value": summary.get("ready", 0), "datatype": "Int", "indicator": "Green"},
		{"label": _("Needs Review Before Reconciliation"), "value": summary.get("needs_review", 0), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Exceptions"), "value": summary.get("exception", 0), "datatype": "Int", "indicator": "Red"},
	]
