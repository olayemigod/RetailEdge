from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import cint, cstr, flt, get_first_day, getdate, nowdate

from retailedge.bank_transaction_matching import (
	ACTIVE_CONFIRMED_MATCH_STATUS,
	INACTIVE_MATCH_STATUSES,
	_active_review_match_for_candidate,
	_amount_scenario_rank,
	_apply_exception_classification,
	_candidate_category_rank,
	_coerce_matching_filters,
	_first_active_review_match,
	_first_match_with_status,
	_get_bank_transaction_rows,
	_get_existing_matches_by_bank_transaction,
	_get_payment_entry_rows,
	_get_payment_entry_sales_invoice_references,
	_get_sales_invoice_doc,
	_get_sales_invoice_rows,
	_invoice_payment_row_is_bank_matchable,
	_is_active_review_status,
	_is_released_review_status,
	_queue_candidate_rank,
	_resolve_account_match_payload,
	_resolve_bank_transaction_canonical_account,
	_review_queue_status_mode,
	_select_candidate_for_queue,
	candidate_document_has_active_confirmed_bank_match,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	get_amount_scenario_label,
	get_bank_transaction_matching_settings,
	get_candidate_category_label,
	get_review_creation_block_reason,
	is_payment_basis_review_candidate,
	normalize_bank_transaction,
	payment_entry_has_active_confirmed_bank_match,
	sales_invoice_has_active_confirmed_bank_match,
	score_bank_transaction_candidate,
)
from retailedge.branch_context import has_doctype, has_field
from retailedge.invoice_payment_audit import classify_payment_method, get_payment_entries_for_sales_invoice, get_sales_invoice_payment_rows


READINESS_READY = "Ready for Reconciliation"
READINESS_NOT_READY = "Not Ready"
READINESS_EXCEPTION = "Exception"
READINESS_NEEDS_REVIEW = "Needs Review"
READINESS_ALREADY_RECONCILED = "Already Reconciled"


def _default_operational_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	return filters


def _report_boolean(value, default=0):
	if value is None:
		return default
	if isinstance(value, str):
		return 1 if value.strip().lower() in {"1", "true", "yes", "y"} else 0
	return 1 if value else 0


def _review_status_filters(filters):
	include_reviewed = _report_boolean(filters.get("include_already_reviewed"), 0)
	include_rejected = _report_boolean(filters.get("include_rejected"), 0)
	include_reconciled = _report_boolean(filters.get("include_reconciled"), 0)
	return include_reviewed, include_rejected, include_reconciled


def _get_review_matches_by_candidate(document_type, document_names):
	document_names = [cstr(name).strip() for name in (document_names or []) if cstr(name).strip()]
	if not document_names or document_type not in {"Sales Invoice", "Payment Entry"} or not has_doctype("RetailEdge Bank Transaction Match"):
		return {}
	fieldname = "sales_invoice" if document_type == "Sales Invoice" else "payment_entry"
	rows = frappe.get_all(
		"RetailEdge Bank Transaction Match",
		filters={fieldname: ["in", document_names]},
		fields=[
			"name",
			"bank_transaction",
			"suggested_document_type",
			"suggested_document",
			"sales_invoice",
			"payment_entry",
			"decision_status",
			"decision_note",
			"last_action",
			"candidate_amount",
			"confirmed_by",
			"confirmed_on",
			"modified",
		],
		limit_page_length=0,
		order_by="modified desc",
	)
	grouped = defaultdict(list)
	for row in rows:
		key = cstr(row.get(fieldname)).strip()
		if key:
			grouped[key].append(row)
	return dict(grouped)


def _get_bank_transaction_match_record(bank_transaction, document_type, document_name):
	bank_transaction = cstr(bank_transaction).strip()
	document_type = cstr(document_type).strip()
	document_name = cstr(document_name).strip()
	if not bank_transaction or document_type not in {"Sales Invoice", "Payment Entry"} or not document_name:
		return None
	if not has_doctype("RetailEdge Bank Transaction Match"):
		return None
	return frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": bank_transaction,
			"suggested_document_type": document_type,
			"suggested_document": document_name,
		},
		["name", "decision_status", "decision_note", "confirmed_by", "confirmed_on", "modified"],
		as_dict=True,
	)


