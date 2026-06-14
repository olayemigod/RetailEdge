from __future__ import annotations

import json
from typing import Any

import frappe
from frappe.utils import cstr, flt

from retailedge.bank_matching_operational_reports import (
	READINESS_ALREADY_RECONCILED,
	_bulk_hydrate_match_candidate_contexts,
	_readiness_for_match_row,
	_safe_load_json,
)
from retailedge.bank_transaction_matching import (
	INACTIVE_MATCH_STATUSES,
	assert_can_access_bank_transaction_matching,
	_invoice_payment_row_is_bank_matchable,
	_resolve_account_match_payload,
)
from retailedge.branch_context import has_doctype
from retailedge.invoice_payment_audit import get_payment_entries_for_sales_invoice, get_sales_invoice_payment_rows
from retailedge.reconciliation_handoff import (
	HANDOFF_ALREADY_RECONCILED,
	HANDOFF_EXCEPTION,
	HANDOFF_NEEDS_REVIEW,
	HANDOFF_NOT_ELIGIBLE,
	HANDOFF_READY,
	classify_reconciliation_handoff,
	get_bank_transaction_reconciliation_context,
	get_payment_event_reconciliation_context,
)


PREFLIGHT_READY = "Ready"
PREFLIGHT_NOT_READY = "Not Ready"
PREFLIGHT_ALREADY_RECONCILED = "Already Reconciled"
PREFLIGHT_NEEDS_REVIEW = "Needs Review"
PREFLIGHT_TARGET_AMBIGUOUS = "Target Ambiguous"
PREFLIGHT_EXCEPTION = "Exception"

READINESS_GROUP_READY = "Ready"
READINESS_GROUP_BLOCKED = "Blocked"
READINESS_GROUP_ALREADY_HANDLED = "Already Handled"
READINESS_GROUP_NEEDS_REVIEW = "Needs Review"

BLOCK_NONE = "ready"
BLOCK_ALREADY_HANDLED = "already_handled"
BLOCK_UNCONFIRMED = "not_confirmed"
BLOCK_UNSUPPORTED_CANDIDATE_TYPE = "unsupported_candidate_type"
BLOCK_MISSING_SOURCE_DOCUMENT = "missing_source_document"
BLOCK_MISSING_BANK_TRANSACTION = "missing_bank_transaction"
BLOCK_BANK_ACCOUNT_MISMATCH = "bank_account_mismatch"
BLOCK_AMOUNT_MISMATCH = "amount_mismatch"
BLOCK_DATE_REFERENCE_CONCERN = "date_reference_concern"
BLOCK_MISSING_PAYMENT_EVENT_IDENTITY = "missing_payment_event_identity"
BLOCK_CANDIDATE_INVALID = "candidate_no_longer_valid"
BLOCK_DUPLICATE_ACTIVE_CONFLICT = "duplicate_active_conflict"
BLOCK_PERMISSION_SETUP = "permission_or_setup_issue"
BLOCK_TARGET_AMBIGUOUS = "target_ambiguous"

TARGET_AVAILABLE = "Reconciliation Target Available"
TARGET_AMBIGUOUS = "Target Ambiguous"
TARGET_MISSING = "Payment Voucher Missing"
TARGET_MANUAL_REVIEW = "Manual ERPNext Review Required"

ERPNext_NATIVE_RECONCILIATION_METHOD = (
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.reconcile_vouchers"
)


def _bool(value, default=0):
	if value is None:
		return default
	if isinstance(value, str):
		return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
	return 1 if value else 0


