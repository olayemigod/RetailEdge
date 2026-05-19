from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import timedelta
from pathlib import Path

import frappe
from frappe.utils import cint, cstr, flt, getdate
from frappe.utils.csvutils import read_csv_content
from frappe.utils.file_manager import get_file_path
from frappe.utils.xlsxutils import read_xlsx_file_from_attached_file

from retailedge.branch_context import has_doctype, has_field
from retailedge.cashier_expense import user_has_any_role
from retailedge.invoice_payment_audit import (
	audit_sales_invoice_payment,
	classify_payment_method,
	get_expected_payment_account_for_invoice,
	get_invoice_payment_audit_settings,
	get_payment_entries_for_sales_invoice,
	get_sales_invoice_payment_rows,
)
from retailedge.utils.settings import get_retailedge_settings


PAYMENT_EVIDENCE_MATCHING_ROLES = {
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
FORCE_REMATCH_ROLES = {
	"System Manager",
	"Accounts Manager",
	"RetailEdge Manager",
	"RetailEdgeManager",
}
ACTIVE_MATCH_STATUSES = {
	"Matched for Review",
	"Strong Candidate",
	"Pending Verification",
	"Verified",
	"Approved",
}
INACTIVE_MATCH_STATUSES = {
	"Cancelled",
	"Rejected",
	"Reopened",
	"Ignored",
}


def assert_can_access_payment_evidence_matching(user: str | None = None):
	if user_has_any_role(user=user, roles=PAYMENT_EVIDENCE_MATCHING_ROLES):
		return
	frappe.throw(
		"You do not have permission to access RetailEdge payment evidence matching.",
		frappe.PermissionError,
	)


def get_payment_evidence_matching_settings():
	settings = get_retailedge_settings()
	return {
		"enabled": bool(getattr(settings, "enable_payment_evidence_matching", 1)),
		"match_against_bank_transactions": bool(getattr(settings, "match_against_bank_transactions", 1)),
		"match_against_statement_import_rows": bool(getattr(settings, "match_against_statement_import_rows", 1)),
		"match_against_payment_entries": bool(getattr(settings, "match_against_payment_entries", 1)),
		"match_against_manual_evidence": bool(getattr(settings, "match_against_manual_evidence", 1)),
		"payment_evidence_amount_tolerance": flt(getattr(settings, "payment_evidence_amount_tolerance", 0)),
		"payment_evidence_date_window_days": cint(getattr(settings, "payment_evidence_date_window_days", 3)),
		"require_reference_for_strong_match": bool(getattr(settings, "require_reference_for_strong_match", 0)),
	}


def normalize_payment_reference(reference=None, narration=None):
	original_reference = cstr(reference).strip()
	source = "reference" if original_reference else "empty"
	candidate = original_reference
	if not candidate:
		candidate = cstr(narration).strip()
		source = "narration" if candidate else "empty"
	candidate = re.sub(r"\s+", " ", candidate).upper().strip()
	normalized = re.sub(r"[-/_.\s]+", "", candidate)
	return {
		"original_reference": original_reference or cstr(narration).strip(),
		"normalized_reference": normalized,
		"source": source,
	}


def build_evidence_fingerprint(
	company=None,
	account=None,
	transaction_date=None,
	amount=None,
	reference=None,
	narration=None,
	payment_category=None,
	statement_type=None,
):
	normalized = normalize_payment_reference(reference=reference, narration=narration)
	date_value = str(getdate(transaction_date)) if transaction_date else ""
	amount_value = f"{abs(flt(amount)):.2f}"
	category_value = cstr(payment_category or statement_type).upper().strip()
	basis = {
		"company": cstr(company).strip(),
		"account": cstr(account).strip(),
		"transaction_date": date_value,
		"amount": amount_value,
		"normalized_reference": normalized.get("normalized_reference"),
		"payment_category": category_value,
	}
	weak_ref = normalized.get("normalized_reference")
	if not weak_ref:
		weak_ref = hashlib.sha1(cstr(narration).upper().strip().encode()).hexdigest()[:16]
	parts = [
		basis.get("company"),
		basis.get("account"),
		basis.get("transaction_date"),
		basis.get("amount"),
		weak_ref,
		basis.get("payment_category"),
	]
	return {
		"fingerprint": "|".join(parts),
		"normalized_reference": normalized.get("normalized_reference"),
		"fingerprint_basis": basis,
	}


def detect_duplicate_evidence(
	company=None,
	account=None,
	transaction_date=None,
	amount=None,
	reference=None,
	narration=None,
	payment_category=None,
	statement_type=None,
	exclude_doctype=None,
	exclude_name=None,
):
	fingerprint_meta = build_evidence_fingerprint(
		company=company,
		account=account,
		transaction_date=transaction_date,
		amount=amount,
		reference=reference,
		narration=narration,
		payment_category=payment_category,
		statement_type=statement_type,
	)
	normalized_reference = fingerprint_meta.get("normalized_reference")
	fingerprint = fingerprint_meta.get("fingerprint")
	date_value = str(getdate(transaction_date)) if transaction_date else None
	amount_value = abs(flt(amount))
	window = cint(get_payment_evidence_matching_settings().get("payment_evidence_date_window_days") or 0)
	candidates = []
	for doctype in ("RetailEdge Payment Evidence", "RetailEdge Statement Import Row"):
		if not has_doctype(doctype):
			continue
		fields = _available_fields(
			doctype,
			(
				"name",
				"company",
				"account",
				"transaction_date",
				"evidence_date",
				"amount",
				"reference",
				"evidence_reference",
				"narration",
				"payment_category",
				"statement_type",
				"normalized_reference",
				"evidence_fingerprint",
			),
		)
		filters = {"company": company} if company and "company" in fields else {}
		rows = frappe.get_all(doctype, filters=filters, fields=fields, limit_page_length=200)
		for row in rows:
			if doctype == exclude_doctype and row.get("name") == exclude_name:
				continue
			row_date = row.get("transaction_date") or row.get("evidence_date")
			row_reference = row.get("reference") or row.get("evidence_reference")
			row_normalized = row.get("normalized_reference") or normalize_payment_reference(
				reference=row_reference, narration=row.get("narration")
			).get("normalized_reference")
			row_fingerprint = row.get("evidence_fingerprint") or build_evidence_fingerprint(
				company=row.get("company"),
				account=row.get("account"),
				transaction_date=row_date,
				amount=row.get("amount"),
				reference=row_reference,
				narration=row.get("narration"),
				payment_category=row.get("payment_category"),
				statement_type=row.get("statement_type"),
			).get("fingerprint")
			if row_fingerprint == fingerprint:
				return {
					"duplicate_status": "Rejected Duplicate",
					"duplicate_of": row.get("name"),
					"duplicate_doctype": doctype,
					"duplicate_name": row.get("name"),
					"duplicate_reason": "Duplicate evidence reference detected from earlier upload/import.",
					"fingerprint": fingerprint,
					"normalized_reference": normalized_reference,
				}
			if not normalized_reference or not row_normalized:
				continue
			date_match = False
			if date_value and row_date:
				date_match = abs((getdate(row_date) - getdate(date_value)).days) <= window
			amount_near = abs(abs(flt(row.get("amount"))) - amount_value) <= get_payment_evidence_matching_settings().get(
				"payment_evidence_amount_tolerance", 0
			)
			narration_hit = normalized_reference and normalized_reference in normalize_payment_reference(
				reference=row_reference, narration=row.get("narration")
			).get("normalized_reference", "")
			if row_normalized == normalized_reference and (date_match or amount_near or narration_hit):
				return {
					"duplicate_status": "Duplicate Suspected",
					"duplicate_of": row.get("name"),
					"duplicate_doctype": doctype,
					"duplicate_name": row.get("name"),
					"duplicate_reason": "A similar evidence reference/amount/date combination already exists for review.",
					"fingerprint": fingerprint,
					"normalized_reference": normalized_reference,
				}
	return {
		"duplicate_status": "Unique",
		"duplicate_of": None,
		"duplicate_doctype": None,
		"duplicate_name": None,
		"duplicate_reason": "",
		"fingerprint": fingerprint,
		"normalized_reference": normalized_reference,
	}


def invoice_has_active_payment_evidence_match(invoice_name):
	return bool(get_active_payment_evidence_match(invoice_name))


def get_active_payment_evidence_match(invoice_name):
	if not has_doctype("RetailEdge Payment Evidence Match"):
		return None
	rows = frappe.get_all(
		"RetailEdge Payment Evidence Match",
		filters={"sales_invoice": invoice_name, "match_status": ["in", list(ACTIVE_MATCH_STATUSES)]},
		fields=["name", "sales_invoice", "match_status", "match_confidence", "evidence_type", "evidence_name", "modified"],
		order_by="modified desc",
		limit_page_length=1,
	)
	return rows[0] if rows else None


def normalize_statement_row(raw_row, mapping_template_doc):
	row = frappe._dict(raw_row or {})
	template = frappe._dict(mapping_template_doc.as_dict() if hasattr(mapping_template_doc, "as_dict") else mapping_template_doc or {})
	issues = []
	date_column = cstr(template.get("date_column")).strip()
	ref_column = cstr(template.get("reference_column")).strip()
	narration_column = cstr(template.get("narration_column")).strip()
	debit_credit_mode = cstr(template.get("debit_credit_mode")).strip() or "Signed Amount Column"
	required = [date_column]
	if debit_credit_mode == "Separate Debit/Credit Columns":
		if not template.get("debit_column") and not template.get("credit_column"):
			raise frappe.ValidationError("Mapping template is missing debit/credit columns.")
	elif not template.get("amount_column"):
		raise frappe.ValidationError("Mapping template is missing amount column.")
	for column in required:
		if column and column not in row:
			raise frappe.ValidationError(f"Required statement column '{column}' was not found in the uploaded row.")

	transaction_date = row.get(date_column) if date_column else None
	value_date = row.get(template.get("value_date_column")) if template.get("value_date_column") else None
	reference = row.get(ref_column) if ref_column else None
	narration = row.get(narration_column) if narration_column else None
	debit = credit = 0.0
	amount = 0.0
	direction = "Unknown"
	if debit_credit_mode == "Separate Debit/Credit Columns":
		debit = flt(row.get(template.get("debit_column")))
		credit = flt(row.get(template.get("credit_column")))
		amount = credit if credit > 0 else debit
		direction = "Credit" if credit > 0 else "Debit" if debit > 0 else "Unknown"
	elif debit_credit_mode == "Credit Only Amount Column":
		amount = flt(row.get(template.get("amount_column")))
		credit = amount
		direction = "Credit"
	else:
		signed_amount = flt(row.get(template.get("amount_column")))
		amount = abs(signed_amount)
		if signed_amount > 0:
			credit = signed_amount
			direction = "Credit"
		elif signed_amount < 0:
			debit = abs(signed_amount)
			direction = "Debit"
	normalized = normalize_payment_reference(reference=reference, narration=narration)
	fingerprint_meta = build_evidence_fingerprint(
		company=template.get("company"),
		account=row.get(template.get("account_column")) if template.get("account_column") else template.get("default_account"),
		transaction_date=transaction_date,
		amount=amount,
		reference=reference,
		narration=narration,
		payment_category=template.get("statement_type") or template.get("payment_category"),
		statement_type=template.get("statement_type"),
	)
	return {
		"transaction_date": str(getdate(transaction_date)) if transaction_date else None,
		"value_date": str(getdate(value_date)) if value_date else None,
		"reference": reference,
		"normalized_reference": normalized.get("normalized_reference"),
		"narration": narration,
		"debit": debit,
		"credit": credit,
		"amount": amount,
		"direction": direction,
		"account": row.get(template.get("account_column")) if template.get("account_column") else template.get("default_account"),
		"party": row.get(template.get("party_column")) if template.get("party_column") else None,
		"channel": row.get(template.get("channel_column")) if template.get("channel_column") else None,
		"branch": row.get(template.get("branch_column")) if template.get("branch_column") else None,
		"currency": row.get(template.get("currency_column")) if template.get("currency_column") else None,
		"balance": flt(row.get(template.get("balance_column"))) if template.get("balance_column") else 0.0,
		"payment_category": template.get("statement_type") or template.get("payment_category"),
		"evidence_fingerprint": fingerprint_meta.get("fingerprint"),
		"issues": issues,
	}


def prepare_payment_evidence_doc(doc):
	duplicate_meta = detect_duplicate_evidence(
		company=getattr(doc, "company", None),
		account=getattr(doc, "account", None),
		transaction_date=getattr(doc, "evidence_date", None),
		amount=getattr(doc, "amount", None),
		reference=getattr(doc, "evidence_reference", None),
		narration=getattr(doc, "notes", None),
		payment_category=getattr(doc, "payment_category", None),
		exclude_doctype="RetailEdge Payment Evidence",
		exclude_name=getattr(doc, "name", None),
	)
	doc.normalized_reference = duplicate_meta.get("normalized_reference")
	doc.evidence_fingerprint = duplicate_meta.get("fingerprint")
	doc.duplicate_of = duplicate_meta.get("duplicate_name")
	doc.duplicate_status = duplicate_meta.get("duplicate_status")
	doc.duplicate_reason = duplicate_meta.get("duplicate_reason")


def prepare_statement_import_row_doc(row, parent=None):
	if parent is None and getattr(row, "parenttype", None) and getattr(row, "parent", None):
		try:
			parent = frappe.get_cached_doc(row.parenttype, row.parent)
		except Exception:
			parent = None
	statement_type = getattr(parent, "statement_type", None) or getattr(parent, "payment_category", None)
	duplicate_meta = detect_duplicate_evidence(
		company=getattr(parent, "company", None),
		account=getattr(row, "account", None),
		transaction_date=getattr(row, "transaction_date", None),
		amount=getattr(row, "amount", None),
		reference=getattr(row, "reference", None),
		narration=getattr(row, "narration", None),
		payment_category=getattr(row, "payment_category", None) or statement_type,
		statement_type=statement_type,
		exclude_doctype="RetailEdge Statement Import Row",
		exclude_name=getattr(row, "name", None),
	)
	row.normalized_reference = duplicate_meta.get("normalized_reference")
	row.evidence_fingerprint = duplicate_meta.get("fingerprint")
	row.duplicate_of = duplicate_meta.get("duplicate_name")
	row.duplicate_status = duplicate_meta.get("duplicate_status")
	row.duplicate_reason = duplicate_meta.get("duplicate_reason")
	if duplicate_meta.get("duplicate_status") == "Rejected Duplicate":
		row.match_status = "Ignored"


def validate_payment_statement_import(doc):
	statement_type = getattr(doc, "statement_type", None) or getattr(doc, "payment_category", None)
	if cstr(statement_type).strip().lower() == "cash":
		frappe.throw("Cash is handled through Daily Sales Audit and cash evidence, not bulk bank statement matching.")
	_refresh_payment_statement_import_summary(doc)

def preview_payment_statement_import_rows(import_name, sample_limit=200):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	template = _get_statement_mapping_template(doc)
	raw_rows = _read_statement_import_attachment(doc)
	preview_rows = []
	errors = []
	duplicate_counter = Counter()
	for index, raw_row in enumerate(raw_rows, start=1):
		try:
			normalized = normalize_statement_row(raw_row, template)
			if not _should_include_statement_row(normalized, doc):
				continue
			duplicate_meta = detect_duplicate_evidence(
				company=doc.company,
				account=normalized.get("account"),
				transaction_date=normalized.get("transaction_date"),
				amount=normalized.get("amount"),
				reference=normalized.get("reference"),
				narration=normalized.get("narration"),
				payment_category=normalized.get("payment_category"),
				statement_type=doc.statement_type or doc.payment_category,
			)
			normalized.update(
				{
					"row_index": index,
					"duplicate_status": duplicate_meta.get("duplicate_status"),
					"duplicate_of": duplicate_meta.get("duplicate_name"),
					"duplicate_reason": duplicate_meta.get("duplicate_reason"),
				}
			)
			duplicate_counter[normalized.get("duplicate_status") or "Unique"] += 1
			if not sample_limit or len(preview_rows) < cint(sample_limit):
				preview_rows.append(normalized)
		except Exception as exc:
			errors.append(f"Row {index}: {frappe.safe_decode(str(exc))}")
	total_rows = sum(duplicate_counter.values())
	return {
		"statement_import": doc.name,
		"mapping_template": doc.mapping_template,
		"row_count": total_rows,
		"sample_row_count": len(preview_rows),
		"truncated": bool(sample_limit and total_rows > cint(sample_limit)),
		"duplicate_summary": {
			"unique_count": duplicate_counter.get("Unique", 0),
			"duplicate_suspected_count": duplicate_counter.get("Duplicate Suspected", 0),
			"rejected_duplicate_count": duplicate_counter.get("Rejected Duplicate", 0),
		},
		"rows": preview_rows,
		"errors": errors,
	}


def import_payment_statement_rows(import_name, replace_rows=True):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	preview = preview_payment_statement_import_rows(import_name, sample_limit=0)
	if bool(cint(replace_rows)) if isinstance(replace_rows, str) else bool(replace_rows):
		frappe.db.delete(
			"RetailEdge Statement Import Row",
			{"parent": doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		)
	for row in preview.get("rows") or []:
		child = frappe.get_doc(
			{
				"doctype": "RetailEdge Statement Import Row",
				"parent": doc.name,
				"parenttype": "RetailEdge Payment Statement Import",
				"parentfield": "rows",
				"transaction_date": row.get("transaction_date"),
				"value_date": row.get("value_date"),
				"payment_category": row.get("payment_category"),
				"reference": row.get("reference"),
				"normalized_reference": row.get("normalized_reference"),
				"narration": row.get("narration"),
				"party": row.get("party"),
				"debit": row.get("debit"),
				"credit": row.get("credit"),
				"amount": row.get("amount"),
				"direction": row.get("direction"),
				"account": row.get("account"),
				"channel": row.get("channel"),
				"branch": row.get("branch"),
				"currency": row.get("currency"),
				"balance": row.get("balance"),
				"mapping_template": doc.mapping_template,
				"evidence_fingerprint": row.get("evidence_fingerprint"),
				"duplicate_of": row.get("duplicate_of"),
				"duplicate_status": row.get("duplicate_status"),
				"duplicate_reason": row.get("duplicate_reason"),
				"match_status": "Ignored" if row.get("duplicate_status") == "Rejected Duplicate" else "Pending",
			}
		)
		child.insert(ignore_permissions=True)
	doc.import_status = "Imported"
	_refresh_payment_statement_import_summary(doc, preview=preview)
	doc.save(ignore_permissions=True)
	frappe.db.commit()
	return {
		"statement_import": doc.name,
		"imported_row_count": preview.get("row_count") or 0,
		"errors": preview.get("errors") or [],
	}


def refresh_payment_statement_import_summary(import_name, persist=True):
	doc = frappe.get_doc("RetailEdge Payment Statement Import", import_name)
	_refresh_payment_statement_import_summary(doc)
	if persist:
		doc.save(ignore_permissions=True)
		frappe.db.commit()
	return {
		"statement_import": doc.name,
		"imported_row_count": cint(getattr(doc, "imported_row_count", 0)),
		"unique_row_count": cint(getattr(doc, "unique_row_count", 0)),
		"duplicate_suspected_count": cint(getattr(doc, "duplicate_suspected_count", 0)),
		"rejected_duplicate_count": cint(getattr(doc, "rejected_duplicate_count", 0)),
	}


def _refresh_payment_statement_import_summary(doc, preview=None):
	if not doc:
		return
	if preview is not None:
		duplicate_summary = frappe._dict(preview.get("duplicate_summary") or {})
		doc.imported_row_count = cint(preview.get("row_count") or 0)
		doc.unique_row_count = cint(duplicate_summary.get("unique_count") or 0)
		doc.duplicate_suspected_count = cint(duplicate_summary.get("duplicate_suspected_count") or 0)
		doc.rejected_duplicate_count = cint(duplicate_summary.get("rejected_duplicate_count") or 0)
		doc.import_summary_note = (
			f"Rows: {doc.imported_row_count} | "
			f"Unique: {doc.unique_row_count} | "
			f"Duplicate Suspected: {doc.duplicate_suspected_count} | "
			f"Rejected Duplicates: {doc.rejected_duplicate_count}"
		)
		return
	if not getattr(doc, "name", None):
		doc.imported_row_count = 0
		doc.unique_row_count = 0
		doc.duplicate_suspected_count = 0
		doc.rejected_duplicate_count = 0
		doc.import_summary_note = None
		return
	rows = frappe.get_all(
		"RetailEdge Statement Import Row",
		filters={"parent": doc.name, "parenttype": "RetailEdge Payment Statement Import"},
		fields=["duplicate_status"],
		limit_page_length=5000,
	)
	counter = Counter((row.get("duplicate_status") or "Unique") for row in rows)
	doc.imported_row_count = len(rows)
	doc.unique_row_count = counter.get("Unique", 0)
	doc.duplicate_suspected_count = counter.get("Duplicate Suspected", 0)
	doc.rejected_duplicate_count = counter.get("Rejected Duplicate", 0)
	doc.import_summary_note = (
		f"Rows: {doc.imported_row_count} | "
		f"Unique: {doc.unique_row_count} | "
		f"Duplicate Suspected: {doc.duplicate_suspected_count} | "
		f"Rejected Duplicates: {doc.rejected_duplicate_count}"
	)


def match_payment_evidence_for_invoice(invoice_name, create_match_records=False, force_rematch=False):
	settings = get_payment_evidence_matching_settings()
	force_rematch = bool(cint(force_rematch)) if isinstance(force_rematch, str) else bool(force_rematch)
	active_match = get_active_payment_evidence_match(invoice_name)
	if active_match and not force_rematch:
		return {
			"invoice": invoice_name,
			"company": active_match.get("company"),
			"branch": active_match.get("branch"),
			"customer": None,
			"posting_date": None,
			"grand_total": 0.0,
			"paid_amount": 0.0,
			"outstanding_amount": 0.0,
			"payment_audit_status": "Already Matched",
			"risk_level": "Low",
			"matches": [],
			"unmatched_payments": [],
			"duplicate_suspicions": [],
			"messages": [
				"Invoice already has an active evidence match. Reopen, cancel, reject, or ignore the existing match before duplicate audit."
			],
		}
	if active_match and force_rematch:
		_assert_force_rematch_allowed()

	invoice_audit = audit_sales_invoice_payment(invoice_name)
	invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)
	payment_rows = get_sales_invoice_payment_rows(invoice_doc)
	payment_entries = get_payment_entries_for_sales_invoice(invoice_name) if settings["match_against_payment_entries"] else []
	matches = []
	messages = list(invoice_audit.get("messages") or [])
	duplicate_suspicions = []
	seen_duplicate_keys = Counter()

	if settings["match_against_payment_entries"]:
		for payment_entry in payment_entries:
			match = _match_against_payment_entry(invoice_doc, invoice_audit, payment_rows, payment_entry, settings, payment_entries)
			matches.append(match)
			_track_duplicate_key(match, seen_duplicate_keys)

	if settings.get("match_against_statement_import_rows"):
		for match in _match_against_statement_import_rows(
			invoice_doc, invoice_audit, payment_rows, payment_entries, settings, messages, seen_duplicate_keys
		):
			matches.append(match)
			_track_duplicate_key(match, seen_duplicate_keys)

	if settings["match_against_bank_transactions"]:
		for match in _match_against_bank_transactions(
			invoice_doc, invoice_audit, payment_rows, payment_entries, settings, messages, seen_duplicate_keys
		):
			matches.append(match)
			_track_duplicate_key(match, seen_duplicate_keys)

	if settings["match_against_manual_evidence"]:
		for match in _match_against_manual_evidence(
			invoice_doc, invoice_audit, payment_rows, payment_entries, settings, seen_duplicate_keys
		):
			matches.append(match)
			_track_duplicate_key(match, seen_duplicate_keys)

	for match in matches:
		key = _match_duplicate_key(match)
		if key and seen_duplicate_keys.get(key, 0) > 1:
			match["duplicate_status"] = "Duplicate Suspected"
			match["duplicate_suspected"] = 1
			match["match_status"] = "Duplicate Suspected"
			match["issue_summary"] = _append_issue(match.get("issue_summary"), "Potential duplicate evidence match detected.")
			match["duplicate_reason"] = _append_issue(match.get("duplicate_reason"), "Potential duplicate evidence match detected.")
			duplicate_suspicions.append(
				{
					"evidence_type": match.get("evidence_type"),
					"evidence_name": match.get("evidence_name"),
					"reference": match.get("reference"),
					"payment_amount": match.get("payment_amount"),
				}
			)

	unmatched_payments = _build_unmatched_payment_rows(payment_rows, matches)
	if create_match_records:
		_persist_payment_evidence_match_records(invoice_audit, matches, force_rematch=force_rematch)

	return {
		"invoice": invoice_name,
		"company": invoice_audit.get("company"),
		"branch": invoice_audit.get("branch"),
		"customer": invoice_audit.get("customer"),
		"posting_date": invoice_audit.get("posting_date"),
		"grand_total": invoice_audit.get("grand_total"),
		"paid_amount": invoice_audit.get("paid_amount"),
		"outstanding_amount": invoice_audit.get("outstanding_amount"),
		"payment_audit_status": invoice_audit.get("payment_audit_status"),
		"risk_level": invoice_audit.get("payment_risk_level"),
		"matches": matches,
		"unmatched_payments": unmatched_payments,
		"duplicate_suspicions": duplicate_suspicions,
		"messages": list(dict.fromkeys(messages)),
	}


def get_payment_evidence_match_list(filters=None, limit=500):
	filters = frappe._dict(filters or {})
	rows = []
	candidate_invoices = _get_candidate_invoices(filters, limit=limit)
	for invoice_row in candidate_invoices:
		if not cint(filters.get("include_already_matched")) and invoice_has_active_payment_evidence_match(invoice_row.get("name")):
			continue
		result = match_payment_evidence_for_invoice(invoice_row.get("name"), create_match_records=False)
		for match in result.get("matches") or []:
			summary_row = _summarise_match_row(result, match)
			if _row_filtered_out(summary_row, filters):
				continue
			rows.append(summary_row)
		if not result.get("matches"):
			for unmatched in result.get("unmatched_payments") or []:
				row = _summarise_unmatched_row(result, unmatched)
				if _row_filtered_out(row, filters):
					continue
				rows.append(row)
	rows = _flag_duplicate_evidence_rows(rows)
	return rows[: cint(limit or 500)]


def get_payment_evidence_match_summary(filters=None):
	rows = get_payment_evidence_match_list(filters=filters, limit=(frappe._dict(filters or {})).get("limit") or 500)
	summary = {
		"invoice_count": 0,
		"matched_invoice_count": 0,
		"unmatched_invoice_count": 0,
		"strong_candidate_count": 0,
		"weak_candidate_count": 0,
		"duplicate_suspected_count": 0,
		"bank_transaction_match_count": 0,
		"payment_entry_match_count": 0,
		"manual_evidence_match_count": 0,
		"high_confidence_count": 0,
		"medium_confidence_count": 0,
		"low_confidence_count": 0,
	}
	invoice_state = {}
	for row in rows:
		invoice = row.get("sales_invoice")
		invoice_state.setdefault(invoice, {"matched": False, "unmatched": False})
		status = row.get("match_status")
		confidence = row.get("match_confidence")
		if status == "Strong Candidate":
			summary["strong_candidate_count"] += 1
			invoice_state[invoice]["matched"] = True
		elif status in {"Weak Candidate", "No Match"}:
			summary["weak_candidate_count"] += 1
			invoice_state[invoice]["unmatched"] = True
		elif status == "Duplicate Suspected":
			summary["duplicate_suspected_count"] += 1
			invoice_state[invoice]["matched"] = True
		else:
			invoice_state[invoice]["matched"] = True
		if row.get("evidence_type") == "Bank Transaction":
			summary["bank_transaction_match_count"] += 1
		elif row.get("evidence_type") == "Payment Entry":
			summary["payment_entry_match_count"] += 1
		elif row.get("evidence_type") == "RetailEdge Payment Evidence":
			summary["manual_evidence_match_count"] += 1
		if confidence == "High":
			summary["high_confidence_count"] += 1
		elif confidence == "Medium":
			summary["medium_confidence_count"] += 1
		else:
			summary["low_confidence_count"] += 1
	summary["invoice_count"] = len(invoice_state)
	for state in invoice_state.values():
		if state["matched"]:
			summary["matched_invoice_count"] += 1
		if state["unmatched"] or not state["matched"]:
			summary["unmatched_invoice_count"] += 1
	return summary


def _match_against_payment_entry(invoice_doc, invoice_audit, payment_rows, payment_entry, settings, payment_entries):
	category_info = classify_payment_method(
		mode_of_payment=payment_entry.get("mode_of_payment"),
		account=payment_entry.get("paid_to") or payment_entry.get("paid_from"),
	)
	expected = get_expected_payment_account_for_invoice(
		invoice_doc,
		payment_category=category_info.get("category"),
		mode_of_payment=payment_entry.get("mode_of_payment"),
	)
	evidence_amount = flt(payment_entry.get("reference_allocated_amount") or payment_entry.get("received_amount") or payment_entry.get("paid_amount"))
	payment_amount = _get_expected_payment_amount(
		payment_rows,
		category_info.get("category"),
		fallback_amount=evidence_amount,
		account=payment_entry.get("paid_to") or payment_entry.get("paid_from"),
	)
	return _build_match_row(
		invoice_doc=invoice_doc,
		invoice_audit=invoice_audit,
		evidence_type="Payment Entry",
		evidence_doctype="Payment Entry",
		evidence_name=payment_entry.get("payment_entry"),
		payment_category=category_info.get("category"),
		payment_amount=payment_amount,
		evidence_amount=evidence_amount,
		evidence_date=payment_entry.get("posting_date"),
		reference_text=payment_entry.get("payment_entry"),
		narration_text=" ".join(part for part in [payment_entry.get("payment_entry"), payment_entry.get("party")] if part),
		account=payment_entry.get("paid_to") or payment_entry.get("paid_from"),
		expected_account=expected.get("account"),
		party=payment_entry.get("party"),
		settings=settings,
		payment_entries=payment_entries,
		reference_match=True,
		statement_import=None,
		mapping_template=None,
	)


def _match_against_bank_transactions(invoice_doc, invoice_audit, payment_rows, payment_entries, settings, messages, seen_duplicate_keys):
	if not _has_non_cash_payment_rows(payment_rows):
		messages.append("Cash payment rows are excluded from bank statement matching.")
		return []
	if not has_doctype("Bank Transaction"):
		messages.append("Bank Transaction is not available on this site, so bank evidence matching was skipped.")
		return []
	fields = _available_fields(
		"Bank Transaction",
		(
			"name",
			"company",
			"date",
			"posting_date",
			"transaction_date",
			"bank_account",
			"account",
			"withdrawal",
			"deposit",
			"description",
			"reference_number",
			"party",
			"party_name",
		),
	)
	query_filters = {}
	if invoice_audit.get("company") and "company" in fields:
		query_filters["company"] = invoice_audit.get("company")
	date_field = _first_existing_field("Bank Transaction", ("date", "posting_date", "transaction_date"))
	if date_field and invoice_audit.get("posting_date"):
		start_date, end_date = _date_window(invoice_audit.get("posting_date"), settings)
		query_filters[date_field] = ["between", [start_date, end_date]]
	try:
		rows = frappe.get_all("Bank Transaction", filters=query_filters, fields=fields, limit_page_length=100, order_by=f"{date_field or 'modified'} desc")
	except Exception as exc:
		messages.append(f"Bank Transaction matching was skipped: {exc}")
		return []
	results = []
	for row in rows:
		evidence_amount = flt(row.get("deposit") or row.get("withdrawal"))
		if evidence_amount <= 0:
			continue
		best_category = _best_payment_category(payment_rows, row.get("account") or row.get("bank_account"))
		if best_category == "Cash":
			continue
		payment_amount = _get_expected_payment_amount(
			payment_rows,
			best_category,
			fallback_amount=evidence_amount,
			account=row.get("account") or row.get("bank_account"),
		)
		expected = get_expected_payment_account_for_invoice(invoice_doc, payment_category=best_category)
		reference_text = row.get("reference_number")
		narration_text = " ".join(
			part for part in [row.get("description"), row.get("reference_number"), row.get("party"), row.get("party_name")] if part
		)
		match = _build_match_row(
			invoice_doc=invoice_doc,
			invoice_audit=invoice_audit,
			evidence_type="Bank Transaction",
			evidence_doctype="Bank Transaction",
			evidence_name=row.get("name"),
			payment_category=best_category,
			payment_amount=payment_amount,
			evidence_amount=evidence_amount,
			evidence_date=row.get(date_field) if date_field else None,
			reference_text=reference_text,
			narration_text=narration_text,
			account=row.get("account") or row.get("bank_account"),
			expected_account=expected.get("account"),
			party=row.get("party") or row.get("party_name"),
			settings=settings,
			payment_entries=payment_entries,
			reference_match=_reference_matches(reference_text, narration_text, invoice_doc, payment_entries),
		)
		results.append(match)
	return results


def _match_against_statement_import_rows(invoice_doc, invoice_audit, payment_rows, payment_entries, settings, messages, seen_duplicate_keys):
	if not _has_non_cash_payment_rows(payment_rows):
		messages.append("Cash payment rows are excluded from statement import matching.")
		return []
	if not has_doctype("RetailEdge Statement Import Row"):
		messages.append("Payment Statement Import rows are not available on this site, so structured statement matching was skipped.")
		return []
	query_filters = {"parenttype": "RetailEdge Payment Statement Import"}
	if invoice_audit.get("posting_date") and has_field("RetailEdge Statement Import Row", "transaction_date"):
		start_date, end_date = _date_window(invoice_audit.get("posting_date"), settings)
		query_filters["transaction_date"] = ["between", [start_date, end_date]]
	if has_field("RetailEdge Statement Import Row", "duplicate_status"):
		query_filters["duplicate_status"] = ["!=", "Rejected Duplicate"]
	fields = _available_fields(
		"RetailEdge Statement Import Row",
		(
			"name",
			"parent",
			"transaction_date",
			"value_date",
			"payment_category",
			"reference",
			"normalized_reference",
			"narration",
			"party",
			"amount",
			"account",
			"payment_entry",
			"sales_invoice",
			"match_status",
			"duplicate_status",
			"duplicate_of",
			"duplicate_reason",
			"evidence_fingerprint",
			"direction",
			"mapping_template",
		),
	)
	try:
		rows = frappe.get_all(
			"RetailEdge Statement Import Row",
			filters=query_filters,
			fields=fields,
			limit_page_length=200,
			order_by="transaction_date desc, creation desc",
		)
	except Exception as exc:
		messages.append(f"Statement import matching was skipped: {exc}")
		return []
	results = []
	for row in rows:
		if row.get("direction") and row.get("direction") != "Credit":
			continue
		category = row.get("payment_category") or _best_payment_category(payment_rows, row.get("account"))
		if category == "Cash":
			continue
		payment_amount = _get_expected_payment_amount(
			payment_rows,
			category,
			fallback_amount=flt(row.get("amount")),
			account=row.get("account"),
		)
		expected = get_expected_payment_account_for_invoice(invoice_doc, payment_category=category)
		reference_match = False
		if row.get("sales_invoice") == invoice_doc.name:
			reference_match = True
		elif row.get("payment_entry") and any(item.get("payment_entry") == row.get("payment_entry") for item in payment_entries):
			reference_match = True
		else:
			reference_match = _reference_matches(row.get("reference"), row.get("narration"), invoice_doc, payment_entries)
		match = _build_match_row(
			invoice_doc=invoice_doc,
			invoice_audit=invoice_audit,
			evidence_type="Statement Import Row",
			evidence_doctype="RetailEdge Statement Import Row",
			evidence_name=row.get("name"),
			payment_category=category,
			payment_amount=payment_amount,
			evidence_amount=flt(row.get("amount")),
			evidence_date=row.get("transaction_date"),
			reference_text=row.get("reference"),
			narration_text=row.get("narration"),
			account=row.get("account"),
			expected_account=expected.get("account"),
			party=row.get("party"),
			settings=settings,
			payment_entries=payment_entries,
			reference_match=reference_match,
			normalized_reference=row.get("normalized_reference"),
			evidence_fingerprint=row.get("evidence_fingerprint"),
			duplicate_status=row.get("duplicate_status"),
			duplicate_of=row.get("duplicate_of"),
			duplicate_reason=row.get("duplicate_reason"),
			statement_import=row.get("parent"),
			mapping_template=row.get("mapping_template"),
			statement_import_row=row.get("name"),
		)
		results.append(match)
	return results


def _match_against_manual_evidence(invoice_doc, invoice_audit, payment_rows, payment_entries, settings, seen_duplicate_keys):
	if not has_doctype("RetailEdge Payment Evidence"):
		return []
	query_filters = {"company": invoice_audit.get("company")}
	if invoice_audit.get("branch") and has_field("RetailEdge Payment Evidence", "branch"):
		query_filters["branch"] = invoice_audit.get("branch")
	if has_field("RetailEdge Payment Evidence", "evidence_date") and invoice_audit.get("posting_date"):
		start_date, end_date = _date_window(invoice_audit.get("posting_date"), settings)
		query_filters["evidence_date"] = ["between", [start_date, end_date]]
	if has_field("RetailEdge Payment Evidence", "duplicate_status"):
		query_filters["duplicate_status"] = ["!=", "Rejected Duplicate"]
	try:
		rows = frappe.get_all(
			"RetailEdge Payment Evidence",
			filters=query_filters,
			fields=_available_fields(
				"RetailEdge Payment Evidence",
				(
					"name",
					"company",
					"branch",
					"evidence_date",
					"payment_category",
					"evidence_reference",
					"normalized_reference",
					"party",
					"party_type",
					"amount",
					"account",
					"payment_entry",
					"sales_invoice",
					"evidence_status",
					"duplicate_status",
					"duplicate_of",
					"duplicate_reason",
					"evidence_fingerprint",
				),
			),
			limit_page_length=100,
			order_by="evidence_date desc, creation desc",
		)
	except Exception:
		return []
	results = []
	for row in rows:
		category = row.get("payment_category") or _best_payment_category(payment_rows, row.get("account"))
		payment_amount = _get_expected_payment_amount(
			payment_rows,
			category,
			fallback_amount=flt(row.get("amount")),
			account=row.get("account"),
		)
		expected = get_expected_payment_account_for_invoice(invoice_doc, payment_category=category)
		if row.get("sales_invoice") == invoice_doc.name:
			reference_match = True
		elif row.get("payment_entry") and any(item.get("payment_entry") == row.get("payment_entry") for item in payment_entries):
			reference_match = True
		else:
			reference_match = _reference_matches(row.get("evidence_reference"), None, invoice_doc, payment_entries)
		match = _build_match_row(
			invoice_doc=invoice_doc,
			invoice_audit=invoice_audit,
			evidence_type="RetailEdge Payment Evidence",
			evidence_doctype="RetailEdge Payment Evidence",
			evidence_name=row.get("name"),
			payment_category=category,
			payment_amount=payment_amount,
			evidence_amount=flt(row.get("amount")),
			evidence_date=row.get("evidence_date"),
			reference_text=row.get("evidence_reference"),
			narration_text=None,
			account=row.get("account"),
			expected_account=expected.get("account"),
			party=row.get("party"),
			settings=settings,
			payment_entries=payment_entries,
			reference_match=reference_match,
			normalized_reference=row.get("normalized_reference"),
			evidence_fingerprint=row.get("evidence_fingerprint"),
			duplicate_status=row.get("duplicate_status"),
			duplicate_of=row.get("duplicate_of"),
			duplicate_reason=row.get("duplicate_reason"),
		)
		results.append(match)
	return results


def _build_match_row(
	invoice_doc,
	invoice_audit,
	evidence_type,
	evidence_doctype,
	evidence_name,
	payment_category,
	payment_amount,
	evidence_amount,
	evidence_date,
	reference_text,
	narration_text,
	account,
	expected_account,
	party,
	settings,
	payment_entries,
	reference_match=False,
	normalized_reference=None,
	evidence_fingerprint=None,
	duplicate_status=None,
	duplicate_of=None,
	duplicate_reason=None,
	statement_import=None,
	mapping_template=None,
	statement_import_row=None,
):
	tolerance = flt(settings.get("payment_evidence_amount_tolerance"))
	payment_amount = flt(payment_amount)
	evidence_amount = flt(evidence_amount)
	amount_difference = abs(payment_amount - evidence_amount)
	amount_match = amount_difference <= tolerance
	date_match = _dates_within_window(invoice_audit.get("posting_date"), evidence_date, settings)
	account_match = None if not expected_account else cstr(account) == cstr(expected_account)
	party_match = _party_matches(invoice_doc, party) or _customer_in_text(invoice_doc, narration_text) or _customer_in_text(invoice_doc, reference_text)
	narration_reference_match = _narration_contains_invoice_or_payment_entry(narration_text, invoice_doc, payment_entries)
	if normalized_reference is None:
		normalized_reference = normalize_payment_reference(reference=reference_text, narration=narration_text).get("normalized_reference")
	if evidence_fingerprint is None:
		evidence_fingerprint = build_evidence_fingerprint(
			company=invoice_audit.get("company"),
			account=account,
			transaction_date=evidence_date,
			amount=evidence_amount,
			reference=reference_text,
			narration=narration_text,
			payment_category=payment_category,
		).get("fingerprint")
	score = 0
	score += 40 if reference_match else 0
	score += 30 if amount_match else 0
	score += 10 if date_match else 0
	score += 10 if account_match else 0
	score += 10 if party_match else 0
	score += 20 if narration_reference_match else 0
	confidence = "High" if score >= 75 else "Medium" if score >= 50 else "Low"
	status = "No Match" if score == 0 else "Weak Candidate" if score < 75 else "Strong Candidate"
	strong_combo = amount_match and (reference_match or (date_match and party_match and account_match is not False and score >= 60))
	if not strong_combo and status == "Strong Candidate":
		status = "Weak Candidate"
	if score and status == "No Match":
		status = "Candidate"
	if settings.get("require_reference_for_strong_match") and not reference_match and status == "Strong Candidate":
		status = "Weak Candidate"
	duplicate_status = duplicate_status or "Unique"
	duplicate_suspected = 0
	if duplicate_status == "Rejected Duplicate":
		status = "Duplicate Suspected"
		confidence = "Low"
		duplicate_suspected = 1
	elif duplicate_status == "Duplicate Suspected":
		status = "Duplicate Suspected"
		confidence = "Medium" if confidence == "High" else confidence
		duplicate_suspected = 1
	issue_summary = []
	if not amount_match:
		issue_summary.append("Amount does not match within tolerance.")
	if not date_match:
		issue_summary.append("Evidence date is outside the configured matching window.")
	if account_match is False:
		issue_summary.append("Evidence account does not match the expected payment account.")
	if not reference_match and settings.get("require_reference_for_strong_match"):
		issue_summary.append("No strong reference match was found.")
	if not party_match:
		issue_summary.append("Party does not clearly match the invoice customer.")
	if duplicate_reason:
		issue_summary.append(duplicate_reason)
	return {
		"evidence_type": evidence_type,
		"evidence_doctype": evidence_doctype,
		"evidence_name": evidence_name,
		"payment_category": payment_category,
		"payment_amount": payment_amount,
		"evidence_amount": evidence_amount,
		"amount_difference": amount_difference,
		"reference_match": bool(reference_match),
		"amount_match": bool(amount_match),
		"date_match": bool(date_match),
		"account_match": account_match,
		"party_match": bool(party_match),
		"match_score": score,
		"match_confidence": confidence,
		"match_status": status,
		"issue_summary": "; ".join(issue_summary),
		"reference": reference_text,
		"normalized_reference": normalized_reference,
		"evidence_fingerprint": evidence_fingerprint,
		"account": account,
		"expected_account": expected_account,
		"evidence_date": evidence_date,
		"duplicate_status": duplicate_status,
		"duplicate_of": duplicate_of,
		"duplicate_reason": duplicate_reason,
		"duplicate_suspected": duplicate_suspected,
		"already_matched_invoice": 0,
		"force_rematch": 0,
		"mapping_template": mapping_template,
		"statement_import": statement_import,
		"statement_import_row": statement_import_row,
	}


def _build_unmatched_payment_rows(payment_rows, matches):
	matched_categories = Counter()
	for match in matches:
		if match.get("match_status") in {"Strong Candidate", "Candidate", "Matched for Review"}:
			matched_categories[match.get("payment_category")] += 1
	rows = []
	for row in payment_rows:
		category = row.get("payment_category")
		if matched_categories.get(category):
			matched_categories[category] -= 1
			continue
		rows.append(
			{
				"payment_category": category,
				"payment_amount": flt(row.get("base_amount") or row.get("amount")),
				"account": row.get("account"),
				"mode_of_payment": row.get("mode_of_payment"),
			}
		)
	return rows


def _summarise_match_row(result, match):
	return {
		"sales_invoice": result.get("invoice"),
		"posting_date": result.get("posting_date"),
		"company": result.get("company"),
		"branch": result.get("branch"),
		"customer": result.get("customer"),
		"payment_category": match.get("payment_category"),
		"payment_amount": match.get("payment_amount"),
		"evidence_type": match.get("evidence_type"),
		"evidence_document": match.get("evidence_name"),
		"evidence_amount": match.get("evidence_amount"),
		"amount_difference": match.get("amount_difference"),
		"reference_match": cint(match.get("reference_match")),
		"amount_match": cint(match.get("amount_match")),
		"date_match": cint(match.get("date_match")),
		"account_match": 1 if match.get("account_match") is True else 0 if match.get("account_match") is False else None,
		"party_match": cint(match.get("party_match")),
		"match_score": match.get("match_score"),
		"match_confidence": match.get("match_confidence"),
		"match_status": match.get("match_status"),
		"issue_summary": match.get("issue_summary"),
		"evidence_key": _match_duplicate_key(match),
		"normalized_reference": match.get("normalized_reference"),
		"evidence_fingerprint": match.get("evidence_fingerprint"),
		"duplicate_status": match.get("duplicate_status"),
		"duplicate_of": match.get("duplicate_of"),
		"already_matched_invoice": cint(match.get("already_matched_invoice")),
		"mapping_template": match.get("mapping_template"),
		"statement_import": match.get("statement_import"),
		"statement_import_row": match.get("statement_import_row"),
	}


def _summarise_unmatched_row(result, unmatched):
	return {
		"sales_invoice": result.get("invoice"),
		"posting_date": result.get("posting_date"),
		"company": result.get("company"),
		"branch": result.get("branch"),
		"customer": result.get("customer"),
		"payment_category": unmatched.get("payment_category"),
		"payment_amount": unmatched.get("payment_amount"),
		"evidence_type": None,
		"evidence_document": None,
		"evidence_amount": 0.0,
		"amount_difference": unmatched.get("payment_amount"),
		"reference_match": 0,
		"amount_match": 0,
		"date_match": 0,
		"account_match": None,
		"party_match": 0,
		"match_score": 0,
		"match_confidence": "Low",
		"match_status": "No Match",
		"issue_summary": "No candidate evidence matched this payment row.",
		"evidence_key": None,
		"normalized_reference": None,
		"evidence_fingerprint": None,
		"duplicate_status": "Unique",
		"duplicate_of": None,
		"already_matched_invoice": 0,
		"mapping_template": None,
		"statement_import": None,
		"statement_import_row": None,
	}


def _persist_payment_evidence_match_records(invoice_audit, matches, force_rematch=False):
	if not has_doctype("RetailEdge Payment Evidence Match"):
		return
	for match in matches:
		if match.get("match_status") == "No Match":
			continue
		existing = frappe.get_all(
			"RetailEdge Payment Evidence Match",
			filters={
				"sales_invoice": invoice_audit.get("invoice"),
				"evidence_doctype": match.get("evidence_doctype"),
				"evidence_name": match.get("evidence_name"),
				"match_status": ["not in", list(INACTIVE_MATCH_STATUSES)],
			},
			fields=["name"],
			limit_page_length=1,
		)
		if existing and not force_rematch:
			continue
		doc = frappe.new_doc("RetailEdge Payment Evidence Match")
		doc.company = invoice_audit.get("company")
		doc.branch = invoice_audit.get("branch")
		doc.sales_invoice = invoice_audit.get("invoice")
		doc.evidence_type = match.get("evidence_type")
		doc.evidence_doctype = match.get("evidence_doctype")
		doc.evidence_name = match.get("evidence_name")
		doc.invoice_amount = invoice_audit.get("grand_total")
		doc.payment_amount = match.get("payment_amount")
		doc.evidence_amount = match.get("evidence_amount")
		doc.amount_difference = match.get("amount_difference")
		doc.invoice_date = invoice_audit.get("posting_date")
		doc.evidence_date = match.get("evidence_date")
		doc.reference_match = cint(match.get("reference_match"))
		doc.amount_match = cint(match.get("amount_match"))
		doc.date_match = cint(match.get("date_match"))
		doc.account_match = 1 if match.get("account_match") is True else 0 if match.get("account_match") is False else None
		doc.party_match = cint(match.get("party_match"))
		doc.match_score = cint(match.get("match_score"))
		doc.match_confidence = match.get("match_confidence")
		doc.match_status = match.get("match_status")
		doc.issue_summary = match.get("issue_summary")
		doc.duplicate_suspected = cint(match.get("duplicate_suspected"))
		doc.duplicate_reason = match.get("duplicate_reason")
		doc.already_matched_invoice = cint(match.get("already_matched_invoice"))
		doc.force_rematch = cint(force_rematch)
		doc.details_json = json.dumps(match, default=str)
		doc.insert(ignore_permissions=True)
	frappe.db.commit()


def _get_candidate_invoices(filters, limit=500):
	settings = get_invoice_payment_audit_settings()
	query_filters = {}
	if settings.get("include_draft_invoices"):
		query_filters["docstatus"] = ["in", [0, 1]]
	else:
		query_filters["docstatus"] = 1
	if settings.get("include_cancelled_invoices") or cint(filters.get("include_cancelled")):
		query_filters["docstatus"] = ["in", [0, 1, 2]] if settings.get("include_draft_invoices") else ["in", [1, 2]]
	for fieldname in ("company", "customer", "pos_profile"):
		if filters.get(fieldname) and has_field("Sales Invoice", fieldname):
			query_filters[fieldname] = filters.get(fieldname)
	if filters.get("sales_invoice"):
		query_filters["name"] = filters.get("sales_invoice")
	_apply_date_filter(query_filters, filters)
	fields = ["name", "company", "customer", "posting_date"]
	for fieldname in ("retailedge_branch", "branch"):
		if has_field("Sales Invoice", fieldname):
			fields.append(fieldname)
	rows = frappe.get_all(
		"Sales Invoice",
		filters=query_filters,
		fields=fields,
		limit_page_length=cint(limit or 500),
		order_by="posting_date desc, creation desc",
	)
	if not filters.get("branch"):
		return rows
	return [row for row in rows if (row.get("retailedge_branch") or row.get("branch")) == filters.get("branch")]


def _available_fields(doctype, fieldnames):
	return [fieldname for fieldname in fieldnames if fieldname == "name" or has_field(doctype, fieldname)]


def _first_existing_field(doctype, fieldnames):
	for fieldname in fieldnames:
		if has_field(doctype, fieldname):
			return fieldname
	return None


def _date_window(base_date, settings):
	date_window = cint(settings.get("payment_evidence_date_window_days") or 0)
	base = getdate(base_date)
	return str(base - timedelta(days=date_window)), str(base + timedelta(days=date_window))


def _dates_within_window(invoice_date, evidence_date, settings):
	if not invoice_date or not evidence_date:
		return False
	window = cint(settings.get("payment_evidence_date_window_days") or 0)
	return abs((getdate(evidence_date) - getdate(invoice_date)).days) <= window


def _reference_matches(reference_text, narration_text, invoice_doc, payment_entries):
	candidate = " ".join(part for part in [reference_text, narration_text] if part)
	text = normalize_payment_reference(reference=candidate).get("normalized_reference")
	if not text:
		return False
	if normalize_payment_reference(reference=invoice_doc.name).get("normalized_reference") in text:
		return True
	for payment_entry in payment_entries or []:
		entry_name = payment_entry.get("payment_entry")
		if entry_name and normalize_payment_reference(reference=entry_name).get("normalized_reference") in text:
			return True
	return False


def _party_matches(invoice_doc, party):
	if not party:
		return False
	return cstr(getattr(invoice_doc, "customer", None)).lower() == cstr(party).lower()


def _customer_in_text(invoice_doc, text):
	if not text:
		return False
	return normalize_payment_reference(reference=getattr(invoice_doc, "customer", None)).get("normalized_reference") in normalize_payment_reference(
		reference=text
	).get("normalized_reference", "")


def _narration_contains_invoice_or_payment_entry(narration_text, invoice_doc, payment_entries):
	if not narration_text:
		return False
	narration_normalized = normalize_payment_reference(reference=narration_text).get("normalized_reference")
	if normalize_payment_reference(reference=invoice_doc.name).get("normalized_reference") in narration_normalized:
		return True
	for payment_entry in payment_entries or []:
		entry_name = payment_entry.get("payment_entry")
		if entry_name and normalize_payment_reference(reference=entry_name).get("normalized_reference") in narration_normalized:
			return True
	return False


def _best_payment_category(payment_rows, account=None):
	if payment_rows:
		for row in payment_rows:
			if account and row.get("account") and cstr(row.get("account")).lower() == cstr(account).lower():
				return row.get("payment_category") or "Other"
		return payment_rows[0].get("payment_category") or "Other"
	return classify_payment_method(account=account).get("category")


def _has_non_cash_payment_rows(payment_rows):
	return any((row.get("payment_category") or "Other") != "Cash" for row in (payment_rows or []))


def _get_expected_payment_amount(payment_rows, payment_category, fallback_amount, account=None):
	for row in payment_rows or []:
		row_amount = flt(row.get("base_amount") if row.get("base_amount") is not None else row.get("amount"))
		if row_amount <= 0:
			continue
		if account and row.get("account") and cstr(row.get("account")).lower() == cstr(account).lower():
			return row_amount
		if payment_category and row.get("payment_category") == payment_category:
			return row_amount
	return flt(fallback_amount)


def _match_duplicate_key(match):
	fingerprint = cstr(match.get("evidence_fingerprint")).strip()
	return fingerprint or None


def _append_issue(existing, new_issue):
	if not existing:
		return new_issue
	if not new_issue or new_issue in existing:
		return existing
	return f"{existing}; {new_issue}"


def _flag_duplicate_evidence_rows(rows):
	by_evidence = {}
	for row in rows:
		key = row.get("evidence_key")
		if not key:
			continue
		by_evidence.setdefault(key, set()).add(row.get("sales_invoice"))
	for row in rows:
		key = row.get("evidence_key")
		if key and len(by_evidence.get(key, set())) > 1:
			row["match_status"] = "Duplicate Suspected"
			row["duplicate_status"] = row.get("duplicate_status") or "Duplicate Suspected"
			row["issue_summary"] = _append_issue(row.get("issue_summary"), "Potential duplicate evidence match detected.")
	return rows


def _row_filtered_out(row, filters):
	if filters.get("payment_category") and row.get("payment_category") != filters.get("payment_category"):
		return True
	if filters.get("match_confidence") and row.get("match_confidence") != filters.get("match_confidence"):
		return True
	if filters.get("match_status") and row.get("match_status") != filters.get("match_status"):
		return True
	if filters.get("duplicate_status") and row.get("duplicate_status") != filters.get("duplicate_status"):
		return True
	if filters.get("statement_import") and row.get("statement_import") != filters.get("statement_import"):
		return True
	if filters.get("mapping_template") and row.get("mapping_template") != filters.get("mapping_template"):
		return True
	if cint(filters.get("only_unmatched")) and row.get("match_status") not in {"No Match", "Weak Candidate"}:
		return True
	if cint(filters.get("only_duplicates")) and row.get("match_status") != "Duplicate Suspected":
		return True
	if not cint(filters.get("include_rejected_duplicates")) and row.get("duplicate_status") == "Rejected Duplicate":
		return True
	return False


def _track_duplicate_key(match, seen_duplicate_keys):
	key = _match_duplicate_key(match)
	if key:
		seen_duplicate_keys[key] += 1


def _get_statement_mapping_template(doc):
	if not getattr(doc, "mapping_template", None):
		frappe.throw("Select a Statement Mapping Template before previewing or importing rows.")
	return frappe.get_doc("RetailEdge Statement Mapping Template", doc.mapping_template)


def _read_statement_import_attachment(doc):
	if not getattr(doc, "attachment", None):
		frappe.throw("Upload a statement attachment before previewing or importing rows.")
	path = Path(get_file_path(doc.attachment))
	if not path.exists():
		frappe.throw("The attached statement file could not be found on disk.")
	content = path.read_bytes()
	suffix = path.suffix.lower()
	if suffix == ".csv":
		rows = read_csv_content(content, False)
	elif suffix == ".xlsx":
		rows = read_xlsx_file_from_attached_file(fcontent=content)
	else:
		frappe.throw("Only CSV and XLSX statement attachments are supported right now.")
	if not rows:
		return []
	headers = [cstr(value).strip() for value in rows[0]]
	data_rows = []
	for raw in rows[1:]:
		if raw is None:
			continue
		row_values = list(raw)
		if not any(value not in (None, "") for value in row_values):
			continue
		data_rows.append({headers[index]: row_values[index] if index < len(row_values) else None for index in range(len(headers))})
	return data_rows


def _should_include_statement_row(normalized_row, statement_import_doc):
	statement_type = cstr(getattr(statement_import_doc, "statement_type", None) or getattr(statement_import_doc, "payment_category", None)).strip().lower()
	if statement_type == "cash":
		return False
	direction = cstr(normalized_row.get("direction")).strip().lower()
	if direction and direction != "credit":
		return False
	return flt(normalized_row.get("amount")) > 0


def _apply_date_filter(query_filters, filters):
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["posting_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["posting_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["posting_date"] = ["<=", filters.get("to_date")]


def _assert_force_rematch_allowed():
	if user_has_any_role(user=None, roles=FORCE_REMATCH_ROLES):
		return
	frappe.throw("Only manager/admin roles can force a rematch for an already matched invoice.", frappe.PermissionError)


def cstr(value):
	if value is None:
		return ""
	return str(value)
