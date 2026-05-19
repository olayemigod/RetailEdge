from __future__ import annotations

import json
from collections import Counter
from datetime import timedelta

import frappe
from frappe.utils import cint, flt, get_datetime, getdate, now_datetime

from retailedge.branch_context import has_doctype, has_field, resolve_retailedge_branch_context
from retailedge.cashier_expense import user_has_any_role
from retailedge.invoice_payment_audit import (
	assert_can_access_invoice_payment_audit,
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
MATCH_STATUS_ORDER = ("Candidate", "Strong Candidate", "Weak Candidate", "Duplicate Suspected", "No Match", "Ignored")
CONFIDENCE_ORDER = ("Low", "Medium", "High")


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
		"match_against_bank_transactions": bool(getattr(settings, "match_against_bank_transactions", 0)),
		"match_against_statement_import_rows": bool(getattr(settings, "match_against_statement_import_rows", 1)),
		"match_against_payment_entries": bool(getattr(settings, "match_against_payment_entries", 1)),
		"match_against_manual_evidence": bool(getattr(settings, "match_against_manual_evidence", 1)),
		"payment_evidence_amount_tolerance": flt(getattr(settings, "payment_evidence_amount_tolerance", 0)),
		"payment_evidence_date_window_days": cint(getattr(settings, "payment_evidence_date_window_days", 3)),
		"require_reference_for_strong_match": bool(getattr(settings, "require_reference_for_strong_match", 0)),
	}


def match_payment_evidence_for_invoice(invoice_name, create_match_records=False):
	settings = get_payment_evidence_matching_settings()
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
			match = _match_against_payment_entry(invoice_doc, invoice_audit, payment_rows, payment_entry, settings)
			matches.append(match)
			_duplicate_key = _match_duplicate_key(match)
			if _duplicate_key:
				seen_duplicate_keys[_duplicate_key] += 1

	if settings.get("match_against_statement_import_rows"):
		matches.extend(
			_match_against_statement_import_rows(
				invoice_doc, invoice_audit, payment_rows, payment_entries, settings, messages, seen_duplicate_keys
			)
		)

	if settings["match_against_bank_transactions"]:
		matches.extend(_match_against_bank_transactions(invoice_doc, invoice_audit, payment_rows, settings, messages, seen_duplicate_keys))

	if settings["match_against_manual_evidence"]:
		matches.extend(_match_against_manual_evidence(invoice_doc, invoice_audit, payment_rows, payment_entries, settings, seen_duplicate_keys))

	for match in matches:
		key = _match_duplicate_key(match)
		if key and seen_duplicate_keys.get(key, 0) > 1:
			match["match_status"] = "Duplicate Suspected"
			match["issue_summary"] = _append_issue(match.get("issue_summary"), "Potential duplicate evidence match detected.")
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
		_persist_payment_evidence_match_records(invoice_audit, matches)

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
		result = match_payment_evidence_for_invoice(invoice_row.get("name"), create_match_records=False)
		for match in result.get("matches") or []:
			summary_row = _summarise_match_row(result, match)
			if filters.get("payment_category") and summary_row.get("payment_category") != filters.get("payment_category"):
				continue
			if filters.get("match_confidence") and summary_row.get("match_confidence") != filters.get("match_confidence"):
				continue
			if filters.get("match_status") and summary_row.get("match_status") != filters.get("match_status"):
				continue
			if cint(filters.get("only_unmatched")) and summary_row.get("match_status") not in {"No Match", "Weak Candidate"}:
				continue
			if cint(filters.get("only_duplicates")) and summary_row.get("match_status") != "Duplicate Suspected":
				continue
			rows.append(summary_row)
		if not result.get("matches"):
			for unmatched in result.get("unmatched_payments") or []:
				row = _summarise_unmatched_row(result, unmatched)
				if cint(filters.get("only_duplicates")):
					continue
				rows.append(row)
	rows = _flag_duplicate_evidence_rows(rows)
	if cint(filters.get("only_duplicates")):
		rows = [row for row in rows if row.get("match_status") == "Duplicate Suspected"]
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


def _match_against_payment_entry(invoice_doc, invoice_audit, payment_rows, payment_entry, settings):
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
		account=payment_entry.get("paid_to") or payment_entry.get("paid_from"),
		expected_account=expected.get("account"),
		party=payment_entry.get("party"),
		settings=settings,
		reference_match=True,
	)


