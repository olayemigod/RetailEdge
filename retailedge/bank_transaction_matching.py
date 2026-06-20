from __future__ import annotations

from collections import defaultdict
import time

import frappe
from frappe.utils import cint, cstr, flt, get_first_day, getdate, nowdate

from retailedge.bank_transaction_bridge import (
	is_reliable_statement_reference,
	normalize_statement_reference,
	normalize_statement_text,
)
from retailedge.branch_context import has_doctype, has_field
from retailedge.branch_profile import get_branch_profile_defaults
from retailedge.cashier_expense import user_has_any_role
from retailedge.invoice_payment_audit import (
	classify_payment_method,
	get_expected_payment_account_for_invoice,
	get_sales_invoice_payment_rows,
)
from retailedge.utils.settings import get_retailedge_settings


BANK_TRANSACTION_MATCHING_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"RetailEdge Manager",
	"RetailEdgeManager",
	"RetailEdge Branch Manager",
	"RetailEdgeBranchManager",
	"RetailEdge Auditor",
	"RetailEdgeAuditor",
}

ACTIVE_CONFIRMED_MATCH_STATUS = "Confirmed"
RELEASED_REVIEW_MATCH_STATUSES = {"Rejected", "Cancelled", "Reopened"}
INACTIVE_MATCH_STATUSES = {"Reopened", "Rejected", "Cancelled"}

AMOUNT_SCENARIO_LABELS = {
	"exact_outstanding_match": "Exact Outstanding Match",
	"exact_outstanding_amount": "Exact Outstanding Match",
	"exact_invoice_amount": "Exact Invoice Amount",
	"partial_payment": "Partial Payment",
	"overpayment": "Overpayment / Advance",
	"overpayment_advance": "Overpayment / Advance",
	"amount_variance": "Amount Variance",
	"multi_invoice_payment": "Multi-Invoice Payment",
	"payment_entry_allocated": "Payment Entry with Invoice Allocation",
	"payment_entry_allocated_amount": "Payment Entry with Invoice Allocation",
	"payment_entry_unallocated": "Payment Entry / Advance",
	"submitted_payment_entry_amount": "Submitted Payment Entry Amount",
	"payment_entry_amount_variance": "Amount Variance",
	"weak_match": "Weak Match",
	"needs_review": "Needs Manual Review",
	"date_mismatch": "Date Mismatch",
	"period_mismatch": "Period Mismatch",
	"account_mismatch": "Account Mismatch",
	"account_unresolved": "Account Unresolved",
	"date_account_mismatch": "Date + Account Mismatch",
	"date_account_unresolved": "Date + Account Unresolved",
	"exception_only": "Exception Only",
	"exact_invoice_payment_row_amount": "Exact Invoice Payment Row Amount",
	"invoice_payment_row_amount_variance": "Invoice Payment Row Amount Variance",
	"invoice_context_only": "Invoice Context Only",
	"weak_invoice_total_similarity": "Weak Invoice Total Similarity",
}

CANDIDATE_CATEGORY_LABELS = {
	"payment_entry_match": "Payment Entry Match",
	"invoice_payment_row_match": "Invoice Payment Row Match",
	"pos_payment_match": "POS Payment Match",
	"invoice_context_only": "Invoice Context Only",
	"weak_invoice_total_similarity": "Weak Invoice Total Similarity",
}

MANUAL_REVIEW_AMOUNT_SCENARIOS = {
	"partial_payment",
	"overpayment",
	"overpayment_advance",
	"amount_variance",
	"multi_invoice_payment",
	"payment_entry_amount_variance",
	"date_mismatch",
	"period_mismatch",
	"account_mismatch",
	"account_unresolved",
	"date_account_mismatch",
	"date_account_unresolved",
	"exception_only",
	"invoice_payment_row_amount_variance",
	"invoice_context_only",
	"weak_invoice_total_similarity",
}

AUTO_MATCH_EXACT_SALES_INVOICE_SCENARIOS = {
	"exact_outstanding_match",
	"exact_outstanding_amount",
}

AUTO_MATCH_EXACT_PAYMENT_ENTRY_SCENARIOS = {
	"submitted_payment_entry_amount",
	"payment_entry_allocated_amount",
}

AUTO_MATCH_ELIGIBLE_CANDIDATE_CATEGORIES = {
	"payment_entry_match",
	"invoice_payment_row_match",
	"pos_payment_match",
}

REVIEW_CREATION_ELIGIBLE_CANDIDATE_CATEGORIES = set(AUTO_MATCH_ELIGIBLE_CANDIDATE_CATEGORIES)


def assert_can_access_bank_transaction_matching(user: str | None = None):
	if user_has_any_role(user=user, roles=BANK_TRANSACTION_MATCHING_ROLES):
		return
	frappe.throw(
		"You do not have permission to access RetailEdge bank transaction matching.",
		frappe.PermissionError,
	)


def normalize_amount_scenario_key(value):
	normalized = cstr(value).strip().lower()
	if not normalized:
		return ""
	normalized = normalized.replace("/", " ").replace("-", " ").replace("_", " ").replace("+", " ")
	return " ".join(normalized.split()).replace(" ", "_")


def get_amount_scenario_label(value):
	key = normalize_amount_scenario_key(value)
	if not key:
		return ""
	return AMOUNT_SCENARIO_LABELS.get(key) or cstr(value).strip().replace("_", " ").title()


def normalize_candidate_category_key(value):
	normalized = cstr(value).strip().lower()
	if not normalized:
		return ""
	normalized = normalized.replace("/", " ").replace("-", " ").replace("_", " ")
	return " ".join(normalized.split()).replace(" ", "_")


def get_candidate_category_label(value):
	key = normalize_candidate_category_key(value)
	if not key:
		return ""
	return CANDIDATE_CATEGORY_LABELS.get(key) or cstr(value).strip().replace("_", " ").title()


def amount_scenario_requires_manual_review(value):
	return normalize_amount_scenario_key(value) in MANUAL_REVIEW_AMOUNT_SCENARIOS


def is_payment_basis_review_candidate(candidate):
	candidate = frappe._dict(candidate or {})
	category_key = normalize_candidate_category_key(candidate.get("candidate_category"))
	if category_key not in REVIEW_CREATION_ELIGIBLE_CANDIDATE_CATEGORIES:
		return False
	if cstr(candidate.get("document_type") or candidate.get("suggested_document_type")).strip() == "Sales Invoice":
		return cint(candidate.get("payment_event_found")) == 1 and cstr(candidate.get("payment_event_source")).strip() != ""
	return True


def get_review_creation_block_reason(candidate):
	candidate = frappe._dict(candidate or {})
	if cstr(candidate.get("document_type") or candidate.get("suggested_document_type")).strip() not in {"Sales Invoice", "Payment Entry"}:
		return "No match candidate found."
	if not cstr(candidate.get("document_name") or candidate.get("suggested_document")).strip():
		return "No match candidate found."
	category_key = normalize_candidate_category_key(candidate.get("candidate_category"))
	if category_key == "invoice_context_only":
		return "Invoice is context only. No payment event was found."
	if category_key == "weak_invoice_total_similarity":
		return "Invoice total matched, but RetailEdge requires Payment Entry or invoice payment row evidence."
	if cstr(candidate.get("document_type") or candidate.get("suggested_document_type")).strip() == "Sales Invoice" and not cint(candidate.get("payment_event_found")):
		return "Sales Invoice is context only; payment event evidence is required for review creation and auto-match."
	return ""


def is_exception_only_candidate(candidate):
	return bool((candidate or {}).get("exception_only")) or normalize_amount_scenario_key((candidate or {}).get("amount_scenario")) in {
		"date_mismatch",
		"period_mismatch",
		"account_mismatch",
		"date_account_mismatch",
		"exception_only",
	}


def _coerce_retailedge_check(value, default=0):
	if value in (None, ""):
		return cint(default)
	return 1 if cint(value) else 0


def _normalize_auto_match_score(value, default=95):
	if value in (None, ""):
		return cint(default)
	raw_value = cstr(value).strip()
	if not raw_value:
		return cint(default)
	if raw_value.endswith("%"):
		raw_value = raw_value[:-1].strip()
	score = flt(raw_value)
	if raw_value not in {"0", "1"} and score > 0 and score <= 1:
		score *= 100
	return max(0, min(100, cint(round(score))))


def get_bank_auto_match_settings(use_cache=True):
	try:
		settings = get_retailedge_settings(use_cache=use_cache)
	except Exception:
		settings = None
	return {
		"enable_bank_auto_match": _coerce_retailedge_check(getattr(settings, "enable_bank_auto_match", 0), default=0),
		"auto_prepare_exact_bank_matches": _coerce_retailedge_check(getattr(settings, "auto_prepare_exact_bank_matches", 0), default=0),
		"auto_confirm_exact_bank_matches": _coerce_retailedge_check(getattr(settings, "auto_confirm_exact_bank_matches", 0), default=0),
		"minimum_auto_match_score": _normalize_auto_match_score(getattr(settings, "minimum_auto_match_score", 95), default=95),
		"require_exact_reference_for_auto_match": _coerce_retailedge_check(getattr(settings, "require_exact_reference_for_auto_match", 1), default=1),
		"require_same_bank_account_for_auto_match": _coerce_retailedge_check(getattr(settings, "require_same_bank_account_for_auto_match", 1), default=1),
		"require_same_branch_for_auto_match": _coerce_retailedge_check(getattr(settings, "require_same_branch_for_auto_match", 1), default=1),
		"allow_auto_match_payment_entry": _coerce_retailedge_check(getattr(settings, "allow_auto_match_payment_entry", 1), default=1),
		"allow_auto_match_sales_invoice": _coerce_retailedge_check(getattr(settings, "allow_auto_match_sales_invoice", 0), default=0),
		"require_no_duplicate_candidate_for_auto_match": _coerce_retailedge_check(getattr(settings, "require_no_duplicate_candidate_for_auto_match", 1), default=1),
		"require_no_active_review_for_auto_match": _coerce_retailedge_check(getattr(settings, "require_no_active_review_for_auto_match", 1), default=1),
	}


def get_bank_transaction_matching_settings(use_cache=True):
	try:
		settings = get_retailedge_settings(use_cache=use_cache)
	except Exception:
		settings = None
	return {
		"date_window_days": cint(getattr(settings, "bank_transaction_match_date_window_days", 3) or 3),
		"exception_date_window_days": cint(getattr(settings, "bank_transaction_match_exception_date_window_days", 400) or 400),
		"amount_tolerance": flt(getattr(settings, "bank_transaction_match_amount_tolerance", 0) or 0),
		"minimum_possible_score": cint(getattr(settings, "bank_transaction_match_minimum_possible_score", 50) or 50),
		"strong_match_score": cint(getattr(settings, "bank_transaction_match_strong_score", 80) or 80),
		**get_bank_auto_match_settings(use_cache=use_cache),
		"include_reconciled_bank_transactions": cint(
			getattr(settings, "bank_transaction_match_include_reconciled", 0) or 0
		),
		"include_cancelled_invoices": cint(
			getattr(settings, "bank_transaction_match_include_cancelled_invoices", 0) or 0
		),
	}


def get_bank_transaction_field_map():
	fieldnames = set()
	try:
		meta = frappe.get_meta("Bank Transaction")
		fieldnames = {field.fieldname for field in meta.fields if getattr(field, "fieldname", None)}
	except Exception:
		fieldnames = set()

	def pick(*candidates):
		for candidate in candidates:
			if candidate in fieldnames:
				return candidate
		return None

	return {
		"bank_account": pick("bank_account"),
		"ledger_account": pick("account", "ledger_account", "bank_ledger_account", "payment_account"),
		"company": pick("company"),
		"transaction_date": pick("date", "transaction_date"),
		"deposit": pick("deposit"),
		"withdrawal": pick("withdrawal"),
		"currency": pick("currency"),
		"description": pick("description"),
		"reference_number": pick("reference_number", "transaction_id"),
		"transaction_id": pick("transaction_id"),
		"party_type": pick("party_type"),
		"party": pick("party"),
		"status": pick("status"),
		"allocated_amount": pick("allocated_amount"),
		"unallocated_amount": pick("unallocated_amount"),
		"retailedge_branch": pick("retailedge_branch"),
	}


def normalize_bank_transaction(bank_transaction_name_or_row):
	field_map = get_bank_transaction_field_map()
	row = (
		frappe.get_doc("Bank Transaction", bank_transaction_name_or_row)
		if isinstance(bank_transaction_name_or_row, str)
		else bank_transaction_name_or_row
	)
	deposit = flt(_get_value(row, field_map.get("deposit")))
	withdrawal = flt(_get_value(row, field_map.get("withdrawal")))
	direction = "Inflow" if deposit > 0 else "Outflow" if withdrawal > 0 else "Unknown"
	amount = deposit if deposit > 0 else withdrawal if withdrawal > 0 else 0.0
	reference = cstr(_get_value(row, field_map.get("reference_number")) or _get_value(row, field_map.get("transaction_id"))).strip()
	description = cstr(_get_value(row, field_map.get("description"))).strip()
	status = cstr(_get_value(row, field_map.get("status"))).strip()
	allocated_amount = flt(_get_value(row, field_map.get("allocated_amount")))
	unallocated_amount = flt(_get_value(row, field_map.get("unallocated_amount")))
	is_reconciled = False
	if status and "reconcil" in status.lower():
		is_reconciled = True
	elif amount > 0 and allocated_amount >= amount and abs(unallocated_amount) <= 0.01:
		is_reconciled = True

	messages = []
	if not field_map.get("transaction_date"):
		messages.append("Bank Transaction date field is not available on this site.")
	if not field_map.get("bank_account"):
		messages.append("Bank Transaction bank account field is not available on this site.")

	return {
		"bank_transaction": cstr(getattr(row, "name", None)).strip() or None,
		"company": _get_value(row, field_map.get("company")),
		"bank_account": _get_value(row, field_map.get("bank_account")),
		"ledger_account": _get_value(row, field_map.get("ledger_account")),
		"transaction_date": cstr(getdate(_get_value(row, field_map.get("transaction_date"))))
		if _get_value(row, field_map.get("transaction_date"))
		else None,
		"amount": amount,
		"direction": direction,
		"reference": reference or None,
		"normalized_reference": normalize_statement_reference(reference=reference) if reference else "",
		"description": description or None,
		"party_type": _get_value(row, field_map.get("party_type")),
		"party": _get_value(row, field_map.get("party")),
		"status": status or None,
		"is_reconciled": is_reconciled,
		"allocated_amount": allocated_amount,
		"unallocated_amount": unallocated_amount,
		"branch": _get_value(row, field_map.get("retailedge_branch")),
		"messages": messages,
	}


def _is_weak_ref_match_similar(c, bank_transaction, settings, all_candidates):
	if c.get("exception_only"):
		return False
		
	bank_amount = flt(bank_transaction.get("amount"))
	c_amount = flt(c.get("candidate_amount"))
	if abs(bank_amount - c_amount) > 0.01:
		return False
		
	c_account_compatible = c.get("account_match") == 1 or c.get("account_resolution_status") in {"match", "match_via_mapping"}
	if not c_account_compatible:
		return False
		
	c_date_diff = c.get("date_difference_days")
	window = settings.get("date_window_days") or 3
	if c_date_diff is None or c_date_diff > window:
		return False
		
	c_party = cstr(c.get("customer") or c.get("party") or "").strip().lower()
	bt_party = cstr(bank_transaction.get("party") or "").strip().lower()
	bt_desc = cstr(bank_transaction.get("description") or "").strip().lower()
	bt_ref = cstr(bank_transaction.get("reference") or "").strip().lower()
	
	if c_party and bt_party:
		if c_party != bt_party:
			return False
	elif c_party:
		c_display = cstr(c.get("customer_display") or c.get("customer") or "").strip().lower()
		c_normalized = normalize_statement_text(c_display or c_party)
		bt_normalized = normalize_statement_text(f"{bt_ref} {bt_desc}")
		if c_normalized and bt_normalized and c_normalized not in bt_normalized:
			has_other_matching_customer = False
			for other in all_candidates or []:
				other_display = cstr(other.get("customer_display") or other.get("customer") or "").strip().lower()
				other_normalized = normalize_statement_text(other_display)
				if other_normalized and other_normalized in bt_normalized:
					has_other_matching_customer = True
					break
			if has_other_matching_customer:
				return False
				
	return True


