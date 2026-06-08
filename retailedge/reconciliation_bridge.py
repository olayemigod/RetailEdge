from __future__ import annotations

import inspect
import json

import frappe
from frappe.utils import cstr, flt, now_datetime

from retailedge.bank_matching_operational_reports import (
	READINESS_ALREADY_RECONCILED,
	_bulk_hydrate_match_candidate_contexts,
	_readiness_for_match_row,
	_safe_load_json,
)
from retailedge.bank_transaction_matching import (
	INACTIVE_MATCH_STATUSES,
	_resolve_account_match_payload,
	_resolve_bank_account_to_ledger_account,
	normalize_bank_transaction,
)
from retailedge.bank_transaction_match_workflow import assert_can_manage_bank_transaction_match
from retailedge.branch_context import has_doctype
from retailedge.invoice_payment_audit import get_payment_entries_for_sales_invoice
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
from retailedge.utils.settings import get_retailedge_settings


PREFLIGHT_READY = "Ready"
PREFLIGHT_NOT_READY = "Not Ready"
PREFLIGHT_ALREADY_RECONCILED = "Already Reconciled"
PREFLIGHT_NEEDS_REVIEW = "Needs Review"
PREFLIGHT_TARGET_AMBIGUOUS = "Target Ambiguous"
PREFLIGHT_EXCEPTION = "Exception"

TARGET_AVAILABLE = "Reconciliation Target Available"
TARGET_AMBIGUOUS = "Target Ambiguous"
TARGET_MISSING = "Payment Voucher Missing"
TARGET_MANUAL_REVIEW = "Manual ERPNext Review Required"

RECONCILIATION_STATUS_NOT_RECONCILED = "Not Reconciled"
RECONCILIATION_STATUS_READY = "Reconciliation Ready"
RECONCILIATION_STATUS_RECONCILED = "Reconciled"
RECONCILIATION_STATUS_FAILED = "Reconciliation Failed"
RECONCILIATION_STATUS_SKIPPED = "Reconciliation Skipped"
RECONCILIATION_INTEGRITY_OK = "Candidate Summary Consistent"
RECONCILIATION_INTEGRITY_MISMATCH = "Candidate Summary Mismatch"

ERPNext_NATIVE_RECONCILIATION_METHOD = (
	"erpnext.accounts.doctype.bank_reconciliation_tool.bank_reconciliation_tool.reconcile_vouchers"
)
PAYMENT_ENTRY_RECONCILIATION_ALLOWED_STATUSES = {"Confirmed", "Auto Confirmed"}
READY_READINESS_STATUSES = {"Ready for Reconciliation"}
ALREADY_RECONCILED_BANK_STATUSES = {"Reconciled", "Settled"}
RECONCILIATION_FAILURE_NEEDS_ATTENTION = "Reconciliation Failed / Needs Attention"


def _bool(value, default=0):
	if value is None:
		return default
	if isinstance(value, str):
		return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
	return 1 if value else 0


def _get_setting_value(settings, fieldname, default=None):
	if settings is None:
		return default
	if isinstance(settings, dict):
		return settings.get(fieldname, default)
	values = getattr(settings, "__dict__", None) or {}
	if fieldname in values:
		return values.get(fieldname)
	return getattr(settings, fieldname, default)


def get_reconciliation_bridge_settings(use_cache=False):
	settings = get_retailedge_settings(use_cache=use_cache)
	return {
		"enable_bank_reconciliation_bridge": _bool(
			_get_setting_value(settings, "enable_bank_reconciliation_bridge", 0), 0
		),
		"allow_payment_entry_reconciliation_execution": _bool(
			_get_setting_value(settings, "allow_payment_entry_reconciliation_execution", 0), 0
		),
		"require_reconciliation_preflight": _bool(
			_get_setting_value(settings, "require_reconciliation_preflight", 1), 1
		),
	}