def _match_against_bank_transactions(invoice_doc, invoice_audit, payment_rows, settings, messages, seen_duplicate_keys):
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
		reference_text = " ".join(
			part for part in [row.get("reference_number"), row.get("description"), row.get("party"), invoice_doc.name] if part
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
			account=row.get("account") or row.get("bank_account"),
			expected_account=expected.get("account"),
			party=row.get("party") or row.get("party_name"),
			settings=settings,
			reference_match=_reference_matches(reference_text, invoice_doc),
		)
		results.append(match)
		key = _match_duplicate_key(match)
		if key:
			seen_duplicate_keys[key] += 1
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
	fields = _available_fields(
		"RetailEdge Statement Import Row",
		(
			"name",
			"parent",
			"transaction_date",
			"payment_category",
			"reference",
			"narration",
			"party",
			"amount",
			"account",
			"bank_transaction",
			"payment_entry",
			"sales_invoice",
			"match_status",
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
		if row.get("sales_invoice") == invoice_doc.name:
			reference_match = True
		elif row.get("payment_entry") and any(item.get("payment_entry") == row.get("payment_entry") for item in payment_entries):
			reference_match = True
		else:
			reference_match = _reference_matches(" ".join(part for part in [row.get("reference"), row.get("narration")] if part), invoice_doc)
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
			reference_text=" ".join(part for part in [row.get("reference"), row.get("narration"), row.get("parent")] if part),
			account=row.get("account"),
			expected_account=expected.get("account"),
			party=row.get("party"),
			settings=settings,
			reference_match=reference_match,
		)
		results.append(match)
		key = _match_duplicate_key(match)
		if key:
			seen_duplicate_keys[key] += 1
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
	try:
		rows = frappe.get_all(
			"RetailEdge Payment Evidence",
			filters=query_filters,
			fields=[
				"name",
				"company",
				"branch",
				"evidence_date",
				"payment_category",
				"evidence_reference",
				"party",
				"party_type",
				"amount",
				"account",
				"payment_entry",
				"sales_invoice",
				"evidence_status",
			],
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
		reference_match = False
		if row.get("sales_invoice") == invoice_doc.name:
			reference_match = True
		elif row.get("payment_entry") and any(item.get("payment_entry") == row.get("payment_entry") for item in payment_entries):
			reference_match = True
		else:
			reference_match = _reference_matches(row.get("evidence_reference"), invoice_doc)
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
			account=row.get("account"),
			expected_account=expected.get("account"),
			party=row.get("party"),
			settings=settings,
			reference_match=reference_match,
		)
		results.append(match)
		key = _match_duplicate_key(match)
		if key:
			seen_duplicate_keys[key] += 1
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
	account,
	expected_account,
	party,
	settings,
	reference_match=False,
):
	tolerance = flt(settings.get("payment_evidence_amount_tolerance"))
	payment_amount = flt(payment_amount)
	evidence_amount = flt(evidence_amount)
	amount_difference = abs(payment_amount - evidence_amount)
	amount_match = amount_difference <= tolerance
	date_match = _dates_within_window(invoice_audit.get("posting_date"), evidence_date, settings)
	account_match = None if not expected_account else cstr(account) == cstr(expected_account)
	party_match = _party_matches(invoice_doc, party)
	score = 0
	score += 35 if reference_match else 0
	score += 25 if amount_match else 0
	score += 15 if date_match else 0
	score += 15 if account_match else 0
	score += 10 if party_match else 0
	confidence = "Low"
	if score >= 70:
		confidence = "High"
	elif score >= 40:
		confidence = "Medium"
	status = "Candidate"
	if score >= 70 and (reference_match or not settings.get("require_reference_for_strong_match")):
		status = "Strong Candidate"
	elif score >= 40:
		status = "Weak Candidate"
	elif score == 0:
		status = "No Match"
	if not amount_match or account_match is False:
		if confidence == "High":
			confidence = "Medium"
		if status == "Strong Candidate":
			status = "Weak Candidate"
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
		"account": account,
		"expected_account": expected_account,
		"evidence_date": evidence_date,
	}


def _build_unmatched_payment_rows(payment_rows, matches):
	matched_categories = Counter()
	for match in matches:
		if match.get("match_status") in {"Strong Candidate", "Candidate"}:
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
	}


def _persist_payment_evidence_match_records(invoice_audit, matches):
	if not has_doctype("RetailEdge Payment Evidence Match"):
		return
	existing = frappe.get_all(
		"RetailEdge Payment Evidence Match",
		filters={"sales_invoice": invoice_audit.get("invoice")},
		fields=["name"],
		limit_page_length=0,
	)
	for row in existing:
		try:
			frappe.delete_doc("RetailEdge Payment Evidence Match", row.get("name"), ignore_permissions=True, force=1)
		except Exception:
			continue
	for match in matches:
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
	rows = frappe.get_all("Sales Invoice", filters=query_filters, fields=fields, limit_page_length=cint(limit or 500), order_by="posting_date desc, creation desc")
	if not filters.get("branch"):
		return rows
	matched = []
	for row in rows:
		branch = row.get("retailedge_branch") or row.get("branch")
		if not branch:
			branch = resolve_retailedge_branch_context(doctype="Sales Invoice", name=row.get("name"), company=row.get("company")).get("branch")
		if branch == filters.get("branch"):
			matched.append(row)
	return matched


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
	invoice_dt = getdate(invoice_date)
	evidence_dt = getdate(evidence_date)
	return abs((evidence_dt - invoice_dt).days) <= window


def _reference_matches(reference_text, invoice_doc):
	text = cstr(reference_text).lower()
	if not text:
		return False
	customer = cstr(getattr(invoice_doc, "customer", None)).lower()
	return any(token and token in text for token in {invoice_doc.name.lower(), customer})


def _party_matches(invoice_doc, party):
	if not party:
		return False
	return cstr(getattr(invoice_doc, "customer", None)).lower() == cstr(party).lower()


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
	reference = cstr(match.get("reference") or match.get("evidence_name")).strip().lower()
	if not reference:
		return None
	return (match.get("evidence_type"), reference, flt(match.get("evidence_amount")), cstr(match.get("evidence_date")))


def _append_issue(existing, new_issue):
	if not existing:
		return new_issue
	if new_issue in existing:
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
			row["issue_summary"] = _append_issue(row.get("issue_summary"), "Potential duplicate evidence match detected.")
	return rows


def _apply_date_filter(query_filters, filters):
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["posting_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["posting_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["posting_date"] = ["<=", filters.get("to_date")]


def cstr(value):
	if value is None:
		return ""
	return str(value)