def _active_conflict_counts(match_doc):
	if not has_doctype("RetailEdge Bank Transaction Match"):
		return {"by_bank_transaction": {}, "by_candidate": {}}

	inactive_statuses = list(INACTIVE_MATCH_STATUSES)
	bank_transaction = cstr(match_doc.get("bank_transaction")).strip()
	candidate_type = cstr(match_doc.get("suggested_document_type")).strip()
	candidate_name = cstr(match_doc.get("suggested_document")).strip()
	by_bank_transaction = {}
	by_candidate = {}

	if bank_transaction:
		by_bank_transaction[bank_transaction] = frappe.db.count(
			"RetailEdge Bank Transaction Match",
			filters={
				"bank_transaction": bank_transaction,
				"decision_status": ["not in", inactive_statuses],
			},
		)

	if candidate_type and candidate_name:
		by_candidate[f"{candidate_type}::{candidate_name}"] = frappe.db.count(
			"RetailEdge Bank Transaction Match",
			filters={
				"suggested_document_type": candidate_type,
				"suggested_document": candidate_name,
				"decision_status": ["not in", inactive_statuses],
			},
		)

	return {
		"by_bank_transaction": by_bank_transaction,
		"by_candidate": by_candidate,
	}


def _resolve_invoice_payment_row_reference(match_row, invoice_name):
	details = _safe_load_json(match_row.get("details_json"))
	target_index = cint_or_zero(
		details.get("payment_row_index") or details.get("payment_row_reference") or match_row.get("payment_row_reference")
	)
	for payment_row in get_sales_invoice_payment_rows(invoice_name):
		if not _invoice_payment_row_is_bank_matchable(payment_row):
			continue
		if target_index and cint_or_zero(payment_row.get("payment_row_index")) == target_index:
			return payment_row
	return None


def cint_or_zero(value):
	try:
		return int(value or 0)
	except Exception:
		return 0


def _load_match_for_preflight(match_name):
	match_name = cstr(match_name).strip()
	if not match_name or not has_doctype("RetailEdge Bank Transaction Match"):
		return {}

	row = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		match_name,
		[
			"name",
			"bank_transaction",
			"transaction_date",
			"bank_amount",
			"bank_account",
			"suggested_document_type",
			"suggested_document",
			"sales_invoice",
			"payment_entry",
			"candidate_amount",
			"amount_difference",
			"amount_scenario",
			"match_confidence",
			"match_score",
			"match_reason",
			"decision_status",
			"confirmed_by",
			"confirmed_on",
			"branch",
			"company",
			"party",
			"customer",
			"details_json",
			"modified",
		],
		as_dict=True,
	) or {}
	if not row:
		return {}

	row = frappe._dict(row)
	context = _bulk_hydrate_match_candidate_contexts([row]).get(match_name, {})
	details = _safe_load_json(row.get("details_json"))
	candidate = {
		"document_type": row.get("suggested_document_type"),
		"document_name": row.get("suggested_document"),
		"candidate_category": context.get("candidate_category") or details.get("candidate_category"),
		"posting_date": context.get("candidate_posting_date") or details.get("candidate_posting_date") or row.get("transaction_date"),
		"payment_account": context.get("payment_account") or details.get("payment_account"),
		"account": context.get("payment_account") or details.get("payment_account") or details.get("candidate_canonical_account"),
		"expected_bank_account": details.get("candidate_canonical_account"),
		"branch": context.get("branch") or row.get("branch"),
	}
	bank_transaction = {
		"bank_account": row.get("bank_account"),
		"bank_transaction": row.get("bank_transaction"),
		"transaction_date": row.get("transaction_date"),
		"amount": row.get("bank_amount"),
		"branch": row.get("branch"),
		"company": row.get("company"),
		"direction": "Inflow",
		"is_reconciled": _bool(details.get("is_reconciled"), 0),
	}
	account_payload = _resolve_account_match_payload(bank_transaction, candidate)
	combined = frappe._dict(dict(row))
	combined["candidate_category"] = context.get("candidate_category") or details.get("candidate_category")
	combined["payment_event_source"] = context.get("payment_event_source") or details.get("payment_event_source")
	combined["payment_event_amount"] = flt(
		context.get("payment_event_amount")
		or details.get("payment_row_amount")
		or details.get("payment_entry_paid_amount")
		or row.get("candidate_amount")
	)
	combined["payment_account"] = context.get("payment_account") or details.get("payment_account")
	combined["candidate_posting_date"] = context.get("candidate_posting_date") or details.get("candidate_posting_date")
	combined["account_resolution_status"] = account_payload.get("status")
	combined["resolved_bank_account"] = account_payload.get("bank_canonical_account")
	combined["resolved_payment_account"] = account_payload.get("candidate_canonical_account")
	combined["branch_match"] = details.get("branch_match")
	combined["branch_match_available"] = details.get("branch_match_available")
	combined["party"] = context.get("party") or row.get("party") or row.get("customer")
	combined["branch"] = context.get("branch") or row.get("branch")

	readiness_status, readiness_reason = _readiness_for_match_row(combined)
	combined["reconciliation_readiness_status"] = readiness_status
	combined["exception_reason"] = readiness_reason

	combined.update(get_bank_transaction_reconciliation_context(row.get("bank_transaction")))
	payment_context = get_payment_event_reconciliation_context(
		row.get("suggested_document_type"),
		row.get("suggested_document"),
		match_doc=combined,
	)
	for key, value in payment_context.items():
		if value not in (None, ""):
			combined[key] = value

	conflict_counts = _active_conflict_counts(combined)
	handoff_status, handoff_priority, handoff_reason = classify_reconciliation_handoff(
		combined, conflict_counts=conflict_counts
	)
	combined["handoff_status"] = handoff_status
	combined["handoff_priority"] = handoff_priority
	combined["blocking_reason"] = handoff_reason
	return combined


