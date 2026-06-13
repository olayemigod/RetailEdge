# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import get_first_day, getdate, nowdate
from retailedge.services.edgepay_reconciliation_readiness import (
	get_edgepay_reconciliation_readiness,
	find_edgepay_payment_entry_bank_match_candidates
)

def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(nowdate()))
	
	# Fetch evidence records matching filters
	db_filters = {}
	if filters.get("from_date") and filters.get("to_date"):
		db_filters["creation"] = ["between", [filters.get("from_date") + " 00:00:00", filters.get("to_date") + " 23:59:59"]]
	if filters.get("review_status"):
		db_filters["review_status"] = filters.get("review_status")
	if filters.get("reconciliation_status"):
		db_filters["reconciliation_status"] = filters.get("reconciliation_status")
		
	evidences = frappe.get_all("RetailEdge EdgePay Payment Evidence", filters=db_filters, fields=[
		"name", "source_doctype", "source_name", "amount", "currency", 
		"provider_reference", "payment_entry", "submission_status", 
		"reconciliation_status", "reconciliation_message"
	])
	
	rows = []
	for ev in evidences:
		# Double check if filter by company matches (if filter company is set and source doc supports company)
		if filters.get("company"):
			source_company = frappe.db.get_value(ev.source_doctype, ev.source_name, "company")
			if source_company != filters.get("company"):
				continue
				
		# Get candidate count
		candidates = find_edgepay_payment_entry_bank_match_candidates(ev.name)
		
		# Resolve blocking reason (which is reconciliation_message)
		blocking_reason = ev.reconciliation_message if ev.reconciliation_status in ("Blocked", "Exception") else ""
		
		rows.append({
			"evidence": ev.name,
			"source_doctype": ev.source_doctype,
			"source_name": ev.source_name,
			"amount": ev.amount,
			"currency": ev.currency,
			"provider_reference": ev.provider_reference,
			"payment_entry": ev.payment_entry,
			"submission_status": ev.submission_status,
			"reconciliation_status": ev.reconciliation_status,
			"candidate_count": len(candidates),
			"blocking_reason": blocking_reason
		})
		
	return get_columns(), rows, None, None, get_report_summary(rows)

def get_columns():
	return [
		{"label": _("Payment Evidence"), "fieldname": "evidence", "fieldtype": "Link", "options": "RetailEdge EdgePay Payment Evidence", "width": 170},
		{"label": _("Source DocType"), "fieldname": "source_doctype", "fieldtype": "Data", "width": 130},
		{"label": _("Source Name"), "fieldname": "source_name", "fieldtype": "Dynamic Link", "options": "source_doctype", "width": 160},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 90},
		{"label": _("Provider Reference"), "fieldname": "provider_reference", "fieldtype": "Data", "width": 150},
		{"label": _("Payment Entry"), "fieldname": "payment_entry", "fieldtype": "Link", "options": "Payment Entry", "width": 170},
		{"label": _("Submission Status"), "fieldname": "submission_status", "fieldtype": "Data", "width": 120},
		{"label": _("Reconciliation Status"), "fieldname": "reconciliation_status", "fieldtype": "Data", "width": 150},
		{"label": _("Candidate Count"), "fieldname": "candidate_count", "fieldtype": "Int", "width": 120},
		{"label": _("Blocking Reason"), "fieldname": "blocking_reason", "fieldtype": "Small Text", "width": 250}
	]

def get_report_summary(rows):
	return [
		{"label": _("Reconciled"), "value": sum(1 for row in rows if row.get("reconciliation_status") == "Reconciled"), "datatype": "Int", "indicator": "Green"},
		{"label": _("Ready"), "value": sum(1 for row in rows if row.get("reconciliation_status") == "Ready"), "datatype": "Int", "indicator": "Blue"},
		{"label": _("Matched"), "value": sum(1 for row in rows if row.get("reconciliation_status") == "Matched"), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Blocked / Not Ready"), "value": sum(1 for row in rows if row.get("reconciliation_status") in ("Blocked", "Exception", "Not Ready")), "datatype": "Int", "indicator": "Red"}
	]
