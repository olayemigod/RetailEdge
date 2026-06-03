from __future__ import annotations

from collections import Counter

import frappe
from frappe.utils import cint, cstr, flt, get_first_day, getdate, nowdate

from retailedge.bank_matching_operational_reports import (
	READINESS_ALREADY_RECONCILED,
	READINESS_EXCEPTION,
	READINESS_NEEDS_REVIEW,
	READINESS_NOT_READY,
	READINESS_READY,
	get_bank_match_reconciliation_readiness_rows,
)
from retailedge.bank_transaction_matching import INACTIVE_MATCH_STATUSES
from retailedge.branch_context import has_doctype, has_field
from retailedge.invoice_payment_audit import get_sales_invoice_payment_rows


HANDOFF_READY = "Ready for ERPNext Reconciliation"
HANDOFF_NEEDS_REVIEW = "Needs Review Before Reconciliation"
HANDOFF_NOT_ELIGIBLE = "Not Eligible for Reconciliation"
HANDOFF_ALREADY_RECONCILED = "Already Reconciled"
HANDOFF_EXCEPTION = "Exception / Manual Investigation Required"


def _default_handoff_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("include_already_reconciled", 0)
	filters.setdefault("include_exceptions", 1)
	filters.setdefault("include_rejected_cancelled", 0)
	return filters


def _bool(value, default=0):
	if value is None:
		return default
	if isinstance(value, str):
		return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
	return 1 if value else 0


def get_bank_transaction_reconciliation_context(bank_transaction):
	name = cstr(bank_transaction).strip()
	if not name or not has_doctype("Bank Transaction"):
		return {}
	fields = [
		"name",
		"date",
		"bank_account",
		"deposit",
		"withdrawal",
		"description",
		"reference_number",
		"party",
		"status",
	]
	if has_field("Bank Transaction", "company"):
		fields.append("company")
	if has_field("Bank Transaction", "retailedge_branch"):
		fields.append("retailedge_branch")
	elif has_field("Bank Transaction", "branch"):
		fields.append("branch")
	row = frappe.db.get_value("Bank Transaction", name, fields, as_dict=True) or {}
	amount = flt(row.get("deposit") or row.get("withdrawal"))
	return {
		"bank_transaction": row.get("name"),
		"bank_transaction_date": row.get("date"),
		"bank_account": row.get("bank_account"),
		"bank_transaction_amount": amount,
		"company": row.get("company"),
		"branch": row.get("retailedge_branch") or row.get("branch"),
		"reference": row.get("reference_number"),
		"narration": row.get("description"),
		"party": row.get("party"),
		"erpnext_reconciliation_target": row.get("name"),
		"erpnext_reconciliation_status": row.get("status"),
	}