def resolve_reconciliation_target(match_doc):
	match_doc = frappe._dict(match_doc or {})
	candidate_doctype = cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip()
	candidate_name = cstr(match_doc.get("suggested_document") or match_doc.get("candidate_name")).strip()
	payment_event_source = cstr(match_doc.get("payment_event_source")).strip()

	if not candidate_doctype or not candidate_name:
		return {
			"target_status": TARGET_MANUAL_REVIEW,
			"erpnext_target_doctype": "",
			"erpnext_target_name": "",
			"recommended_action": "Do not reconcile this row from RetailEdge.",
			"blocking_reason": "No valid payment-event target was found.",
			"notes": "RetailEdge could not resolve a native ERPNext voucher target.",
		}

	if candidate_doctype == "Payment Entry":
		docstatus = match_doc.get("candidate_docstatus")
		if docstatus not in (None, 1):
			return {
				"target_status": TARGET_MANUAL_REVIEW,
				"erpnext_target_doctype": "Payment Entry",
				"erpnext_target_name": candidate_name,
				"recommended_action": "Review or submit the Payment Entry before reconciliation.",
				"blocking_reason": "Payment Entry is not submitted.",
				"notes": "ERPNext native reconciliation expects a submitted Payment Entry voucher.",
			}
		return {
			"target_status": TARGET_AVAILABLE,
			"erpnext_target_doctype": "Payment Entry",
			"erpnext_target_name": candidate_name,
			"recommended_action": f"Open ERPNext Bank Reconciliation and reconcile Bank Transaction {match_doc.get('bank_transaction')} against Payment Entry {candidate_name}.",
			"blocking_reason": "",
			"notes": (
				"ERPNext's native bank reconciliation hook supports Payment Entry, and "
				f"`{ERPNext_NATIVE_RECONCILIATION_METHOD}` accepts Payment Entry vouchers."
			),
		}

	if candidate_doctype == "Sales Invoice":
		docstatus = match_doc.get("candidate_docstatus")
		if docstatus not in (None, 1):
			return {
				"target_status": TARGET_MANUAL_REVIEW,
				"erpnext_target_doctype": "Sales Invoice",
				"erpnext_target_name": candidate_name,
				"recommended_action": "Review the Sales Invoice before reconciliation.",
				"blocking_reason": "Sales Invoice is not submitted.",
				"notes": "Native ERPNext reconciliation does not accept cancelled or draft Sales Invoices as safe targets.",
			}
		if payment_event_source not in {"Invoice Payment Row", "POS Payment Row"}:
			return {
				"target_status": TARGET_MANUAL_REVIEW,
				"erpnext_target_doctype": "Sales Invoice",
				"erpnext_target_name": candidate_name,
				"recommended_action": "Do not reconcile this row from RetailEdge.",
				"blocking_reason": "This Sales Invoice match is not tied to a bank-matchable payment row.",
				"notes": "Invoice total-only, outstanding-only, and context-only similarities stay outside the reconciliation bridge.",
			}

		linked_payment_entries = get_payment_entries_for_sales_invoice(candidate_name) or []
		if not linked_payment_entries:
			return {
				"target_status": TARGET_MISSING,
				"erpnext_target_doctype": "Sales Invoice",
				"erpnext_target_name": candidate_name,
				"recommended_action": "Review this invoice manually in ERPNext. A native payment voucher target is missing.",
				"blocking_reason": "Payment voucher missing: no submitted Payment Entry voucher is linked to this Sales Invoice payment event.",
				"notes": (
					"ERPNext natively lists Sales Invoice in bank reconciliation targets, but its native method "
					"clears Sales Invoice payment evidence at the parent invoice level rather than the specific RetailEdge payment row."
				),
			}

		payment_entry_names = ", ".join(cstr(row.get("payment_entry")).strip() for row in linked_payment_entries if cstr(row.get("payment_entry")).strip())
		return {
			"target_status": TARGET_AMBIGUOUS,
			"erpnext_target_doctype": "Sales Invoice",
			"erpnext_target_name": candidate_name,
			"recommended_action": "Review this match manually in ERPNext before any reconciliation.",
			"blocking_reason": "ERPNext's native Sales Invoice reconciliation path is parent-invoice based and is not payment-row-specific.",
			"notes": (
				"Linked Payment Entries: "
				+ (payment_entry_names or "none")
				+ ". RetailEdge matched a specific non-cash invoice/POS payment row, but ERPNext's native Sales Invoice reconciliation updates the whole invoice payment evidence."
			),
		}

	return {
		"target_status": TARGET_MANUAL_REVIEW,
		"erpnext_target_doctype": candidate_doctype,
		"erpnext_target_name": candidate_name,
		"recommended_action": "Review this voucher type manually in ERPNext before reconciliation.",
		"blocking_reason": f"{candidate_doctype} is not a supported RetailEdge reconciliation bridge target yet.",
		"notes": "RetailEdge R6.0 only resolves Payment Entry targets directly. Other voucher types remain manual handoff items.",
	}