def resolve_bank_transaction_reconciliation_account(bank_transaction):
	bank_transaction_doc = (
		normalize_bank_transaction(bank_transaction)
		if bank_transaction and not isinstance(bank_transaction, dict)
		else frappe._dict(bank_transaction or {})
	)
	bank_account = cstr(bank_transaction_doc.get("bank_account")).strip()
	ledger_account = cstr(bank_transaction_doc.get("ledger_account")).strip()
	if bank_account:
		mapped_account = cstr(_resolve_bank_account_to_ledger_account(bank_account)).strip()
		if mapped_account:
			return {
				"resolved": True,
				"status": "resolved",
				"bank_account": bank_account,
				"canonical_account": mapped_account,
				"reason": f"Bank Transaction bank account {bank_account} resolves to ledger account {mapped_account}.",
				"resolution_source": "bank_account_mapping",
			}
	if ledger_account:
		return {
			"resolved": True,
			"status": "resolved",
			"bank_account": bank_account,
			"canonical_account": ledger_account,
			"reason": f"Bank Transaction ledger account {ledger_account} is stored directly on the transaction.",
			"resolution_source": "bank_transaction_ledger_account",
		}
	return {
		"resolved": False,
		"status": "unresolved",
		"bank_account": bank_account,
		"canonical_account": "",
		"reason": "Bank Transaction bank account could not be resolved to an executable ERPNext ledger account.",
		"resolution_source": "unresolved",
	}


def get_payment_entry_gl_bank_accounts(payment_entry_name):
	payment_entry_name = cstr(payment_entry_name).strip()
	if not payment_entry_name or not has_doctype("GL Entry") or not has_doctype("Account"):
		return {}
	rows = frappe.db.sql(
		"""
		SELECT
			gle.account AS gl_account,
			SUM(ABS(gle.credit_in_account_currency - gle.debit_in_account_currency)) AS amount
		FROM `tabGL Entry` gle
		LEFT JOIN `tabAccount` ac ON ac.name = gle.account
		WHERE
			gle.voucher_type = 'Payment Entry'
			AND gle.voucher_no = %(payment_entry_name)s
			AND gle.is_cancelled = 0
			AND ac.account_type = 'Bank'
		GROUP BY gle.account
		""",
		{"payment_entry_name": payment_entry_name},
		as_dict=True,
	)
	return {
		cstr(row.get("gl_account")).strip(): flt(row.get("amount"))
		for row in rows
		if cstr(row.get("gl_account")).strip()
	}


def resolve_payment_entry_bank_accounts(payment_entry):
	payment_entry_doc = payment_entry
	if payment_entry and not hasattr(payment_entry, "paid_to") and not isinstance(payment_entry, dict):
		try:
			payment_entry_doc = frappe.get_doc("Payment Entry", payment_entry)
		except Exception:
			payment_entry_doc = frappe._dict({"name": payment_entry})
	name = cstr(getattr(payment_entry_doc, "name", None) or (payment_entry_doc or {}).get("name")).strip()
	direct_accounts = set()
	for fieldname in ("paid_to", "paid_from"):
		value = cstr(getattr(payment_entry_doc, fieldname, None) or (payment_entry_doc or {}).get(fieldname)).strip()
		if value:
			direct_accounts.add(value)
	bank_account_link = cstr(
		getattr(payment_entry_doc, "bank_account", None) or (payment_entry_doc or {}).get("bank_account")
	).strip()
	if bank_account_link:
		mapped_account = cstr(_resolve_bank_account_to_ledger_account(bank_account_link)).strip()
		if mapped_account:
			direct_accounts.add(mapped_account)
	gl_accounts = get_payment_entry_gl_bank_accounts(name)
	all_accounts = set(gl_accounts.keys()) | direct_accounts
	return {
		"resolved": bool(all_accounts),
		"status": "resolved" if all_accounts else "unresolved",
		"payment_entry": name,
		"accounts": sorted(all_accounts),
		"gl_accounts": gl_accounts,
		"direct_accounts": sorted(direct_accounts),
		"reason": (
			f"Payment Entry affects bank ledger account(s): {', '.join(sorted(all_accounts))}."
			if all_accounts
			else "RetailEdge could not prove that the Payment Entry affects a bank ledger account."
		),
	}


