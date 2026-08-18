from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import cstr, flt, getdate

from retailedge.bank_fuzzy_discovery import enrich_ranked_candidates
from retailedge.bank_transaction_matching import (
	assert_can_access_bank_transaction_matching,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	normalize_bank_transaction,
)
from retailedge.branch_context import has_doctype, has_field

DIRECTION_INFLOW = "Inflow"
DIRECTION_OUTFLOW = "Outflow"

CATEGORY_CUSTOMER_RECEIPT = "Customer Receipt"
CATEGORY_POS_SALE = "POS Sale"
CATEGORY_BANK_DEPOSIT = "Deposit to Bank"
CATEGORY_SUPPLIER_PAYMENT = "Supplier Payment"
CATEGORY_EXPENSE = "Expense"
CATEGORY_BANK_TRANSFER = "Bank Transfer"
CATEGORY_OTHER_INCOME = "Other Income"
CATEGORY_OTHER_OUTFLOW = "Other Outflow"


def _date_distance(bank_date, candidate_date):
	if not bank_date or not candidate_date:
		return None
	try:
		return abs((getdate(bank_date) - getdate(candidate_date)).days)
	except Exception:
		return None


def _resolve_bank_ledger_account(bank_transaction):
	ledger_account = cstr(bank_transaction.get("ledger_account")).strip()
	if ledger_account:
		return ledger_account
	bank_account = cstr(bank_transaction.get("bank_account")).strip()
	if not bank_account or not has_doctype("Bank Account"):
		return ""
	return cstr(frappe.db.get_value("Bank Account", bank_account, "account") or "").strip()


def _journal_entry_candidates(bank_transaction, limit=40):
	if not has_doctype("Journal Entry") or not has_doctype("Journal Entry Account"):
		return []
	bank_ledger = _resolve_bank_ledger_account(bank_transaction)
	if not bank_ledger:
		return []

	company = cstr(bank_transaction.get("company")).strip()
	bank_date = bank_transaction.get("transaction_date")
	bank_amount = flt(bank_transaction.get("amount"))
	direction = cstr(bank_transaction.get("direction")).strip()
	if bank_amount <= 0 or direction not in {DIRECTION_INFLOW, DIRECTION_OUTFLOW}:
		return []

	filters = {"account": bank_ledger, "docstatus": 1}
	amount_field = "debit_in_account_currency" if direction == DIRECTION_INFLOW else "credit_in_account_currency"
	if has_field("Journal Entry Account", amount_field):
		filters[amount_field] = [">", 0]

	fields = ["parent", "account", "debit_in_account_currency", "credit_in_account_currency"]
	for fieldname in ("reference_type", "reference_name", "party_type", "party"):
		if has_field("Journal Entry Account", fieldname):
			fields.append(fieldname)
	account_rows = frappe.get_all(
		"Journal Entry Account",
		filters=filters,
		fields=fields,
		limit_page_length=max(limit * 4, 80),
	)
	entry_names = list(dict.fromkeys(row.get("parent") for row in account_rows if row.get("parent")))
	if not entry_names:
		return []

	je_fields = ["name", "posting_date", "company", "voucher_type", "user_remark"]
	for fieldname in ("cheque_no", "cheque_date", "title", "remark"):
		if has_field("Journal Entry", fieldname) and fieldname not in je_fields:
			je_fields.append(fieldname)
	je_filters = {"name": ["in", entry_names], "docstatus": 1}
	if company and has_field("Journal Entry", "company"):
		je_filters["company"] = company
	entries = {
		row.get("name"): row
		for row in frappe.get_all(
			"Journal Entry",
			filters=je_filters,
			fields=je_fields,
			limit_page_length=max(limit * 4, 80),
		)
	}

	candidates = []
	for account_row in account_rows:
		entry = entries.get(account_row.get("parent"))
		if not entry:
			continue
		candidate_amount = flt(
			account_row.get("debit_in_account_currency")
			if direction == DIRECTION_INFLOW
			else account_row.get("credit_in_account_currency")
		)
		if candidate_amount <= 0:
			continue
		days = _date_distance(bank_date, entry.get("posting_date"))
		if days is not None and days > 7:
			continue
		amount_diff = abs(bank_amount - candidate_amount)
		if amount_diff > max(0.01, bank_amount * 0.001):
			continue

		voucher_type = cstr(entry.get("voucher_type")).strip()
		remarks = cstr(entry.get("user_remark") or entry.get("remark")).strip()
		category = "Journal Entry Match"
		business_category = CATEGORY_OTHER_INCOME if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW
		lower_text = f"{voucher_type} {remarks}".lower()
		if "bank entry" in lower_text or "transfer" in lower_text:
			category = "Deposit to Bank" if direction == DIRECTION_INFLOW else "Bank Transfer"
			business_category = CATEGORY_BANK_DEPOSIT if direction == DIRECTION_INFLOW else CATEGORY_BANK_TRANSFER
		elif any(token in lower_text for token in ("expense", "charge", "fee")):
			category = "Expense Payment" if direction == DIRECTION_OUTFLOW else "Other Income"
			business_category = CATEGORY_EXPENSE if direction == DIRECTION_OUTFLOW else CATEGORY_OTHER_INCOME

		candidate = {
			"document_type": "Journal Entry",
			"document_name": entry.get("name"),
			"candidate_category": category,
			"transaction_category": business_category,
			"candidate_amount": candidate_amount,
			"amount_difference": amount_diff,
			"posting_date": entry.get("posting_date"),
			"direction": direction,
			"payment_account": bank_ledger,
			"account": bank_ledger,
			"reference": entry.get("cheque_no"),
			"party_type": account_row.get("party_type"),
			"party": account_row.get("party"),
			"remarks": remarks,
			"description": remarks,
			"match_score": 72 if days in {None, 0} else 68,
			"reasons": ["Submitted Journal Entry impacts the selected bank ledger with a compatible amount."],
			"payment_event_found": 1,
			"payment_event_source": "Journal Entry",
		}
		candidates.append(candidate)
	return candidates[:limit]


