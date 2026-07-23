from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import get_operational_report_message
from retailedge.reconciliation_handoff import get_reconciliation_handoff_summary
from retailedge.report_edgeui import append_report_metadata, build_report_metadata, recommendation


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_already_reconciled", 0)
	filters.setdefault("include_exceptions", 1)
	filters.setdefault("include_rejected_cancelled", 0)
	result = get_reconciliation_handoff_summary(filters=filters, limit=filters.get("limit") or 500)
	rows = result.get("rows") or []
	handoff_summary = result.get("summary") or {}
	message = get_operational_report_message() or (None if rows else _("No reconciliation handoff rows were found for the selected filters."))
	summary = append_report_metadata(
		get_report_summary(handoff_summary),
		get_edgesuite_metadata(filters, rows, handoff_summary),
	)
	return get_columns(), rows, message, None, summary


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


def get_edgesuite_metadata(filters, rows, summary):
	ready_count = int(summary.get("ready") or 0)
	needs_review_count = int(summary.get("needs_review") or 0)
	exception_count = int(summary.get("exception") or 0)
	blocking_count = sum(1 for row in rows if row.get("blocking_reason"))
	high_priority_count = sum(
		1
		for row in rows
		if str(row.get("handoff_priority") or "").strip().lower() in {"high", "urgent", "critical"}
		and row.get("handoff_status") != "Ready for ERPNext Reconciliation"
	)
	missing_candidate_count = sum(
		1
		for row in rows
		if row.get("handoff_status") != "Already Reconciled"
		and (not row.get("candidate_doctype") or not row.get("candidate_name"))
	)
	recommendations = []
	if exception_count:
		recommendations.append(
			recommendation(
				_("Investigate manual exceptions"),
				_("Investigate the {0} exception row(s) before any ERPNext reconciliation is attempted.").format(exception_count),
				"danger",
			)
		)
	if needs_review_count:
		recommendations.append(
			recommendation(
				_("Complete pre-reconciliation review"),
				_("Complete evidence and approval review for {0} handoff row(s) before processing them in ERPNext.").format(needs_review_count),
				"warning",
			)
		)
	if blocking_count:
		recommendations.append(
			recommendation(
				_("Resolve handoff blockers"),
				_("Resolve the blocking reasons recorded on {0} row(s) before moving them forward.").format(blocking_count),
				"danger",
			)
		)
	if missing_candidate_count:
		recommendations.append(
			recommendation(
				_("Complete candidate evidence"),
				_("Confirm the candidate document and type for {0} row(s) before reconciliation handoff.").format(missing_candidate_count),
				"warning",
			)
		)
	if high_priority_count:
		recommendations.append(
			recommendation(
				_("Escalate high-priority handoffs"),
				_("Review {0} high-priority row(s) that are not yet ready for ERPNext reconciliation.").format(high_priority_count),
				"warning",
			)
		)
	if ready_count and not (exception_count or needs_review_count or blocking_count):
		recommendations.append(
			recommendation(
				_("Proceed through the controlled ERPNext reconciliation flow"),
				_("The current view contains {0} ready row(s). Process them only through the normal permission-controlled ERPNext reconciliation workflow.").format(ready_count),
				"success",
			)
		)

	if exception_count or blocking_count:
		status_label = _("Handoff blockers require attention")
		status_tone = "danger"
	elif needs_review_count or missing_candidate_count or high_priority_count:
		status_label = _("Review required before handoff")
		status_tone = "warning"
	elif ready_count:
		status_label = _("Ready handoff queue available")
		status_tone = "success"
	else:
		status_label = _("No handoff rows in current view")
		status_tone = "neutral"

	return build_report_metadata(
		title=_("Reconciliation Handoff"),
		icon="arrow-right-circle",
		filters=filters,
		filter_fields=(
			("company", _("Company")),
			("branch", _("Branch")),
			("bank_account", _("Bank Account")),
			("handoff_status", _("Handoff Status")),
			("match_type", _("Match Type")),
			("match_status", _("Match Status")),
			("candidate_doctype", _("Candidate Type")),
			("include_already_reconciled", _("Include Already Reconciled")),
			("include_exceptions", _("Include Exceptions")),
		),
		row_count=len(rows),
		empty_message=_("No reconciliation handoff rows matched the selected filters."),
		empty_suggestions=(
			_("Choose another date range, company, branch, bank account, handoff status, match type, or candidate type."),
			_("Confirm that approved bank match reviews have complete candidate, account, amount and reconciliation evidence."),
		),
		recommendations=recommendations,
		visible_card_labels=(
			_("Ready for ERPNext Reconciliation"),
			_("Needs Review Before Reconciliation"),
			_("Exceptions"),
		),
		status_label=status_label,
		status_tone=status_tone,
	)