def get_payment_event_reconciliation_context(candidate_doctype, candidate_name, match_doc=None):
	doctype = cstr(candidate_doctype).strip()
	name = cstr(candidate_name).strip()
	match_doc = frappe._dict(match_doc or {})
	if not doctype or not name:
		return {}
	if doctype == "Payment Entry" and has_doctype("Payment Entry"):
		fields = [
			"name",
			"posting_date",
			"paid_to",
			"paid_from",
			"received_amount",
			"paid_amount",
			"party",
			"party_type",
			"mode_of_payment",
			"docstatus",
			"reference_no",
		]
		if has_field("Payment Entry", "company"):
			fields.append("company")
		if has_field("Payment Entry", "retailedge_branch"):
			fields.append("retailedge_branch")
		row = frappe.db.get_value("Payment Entry", name, fields, as_dict=True) or {}
		return {
			"candidate_doctype": doctype,
			"candidate_name": name,
			"candidate_date": row.get("posting_date"),
			"candidate_account": cstr(row.get("paid_to") or row.get("paid_from")).strip(),
			"candidate_amount": flt(row.get("received_amount") or row.get("paid_amount")),
			"candidate_mode_of_payment": row.get("mode_of_payment"),
			"candidate_reference": row.get("reference_no"),
			"candidate_party": row.get("party"),
			"candidate_branch": row.get("retailedge_branch"),
			"candidate_docstatus": row.get("docstatus"),
			"payment_event_source": "Payment Entry",
		}
	if doctype == "Sales Invoice" and has_doctype("Sales Invoice"):
		doc = frappe.get_doc("Sales Invoice", name)
		payment_rows = []
		try:
			payment_rows = get_sales_invoice_payment_rows(doc)
		except Exception:
			payment_rows = []
		candidate_amount = flt(match_doc.get("payment_event_amount") or match_doc.get("candidate_amount") or 0)
		best_row = None
		best_diff = None
		for payment_row in payment_rows:
			if cstr(payment_row.get("payment_category")).strip().lower() == "cash":
				continue
			account = cstr(payment_row.get("account") or payment_row.get("expected_account")).strip()
			if not account:
				continue
			amount = flt(payment_row.get("base_amount") or payment_row.get("amount"))
			diff = abs(amount - candidate_amount)
			if best_row is None or diff < best_diff:
				best_row = payment_row
				best_diff = diff
		if not best_row:
			return {
				"candidate_doctype": doctype,
				"candidate_name": name,
				"candidate_date": getattr(doc, "posting_date", None),
				"candidate_account": "",
				"candidate_amount": 0,
				"candidate_mode_of_payment": "",
				"candidate_reference": name,
				"candidate_party": getattr(doc, "customer", None),
				"candidate_branch": getattr(doc, "retailedge_branch", None),
				"candidate_docstatus": getattr(doc, "docstatus", None),
				"payment_event_source": "Sales Invoice",
			}
		category = cstr(best_row.get("payment_category")).strip()
		return {
			"candidate_doctype": doctype,
			"candidate_name": name,
			"candidate_date": getattr(doc, "posting_date", None),
			"candidate_account": cstr(best_row.get("account") or best_row.get("expected_account")).strip(),
			"candidate_amount": flt(best_row.get("base_amount") or best_row.get("amount")),
			"candidate_mode_of_payment": best_row.get("mode_of_payment"),
			"candidate_reference": name,
			"candidate_party": getattr(doc, "customer", None),
			"candidate_branch": getattr(doc, "retailedge_branch", None),
			"candidate_docstatus": getattr(doc, "docstatus", None),
			"payment_row_reference": best_row.get("payment_row_index"),
			"payment_event_source": "POS Payment Row" if category == "Card / POS" else "Invoice Payment Row",
		}
	return {}


def _get_match_rows(filters=None, limit=500):
	filters = _default_handoff_filters(filters)
	readiness_filters = frappe._dict(filters.copy())
	readiness_filters["include_reconciled"] = 1
	readiness_filters["include_rejected_cancelled"] = 1
	return get_bank_match_reconciliation_readiness_rows(filters=readiness_filters, limit=limit)


def _get_conflict_counts(rows):
	active_rows = [
		row for row in rows
		if cstr(row.get("review_status")).strip() not in INACTIVE_MATCH_STATUSES
	]
	return {
		"by_bank_transaction": Counter(cstr(row.get("bank_transaction")).strip() for row in active_rows if cstr(row.get("bank_transaction")).strip()),
		"by_candidate": Counter(
			f"{cstr(row.get('suggested_document_type')).strip()}::{cstr(row.get('suggested_document')).strip()}"
			for row in active_rows
			if cstr(row.get("suggested_document_type")).strip() and cstr(row.get("suggested_document")).strip()
		),
	}