def _validate_prefetched_candidate_identity(bank_transaction, candidate, all_candidates, settings):
	if not candidate:
		return False
		
	strength = candidate.get("reference_match_strength") or "none"
	is_strong_ref = strength in {"exact", "strong", "contains", "narration_contains_reference"}
	if is_strong_ref:
		return True
		
	# Weak reference rules:
	if candidate.get("exception_only"):
		return False
		
	if not _is_weak_ref_match_similar(candidate, bank_transaction, settings, all_candidates):
		return False
		
	matches_count = 0
	for other in all_candidates or []:
		if _is_weak_ref_match_similar(other, bank_transaction, settings, all_candidates):
			matches_count += 1
	if matches_count > 1:
		return False
		
	return True


def _build_scored_sales_invoices(bank_transaction, invoices, filters, settings, context):
	results = []
	for invoice in invoices:
		if sales_invoice_has_active_confirmed_bank_match(invoice.get("name")) and not cint(filters.get("include_confirmed_matches")):
			continue
		for candidate in _build_sales_invoice_candidates(bank_transaction, invoice, filters, settings, context=context):
			if not candidate:
				continue
			_apply_exception_classification(bank_transaction, candidate, filters, settings)
			if candidate.get("exception_only") and not cint(filters.get("include_exception_candidates")):
				continue
			active_review_match = _active_review_match_for_candidate("Sales Invoice", candidate.get("document_name"))
			if active_review_match:
				status = cstr(active_review_match.get("decision_status")).strip()
				if status == "Confirmed":
					candidate.setdefault("decision_status", "Confirmed")
					candidate.setdefault("action_status", "Already Confirmed")
					candidate.setdefault("reason", "This invoice already has a confirmed bank match.")
				elif _review_queue_status_mode(filters) == "Open Suggestions Only":
					continue
				else:
					candidate.setdefault("decision_status", status)
					candidate.setdefault("action_status", "Existing Active Review")
					candidate.setdefault("match_record", active_review_match.get("name"))
					candidate.setdefault("reason", "Active review record already exists.")
			score_payload = score_bank_transaction_candidate(bank_transaction, candidate)
			candidate.update(score_payload)
			if candidate["score"] >= 30:
				results.append(candidate)
	results.extend(_build_multi_invoice_candidates(bank_transaction, invoices, filters, settings))
	strength_map = {"strong": 4, "exact": 3, "contains": 2, "narration_contains_reference": 1}
	results.sort(
		key=lambda row: (
			-_candidate_category_rank(row.get("candidate_category")),
			-int(row.get("score") or 0),
			-strength_map.get(cstr(row.get("reference_match_strength")).strip().lower(), 0),
			abs(flt(row.get("amount_difference"))),
			cstr(row.get("document_name")),
		)
	)
	return results


def _build_scored_payment_entries(bank_transaction, payment_entries, filters, settings, context):
	references_by_entry = (context or {}).get("payment_entry_references_by_entry") or _get_payment_entry_sales_invoice_references([row.get("name") for row in payment_entries])
	results = []
	for payment_entry in payment_entries:
		if payment_entry_has_active_confirmed_bank_match(payment_entry.get("name")) and not cint(filters.get("include_confirmed_matches")):
			continue
		candidate = _build_payment_entry_candidate(
			bank_transaction,
			payment_entry,
			references_by_entry.get(payment_entry.get("name")) or [],
		)
		_apply_exception_classification(bank_transaction, candidate, filters, settings)
		if candidate.get("exception_only") and not cint(filters.get("include_exception_candidates")):
			continue
		active_review_match = _active_review_match_for_candidate("Payment Entry", candidate.get("document_name"))
		if active_review_match:
			status = cstr(active_review_match.get("decision_status")).strip()
			if status == "Confirmed":
				candidate.setdefault("decision_status", "Confirmed")
				candidate.setdefault("action_status", "Already Confirmed")
				candidate.setdefault("reason", "This payment entry already has a confirmed bank match.")
			elif _review_queue_status_mode(filters) == "Open Suggestions Only":
				continue
			else:
				candidate.setdefault("decision_status", status)
				candidate.setdefault("action_status", "Existing Active Review")
				candidate.setdefault("match_record", active_review_match.get("name"))
				candidate.setdefault("reason", "Active review record already exists.")
		score_payload = score_bank_transaction_candidate(bank_transaction, candidate)
		candidate.update(score_payload)
		if candidate["score"] >= 30:
			results.append(candidate)
	strength_map = {"strong": 4, "exact": 3, "contains": 2, "narration_contains_reference": 1}
	results.sort(
		key=lambda row: (
			-_candidate_category_rank(row.get("candidate_category")),
			-int(row.get("score") or 0),
			-strength_map.get(cstr(row.get("reference_match_strength")).strip().lower(), 0),
			abs(flt(row.get("amount_difference"))),
			cstr(row.get("document_name")),
		)
	)
	return results


def find_sales_invoice_candidates_for_bank_transaction(bank_transaction_name, filters=None, limit=20, context=None):
	filters = frappe._dict(filters or {})
	context = context or getattr(frappe.local, "_retailedge_bank_match_context", None)
	settings = (context or {}).get("settings") or get_bank_transaction_matching_settings()
	bank_transaction = ((context or {}).get("bank_transactions_by_name") or {}).get(bank_transaction_name) or normalize_bank_transaction(bank_transaction_name)
	if bank_transaction.get("direction") != "Inflow":
		return []
	if not has_doctype("Sales Invoice"):
		return []

	# Try prefetch
	prefetched_invoices = ((context or {}).get("sales_invoices_by_bank_transaction") or {}).get(bank_transaction.get("bank_transaction"))
	if prefetched_invoices is not None:
		results = _build_scored_sales_invoices(bank_transaction, prefetched_invoices, filters, settings, context)
		safe_results = [c for c in results if _validate_prefetched_candidate_identity(bank_transaction, c, results, settings)]
		if safe_results:
			return safe_results[: int(limit or 20)]

	# Fallback to direct resolver
	direct_invoices = _get_sales_invoice_rows(bank_transaction, filters, settings, limit=max(int(limit or 20) * 3, 20))
	results = _build_scored_sales_invoices(bank_transaction, direct_invoices, filters, settings, context)
	safe_results = [c for c in results if _validate_prefetched_candidate_identity(bank_transaction, c, results, settings)]
	return safe_results[: int(limit or 20)]


def find_payment_entry_candidates_for_bank_transaction(bank_transaction_name, filters=None, limit=20, context=None):
	filters = frappe._dict(filters or {})
	context = context or getattr(frappe.local, "_retailedge_bank_match_context", None)
	settings = (context or {}).get("settings") or get_bank_transaction_matching_settings()
	bank_transaction = ((context or {}).get("bank_transactions_by_name") or {}).get(bank_transaction_name) or normalize_bank_transaction(bank_transaction_name)
	if not has_doctype("Payment Entry"):
		return []

	# Try prefetch
	prefetched_entries = ((context or {}).get("payment_entries_by_bank_transaction") or {}).get(bank_transaction.get("bank_transaction"))
	if prefetched_entries is not None:
		results = _build_scored_payment_entries(bank_transaction, prefetched_entries, filters, settings, context)
		safe_results = [c for c in results if _validate_prefetched_candidate_identity(bank_transaction, c, results, settings)]
		if safe_results:
			return safe_results[: int(limit or 20)]

	# Fallback to direct resolver
	direct_entries = _get_payment_entry_rows(bank_transaction, filters, settings, limit=max(int(limit or 20) * 3, 20))
	results = _build_scored_payment_entries(bank_transaction, direct_entries, filters, settings, context)
	safe_results = [c for c in results if _validate_prefetched_candidate_identity(bank_transaction, c, results, settings)]
	return safe_results[: int(limit or 20)]


def sales_invoice_has_active_confirmed_bank_match(sales_invoice):
	return candidate_document_has_active_confirmed_bank_match("Sales Invoice", sales_invoice)


def payment_entry_has_active_confirmed_bank_match(payment_entry):
	return candidate_document_has_active_confirmed_bank_match("Payment Entry", payment_entry)


def candidate_document_has_active_confirmed_bank_match(document_type, document_name):
	document_name = cstr(document_name).strip()
	document_type = cstr(document_type).strip()
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	confirmed_map = (context or {}).get("confirmed_review_by_candidate")
	if confirmed_map is not None and (document_type, document_name) in confirmed_map:
		return True
	if not document_name or not has_doctype("RetailEdge Bank Transaction Match"):
		return False
	if document_type == "Sales Invoice":
		filters = {"sales_invoice": document_name, "decision_status": ACTIVE_CONFIRMED_MATCH_STATUS}
	elif document_type == "Payment Entry":
		filters = {"payment_entry": document_name, "decision_status": ACTIVE_CONFIRMED_MATCH_STATUS}
	else:
		return False
	return bool(frappe.db.exists("RetailEdge Bank Transaction Match", filters))


def get_auto_match_status_for_row(row, settings=None):
	row = frappe._dict(row or {})
	settings = settings or get_bank_transaction_matching_settings()
	last_action = cstr(row.get("last_action")).strip()
	decision_status = cstr(row.get("decision_status")).strip()
	action_status = cstr(row.get("action_status")).strip()
	match_record = cstr(row.get("match_record")).strip()
	suggested_document_type = cstr(row.get("suggested_document_type")).strip()
	amount_scenario_key = normalize_amount_scenario_key(row.get("amount_scenario"))
	candidate_category_key = normalize_candidate_category_key(row.get("candidate_category"))
	payment_entry_context = [
		part.strip()
		for part in cstr(row.get("payment_entry_invoice_context")).split(",")
		if part.strip()
	]
	match_score = _normalize_auto_match_score(
		row.get("match_score") if row.get("match_score") not in (None, "") else row.get("score"),
		default=0,
	)
	minimum_auto_match_score = _normalize_auto_match_score(
		settings.get("minimum_auto_match_score"),
		default=95,
	)

	def blocked(reason, category="blocked"):
		return {
			"status": "Blocked from Auto-Match",
			"reason": reason,
			"eligible_prepare": False,
			"eligible_confirm": False,
			"category": category,
		}

	def manual(reason, category="manual_review"):
		return {
			"status": "Needs Manual Review",
			"reason": reason,
			"eligible_prepare": False,
			"eligible_confirm": False,
			"category": category,
		}

	if last_action == "Auto Confirmed":
		return {
			"status": "Auto Confirmed",
			"reason": cstr(row.get("decision_note")).strip()
			or "RetailEdge auto-confirmed this strict exact Bank Match Review record only. It did not reconcile the Bank Transaction or create accounting entries.",
			"eligible_prepare": False,
			"eligible_confirm": False,
			"category": "auto_confirmed",
		}
	if last_action == "Auto Prepared":
		return {
			"status": "Auto Prepared",
			"reason": cstr(row.get("decision_note")).strip()
			or "RetailEdge auto-prepared this strict exact Bank Match Review record for review only.",
			"eligible_prepare": False,
			"eligible_confirm": False,
			"category": "auto_prepared",
		}
	if decision_status == "Confirmed" or action_status == "Already Confirmed":
		return blocked("Candidate already confirmed.", category="already_confirmed")
	if action_status in {"Already Reconciled", "Already Bank Verified"}:
		return blocked(f"{action_status} rows cannot be auto-matched.", category="blocked")
	if not settings.get("enable_bank_auto_match"):
		return blocked("RetailEdge auto-match is disabled in Settings.")
	if not (settings.get("auto_prepare_exact_bank_matches") or settings.get("auto_confirm_exact_bank_matches")):
		return blocked("RetailEdge auto-match actions are disabled in Settings.")
	if not row.get("bank_transaction"):
		return blocked("Missing Bank Transaction.", category="unsafe")
	if not suggested_document_type or not row.get("suggested_document"):
		return blocked("No match candidate found.", category="unsafe")
	if action_status == "Duplicate Candidate" or cint(row.get("duplicate_candidate_skipped")):
		return manual("Duplicate candidate in current view requires manual review.", category="duplicate_candidate")
	if action_status == "Exception Only" or cint(row.get("exception_only")):
		return manual("Date or bank account exception requires manual review.", category="exception_only")
	if amount_scenario_requires_manual_review(row.get("amount_scenario")):
		return manual(f"{get_amount_scenario_label(row.get('amount_scenario'))} requires manual review.", category="manual_review")
	if candidate_category_key not in AUTO_MATCH_ELIGIBLE_CANDIDATE_CATEGORIES:
		if candidate_category_key == "weak_invoice_total_similarity":
			return manual(
				"Paid invoice total similarity only - requires Payment Entry or invoice payment row evidence.",
				category="manual_review",
			)
		if candidate_category_key == "invoice_context_only":
			return manual(
				"Sales Invoice is context only; payment event evidence is required for auto-match.",
				category="manual_review",
			)
		return manual(
			f"{get_candidate_category_label(row.get('candidate_category')) or 'This candidate'} requires payment-event evidence before auto-match.",
			category="manual_review",
		)
	if row.get("match_confidence") != "Strong Match":
		return manual("Only strong exact matches are eligible for RetailEdge auto-match.", category="manual_review")
	if match_score < minimum_auto_match_score:
		return blocked(
			f"Score below auto-match threshold. Match Score: {match_score}. Required Minimum: {minimum_auto_match_score}.",
			category="score_below_threshold",
		)
	if abs(flt(row.get("amount_difference"))) > 0.01:
		return manual("Amount variance requires manual review.", category="manual_review")
	if suggested_document_type == "Sales Invoice":
		if not settings.get("allow_auto_match_sales_invoice"):
			return blocked("Sales Invoice auto-match is disabled in Settings.")
		if candidate_category_key not in {"invoice_payment_row_match", "pos_payment_match"}:
			return manual(
				"Only invoice payment row or POS payment row evidence is eligible for Sales Invoice auto-match.",
				category="manual_review",
			)
		if amount_scenario_key not in {"exact_invoice_payment_row_amount"}:
			return manual(
				"Only exact invoice payment row matches are eligible for auto-match.",
				category="manual_review",
			)
	elif suggested_document_type == "Payment Entry":
		if not settings.get("allow_auto_match_payment_entry"):
			return blocked("Payment Entry auto-match is disabled in Settings.")
		if amount_scenario_key not in AUTO_MATCH_EXACT_PAYMENT_ENTRY_SCENARIOS:
			return manual("Only exact Payment Entry matches are eligible for auto-match.", category="manual_review")
		if len(payment_entry_context) > 1:
			return manual("Payment Entry with multiple invoice allocations requires manual review.", category="manual_review")
	else:
		return blocked("Only Sales Invoice and Payment Entry suggestions are supported for auto-match.", category="unsafe")
	if settings.get("require_exact_reference_for_auto_match") and not cint(row.get("reference_match_exact")):
		return blocked("Reference is not strong enough.", category="weak_reference")
	if settings.get("require_same_bank_account_for_auto_match"):
		if cstr(row.get("account_resolution_status")).strip() == "unresolved":
			return blocked("Could not resolve bank/payment account mapping; manual review required.", category="account_unresolved")
		if row.get("account_match_available") and not cint(row.get("account_match")):
			return blocked("Bank account mismatch.", category="account_mismatch")
	if settings.get("require_same_branch_for_auto_match") and cint(row.get("branch_match_available")) and not cint(row.get("branch_match")):
		return blocked("Branch mismatch.", category="branch_mismatch")
	if settings.get("require_no_duplicate_candidate_for_auto_match") and cint(row.get("duplicate_candidate_skipped")):
		return blocked("Duplicate candidate in current view.", category="duplicate_candidate")
	if settings.get("require_no_active_review_for_auto_match") and match_record and decision_status not in {"", "Rejected", "Cancelled", "Reopened"}:
		return blocked("Active review already exists.", category="active_review")
	if settings.get("auto_confirm_exact_bank_matches"):
		return {
			"status": "Eligible for Auto-Confirm",
			"reason": "Strict exact high-confidence match is eligible for RetailEdge auto-confirm at the review layer only.",
			"eligible_prepare": True,
			"eligible_confirm": True,
			"category": "eligible_confirm",
		}
	if settings.get("auto_prepare_exact_bank_matches"):
		return {
			"status": "Eligible for Auto-Prepare",
			"reason": "Strict exact high-confidence match is eligible for RetailEdge auto-prepare as a review record only.",
			"eligible_prepare": True,
			"eligible_confirm": False,
			"category": "eligible_prepare",
		}
	return blocked("RetailEdge auto-match actions are disabled in Settings.")


