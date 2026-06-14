# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate

def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(nowdate()))
	
	db_filters = {}
	if filters.get("from_date") and filters.get("to_date"):
		db_filters["creation"] = ["between", [filters.get("from_date") + " 00:00:00", filters.get("to_date") + " 23:59:59"]]
	if filters.get("review_status"):
		db_filters["review_status"] = filters.get("review_status")
	if filters.get("reconciliation_status"):
		db_filters["reconciliation_status"] = filters.get("reconciliation_status")
	if filters.get("posting_status"):
		db_filters["posting_status"] = filters.get("posting_status")
	if filters.get("submission_status"):
		db_filters["submission_status"] = filters.get("submission_status")
		
	evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters=db_filters, fields=[
		"name", "edgepay_handoff_event", "edgepay_payment_request", "source_doctype", "source_name",
		"amount", "currency", "provider", "provider_reference", "review_status", "posting_status",
		"submission_status", "reconciliation_status", "payment_entry", "linked_bank_transaction",
		"linked_bank_match_review", "reconciliation_message", "creation", "modified"
	])
	
	rows = []
	for ev in evidences:
		if filters.get("company"):
			source_company = frappe.db.get_value(ev.source_doctype, ev.source_name, "company")
			if source_company != filters.get("company"):
				continue
				
		rows.append({
			"evidence": ev.name,
			"edgepay_handoff_event": ev.edgepay_handoff_event,
			"source_doctype": ev.source_doctype,
			"source_name": ev.source_name,
			"amount": ev.amount,
			"currency": ev.currency,
			"provider": ev.provider,
			"provider_reference": ev.provider_reference,
			"review_status": ev.review_status,
			"posting_status": ev.posting_status,
			"submission_status": ev.submission_status,
			"reconciliation_status": ev.reconciliation_status,
			"payment_entry": ev.payment_entry,
			"linked_bank_transaction": ev.linked_bank_transaction,
			"linked_bank_match_review": ev.linked_bank_match_review,
			"reconciliation_message": ev.reconciliation_message,
			"creation": ev.creation,
			"modified": ev.modified
		})
		
	return get_columns(), rows, None, None, get_report_summary(rows)

def get_columns():
	return [
		{"label": _("Payment Evidence"), "fieldname": "evidence", "fieldtype": "Link", "options": "RetailEdge EdgePay Payment Evidence", "width": 170},
		{"label": _("Handoff Event"), "fieldname": "edgepay_handoff_event", "fieldtype": "Link", "options": "EdgePay Status Handoff Event", "width": 170},
		{"label": _("Source DocType"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 130},
		{"label": _("Source Name"), "fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 160},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 90},
		{"label": _("Provider"), "fieldname": "provider", "fieldtype": "Data", "width": 130},
		{"label": _("Provider Reference"), "fieldname": "provider_reference", "fieldtype": "Data", "width": 150},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 120},
		{"label": _("Posting Status"), "fieldname": "posting_status", "fieldtype": "Data", "width": 120},
		{"label": _("Submission Status"), "fieldname": "submission_status", "fieldtype": "Data", "width": 120},
		{"label": _("Reconciliation Status"), "fieldname": "reconciliation_status", "fieldtype": "Data", "width": 140},
		{"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 170},
		{"label": _("Linked Bank Transaction"), "fieldname": "linked_bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 170},
		{"label": _("Linked Bank Match Review"), "fieldname": "linked_bank_match_review", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 170},
		{"label": _("Reconciliation Message"), "fieldname": "reconciliation_message", "fieldtype": "Small Text", "width": 200},
		{"label": _("Created On"), "fieldname": "creation", "fieldtype": "Datetime", "width": 160},
		{"label": _("Modified On"), "fieldname": "modified", "fieldtype": "Datetime", "width": 160}
	]

def get_report_summary(rows):
	return [
		{"label": _("Total Evidence"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Pending Review"), "value": sum(1 for r in rows if r.get("review_status") == "Pending Review"), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Reviewed / Ready"), "value": sum(1 for r in rows if r.get("review_status") == "Reviewed"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Submitted PE"), "value": sum(1 for r in rows if r.get("submission_status") == "Submitted"), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Blocked / Exception"), "value": sum(1 for r in rows if r.get("reconciliation_status") in ("Blocked", "Exception")), "datatype": "Int", "indicator": "Red"}
	]