def payment_entry_affects_bank_transaction_account(payment_entry, bank_transaction):
	bank_account_payload = resolve_bank_transaction_reconciliation_account(bank_transaction)
	if not bank_account_payload.get("resolved"):
		return {
			"matched": False,
			"status": "bank_transaction_account_unresolved",
			"blocking_reason": "Account Unresolved: Bank Transaction bank account could not be resolved for ERPNext reconciliation.",
			"bank_account_payload": bank_account_payload,
			"payment_entry_payload": {},
		}

	payment_entry_payload = resolve_payment_entry_bank_accounts(payment_entry)
	if not payment_entry_payload.get("resolved"):
		return {
			"matched": False,
			"status": "payment_entry_bank_account_unresolved",
			"blocking_reason": "Payment Entry Bank Account Unresolved: RetailEdge could not prove that the Payment Entry affects a bank ledger account.",
			"bank_account_payload": bank_account_payload,
			"payment_entry_payload": payment_entry_payload,
		}

	target_account = cstr(bank_account_payload.get("canonical_account")).strip()
	if target_account in set(payment_entry_payload.get("accounts") or []):
		return {
			"matched": True,
			"status": "matched",
			"blocking_reason": "",
			"bank_account_payload": bank_account_payload,
			"payment_entry_payload": payment_entry_payload,
		}

	return {
		"matched": False,
		"status": "payment_entry_bank_account_mismatch",
		"blocking_reason": (
			"Payment Entry Bank Account Mismatch: "
			f"Payment Entry does not affect the resolved Bank Transaction ledger account {target_account}."
		),
		"bank_account_payload": bank_account_payload,
		"payment_entry_payload": payment_entry_payload,
	}


def _candidate_summary_payment_entry_name(match_doc):
	match_doc = frappe._dict(match_doc or {})
	payment_entry = cstr(match_doc.get("payment_entry")).strip()
	if payment_entry:
		return payment_entry
	if cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip() == "Payment Entry":
		return cstr(match_doc.get("suggested_document") or match_doc.get("candidate_name")).strip()
	return ""


def validate_reconciliation_candidate_consistency(match_doc):
	match_doc = frappe._dict(match_doc or {})
	reconciliation_status = cstr(match_doc.get("reconciliation_status")).strip()
	target_doctype = cstr(match_doc.get("reconciliation_target_doctype")).strip()
	target_name = cstr(match_doc.get("reconciliation_target")).strip()
	current_candidate_type = cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip()
	current_candidate_name = cstr(match_doc.get("suggested_document") or match_doc.get("candidate_name")).strip()
	current_payment_entry = _candidate_summary_payment_entry_name(match_doc)
	payload = {
		"match_name": cstr(match_doc.get("name") or match_doc.get("bank_match_review")).strip(),
		"bank_transaction": cstr(match_doc.get("bank_transaction")).strip(),
		"suggested_document_type": current_candidate_type,
		"suggested_document": current_candidate_name,
		"payment_entry": current_payment_entry,
		"reconciliation_status": reconciliation_status or RECONCILIATION_STATUS_NOT_RECONCILED,
		"reconciliation_target_doctype": target_doctype,
		"reconciliation_target": target_name,
		"integrity_status": RECONCILIATION_INTEGRITY_OK,
		"mismatch_detected": False,
		"mismatch_reason": "",
		"recommended_action": "No reconciliation integrity issue detected.",
	}
	if not reconciliation_status or reconciliation_status == RECONCILIATION_STATUS_NOT_RECONCILED:
		payload["integrity_status"] = "No Reconciliation Outcome"
		payload["recommended_action"] = "No reconciliation outcome is stored yet."
		return payload
	if not target_doctype or not target_name:
		payload["integrity_status"] = "No Reconciliation Target Recorded"
		payload["recommended_action"] = "Review the reconciliation outcome details before retrying."
		return payload
	if target_doctype == "Payment Entry":
		if current_candidate_type != "Payment Entry":
			payload.update({
				"integrity_status": RECONCILIATION_INTEGRITY_MISMATCH,
				"mismatch_detected": True,
				"mismatch_reason": f"Current candidate type {current_candidate_type or 'Unknown'} does not match reconciliation target Payment Entry {target_name}.",
				"recommended_action": "Reset the failed reconciliation outcome and review or recreate the RetailEdge match before retrying.",
			})
			return payload
		comparison_names = {name for name in {current_payment_entry, current_candidate_name} if name}
		if target_name not in comparison_names:
			payload.update({
				"integrity_status": RECONCILIATION_INTEGRITY_MISMATCH,
				"mismatch_detected": True,
				"mismatch_reason": (
					"Current Payment Entry candidate "
					+ (current_payment_entry or current_candidate_name or "Unknown")
					+ f" does not match {reconciliation_status.lower()} target {target_name}."
				),
				"recommended_action": "Reset the failed reconciliation outcome and review or recreate the RetailEdge match before retrying.",
			})
			return payload
	return payload


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
			"reconciliation_status",
			"reconciled_on",
			"reconciled_by",
			"reconciliation_method",
			"reconciliation_target_doctype",
			"reconciliation_target",
			"reconciliation_result_message",
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

		payment_entry_names = ", ".join(
			cstr(row.get("payment_entry")).strip()
			for row in linked_payment_entries
			if cstr(row.get("payment_entry")).strip()
		)
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
		"notes": "RetailEdge only resolves Payment Entry targets directly. Other voucher types remain manual handoff items.",
	}


