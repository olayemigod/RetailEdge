from __future__ import annotations

import time

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_first_day, getdate, nowdate

from retailedge.bank_transaction_matching import (
	get_candidate_category_label,
	get_amount_scenario_label,
	get_bank_transaction_matching_rows,
	get_bank_transaction_matching_settings,
)

DEFAULT_RESULT_LIMIT = 10
MAX_RESULT_LIMIT = 500


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_unmatched", 1)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_verified_invoices", 0)
	filters.setdefault("include_confirmed_matches", 0)
	filters.setdefault("review_queue_status", "Open Suggestions Only")
	filters.setdefault("include_rejected_candidates", 0)
	result_limit = normalize_result_limit(filters)
	filters["result_limit"] = result_limit
	validate_filters(filters)
	data = get_bank_transaction_matching_rows(filters=filters, limit=result_limit)
	for row in data:
		row["suggested_match"] = build_suggested_match_label(row)
		row["amount_scenario_label"] = get_amount_scenario_label(row.get("amount_scenario"))
		row["candidate_category_label"] = get_candidate_category_label(row.get("candidate_category"))
	if data:
		message = _("Showing first {0} results. Narrow filters for more precise matching.").format(result_limit) if len(data) >= result_limit else None
	else:
		message = _(
			"No matching bank transactions were found. Adjust filters or date range. Cash-only payments, already confirmed matches, and reconciled records may be excluded."
		)
	return get_columns(), data, message, None, get_report_summary(data)


def normalize_result_limit(filters):
	requested = cint(filters.get("result_limit") or filters.get("limit") or DEFAULT_RESULT_LIMIT)
	if requested <= 0:
		requested = DEFAULT_RESULT_LIMIT
	return min(requested, MAX_RESULT_LIMIT)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))
	if filters.get("from_date") and filters.get("to_date") and (getdate(filters.to_date) - getdate(filters.from_date)).days + 1 > 60:
		frappe.throw(_("Date range too wide for live report. Please use 60 days or less."))


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
		{"label": _("Bank Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("SI/PE Amount"), "fieldname": "candidate_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Difference"), "fieldname": "amount_difference", "fieldtype": "Currency", "width": 95},
		{"label": _("Action Status"), "fieldname": "action_status", "fieldtype": "Data", "width": 180},
		{"label": _("Exception Type"), "fieldname": "exception_type", "fieldtype": "Data", "width": 150},
		{"label": _("Action"), "fieldname": "action", "fieldtype": "Data", "width": 110},
		{"label": _("Customer / Party"), "fieldname": "customer", "fieldtype": "Data", "width": 160},
		{"label": _("Suggested Match"), "fieldname": "suggested_match", "fieldtype": "Data", "width": 210},
		{"label": _("Match Confidence"), "fieldname": "match_confidence", "fieldtype": "Data", "width": 115},
		{"label": _("Match Score"), "fieldname": "match_score", "fieldtype": "Int", "width": 80},
		{"label": _("Issue / Reason"), "fieldname": "match_reason", "fieldtype": "Small Text", "width": 240},
		{"label": _("Amount Scenario"), "fieldname": "amount_scenario_label", "fieldtype": "Data", "width": 150},
		{"label": _("Candidate Category"), "fieldname": "candidate_category_label", "fieldtype": "Data", "width": 160},
		{"label": _("Auto-Match Status"), "fieldname": "auto_match_status", "fieldtype": "Data", "width": 165},
		{"label": _("Auto-Match Reason"), "fieldname": "auto_match_reason", "fieldtype": "Small Text", "width": 220},
		{"label": _("Bank Account"), "fieldname": "bank_account", "fieldtype": "Link", "options": "Bank Account", "width": 170},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 135},
		{"label": _("Narration"), "fieldname": "narration", "fieldtype": "Small Text", "width": 180},
		{"label": _("Suggested Document Type"), "fieldname": "suggested_document_type", "fieldtype": "Data", "width": 135},
		{"label": _("Suggested Document"), "fieldname": "suggested_document", "fieldtype": "Dynamic Link", "options": "suggested_document_type", "width": 160},
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 160},
		{"label": _("Suggested Sales Invoice"), "fieldname": "suggested_sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 155},
		{"label": _("Direction"), "fieldname": "direction", "fieldtype": "Data", "width": 90},
	]