def score_bank_transaction_candidate(bank_transaction, candidate):
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	settings = (context or {}).get("settings") or get_bank_transaction_matching_settings()
	tolerance = flt(settings.get("amount_tolerance"))
	score = 0
	reasons = []
	bank_amount = flt(bank_transaction.get("amount"))
	candidate_amount = flt(candidate.get("candidate_amount"))
	amount_difference = abs(bank_amount - candidate_amount)

	if amount_difference <= 0.01:
		score += 35
		reasons.append(candidate.get("reason") or "Exact amount match.")
	elif amount_difference <= tolerance:
		score += 25
		reasons.append(candidate.get("reason") or "Amount is within the configured tolerance.")
	elif candidate.get("supports_partial_match") and min(bank_amount, candidate_amount) > 0:
		score += 15
		reasons.append(candidate.get("reason") or "Amount suggests a possible partial or allocated match.")
	else:
		score -= 25
		reasons.append(candidate.get("reason") or "Amount is materially different.")

	bank_reference_text = " ".join(
		part
		for part in (
			cstr(bank_transaction.get("reference")).strip(),
			cstr(bank_transaction.get("description")).strip(),
		)
		if part
	)
	normalized_bank_text = normalize_statement_text(bank_reference_text)
	candidate_reference = cstr(candidate.get("reference")).strip()
	normalized_candidate_reference = normalize_statement_reference(reference=candidate_reference) if candidate_reference else ""
	candidate_name = cstr(candidate.get("document_name")).strip()
	normalized_candidate_name = normalize_statement_text(candidate_name)
	suggested_invoice = cstr(candidate.get("suggested_sales_invoice")).strip()
	normalized_invoice_name = normalize_statement_text(suggested_invoice) if suggested_invoice else ""
	reference_match_exact = 0
	reference_match_strength = "weak"

	if normalized_invoice_name and normalized_invoice_name in normalized_bank_text:
		score += 30
		reasons.append("Bank narration/reference contains the Sales Invoice name.")
		reference_match_exact = 1
		reference_match_strength = "strong"
	elif normalized_candidate_name and normalized_candidate_name in normalized_bank_text:
		score += 30
		reasons.append("Bank narration/reference contains the suggested document name.")
		reference_match_exact = 1
		reference_match_strength = "strong"
	elif normalized_candidate_reference and normalized_candidate_reference == bank_transaction.get("normalized_reference"):
		score += 25
		reasons.append("Normalized reference matches exactly.")
		reference_match_exact = 1
		reference_match_strength = "exact"

	customer = cstr(candidate.get("customer")).strip()
	if customer and normalize_statement_text(customer) in normalized_bank_text:
		score += 15
		reasons.append("Customer or party name appears in the bank narration.")

	bank_date = bank_transaction.get("transaction_date")
	candidate_date = candidate.get("posting_date")
	date_difference = _date_difference_days(bank_date, candidate_date)
	if date_difference == 0:
		score += 10
		reasons.append("Transaction date matches exactly.")
	elif date_difference is not None and date_difference <= cint(settings.get("date_window_days") or 3):
		score += 5
		reasons.append("Transaction date is within the matching window.")

	if candidate.get("account_resolution_status"):
		account_payload = {
			"status": candidate.get("account_resolution_status"),
			"matched": candidate.get("account_resolution_status") in {"match", "match_via_mapping"},
			"available": bool(candidate.get("bank_canonical_account") or candidate.get("candidate_canonical_account")),
			"reason": candidate.get("account_resolution_reason"),
			"bank_canonical_account": candidate.get("bank_canonical_account"),
			"candidate_canonical_account": candidate.get("candidate_canonical_account"),
		}
	else:
		account_payload = _resolve_account_match_payload(bank_transaction, candidate)
	account_match = account_payload.get("matched") is True
	account_match_available = 1 if account_payload.get("available") else 0
	if account_match:
		score += 10
		reasons.append(account_payload.get("reason") or "Bank account or expected account aligns with the transaction.")

	branch_match = bool(bank_transaction.get("branch") and candidate.get("branch") and bank_transaction.get("branch") == candidate.get("branch"))
	branch_match_available = 1 if bank_transaction.get("branch") and candidate.get("branch") else 0
	if branch_match:
		score += 5
		reasons.append("RetailEdge branch attribution matches.")

	if candidate.get("document_type") == "Sales Invoice" and cstr(candidate.get("payment_verification_status")).strip() == "Bank Verified":
		score -= 30
		reasons.append("Sales Invoice is already marked Bank Verified.")

	if bank_transaction.get("direction") == "Outflow" and candidate.get("document_type") == "Sales Invoice":
		score -= 60
		reasons.append("Outflow transactions are not treated as customer sales receipts.")

	category_key = normalize_candidate_category_key(candidate.get("candidate_category"))
	if category_key == "payment_entry_match":
		score += 20
		reasons.append("Matched submitted Payment Entry.")
	elif category_key in {"invoice_payment_row_match", "pos_payment_match"}:
		score += 15
		reasons.append(
			"Matched POS payment row." if category_key == "pos_payment_match" else "Matched invoice payment row."
		)
	elif category_key == "invoice_context_only":
		if getattr(frappe.local, "_retailedge_matching_diagnostics", None) is not None:
			frappe.local._retailedge_matching_diagnostics["excluded_context_only"] += 1
		score = min(score, cint(settings.get("strong_match_score") or 80) - 1)
		reasons.append("Sales Invoice is context only; payment event evidence is required for auto-match.")
	elif category_key == "weak_invoice_total_similarity":
		if getattr(frappe.local, "_retailedge_matching_diagnostics", None) is not None:
			frappe.local._retailedge_matching_diagnostics["excluded_context_only"] += 1
		score = min(score, 45)
		reasons.append("Invoice total matched, but no matching payment event was found.")

	if amount_scenario_requires_manual_review(candidate.get("amount_scenario")):
		score = min(score, cint(settings.get("strong_match_score") or 80) - 1)
		reasons.append(f"{get_amount_scenario_label(candidate.get('amount_scenario'))} requires manual review.")

	if score >= cint(settings.get("strong_match_score") or 80):
		confidence = "Strong Match"
	elif score >= cint(settings.get("minimum_possible_score") or 50):
		confidence = "Possible Match"
	elif score >= 30:
		confidence = "Weak Match"
	else:
		confidence = "No Match"

	return {
		"score": score,
		"confidence": confidence,
		"reasons": reasons,
		"reference_match_exact": reference_match_exact,
		"reference_match_strength": reference_match_strength,
		"date_difference_days": date_difference,
		"date_exact": 1 if date_difference == 0 else 0,
		"date_in_normal_window": 1 if date_difference is not None and date_difference <= cint(settings.get("date_window_days") or 3) else 0,
		"account_match": 1 if account_match else 0,
		"account_match_available": account_match_available,
		"account_resolution_status": account_payload.get("status"),
		"account_resolution_reason": account_payload.get("reason"),
		"bank_canonical_account": account_payload.get("bank_canonical_account"),
		"candidate_canonical_account": account_payload.get("candidate_canonical_account"),
		"branch_match": 1 if branch_match else 0,
		"branch_match_available": branch_match_available,
	}



def _timing_bucket(debug_timings, key):
	if debug_timings is None:
		return None
	debug_timings.setdefault(key, 0.0)
	return time.perf_counter()


def _finish_timing(debug_timings, key, start):
	if debug_timings is not None and start is not None:
		debug_timings[key] = debug_timings.get(key, 0.0) + (time.perf_counter() - start)


def _date_bounds_for_transactions(bank_transactions, window_days):
	dates = [getdate(row.get("transaction_date")) for row in bank_transactions or [] if row.get("transaction_date")]
	if not dates:
		return None
	return [
		str(frappe.utils.add_days(min(dates), -cint(window_days or 0))),
		str(frappe.utils.add_days(max(dates), cint(window_days or 0))),
	]


def build_matching_report_context(bank_transaction_rows, filters=None, settings=None, debug_timings=None):
	filters = frappe._dict(filters or {})
	settings = settings or get_bank_transaction_matching_settings()
	start = _timing_bucket(debug_timings, "context_total")
	normalized_transactions = []
	for source_row in bank_transaction_rows or []:
		normalized = normalize_bank_transaction(source_row)
		if not normalized.get("bank_transaction") and isinstance(source_row, dict):
			normalized["bank_transaction"] = source_row.get("name")
		normalized_transactions.append(normalized)
	context = frappe._dict(
		{
			"settings": settings,
			"bank_transactions_by_name": {row.get("bank_transaction"): row for row in normalized_transactions if row.get("bank_transaction")},
			"payment_entries_by_bank_transaction": {},
			"payment_entry_references_by_entry": {},
			"sales_invoices_by_bank_transaction": {},
			"invoice_payment_rows_by_invoice": {},
			"active_review_by_candidate": {},
			"confirmed_review_by_candidate": {},
			"bank_account_ledger_cache": {},
			"mode_of_payment_account_cache": {},
			"branch_profile_defaults_cache": {},
		}
	)
	_prefetch_payment_entry_context(context, normalized_transactions, filters, settings, debug_timings=debug_timings)
	_prefetch_sales_invoice_context(context, normalized_transactions, filters, settings, debug_timings=debug_timings)
	_prefetch_active_review_context(context, debug_timings=debug_timings)
	_finish_timing(debug_timings, "context_total", start)
	if debug_timings is not None:
		debug_timings["bank_transactions_selected"] = len(bank_transaction_rows or [])
		debug_timings["payment_entries_prefetched"] = sum(len(rows or []) for rows in context.payment_entries_by_bank_transaction.values())
		debug_timings["sales_invoices_prefetched"] = sum(len(rows or []) for rows in context.sales_invoices_by_bank_transaction.values())
		debug_timings["invoice_payment_rows_prefetched"] = sum(len(rows or []) for rows in context.invoice_payment_rows_by_invoice.values())
	return context


def _prefetch_payment_entry_sort_key(row, bank_transaction, bank_canonical_account):
	direction = bank_transaction.get("direction")
	candidate_amount = flt(row.get("received_amount") if direction == "Inflow" else row.get("paid_amount"))
	if candidate_amount <= 0:
		candidate_amount = flt(row.get("paid_amount") or row.get("received_amount"))
	
	amt_diff = abs(flt(bank_transaction.get("amount")) - candidate_amount)
	is_exact_amount = 1 if amt_diff <= 0.01 else 0
	
	bank_ref_norm = bank_transaction.get("normalized_reference")
	bank_text = " ".join(part for part in (cstr(bank_transaction.get("reference")).strip(), cstr(bank_transaction.get("description")).strip()) if part).lower()
	
	candidate_ref = cstr(row.get("reference_no")).strip()
	candidate_ref_norm = normalize_statement_reference(reference=candidate_ref) if candidate_ref else ""
	candidate_name = cstr(row.get("name")).strip().lower()
	
	ref_rank = 0
	if candidate_ref_norm and bank_ref_norm and candidate_ref_norm == bank_ref_norm:
		ref_rank = 3
	elif (candidate_ref_norm and candidate_ref_norm in bank_text) or (candidate_name in bank_text):
		ref_rank = 2
	
	candidate_account = row.get("paid_to") if direction == "Inflow" else row.get("paid_from")
	is_account_match = 0
	if bank_canonical_account and candidate_account and bank_canonical_account == candidate_account:
		is_account_match = 1
		
	date_diff = 9999
	if bank_transaction.get("transaction_date") and row.get("posting_date"):
		try:
			date_diff = abs((getdate(bank_transaction.get("transaction_date")) - getdate(row.get("posting_date"))).days)
		except Exception:
			pass
			
	return (-ref_rank, -is_exact_amount, -is_account_match, date_diff, -candidate_amount)


def _prefetch_sales_invoice_sort_key(row, bank_transaction, bank_canonical_account):
	bank_amount = flt(bank_transaction.get("amount"))
	best_amt_diff = min(
		abs(bank_amount - flt(row.get("outstanding_amount"))),
		abs(bank_amount - flt(row.get("grand_total"))),
		abs(bank_amount - flt(row.get("paid_amount"))) if flt(row.get("paid_amount")) > 0 else 999999
	)
	is_exact_amount = 1 if best_amt_diff <= 0.01 else 0
	
	bank_ref_norm = bank_transaction.get("normalized_reference")
	bank_text = " ".join(part for part in (cstr(bank_transaction.get("reference")).strip(), cstr(bank_transaction.get("description")).strip()) if part).lower()
	
	candidate_name = cstr(row.get("name")).strip().lower()
	customer_name = cstr(row.get("customer_name") or row.get("customer")).strip().lower()
	
	ref_rank = 0
	if bank_ref_norm and normalize_statement_reference(reference=row.get("name")) == bank_ref_norm:
		ref_rank = 3
	elif candidate_name in bank_text:
		ref_rank = 2
	elif customer_name and customer_name in bank_text:
		ref_rank = 1
		
	date_diff = 9999
	if bank_transaction.get("transaction_date") and row.get("posting_date"):
		try:
			date_diff = abs((getdate(bank_transaction.get("transaction_date")) - getdate(row.get("posting_date"))).days)
		except Exception:
			pass
			
	return (-ref_rank, -is_exact_amount, date_diff, -flt(row.get("grand_total")))


def _prefetch_payment_entry_context(context, bank_transactions, filters, settings, debug_timings=None):
	if not bank_transactions or not has_doctype("Payment Entry"):
		return
	start = _timing_bucket(debug_timings, "payment_entry_prefetch")
	try:
		fields = ["name", "posting_date", "company", "party", "party_type", "paid_from", "paid_to", "paid_amount", "received_amount"]
		for fieldname in ("reference_no", "remarks", "custom_remarks", "status", "retailedge_branch", "bank_account", "mode_of_payment"):
			if has_field("Payment Entry", fieldname) and fieldname not in fields:
				fields.append(fieldname)
		filters_payload = {"docstatus": 1}
		if filters.get("company") and has_field("Payment Entry", "company"):
			filters_payload["company"] = filters.get("company")
		elif has_field("Payment Entry", "company"):
			companies = sorted({row.get("company") for row in bank_transactions if row.get("company")})
			if len(companies) == 1:
				filters_payload["company"] = companies[0]
			elif len(companies) > 1:
				filters_payload["company"] = ["in", companies]
		if filters.get("branch") and has_field("Payment Entry", "retailedge_branch"):
			filters_payload["retailedge_branch"] = filters.get("branch")
		window = _candidate_search_date_window(filters, settings)
		bounds = _date_bounds_for_transactions(bank_transactions, window)
		if bounds and has_field("Payment Entry", "posting_date"):
			filters_payload["posting_date"] = ["between", bounds]
		all_rows = frappe.get_all(
			"Payment Entry",
			filters=filters_payload,
			fields=fields,
			limit_page_length=0,
			order_by="posting_date desc, modified desc",
		)
		entry_names = [row.get("name") for row in all_rows if row.get("name")]
		context.payment_entry_references_by_entry = _get_payment_entry_sales_invoice_references(entry_names)
		for bank_transaction in bank_transactions:
			rows = []
			date_filter = _date_range_filter(bank_transaction.get("transaction_date"), window)
			for row in all_rows:
				if bank_transaction.get("company") and row.get("company") != bank_transaction.get("company"):
					continue
				if date_filter and row.get("posting_date"):
					posting_date = str(getdate(row.get("posting_date")))
					if posting_date < date_filter[1][0] or posting_date > date_filter[1][1]:
						continue
				rows.append(row)
			
			bank_canonical_account = _resolve_bank_transaction_canonical_account(bank_transaction).get("canonical_account")
			rows.sort(key=lambda r: _prefetch_payment_entry_sort_key(r, bank_transaction, bank_canonical_account))
			context.payment_entries_by_bank_transaction[bank_transaction.get("bank_transaction")] = _dedupe_named_rows(rows)[:60]
	finally:
		_finish_timing(debug_timings, "payment_entry_prefetch", start)


