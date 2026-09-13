from __future__ import annotations

from datetime import timedelta
from typing import Any

import frappe
from frappe.utils import cstr, flt, getdate

from retailedge.bank_fuzzy_discovery import enrich_ranked_candidates
from retailedge.bank_transaction_match_workflow import (
	assert_can_manage_bank_transaction_match,
	create_or_get_bank_transaction_match,
)
from retailedge.bank_transaction_matching import (
	assert_can_access_bank_transaction_matching,
	find_payment_entry_candidates_for_bank_transaction,
	find_sales_invoice_candidates_for_bank_transaction,
	normalize_bank_transaction,
)
from retailedge.branch_context import has_doctype, has_field
from retailedge.retailedge.doctype.retailedge_bank_transaction_match.retailedge_bank_transaction_match import (
	_resolve_manual_candidate_context,
)

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

OUTCOME_CANDIDATES_FOUND = "candidates_found"
OUTCOME_BANKING_SETUP_BLOCKED = "banking_setup_blocked"
OUTCOME_ACCOUNTING_EVENT_MISSING = "accounting_event_missing"
OUTCOME_ACCOUNTING_EVENT_NOT_ELIGIBLE = "accounting_event_not_eligible"
OUTCOME_CANDIDATE_REVIEW_BLOCKED = "candidate_review_blocked"

REVIEW_SUPPORTED_DOCTYPES = {"Sales Invoice", "Payment Entry", "Journal Entry"}


def _date_distance(bank_date, candidate_date):
	if not bank_date or not candidate_date:
		return None
	try:
		return abs((getdate(bank_date) - getdate(candidate_date)).days)
	except Exception:
		return None


def _can_read_candidate(doctype, name):
	doctype = cstr(doctype).strip()
	name = cstr(name).strip()
	if not doctype or not name:
		return False
	try:
		return bool(frappe.has_permission(doctype, "read", doc=name))
	except Exception:
		return False


def _resolve_bank_ledger_account(bank_transaction):
	ledger_account = cstr(bank_transaction.get("ledger_account")).strip()
	if ledger_account:
		return ledger_account
	bank_account = cstr(bank_transaction.get("bank_account")).strip()
	if not bank_account or not has_doctype("Bank Account"):
		return ""
	return cstr(frappe.db.get_value("Bank Account", bank_account, "account") or "").strip()


def _journal_entry_counterpart_context(parent_names, bank_ledger):
	"""Return bounded accounting metadata for non-bank rows on candidate Journal Entries."""
	parents = list(
		dict.fromkeys(
			cstr(parent).strip()
			for parent in parent_names or []
			if cstr(parent).strip()
		)
	)
	bank_ledger = cstr(bank_ledger).strip()
	if not parents or not bank_ledger or not has_doctype("Account"):
		return {}

	rows = frappe.get_all(
		"Journal Entry Account",
		filters={"parent": ["in", parents], "docstatus": 1},
		fields=["parent", "account"],
		limit_page_length=min(max(len(parents) * 6, 160), 5000),
	)
	account_names = list(
		dict.fromkeys(
			cstr(row.get("account")).strip()
			for row in rows
			if cstr(row.get("account")).strip()
			and cstr(row.get("account")).strip() != bank_ledger
		)
	)
	if not account_names:
		return {}

	account_fields = ["name"]
	for fieldname in ("root_type", "account_type"):
		if has_field("Account", fieldname):
			account_fields.append(fieldname)
	account_rows = frappe.get_all(
		"Account",
		filters={"name": ["in", account_names]},
		fields=account_fields,
		limit_page_length=len(account_names),
	)
	account_metadata = {
		cstr(row.get("name")).strip(): row
		for row in account_rows
		if cstr(row.get("name")).strip()
	}

	output = {}
	for row in rows:
		parent = cstr(row.get("parent")).strip()
		account = cstr(row.get("account")).strip()
		if not parent or not account or account == bank_ledger:
			continue
		metadata = dict(account_metadata.get(account) or {})
		metadata["account"] = account
		output.setdefault(parent, []).append(metadata)
	return output