def build_suggested_match_label(row):
	suggested_document = cstr(row.get("suggested_document")).strip()
	suggested_document_type = cstr(row.get("suggested_document_type")).strip()
	customer = cstr(row.get("customer")).strip()
	if not suggested_document:
		return ""
	if suggested_document_type == "Sales Invoice":
		if cstr(row.get("candidate_category")).strip() in {"invoice_payment_row_match", "pos_payment_match"}:
			amounts = []
			if row.get("payment_row_amount"):
				amounts.append(_("Payment Row: {0}").format(frappe.format_value(row.get("payment_row_amount"), {"fieldtype": "Currency"})))
			if row.get("payment_mode"):
				amounts.append(_("Mode: {0}").format(row.get("payment_mode")))
			suffix = f" — {customer}" if customer else ""
			amount_text = f" ({' | '.join(amounts)})" if amounts else ""
			return f"{suggested_document}{suffix}{amount_text}"
		amounts = []
		if row.get("sales_invoice_outstanding_amount"):
			amounts.append(_("Outstanding: {0}").format(frappe.format_value(row.get("sales_invoice_outstanding_amount"), {"fieldtype": "Currency"})))
		if row.get("sales_invoice_grand_total"):
			amounts.append(_("Invoice Total: {0}").format(frappe.format_value(row.get("sales_invoice_grand_total"), {"fieldtype": "Currency"})))
		suffix = f" — {customer}" if customer else ""
		amount_text = f" ({' | '.join(amounts)})" if amounts else ""
		return f"{suggested_document}{suffix}{amount_text}"
	if suggested_document_type == "Payment Entry":
		amounts = []
		if row.get("payment_entry_paid_amount"):
			amounts.append(_("Paid: {0}").format(frappe.format_value(row.get("payment_entry_paid_amount"), {"fieldtype": "Currency"})))
		if row.get("payment_entry_allocated_amount"):
			amounts.append(_("Allocated: {0}").format(frappe.format_value(row.get("payment_entry_allocated_amount"), {"fieldtype": "Currency"})))
		party = f" — {customer}" if customer else ""
		amount_text = f" ({' | '.join(amounts)})" if amounts else ""
		return f"Payment Entry {suggested_document}{party}{amount_text}"
	return f"{suggested_document_type} {suggested_document}".strip()


def get_report_summary(rows):
	settings = get_bank_transaction_matching_settings()
	if not rows:
		return [
			{
				"value": _("No Match Rows"),
				"label": _("Report Status"),
				"datatype": "Data",
				"indicator": "Orange",
			}
		]
	return [
		{
			"value": len(rows),
			"label": _("Bank Transactions"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": sum(1 for row in rows if row.get("match_confidence") == "Strong Match"),
			"label": _("Strong Matches"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": sum(1 for row in rows if row.get("action_status") == "Needs Review"),
			"label": _("Needs Review"),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"value": sum(1 for row in rows if row.get("action_status") == "Duplicate Candidate"),
			"label": _("Duplicate Candidates"),
			"datatype": "Int",
			"indicator": "Orange",
		},
		{
			"value": sum(1 for row in rows if row.get("action_status") == "Exception Only" or row.get("exception_type")),
			"label": _("Date/Account Exceptions"),
			"datatype": "Int",
			"indicator": "Red",
		},
		{
			"value": sum(1 for row in rows if row.get("match_record")),
			"label": _("Already Reviewed"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": sum(1 for row in rows if row.get("decision_status") == "Confirmed"),
			"label": _("Confirmed Matches"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": sum(1 for row in rows if row.get("auto_match_status") == "Eligible for Auto-Prepare"),
			"label": _("Eligible for Auto-Prepare"),
			"datatype": "Int",
			"indicator": "Blue",
		},
		{
			"value": sum(1 for row in rows if row.get("auto_match_status") == "Eligible for Auto-Confirm"),
			"label": _("Eligible for Auto-Confirm"),
			"datatype": "Int",
			"indicator": "Green",
		},
		{
			"value": cint(settings.get("minimum_possible_score") or 50),
			"label": _("Minimum Possible Score"),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]



def get_bank_transaction_matching_timing(filters=None):
	"""Developer-only timing helper for local report profiling."""
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_unmatched", 1)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_verified_invoices", 0)
	filters.setdefault("include_confirmed_matches", 0)
	filters.setdefault("review_queue_status", "Open Suggestions Only")
	filters.setdefault("include_rejected_candidates", 0)
	result_limit = normalize_result_limit(filters)
	filters["result_limit"] = result_limit
	validate_filters(filters)
	debug_timings = {}
	start = time.perf_counter()
	data = get_bank_transaction_matching_rows(filters=filters, limit=result_limit, debug_timings=debug_timings)
	total = time.perf_counter() - start
	return {
		"total_seconds": round(total, 3),
		"rows": len(data or []),
		"result_limit": result_limit,
		"timings": {key: round(value, 3) if isinstance(value, float) else value for key, value in debug_timings.items()},
	}



def profile_bank_transaction_matching_default_10():
	return get_bank_transaction_matching_timing({"result_limit": 10})


def profile_bank_transaction_matching_keyword_10():
	return get_bank_transaction_matching_timing({"reference_search": "RE-LIVE-BATCH-TEST", "result_limit": 10})


def profile_bank_transaction_matching_keyword_50():
	return get_bank_transaction_matching_timing({"reference_search": "RE-LIVE-BATCH-TEST", "result_limit": 50})


def profile_bank_transaction_matching_keyword_200():
	return get_bank_transaction_matching_timing({"reference_search": "RE-LIVE-BATCH-TEST", "result_limit": 200})