def _candidate_count_for_bank_transaction(bank_transaction_name, filters):
	matching_filters = _coerce_matching_filters(filters)
	matching_filters["include_exception_candidates"] = 1
	candidates = []
	candidates.extend(find_payment_entry_candidates_for_bank_transaction(bank_transaction_name, filters=matching_filters, limit=50))
	candidates.extend(find_sales_invoice_candidates_for_bank_transaction(bank_transaction_name, filters=matching_filters, limit=50))
	return candidates


def _build_unmatched_bank_transaction_row(bank_transaction, matches, filters):
	candidate_filters = _coerce_matching_filters(filters)
	candidate_filters["include_exception_candidates"] = 1
	if _report_boolean(filters.get("include_rejected"), 0):
		candidate_filters["include_rejected_candidates"] = 1
	candidates = _candidate_count_for_bank_transaction(bank_transaction.get("bank_transaction"), candidate_filters)
	best_candidate, best_match = _select_candidate_for_queue(candidates, matches, candidate_filters)
	resolved_account = _resolve_bank_transaction_canonical_account(bank_transaction)
	block_reason = ""
	if best_candidate:
		block_reason = (
			get_review_creation_block_reason(best_candidate)
			or cstr(best_candidate.get("account_resolution_reason")).strip()
			or cstr(best_candidate.get("reason") or " ".join(best_candidate.get("reasons") or [])).strip()
		)
	else:
		block_reason = "No bank-matchable payment event found."
	review_status = "Open Suggestion"
	if best_match:
		review_status = cstr(best_match.get("decision_status")).strip() or "Reviewed"
	elif bank_transaction.get("is_reconciled"):
		review_status = "Already Reconciled"
	return {
		"bank_transaction": bank_transaction.get("bank_transaction"),
		"transaction_date": bank_transaction.get("transaction_date"),
		"company": bank_transaction.get("company"),
		"branch": bank_transaction.get("branch"),
		"bank_account": bank_transaction.get("bank_account"),
		"resolved_canonical_account": resolved_account.get("canonical_account"),
		"account_resolution_status": "Resolved" if resolved_account.get("resolved") else "Unresolved",
		"direction": bank_transaction.get("direction"),
		"amount": flt(bank_transaction.get("amount")),
		"reference": bank_transaction.get("reference"),
		"narration": bank_transaction.get("description"),
		"party": bank_transaction.get("party"),
		"review_status": review_status,
		"existing_match": best_match.get("name") if best_match else None,
		"suggested_candidate_count": len(candidates),
		"best_candidate": cstr((best_candidate or {}).get("document_name")).strip(),
		"best_candidate_type": cstr((best_candidate or {}).get("document_type")).strip(),
		"best_candidate_category": get_candidate_category_label((best_candidate or {}).get("candidate_category")),
		"blocked_reason": block_reason,
		"reconciliation_status": bank_transaction.get("reconciliation_status"),
		"days_outstanding": _days_since(bank_transaction.get("transaction_date")),
	}


def get_unmatched_bank_transaction_rows(filters=None, limit=500):
	filters = _default_operational_filters(filters)
	matching_filters = _coerce_matching_filters(filters)
	bank_rows = _get_bank_transaction_rows(matching_filters, min(int(limit or 500), 2000))
	existing_matches = _get_existing_matches_by_bank_transaction([row.get("name") for row in bank_rows if row.get("name")])
	include_reviewed, include_rejected, include_reconciled = _review_status_filters(filters)
	results = []
	for bank_row in bank_rows:
		bank_transaction = normalize_bank_transaction(bank_row)
		matches = existing_matches.get(bank_transaction.get("bank_transaction")) or []
		active_review = _first_active_review_match(matches)
		confirmed_match = _first_match_with_status(matches, ACTIVE_CONFIRMED_MATCH_STATUS)
		rejected_match = _first_match_with_status(matches, "Rejected")
		if bank_transaction.get("is_reconciled") and not include_reconciled:
			continue
		if confirmed_match and not include_reviewed:
			continue
		if active_review and not include_reviewed:
			continue
		if rejected_match and not include_rejected:
			# rejected exact pairs stay suppressed by default, but the transaction may still appear if another candidate exists
			pass
		if filters.get("direction") and filters.get("direction") != "All" and bank_transaction.get("direction") != filters.get("direction"):
			continue
		if filters.get("amount_from") and flt(bank_transaction.get("amount")) < flt(filters.get("amount_from")):
			continue
		if filters.get("amount_to") and flt(bank_transaction.get("amount")) > flt(filters.get("amount_to")):
			continue
		row = _build_unmatched_bank_transaction_row(bank_transaction, matches, filters)
		if filters.get("account_resolution_status"):
			expected = cstr(filters.get("account_resolution_status")).strip().lower()
			actual = cstr(row.get("account_resolution_status")).strip().lower()
			if expected and actual != expected:
				continue
		if filters.get("match_status"):
			status_text = cstr(row.get("review_status")).strip()
			if status_text != cstr(filters.get("match_status")).strip():
				continue
		results.append(row)
	return results