def _journal_entry_business_category(direction, voucher_type, remarks, counterpart_accounts=None):
	"""Classify Journal Entry bank events using accounting structure before descriptive text."""
	counterparts = counterpart_accounts or []
	lower_text = f"{cstr(voucher_type).strip()} {cstr(remarks).strip()}".lower()
	has_expense_counterpart = any(
		cstr(row.get("root_type")).strip() == "Expense"
		for row in counterparts
	)
	has_bank_counterpart = any(
		cstr(row.get("account_type")).strip() == "Bank"
		for row in counterparts
	)
	has_expense_text = any(
		token in lower_text
		for token in ("expense", "charge", "fee", "rent", "utility")
	)

	if direction == DIRECTION_OUTFLOW and (has_expense_counterpart or has_expense_text):
		return "Expense Payment", CATEGORY_EXPENSE
	if has_bank_counterpart or "bank entry" in lower_text or "transfer" in lower_text:
		return (
			("Deposit to Bank", CATEGORY_BANK_DEPOSIT)
			if direction == DIRECTION_INFLOW
			else ("Bank Transfer", CATEGORY_BANK_TRANSFER)
		)
	return (
		"Journal Entry Match",
		CATEGORY_OTHER_INCOME if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW,
	)


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

	je_fields = ["name", "posting_date", "company", "voucher_type", "user_remark"]
	for fieldname in ("cheque_no", "cheque_date", "title", "remark"):
		if has_field("Journal Entry", fieldname) and fieldname not in je_fields:
			je_fields.append(fieldname)
	je_filters: dict[str, Any] = {"docstatus": 1}
	if company and has_field("Journal Entry", "company"):
		je_filters["company"] = company
	if bank_date and has_field("Journal Entry", "posting_date"):
		center = getdate(bank_date)
		je_filters["posting_date"] = ["between", [center - timedelta(days=7), center + timedelta(days=7)]]

	entry_rows = frappe.get_list(
		"Journal Entry",
		filters=je_filters,
		fields=je_fields,
		order_by="posting_date desc, modified desc",
		limit_page_length=min(max(limit * 8, 160), 1000),
	)
	entries = {row.get("name"): row for row in entry_rows if row.get("name")}
	entry_names = list(entries)
	if not entry_names:
		return []

	filters = {"parent": ["in", entry_names], "account": bank_ledger, "docstatus": 1}
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
		limit_page_length=min(max(limit * 8, 160), 1000),
	)
	candidate_parents = list(
		dict.fromkeys(
			cstr(row.get("parent")).strip()
			for row in account_rows
			if cstr(row.get("parent")).strip()
		)
	)
	counterpart_context = _journal_entry_counterpart_context(candidate_parents, bank_ledger)

	candidates = []
	for account_row in account_rows:
		entry = entries.get(account_row.get("parent"))
		if not entry or not _can_read_candidate("Journal Entry", entry.get("name")):
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
		category, business_category = _journal_entry_business_category(
			direction,
			voucher_type,
			remarks,
			counterpart_accounts=counterpart_context.get(cstr(entry.get("name")).strip()) or [],
		)

		candidates.append(
			{
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
				"review_supported": 1,
				"review_block_reason": "",
			}
		)
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
	rows = frappe.get_list(
		"Payment Entry",
		filters={"name": ["in", list(dict.fromkeys(names))], "docstatus": 1},
		fields=fields,
		limit_page_length=len(set(names)) or 1,
	)
	return {row.get("name"): row for row in rows if row.get("name")}


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

	row.setdefault("review_supported", 1 if doctype in REVIEW_SUPPORTED_DOCTYPES else 0)
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
	row["transaction_category"] = CATEGORY_OTHER_INCOME if direction == DIRECTION_INFLOW else CATEGORY_OTHER_OUTFLOW
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


def _normalize_candidate_limit(limit):
	try:
		value = int(limit or 40)
	except (TypeError, ValueError):
		value = 40
	return min(max(value, 1), 100)


def _candidate_bank_readiness(bank_transaction):
	"""Return Banking Readiness for real normalized rows while preserving lightweight unit mocks."""
	if "bank_account" not in bank_transaction:
		return {}
	from retailedge.banking_readiness import evaluate_bank_account_readiness

	return evaluate_bank_account_readiness(
		bank_transaction.get("bank_account"),
		company=bank_transaction.get("company"),
	)