def build_reconciliation_preflight(match_doc):
	match_doc = frappe._dict(match_doc or {})
	if not match_doc:
		return {
			"status": PREFLIGHT_EXCEPTION,
			"dry_run": True,
			"match_name": "",
			"recommended_action": "Check the RetailEdge Bank Transaction Match record.",
			"blocking_reason": "RetailEdge Bank Transaction Match was not found.",
			"notes": "Preflight is read-only and could not load the requested match.",
			"native_reconciliation_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
		}

	target = resolve_reconciliation_target(match_doc)
	handoff_status = cstr(match_doc.get("handoff_status")).strip()
	readiness_status = cstr(match_doc.get("reconciliation_readiness_status")).strip()
	blocking_reason = cstr(match_doc.get("blocking_reason") or match_doc.get("exception_reason")).strip()

	if readiness_status == READINESS_ALREADY_RECONCILED or handoff_status == HANDOFF_ALREADY_RECONCILED:
		status = PREFLIGHT_ALREADY_RECONCILED
	elif target.get("target_status") in {TARGET_AMBIGUOUS, TARGET_MISSING}:
		status = PREFLIGHT_TARGET_AMBIGUOUS
	elif handoff_status == HANDOFF_EXCEPTION:
		status = PREFLIGHT_EXCEPTION
	elif handoff_status == HANDOFF_NOT_ELIGIBLE:
		status = PREFLIGHT_NOT_READY
	elif handoff_status == HANDOFF_NEEDS_REVIEW or readiness_status in {"Needs Review", "Not Ready"}:
		status = PREFLIGHT_NEEDS_REVIEW
	elif handoff_status == HANDOFF_READY and target.get("target_status") == TARGET_AVAILABLE:
		status = PREFLIGHT_READY
	else:
		status = PREFLIGHT_NOT_READY

	if status == PREFLIGHT_READY:
		recommended_action = target.get("recommended_action")
		blocking_reason = ""
	elif status == PREFLIGHT_ALREADY_RECONCILED:
		recommended_action = "No reconciliation handoff is needed."
		blocking_reason = blocking_reason or "Bank Transaction already appears reconciled in ERPNext."
	elif status == PREFLIGHT_TARGET_AMBIGUOUS:
		recommended_action = target.get("recommended_action")
		blocking_reason = target.get("blocking_reason") or blocking_reason
	elif status == PREFLIGHT_NEEDS_REVIEW:
		recommended_action = "Review and confirm the RetailEdge match before ERPNext reconciliation."
		blocking_reason = blocking_reason or "This match is not confirmed or still needs review."
	elif status == PREFLIGHT_EXCEPTION:
		recommended_action = "Investigate the exception before attempting ERPNext reconciliation."
		blocking_reason = blocking_reason or target.get("blocking_reason") or "A conflicting or unsafe condition was detected."
	else:
		recommended_action = target.get("recommended_action") or "Do not reconcile this row from RetailEdge."
		blocking_reason = blocking_reason or target.get("blocking_reason") or "This row is not eligible for reconciliation."

	return {
		"status": status,
		"dry_run": True,
		"match_name": match_doc.get("name") or match_doc.get("bank_match_review"),
		"bank_transaction": match_doc.get("bank_transaction"),
		"bank_transaction_date": match_doc.get("bank_transaction_date") or match_doc.get("transaction_date"),
		"bank_account": match_doc.get("bank_account"),
		"bank_amount": flt(match_doc.get("bank_transaction_amount") or match_doc.get("bank_amount")),
		"suggested_document_type": match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype"),
		"suggested_document": match_doc.get("suggested_document") or match_doc.get("candidate_name"),
		"candidate_category": match_doc.get("candidate_category") or match_doc.get("candidate_type"),
		"candidate_doctype": match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype"),
		"candidate_name": match_doc.get("suggested_document") or match_doc.get("candidate_name"),
		"candidate_date": match_doc.get("candidate_date") or match_doc.get("candidate_posting_date"),
		"candidate_account": match_doc.get("candidate_account") or match_doc.get("payment_account"),
		"candidate_amount": flt(match_doc.get("candidate_amount")),
		"payment_event_source": match_doc.get("payment_event_source"),
		"payment_event_amount": flt(match_doc.get("payment_event_amount") or match_doc.get("candidate_amount")),
		"amount_difference": flt(match_doc.get("amount_difference")),
		"canonical_bank_account": match_doc.get("resolved_bank_account"),
		"canonical_payment_account": match_doc.get("resolved_payment_account"),
		"account_resolution_status": match_doc.get("account_resolution_status"),
		"match_confidence": match_doc.get("match_confidence"),
		"match_score": match_doc.get("match_score"),
		"review_status": match_doc.get("review_status") or match_doc.get("decision_status"),
		"readiness_status": match_doc.get("reconciliation_readiness_status"),
		"handoff_status": match_doc.get("handoff_status"),
		"erpnext_target_status": target.get("target_status"),
		"erpnext_target_doctype": target.get("erpnext_target_doctype"),
		"erpnext_target_name": target.get("erpnext_target_name"),
		"recommended_action": recommended_action,
		"blocking_reason": blocking_reason,
		"notes": target.get("notes"),
		"native_reconciliation_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
		"native_execution_supported": False,
	}