def _payment_entry_event_rows(filters):
	if not has_doctype("Payment Entry"):
		return []
	settings = get_bank_transaction_matching_settings()
	date_filters = _default_operational_filters(filters)
	bank_probe = {
		"company": date_filters.get("company"),
		"transaction_date": date_filters.get("to_date"),
		"direction": "Inflow",
		"amount": 0,
	}
	rows = _get_payment_entry_rows(bank_probe, date_filters, settings, limit=500)
	if filters.get("from_date") or filters.get("to_date"):
		from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
		to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None
		rows = [
			row
			for row in rows
			if (not from_date or getdate(row.get("posting_date")) >= from_date)
			and (not to_date or getdate(row.get("posting_date")) <= to_date)
		]
	references = _get_payment_entry_sales_invoice_references([row.get("name") for row in rows])
	results = []
	for payment_entry in rows:
		account = cstr(payment_entry.get("paid_to") or payment_entry.get("paid_from")).strip()
		if not account:
			continue
		event_type = "Payment Entry"
		match_record = _active_review_match_for_candidate("Payment Entry", payment_entry.get("name"))
		confirmed = payment_entry_has_active_confirmed_bank_match(payment_entry.get("name"))
		if confirmed and not _report_boolean(filters.get("include_already_matched"), 0):
			continue
		if filters.get("payment_event_type") and filters.get("payment_event_type") not in {"", "All", event_type}:
			continue
		linked_invoice = ", ".join(
			row.get("reference_name")
			for row in references.get(payment_entry.get("name")) or []
			if row.get("reference_name")
		)
		event = {
			"payment_event_type": event_type,
			"payment_event_document": payment_entry.get("name"),
			"payment_row_reference": "",
			"posting_date": payment_entry.get("posting_date"),
			"company": payment_entry.get("company"),
			"branch": payment_entry.get("retailedge_branch"),
			"party": payment_entry.get("party"),
			"customer_supplier": payment_entry.get("party"),
			"mode_of_payment": payment_entry.get("mode_of_payment"),
			"payment_account": account,
			"resolved_canonical_account": account,
			"amount": flt(payment_entry.get("received_amount") or payment_entry.get("paid_amount")),
			"reference_no": payment_entry.get("reference_no") or payment_entry.get("name"),
			"linked_sales_invoice": linked_invoice,
			"linked_payment_entry": payment_entry.get("name"),
			"existing_bank_match": match_record.get("name") if match_record else None,
			"match_status": "Confirmed" if confirmed else (cstr((match_record or {}).get("decision_status")).strip() or "Unmatched"),
			"candidate_bank_transaction": None,
			"reason_exception": "",
			"days_outstanding": _days_since(payment_entry.get("posting_date")),
			"suggested_document_type": "Payment Entry",
			"suggested_document": payment_entry.get("name"),
			"candidate_category": "payment_entry_match",
		}
		best_bank = _find_candidate_bank_transaction_for_event(event, filters)
		if best_bank:
			event["candidate_bank_transaction"] = best_bank.get("bank_transaction")
			event["reason_exception"] = best_bank.get("match_reason") or ""
		results.append(event)
	return results