def _prefetch_sales_invoice_context(context, bank_transactions, filters, settings, debug_timings=None):
	if not bank_transactions or not has_doctype("Sales Invoice"):
		return
	start = _timing_bucket(debug_timings, "sales_invoice_prefetch")
	try:
		fields = ["name", "posting_date", "company", "customer", "customer_name", "grand_total", "outstanding_amount"]
		optional_fields = ("paid_amount", "pos_profile", "retailedge_branch", "branch", "retailedge_payment_verification_status", "debit_to", "cash_bank_account", "owner")
		for fieldname in optional_fields:
			if has_field("Sales Invoice", fieldname) and fieldname not in fields:
				fields.append(fieldname)
		filters_payload = {"docstatus": 1}
		if filters.get("company") and has_field("Sales Invoice", "company"):
			filters_payload["company"] = filters.get("company")
		elif has_field("Sales Invoice", "company"):
			companies = sorted({row.get("company") for row in bank_transactions if row.get("company")})
			if len(companies) == 1:
				filters_payload["company"] = companies[0]
			elif len(companies) > 1:
				filters_payload["company"] = ["in", companies]
		if filters.get("branch"):
			branch_field = _first_existing_sales_invoice_branch_field()
			if branch_field:
				filters_payload[branch_field] = filters.get("branch")
		if filters.get("pos_profile") and has_field("Sales Invoice", "pos_profile"):
			filters_payload["pos_profile"] = filters.get("pos_profile")
		if filters.get("only_pos_invoices") and has_field("Sales Invoice", "is_pos"):
			filters_payload["is_pos"] = 1
		window = _candidate_search_date_window(filters, settings)
		bounds = _date_bounds_for_transactions(bank_transactions, window)
		if bounds and has_field("Sales Invoice", "posting_date"):
			filters_payload["posting_date"] = ["between", bounds]
		all_rows = frappe.get_all(
			"Sales Invoice",
			filters=filters_payload,
			fields=fields,
			limit_page_length=0,
			order_by="posting_date desc, modified desc",
		)
		if not cint(filters.get("include_verified_invoices")) and has_field("Sales Invoice", "retailedge_payment_verification_status"):
			all_rows = [row for row in all_rows if cstr(row.get("retailedge_payment_verification_status")).strip() != "Bank Verified"]
		for bank_transaction in bank_transactions:
			rows = []
			date_filter = _date_range_filter(bank_transaction.get("transaction_date"), window)
			for row in all_rows:
				if bank_transaction.get("company") and row.get("company") != bank_transaction.get("company"):
					continue
				if date_filter and row.get("posting_date"):
					posting_date = str(getdate(row.get("posting_date")))
					if posting_date < date_filter[1][0] or posting_date > date_filter[1][1]:
						continue
				rows.append(row)
			
			bank_canonical_account = _resolve_bank_transaction_canonical_account(bank_transaction).get("canonical_account")
			rows.sort(key=lambda r: _prefetch_sales_invoice_sort_key(r, bank_transaction, bank_canonical_account))
			context.sales_invoices_by_bank_transaction[bank_transaction.get("bank_transaction")] = _dedupe_named_rows(rows)[:60]
		invoice_names = sorted({row.get("name") for rows in context.sales_invoices_by_bank_transaction.values() for row in rows if row.get("name")})
		context.invoice_payment_rows_by_invoice = _prefetch_invoice_payment_rows(invoice_names, all_rows)
		bank_matchable_invoice_names = set(context.invoice_payment_rows_by_invoice)
		for bank_transaction_name, rows in list(context.sales_invoices_by_bank_transaction.items()):
			context.sales_invoices_by_bank_transaction[bank_transaction_name] = [
				row for row in rows if row.get("name") in bank_matchable_invoice_names
			]
	finally:
		_finish_timing(debug_timings, "sales_invoice_prefetch", start)


def _prefetch_invoice_payment_rows(invoice_names, invoice_rows):
	if not invoice_names or not has_doctype("Sales Invoice Payment"):
		return {}
	try:
		fields = ["parent", "idx", "mode_of_payment", "account", "amount", "base_amount"]
		for fieldname in ("default_account",):
			if has_field("Sales Invoice Payment", fieldname):
				fields.append(fieldname)
		payment_rows = frappe.get_all(
			"Sales Invoice Payment",
			filters={"parent": ["in", invoice_names]},
			fields=fields,
			limit_page_length=0,
			order_by="parent asc, idx asc",
		)
	except Exception:
		return {}
	invoice_by_name = {row.get("name"): row for row in invoice_rows or [] if row.get("name")}
	grouped = defaultdict(list)
	for idx, payment_row in enumerate(payment_rows or [], start=1):
		invoice = frappe._dict(invoice_by_name.get(payment_row.get("parent")) or {})
		row = frappe._dict(payment_row or {})
		amount = flt(row.get("base_amount") if row.get("base_amount") is not None else row.get("amount"))
		classification = classify_payment_method(
			mode_of_payment=row.get("mode_of_payment"),
			account=row.get("account") or row.get("default_account"),
			row=row,
		)
		try:
			expected = get_expected_payment_account_for_invoice(
				invoice,
				payment_category=classification.get("category"),
				mode_of_payment=row.get("mode_of_payment"),
			)
		except Exception:
			expected = {}
		actual_account = row.get("account") or row.get("default_account")
		expected_account = expected.get("account")
		account_matches_expected = None
		issue = None
		if expected_account:
			account_matches_expected = actual_account == expected_account
			if account_matches_expected is False:
				issue = "Payment account does not match the expected branch account."
		grouped[row.get("parent")].append(
			{
				"payment_row_index": row.get("idx") or idx,
				"mode_of_payment": row.get("mode_of_payment"),
				"account": actual_account,
				"amount": flt(row.get("amount")),
				"base_amount": amount,
				"payment_category": classification.get("category"),
				"expected_account": expected_account,
				"account_matches_expected": account_matches_expected,
				"issue": issue,
			}
		)
	return dict(grouped)


def _prefetch_active_review_context(context, debug_timings=None):
	if not has_doctype("RetailEdge Bank Transaction Match"):
		return
	start = _timing_bucket(debug_timings, "active_review_prefetch")
	try:
		fields = ["name", "bank_transaction", "suggested_document_type", "suggested_document", "sales_invoice", "payment_entry", "decision_status", "decision_note", "last_action", "candidate_amount", "modified"]
		status_filter = ["not in", sorted(RELEASED_REVIEW_MATCH_STATUSES)]
		candidate_keys = set()
		for rows in context.sales_invoices_by_bank_transaction.values():
			candidate_keys.update(("Sales Invoice", row.get("name")) for row in rows if row.get("name"))
		for rows in context.payment_entries_by_bank_transaction.values():
			candidate_keys.update(("Payment Entry", row.get("name")) for row in rows if row.get("name"))
		all_matches = []
		for doctype in ("Sales Invoice", "Payment Entry"):
			names = sorted(name for candidate_doctype, name in candidate_keys if candidate_doctype == doctype)
			if not names:
				continue
			all_matches.extend(frappe.get_all("RetailEdge Bank Transaction Match", filters={"suggested_document_type": doctype, "suggested_document": ["in", names], "decision_status": status_filter}, fields=fields, limit_page_length=0, order_by="modified desc"))
			legacy_field = "sales_invoice" if doctype == "Sales Invoice" else "payment_entry"
			all_matches.extend(frappe.get_all("RetailEdge Bank Transaction Match", filters={legacy_field: ["in", names], "decision_status": status_filter}, fields=fields, limit_page_length=0, order_by="modified desc"))
		for match_row in all_matches:
			keys = []
			if match_row.get("suggested_document_type") and match_row.get("suggested_document"):
				keys.append((match_row.get("suggested_document_type"), match_row.get("suggested_document")))
			if match_row.get("sales_invoice"):
				keys.append(("Sales Invoice", match_row.get("sales_invoice")))
			if match_row.get("payment_entry"):
				keys.append(("Payment Entry", match_row.get("payment_entry")))
			for key in keys:
				context.active_review_by_candidate.setdefault(key, match_row)
				if cstr(match_row.get("decision_status")).strip() == ACTIVE_CONFIRMED_MATCH_STATUS:
					context.confirmed_review_by_candidate.setdefault(key, match_row)
	finally:
		_finish_timing(debug_timings, "active_review_prefetch", start)

def get_bank_transaction_matching_rows(filters=None, limit=500, debug_timings=None):
	filters = _coerce_matching_filters(filters)
	settings = get_bank_transaction_matching_settings()
	result_limit = min(int(limit or 500), 2000)

	# Determine chunking configurations
	chunk_size = 100
	scan_limit = min(max(1000, result_limit * 10), 5000)

	candidate_rows = []
	suppressed_rows = []
	eligible_rows = []
	raw_rows_scanned = 0
	limit_start = 0
	stop_reason = "No more source Bank Transactions exist"

	# Diagnostics counters
	diagnostics = {
		"excluded_active_review": 0,
	}

	# Register diagnostics on thread-local
	frappe.local._retailedge_matching_diagnostics = {
		"excluded_cash": 0,
		"excluded_context_only": 0,
	}

	fetched_names = set()
	try:
		while raw_rows_scanned < scan_limit:
			next_chunk_size = min(chunk_size, scan_limit - raw_rows_scanned)
			if next_chunk_size <= 0:
				stop_reason = "scan_limit reached"
				break

			chunk_rows = _get_bank_transaction_rows(filters, next_chunk_size, limit_start=limit_start)
			if not chunk_rows:
				stop_reason = "No more source Bank Transactions exist"
				break

			new_chunk_rows = []
			for r in chunk_rows:
				name = r.get("name")
				if name not in fetched_names:
					fetched_names.add(name)
					new_chunk_rows.append(r)

			if not new_chunk_rows:
				stop_reason = "No more source Bank Transactions exist"
				break

			chunk_rows = new_chunk_rows
			raw_rows_scanned += len(chunk_rows)
			limit_start += len(chunk_rows)

			start_time = _timing_bucket(debug_timings, "existing_match_fetch")
			existing_matches_by_transaction = _get_existing_matches_by_bank_transaction(
				[row.get("name") for row in chunk_rows if row.get("name")]
			)
			_finish_timing(debug_timings, "existing_match_fetch", start_time)

			context = build_matching_report_context(chunk_rows, filters=filters, settings=settings, debug_timings=debug_timings)
			previous_context = getattr(frappe.local, "_retailedge_bank_match_context", None)
			frappe.local._retailedge_bank_match_context = context

			chunk_candidate_rows = []
			try:
				for bank_transaction_row in chunk_rows:
					bank_transaction = context.bank_transactions_by_name.get(bank_transaction_row.get("name")) or normalize_bank_transaction(bank_transaction_row)
					transaction_matches = existing_matches_by_transaction.get(bank_transaction.get("bank_transaction")) or []
					confirmed_match = _first_match_with_status(transaction_matches, "Confirmed")
					rejected_match = _first_match_with_status(transaction_matches, "Rejected")
					active_review_match = _first_active_review_match(transaction_matches)
					active_nonconfirmed_match = _first_active_review_match(transaction_matches, include_confirmed=False)
					review_queue_status = _review_queue_status_mode(filters)

					if review_queue_status == "Open Suggestions Only" and active_review_match:
						diagnostics["excluded_active_review"] += 1
						continue
					if review_queue_status == "Already In Review" and not active_nonconfirmed_match:
						continue
					if review_queue_status == "Confirmed" and not confirmed_match:
						continue
					if review_queue_status == "Rejected" and not rejected_match:
						continue
					if confirmed_match and not filters.get("include_confirmed_matches") and review_queue_status not in {"Confirmed", "All"}:
						diagnostics["excluded_active_review"] += 1
						continue
					if bank_transaction.get("is_reconciled") and not filters.get("include_reconciled"):
						continue
					if bank_transaction.get("direction") == "Outflow":
						if confirmed_match and filters.get("include_confirmed_matches"):
							row = _build_matching_row(
								bank_transaction,
								candidate=None,
								action_status="Outflow / Not Sales Receipt",
								match_reason="Outflow transactions are not eligible for customer receipt bank matching in this phase.",
							)
							_apply_selected_match_to_row(row, confirmed_match, include_confirmed=filters.get("include_confirmed_matches"))
							auto_match_status = get_auto_match_status_for_row(row, settings=settings)
							row["auto_match_status"] = auto_match_status.get("status")
							row["auto_match_reason"] = auto_match_status.get("reason")
							row["auto_match_category"] = auto_match_status.get("category")
							row["eligible_for_auto_prepare"] = 1 if auto_match_status.get("eligible_prepare") else 0
							row["eligible_for_auto_confirm"] = 1 if auto_match_status.get("eligible_confirm") else 0
							if not _matching_row_passes_optional_filters(row, filters):
								continue
							chunk_candidate_rows.append(row)
						continue

					sales_start = _timing_bucket(debug_timings, "sales_invoice_resolution")
					sales_candidates = find_sales_invoice_candidates_for_bank_transaction(
						bank_transaction.get("bank_transaction"),
						filters=filters,
						limit=20,
						context=context,
					)
					_finish_timing(debug_timings, "sales_invoice_resolution", sales_start)
					payment_start = _timing_bucket(debug_timings, "payment_entry_resolution")
					payment_candidates = find_payment_entry_candidates_for_bank_transaction(
						bank_transaction.get("bank_transaction"),
						filters=filters,
						limit=20,
						context=context,
					)
					_finish_timing(debug_timings, "payment_entry_resolution", payment_start)
					candidates = sorted(
						sales_candidates + payment_candidates,
						key=_queue_candidate_rank,
						reverse=True,
					)
					best_candidate, selected_match = _select_candidate_for_queue(candidates, transaction_matches, filters)
					if review_queue_status == "Rejected" and rejected_match:
						best_candidate = _find_candidate_for_match_row(candidates, rejected_match)
						selected_match = rejected_match if best_candidate else selected_match
					if not best_candidate and confirmed_match and filters.get("include_confirmed_matches"):
						selected_match = confirmed_match
					if not best_candidate and not selected_match:
						continue
					action_status = _derive_action_status(bank_transaction, best_candidate)
					match_reason = "; ".join((best_candidate or {}).get("reasons") or []) if best_candidate else "No candidate reached the minimum matching confidence."
					row = _build_matching_row(
						bank_transaction,
						candidate=best_candidate,
						action_status=action_status,
						match_reason=match_reason,
					)
					if filters.get("match_confidence") and row.get("match_confidence") != filters.get("match_confidence"):
						continue
					if _as_bool(filters.get("only_unmatched")) and row.get("action_status") in {"Already Reconciled", "Already Bank Verified"}:
						continue
					min_score = cint(filters.get("min_score") or 0)
					if min_score and cint(row.get("match_score") or 0) < min_score:
						continue
					_apply_selected_match_to_row(
						row,
						selected_match or confirmed_match,
						include_confirmed=filters.get("include_confirmed_matches"),
					)
					if active_review_match and not row.get("match_record") and review_queue_status in {"Already In Review", "All", "Confirmed"}:
						row["match_record"] = active_review_match.get("name")
						row["decision_status"] = active_review_match.get("decision_status")
						row["action_status"] = "Existing Active Review" if cstr(active_review_match.get("decision_status")).strip() != "Confirmed" else "Already Confirmed"
						row["match_reason"] = (row.get("match_reason") or "") + ("; " if row.get("match_reason") else "") + "Active review record already exists."
					auto_match_status = get_auto_match_status_for_row(row, settings=settings)
					row["auto_match_status"] = auto_match_status.get("status")
					row["auto_match_reason"] = auto_match_status.get("reason")
					row["auto_match_category"] = auto_match_status.get("category")
					row["eligible_for_auto_prepare"] = 1 if auto_match_status.get("eligible_prepare") else 0
					row["eligible_for_auto_confirm"] = 1 if auto_match_status.get("eligible_confirm") else 0
					if not _matching_row_passes_optional_filters(row, filters):
						continue
					chunk_candidate_rows.append(row)
			finally:
				if previous_context is None:
					try:
						del frappe.local._retailedge_bank_match_context
					except AttributeError:
						pass
				else:
					frappe.local._retailedge_bank_match_context = previous_context

			candidate_rows.extend(chunk_candidate_rows)

			# Re-apply duplicate suppression + post filters on the entire collected candidate_rows
			suppressed_rows = suppress_duplicate_candidate_suggestions(candidate_rows, mark_duplicates=True)
			eligible_rows = [row for row in suppressed_rows if _matching_row_passes_post_suppression_filters(row, filters)]

			if len(eligible_rows) >= result_limit:
				stop_reason = "eligible_rows_returned >= result_limit"
				break
	finally:
		# Extract and clean up thread-local diagnostics
		local_diag = getattr(frappe.local, "_retailedge_matching_diagnostics", {})
		if hasattr(frappe.local, "_retailedge_matching_diagnostics"):
			del frappe.local._retailedge_matching_diagnostics

	# Compute duplicate conflict exclusion count
	excluded_duplicate_conflict = sum(
		1 for row in suppressed_rows
		if row.get("duplicate_candidate_skipped") or row.get("action_status") == "Duplicate Candidate"
	)

	# Expose diagnostics in debug_timings if passed
	if debug_timings is not None:
		debug_timings.update({
			"result_limit": result_limit,
			"scan_limit": scan_limit,
			"raw_rows_scanned": raw_rows_scanned,
			"candidate_rows_built": len(candidate_rows),
			"excluded_active_review": diagnostics["excluded_active_review"],
			"excluded_context_only": local_diag.get("excluded_context_only", 0),
			"excluded_cash": local_diag.get("excluded_cash", 0),
			"excluded_duplicate_conflict": excluded_duplicate_conflict,
			"eligible_rows_returned": len(eligible_rows),
			"scan_stopped_reason": stop_reason
		})
		debug_timings["rows_returned"] = len(eligible_rows[:result_limit])

	return eligible_rows[:result_limit]