def get_reconciliation_preflight(match_name):
	return build_reconciliation_preflight(_load_match_for_preflight(match_name))


def reconcile_confirmed_bank_match(match_name, dry_run=True):
	dry_run = _bool(dry_run, 1)
	preflight = get_reconciliation_preflight(match_name)
	if dry_run:
		return preflight
	result = dict(preflight)
	result["dry_run"] = False
	result["execution_attempted"] = False
	result["execution_deferred"] = True
	result["recommended_action"] = preflight.get("recommended_action") or "Use ERPNext Bank Reconciliation manually."
	result["notes"] = (
		(preflight.get("notes") or "")
		+ " RetailEdge execution is deferred in R6.0 because the native ERPNext method mutates Bank Transaction status and linked voucher clearance fields; only read-only preflight is enabled in this phase."
	).strip()
	return result



def _coerce_json_list(value):
	if value in (None, ""):
		return []
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except Exception:
			return [value]
	if isinstance(value, (list, tuple, set)):
		return [cstr(item).strip() for item in value if cstr(item).strip()]
	return [cstr(value).strip()] if cstr(value).strip() else []


def _payment_event_identity(match_doc, preflight):
	source = cstr(preflight.get("payment_event_source") or match_doc.get("payment_event_source")).strip()
	candidate_doctype = cstr(preflight.get("candidate_doctype") or match_doc.get("suggested_document_type")).strip()
	candidate_name = cstr(preflight.get("candidate_name") or match_doc.get("suggested_document")).strip()
	details = _safe_load_json(match_doc.get("details_json")) if hasattr(match_doc, "get") else {}
	row_reference = cstr(
		match_doc.get("payment_row_reference")
		or match_doc.get("payment_row_index")
		or details.get("payment_row_reference")
		or details.get("payment_row_index")
	).strip()
	if source and row_reference:
		return f"{source}:{row_reference}"
	if source == "Payment Entry" and candidate_doctype == "Payment Entry" and candidate_name:
		return f"Payment Entry:{candidate_name}"
	if source and candidate_name:
		return f"{source}:{candidate_name}"
	if candidate_doctype == "Payment Entry" and candidate_name:
		return f"Payment Entry:{candidate_name}"
	return ""


