from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint, cstr, get_first_day, getdate, nowdate

from retailedge.bank_transaction_matching import (
	get_bank_transaction_matching_rows,
	get_bank_transaction_matching_settings,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_unmatched", 1)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_verified_invoices", 0)
	validate_filters(filters)
	data = get_bank_transaction_matching_rows(filters=filters, limit=filters.get("limit") or 500)
	for row in data:
		row["suggested_match"] = build_suggested_match_label(row)
	message = None if data else _("No matching bank transactions were found for the selected filters.")
	return get_columns(), data, message, None, get_report_summary(data)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "transaction_date", "fieldtype": "Date", "width": 95},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 120},
		{"label": _("Bank Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("SI/PE Amount"), "fieldname": "candidate_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Difference"), "fieldname": "amount_difference", "fieldtype": "Currency", "width": 95},
		{"label": _("Customer / Party"), "fieldname": "customer", "fieldtype": "Data", "width": 160},
		{"label": _("Suggested Match"), "fieldname": "suggested_match", "fieldtype": "Data", "width": 210},
		{"label": _("Match Confidence"), "fieldname": "match_confidence", "fieldtype": "Data", "width": 115},
		{"label": _("Match Score"), "fieldname": "match_score", "fieldtype": "Int", "width": 80},
		{"label": _("Issue / Reason"), "fieldname": "match_reason", "fieldtype": "Small Text", "width": 260},
		{"label": _("Action Status"), "fieldname": "action_status", "fieldtype": "Data", "width": 135},
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
		return f"{suggested_document} — {customer}" if customer else suggested_document
	if suggested_document_type == "Payment Entry":
		return f"Payment Entry {suggested_document}"
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
			"value": cint(settings.get("minimum_possible_score") or 50),
			"label": _("Minimum Possible Score"),
			"datatype": "Int",
			"indicator": "Blue",
		},
	]