def classify_reconciliation_handoff(match_doc, conflict_counts=None):
	match_doc = frappe._dict(match_doc or {})
	review_status = cstr(match_doc.get("review_status") or match_doc.get("decision_status")).strip()
	candidate_type = cstr(match_doc.get("suggested_document_type")).strip()
	candidate_name = cstr(match_doc.get("suggested_document")).strip()
	candidate_category = cstr(match_doc.get("candidate_type") or match_doc.get("candidate_category")).strip()
	readiness_status = cstr(match_doc.get("reconciliation_readiness_status")).strip()
	account_status = cstr(match_doc.get("account_resolution_status")).strip()
	amount_scenario = cstr(match_doc.get("amount_scenario")).strip()
	blocking_reason = cstr(match_doc.get("exception_reason")).strip()
	bank_key = cstr(match_doc.get("bank_transaction")).strip()
	candidate_key = f"{candidate_type}::{candidate_name}" if candidate_type and candidate_name else ""
	bank_conflicts = cint((conflict_counts or {}).get("by_bank_transaction", {}).get(bank_key))
	candidate_conflicts = cint((conflict_counts or {}).get("by_candidate", {}).get(candidate_key))

	if readiness_status == READINESS_ALREADY_RECONCILED:
		return HANDOFF_ALREADY_RECONCILED, "Low", "Already reconciled in ERPNext; no RetailEdge action needed."

	if review_status in {"Rejected", "Cancelled"}:
		return HANDOFF_NOT_ELIGIBLE, "Low", "Rejected or cancelled matches are not eligible for reconciliation handoff."

	if not bank_key or not candidate_type or not candidate_name:
		return HANDOFF_NOT_ELIGIBLE, "High", "No valid bank transaction and payment-event candidate pair was found."

	if candidate_category in {"Cash", "cash", "invoice_context_only", "weak_invoice_total_similarity"}:
		return HANDOFF_NOT_ELIGIBLE, "High", "This match is not a bank-matchable payment event."

	if bank_conflicts > 1:
		return HANDOFF_EXCEPTION, "High", "This Bank Transaction appears in multiple active or confirmed matches."

	if candidate_conflicts > 1:
		return HANDOFF_EXCEPTION, "High", "This payment event appears in multiple active or confirmed matches."

	if account_status == "mismatch":
		return HANDOFF_EXCEPTION, "High", "Bank and payment accounts do not align for safe reconciliation."

	if account_status == "unresolved":
		return HANDOFF_NEEDS_REVIEW, "High", "Bank/payment account mapping must be reviewed before reconciliation."

	if amount_scenario and amount_scenario not in {"Submitted Payment Entry Amount", "Exact Invoice Payment Row Amount", "Submitted Payment Entry Amount Match", "Exact Invoice Payment Row Match"}:
		lowered = amount_scenario.lower()
		if "variance" in lowered or "partial" in lowered or "overpayment" in lowered or "multi" in lowered:
			return HANDOFF_EXCEPTION, "High", blocking_reason or f"{amount_scenario} requires manual investigation."

	if readiness_status == READINESS_EXCEPTION:
		return HANDOFF_EXCEPTION, "High", blocking_reason or "Manual investigation is required before reconciliation."

	if readiness_status in {READINESS_NOT_READY, READINESS_NEEDS_REVIEW}:
		return HANDOFF_NEEDS_REVIEW, "Medium", blocking_reason or "Review the match before handing off to ERPNext reconciliation."

	if readiness_status == READINESS_READY and review_status in {"Confirmed", "Auto Confirmed"}:
		return HANDOFF_READY, "High", "Ready to reconcile manually in ERPNext."

	return HANDOFF_NEEDS_REVIEW, "Medium", blocking_reason or "Review the match before reconciliation."


def build_erpnext_reconciliation_guidance(match_doc):
	match_doc = frappe._dict(match_doc or {})
	handoff_status = cstr(match_doc.get("handoff_status")).strip()
	candidate_type = cstr(match_doc.get("candidate_doctype") or match_doc.get("suggested_document_type")).strip()
	candidate_name = cstr(match_doc.get("candidate_name") or match_doc.get("suggested_document")).strip()
	bank_transaction = cstr(match_doc.get("bank_transaction")).strip()
	blocking_reason = cstr(match_doc.get("blocking_reason")).strip()
	if handoff_status == HANDOFF_READY:
		return {
			"recommended_action": f"Open ERPNext Bank Reconciliation and reconcile Bank Transaction {bank_transaction} against {candidate_type} {candidate_name}.",
			"reviewer_message": "RetailEdge has confirmed this payment-event match and it appears ready for manual ERPNext reconciliation.",
			"erpnext_reconciliation_target": bank_transaction,
			"erpnext_reconciliation_notes": f"Use {candidate_type} {candidate_name} as the reconciliation target. Do not reconcile from RetailEdge.",
		}
	if handoff_status == HANDOFF_ALREADY_RECONCILED:
		return {
			"recommended_action": "No reconciliation handoff is needed.",
			"reviewer_message": "ERPNext already appears to have handled reconciliation for this bank transaction.",
			"erpnext_reconciliation_target": bank_transaction,
			"erpnext_reconciliation_notes": "Review ERPNext Bank Transaction status before making any further changes.",
		}
	if handoff_status == HANDOFF_EXCEPTION:
		return {
			"recommended_action": "Investigate the exception before attempting ERPNext reconciliation.",
			"reviewer_message": blocking_reason or "A conflicting or unsafe condition was detected.",
			"erpnext_reconciliation_target": bank_transaction,
			"erpnext_reconciliation_notes": "Do not reconcile from RetailEdge. Resolve the exception and confirm the correct match first.",
		}
	if handoff_status == HANDOFF_NOT_ELIGIBLE:
		return {
			"recommended_action": "Do not reconcile this row from RetailEdge.",
			"reviewer_message": blocking_reason or "This row is not a bank-matchable reconciliation candidate.",
			"erpnext_reconciliation_target": bank_transaction,
			"erpnext_reconciliation_notes": "Cash, context-only, rejected, cancelled, and invalid candidate rows must stay outside the handoff flow.",
		}
	return {
		"recommended_action": "Review the match and resolve any blocking issues before ERPNext reconciliation.",
		"reviewer_message": blocking_reason or "This row still needs review before it is safe to reconcile.",
		"erpnext_reconciliation_target": bank_transaction,
		"erpnext_reconciliation_notes": "RetailEdge is providing guidance only; reconcile manually in ERPNext after review.",
	}