def _sales_invoice_payment_event_rows(filters):
	if not has_doctype("Sales Invoice"):
		return []
	settings = get_bank_transaction_matching_settings()
	probe_transaction = {
		"company": filters.get("company"),
		"transaction_date": filters.get("to_date"),
		"amount": 0,
		"direction": "Inflow",
	}
	invoices = _get_sales_invoice_rows(probe_transaction, _coerce_matching_filters(filters), settings, limit=500)
	results = []
	for invoice in invoices:
		invoice_doc = _get_sales_invoice_doc(invoice)
		if not invoice_doc:
			continue
		if cstr(getattr(invoice_doc, "docstatus", 1)) == "2":
			continue
		try:
			payment_rows = get_sales_invoice_payment_rows(invoice_doc)
		except Exception:
			payment_rows = []
		for payment_row in payment_rows:
			if not _invoice_payment_row_is_bank_matchable(payment_row):
				continue
			payment_category = cstr(payment_row.get("payment_category")).strip()
			event_type = "POS Payment Row" if payment_category == "Card / POS" else "Invoice Payment Row"
			if filters.get("payment_event_type") and filters.get("payment_event_type") not in {"", "All", event_type}:
				continue
			if filters.get("mode_of_payment") and cstr(payment_row.get("mode_of_payment")).strip() != cstr(filters.get("mode_of_payment")).strip():
				continue
			if filters.get("payment_account") and cstr(payment_row.get("account")).strip() != cstr(filters.get("payment_account")).strip():
				continue
			match_record = _active_review_match_for_candidate("Sales Invoice", invoice.get("name"))
			confirmed = sales_invoice_has_active_confirmed_bank_match(invoice.get("name"))
			if confirmed and not _report_boolean(filters.get("include_already_matched"), 0):
				continue
			event = {
				"payment_event_type": event_type,
				"payment_event_document": invoice.get("name"),
				"payment_row_reference": payment_row.get("payment_row_index"),
				"posting_date": invoice.get("posting_date"),
				"company": invoice.get("company"),
				"branch": invoice.get("retailedge_branch") or invoice.get("branch"),
				"party": invoice.get("customer"),
				"customer_supplier": invoice.get("customer_name") or invoice.get("customer"),
				"mode_of_payment": payment_row.get("mode_of_payment"),
				"payment_account": payment_row.get("account"),
				"resolved_canonical_account": payment_row.get("account") or payment_row.get("expected_account"),
				"amount": flt(payment_row.get("base_amount") or payment_row.get("amount")),
				"reference_no": invoice.get("name"),
				"linked_sales_invoice": invoice.get("name"),
				"linked_payment_entry": _first_linked_payment_entry(invoice.get("name")),
				"existing_bank_match": match_record.get("name") if match_record else None,
				"match_status": "Confirmed" if confirmed else (cstr((match_record or {}).get("decision_status")).strip() or "Unmatched"),
				"candidate_bank_transaction": None,
				"reason_exception": "",
				"days_outstanding": _days_since(invoice.get("posting_date")),
				"suggested_document_type": "Sales Invoice",
				"suggested_document": invoice.get("name"),
				"candidate_category": "pos_payment_match" if event_type == "POS Payment Row" else "invoice_payment_row_match",
			}
			best_bank = _find_candidate_bank_transaction_for_event(event, filters)
			if best_bank:
				event["candidate_bank_transaction"] = best_bank.get("bank_transaction")
				event["reason_exception"] = best_bank.get("match_reason") or ""
			results.append(event)
	return results


def _first_linked_payment_entry(invoice_name):
	entries = get_payment_entries_for_sales_invoice(invoice_name)
	if not entries:
		return None
	return entries[0].get("payment_entry")