def _amounts_differ(bank_amount, candidate_amount, amount_difference=None):
	if abs(flt(amount_difference)) > 0.005:
		return True
	if bank_amount not in (None, "") and candidate_amount not in (None, ""):
		return abs(abs(flt(bank_amount)) - abs(flt(candidate_amount))) > 0.005
	return False


def _block_code_for_preflight(preflight, match_doc):
	status = preflight.get("status")
	candidate_doctype = cstr(preflight.get("candidate_doctype") or match_doc.get("suggested_document_type")).strip()
	candidate_name = cstr(preflight.get("candidate_name") or match_doc.get("suggested_document")).strip()
	bank_transaction = cstr(preflight.get("bank_transaction") or match_doc.get("bank_transaction")).strip()
	account_status = cstr(preflight.get("account_resolution_status") or match_doc.get("account_resolution_status")).strip().lower()
	blocking_reason = cstr(preflight.get("blocking_reason") or match_doc.get("blocking_reason") or match_doc.get("exception_reason")).lower()
	decision_status = cstr(match_doc.get("decision_status") or match_doc.get("review_status")).strip()
	payment_identity = _payment_event_identity(match_doc, preflight)
	candidate_docstatus = match_doc.get("candidate_docstatus")

	if status == PREFLIGHT_ALREADY_RECONCILED:
		return BLOCK_ALREADY_HANDLED
	if decision_status and decision_status != "Confirmed":
		return BLOCK_UNCONFIRMED
	if not bank_transaction or match_doc.get("bank_transaction_missing"):
		return BLOCK_MISSING_BANK_TRANSACTION
	if not candidate_doctype or not candidate_name or match_doc.get("candidate_missing") or match_doc.get("candidate_exists") is False:
		return BLOCK_MISSING_SOURCE_DOCUMENT
	if candidate_doctype not in {"Payment Entry", "Sales Invoice"}:
		return BLOCK_UNSUPPORTED_CANDIDATE_TYPE
	if candidate_docstatus not in (None, 1):
		return BLOCK_CANDIDATE_INVALID
	if "mismatch" in account_status or "account" in blocking_reason and "mismatch" in blocking_reason:
		return BLOCK_BANK_ACCOUNT_MISMATCH
	if _amounts_differ(preflight.get("bank_amount"), preflight.get("candidate_amount"), preflight.get("amount_difference")):
		return BLOCK_AMOUNT_MISMATCH
	if status == PREFLIGHT_READY:
		return BLOCK_NONE
	if candidate_doctype == "Sales Invoice" and not payment_identity:
		return BLOCK_MISSING_PAYMENT_EVENT_IDENTITY
	if "duplicate" in blocking_reason or "conflict" in blocking_reason or "active" in blocking_reason:
		return BLOCK_DUPLICATE_ACTIVE_CONFLICT
	if status == PREFLIGHT_TARGET_AMBIGUOUS:
		return BLOCK_TARGET_AMBIGUOUS
	if "date" in blocking_reason or "reference" in blocking_reason:
		return BLOCK_DATE_REFERENCE_CONCERN
	if status == PREFLIGHT_NEEDS_REVIEW:
		return BLOCK_UNCONFIRMED
	if status == PREFLIGHT_EXCEPTION:
		return BLOCK_PERMISSION_SETUP
	return BLOCK_PERMISSION_SETUP