def _has_nearby_submitted_accounting_event(bank_transaction):
	"""Detect permission-visible accounting events with compatible date/amount but no safe match.

	This diagnostic runs only after normal candidate discovery returns nothing. It does not
	make an event eligible; it only lets the UI distinguish a missing accounting event from
	an existing event that failed account/reference/eligibility safety checks.
	"""
	amount = flt(bank_transaction.get("amount"))
	direction = cstr(bank_transaction.get("direction")).strip()
	company = cstr(bank_transaction.get("company")).strip()
	bank_date = bank_transaction.get("transaction_date")
	if amount <= 0 or direction not in {DIRECTION_INFLOW, DIRECTION_OUTFLOW}:
		return False

	tolerance = max(0.01, amount * 0.001)
	amount_range = [max(0, amount - tolerance), amount + tolerance]
	date_range = None
	if bank_date:
		center = getdate(bank_date)
		date_range = [center - timedelta(days=7), center + timedelta(days=7)]

	if has_doctype("Payment Entry"):
		amount_field = "received_amount" if direction == DIRECTION_INFLOW else "paid_amount"
		filters: dict[str, Any] = {"docstatus": 1}
		if has_field("Payment Entry", amount_field):
			filters[amount_field] = ["between", amount_range]
		if company and has_field("Payment Entry", "company"):
			filters["company"] = company
		if date_range and has_field("Payment Entry", "posting_date"):
			filters["posting_date"] = ["between", date_range]
		if frappe.get_list(
			"Payment Entry",
			filters=filters,
			fields=["name"],
			limit_page_length=1,
		):
			return True

	if has_doctype("Journal Entry") and has_doctype("Journal Entry Account"):
		je_filters: dict[str, Any] = {"docstatus": 1}
		if company and has_field("Journal Entry", "company"):
			je_filters["company"] = company
		if date_range and has_field("Journal Entry", "posting_date"):
			je_filters["posting_date"] = ["between", date_range]
		entries = frappe.get_list(
			"Journal Entry",
			filters=je_filters,
			fields=["name"],
			limit_page_length=40,
		)
		entry_names = [cstr(row.get("name")).strip() for row in entries if cstr(row.get("name")).strip()]
		if entry_names:
			amount_field = (
				"debit_in_account_currency"
				if direction == DIRECTION_INFLOW
				else "credit_in_account_currency"
			)
			filters = {"parent": ["in", entry_names], "docstatus": 1}
			if has_field("Journal Entry Account", amount_field):
				filters[amount_field] = ["between", amount_range]
			if frappe.get_all(
				"Journal Entry Account",
				filters=filters,
				fields=["parent"],
				limit_page_length=1,
			):
				return True

	return False


def _candidate_search_outcome(bank_transaction, candidates, banking_readiness=None):
	readiness = frappe._dict(banking_readiness or {})
	if cstr(readiness.get("readiness")).strip() == "Blocked":
		issues = [
			cstr(issue.get("message")).strip()
			for issue in readiness.get("issues") or []
			if cstr(issue.get("message")).strip()
		]
		message = " ".join(issues[:3]) or "Banking setup could not be resolved safely."
		return {
			"code": OUTCOME_BANKING_SETUP_BLOCKED,
			"title": "Banking setup needs attention",
			"message": f"{message} Correct Banking Setup & Readiness before matching this transaction.",
			"indicator": "red",
			"action": "banking_readiness",
		}

	rows = list(candidates or [])
	if rows:
		reviewable = [row for row in rows if int(row.get("review_supported", 1) or 0) != 0]
		if not reviewable:
			return {
				"code": OUTCOME_CANDIDATE_REVIEW_BLOCKED,
				"title": "Accounting evidence found, but review is blocked",
				"message": "Accounting records were found, but none currently has sufficient payment evidence to enter Bank Match Review safely.",
				"indicator": "orange",
			}
		return {
			"code": OUTCOME_CANDIDATES_FOUND,
			"title": "Matching candidates found",
			"message": "Safe accounting candidates are available for review.",
			"indicator": "green",
		}

	if _has_nearby_submitted_accounting_event(bank_transaction):
		return {
			"code": OUTCOME_ACCOUNTING_EVENT_NOT_ELIGIBLE,
			"title": "Accounting entry found, but it is not safe to match",
			"message": "A submitted accounting entry with a compatible amount and date exists, but it failed bank-account, reference, direction, or eligibility safety checks. Review the accounting document and Banking Setup before retrying; do not force the match.",
			"indicator": "orange",
		}

	return {
		"code": OUTCOME_ACCOUNTING_EVENT_MISSING,
		"title": "No matching accounting entry found",
		"message": "No submitted accounting event with a compatible amount and date was found for this bank transaction. Create or import the corresponding accounting entry, then run Find Match again.",
		"indicator": "blue",
	}