def build_reconciliation_preflight(match_doc, execution_intent=False):
	match_doc = frappe._dict(match_doc or {})
	integrity = validate_reconciliation_candidate_consistency(match_doc) if match_doc else {}
	if not match_doc:
		return {
			"status": PREFLIGHT_EXCEPTION,
			"dry_run": True,
			"execution_status": "Dry Run",
			"execution_attempted": False,
			"match_name": "",
			"recommended_action": "Check the RetailEdge Bank Transaction Match record.",
			"blocking_reason": "RetailEdge Bank Transaction Match was not found.",
			"notes": "Preflight is read-only and could not load the requested match.",
			"native_reconciliation_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
			"native_execution_supported": False,
		}

	target = resolve_reconciliation_target(match_doc)
	execution_intent = _bool(execution_intent, 0)
	handoff_status = cstr(match_doc.get("handoff_status")).strip()
	readiness_status = cstr(match_doc.get("reconciliation_readiness_status")).strip()
	blocking_reason = cstr(match_doc.get("blocking_reason") or match_doc.get("exception_reason")).strip()
	reconciliation_status = cstr(match_doc.get("reconciliation_status")).strip()
	bank_account_validation = {}
	integrity_mismatch = bool((integrity or {}).get("mismatch_detected"))
	integrity_reason = cstr((integrity or {}).get("mismatch_reason")).strip()
	integrity_status = cstr((integrity or {}).get("integrity_status")).strip()

	if integrity_mismatch:
		status = PREFLIGHT_EXCEPTION
	elif readiness_status == READINESS_ALREADY_RECONCILED or handoff_status == HANDOFF_ALREADY_RECONCILED:
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

	if cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip() == "Payment Entry":
		bank_account_validation = payment_entry_affects_bank_transaction_account(
			{
				"name": match_doc.get("suggested_document") or match_doc.get("candidate_name"),
				"paid_to": match_doc.get("candidate_account") or match_doc.get("payment_account") or match_doc.get("resolved_payment_account"),
				"paid_from": match_doc.get("candidate_account") or match_doc.get("payment_account") or match_doc.get("resolved_payment_account"),
				"bank_account": match_doc.get("candidate_bank_account"),
			},
			{
				"bank_transaction": match_doc.get("bank_transaction"),
				"bank_account": match_doc.get("bank_account"),
				"ledger_account": match_doc.get("resolved_bank_account"),
			},
		)
		if status == PREFLIGHT_READY and not bank_account_validation.get("matched"):
			status = PREFLIGHT_NOT_READY
			blocking_reason = bank_account_validation.get("blocking_reason")
			target["recommended_action"] = "Review the Bank Transaction and Payment Entry bank-account mapping before reconciliation."

	if execution_intent and cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip() == "Payment Entry":
		settings = get_reconciliation_bridge_settings(use_cache=False)
		if not settings.get("enable_bank_reconciliation_bridge"):
			status = PREFLIGHT_NOT_READY
			blocking_reason = "Reconciliation execution is disabled in RetailEdge Settings."
		elif not settings.get("allow_payment_entry_reconciliation_execution"):
			status = PREFLIGHT_NOT_READY
			blocking_reason = "Payment Entry reconciliation execution is disabled in RetailEdge Settings."

	if integrity_mismatch:
		recommended_action = "Repair or reset the failed reconciliation exception before retrying."
		blocking_reason = integrity_reason or "Reconciliation target and current candidate summary do not match."
		handoff_status = f"{HANDOFF_EXCEPTION} / {RECONCILIATION_INTEGRITY_MISMATCH}"
		readiness_status = "Not Ready"
	elif status == PREFLIGHT_READY:
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

	native_execution_supported = (
		cstr(match_doc.get("suggested_document_type") or match_doc.get("candidate_doctype")).strip() == "Payment Entry"
		and target.get("target_status") == TARGET_AVAILABLE
	)
	return {
		"status": status,
		"dry_run": True,
		"execution_status": "Dry Run",
		"execution_attempted": False,
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
		"readiness_status": readiness_status or match_doc.get("reconciliation_readiness_status"),
		"handoff_status": handoff_status or match_doc.get("handoff_status"),
		"erpnext_target_status": target.get("target_status"),
		"erpnext_target_doctype": target.get("erpnext_target_doctype"),
		"erpnext_target_name": target.get("erpnext_target_name"),
		"recommended_action": recommended_action,
		"blocking_reason": blocking_reason,
		"notes": target.get("notes"),
		"execution_intent": bool(execution_intent),
		"native_reconciliation_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
		"native_execution_supported": native_execution_supported,
		"reconciliation_status": match_doc.get("reconciliation_status") or RECONCILIATION_STATUS_NOT_RECONCILED,
		"reconciled_on": match_doc.get("reconciled_on"),
		"reconciled_by": match_doc.get("reconciled_by"),
		"reconciliation_target_doctype": match_doc.get("reconciliation_target_doctype"),
		"reconciliation_target": match_doc.get("reconciliation_target"),
		"reconciliation_result_message": match_doc.get("reconciliation_result_message"),
		"preflight_bank_account_validation_status": bank_account_validation.get("status") or "",
		"preflight_bank_account_validation_reason": bank_account_validation.get("blocking_reason") or "",
		"preflight_resolved_bank_account": (bank_account_validation.get("bank_account_payload") or {}).get("canonical_account"),
		"preflight_payment_entry_bank_accounts": (bank_account_validation.get("payment_entry_payload") or {}).get("accounts") or [],
		"needs_attention": reconciliation_status == RECONCILIATION_STATUS_FAILED or integrity_mismatch,
		"reconciliation_integrity_status": integrity_status,
		"mismatch_detected": integrity_mismatch,
		"mismatch_reason": integrity_reason,
	}