def _hydrate_match_candidate_context(row, details):
	suggested_document_type = cstr(row.get("suggested_document_type")).strip()
	context = {
		"candidate_category": cstr(details.get("candidate_category")).strip(),
		"payment_event_source": cstr(details.get("payment_event_source")).strip(),
		"payment_account": cstr(details.get("payment_account")).strip(),
		"payment_event_amount": flt(details.get("payment_row_amount") or details.get("payment_entry_paid_amount") or row.get("candidate_amount")),
	}
	if suggested_document_type == "Payment Entry":
		entry_name = cstr(row.get("payment_entry") or row.get("suggested_document")).strip()
		if entry_name and has_doctype("Payment Entry"):
			fields = ["paid_to", "paid_from", "received_amount", "paid_amount", "mode_of_payment", "party", "party_type"]
			if has_field("Payment Entry", "retailedge_branch"):
				fields.append("retailedge_branch")
			payload = frappe.db.get_value("Payment Entry", entry_name, fields, as_dict=True) or {}
			context["candidate_category"] = context.get("candidate_category") or "payment_entry_match"
			context["payment_event_source"] = context.get("payment_event_source") or "Payment Entry"
			context["payment_account"] = context.get("payment_account") or cstr(payload.get("paid_to") or payload.get("paid_from")).strip()
			context["payment_event_amount"] = flt(context.get("payment_event_amount") or payload.get("received_amount") or payload.get("paid_amount"))
			context["party"] = payload.get("party") or row.get("party") or row.get("customer")
			context["branch"] = payload.get("retailedge_branch") or row.get("branch")
		return context

	if suggested_document_type == "Sales Invoice":
		invoice_name = cstr(row.get("sales_invoice") or row.get("suggested_document")).strip()
		invoice_doc = _get_sales_invoice_doc({"name": invoice_name}) if invoice_name else None
		if invoice_doc:
			try:
				payment_rows = get_sales_invoice_payment_rows(invoice_doc)
			except Exception:
				payment_rows = []
			best_row = None
			best_diff = None
			for payment_row in payment_rows:
				if not _invoice_payment_row_is_bank_matchable(payment_row):
					continue
				amount = flt(payment_row.get("base_amount") or payment_row.get("amount"))
				diff = abs(amount - flt(row.get("candidate_amount")))
				if best_row is None or diff < best_diff:
					best_row = payment_row
					best_diff = diff
			if best_row:
				category = "pos_payment_match" if cstr(best_row.get("payment_category")).strip() == "Card / POS" else "invoice_payment_row_match"
				context["candidate_category"] = context.get("candidate_category") or category
				context["payment_event_source"] = context.get("payment_event_source") or ("POS Payment Row" if category == "pos_payment_match" else "Invoice Payment Row")
				context["payment_account"] = context.get("payment_account") or cstr(best_row.get("account") or best_row.get("expected_account")).strip()
				context["payment_event_amount"] = flt(context.get("payment_event_amount") or best_row.get("base_amount") or best_row.get("amount"))
				context["party"] = row.get("party") or row.get("customer") or getattr(invoice_doc, "customer", None)
		return context

	return context


def _find_candidate_bank_transaction_for_event(event_row, filters):
	bank_rows = _get_bank_transaction_rows(_coerce_matching_filters(filters), 200)
	candidate = _event_row_to_candidate(event_row)
	best_row = None
	best_payload = None
	for bank_row in bank_rows:
		normalized = normalize_bank_transaction(bank_row)
		score_payload = score_bank_transaction_candidate(normalized, candidate)
		if cint(score_payload.get("score")) < 30:
			continue
		candidate_copy = dict(candidate)
		candidate_copy.update(score_payload)
		candidate_copy["amount_scenario"] = candidate.get("amount_scenario")
		_apply_exception_classification(normalized, candidate_copy, _coerce_matching_filters(filters), get_bank_transaction_matching_settings())
		row = {
			"bank_transaction": normalized.get("bank_transaction"),
			"transaction_date": normalized.get("transaction_date"),
			"amount": normalized.get("amount"),
			"match_reason": cstr(candidate_copy.get("reason") or " ".join(candidate_copy.get("reasons") or [])).strip(),
			"score": candidate_copy.get("score"),
			"candidate": candidate_copy,
		}
		if best_row is None or _queue_candidate_rank(candidate_copy) > _queue_candidate_rank(best_payload):
			best_row = row
			best_payload = candidate_copy
	return best_row