def _matching_row_passes_optional_filters(row, filters):
	checks = {
		"amount_scenario": row.get("amount_scenario"),
		"candidate_category": row.get("candidate_category_label") or row.get("candidate_category"),
		"customer": row.get("customer") or row.get("party"),
		"party": row.get("party") or row.get("customer"),
		"suggested_document_type": row.get("suggested_document_type"),
		"decision_status": row.get("decision_status"),
		"review_status": row.get("decision_status"),
		"suggested_document": row.get("suggested_document"),
		"auto_match_status": row.get("auto_match_status"),
	}
	for fieldname, value in checks.items():
		if filters.get(fieldname) and cstr(filters.get(fieldname)).strip() != cstr(value).strip():
			return False
	return True


def _matching_row_passes_post_suppression_filters(row, filters):
	checks = {
		"action_status": row.get("action_status"),
		"duplicate_candidate_status": "Duplicate Candidate" if cint(row.get("duplicate_candidate_skipped")) else "Not Duplicate Candidate",
		"already_reviewed_status": "Has Review Record" if row.get("match_record") else "No Review Record",
		"exception_status": "Exception Only" if cint(row.get("exception_only")) else "Normal Candidate",
		"review_queue_status": (
			"Confirmed" if cstr(row.get("decision_status")).strip() == "Confirmed" else "Rejected" if cstr(row.get("decision_status")).strip() == "Rejected" else "Already In Review" if row.get("match_record") else "Open Suggestions Only"
		),
	}
	for fieldname, value in checks.items():
		if filters.get(fieldname) and cstr(filters.get(fieldname)).strip() != cstr(value).strip():
			return False
	return True


def suppress_duplicate_candidate_suggestions(rows, mark_duplicates=False):
	"""Keep one normal suggestion per Sales Invoice/Payment Entry in the current result set."""
	indexed_rows = [(idx, frappe._dict(row or {})) for idx, row in enumerate(rows or [])]
	best_by_candidate = {}
	for idx, row in indexed_rows:
		key = get_candidate_document_key(row)
		if not key or row.get("action_status") in {"No Match", "Outflow / Not Sales Receipt", "Already Confirmed"}:
			continue
		current = best_by_candidate.get(key)
		if current is None or _duplicate_candidate_rank(row, idx) > _duplicate_candidate_rank(current[1], current[0]):
			best_by_candidate[key] = (idx, row)

	result = []
	for idx, row in indexed_rows:
		key = get_candidate_document_key(row)
		if key and key in best_by_candidate and best_by_candidate[key][0] != idx:
			winner = best_by_candidate[key][1]
			row["duplicate_candidate_skipped"] = 1
			row["duplicate_candidate_winner_bank_transaction"] = winner.get("bank_transaction")
			row["duplicate_candidate_reason"] = "Candidate already suggested in this batch/current queue."
			if mark_duplicates:
				row["action_status"] = "Duplicate Candidate"
				row["match_reason"] = (
					"Duplicate Candidate - this invoice/payment entry is already suggested for another bank transaction in the current view."
					+ (
						f" Kept suggestion is {winner.get('bank_transaction')} because it has stronger confidence/score."
						if winner.get("bank_transaction")
						else ""
					)
				)
				result.append(row)
			continue
		result.append(row)
	return result


def split_duplicate_candidate_suggestions(rows):
	marked_rows = suppress_duplicate_candidate_suggestions(rows, mark_duplicates=True)
	kept = [row for row in marked_rows if not cint(row.get("duplicate_candidate_skipped"))]
	skipped = []
	for row in marked_rows:
		if cint(row.get("duplicate_candidate_skipped")) and get_candidate_document_key(row):
			skipped.append(
				frappe._dict(
					{
						**dict(row),
						"duplicate_candidate_skipped": 1,
						"duplicate_candidate_reason": cstr(row.get("duplicate_candidate_reason"))
						or "Candidate already suggested in this batch/current queue.",
						"duplicate_candidate_winner_bank_transaction": row.get("duplicate_candidate_winner_bank_transaction"),
					}
				)
			)
	return kept, skipped


def get_candidate_document_key(row):
	row = row or {}
	document_type = cstr(row.get("suggested_document_type") or row.get("document_type")).strip()
	document_name = cstr(row.get("suggested_document") or row.get("document_name")).strip()
	if document_type not in {"Sales Invoice", "Payment Entry"} or not document_name:
		return None
	return (document_type, document_name)


def _suggestion_identity_key(row):
	row = row or {}
	return (
		cstr(row.get("bank_transaction")).strip(),
		cstr(row.get("suggested_document_type") or row.get("document_type")).strip(),
		cstr(row.get("suggested_document") or row.get("document_name")).strip(),
	)


def _duplicate_candidate_rank(row, index):
	confidence_rank = {"Strong Match": 3, "Possible Match": 2, "Weak Match": 1, "No Match": 0}
	reason_text = cstr(row.get("match_reason") or row.get("reason") or " ".join(row.get("reasons") or [])).lower()
	return (
		_candidate_category_rank(row.get("candidate_category")),
		_amount_scenario_rank(row.get("amount_scenario")),
		confidence_rank.get(cstr(row.get("match_confidence") or row.get("confidence")).strip(), 0),
		cint(row.get("match_score") or row.get("score") or 0),
		-abs(flt(row.get("amount_difference"))),
		-_transaction_candidate_date_gap(row),
		1 if "reference" in reason_text or "invoice name" in reason_text or "suggested document" in reason_text else 0,
		-index,
	)


def _queue_candidate_rank(row):
	confidence_rank = {"Strong Match": 3, "Possible Match": 2, "Weak Match": 1, "No Match": 0}
	strength_map = {"strong": 4, "exact": 3, "contains": 2, "narration_contains_reference": 1}
	return (
		_amount_scenario_rank(row.get("amount_scenario")),
		confidence_rank.get(cstr(row.get("match_confidence") or row.get("confidence")).strip(), 0),
		cint(row.get("match_score") or row.get("score") or 0),
		strength_map.get(cstr(row.get("reference_match_strength")).strip().lower(), 0),
		_candidate_category_rank(row.get("candidate_category")),
		-abs(flt(row.get("amount_difference"))),
		-_transaction_candidate_date_gap(row),
	)


def _candidate_category_rank(value):
	key = normalize_candidate_category_key(value)
	if key == "payment_entry_match":
		return 5
	if key in {"invoice_payment_row_match", "pos_payment_match"}:
		return 4
	if key == "invoice_context_only":
		return 2
	if key == "weak_invoice_total_similarity":
		return 1
	return 0


def _amount_scenario_rank(value):
	key = normalize_amount_scenario_key(value)
	if key in {
		"exact_outstanding_match",
		"exact_outstanding_amount",
		"exact_invoice_amount",
		"submitted_payment_entry_amount",
		"payment_entry_allocated_amount",
		"exact_invoice_payment_row_amount",
	}:
		return 5
	if key in {"invoice_context_only", "weak_invoice_total_similarity"}:
		return 1
	if key in {"partial_payment", "payment_entry_allocated"}:
		return 3
	if key in {"overpayment", "overpayment_advance", "amount_variance", "payment_entry_amount_variance", "multi_invoice_payment"}:
		return 2
	return 1


def _transaction_candidate_date_gap(row):
	transaction_date = row.get("transaction_date")
	candidate_date = row.get("candidate_posting_date") or row.get("posting_date")
	if not transaction_date or not candidate_date:
		return 9999
	return abs((getdate(transaction_date) - getdate(candidate_date)).days)


def _get_sales_invoice_rows(bank_transaction, filters, settings, limit=60):
	fields = [
		"name",
		"posting_date",
		"company",
		"customer",
		"customer_name",
		"grand_total",
		"outstanding_amount",
	]
	optional_fields = (
		"paid_amount",
		"pos_profile",
		"retailedge_branch",
		"branch",
		"retailedge_payment_verification_status",
		"debit_to",
		"cash_bank_account",
	)
	for fieldname in optional_fields:
		if has_field("Sales Invoice", fieldname):
			fields.append(fieldname)

	filters_payload = {"docstatus": 1}
	if bank_transaction.get("company") and has_field("Sales Invoice", "company"):
		filters_payload["company"] = bank_transaction.get("company")
	if filters.get("company") and has_field("Sales Invoice", "company"):
		filters_payload["company"] = filters.get("company")
	if filters.get("branch"):
		branch_field = _first_existing_sales_invoice_branch_field()
		if branch_field:
			filters_payload[branch_field] = filters.get("branch")
	if filters.get("pos_profile") and has_field("Sales Invoice", "pos_profile"):
		filters_payload["pos_profile"] = filters.get("pos_profile")
	if filters.get("only_pos_invoices") and has_field("Sales Invoice", "is_pos"):
		filters_payload["is_pos"] = 1
	date_window = _candidate_search_date_window(filters, settings)
	date_filters = _date_range_filter(bank_transaction.get("transaction_date"), date_window)
	if date_filters and has_field("Sales Invoice", "posting_date"):
		filters_payload["posting_date"] = date_filters

	rows = frappe.get_all(
		"Sales Invoice",
		filters=filters_payload,
		fields=fields,
		limit_page_length=limit,
		order_by="posting_date desc, modified desc",
	)
	if not cint(filters.get("include_verified_invoices")) and has_field("Sales Invoice", "retailedge_payment_verification_status"):
		rows = [
			row
			for row in rows
			if cstr(row.get("retailedge_payment_verification_status")).strip() != "Bank Verified"
		]

	strong_reference = bank_transaction.get("normalized_reference")
	strong_reference_text = " ".join(
		part
		for part in (
			cstr(bank_transaction.get("reference")).strip(),
			cstr(bank_transaction.get("description")).strip(),
		)
		if part
	)
	if strong_reference and is_reliable_statement_reference(strong_reference) and _looks_like_invoice_reference(strong_reference_text):
		for row in frappe.get_all(
			"Sales Invoice",
			filters={"docstatus": 1},
			fields=fields,
			limit_page_length=limit,
			order_by="posting_date desc, modified desc",
		):
			if bank_transaction.get("company") and row.get("company") != bank_transaction.get("company"):
				continue
			if cstr(row.get("name")) and normalize_statement_text(row.get("name")) in strong_reference:
				rows.append(row)

	return _dedupe_named_rows(rows)


def _build_sales_invoice_candidates(bank_transaction, invoice, filters, settings, context=None):
	if context is not None:
		invoice_name = cstr((invoice or {}).get("name")).strip()
		payment_rows_by_invoice = (context or {}).get("invoice_payment_rows_by_invoice") or {}
		if invoice_name and not payment_rows_by_invoice.get(invoice_name):
			return []
	amount_details = _best_invoice_amount_match(bank_transaction, invoice, settings)
	if not amount_details["fieldname"] or amount_details["amount"] <= 0:
		return []
	if amount_details["difference"] > max(flt(settings.get("amount_tolerance")), flt(bank_transaction.get("amount"))):
		return []

	branch = _row_value(invoice, "retailedge_branch") or _row_value(invoice, "branch")
	expected_account = None
	try:
		cache = ((context or {}).get("branch_profile_defaults_cache") if context else None)
		cache_key = (invoice.get("company"), branch, invoice.get("pos_profile"))
		if cache is not None and cache_key in cache:
			profile_defaults = cache.get(cache_key) or {}
		else:
			profile_defaults = get_branch_profile_defaults(
				company=invoice.get("company"),
				branch=branch,
				pos_profile=invoice.get("pos_profile"),
			)
			if cache is not None:
				cache[cache_key] = profile_defaults
		expected_account = profile_defaults.get("default_bank_account")
	except Exception:
		expected_account = None

	base_candidate = {
		"document_type": "Sales Invoice",
		"document_name": invoice.get("name"),
		"suggested_sales_invoice": invoice.get("name"),
		"posting_date": invoice.get("posting_date"),
		"customer": invoice.get("customer"),
		"customer_display": invoice.get("customer_name") or invoice.get("customer"),
		"party": invoice.get("customer"),
		"party_type": "Customer",
		"sales_invoice_outstanding_amount": flt(invoice.get("outstanding_amount")),
		"sales_invoice_grand_total": flt(invoice.get("grand_total")),
		"reference": invoice.get("name"),
		"branch": branch,
		"expected_bank_account": expected_account,
		"payment_verification_status": invoice.get("retailedge_payment_verification_status"),
		"supports_partial_match": True,
	}

	payment_row_candidates = _build_invoice_payment_row_candidates(
		bank_transaction=bank_transaction,
		invoice=invoice,
		base_candidate=base_candidate,
		settings=settings,
		context=context,
	)
	return payment_row_candidates