def get_reconciliation_preflight(match_name, execution_intent=False):
	return build_reconciliation_preflight(
		_load_match_for_preflight(match_name),
		execution_intent=execution_intent,
	)


def _blocked_execution_result(preflight, reason, recommended_action=None, execution_status="Blocked"):
	payload = dict(preflight or {})
	payload["dry_run"] = False
	payload["execution_attempted"] = False
	payload["execution_status"] = execution_status
	payload["blocking_reason"] = reason
	payload["recommended_action"] = recommended_action or payload.get("recommended_action") or "Use ERPNext Bank Reconciliation manually."
	return payload


def _get_native_reconcile_vouchers_callable():
	native_fn = frappe.get_attr(ERPNext_NATIVE_RECONCILIATION_METHOD)
	params = list(inspect.signature(native_fn).parameters.values())
	if len(params) < 2:
		raise RuntimeError(
			f"ERPNext native reconciliation signature is unsupported for {ERPNext_NATIVE_RECONCILIATION_METHOD}."
		)
	return native_fn


def _payment_entry_already_linked_to_other_bank_transaction(payment_entry_name, bank_transaction_name):
	if not payment_entry_name or not has_doctype("Bank Transaction Payments"):
		return []
	rows = frappe.get_all(
		"Bank Transaction Payments",
		filters={"payment_document": "Payment Entry", "payment_entry": payment_entry_name},
		fields=["parent"],
		limit_page_length=0,
	)
	parents = [cstr(row.get("parent")).strip() for row in rows if cstr(row.get("parent")).strip()]
	return [parent for parent in parents if parent and parent != cstr(bank_transaction_name).strip()]


def _bank_transaction_snapshot(transaction_doc):
	if not transaction_doc:
		return {}
	return {
		"name": getattr(transaction_doc, "name", None),
		"status": getattr(transaction_doc, "status", None),
		"allocated_amount": flt(getattr(transaction_doc, "allocated_amount", 0)),
		"unallocated_amount": flt(getattr(transaction_doc, "unallocated_amount", 0)),
	}


def _set_match_reconciliation_result(doc, status, message, target_doctype, target_name, method, user=None):
	user = user or frappe.session.user
	doc.reconciliation_status = status
	doc.reconciliation_result_message = message
	doc.reconciliation_method = method
	doc.reconciliation_target_doctype = target_doctype
	doc.reconciliation_target = target_name
	if status == RECONCILIATION_STATUS_RECONCILED:
		doc.reconciled_by = user
		doc.reconciled_on = now_datetime()
	else:
		doc.reconciled_by = None
		doc.reconciled_on = None