def _event_row_to_candidate(event_row):
	category = cstr(event_row.get("candidate_category")).strip()
	document_type = cstr(event_row.get("suggested_document_type")).strip()
	return {
		"document_type": document_type,
		"document_name": event_row.get("suggested_document"),
		"suggested_sales_invoice": event_row.get("linked_sales_invoice"),
		"posting_date": event_row.get("posting_date"),
		"customer": event_row.get("party"),
		"customer_display": event_row.get("customer_supplier") or event_row.get("party"),
		"party": event_row.get("party"),
		"party_type": "Customer",
		"candidate_amount": flt(event_row.get("amount")),
		"amount_difference": 0,
		"amount_scenario": "Submitted Payment Entry Amount" if document_type == "Payment Entry" else "Exact Invoice Payment Row Amount",
		"candidate_category": category,
		"payment_event_found": 1,
		"payment_event_source": event_row.get("payment_event_type"),
		"payment_row_index": event_row.get("payment_row_reference"),
		"payment_row_amount": flt(event_row.get("amount")),
		"payment_mode": event_row.get("mode_of_payment"),
		"payment_account": event_row.get("payment_account"),
		"payment_category": event_row.get("payment_event_type"),
		"account": event_row.get("resolved_canonical_account") or event_row.get("payment_account"),
		"reference": event_row.get("reference_no"),
		"branch": event_row.get("branch"),
		"reason": "Submitted Payment Entry candidate." if document_type == "Payment Entry" else "Matched invoice payment row.",
	}


def get_unmatched_bank_payment_event_rows(filters=None, limit=500):
	filters = _default_operational_filters(filters)
	rows = _payment_entry_event_rows(filters) + _sales_invoice_payment_event_rows(filters)
	rows.sort(key=lambda row: (cstr(row.get("posting_date")), cstr(row.get("payment_event_document"))), reverse=True)
	return rows[: min(int(limit or 500), len(rows) or 500)]


def _readiness_for_match_row(match_row):
	review_status = cstr(match_row.get("decision_status")).strip()
	if review_status in {"Rejected", "Cancelled"}:
		return READINESS_NOT_READY, "Previously rejected or cancelled match."
	if review_status not in {"Confirmed", "Auto Confirmed"}:
		return READINESS_NEEDS_REVIEW, "Decision is not confirmed yet."
	if match_row.get("is_reconciled"):
		return READINESS_ALREADY_RECONCILED, "Bank Transaction already appears reconciled/settled."
	if cstr(match_row.get("candidate_category")).strip() not in {"payment_entry_match", "invoice_payment_row_match", "pos_payment_match"}:
		return READINESS_NOT_READY, "No bank-matchable payment event found."
	if abs(flt(match_row.get("amount_difference"))) > 0.01:
		return READINESS_NOT_READY, "Amount variance requires review"
	account_status = cstr(match_row.get("account_resolution_status")).strip()
	if account_status == "unresolved":
		return READINESS_EXCEPTION, "Account unresolved"
	if account_status == "mismatch":
		return READINESS_EXCEPTION, "Account mismatch"
	if cint(match_row.get("branch_match_available")) and not cint(match_row.get("branch_match")):
		return READINESS_EXCEPTION, "Branch mismatch"
	if cstr(match_row.get("amount_scenario")).strip() in {
		"Partial Payment",
		"Overpayment / Advance",
		"Amount Variance",
		"Multi-Invoice Payment",
	}:
		return READINESS_NOT_READY, f"{cstr(match_row.get('amount_scenario')).strip()} requires review"
	return READINESS_READY, "Ready for reconciliation review."


