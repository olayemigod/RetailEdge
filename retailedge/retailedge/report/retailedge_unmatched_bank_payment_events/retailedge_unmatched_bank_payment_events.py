from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	get_operational_report_message,
	get_unmatched_bank_payment_event_rows,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("payment_event_type", "All")
	filters.setdefault("include_already_matched", 0)
	filters.setdefault("include_cash", 0)
	filters.setdefault("include_candidate_preview", 0)
	rows = get_unmatched_bank_payment_event_rows(filters=filters, limit=filters.get("limit") or 500)
	message = get_operational_report_message() or (None if rows else _("No unmatched bank payment events were found for the selected filters."))
	return get_columns(), rows, message, None, get_report_summary(rows)


def get_columns():
	return [
		{"label": _("Payment Event Type"), "fieldname": "payment_event_type", "fieldtype": "Data", "width": 130},
		{"label": _("Payment Event Document"), "fieldname": "payment_event_document", "fieldtype": "Dynamic Link", "options": "suggested_document_type", "width": 170},
		{"label": _("Payment Row Reference / Index"), "fieldname": "payment_row_reference", "fieldtype": "Data", "width": 120},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 150},
		{"label": _("Branch"), "fieldname": "branch", "fieldtype": "Link", "options": "Branch", "width": 130},
		{"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 150},
		{"label": _("Customer / Supplier"), "fieldname": "customer_supplier", "fieldtype": "Data", "width": 160},
		{"label": _("Mode of Payment"), "fieldname": "mode_of_payment", "fieldtype": "Link", "options": "Mode of Payment", "width": 130},
		{"label": _("Payment Account"), "fieldname": "payment_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Resolved Canonical Account"), "fieldname": "resolved_canonical_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Reference No"), "fieldname": "reference_no", "fieldtype": "Data", "width": 130},
		{"label": _("Linked Sales Invoice"), "fieldname": "linked_sales_invoice", "fieldtype": "Link", "options": "Sales Invoice", "width": 160},
		{"label": _("Linked Payment Entry"), "fieldname": "linked_payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 150},
		{"label": _("Existing Bank Match"), "fieldname": "existing_bank_match", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 160},
		{"label": _("Match Status"), "fieldname": "match_status", "fieldtype": "Data", "width": 120},
		{"label": _("Candidate Bank Transaction"), "fieldname": "candidate_bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 165},
		{"label": _("Reason / Exception"), "fieldname": "reason_exception", "fieldtype": "Small Text", "width": 240},
		{"label": _("Days Outstanding"), "fieldname": "days_outstanding", "fieldtype": "Int", "width": 110},
	]


def get_report_summary(rows):
	return [
		{"label": _("Unmatched Payment Events"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Payment Entries"), "value": sum(1 for row in rows if row.get("payment_event_type") == "Payment Entry"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Invoice / POS Payment Rows"), "value": sum(1 for row in rows if row.get("payment_event_type") != "Payment Entry"), "datatype": "Int", "indicator": "Blue"},
	]