def _build_handoff_row(readiness_row, conflict_counts):
	readiness_row = frappe._dict(readiness_row or {})
	payment_context = get_payment_event_reconciliation_context(
		readiness_row.get("suggested_document_type"),
		readiness_row.get("suggested_document"),
		match_doc=readiness_row,
	)
	bank_context = get_bank_transaction_reconciliation_context(readiness_row.get("bank_transaction"))
	enriched = frappe._dict(dict(readiness_row))
	enriched.update(payment_context)
	enriched.update(bank_context)
	handoff_status, handoff_priority, blocking_reason = classify_reconciliation_handoff(enriched, conflict_counts=conflict_counts)
	enriched["handoff_status"] = handoff_status
	enriched["handoff_priority"] = handoff_priority
	enriched["blocking_reason"] = blocking_reason
	guidance = build_erpnext_reconciliation_guidance(enriched)
	enriched.update(guidance)
	enriched["match_type"] = readiness_row.get("candidate_type") or readiness_row.get("suggested_document_type")
	enriched["match_status"] = readiness_row.get("review_status")
	enriched["readiness_status"] = readiness_row.get("reconciliation_readiness_status")
	enriched["notes"] = guidance.get("erpnext_reconciliation_notes")
	return {
		"handoff_status": enriched.get("handoff_status"),
		"handoff_priority": enriched.get("handoff_priority"),
		"bank_transaction": enriched.get("bank_transaction"),
		"bank_transaction_date": enriched.get("bank_transaction_date") or readiness_row.get("transaction_date"),
		"bank_account": enriched.get("bank_account"),
		"bank_transaction_amount": flt(enriched.get("bank_transaction_amount") or readiness_row.get("bank_amount")),
		"candidate_doctype": cstr(enriched.get("candidate_doctype") or readiness_row.get("suggested_document_type")).strip(),
		"candidate_name": cstr(enriched.get("candidate_name") or readiness_row.get("suggested_document")).strip(),
		"candidate_date": enriched.get("candidate_date"),
		"candidate_account": enriched.get("candidate_account") or readiness_row.get("resolved_payment_account") or readiness_row.get("payment_account"),
		"candidate_amount": flt(enriched.get("candidate_amount") or readiness_row.get("payment_event_amount")),
		"match_type": enriched.get("match_type"),
		"match_status": enriched.get("match_status"),
		"match_confidence": readiness_row.get("match_confidence"),
		"match_score": readiness_row.get("match_score"),
		"readiness_status": enriched.get("readiness_status"),
		"recommended_action": enriched.get("recommended_action"),
		"reviewer_message": enriched.get("reviewer_message"),
		"blocking_reason": enriched.get("blocking_reason"),
		"erpnext_reconciliation_target": enriched.get("erpnext_reconciliation_target"),
		"erpnext_reconciliation_notes": enriched.get("erpnext_reconciliation_notes"),
		"payment_event_source": enriched.get("payment_event_source") or readiness_row.get("payment_event_source"),
		"payment_row_reference": enriched.get("payment_row_reference"),
		"party": enriched.get("candidate_party") or readiness_row.get("party"),
		"branch": enriched.get("candidate_branch") or readiness_row.get("branch"),
		"bank_match_review": readiness_row.get("bank_match_review"),
	}