@frappe.whitelist()
def get_direction_aware_bank_candidates(bank_transaction_name, filters=None, limit=40):
	"""Return direction-safe existing candidates plus permission-aware ERPNext bank events."""
	assert_can_access_bank_transaction_matching()
	limit = _normalize_candidate_limit(limit)
	bank_transaction = normalize_bank_transaction(bank_transaction_name)
	direction = cstr(bank_transaction.get("direction")).strip()
	if direction not in {DIRECTION_INFLOW, DIRECTION_OUTFLOW}:
		frappe.throw("Bank Transaction direction could not be determined safely.")

	banking_readiness = _candidate_bank_readiness(bank_transaction)
	if cstr(banking_readiness.get("readiness")).strip() == "Blocked":
		return {
			"bank_transaction": bank_transaction_name,
			"direction": direction,
			"candidates": [],
			"count": 0,
			"banking_readiness": banking_readiness,
			"outcome": _candidate_search_outcome(bank_transaction, [], banking_readiness),
		}

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
	base_candidates = [
		row
		for row in base_candidates
		if _can_read_candidate(row.get("document_type"), row.get("document_name"))
	]
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
		if len(output) >= limit:
			break
	return {
		"bank_transaction": bank_transaction_name,
		"direction": direction,
		"candidates": output,
		"count": len(output),
		"banking_readiness": banking_readiness,
		"outcome": _candidate_search_outcome(bank_transaction, output, banking_readiness),
	}


def _prepare_journal_entry_review(bank_transaction_name, document_name):
	assert_can_manage_bank_transaction_match()
	if not _can_read_candidate("Journal Entry", document_name):
		frappe.throw("You do not have permission to review this Journal Entry.", frappe.PermissionError)
	candidate_context = _resolve_manual_candidate_context(
		bank_transaction=bank_transaction_name,
		suggested_document_type="Journal Entry",
		suggested_document=document_name,
	)
	if candidate_context.get("block_reason"):
		frappe.throw(candidate_context.get("block_reason"))

	existing = frappe.db.get_value(
		"RetailEdge Bank Transaction Match",
		{
			"bank_transaction": bank_transaction_name,
			"suggested_document_type": "Journal Entry",
			"suggested_document": document_name,
		},
		"name",
	)
	if existing:
		return {
			"status": "Review Ready",
			"created": False,
			"match_name": existing,
			"decision_status": frappe.db.get_value(
				"RetailEdge Bank Transaction Match", existing, "decision_status"
			),
			"message": "Existing Journal Entry Bank Match Review opened.",
		}

	doc = frappe.get_doc({"doctype": "RetailEdge Bank Transaction Match"})
	for fieldname, value in (candidate_context.get("doc_values") or {}).items():
		if value is not None:
			doc.set(fieldname, value)
	doc.bank_transaction = bank_transaction_name
	doc.suggested_document_type = "Journal Entry"
	doc.suggested_document = document_name
	doc.source_report = "Bank Matching & Reconciliation"
	doc.decision_status = "Needs Review"
	doc.decision_note = "Journal Entry candidate requires explicit manual review before confirmation."
	doc.insert(ignore_permissions=True)
	return {
		"status": "Review Ready",
		"created": True,
		"match_name": doc.name,
		"decision_status": doc.decision_status,
		"message": "Journal Entry candidate was revalidated and prepared for explicit manual review.",
	}


@frappe.whitelist()
def prepare_direction_aware_bank_candidate(bank_transaction_name, document_type, document_name):
	"""Create/open the common RetailEdge Bank Match Review for a freshly revalidated candidate."""
	assert_can_access_bank_transaction_matching()
	document_type = cstr(document_type).strip()
	document_name = cstr(document_name).strip()
	if document_type not in REVIEW_SUPPORTED_DOCTYPES:
		return {
			"status": "Review Support Pending",
			"created": False,
			"message": f"{document_type} is not enabled for RetailEdge Bank Match Review.",
		}
	if not _can_read_candidate(document_type, document_name):
		frappe.throw(f"You do not have permission to review this {document_type}.", frappe.PermissionError)

	payload = get_direction_aware_bank_candidates(bank_transaction_name, limit=100)
	candidate = next(
		(
			row
			for row in payload.get("candidates") or []
			if cstr(row.get("document_type")).strip() == document_type
			and cstr(row.get("document_name")).strip() == document_name
		),
		None,
	)
	if not candidate:
		frappe.throw("Selected candidate is no longer eligible. Refresh candidates and review again.")

	if document_type == "Journal Entry":
		return _prepare_journal_entry_review(bank_transaction_name, document_name)

	result = create_or_get_bank_transaction_match(
		bank_transaction_name=bank_transaction_name,
		suggested_document_type=document_type,
		suggested_document=document_name,
		sales_invoice=document_name if document_type == "Sales Invoice" else None,
		payment_entry=document_name if document_type == "Payment Entry" else None,
		source_report="Bank Matching & Reconciliation",
		locked_candidate=candidate,
		allow_fallback=False,
	)
	return {
		"status": "Review Ready",
		"created": bool(result.get("created")),
		"match_name": result.get("name"),
		"decision_status": result.get("decision_status"),
		"message": "Candidate was revalidated and prepared in the existing Bank Match Review workflow.",
	}