def get_bank_match_reconciliation_readiness_rows(filters=None, limit=500):
	filters = _default_operational_filters(filters)
	if not has_doctype("RetailEdge Bank Transaction Match"):
		return []
	match_rows = frappe.get_all(
		"RetailEdge Bank Transaction Match",
		filters={},
		fields=[
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
		limit_page_length=min(int(limit or 500), 2000),
		order_by="transaction_date desc, modified desc",
	)
	results = []
	for row in match_rows:
		details = _safe_load_json(row.get("details_json"))
		combined = frappe._dict(dict(row))
		combined.update(details)
		hydrated = _hydrate_match_candidate_context(row, details)
		candidate = {
			"document_type": row.get("suggested_document_type"),
			"document_name": row.get("suggested_document"),
			"candidate_category": hydrated.get("candidate_category") or details.get("candidate_category"),
			"posting_date": details.get("candidate_posting_date") or row.get("transaction_date"),
			"payment_account": hydrated.get("payment_account") or details.get("payment_account"),
			"account": hydrated.get("payment_account") or details.get("payment_account") or details.get("candidate_canonical_account"),
			"expected_bank_account": details.get("candidate_canonical_account"),
			"branch": hydrated.get("branch") or row.get("branch"),
		}
		bank_transaction = {
			"bank_account": row.get("bank_account"),
			"bank_transaction": row.get("bank_transaction"),
			"transaction_date": row.get("transaction_date"),
			"amount": row.get("bank_amount"),
			"branch": row.get("branch"),
			"company": row.get("company"),
			"direction": "Inflow",
			"is_reconciled": _report_boolean(details.get("is_reconciled"), 0),
		}
		account_payload = _resolve_account_match_payload(bank_transaction, candidate)
		combined["account_resolution_status"] = account_payload.get("status")
		combined["resolved_bank_account"] = account_payload.get("bank_canonical_account")
		combined["resolved_payment_account"] = account_payload.get("candidate_canonical_account")
		combined["candidate_category"] = hydrated.get("candidate_category") or details.get("candidate_category")
		combined["payment_event_source"] = hydrated.get("payment_event_source") or details.get("payment_event_source")
		combined["payment_event_amount"] = flt(hydrated.get("payment_event_amount") or details.get("payment_row_amount") or details.get("payment_entry_paid_amount") or row.get("candidate_amount"))
		combined["payment_account"] = hydrated.get("payment_account") or details.get("payment_account")
		combined["branch_match"] = details.get("branch_match")
		combined["branch_match_available"] = details.get("branch_match_available")
		readiness, reason = _readiness_for_match_row(combined)
		if not _report_boolean(filters.get("include_rejected_cancelled"), 0) and cstr(row.get("decision_status")).strip() in {"Rejected", "Cancelled"}:
			continue
		if not _report_boolean(filters.get("include_reconciled"), 0) and readiness == READINESS_ALREADY_RECONCILED:
			continue
		if filters.get("reconciliation_readiness_status") and cstr(filters.get("reconciliation_readiness_status")).strip() != readiness:
			continue
		results.append(
			{
				"bank_match_review": row.get("name"),
				"bank_transaction": row.get("bank_transaction"),
				"transaction_date": row.get("transaction_date"),
				"bank_amount": flt(row.get("bank_amount")),
				"bank_account": row.get("bank_account"),
				"resolved_bank_account": account_payload.get("bank_canonical_account"),
				"candidate_type": get_candidate_category_label(hydrated.get("candidate_category") or details.get("candidate_category") or row.get("suggested_document_type")),
				"suggested_document_type": row.get("suggested_document_type"),
				"suggested_document": row.get("suggested_document"),
				"payment_event_source": hydrated.get("payment_event_source") or details.get("payment_event_source"),
				"payment_event_amount": flt(hydrated.get("payment_event_amount") or details.get("payment_row_amount") or details.get("payment_entry_paid_amount") or row.get("candidate_amount")),
				"payment_account": hydrated.get("payment_account") or details.get("payment_account"),
				"resolved_payment_account": account_payload.get("candidate_canonical_account"),
				"party": row.get("party") or row.get("customer"),
				"branch": row.get("branch"),
				"match_confidence": row.get("match_confidence"),
				"match_score": cint(row.get("match_score") or 0),
				"amount_scenario": get_amount_scenario_label(row.get("amount_scenario")),
				"account_resolution_status": account_payload.get("status"),
				"review_status": row.get("decision_status"),
				"action_status": details.get("action_status") or row.get("decision_status"),
				"reconciliation_readiness_status": readiness,
				"exception_reason": reason,
				"existing_reconciliation_status": "Reconciled" if readiness == READINESS_ALREADY_RECONCILED else "",
				"confirmed_by": row.get("confirmed_by"),
				"confirmed_on": row.get("confirmed_on"),
				"days_since_confirmation": _days_since(row.get("confirmed_on")),
			}
		)
	return results


def _safe_load_json(value):
	if not value:
		return {}
	try:
		loaded = frappe.parse_json(value)
		return loaded or {}
	except Exception:
		return {}


def _days_since(value):
	if not value:
		return None
	return abs((getdate(nowdate()) - getdate(value)).days)
