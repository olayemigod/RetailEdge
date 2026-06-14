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
		
	evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters=db_filters, fields=[
		"name", "edgepay_handoff_event", "edgepay_payment_request", "source_doctype", "source_name",
		"amount", "currency", "request_status", "transaction_status", "review_status", "posting_status",
		"submission_status", "reconciliation_status", "payment_entry", "linked_bank_transaction",
		"linked_bank_match_review", "modified"
	])
	
	rows = []
	for ev in evidences:
		if filters.get("company"):
			source_company = frappe.db.get_value(ev.source_doctype, ev.source_name, "company")
			if source_company != filters.get("company"):
				continue
				
		# Fetch handoff status
		handoff_status = ""
		if ev.edgepay_handoff_event:
			handoff_status = frappe.db.get_value("RetailEdge EdgePay Handoff Log", {"edgepay_event": ev.edgepay_handoff_event}, "processing_status") or "Processed"
			
		rows.append({
			"payment_request": ev.edgepay_payment_request,
			"handoff_log": ev.edgepay_handoff_event,
			"evidence": ev.name,
			"source_doctype": ev.source_doctype,
			"source_name": ev.source_name,
			"amount": ev.amount,
			"currency": ev.currency,
			"handoff_status": handoff_status,
			"review_status": ev.review_status,
			"posting_status": ev.posting_status,
			"submission_status": ev.submission_status,
			"reconciliation_status": ev.reconciliation_status,
			"payment_entry": ev.payment_entry,
			"bank_transaction": ev.linked_bank_transaction,
			"bank_match_review": ev.linked_bank_match_review,
			"modified": ev.modified
		})
		
	return get_columns(), rows, None, None, get_report_summary(rows)

def get_columns():
	return [
		{"label": _("Payment Request"), "fieldname": "payment_request", "fieldtype": "Link", "options": "EdgePay Payment Request", "width": 170},
		{"label": _("Handoff Log"), "fieldname": "handoff_log", "fieldtype": "Link", "options": "RetailEdge EdgePay Handoff Log", "width": 170},
		{"label": _("Payment Evidence"), "fieldname": "evidence", "fieldtype": "Link", "options": "RetailEdge EdgePay Payment Evidence", "width": 170},
		{"label": _("Source DocType"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 130},
		{"label": _("Source Name"), "fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 160},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 90},
		{"label": _("Handoff Status"), "fieldname": "handoff_status", "fieldtype": "Data", "width": 120},
		{"label": _("Review Status"), "fieldname": "review_status", "fieldtype": "Data", "width": 120},
		{"label": _("Posting Status"), "fieldname": "posting_status", "fieldtype": "Data", "width": 120},
		{"label": _("Submission Status"), "fieldname": "submission_status", "fieldtype": "Data", "width": 120},
		{"label": _("Reconciliation Status"), "fieldname": "reconciliation_status", "fieldtype": "Data", "width": 140},
		{"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 170},
		{"label": _("Bank Transaction"), "fieldname": "bank_transaction", "fieldtype": "Link", "options": "Bank Transaction", "width": 170},
		{"label": _("Bank Match Review"), "fieldname": "bank_match_review", "fieldtype": "Link", "options": "RetailEdge Bank Transaction Match", "width": 170},
		{"label": _("Last Action"), "fieldname": "modified", "fieldtype": "Datetime", "width": 160}
	]

def get_report_summary(rows):
	return [
		{"label": _("Total Requests"), "value": len(rows), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Handoff Processed"), "value": sum(1 for r in rows if r.get("handoff_status") == "Processed"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Evidence Reviewed"), "value": sum(1 for r in rows if r.get("review_status") == "Reviewed"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Payment Entries Submitted"), "value": sum(1 for r in rows if r.get("submission_status") == "Submitted"), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Reconciliation Confirmed"), "value": sum(1 for r in rows if r.get("reconciliation_status") in ("Matched", "Reconciled")), "datatype": "Int", "indicator": "Green"}
	]