def _best_invoice_amount_match(bank_transaction, invoice, settings):
	bank_amount = flt(bank_transaction.get("amount"))
	outstanding_amount = flt(invoice.get("outstanding_amount"))
	grand_total = flt(invoice.get("grand_total"))
	paid_amount = flt(invoice.get("paid_amount"))
	tolerance = flt(settings.get("amount_tolerance"))
	if outstanding_amount > 0:
		difference = abs(bank_amount - outstanding_amount)
		if difference <= max(tolerance, 0.01):
			return {
				"fieldname": "outstanding_amount",
				"amount": outstanding_amount,
				"difference": difference,
				"scenario": "Exact Outstanding Amount",
				"reason": "Bank amount matches the Sales Invoice outstanding amount.",
			}
		if bank_amount < outstanding_amount:
			return {
				"fieldname": "outstanding_amount",
				"amount": outstanding_amount,
				"difference": difference,
				"scenario": "Partial Payment",
				"reason": "Bank amount is less than the Sales Invoice outstanding amount. Review as a possible partial payment.",
			}
		return {
			"fieldname": "outstanding_amount",
			"amount": outstanding_amount,
			"difference": difference,
			"scenario": "Overpayment / Advance",
			"reason": "Bank amount is greater than the Sales Invoice outstanding amount. Review as a possible overpayment or advance.",
		}

	candidates = [("grand_total", grand_total), ("paid_amount", paid_amount)]
	best_name = None
	best_amount = 0.0
	best_difference = abs(bank_amount)
	for fieldname, amount in candidates:
		if amount <= 0:
			continue
		difference = abs(bank_amount - amount)
		if not best_name or difference < best_difference:
			best_name = fieldname
			best_amount = amount
			best_difference = difference
	return {
		"fieldname": best_name,
		"amount": best_amount,
		"difference": best_difference,
		"scenario": "Amount Variance" if best_difference > max(tolerance, 0.01) else "Exact Invoice Amount",
		"reason": f"Best invoice amount match used {best_name or 'no supported amount field'}.",
	}


def _build_invoice_payment_row_candidates(bank_transaction, invoice, base_candidate, settings, context=None):
	context = context or getattr(frappe.local, "_retailedge_bank_match_context", None)
	invoice_name = cstr((invoice or {}).get("name")).strip()
	payment_rows = ((context or {}).get("invoice_payment_rows_by_invoice") or {}).get(invoice_name)
	if payment_rows is None:
		invoice_doc = _get_sales_invoice_doc(invoice)
		if not invoice_doc:
			return []
		try:
			payment_rows = get_sales_invoice_payment_rows(invoice_doc)
		except Exception:
			payment_rows = []
	if not payment_rows:
		return []

	bank_amount = flt(bank_transaction.get("amount"))
	tolerance = flt(settings.get("amount_tolerance"))
	candidates = []
	for payment_row in payment_rows:
		payment_category = cstr(payment_row.get("payment_category")).strip()
		candidate_amount = flt(payment_row.get("base_amount") or payment_row.get("amount"))
		if candidate_amount <= 0:
			continue
		amount_difference = abs(bank_amount - candidate_amount)
		if amount_difference > max(tolerance, bank_amount):
			continue
		if not _invoice_payment_row_is_bank_matchable(payment_row):
			continue
		category_key = "pos_payment_match" if payment_category == "Card / POS" else "invoice_payment_row_match"
		scenario = "Exact Invoice Payment Row Amount" if amount_difference <= max(tolerance, 0.01) else "Invoice Payment Row Amount Variance"
		candidate = dict(base_candidate)
		candidate.update(
			{
				"candidate_amount": candidate_amount,
				"amount_difference": amount_difference,
				"amount_scenario": scenario,
				"amount_scenario_label": get_amount_scenario_label(scenario),
				"candidate_category": category_key,
				"candidate_category_label": get_candidate_category_label(category_key),
				"payment_event_found": 1,
				"payment_event_source": "POS Payment Row" if payment_category == "Card / POS" else "Invoice Payment Row",
				"payment_row_index": payment_row.get("payment_row_index"),
				"payment_row_amount": candidate_amount,
				"payment_mode": payment_row.get("mode_of_payment"),
				"payment_account": payment_row.get("account"),
				"payment_category": payment_category,
				"account": payment_row.get("account"),
				"expected_bank_account": payment_row.get("expected_account") or base_candidate.get("expected_bank_account"),
				"reason": "Matched invoice payment row." if payment_category != "Card / POS" else "Matched POS payment row.",
			}
		)
		candidates.append(candidate)
	return candidates


def _invoice_payment_row_is_bank_matchable(payment_row):
	payment_category = cstr((payment_row or {}).get("payment_category")).strip()
	if payment_category == "Cash":
		if getattr(frappe.local, "_retailedge_matching_diagnostics", None) is not None:
			frappe.local._retailedge_matching_diagnostics["excluded_cash"] += 1
		return False
	account = cstr((payment_row or {}).get("account")).strip()
	expected_account = cstr((payment_row or {}).get("expected_account")).strip()
	return bool(account or expected_account)


def _get_sales_invoice_doc(invoice):
	invoice_name = cstr((invoice or {}).get("name")).strip()
	if not invoice_name:
		return None
	try:
		return frappe.get_doc("Sales Invoice", invoice_name)
	except Exception:
		return None


def _invoice_context_candidate_category(invoice, amount_details):
	if flt(invoice.get("outstanding_amount")) <= 0:
		return "weak_invoice_total_similarity"
	return "invoice_context_only"


def _invoice_context_reason(invoice, amount_details):
	scenario_key = normalize_amount_scenario_key(amount_details.get("scenario"))
	if flt(invoice.get("outstanding_amount")) <= 0:
		if amount_details.get("fieldname") == "grand_total" or scenario_key == "exact_invoice_amount":
			return "Paid invoice total similarity only - requires Payment Entry or invoice payment row evidence."
		return "Invoice is context only. Payment Entry or invoice payment row evidence is required."
	if scenario_key == "exact_invoice_amount":
		return "Invoice total matched, but no matching payment event was found."
	return "Invoice is context only. Payment Entry or invoice payment row evidence is required."


def _build_multi_invoice_candidates(bank_transaction, invoices, filters, settings):
	return []


def _get_payment_entry_rows(bank_transaction, filters, settings, limit=60):
	fields = ["name", "posting_date", "company", "party", "party_type", "paid_from", "paid_to", "paid_amount", "received_amount"]
	for fieldname in ("reference_no", "remarks", "custom_remarks", "status", "retailedge_branch", "bank_account"):
		if has_field("Payment Entry", fieldname):
			fields.append(fieldname)

	filters_payload = {"docstatus": 1}
	if bank_transaction.get("company") and has_field("Payment Entry", "company"):
		filters_payload["company"] = bank_transaction.get("company")
	if filters.get("company") and has_field("Payment Entry", "company"):
		filters_payload["company"] = filters.get("company")
	if filters.get("branch") and has_field("Payment Entry", "retailedge_branch"):
		filters_payload["retailedge_branch"] = filters.get("branch")
	date_window = _candidate_search_date_window(filters, settings)
	if has_field("Payment Entry", "posting_date"):
		filters_payload["posting_date"] = _date_range_filter(bank_transaction.get("transaction_date"), date_window)

	rows = frappe.get_all(
		"Payment Entry",
		filters=filters_payload,
		fields=fields,
		limit_page_length=limit,
		order_by="posting_date desc, modified desc",
	)
	return _dedupe_named_rows(rows)


def _get_payment_entry_sales_invoice_references(payment_entry_names):
	if not payment_entry_names or not has_doctype("Payment Entry Reference"):
		return {}
	rows = frappe.get_all(
		"Payment Entry Reference",
		filters={
			"parent": ["in", payment_entry_names],
			"reference_doctype": "Sales Invoice",
		},
		fields=["parent", "reference_name", "allocated_amount", "total_amount"],
		limit_page_length=0,
		order_by="idx asc",
	)
	grouped = defaultdict(list)
	for row in rows:
		grouped[row.get("parent")].append(row)
	return dict(grouped)


def _build_payment_entry_candidate(bank_transaction, payment_entry, references):
	direction = bank_transaction.get("direction")
	candidate_amount = flt(payment_entry.get("received_amount") if direction == "Inflow" else payment_entry.get("paid_amount"))
	if candidate_amount <= 0:
		candidate_amount = flt(payment_entry.get("paid_amount") or payment_entry.get("received_amount"))
	suggested_invoice = None
	if references:
		suggested_invoice = references[0].get("reference_name")
	allocated_total = sum(flt(row.get("allocated_amount") or row.get("total_amount")) for row in references or [])
	amount_difference = abs(flt(bank_transaction.get("amount")) - candidate_amount)
	amount_scenario = "Submitted Payment Entry Amount" if amount_difference <= 0.01 else "Payment Entry Amount Variance"
	if amount_difference > 0.01 and allocated_total > 0 and abs(flt(bank_transaction.get("amount")) - allocated_total) <= 0.01:
		amount_scenario = "Payment Entry Allocated Amount"

	return {
		"document_type": "Payment Entry",
		"document_name": payment_entry.get("name"),
		"suggested_document": payment_entry.get("name"),
		"suggested_sales_invoice": suggested_invoice,
		"posting_date": payment_entry.get("posting_date"),
		"customer": payment_entry.get("party") if payment_entry.get("party_type") == "Customer" else None,
		"customer_display": payment_entry.get("party"),
		"party": payment_entry.get("party"),
		"party_type": payment_entry.get("party_type") or "Customer",
		"candidate_amount": candidate_amount,
		"amount_difference": amount_difference,
		"amount_scenario": amount_scenario,
		"amount_scenario_label": get_amount_scenario_label(amount_scenario),
		"candidate_category": "payment_entry_match",
		"candidate_category_label": get_candidate_category_label("payment_entry_match"),
		"payment_event_found": 1,
		"payment_event_source": "Payment Entry",
		"payment_entry_paid_amount": candidate_amount,
		"payment_entry_allocated_amount": allocated_total,
		"payment_mode": payment_entry.get("mode_of_payment"),
		"payment_account": payment_entry.get("paid_to") if direction == "Inflow" else payment_entry.get("paid_from"),
		"reference": payment_entry.get("reference_no") or payment_entry.get("name"),
		"branch": payment_entry.get("retailedge_branch"),
		"account": payment_entry.get("paid_to") if direction == "Inflow" else payment_entry.get("paid_from"),
		"supports_partial_match": True,
		"remarks": payment_entry.get("remarks") or payment_entry.get("custom_remarks"),
		"payment_entry_invoice_context": ", ".join(row.get("reference_name") for row in references or [] if row.get("reference_name")),
		"reason": f"Payment Entry references invoices: {', '.join(row.get('reference_name') for row in references or [] if row.get('reference_name'))}."
		if references
		else "Submitted Payment Entry candidate.",
	}


def _build_matching_row(bank_transaction, candidate=None, action_status="No Match", match_reason=None):
	candidate = candidate or {}
	if cstr(candidate.get("decision_status")).strip() == "Confirmed":
		action_status = candidate.get("action_status") or "Already Confirmed"
		match_reason = match_reason or candidate.get("reason") or "Candidate already confirmed in another match."
	candidate_doctype = candidate.get("document_type")
	candidate_name = candidate.get("document_name")
	payment_reference = candidate.get("reference") or candidate.get("payment_reference")
	return {
		"bank_transaction": bank_transaction.get("bank_transaction"),
		"transaction_date": bank_transaction.get("transaction_date"),
		"bank_transaction_date": bank_transaction.get("transaction_date"),
		"bank_account": bank_transaction.get("bank_account"),
		"reference": bank_transaction.get("reference"),
		"narration": bank_transaction.get("description"),
		"amount": flt(bank_transaction.get("amount")),
		"direction": bank_transaction.get("direction"),
		"candidate_doctype": candidate_doctype,
		"candidate_name": candidate_name,
		"suggested_document_type": candidate_doctype,
		"suggested_document": candidate_name,
		"suggested_sales_invoice": candidate.get("suggested_sales_invoice"),
		"candidate_posting_date": candidate.get("posting_date"),
		"candidate_date": candidate.get("posting_date"),
		"payment_entry_posting_date": candidate.get("posting_date") if candidate_doctype == "Payment Entry" else None,
		"sales_invoice_posting_date": candidate.get("posting_date") if candidate_doctype == "Sales Invoice" else None,
		"customer": candidate.get("customer_display") or candidate.get("customer") or bank_transaction.get("party"),
		"party": candidate.get("party") or bank_transaction.get("party"),
		"party_type": candidate.get("party_type") or bank_transaction.get("party_type") or "Customer",
		"candidate_amount": flt(candidate.get("candidate_amount")),
		"amount_difference": flt(candidate.get("amount_difference")),
		"match_confidence": candidate.get("confidence") or "No Match",
		"match_score": _normalize_auto_match_score(candidate.get("score"), default=0),
		"match_reason": match_reason or candidate.get("reason") or "No candidate reached the minimum matching confidence.",
		"candidate_category": candidate.get("candidate_category"),
		"candidate_category_label": candidate.get("candidate_category_label")
		or get_candidate_category_label(candidate.get("candidate_category")),
		"payment_event_found": cint(candidate.get("payment_event_found")),
		"payment_event_source": candidate.get("payment_event_source"),
		"payment_reference": payment_reference,
		"payment_row_index": candidate.get("payment_row_index"),
		"payment_row_amount": flt(candidate.get("payment_row_amount")),
		"mode_of_payment": candidate.get("payment_mode"),
		"payment_mode": candidate.get("payment_mode"),
		"payment_account": candidate.get("payment_account"),
		"payment_category": candidate.get("payment_category"),
		"amount_scenario": candidate.get("amount_scenario"),
		"amount_scenario_label": candidate.get("amount_scenario_label") or get_amount_scenario_label(candidate.get("amount_scenario")),
		"sales_invoice_outstanding_amount": flt(candidate.get("sales_invoice_outstanding_amount")),
		"sales_invoice_grand_total": flt(candidate.get("sales_invoice_grand_total")),
		"payment_entry_paid_amount": flt(candidate.get("payment_entry_paid_amount")),
		"payment_entry_allocated_amount": flt(candidate.get("payment_entry_allocated_amount")),
		"payment_entry_invoice_context": candidate.get("payment_entry_invoice_context"),
		"multi_invoice_references": ", ".join(candidate.get("multi_invoice_references") or [])
		if isinstance(candidate.get("multi_invoice_references"), list)
		else candidate.get("multi_invoice_references"),
		"exception_only": cint(candidate.get("exception_only")),
		"exception_type": candidate.get("exception_type"),
		"branch": bank_transaction.get("branch") or candidate.get("branch"),
		"action_status": action_status,
		"action": "Review" if bank_transaction.get("bank_transaction") else "",
		"decision_status": candidate.get("decision_status"),
		"decision_note": candidate.get("decision_note"),
		"last_action": candidate.get("last_action"),
		"match_record": None,
		"reference_match_exact": cint(candidate.get("reference_match_exact")),
		"reference_match_strength": candidate.get("reference_match_strength"),
		"account_match": cint(candidate.get("account_match")),
		"account_match_available": cint(candidate.get("account_match_available")),
		"branch_match": cint(candidate.get("branch_match")),
		"branch_match_available": cint(candidate.get("branch_match_available")),
		"date_difference_days": candidate.get("date_difference_days"),
		"date_exact": cint(candidate.get("date_exact")),
		"date_in_normal_window": cint(candidate.get("date_in_normal_window")),
		"auto_match_status": "",
		"auto_match_reason": "",
		"auto_match_category": "",
		"eligible_for_auto_prepare": 0,
		"eligible_for_auto_confirm": 0,
	}


def _derive_action_status(bank_transaction, candidate):
	if bank_transaction.get("is_reconciled"):
		return "Already Reconciled"
	if bank_transaction.get("direction") != "Inflow":
		return "Outflow / Not Sales Receipt"
	if not candidate:
		return "No Match"
	if candidate.get("exception_only"):
		return "Exception Only"
	category_key = normalize_candidate_category_key(candidate.get("candidate_category"))
	if category_key in {"invoice_context_only", "weak_invoice_total_similarity"}:
		return "Informational Only"
	if candidate.get("document_type") == "Sales Invoice" and cstr(candidate.get("payment_verification_status")).strip() == "Bank Verified":
		return "Already Bank Verified"
	if candidate.get("confidence") == "Strong Match":
		return "Suggested"
	if candidate.get("confidence") == "Possible Match":
		return "Suggested"
	if candidate.get("confidence") == "Weak Match":
		return "Needs Review"
	return "No Match"


def _candidate_account_matches_bank_transaction(bank_transaction, candidate):
	return _resolve_account_match_payload(bank_transaction, candidate).get("matched") is True