def _hydrate_payment_entry_metadata(candidates):
	names = [
		cstr(row.get("document_name")).strip()
		for row in candidates or []
		if cstr(row.get("document_type")).strip() == "Payment Entry"
		and cstr(row.get("document_name")).strip()
	]
	if not names or not has_doctype("Payment Entry"):
		return {}
	fields = ["name", "payment_type", "party_type", "party", "paid_from", "paid_to"]
	for fieldname in ("mode_of_payment", "remarks", "reference_no"):
		if has_field("Payment Entry", fieldname):
			fields.append(fieldname)
	return {
		row.get("name"): row
		for row in frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", list(dict.fromkeys(names))], "docstatus": 1},
			fields=fields,
			limit_page_length=len(set(names)) or 1,
		)
	}


def _payment_entry_business_category(metadata, direction):
	payment_type = cstr(metadata.get("payment_type")).strip()
	party_type = cstr(metadata.get("party_type")).strip()
	remarks = cstr(metadata.get("remarks")).strip().lower()

	if payment_type == "Internal Transfer":
		return CATEGORY_BANK_DEPOSIT if direction == DIRECTION_INFLOW else CATEGORY_BANK_TRANSFER
	if direction == DIRECTION_INFLOW:
		return CATEGORY_CUSTOMER_RECEIPT if party_type == "Customer" else CATEGORY_OTHER_INCOME
	if party_type == "Supplier":
		return CATEGORY_SUPPLIER_PAYMENT
	if any(token in remarks for token in ("expense", "charge", "fee", "rent", "utility")):
		return CATEGORY_EXPENSE
	return CATEGORY_OTHER_OUTFLOW