def _readiness_group_for_preflight(preflight, block_code):
	if block_code == BLOCK_NONE:
		return READINESS_GROUP_READY
	if block_code == BLOCK_ALREADY_HANDLED:
		return READINESS_GROUP_ALREADY_HANDLED
	if preflight.get("status") == PREFLIGHT_NEEDS_REVIEW or block_code in {BLOCK_UNCONFIRMED, BLOCK_DATE_REFERENCE_CONCERN}:
		return READINESS_GROUP_NEEDS_REVIEW
	return READINESS_GROUP_BLOCKED


def _readiness_warnings(preflight, match_doc, block_code):
	warnings = []
	if block_code == BLOCK_AMOUNT_MISMATCH:
		warnings.append("Bank amount and candidate amount differ.")
	if block_code == BLOCK_BANK_ACCOUNT_MISMATCH:
		warnings.append("Bank account and candidate payment account do not align.")
	if block_code == BLOCK_TARGET_AMBIGUOUS:
		warnings.append("ERPNext target is ambiguous for automated reconciliation.")
	if cstr(preflight.get("match_confidence")) and cstr(preflight.get("match_confidence")) != "Strong Match":
		warnings.append(f"Match confidence is {preflight.get('match_confidence')}.")
	return warnings


def build_reconciliation_readiness_result(match_doc):
	match_doc = frappe._dict(match_doc or {})
	preflight = build_reconciliation_preflight(match_doc)
	block_code = _block_code_for_preflight(preflight, match_doc)
	group = _readiness_group_for_preflight(preflight, block_code)
	payment_identity = _payment_event_identity(match_doc, preflight)
	block_reason = preflight.get("blocking_reason") or ""
	if group == READINESS_GROUP_READY:
		block_reason = ""
	elif not block_reason:
		block_reason = _default_block_reason(block_code)
	return {
		"review_name": preflight.get("match_name") or match_doc.get("name"),
		"bank_match_review": preflight.get("match_name") or match_doc.get("name"),
		"bank_transaction": preflight.get("bank_transaction"),
		"candidate_doctype": preflight.get("candidate_doctype"),
		"candidate_name": preflight.get("candidate_name"),
		"payment_event_identity": payment_identity,
		"bank_account": preflight.get("bank_account"),
		"bank_amount": preflight.get("bank_amount"),
		"candidate_amount": preflight.get("candidate_amount"),
		"eligibility_status": group,
		"readiness_group": group,
		"block_code": block_code,
		"block_reason": block_reason,
		"dry_run_action_summary": preflight.get("recommended_action"),
		"warnings": _readiness_warnings(preflight, match_doc, block_code),
		"safe_next_step": preflight.get("recommended_action"),
		"dry_run": True,
		"native_execution_supported": False,
		"execution_attempted": False,
		"preflight_status": preflight.get("status"),
		"erpnext_target_status": preflight.get("erpnext_target_status"),
		"erpnext_target_doctype": preflight.get("erpnext_target_doctype"),
		"erpnext_target_name": preflight.get("erpnext_target_name"),
		"operator_message": _operator_message_for_readiness(group, block_reason),
	}