def _handoff_status_allowed(row, filters):
	filters = frappe._dict(filters or {})
	selected_status = cstr(filters.get("handoff_status")).strip()
	if selected_status:
		return cstr(row.get("handoff_status")).strip() == selected_status
	include_already_reconciled = _bool(filters.get("include_already_reconciled"), 0)
	include_exceptions = _bool(filters.get("include_exceptions"), 1)
	if row.get("handoff_status") == HANDOFF_ALREADY_RECONCILED and not include_already_reconciled:
		return False
	if row.get("handoff_status") == HANDOFF_EXCEPTION and not include_exceptions:
		return False
	allowed = {HANDOFF_READY, HANDOFF_NEEDS_REVIEW}
	if include_exceptions:
		allowed.add(HANDOFF_EXCEPTION)
	if include_already_reconciled:
		allowed.add(HANDOFF_ALREADY_RECONCILED)
	return row.get("handoff_status") in allowed


def get_reconciliation_handoff_summary(filters=None, limit=500):
	filters = _default_handoff_filters(filters)
	rows = _get_match_rows(filters=filters, limit=min(int(limit or 500), 2000))
	conflict_counts = _get_conflict_counts(rows)
	handoff_rows = []
	for readiness_row in rows:
		if filters.get("candidate_doctype") and cstr(readiness_row.get("suggested_document_type")).strip() != cstr(filters.get("candidate_doctype")).strip():
			continue
		if filters.get("match_type") and cstr(readiness_row.get("candidate_type")).strip() != cstr(filters.get("match_type")).strip():
			continue
		if filters.get("match_status") and cstr(readiness_row.get("review_status")).strip() != cstr(filters.get("match_status")).strip():
			continue
		row = _build_handoff_row(readiness_row, conflict_counts)
		if not _handoff_status_allowed(row, filters):
			continue
		handoff_rows.append(row)
	counts = Counter(cstr(row.get("handoff_status")).strip() for row in handoff_rows)
	return {
		"rows": handoff_rows,
		"summary": {
			"ready": counts.get(HANDOFF_READY, 0),
			"needs_review": counts.get(HANDOFF_NEEDS_REVIEW, 0),
			"not_eligible": counts.get(HANDOFF_NOT_ELIGIBLE, 0),
			"already_reconciled": counts.get(HANDOFF_ALREADY_RECONCILED, 0),
			"exception": counts.get(HANDOFF_EXCEPTION, 0),
			"total": len(handoff_rows),
		},
	}


def get_reconciliation_handoff_for_match(match_name):
	match_name = cstr(match_name).strip()
	if not match_name:
		return {}
	summary = get_reconciliation_handoff_summary(
		{
			"from_date": "2000-01-01",
			"to_date": str(getdate(nowdate())),
			"include_already_reconciled": 1,
			"include_exceptions": 1,
			"include_rejected_cancelled": 1,
		},
		limit=5000,
	)
	for row in summary.get("rows") or []:
		if cstr(row.get("bank_match_review")).strip() == match_name:
			return {
				"match_name": row.get("bank_match_review"),
				"handoff_status": row.get("handoff_status"),
				"handoff_priority": row.get("handoff_priority"),
				"recommended_action": row.get("recommended_action"),
				"reviewer_message": row.get("reviewer_message"),
				"blocking_reason": row.get("blocking_reason"),
				"erpnext_reconciliation_target": row.get("erpnext_reconciliation_target"),
				"erpnext_reconciliation_notes": row.get("erpnext_reconciliation_notes"),
				"bank_transaction": row.get("bank_transaction"),
				"candidate_doctype": row.get("candidate_doctype"),
				"candidate_name": row.get("candidate_name"),
				"match_type": row.get("match_type"),
				"match_status": row.get("match_status"),
				"readiness_status": row.get("readiness_status"),
			}
	return {}