def _get_bank_transaction_rows(filters, limit, limit_start=0):
	field_map = get_bank_transaction_field_map()
	fields = ["name"]
	for canonical in (
		"bank_account",
		"company",
		"transaction_date",
		"deposit",
		"withdrawal",
		"currency",
		"description",
		"reference_number",
		"transaction_id",
		"party_type",
		"party",
		"status",
		"allocated_amount",
		"unallocated_amount",
		"retailedge_branch",
	):
		fieldname = field_map.get(canonical)
		if fieldname and fieldname not in fields:
			fields.append(fieldname)

	filters_payload = {}
	date_field = field_map.get("transaction_date")
	if filters.get("company") and field_map.get("company"):
		filters_payload[field_map["company"]] = filters.get("company")
	if filters.get("bank_account") and field_map.get("bank_account"):
		filters_payload[field_map["bank_account"]] = filters.get("bank_account")
	if filters.get("transaction_status") and field_map.get("status"):
		filters_payload[field_map["status"]] = filters.get("transaction_status")
	if filters.get("branch") and field_map.get("retailedge_branch"):
		filters_payload[field_map["retailedge_branch"]] = filters.get("branch")
	if filters.get("from_date") and filters.get("to_date") and date_field:
		filters_payload[date_field] = ["between", [filters.get("from_date"), filters.get("to_date")]]

	keyword = cstr(filters.get("reference_search") or filters.get("keyword") or filters.get("search") or "").strip()
	or_filters = []
	if keyword:
		like_keyword = f"%{keyword}%"
		for canonical in ("reference_number", "description", "transaction_id", "party"):
			fieldname = field_map.get(canonical)
			if fieldname:
				or_filters.append([fieldname, "like", like_keyword])
		or_filters.append(["name", "like", like_keyword])

	order_by = f"{date_field or 'modified'} desc, modified desc"
	return frappe.get_all(
		"Bank Transaction",
		filters=filters_payload,
		or_filters=or_filters or None,
		fields=fields,
		limit_page_length=limit,
		limit_start=limit_start,
		order_by=order_by,
	)


def _coerce_matching_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_unmatched", 1)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_verified_invoices", 0)
	filters.setdefault("include_confirmed_matches", 0)
	filters.setdefault("include_rejected_candidates", 0)
	filters.setdefault("include_exception_candidates", 0)
	filters.setdefault("review_queue_status", "Open Suggestions Only")
	if cstr(filters.get("review_queue_status")).strip() in {"Confirmed", "All"}:
		filters["include_confirmed_matches"] = 1
	if cstr(filters.get("review_queue_status")).strip() in {"Rejected", "All"}:
		filters["include_rejected_candidates"] = 1
	for fieldname in (
		"only_unmatched",
		"include_reconciled",
		"include_verified_invoices",
		"include_confirmed_matches",
		"include_rejected_candidates",
		"include_exception_candidates",
	):
		filters[fieldname] = 1 if _as_bool(filters.get(fieldname)) else 0
	return filters


def _first_existing_sales_invoice_branch_field():
	for fieldname in ("retailedge_branch", "branch"):
		if has_field("Sales Invoice", fieldname):
			return fieldname
	return None


def _date_range_filter(base_date, window_days):
	if not base_date:
		return None
	base = getdate(base_date)
	return [
		"between",
		[
			str(frappe.utils.add_days(base, -cint(window_days or 0))),
			str(frappe.utils.add_days(base, cint(window_days or 0))),
		],
	]


def _candidate_search_date_window(filters, settings):
	if cint((filters or {}).get("include_exception_candidates")):
		return cint((filters or {}).get("exception_date_window_days") or settings.get("exception_date_window_days") or 400)
	return cint((filters or {}).get("date_window_days") or settings.get("date_window_days") or 3)


def _get_bank_account_match_tokens(bank_account):
	tokens = set()
	normalized_name = normalize_statement_text(bank_account)
	if normalized_name:
		tokens.add(normalized_name)
	resolved_account = _resolve_bank_account_to_ledger_account(bank_account)
	if resolved_account:
		normalized_account = normalize_statement_text(resolved_account)
		if normalized_account:
			tokens.add(normalized_account)
	if not bank_account or not has_doctype("Bank Account"):
		return tokens
	try:
		account_field = "account" if has_field("Bank Account", "account") else None
		if account_field:
			account_name = frappe.db.get_value("Bank Account", bank_account, account_field)
			normalized_account = normalize_statement_text(account_name)
			if normalized_account:
				tokens.add(normalized_account)
	except Exception:
		pass
	return tokens


def _resolve_bank_account_to_ledger_account(bank_account):
	if not bank_account:
		return None
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	cache = (context or {}).get("bank_account_ledger_cache")
	if cache is not None and bank_account in cache:
		return cache.get(bank_account)
	if has_doctype("Account"):
		try:
			if frappe.db.exists("Account", bank_account):
				if cache is not None:
					cache[bank_account] = bank_account
				return bank_account
		except Exception:
			pass
	if not has_doctype("Bank Account"):
		return None
	try:
		account_field = "account" if has_field("Bank Account", "account") else None
		if account_field:
			result = frappe.db.get_value("Bank Account", bank_account, account_field)
			if cache is not None:
				cache[bank_account] = result
			return result
	except Exception:
		if cache is not None:
			cache[bank_account] = None
		return None
	if cache is not None:
		cache[bank_account] = None
	return None


def _resolve_mode_of_payment_default_account(mode_of_payment, company=None):
	mode_of_payment = cstr(mode_of_payment).strip()
	cache_key = (mode_of_payment, cstr(company).strip())
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	cache = (context or {}).get("mode_of_payment_account_cache")
	if cache is not None and cache_key in cache:
		return cache.get(cache_key)
	if not mode_of_payment or not has_doctype("Mode of Payment Account"):
		return None
	fieldname = None
	if has_field("Mode of Payment Account", "default_account"):
		fieldname = "default_account"
	elif has_field("Mode of Payment Account", "account"):
		fieldname = "account"
	if not fieldname:
		return None
	filters = {"parent": mode_of_payment}
	if company and has_field("Mode of Payment Account", "company"):
		filters["company"] = company
	try:
		rows = frappe.get_all(
			"Mode of Payment Account",
			filters=filters,
			fields=[fieldname],
			limit_page_length=1,
		)
		if not rows and filters.get("company"):
			rows = frappe.get_all(
				"Mode of Payment Account",
				filters={"parent": mode_of_payment},
				fields=[fieldname],
				limit_page_length=1,
			)
		source = rows[0] if rows else {}
		result = cstr(source.get(fieldname)).strip() or None
		if cache is not None:
			cache[cache_key] = result
		return result
	except Exception:
		if cache is not None:
			cache[cache_key] = None
		return None


def _guess_bank_transaction_mode_of_payment(bank_transaction):
	bank_transaction = bank_transaction or {}
	for fieldname in ("mode_of_payment", "payment_method"):
		value = cstr(bank_transaction.get(fieldname)).strip()
		if value:
			return value
	account_name = cstr(bank_transaction.get("bank_account")).strip()
	if " - " in account_name:
		return account_name.split(" - ", 1)[0].strip()
	return None


def _resolve_bank_transaction_canonical_account(bank_transaction):
	bank_transaction = bank_transaction or {}
	for fieldname in ("ledger_account", "account", "payment_account"):
		value = cstr(bank_transaction.get(fieldname)).strip()
		if value:
			return {
				"canonical_account": value,
				"display_account": cstr(bank_transaction.get("bank_account") or value).strip(),
				"resolution_source": fieldname,
				"resolved": True,
			}
	account_name = cstr(bank_transaction.get("bank_account")).strip()
	resolved = cstr(_resolve_bank_account_to_ledger_account(account_name)).strip()
	if resolved:
		return {
			"canonical_account": resolved,
			"display_account": account_name or resolved,
			"resolution_source": "bank_account_mapping",
			"resolved": True,
		}
	mode_of_payment = _guess_bank_transaction_mode_of_payment(bank_transaction)
	mapped_account = cstr(
		_resolve_mode_of_payment_default_account(mode_of_payment, company=bank_transaction.get("company"))
	).strip()
	if mapped_account:
		return {
			"canonical_account": mapped_account,
			"display_account": account_name or mode_of_payment or mapped_account,
			"resolution_source": "mode_of_payment_mapping",
			"resolved": True,
		}
	return {
		"canonical_account": None,
		"display_account": account_name,
		"resolution_source": "unresolved",
		"resolved": False,
	}


def _resolve_candidate_canonical_account(candidate):
	candidate = candidate or {}
	for fieldname in ("account", "payment_account", "expected_bank_account"):
		value = cstr(candidate.get(fieldname)).strip()
		if value:
			return {
				"canonical_account": value,
				"display_account": cstr(candidate.get("payment_account") or candidate.get("account") or candidate.get("bank_account") or value).strip(),
				"resolution_source": fieldname,
				"resolved": True,
			}
	account_name = cstr(candidate.get("bank_account")).strip()
	resolved = cstr(_resolve_bank_account_to_ledger_account(account_name)).strip()
	if resolved:
		return {
			"canonical_account": resolved,
			"display_account": account_name or resolved,
			"resolution_source": "bank_account_mapping",
			"resolved": True,
		}
	return {
		"canonical_account": None,
		"display_account": cstr(candidate.get("payment_account") or candidate.get("account") or account_name).strip(),
		"resolution_source": "unresolved",
		"resolved": False,
	}


def _resolve_account_match_payload(bank_transaction, candidate):
	bank_payload = _resolve_bank_transaction_canonical_account(bank_transaction)
	candidate_payload = _resolve_candidate_canonical_account(candidate)
	bank_account = cstr(bank_payload.get("canonical_account")).strip()
	candidate_account = cstr(candidate_payload.get("canonical_account")).strip()
	raw_bank_account = cstr(bank_payload.get("display_account")).strip()
	raw_candidate_account = cstr(candidate_payload.get("display_account")).strip()
	if bank_account and candidate_account:
		if bank_account == candidate_account:
			via_mapping = bool(raw_bank_account and raw_candidate_account and raw_bank_account != raw_candidate_account)
			reason = (
				f"Bank Transaction account {raw_bank_account} resolves to {bank_account}."
				if via_mapping and raw_bank_account and bank_account
				else "Bank transaction account resolves to the same ledger account as the payment."
			)
			return {
				"status": "match_via_mapping" if via_mapping else "match",
				"matched": True,
				"available": True,
				"reason": reason,
				"bank_canonical_account": bank_account,
				"candidate_canonical_account": candidate_account,
			}
		return {
			"status": "mismatch",
			"matched": False,
			"available": True,
			"reason": "Bank transaction resolved account differs from payment account.",
			"bank_canonical_account": bank_account,
			"candidate_canonical_account": candidate_account,
		}
	return {
		"status": "unresolved",
		"matched": False,
		"available": False,
		"reason": "Could not resolve bank/payment account mapping; manual review required.",
		"bank_canonical_account": bank_account or None,
		"candidate_canonical_account": candidate_account or None,
	}


def _date_difference_days(left, right):
	if not left or not right:
		return None
	return abs((getdate(left) - getdate(right)).days)


def _same_accounting_period(left, right):
	if not left or not right:
		return True
	left_date = getdate(left)
	right_date = getdate(right)
	return left_date.year == right_date.year and left_date.month == right_date.month


def _candidate_account_is_known(candidate):
	return bool(cstr((candidate or {}).get("account") or (candidate or {}).get("expected_bank_account") or (candidate or {}).get("bank_account")).strip())


def _apply_exception_classification(bank_transaction, candidate, filters, settings):
	if not candidate:
		return candidate
	normal_window = cint((filters or {}).get("date_window_days") or settings.get("date_window_days") or 3)
	date_gap = _date_difference_days(bank_transaction.get("transaction_date"), candidate.get("posting_date"))
	date_mismatch = date_gap is not None and date_gap > normal_window
	period_mismatch = date_mismatch and not _same_accounting_period(bank_transaction.get("transaction_date"), candidate.get("posting_date"))
	account_payload = _resolve_account_match_payload(bank_transaction, candidate)
	candidate["account_resolution_status"] = account_payload.get("status")
	candidate["account_resolution_reason"] = account_payload.get("reason")
	candidate["bank_canonical_account"] = account_payload.get("bank_canonical_account")
	candidate["candidate_canonical_account"] = account_payload.get("candidate_canonical_account")
	account_mismatch = account_payload.get("status") == "mismatch"
	account_unresolved = account_payload.get("status") == "unresolved"
	if not (date_mismatch or account_mismatch or account_unresolved):
		return candidate

	if date_mismatch and account_mismatch:
		exception_type = "Date + Account Mismatch"
	elif date_mismatch and account_unresolved:
		exception_type = "Date + Account Unresolved"
	elif account_mismatch:
		exception_type = "Account Mismatch"
	elif account_unresolved:
		exception_type = "Account Unresolved"
	elif period_mismatch:
		exception_type = "Period Mismatch"
	else:
		exception_type = "Date Mismatch"

	reasons = []
	if date_mismatch:
		reasons.append(
			f"Bank Transaction date is {bank_transaction.get('transaction_date')} but {candidate.get('document_type')} date is {candidate.get('posting_date')}. This is outside the normal matching window."
		)
	if period_mismatch:
		reasons.append("The bank transaction and suggested document are in different accounting periods.")
	if account_mismatch:
		reasons.append(account_payload.get("reason") or "Bank transaction resolved account differs from payment account.")
	elif account_unresolved:
		reasons.append(account_payload.get("reason") or "Could not resolve bank/payment account mapping; manual review required.")
	reasons.append("Exception candidates are for investigation only and cannot be confirmed in this phase.")

	candidate["exception_only"] = 1
	candidate["exception_type"] = exception_type
	candidate["amount_scenario"] = exception_type
	candidate["amount_scenario_label"] = get_amount_scenario_label(exception_type)
	candidate["reason"] = " ".join(reason for reason in reasons if reason)
	return candidate


def _candidate_account_label(candidate):
	for fieldname in ("account", "expected_bank_account", "bank_account"):
		value = cstr((candidate or {}).get(fieldname)).strip()
		if value:
			return value
	return "not available"


def _get_value(row, fieldname):
	if not fieldname:
		return None
	if isinstance(row, dict):
		return row.get(fieldname)
	return getattr(row, fieldname, None)


def _row_value(row, fieldname):
	if not fieldname:
		return None
	return row.get(fieldname) if isinstance(row, dict) else getattr(row, fieldname, None)


def _dedupe_named_rows(rows):
	seen = {}
	for row in rows:
		name = cstr((row or {}).get("name")).strip()
		if name and name not in seen:
			seen[name] = row
	return list(seen.values())


def _as_bool(value):
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "y"}
	return bool(value)


def _review_queue_status_mode(filters):
	mode = cstr((filters or {}).get("review_queue_status") or "Open Suggestions Only").strip()
	return mode or "Open Suggestions Only"


def _is_released_review_status(status):
	return cstr(status).strip() in RELEASED_REVIEW_MATCH_STATUSES


def _is_active_review_status(status):
	status = cstr(status).strip()
	return bool(status) and not _is_released_review_status(status)


def _first_active_review_match(matches, include_confirmed=True):
	for match_row in matches or []:
		status = cstr(match_row.get("decision_status")).strip()
		if not _is_active_review_status(status):
			continue
		if not include_confirmed and status == "Confirmed":
			continue
		return match_row
	return None