def _default_block_reason(block_code):
	reasons = {
		BLOCK_ALREADY_HANDLED: "Bank Transaction already appears reconciled or handled.",
		BLOCK_UNCONFIRMED: "The Bank Match Review must be confirmed before reconciliation readiness.",
		BLOCK_UNSUPPORTED_CANDIDATE_TYPE: "This candidate type is not supported for RetailEdge reconciliation readiness.",
		BLOCK_MISSING_SOURCE_DOCUMENT: "The selected candidate document is missing or no longer available.",
		BLOCK_MISSING_BANK_TRANSACTION: "The linked Bank Transaction is missing or no longer available.",
		BLOCK_BANK_ACCOUNT_MISMATCH: "Bank account and candidate payment account do not align for safe reconciliation.",
		BLOCK_AMOUNT_MISMATCH: "Bank amount and candidate amount do not align for safe reconciliation.",
		BLOCK_DATE_REFERENCE_CONCERN: "Date or reference concerns require review before reconciliation readiness.",
		BLOCK_MISSING_PAYMENT_EVENT_IDENTITY: "RetailEdge could not identify the matched payment event safely.",
		BLOCK_CANDIDATE_INVALID: "The selected candidate is no longer valid for reconciliation readiness.",
		BLOCK_DUPLICATE_ACTIVE_CONFLICT: "Another active or duplicate match conflicts with this reconciliation candidate.",
		BLOCK_PERMISSION_SETUP: "A permission or setup issue blocks reconciliation readiness.",
		BLOCK_TARGET_AMBIGUOUS: "The ERPNext reconciliation target is ambiguous for this match.",
	}
	return reasons.get(block_code) or "This confirmed review is not ready for reconciliation."


def _operator_message_for_readiness(group, block_reason):
	if group == READINESS_GROUP_READY:
		return "This confirmed Bank Match Review is ready for future controlled reconciliation. No execution was performed."
	if group == READINESS_GROUP_ALREADY_HANDLED:
		return "This item already appears handled or reconciled. No action is required."
	if group == READINESS_GROUP_NEEDS_REVIEW:
		return block_reason or "Review this match before reconciliation readiness can be approved."
	return block_reason or "This confirmed Bank Match Review is blocked from reconciliation readiness."


def _summarize_readiness_results(results):
	groups = {
		READINESS_GROUP_READY: [],
		READINESS_GROUP_BLOCKED: [],
		READINESS_GROUP_ALREADY_HANDLED: [],
		READINESS_GROUP_NEEDS_REVIEW: [],
	}
	for row in results:
		groups.setdefault(row.get("readiness_group") or READINESS_GROUP_BLOCKED, []).append(row)
	return {
		"dry_run": True,
		"execution_attempted": False,
		"total_count": len(results),
		"ready_count": len(groups[READINESS_GROUP_READY]),
		"blocked_count": len(groups[READINESS_GROUP_BLOCKED]),
		"already_handled_count": len(groups[READINESS_GROUP_ALREADY_HANDLED]),
		"needs_review_count": len(groups[READINESS_GROUP_NEEDS_REVIEW]),
		"groups": groups,
		"results": results,
		"message": f"Dry-run checked {len(results)} confirmed Bank Match Review record(s). No reconciliation was executed.",
	}


@frappe.whitelist()
def dry_run_reconciliation_for_match(match_name):
	assert_can_access_bank_transaction_matching()
	return build_reconciliation_readiness_result(_load_match_for_preflight(match_name))


@frappe.whitelist()
def dry_run_reconciliation_for_matches(match_names):
	assert_can_access_bank_transaction_matching()
	names = _coerce_json_list(match_names)
	results = [dry_run_reconciliation_for_match(name) for name in names]
	return _summarize_readiness_results(results)


@frappe.whitelist()
def get_reconciliation_readiness_summary(filters=None, limit=100):
	assert_can_access_bank_transaction_matching()
	filters_payload = {}
	if filters:
		if isinstance(filters, str):
			try:
				filters_payload = json.loads(filters) or {}
			except Exception:
				filters_payload = {}
		elif isinstance(filters, dict):
			filters_payload = filters
	db_filters = {"decision_status": "Confirmed"}
	for fieldname in ("company", "branch", "bank_account"):
		if filters_payload.get(fieldname):
			db_filters[fieldname] = filters_payload.get(fieldname)
	names = frappe.get_all(
		"RetailEdge Bank Transaction Match",
		filters=db_filters,
		pluck="name",
		order_by="confirmed_on desc, modified desc",
		limit_page_length=int(limit or 100),
	)
	return dry_run_reconciliation_for_matches(names)