def _save_match_with_reconciliation_log(doc, action, remarks, details):
	action_on = now_datetime()
	frappe.db.set_value(
		"RetailEdge Bank Transaction Match",
		doc.name,
		{
			"reconciliation_status": doc.reconciliation_status,
			"reconciled_by": doc.reconciled_by,
			"reconciled_on": doc.reconciled_on,
			"reconciliation_method": doc.reconciliation_method,
			"reconciliation_target_doctype": doc.reconciliation_target_doctype,
			"reconciliation_target": doc.reconciliation_target,
			"reconciliation_result_message": doc.reconciliation_result_message,
			"last_action": action,
			"last_action_by": frappe.session.user,
			"last_action_on": action_on,
		},
		update_modified=True,
	)
	log_row = frappe.get_doc(
		{
			"doctype": "RetailEdge Bank Transaction Match Action Log",
			"parenttype": "RetailEdge Bank Transaction Match",
			"parentfield": "action_logs",
			"parent": doc.name,
			"action": action,
			"action_by": frappe.session.user,
			"action_on": action_on,
			"old_status": doc.decision_status,
			"new_status": doc.decision_status,
			"remarks": remarks,
			"details_json": json.dumps(details or {}, default=str, sort_keys=True, indent=2),
		}
	)
	log_row.insert(ignore_permissions=True)
	doc.last_action = action
	doc.last_action_by = frappe.session.user
	doc.last_action_on = action_on