def _active_review_match_for_candidate(document_type, document_name):
	document_name = cstr(document_name).strip()
	document_type = cstr(document_type).strip()
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	active_map = (context or {}).get("active_review_by_candidate")
	if active_map is not None and (document_type, document_name) in active_map:
		return active_map.get((document_type, document_name))
	if active_map is not None and document_type in {"Sales Invoice", "Payment Entry"}:
		return None
	if not document_name or document_type not in {"Sales Invoice", "Payment Entry"} or not has_doctype("RetailEdge Bank Transaction Match"):
		return None
	status_filter = ["not in", sorted(RELEASED_REVIEW_MATCH_STATUSES)]
	filters = {
		"suggested_document_type": document_type,
		"suggested_document": document_name,
		"decision_status": status_filter,
	}
	fields = ["name", "bank_transaction", "suggested_document_type", "suggested_document", "sales_invoice", "payment_entry", "decision_status", "decision_note", "last_action", "candidate_amount", "modified"]
	rows = frappe.get_all("RetailEdge Bank Transaction Match", filters=filters, fields=fields, limit_page_length=1, order_by="modified desc")
	if rows:
		return rows[0]
	if document_type == "Sales Invoice":
		rows = frappe.get_all("RetailEdge Bank Transaction Match", filters={"sales_invoice": document_name, "decision_status": status_filter}, fields=fields, limit_page_length=1, order_by="modified desc")
	elif document_type == "Payment Entry":
		rows = frappe.get_all("RetailEdge Bank Transaction Match", filters={"payment_entry": document_name, "decision_status": status_filter}, fields=fields, limit_page_length=1, order_by="modified desc")
	else:
		rows = []
	return rows[0] if rows else None


def _looks_like_invoice_reference(text):
	normalized = normalize_statement_text(text)
	return any(token in normalized for token in ("INV", "SINV", "SI"))


def _get_existing_matches_by_bank_transaction(bank_transactions):
	if not bank_transactions or not has_doctype("RetailEdge Bank Transaction Match"):
		return {}

	match_rows = frappe.get_all(
		"RetailEdge Bank Transaction Match",
		filters={"bank_transaction": ["in", bank_transactions]},
		fields=[
			"name",
			"bank_transaction",
			"suggested_document_type",
			"suggested_document",
			"sales_invoice",
			"payment_entry",
			"candidate_amount",
			"decision_status",
			"decision_note",
			"last_action",
			"modified",
		],
		limit_page_length=0,
		order_by="modified desc",
	)

	grouped = defaultdict(list)
	for match_row in match_rows:
		grouped[match_row.get("bank_transaction")].append(match_row)
	return dict(grouped)

def _select_candidate_for_queue(candidates, matches, filters):
	include_rejected = cint(filters.get("include_rejected_candidates") or 0)
	include_confirmed = cint(filters.get("include_confirmed_matches") or 0)
	preferred_statuses = {"Needs Review", "Reopened", "Suggested"}
	fallback = None
	ordered_candidates = sorted(candidates or [], key=_queue_candidate_rank, reverse=True)

	for candidate in ordered_candidates:
		match_row = _find_match_for_candidate(candidate, matches)
		status = cstr((match_row or {}).get("decision_status")).strip()
		if status == "Confirmed":
			if include_confirmed:
				return candidate, match_row
			continue
		if status == "Rejected" and not include_rejected:
			continue
		if status in preferred_statuses:
			return candidate, match_row
		if fallback is None:
			fallback = (candidate, match_row)

	return fallback or (None, None)


def _find_match_for_candidate(candidate, matches):
	if not candidate:
		return None
	suggested_document = cstr(candidate.get("document_name")).strip()
	suggested_document_type = cstr(candidate.get("document_type")).strip()
	suggested_sales_invoice = cstr(candidate.get("suggested_sales_invoice")).strip()
	for match_row in matches or []:
		if (
			suggested_document
			and cstr(match_row.get("suggested_document")).strip() == suggested_document
			and cstr(match_row.get("suggested_document_type")).strip() == suggested_document_type
		):
			return match_row
	for match_row in matches or []:
		if suggested_sales_invoice and cstr(match_row.get("sales_invoice")).strip() == suggested_sales_invoice:
			return match_row
	return None

def _find_candidate_for_match_row(candidates, match_row):
	match_row = match_row or {}
	suggested_document = cstr(match_row.get("suggested_document")).strip()
	suggested_document_type = cstr(match_row.get("suggested_document_type")).strip()
	sales_invoice = cstr(match_row.get("sales_invoice")).strip()
	for candidate in candidates or []:
		if (
			suggested_document
			and cstr(candidate.get("document_name")).strip() == suggested_document
			and cstr(candidate.get("document_type")).strip() == suggested_document_type
		):
			return candidate
	for candidate in candidates or []:
		if sales_invoice and cstr(candidate.get("suggested_sales_invoice")).strip() == sales_invoice:
			return candidate
	return None


def _first_match_with_status(matches, status):
	for match_row in matches or []:
		if cstr(match_row.get("decision_status")).strip() == status:
			return match_row
	return None


def _apply_selected_match_to_row(row, selected_match, include_confirmed=False):
	if not row or not selected_match:
		return
	row["match_record"] = selected_match.get("name")
	row["decision_status"] = selected_match.get("decision_status")
	row["decision_note"] = selected_match.get("decision_note")
	row["last_action"] = selected_match.get("last_action")
	if flt(selected_match.get("candidate_amount")) and not flt(row.get("candidate_amount")):
		row["candidate_amount"] = flt(selected_match.get("candidate_amount"))
		row["amount_difference"] = flt(row.get("amount")) - flt(row.get("candidate_amount"))
	status = cstr(selected_match.get("decision_status")).strip()
	if not status or status == "Draft":
		return
	if status == "Confirmed" and include_confirmed:
		row["action_status"] = "Already Confirmed"
		if row.get("exception_type"):
			row["exception_type"] = f"{row.get('exception_type')} (Already Confirmed)"
	else:
		row["action_status"] = status
	if status == "Rejected":
		row["match_reason"] = (row.get("match_reason") or "") + ("; " if row.get("match_reason") else "") + "Previously rejected match pair."


def _pick_existing_match_for_row(row, matches):
	if not matches:
		return None
	suggested_document = cstr(row.get("suggested_document")).strip()
	suggested_document_type = cstr(row.get("suggested_document_type")).strip()
	suggested_sales_invoice = cstr(row.get("suggested_sales_invoice")).strip()
	for match_row in matches:
		if (
			suggested_document
			and cstr(match_row.get("suggested_document")).strip() == suggested_document
			and cstr(match_row.get("suggested_document_type")).strip() == suggested_document_type
		):
			return match_row
	for match_row in matches:
		if suggested_sales_invoice and cstr(match_row.get("sales_invoice")).strip() == suggested_sales_invoice:
			return match_row
	return matches[0]

CANDIDATE_CATEGORY_LABELS.update(
	{
		"grouped_payment_event_match": "Grouped Payment Event Match",
		"multi_payment_bank_transaction_candidate": "Multi-Payment Bank Transaction Candidate",
	}
)



def _reference_contains(haystack, needle):
	return bool(haystack and needle and needle in haystack)



def _reference_match_payload(bank_transaction, candidate):
	bank_reference = cstr(bank_transaction.get("reference")).strip()
	bank_description = cstr(bank_transaction.get("description")).strip()
	bank_text = " ".join(part for part in (bank_reference, bank_description) if part)
	bank_reference_normalized = normalize_statement_reference(reference=bank_reference) if bank_reference else ""
	bank_text_normalized = normalize_statement_text(bank_text)
	bank_text_reference = normalize_statement_reference(reference=bank_text) if bank_text else ""
	candidate_reference = cstr(candidate.get("reference")).strip()
	candidate_reference_normalized = normalize_statement_reference(reference=candidate_reference) if candidate_reference else ""
	candidate_name = cstr(candidate.get("document_name")).strip()
	candidate_name_normalized = normalize_statement_text(candidate_name)
	candidate_name_reference = normalize_statement_reference(reference=candidate_name) if candidate_name else ""
	suggested_invoice = cstr(candidate.get("suggested_sales_invoice")).strip()
	suggested_invoice_normalized = normalize_statement_text(suggested_invoice) if suggested_invoice else ""
	suggested_invoice_reference = normalize_statement_reference(reference=suggested_invoice) if suggested_invoice else ""
	customer_normalized = normalize_statement_text(cstr(candidate.get("customer") or candidate.get("party")).strip())

	if candidate_name_normalized and _reference_contains(bank_text_normalized, candidate_name_normalized):
		return {
			"score": 30,
			"reason": "Bank narration/reference contains the suggested document name.",
			"reference_match_exact": 1,
			"reference_match_strength": "strong",
		}
	if suggested_invoice_normalized and _reference_contains(bank_text_normalized, suggested_invoice_normalized):
		return {
			"score": 30,
			"reason": "Bank narration/reference contains the Sales Invoice name.",
			"reference_match_exact": 1,
			"reference_match_strength": "strong",
		}
	if candidate_reference_normalized and bank_reference_normalized and candidate_reference_normalized == bank_reference_normalized:
		return {
			"score": 25,
			"reason": "Normalized reference matches exactly.",
			"reference_match_exact": 1,
			"reference_match_strength": "exact",
		}
	if candidate_reference_normalized and _reference_contains(bank_text_normalized, candidate_reference_normalized):
		return {
			"score": 20,
			"reason": "Bank narration/reference contains the payment reference.",
			"reference_match_exact": 0,
			"reference_match_strength": "contains",
		}
	if bank_reference_normalized and _reference_contains(normalize_statement_text(candidate_reference), bank_reference_normalized):
		return {
			"score": 20,
			"reason": "Payment reference/remarks contains the bank reference.",
			"reference_match_exact": 0,
			"reference_match_strength": "contains",
		}
	if suggested_invoice_reference and _reference_contains(bank_text_reference, suggested_invoice_reference):
		return {
			"score": 18,
			"reason": "Bank narration/reference contains the Sales Invoice reference.",
			"reference_match_exact": 0,
			"reference_match_strength": "narration_contains_reference",
		}
	if candidate_name_reference and _reference_contains(bank_text_reference, candidate_name_reference):
		return {
			"score": 18,
			"reason": "Bank narration/reference contains the suggested document reference.",
			"reference_match_exact": 0,
			"reference_match_strength": "narration_contains_reference",
		}
	if customer_normalized and _reference_contains(bank_text_normalized, customer_normalized):
		return {
			"score": 8,
			"reason": "Customer or party name appears in the bank narration.",
			"reference_match_exact": 0,
			"reference_match_strength": "weak",
		}
	return {
		"score": 0,
		"reason": "No strong reference match found.",
		"reference_match_exact": 0,
		"reference_match_strength": "none",
	}


def score_bank_transaction_candidate(bank_transaction, candidate):
	context = getattr(frappe.local, "_retailedge_bank_match_context", None)
	settings = (context or {}).get("settings") or get_bank_transaction_matching_settings()
	tolerance = flt(settings.get("amount_tolerance"))
	score = 0
	reasons = []
	bank_amount = flt(bank_transaction.get("amount"))
	candidate_amount = flt(candidate.get("candidate_amount"))
	amount_difference = abs(bank_amount - candidate_amount)

	if amount_difference <= 0.01:
		score += 35
		reasons.append(candidate.get("reason") or "Exact amount match.")
	elif amount_difference <= tolerance:
		score += 25
		reasons.append(candidate.get("reason") or "Amount is within the configured tolerance.")
	elif candidate.get("supports_partial_match") and min(bank_amount, candidate_amount) > 0:
		score += 15
		reasons.append(candidate.get("reason") or "Amount suggests a possible partial or allocated match.")
	else:
		score -= 25
		reasons.append(candidate.get("reason") or "Amount is materially different.")

	reference_payload = _reference_match_payload(bank_transaction, candidate)
	score += cint(reference_payload.get("score") or 0)
	if reference_payload.get("reason") and reference_payload.get("score"):
		reasons.append(reference_payload.get("reason"))

	bank_date = bank_transaction.get("transaction_date")
	candidate_date = candidate.get("posting_date")
	date_difference = _date_difference_days(bank_date, candidate_date)
	if date_difference == 0:
		score += 10
		reasons.append("Transaction date matches exactly.")
	elif date_difference is not None and date_difference <= cint(settings.get("date_window_days") or 3):
		score += 5
		reasons.append("Transaction date is within the matching window.")

	if candidate.get("account_resolution_status"):
		account_payload = {
			"status": candidate.get("account_resolution_status"),
			"matched": candidate.get("account_resolution_status") in {"match", "match_via_mapping"},
			"available": bool(candidate.get("bank_canonical_account") or candidate.get("candidate_canonical_account")),
			"reason": candidate.get("account_resolution_reason"),
			"bank_canonical_account": candidate.get("bank_canonical_account"),
			"candidate_canonical_account": candidate.get("candidate_canonical_account"),
		}
	else:
		account_payload = _resolve_account_match_payload(bank_transaction, candidate)
	account_match = account_payload.get("matched") is True
	account_match_available = 1 if account_payload.get("available") else 0
	if account_match:
		score += 10
		reasons.append(account_payload.get("reason") or "Bank account or expected account aligns with the transaction.")

	branch_match = bool(bank_transaction.get("branch") and candidate.get("branch") and bank_transaction.get("branch") == candidate.get("branch"))
	branch_match_available = 1 if bank_transaction.get("branch") and candidate.get("branch") else 0
	if branch_match:
		score += 5
		reasons.append("RetailEdge branch attribution matches.")

	if candidate.get("document_type") == "Sales Invoice" and cstr(candidate.get("payment_verification_status")).strip() == "Bank Verified":
		score -= 30
		reasons.append("Sales Invoice is already marked Bank Verified.")

	if bank_transaction.get("direction") == "Outflow" and candidate.get("document_type") == "Sales Invoice":
		score -= 60
		reasons.append("Outflow transactions are not treated as customer sales receipts.")

	category_key = normalize_candidate_category_key(candidate.get("candidate_category"))
	if category_key == "payment_entry_match":
		score += 20
		reasons.append("Matched submitted Payment Entry.")
	elif category_key in {"invoice_payment_row_match", "pos_payment_match"}:
		score += 15
		reasons.append("Matched POS payment row." if category_key == "pos_payment_match" else "Matched invoice payment row.")
	elif category_key == "invoice_context_only":
		score = min(score, cint(settings.get("strong_match_score") or 80) - 1)
		reasons.append("Sales Invoice is context only; payment event evidence is required for auto-match.")
	elif category_key == "weak_invoice_total_similarity":
		score = min(score, 45)
		reasons.append("Invoice total matched, but no matching payment event was found.")
	elif category_key in {"grouped_payment_event_match", "multi_payment_bank_transaction_candidate"}:
		score = min(score, cint(settings.get("strong_match_score") or 80) - 1)
		reasons.append("Grouped or multi-payment candidates require manual review in this phase.")

	if amount_scenario_requires_manual_review(candidate.get("amount_scenario")):
		score = min(score, cint(settings.get("strong_match_score") or 80) - 1)
		reasons.append(f"{get_amount_scenario_label(candidate.get('amount_scenario'))} requires manual review.")

	if score >= cint(settings.get("strong_match_score") or 80):
		confidence = "Strong Match"
	elif score >= cint(settings.get("minimum_possible_score") or 50):
		confidence = "Possible Match"
	elif score >= 30:
		confidence = "Weak Match"
	else:
		confidence = "No Match"

	return {
		"score": score,
		"confidence": confidence,
		"reasons": reasons,
		"reference_match_exact": cint(reference_payload.get("reference_match_exact") or 0),
		"reference_match_strength": reference_payload.get("reference_match_strength") or "none",
		"date_difference_days": date_difference,
		"date_exact": 1 if date_difference == 0 else 0,
		"date_in_normal_window": 1 if date_difference is not None and date_difference <= cint(settings.get("date_window_days") or 3) else 0,
		"account_match": 1 if account_match else 0,
		"account_match_available": account_match_available,
		"account_resolution_status": account_payload.get("status"),
		"account_resolution_reason": account_payload.get("reason"),
		"bank_canonical_account": account_payload.get("bank_canonical_account"),
		"candidate_canonical_account": account_payload.get("candidate_canonical_account"),
		"branch_match": 1 if branch_match else 0,
		"branch_match_available": branch_match_available,
	}



def _build_multi_invoice_candidates(bank_transaction, invoices, filters, settings):
	# R5.3.1 keeps grouped payment-event matching as a manual-review design foundation only.
	# We intentionally avoid forcing a misleading one-document review record until the DocType
	# can safely store multiple matched payment events in a dedicated child structure.
	return []
