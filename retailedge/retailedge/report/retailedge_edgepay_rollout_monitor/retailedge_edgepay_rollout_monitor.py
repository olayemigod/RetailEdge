# -*- coding: utf-8 -*-
from __future__ import annotations
import frappe
from frappe import _
from frappe.utils import add_days, now_datetime

def execute(filters=None):
	filters = frappe._dict(filters or {})
	stale_days = int(filters.get("stale_days") or 3)
	stale_threshold = add_days(now_datetime(), -stale_days)

	# Fetch counts from DB
	pending_review = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"review_status": "Pending Review"})
	draft_prepared = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"review_status": "Reviewed", "posting_status": "Draft Created"})
	submitted_pe = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"submission_status": "Submitted"})
	reconciliation_ready = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Ready"})
	match_reviews = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Matched"})
	confirmed_matches = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Reconciled"})
	blocked_records = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"reconciliation_status": "Blocked"})
	exception_records = frappe.db.count("RetailEdge EdgePay Payment Evidence", {"review_status": "Exception"})
	
	# Failed handoffs
	failed_handoffs = frappe.db.count("RetailEdge EdgePay Handoff Log", {"processing_status": "Failed"})

	# Stale records
	# 1. Handoff logs in Pending status older than threshold
	stale_handoffs = frappe.db.count("RetailEdge EdgePay Handoff Log", {
		"processing_status": "Pending",
		"creation": ["<=", stale_threshold]
	})
	
	# 2. Payment Evidence not fully reconciled/blocked older than threshold
	stale_evidence = frappe.db.count("RetailEdge EdgePay Payment Evidence", {
		"reconciliation_status": ["not in", ["Reconciled", "Blocked"]],
		"modified": ["<=", stale_threshold]
	})

	stale_total = stale_handoffs + stale_evidence

	# Construct rows
	rows = [
		{
			"metric": _("Pending Evidence Review"),
			"count": pending_review,
			"status": "Action Required" if pending_review > 0 else "Healthy",
			"description": _("EdgePay Payment Evidence records awaiting reviewer approval.")
		},
		{
			"metric": _("Draft Payment Entries Prepared"),
			"count": draft_prepared,
			"status": "Action Required" if draft_prepared > 0 else "Healthy",
			"description": _("Payment Entries prepared in Draft status, awaiting manual submission.")
		},
		{
			"metric": _("Submitted Payment Entries"),
			"count": submitted_pe,
			"status": "Healthy",
			"description": _("Payment Entries successfully posted to the general ledger.")
		},
		{
			"metric": _("Reconciliation-Ready Records"),
			"count": reconciliation_ready,
			"status": "Action Required" if reconciliation_ready > 0 else "Healthy",
			"description": _("Submitted Payment Entries awaiting bank matching review.")
		},
		{
			"metric": _("Match Reviews Created"),
			"count": match_reviews,
			"status": "Under Review" if match_reviews > 0 else "Healthy",
			"description": _("Bank Match Reviews created, awaiting manager confirmation.")
		},
		{
			"metric": _("Confirmed Matches"),
			"count": confirmed_matches,
			"status": "Healthy",
			"description": _("Bank Match Reviews manually confirmed.")
		},
		{
			"metric": _("Blocked/Exception Records"),
			"count": blocked_records + exception_records,
			"status": "Alert" if (blocked_records + exception_records) > 0 else "Healthy",
			"description": _("Evidence or matching blocked due to preflight mismatch.")
		},
		{
			"metric": _("Failed Handoffs"),
			"count": failed_handoffs,
			"status": "Alert" if failed_handoffs > 0 else "Healthy",
			"description": _("EdgePay handoffs that failed validation/intake.")
		},
		{
			"metric": _("Stale Records"),
			"count": stale_total,
			"status": "Warning" if stale_total > 0 else "Healthy",
			"description": _("Unreconciled evidence/handoffs older than {0} days.").format(stale_days)
		}
	]

	return get_columns(), rows, None, None, get_report_summary(rows)

def get_columns():
	return [
		{"label": _("Metric / Category"), "fieldname": "metric", "fieldtype": "Data", "width": 250},
		{"label": _("Count"), "fieldname": "count", "fieldtype": "Int", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 150},
		{"label": _("Description / Detail"), "fieldname": "description", "fieldtype": "Data", "width": 450}
	]

def get_report_summary(rows):
	summary_map = {r["metric"]: r["count"] for r in rows}
	return [
		{"label": _("Pending Review"), "value": summary_map.get(_("Pending Evidence Review"), 0), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Draft Prepared"), "value": summary_map.get(_("Draft Payment Entries Prepared"), 0), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Reconciliation Ready"), "value": summary_map.get(_("Reconciliation-Ready Records"), 0), "datatype": "Int", "indicator": "Orange"},
		{"label": _("Failed/Blocked"), "value": summary_map.get(_("Failed Handoffs"), 0) + summary_map.get(_("Blocked/Exception Records"), 0), "datatype": "Int", "indicator": "Red"},
		{"label": _("Stale Records"), "value": summary_map.get(_("Stale Records"), 0), "datatype": "Int", "indicator": "Red"}
	]