def _execute_payment_entry_reconciliation(match_doc, preflight):
	settings = get_reconciliation_bridge_settings(use_cache=False)
	if not settings.get("enable_bank_reconciliation_bridge"):
		return _blocked_execution_result(
			preflight,
			"Reconciliation execution is disabled in RetailEdge Settings.",
		)
	if not settings.get("allow_payment_entry_reconciliation_execution"):
		return _blocked_execution_result(
			preflight,
			"Payment Entry reconciliation execution is disabled in RetailEdge Settings.",
		)
	if settings.get("require_reconciliation_preflight") and preflight.get("status") != PREFLIGHT_READY:
		return _blocked_execution_result(
			preflight,
			cstr(preflight.get("blocking_reason")).strip() or "Preflight is not Ready.",
			recommended_action=preflight.get("recommended_action"),
		)
	if cstr(preflight.get("candidate_doctype")).strip() != "Payment Entry" or cstr(preflight.get("erpnext_target_doctype")).strip() != "Payment Entry":
		return _blocked_execution_result(
			preflight,
			"Only Payment Entry matches can be reconciled in R6.1.",
		)
	if cstr(match_doc.decision_status).strip() not in PAYMENT_ENTRY_RECONCILIATION_ALLOWED_STATUSES:
		return _blocked_execution_result(
			preflight,
			"RetailEdge match is not confirmed.",
		)
	if cstr(getattr(match_doc, "reconciliation_status", "")).strip() == RECONCILIATION_STATUS_RECONCILED:
		return _blocked_execution_result(
			preflight,
			"RetailEdge match is already reconciled.",
			execution_status="Skipped",
		)

	bank_transaction_name = cstr(preflight.get("bank_transaction")).strip()
	payment_entry_name = cstr(preflight.get("erpnext_target_name")).strip()
	bank_transaction_doc = frappe.get_doc("Bank Transaction", bank_transaction_name)
	if cstr(getattr(bank_transaction_doc, "status", "")).strip() == "Cancelled":
		return _blocked_execution_result(preflight, "Bank Transaction is cancelled.")
	if cstr(getattr(bank_transaction_doc, "status", "")).strip() in ALREADY_RECONCILED_BANK_STATUSES:
		return _blocked_execution_result(
			preflight,
			"Bank Transaction is already reconciled.",
			execution_status="Skipped",
		)

	payment_entry_doc = frappe.get_doc("Payment Entry", payment_entry_name)
	if getattr(payment_entry_doc, "docstatus", 0) != 1:
		return _blocked_execution_result(preflight, "Payment Entry is not submitted.")

	other_bank_transactions = _payment_entry_already_linked_to_other_bank_transaction(payment_entry_name, bank_transaction_name)
	if other_bank_transactions:
		return _blocked_execution_result(
			preflight,
			"Payment Entry already appears reconciled to another Bank Transaction.",
		)

	conflict_counts = _active_conflict_counts(
		{
			"bank_transaction": bank_transaction_name,
			"suggested_document_type": "Payment Entry",
			"suggested_document": payment_entry_name,
		}
	)
	if conflict_counts.get("by_bank_transaction", {}).get(bank_transaction_name, 0) > 1 or conflict_counts.get("by_candidate", {}).get(f"Payment Entry::{payment_entry_name}", 0) > 1:
		return _blocked_execution_result(
			preflight,
			"Another active or confirmed match already exists.",
		)

	try:
		native_reconcile = _get_native_reconcile_vouchers_callable()
	except Exception as exc:
		return _blocked_execution_result(
			preflight,
			f"ERPNext native reconciliation method is unavailable or unsupported: {cstr(exc)}",
		)

	before = _bank_transaction_snapshot(bank_transaction_doc)
	vouchers_payload = json.dumps(
		[{"payment_doctype": "Payment Entry", "payment_name": payment_entry_name}],
		sort_keys=True,
	)
	try:
		updated_transaction = native_reconcile(bank_transaction_name, vouchers_payload)
	except Exception as exc:
		message = f"ERPNext native reconciliation failed: {cstr(exc)}"
		_set_match_reconciliation_result(
			match_doc,
			RECONCILIATION_STATUS_FAILED,
			message,
			"Payment Entry",
			payment_entry_name,
			ERPNext_NATIVE_RECONCILIATION_METHOD,
		)
		_save_match_with_reconciliation_log(
			match_doc,
			action="Reconciliation Failed",
			remarks=message,
			details={
				"preflight": preflight,
				"before_bank_transaction": before,
				"native_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
			},
		)
		return {
			**dict(preflight),
			"dry_run": False,
			"execution_attempted": True,
			"execution_status": "Failed",
			"blocking_reason": message,
			"recommended_action": "Review the ERPNext bank reconciliation error before retrying.",
			"reconciliation_status": RECONCILIATION_STATUS_FAILED,
		}

	after = _bank_transaction_snapshot(updated_transaction)
	if cstr(after.get("status")).strip() not in ALREADY_RECONCILED_BANK_STATUSES:
		message = (
			"ERPNext native reconciliation did not produce a reconciled Bank Transaction status. "
			f"Current status: {after.get('status') or 'Unknown'}."
		)
		_set_match_reconciliation_result(
			match_doc,
			RECONCILIATION_STATUS_FAILED,
			message,
			"Payment Entry",
			payment_entry_name,
			ERPNext_NATIVE_RECONCILIATION_METHOD,
		)
		_save_match_with_reconciliation_log(
			match_doc,
			action="Reconciliation Failed",
			remarks=message,
			details={
				"preflight": preflight,
				"before_bank_transaction": before,
				"after_bank_transaction": after,
				"native_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
			},
		)
		return {
			**dict(preflight),
			"dry_run": False,
			"execution_attempted": True,
			"execution_status": "Failed",
			"blocking_reason": message,
			"recommended_action": "Review the ERPNext bank reconciliation result before retrying.",
			"reconciliation_status": RECONCILIATION_STATUS_FAILED,
		}

	message = (
		f"ERPNext reconciled Bank Transaction {bank_transaction_name} against Payment Entry {payment_entry_name} using the native bank reconciliation method."
	)
	_set_match_reconciliation_result(
		match_doc,
		RECONCILIATION_STATUS_RECONCILED,
		message,
		"Payment Entry",
		payment_entry_name,
		ERPNext_NATIVE_RECONCILIATION_METHOD,
	)
	_save_match_with_reconciliation_log(
		match_doc,
		action="Reconciled via ERPNext",
		remarks=message,
		details={
			"preflight": preflight,
			"before_bank_transaction": before,
			"after_bank_transaction": after,
			"native_method": ERPNext_NATIVE_RECONCILIATION_METHOD,
		},
	)
	return {
		**dict(preflight),
		"status": PREFLIGHT_READY,
		"dry_run": False,
		"execution_attempted": True,
		"execution_status": "Succeeded",
		"blocking_reason": "",
		"recommended_action": "ERPNext native reconciliation completed successfully.",
		"message": message,
		"reconciliation_status": RECONCILIATION_STATUS_RECONCILED,
		"reconciled_by": frappe.session.user,
		"reconciled_on": cstr(match_doc.reconciled_on),
		"reconciliation_target_doctype": "Payment Entry",
		"reconciliation_target": payment_entry_name,
	}


