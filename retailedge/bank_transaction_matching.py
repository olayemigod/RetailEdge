from __future__ import annotations

from collections import defaultdict

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
from retailedge.invoice_payment_audit import classify_payment_method
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


def assert_can_access_bank_transaction_matching(user: str | None = None):
	if user_has_any_role(user=user, roles=BANK_TRANSACTION_MATCHING_ROLES):
		return
	frappe.throw(
		"You do not have permission to access RetailEdge bank transaction matching.",
		frappe.PermissionError,
	)


def get_bank_transaction_matching_settings():
	try:
		settings = get_retailedge_settings()
	except Exception:
		settings = None
	return {
		"date_window_days": cint(getattr(settings, "bank_transaction_match_date_window_days", 3) or 3),
		"amount_tolerance": flt(getattr(settings, "bank_transaction_match_amount_tolerance", 0) or 0),
		"minimum_possible_score": cint(getattr(settings, "bank_transaction_match_minimum_possible_score", 50) or 50),
		"strong_match_score": cint(getattr(settings, "bank_transaction_match_strong_score", 80) or 80),
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


def find_sales_invoice_candidates_for_bank_transaction(bank_transaction_name, filters=None, limit=20):
	filters = frappe._dict(filters or {})
	settings = get_bank_transaction_matching_settings()
	bank_transaction = normalize_bank_transaction(bank_transaction_name)
	if bank_transaction.get("direction") != "Inflow":
		return []
	if not has_doctype("Sales Invoice"):
		return []

	invoices = _get_sales_invoice_rows(bank_transaction, filters, settings, limit=max(int(limit or 20) * 3, 20))
	results = []
	for invoice in invoices:
		candidate = _build_sales_invoice_candidate(bank_transaction, invoice, filters, settings)
		if not candidate:
			continue
		score_payload = score_bank_transaction_candidate(bank_transaction, candidate)
		candidate.update(score_payload)
		if candidate["score"] >= 30:
			results.append(candidate)
	results.sort(key=lambda row: (-int(row.get("score") or 0), abs(flt(row.get("amount_difference"))), cstr(row.get("document_name"))))
	return results[: int(limit or 20)]


def find_payment_entry_candidates_for_bank_transaction(bank_transaction_name, filters=None, limit=20):
	filters = frappe._dict(filters or {})
	settings = get_bank_transaction_matching_settings()
	bank_transaction = normalize_bank_transaction(bank_transaction_name)
	if not has_doctype("Payment Entry"):
		return []

	payment_entries = _get_payment_entry_rows(
		bank_transaction,
		filters,
		settings,
		limit=max(int(limit or 20) * 3, 20),
	)
	references_by_entry = _get_payment_entry_sales_invoice_references([row.get("name") for row in payment_entries])
	results = []
	for payment_entry in payment_entries:
		candidate = _build_payment_entry_candidate(
			bank_transaction,
			payment_entry,
			references_by_entry.get(payment_entry.get("name")) or [],
		)
		score_payload = score_bank_transaction_candidate(bank_transaction, candidate)
		candidate.update(score_payload)
		if candidate["score"] >= 30:
			results.append(candidate)
	results.sort(key=lambda row: (-int(row.get("score") or 0), abs(flt(row.get("amount_difference"))), cstr(row.get("document_name"))))
	return results[: int(limit or 20)]


def score_bank_transaction_candidate(bank_transaction, candidate):
	settings = get_bank_transaction_matching_settings()
	tolerance = flt(settings.get("amount_tolerance"))
	score = 0
	reasons = []
	bank_amount = flt(bank_transaction.get("amount"))
	candidate_amount = flt(candidate.get("candidate_amount"))
	amount_difference = abs(bank_amount - candidate_amount)

	if amount_difference <= 0.01:
		score += 35
		reasons.append("Exact amount match.")
	elif amount_difference <= tolerance:
		score += 25
		reasons.append("Amount is within the configured tolerance.")
	elif candidate.get("supports_partial_match") and min(bank_amount, candidate_amount) > 0:
		score += 15
		reasons.append("Amount suggests a possible partial or allocated match.")
	else:
		score -= 25
		reasons.append("Amount is materially different.")

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

	if normalized_invoice_name and normalized_invoice_name in normalized_bank_text:
		score += 30
		reasons.append("Bank narration/reference contains the Sales Invoice name.")
	elif normalized_candidate_name and normalized_candidate_name in normalized_bank_text:
		score += 30
		reasons.append("Bank narration/reference contains the suggested document name.")
	elif normalized_candidate_reference and normalized_candidate_reference == bank_transaction.get("normalized_reference"):
		score += 25
		reasons.append("Normalized reference matches exactly.")

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

	if _candidate_account_matches_bank_transaction(bank_transaction, candidate):
		score += 10
		reasons.append("Bank account or expected account aligns with the transaction.")

	if bank_transaction.get("branch") and candidate.get("branch") and bank_transaction.get("branch") == candidate.get("branch"):
		score += 5
		reasons.append("RetailEdge branch attribution matches.")

	if candidate.get("document_type") == "Sales Invoice" and cstr(candidate.get("payment_verification_status")).strip() == "Bank Verified":
		score -= 30
		reasons.append("Sales Invoice is already marked Bank Verified.")

	if bank_transaction.get("direction") == "Outflow" and candidate.get("document_type") == "Sales Invoice":
		score -= 60
		reasons.append("Outflow transactions are not treated as customer sales receipts.")

	if score >= cint(settings.get("strong_match_score") or 80):
		confidence = "Strong Match"
	elif score >= cint(settings.get("minimum_possible_score") or 50):
		confidence = "Possible Match"
	elif score >= 30:
		confidence = "Weak Match"
	else:
		confidence = "No Match"

	return {"score": score, "confidence": confidence, "reasons": reasons}


def get_bank_transaction_matching_rows(filters=None, limit=500):
	filters = _coerce_matching_filters(filters)
	settings = get_bank_transaction_matching_settings()
	filtered_limit = min(int(limit or 500), 2000)
	rows = []
	for bank_transaction_row in _get_bank_transaction_rows(filters, filtered_limit):
		bank_transaction = normalize_bank_transaction(bank_transaction_row)
		if bank_transaction.get("is_reconciled") and not filters.get("include_reconciled"):
			continue

		if bank_transaction.get("direction") == "Outflow":
			rows.append(
				_build_matching_row(
					bank_transaction,
					candidate=None,
					action_status="Outflow / Not Sales Receipt",
					match_reason="Outflow transactions are shown for review but not matched to customer Sales Invoices in this phase.",
				)
			)
			continue

		sales_candidates = find_sales_invoice_candidates_for_bank_transaction(
			bank_transaction.get("bank_transaction"),
			filters=filters,
			limit=20,
		)
		payment_candidates = find_payment_entry_candidates_for_bank_transaction(
			bank_transaction.get("bank_transaction"),
			filters=filters,
			limit=20,
		)
		candidates = sorted(
			sales_candidates + payment_candidates,
			key=lambda row: (-int(row.get("score") or 0), cstr(row.get("document_type")), cstr(row.get("document_name"))),
		)
		best_candidate = candidates[0] if candidates else None
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
		rows.append(row)
	return rows[:filtered_limit]


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
	date_window = cint(filters.get("date_window_days") or settings.get("date_window_days") or 3)
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


def _build_sales_invoice_candidate(bank_transaction, invoice, filters, settings):
	amount_details = _best_invoice_amount_match(bank_transaction, invoice, settings)
	if not amount_details["fieldname"] or amount_details["amount"] <= 0:
		return None
	if amount_details["difference"] > max(flt(settings.get("amount_tolerance")), flt(bank_transaction.get("amount"))):
		return None

	branch = _row_value(invoice, "retailedge_branch") or _row_value(invoice, "branch")
	expected_account = None
	try:
		profile_defaults = get_branch_profile_defaults(
			company=invoice.get("company"),
			branch=branch,
			pos_profile=invoice.get("pos_profile"),
		)
		expected_account = profile_defaults.get("default_bank_account")
	except Exception:
		expected_account = None

	return {
		"document_type": "Sales Invoice",
		"document_name": invoice.get("name"),
		"suggested_sales_invoice": invoice.get("name"),
		"posting_date": invoice.get("posting_date"),
		"customer": invoice.get("customer_name") or invoice.get("customer"),
		"candidate_amount": amount_details["amount"],
		"amount_difference": amount_details["difference"],
		"reference": invoice.get("name"),
		"branch": branch,
		"expected_bank_account": expected_account,
		"payment_verification_status": invoice.get("retailedge_payment_verification_status"),
		"supports_partial_match": True,
		"reason": amount_details["reason"],
	}


def _best_invoice_amount_match(bank_transaction, invoice, settings):
	candidates = [
		("grand_total", flt(invoice.get("grand_total"))),
		("outstanding_amount", flt(invoice.get("outstanding_amount"))),
		("paid_amount", flt(invoice.get("paid_amount"))),
	]
	bank_amount = flt(bank_transaction.get("amount"))
	best_name = None
	best_amount = 0.0
	best_difference = None
	for fieldname, amount in candidates:
		if amount <= 0:
			continue
		difference = abs(bank_amount - amount)
		if best_difference is None or difference < best_difference:
			best_difference = difference
			best_name = fieldname
			best_amount = amount
	if best_difference is None:
		best_difference = abs(bank_amount)
	return {
		"fieldname": best_name,
		"amount": best_amount,
		"difference": best_difference,
		"reason": f"Best invoice amount match used {best_name or 'no supported amount field'}.",
	}


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
	date_window = cint(filters.get("date_window_days") or settings.get("date_window_days") or 3)
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
		allocated_amount = flt(references[0].get("allocated_amount") or references[0].get("total_amount"))
		if allocated_amount > 0:
			candidate_amount = allocated_amount

	return {
		"document_type": "Payment Entry",
		"document_name": payment_entry.get("name"),
		"suggested_document": payment_entry.get("name"),
		"suggested_sales_invoice": suggested_invoice,
		"posting_date": payment_entry.get("posting_date"),
		"customer": payment_entry.get("party"),
		"candidate_amount": candidate_amount,
		"amount_difference": abs(flt(bank_transaction.get("amount")) - candidate_amount),
		"reference": payment_entry.get("reference_no") or payment_entry.get("name"),
		"branch": payment_entry.get("retailedge_branch"),
		"account": payment_entry.get("paid_to") if direction == "Inflow" else payment_entry.get("paid_from"),
		"supports_partial_match": True,
		"remarks": payment_entry.get("remarks") or payment_entry.get("custom_remarks"),
	}


def _build_matching_row(bank_transaction, candidate=None, action_status="No Match", match_reason=None):
	candidate = candidate or {}
	return {
		"bank_transaction": bank_transaction.get("bank_transaction"),
		"transaction_date": bank_transaction.get("transaction_date"),
		"bank_account": bank_transaction.get("bank_account"),
		"reference": bank_transaction.get("reference"),
		"narration": bank_transaction.get("description"),
		"amount": flt(bank_transaction.get("amount")),
		"direction": bank_transaction.get("direction"),
		"suggested_document_type": candidate.get("document_type"),
		"suggested_document": candidate.get("document_name"),
		"suggested_sales_invoice": candidate.get("suggested_sales_invoice"),
		"customer": candidate.get("customer") or bank_transaction.get("party"),
		"candidate_amount": flt(candidate.get("candidate_amount")),
		"amount_difference": flt(candidate.get("amount_difference")),
		"match_confidence": candidate.get("confidence") or "No Match",
		"match_score": cint(candidate.get("score") or 0),
		"match_reason": match_reason or candidate.get("reason") or "No candidate reached the minimum matching confidence.",
		"branch": bank_transaction.get("branch") or candidate.get("branch"),
		"action_status": action_status,
	}


def _derive_action_status(bank_transaction, candidate):
	if bank_transaction.get("is_reconciled"):
		return "Already Reconciled"
	if bank_transaction.get("direction") != "Inflow":
		return "Outflow / Not Sales Receipt"
	if not candidate:
		return "No Match"
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
	bank_tokens = _get_bank_account_match_tokens(bank_transaction.get("bank_account"))
	for value in (
		candidate.get("account"),
		candidate.get("expected_bank_account"),
		candidate.get("bank_account"),
	):
		token = normalize_statement_text(value)
		if token and token in bank_tokens:
			return True
	return False


def _get_bank_transaction_rows(filters, limit):
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

	order_by = f"{date_field or 'modified'} desc, modified desc"
	return frappe.get_all(
		"Bank Transaction",
		filters=filters_payload,
		fields=fields,
		limit_page_length=limit,
		order_by=order_by,
	)


def _coerce_matching_filters(filters=None):
	filters = frappe._dict(filters or {})
	filters.setdefault("from_date", str(get_first_day(nowdate())))
	filters.setdefault("to_date", str(getdate(nowdate())))
	filters.setdefault("only_unmatched", 1)
	filters.setdefault("include_reconciled", 0)
	filters.setdefault("include_verified_invoices", 0)
	for fieldname in ("only_unmatched", "include_reconciled", "include_verified_invoices"):
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


def _get_bank_account_match_tokens(bank_account):
	tokens = set()
	normalized_name = normalize_statement_text(bank_account)
	if normalized_name:
		tokens.add(normalized_name)
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


def _date_difference_days(left, right):
	if not left or not right:
		return None
	return abs((getdate(left) - getdate(right)).days)


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


def _looks_like_invoice_reference(text):
	normalized = normalize_statement_text(text)
	return any(token in normalized for token in ("INV", "SINV", "SI"))
