from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import getdate

from retailedge.payment_evidence_matching import (
	get_payment_evidence_match_list,
	get_payment_evidence_match_summary,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_payment_evidence_match_list(filters=filters, limit=filters.get("limit") or 500)
	return get_columns(), data, None, None, get_report_summary(filters)


def validate_filters(filters):
	if filters.get("from_date") and filters.get("to_date") and getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def get_columns():
	return [
		{"label": _("Sales Invoice"), "fieldname": "sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 150},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 95},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 155},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 155},
		{"label": _("Payment Category"), "fieldname": "payment_category", "fieldtype": "Data", "width": 120},
		{"label": _("Payment Amount"), "fieldname": "payment_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Evidence Type"), "fieldname": "evidence_type", "fieldtype": "Data", "width": 140},
		{"label": _("Evidence Document"), "fieldname": "evidence_document", "fieldtype": "Data", "width": 160},
		{"label": _("Statement Import"), "fieldname": "statement_import", "fieldtype": "Link", "options": "RetailEdge Payment Statement Import", "width": 160},
		{"label": _("Statement Import Row"), "fieldname": "statement_import_row", "fieldtype": "Data", "width": 150},
		{"label": _("Mapping Template"), "fieldname": "mapping_template", "fieldtype": "Link", "options": "RetailEdge Statement Mapping Template", "width": 160},
		{"label": _("Evidence Amount"), "fieldname": "evidence_amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Amount Difference"), "fieldname": "amount_difference", "fieldtype": "Currency", "width": 120},
		{"label": _("Normalized Reference"), "fieldname": "normalized_reference", "fieldtype": "Data", "width": 150},
		{"label": _("Evidence Fingerprint"), "fieldname": "evidence_fingerprint", "fieldtype": "Data", "width": 200},
		{"label": _("Reference Match"), "fieldname": "reference_match", "fieldtype": "Check", "width": 110},
		{"label": _("Amount Match"), "fieldname": "amount_match", "fieldtype": "Check", "width": 105},
		{"label": _("Date Match"), "fieldname": "date_match", "fieldtype": "Check", "width": 90},
		{"label": _("Account Match"), "fieldname": "account_match", "fieldtype": "Check", "width": 105},
		{"label": _("Party Match"), "fieldname": "party_match", "fieldtype": "Check", "width": 95},
		{"label": _("Match Score"), "fieldname": "match_score", "fieldtype": "Int", "width": 90},
		{"label": _("Confidence"), "fieldname": "match_confidence", "fieldtype": "Data", "width": 90},
		{"label": _("Match Status"), "fieldname": "match_status", "fieldtype": "Data", "width": 130},
		{"label": _("Duplicate Status"), "fieldname": "duplicate_status", "fieldtype": "Data", "width": 130},
		{"label": _("Duplicate Of"), "fieldname": "duplicate_of", "fieldtype": "Data", "width": 130},
		{"label": _("Already Matched Invoice"), "fieldname": "already_matched_invoice", "fieldtype": "Check", "width": 130},
		{"label": _("Issue Summary"), "fieldname": "issue_summary", "fieldtype": "Small Text", "width": 260},
	]


def get_report_summary(filters):
	summary = get_payment_evidence_match_summary(filters=filters)
	return [
		{"value": summary.get("invoice_count"), "label": _("Invoices"), "datatype": "Int", "indicator": "Blue"},
		{
			"value": summary.get("matched_invoice_count"),
			"label": _("Matched Invoices"),
			"datatype": "Int",
			"indicator": "Green" if summary.get("matched_invoice_count") else "Blue",
		},
		{
			"value": summary.get("duplicate_suspected_count"),
			"label": _("Duplicates Suspected"),
			"datatype": "Int",
			"indicator": "Red" if summary.get("duplicate_suspected_count") else "Green",
		},
		{
			"value": summary.get("unmatched_invoice_count"),
			"label": _("Unmatched Invoices"),
			"datatype": "Int",
			"indicator": "Orange" if summary.get("unmatched_invoice_count") else "Green",
		},
	]