def reconcile_confirmed_bank_match(match_name, dry_run=True):
	dry_run = _bool(dry_run, 1)
	preflight = get_reconciliation_preflight(match_name, execution_intent=not dry_run)
	if dry_run:
		return preflight

	assert_can_manage_bank_transaction_match()
	match_name = cstr(match_name).strip()
	if not match_name or not has_doctype("RetailEdge Bank Transaction Match"):
		return _blocked_execution_result(
			preflight,
			"RetailEdge Bank Transaction Match was not found.",
		)

	fresh_preflight = get_reconciliation_preflight(match_name, execution_intent=True)
	match_doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	return _execute_payment_entry_reconciliation(match_doc, fresh_preflight)


def validate_reconciliation_match_integrity(match_name):
	return validate_reconciliation_candidate_consistency(_load_match_for_preflight(match_name))


def reset_failed_reconciliation_status(match_name):
	assert_can_manage_bank_transaction_match()
	match_name = cstr(match_name).strip()
	if not match_name or not has_doctype("RetailEdge Bank Transaction Match"):
		frappe.throw("RetailEdge Bank Transaction Match was not found.")
	doc = frappe.get_doc("RetailEdge Bank Transaction Match", match_name)
	candidate_summary_before = {
		"suggested_document_type": cstr(getattr(doc, "suggested_document_type", "")).strip(),
		"suggested_document": cstr(getattr(doc, "suggested_document", "")).strip(),
		"payment_entry": cstr(getattr(doc, "payment_entry", "")).strip(),
		"candidate_type": cstr(getattr(doc, "candidate_type", "")).strip(),
		"candidate_amount": flt(getattr(doc, "candidate_amount", 0)),
		"candidate_posting_date": getattr(doc, "candidate_posting_date", None),
		"payment_event_source": cstr(getattr(doc, "payment_event_source", "")).strip(),
		"payment_account": cstr(getattr(doc, "payment_account", "")).strip(),
		"resolved_payment_account": cstr(getattr(doc, "resolved_payment_account", "")).strip(),
		"match_confidence": cstr(getattr(doc, "match_confidence", "")).strip(),
		"match_score": flt(getattr(doc, "match_score", 0)),
		"review_status": cstr(getattr(doc, "review_status", getattr(doc, "decision_status", ""))).strip(),
		"match_status": cstr(getattr(doc, "match_status", "")).strip(),
	}
	before = {
		"reconciliation_status": cstr(getattr(doc, "reconciliation_status", "")).strip() or RECONCILIATION_STATUS_NOT_RECONCILED,
		"reconciled_by": getattr(doc, "reconciled_by", None),
		"reconciled_on": getattr(doc, "reconciled_on", None),
		"reconciliation_method": getattr(doc, "reconciliation_method", None),
		"reconciliation_target_doctype": getattr(doc, "reconciliation_target_doctype", None),
		"reconciliation_target": getattr(doc, "reconciliation_target", None),
		"reconciliation_result_message": getattr(doc, "reconciliation_result_message", None),
	}
	if cstr(getattr(doc, "reconciliation_status", "")).strip() != RECONCILIATION_STATUS_FAILED:
		return {
			"name": doc.name,
			"reconciliation_status": cstr(getattr(doc, "reconciliation_status", "")).strip()
			or RECONCILIATION_STATUS_NOT_RECONCILED,
			"message": "No failed reconciliation state was present to reset.",
			"before": before,
			"after": before,
			"candidate_summary": candidate_summary_before,
		}
	doc.reconciliation_status = RECONCILIATION_STATUS_NOT_RECONCILED
	doc.reconciled_by = None
	doc.reconciled_on = None
	doc.reconciliation_method = None
	doc.reconciliation_target_doctype = None
	doc.reconciliation_target = None
	doc.reconciliation_result_message = None
	_save_match_with_reconciliation_log(
		doc,
		action="Reconciliation Reset",
		remarks="Cleared failed reconciliation outcome fields only.",
		details={"reset_reason": "Reviewer reset after failed reconciliation attempt.", "before": before},
	)
	after = {
		"reconciliation_status": RECONCILIATION_STATUS_NOT_RECONCILED,
		"reconciled_by": None,
		"reconciled_on": None,
		"reconciliation_method": None,
		"reconciliation_target_doctype": None,
		"reconciliation_target": None,
		"reconciliation_result_message": None,
	}
	return {
		"name": doc.name,
		"reconciliation_status": RECONCILIATION_STATUS_NOT_RECONCILED,
		"message": "Failed reconciliation outcome fields were cleared.",
		"before": before,
		"after": after,
		"candidate_summary_before": candidate_summary_before,
		"candidate_summary_after": candidate_summary_before,
	}