def _annotate_candidate_business_context(candidate, bank_transaction, payment_metadata):
	row = dict(candidate or {})
	direction = cstr(bank_transaction.get("direction")).strip()
	doctype = cstr(row.get("document_type")).strip()
	category = cstr(row.get("candidate_category")).lower()
	payment_source = cstr(row.get("payment_event_source")).lower()

	if row.get("transaction_category"):
		return row
	if doctype == "Payment Entry":
		metadata = payment_metadata.get(cstr(row.get("document_name")).strip()) or {}
		row["transaction_category"] = _payment_entry_business_category(metadata, direction)
		row.setdefault("party_type", metadata.get("party_type"))
		row.setdefault("party", metadata.get("party"))
		row.setdefault("remarks", metadata.get("remarks"))
		row.setdefault("reference", metadata.get("reference_no"))
		row["payment_type"] = metadata.get("payment_type")
		return row
	if doctype == "Sales Invoice":
		row["transaction_category"] = (
			CATEGORY_POS_SALE
			if "pos" in category or "pos payment" in payment_source
			else CATEGORY_CUSTOMER_RECEIPT
		)
		return row
	row["transaction_category"] = (
		CATEGORY_OTHER_INCOME if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW
	)
	return row


def _prepare_candidate_for_fuzzy(candidate, bank_transaction):
	row = dict(candidate or {})
	row.setdefault("direction", bank_transaction.get("direction"))
	row.setdefault("posting_date", row.get("candidate_posting_date") or row.get("date"))
	row.setdefault("party", row.get("customer") or row.get("supplier"))
	row.setdefault("reference", row.get("reference_no") or row.get("document_name"))
	row.setdefault("description", row.get("remarks") or row.get("match_reason"))
	if not row.get("payment_account"):
		row["payment_account"] = row.get("account") or row.get("expected_bank_account")
	return row


def get_direction_aware_bank_candidates(bank_transaction_name, filters=None, limit=40):
	"""Return existing RetailEdge candidates plus direction-specific ERPNext bank events.

	Fuzzy similarity is applied only after the existing candidate builders and hard accounting
	guards have produced candidates. This service does not reconcile or mutate accounting docs.
	"""
	assert_can_access_bank_transaction_matching()
	bank_transaction = normalize_bank_transaction(bank_transaction_name)
	direction = cstr(bank_transaction.get("direction")).strip()
	if direction not in {DIRECTION_INFLOW, DIRECTION_OUTFLOW}:
		frappe.throw("Bank Transaction direction could not be determined safely.")

	filters = frappe._dict(filters or {})
	base_candidates = []
	payment_candidates = find_payment_entry_candidates_for_bank_transaction(
		bank_transaction_name,
		filters=filters,
		limit=limit,
	)
	base_candidates.extend(payment_candidates or [])

	if direction == DIRECTION_INFLOW:
		base_candidates.extend(
			find_sales_invoice_candidates_for_bank_transaction(
				bank_transaction_name,
				filters=filters,
				limit=limit,
			)
			or []
		)

	base_candidates.extend(_journal_entry_candidates(bank_transaction, limit=limit))
	payment_metadata = _hydrate_payment_entry_metadata(base_candidates)
	annotated = [
		_annotate_candidate_business_context(candidate, bank_transaction, payment_metadata)
		for candidate in base_candidates
	]
	prepared = [_prepare_candidate_for_fuzzy(candidate, bank_transaction) for candidate in annotated]
	prepared = enrich_ranked_candidates(bank_transaction, prepared)

	seen = set()
	output = []
	for row in prepared:
		key = (cstr(row.get("document_type")).strip(), cstr(row.get("document_name")).strip())
		if not all(key) or key in seen:
			continue
		seen.add(key)
		output.append(row)
		if len(output) >= int(limit or 40):
			break
	return {
		"bank_transaction": bank_transaction_name,
		"direction": direction,
		"candidates": output,
		"count": len(output),
	}
