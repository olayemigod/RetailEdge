from __future__ import annotations

from collections import Counter

import frappe
from frappe.utils import cint, flt, getdate

from retailedge.branch_context import has_doctype, has_field, resolve_retailedge_branch_context
from retailedge.branch_profile import get_branch_profile_defaults
from retailedge.cashier_expense import user_has_any_role
from retailedge.utils.settings import get_retailedge_settings


INVOICE_PAYMENT_AUDIT_ROLES = {
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
PAYMENT_AUDIT_STATUSES = (
	"Credit",
	"Partially Paid",
	"Fully Paid Pending Audit",
	"Payment Rows Missing",
	"Payment Account Mismatch",
	"Payment Amount Mismatch",
	"Split Payment",
	"Overpaid",
	"Underpaid",
	"Pending Verification",
	"Ready for Verification",
	"Verified in Daily Audit",
	"Variance Found",
	"Cancelled",
	"Unknown",
)
PAYMENT_CATEGORIES = ("Cash", "Bank Transfer", "Card / POS", "Mobile Money", "Credit", "Other")


def assert_can_access_invoice_payment_audit(user: str | None = None):
	if user_has_any_role(user=user, roles=INVOICE_PAYMENT_AUDIT_ROLES):
		return
	frappe.throw(
		"You do not have permission to access RetailEdge invoice payment audit intelligence.",
		frappe.PermissionError,
	)


def get_invoice_payment_audit_settings():
	settings = get_retailedge_settings()
	return {
		"enabled": bool(getattr(settings, "enable_invoice_payment_audit", 1)),
		"include_draft_invoices": bool(getattr(settings, "invoice_payment_audit_include_draft_invoices", 0)),
		"include_cancelled_invoices": bool(getattr(settings, "invoice_payment_audit_include_cancelled_invoices", 0)),
		"tolerance_amount": flt(getattr(settings, "invoice_payment_audit_tolerance_amount", 0)),
		"check_expected_account": bool(getattr(settings, "invoice_payment_audit_check_expected_account", 1)),
		"check_payment_rows": bool(getattr(settings, "invoice_payment_audit_check_payment_rows", 1)),
		"check_payment_entries": bool(getattr(settings, "invoice_payment_audit_check_payment_entries", 1)),
	}


def classify_payment_method(mode_of_payment=None, account=None, row=None):
	text = " ".join(
		part.lower()
		for part in (
			cstr(mode_of_payment),
			cstr(account),
			cstr((row or {}).get("mode_of_payment") if isinstance(row, dict) else None),
			cstr((row or {}).get("account") if isinstance(row, dict) else None),
		)
		if part
	)
	if not text:
		return {"category": "Other", "confidence": "Low", "reason": "No payment method or account was available."}
	if any(token in text for token in ("cash", "petty cash")):
		return {"category": "Cash", "confidence": "High", "reason": "Cash keyword matched mode of payment or account."}
	if any(token in text for token in ("mobile", "money", "momo", "wallet")):
		return {"category": "Mobile Money", "confidence": "High", "reason": "Mobile money keyword matched mode of payment or account."}
	if any(token in text for token in ("card", "pos", "terminal")):
		return {"category": "Card / POS", "confidence": "High", "reason": "Card/POS keyword matched mode of payment or account."}
	if any(token in text for token in ("bank", "transfer")):
		return {"category": "Bank Transfer", "confidence": "High", "reason": "Bank/transfer keyword matched mode of payment or account."}
	if "credit" in text:
		return {"category": "Credit", "confidence": "Medium", "reason": "Credit keyword matched mode of payment or account."}
	return {"category": "Other", "confidence": "Low", "reason": "No standard payment category keyword matched."}


def get_expected_payment_account_for_invoice(invoice_doc, payment_category=None, mode_of_payment=None):
	branch_result = _resolve_invoice_branch(invoice_doc)
	profile_defaults = get_branch_profile_defaults(
		company=getattr(invoice_doc, "company", None),
		branch=branch_result.get("branch"),
		user=getattr(invoice_doc, "owner", None),
		pos_profile=getattr(invoice_doc, "pos_profile", None),
	)
	category = payment_category or classify_payment_method(mode_of_payment=mode_of_payment).get("category")
	messages = list(profile_defaults.get("messages") or [])
	accounts = []
	if category == "Cash":
		accounts = _unique_non_empty(
			[
				profile_defaults.get("default_cash_account"),
				profile_defaults.get("default_pos_opening_cash_account"),
			]
		)
	elif category == "Bank Transfer":
		accounts = _unique_non_empty([profile_defaults.get("default_bank_account")])
	elif category == "Card / POS":
		accounts = _unique_non_empty([profile_defaults.get("default_card_pos_account")])
	elif category == "Mobile Money":
		accounts = _unique_non_empty([profile_defaults.get("default_mobile_money_account")])
	if len(accounts) > 1:
		messages.append(f"Multiple expected accounts were configured for {category}.")
		return {
			"account": None,
			"branch": branch_result.get("branch"),
			"branch_source": branch_result.get("branch_source"),
			"category": category,
			"messages": messages,
			"ambiguous": True,
		}
	account = accounts[0] if accounts else None
	return {
		"account": account,
		"branch": branch_result.get("branch"),
		"branch_source": branch_result.get("branch_source"),
		"category": category,
		"messages": messages,
		"ambiguous": False,
	}


def get_sales_invoice_payment_rows(invoice_doc):
	rows = []
	for payment_row in getattr(invoice_doc, "payments", []) or []:
		row = payment_row.as_dict() if hasattr(payment_row, "as_dict") else dict(payment_row)
		amount = flt(row.get("base_amount") if row.get("base_amount") is not None else row.get("amount"))
		classification = classify_payment_method(
			mode_of_payment=row.get("mode_of_payment"),
			account=row.get("account") or row.get("default_account"),
			row=row,
		)
		expected = get_expected_payment_account_for_invoice(
			invoice_doc,
			payment_category=classification.get("category"),
			mode_of_payment=row.get("mode_of_payment"),
		)
		actual_account = row.get("account") or row.get("default_account")
		expected_account = expected.get("account")
		account_matches_expected = None
		issue = None
		if expected_account:
			account_matches_expected = actual_account == expected_account
			if account_matches_expected is False:
				issue = "Payment account does not match the expected branch account."
		rows.append(
			{
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
	return rows


def get_payment_entries_for_sales_invoice(invoice_name):
	if not has_doctype("Payment Entry Reference") or not has_doctype("Payment Entry"):
		return []
	try:
		reference_rows = frappe.get_all(
			"Payment Entry Reference",
			filters={"reference_doctype": "Sales Invoice", "reference_name": invoice_name},
			fields=["parent", "allocated_amount", "total_amount"],
			limit_page_length=0,
			order_by="creation asc",
		)
	except Exception:
		return []
	if not reference_rows:
		return []
	allocated_by_entry = {}
	for row in reference_rows:
		allocated_by_entry.setdefault(row.get("parent"), 0.0)
		allocated_by_entry[row.get("parent")] += flt(row.get("allocated_amount") or row.get("total_amount"))
	try:
		payment_rows = frappe.get_all(
			"Payment Entry",
			filters={"name": ["in", list(allocated_by_entry)], "docstatus": 1},
			fields=[
				"name",
				"posting_date",
				"party",
				"paid_amount",
				"received_amount",
				"paid_from",
				"paid_to",
				"mode_of_payment",
				"docstatus",
			],
			limit_page_length=0,
			order_by="posting_date asc, creation asc",
		)
	except Exception:
		return []
	results = []
	for row in payment_rows:
		results.append(
			{
				"payment_entry": row.get("name"),
				"posting_date": row.get("posting_date"),
				"party": row.get("party"),
				"paid_amount": flt(row.get("paid_amount")),
				"received_amount": flt(row.get("received_amount")),
				"paid_from": row.get("paid_from"),
				"paid_to": row.get("paid_to"),
				"mode_of_payment": row.get("mode_of_payment"),
				"reference_allocated_amount": flt(allocated_by_entry.get(row.get("name"))),
				"docstatus": row.get("docstatus"),
			}
		)
	return results


def audit_sales_invoice_payment(invoice_name, use_payment_entries=True):
	settings = get_invoice_payment_audit_settings()
	invoice_doc = frappe.get_doc("Sales Invoice", invoice_name)
	branch_result = _resolve_invoice_branch(invoice_doc)
	tolerance = flt(settings.get("tolerance_amount"))
	grand_total = flt(getattr(invoice_doc, "grand_total", 0))
	rounded_total = flt(getattr(invoice_doc, "rounded_total", grand_total) or grand_total)
	expected_payment_amount = rounded_total or grand_total
	outstanding_amount = flt(getattr(invoice_doc, "outstanding_amount", 0))
	paid_amount = flt(getattr(invoice_doc, "paid_amount", expected_payment_amount - outstanding_amount))

	payment_rows = get_sales_invoice_payment_rows(invoice_doc) if settings.get("check_payment_rows") else []
	net_payment_row_amount = sum(flt(row.get("base_amount")) for row in payment_rows)
	payment_entries = (
		get_payment_entries_for_sales_invoice(invoice_name)
		if use_payment_entries and settings.get("check_payment_entries")
		else []
	)
	payment_entry_amount = sum(flt(row.get("reference_allocated_amount")) for row in payment_entries)
	effective_payment_amount = max(paid_amount, net_payment_row_amount, payment_entry_amount)
	payment_difference = effective_payment_amount - expected_payment_amount

	issues = []
	messages = []
	evidence_links = []
	account_summary = {"actual_accounts": [], "expected_accounts": [], "mismatched_accounts": []}
	payment_method_counter = Counter()

	for row in payment_rows:
		category = row.get("payment_category") or "Other"
		payment_method_counter[category] += flt(row.get("base_amount"))
		if row.get("account"):
			account_summary["actual_accounts"].append(row.get("account"))
		if row.get("expected_account"):
			account_summary["expected_accounts"].append(row.get("expected_account"))
		if row.get("account_matches_expected") is False:
			account_summary["mismatched_accounts"].append(row.get("account"))
			issues.append("Payment account mismatch detected in invoice payment rows.")
		if row.get("issue"):
			messages.append(row.get("issue"))

	for payment_entry in payment_entries:
		classification = classify_payment_method(
			mode_of_payment=payment_entry.get("mode_of_payment"),
			account=payment_entry.get("paid_to") or payment_entry.get("paid_from"),
		)
		payment_method_counter[classification.get("category")] += flt(payment_entry.get("reference_allocated_amount"))
		evidence_links.append(payment_entry.get("payment_entry"))
		expected = get_expected_payment_account_for_invoice(
			invoice_doc,
			payment_category=classification.get("category"),
			mode_of_payment=payment_entry.get("mode_of_payment"),
		)
		entry_account = payment_entry.get("paid_to") or payment_entry.get("paid_from")
		if entry_account:
			account_summary["actual_accounts"].append(entry_account)
		if expected.get("account"):
			account_summary["expected_accounts"].append(expected.get("account"))
			if entry_account and entry_account != expected.get("account"):
				account_summary["mismatched_accounts"].append(entry_account)
				issues.append("Payment Entry account differs from the expected branch payment account.")
		messages.extend(expected.get("messages") or [])

	is_cancelled = cint(getattr(invoice_doc, "docstatus", 0)) == 2
	is_credit = expected_payment_amount > tolerance and paid_amount <= tolerance and outstanding_amount >= expected_payment_amount - tolerance
	is_partially_paid = paid_amount > tolerance and outstanding_amount > tolerance
	rows_missing = (
		(cint(getattr(invoice_doc, "is_pos", 0)) or paid_amount > tolerance or outstanding_amount <= tolerance)
		and not payment_rows
		and not payment_entries
		and not is_credit
		and not is_partially_paid
	)
	amount_mismatch = False
	if (payment_rows or payment_entries) and settings.get("check_payment_rows"):
		if payment_rows and abs(net_payment_row_amount - paid_amount) > tolerance and paid_amount > tolerance:
			amount_mismatch = True
		if payment_entries and abs(payment_entry_amount - paid_amount) > tolerance and paid_amount > tolerance:
			amount_mismatch = True
		if abs(effective_payment_amount - expected_payment_amount) > tolerance and outstanding_amount <= tolerance:
			amount_mismatch = True
	if amount_mismatch:
		issues.append("Payment amount mismatch exceeds the configured tolerance.")

	split_payment = sum(1 for value in payment_method_counter.values() if flt(value) > 0) > 1
	if split_payment:
		issues.append("Invoice uses multiple payment methods.")

	overpaid = effective_payment_amount > expected_payment_amount + tolerance
	underpaid = (
		expected_payment_amount > tolerance
		and outstanding_amount > tolerance
		and effective_payment_amount > tolerance
		and abs((effective_payment_amount + outstanding_amount) - expected_payment_amount) > tolerance
	)
	account_mismatch = bool(account_summary["mismatched_accounts"])
	if overpaid:
		issues.append("Invoice appears overpaid beyond tolerance.")
	if underpaid:
		issues.append("Invoice appears underpaid or outstanding does not reconcile cleanly.")

	verified_in_daily_audit = _invoice_verified_in_daily_audit(invoice_name)
	classification = "Unknown"
	audit_status = "Unknown"

	if is_cancelled:
		audit_status = "Cancelled"
		classification = "Cancelled"
	elif verified_in_daily_audit:
		audit_status = "Verified in Daily Audit"
		classification = "Verified in Daily Audit"
	elif is_credit:
		audit_status = "Credit"
		classification = "Credit"
	elif is_partially_paid:
		audit_status = "Partially Paid"
		classification = "Partially Paid"
	elif overpaid:
		audit_status = "Overpaid"
		classification = "Variance Found"
	elif underpaid:
		audit_status = "Underpaid"
		classification = "Variance Found"
	elif account_mismatch:
		audit_status = "Payment Account Mismatch"
		classification = "Variance Found"
	elif amount_mismatch:
		audit_status = "Payment Amount Mismatch"
		classification = "Variance Found"
	elif rows_missing:
		audit_status = "Payment Rows Missing"
		classification = "Pending Verification"
	elif split_payment:
		audit_status = "Split Payment"
		classification = "Pending Verification"
	elif outstanding_amount <= tolerance and effective_payment_amount > tolerance:
		audit_status = "Ready for Verification" if not messages and not issues else "Fully Paid Pending Audit"
		classification = "Ready for Verification" if audit_status == "Ready for Verification" else "Pending Verification"
	elif paid_amount > tolerance or payment_entries:
		audit_status = "Pending Verification"
		classification = "Pending Verification"

	risk_level = _score_payment_risk(
		audit_status=audit_status,
		account_mismatch=account_mismatch,
		amount_mismatch=amount_mismatch,
		overpaid=overpaid,
		underpaid=underpaid,
		split_payment=split_payment,
		rows_missing=rows_missing,
		is_partially_paid=is_partially_paid,
		is_cancelled=is_cancelled,
		issue_count=len(_unique_non_empty(issues)),
	)
	if account_summary["expected_accounts"] and not account_summary["actual_accounts"]:
		messages.append("Expected branch payment accounts were found, but no actual payment accounts were present in the audit evidence.")

	return {
		"invoice": invoice_name,
		"company": getattr(invoice_doc, "company", None),
		"customer": getattr(invoice_doc, "customer", None),
		"posting_date": getattr(invoice_doc, "posting_date", None),
		"branch": branch_result.get("branch"),
		"branch_source": branch_result.get("branch_source"),
		"grand_total": grand_total,
		"rounded_total": rounded_total,
		"paid_amount": paid_amount,
		"outstanding_amount": outstanding_amount,
		"net_payment_row_amount": net_payment_row_amount,
		"payment_entry_amount": payment_entry_amount,
		"expected_payment_amount": expected_payment_amount,
		"payment_difference": payment_difference,
		"erp_status": getattr(invoice_doc, "status", None),
		"docstatus": getattr(invoice_doc, "docstatus", None),
		"is_pos": bool(cint(getattr(invoice_doc, "is_pos", 0))),
		"payment_audit_status": audit_status,
		"payment_risk_level": risk_level,
		"payment_classification": classification,
		"payment_method_summary": dict(payment_method_counter),
		"account_summary": {
			"actual_accounts": _unique_non_empty(account_summary["actual_accounts"]),
			"expected_accounts": _unique_non_empty(account_summary["expected_accounts"]),
			"mismatched_accounts": _unique_non_empty(account_summary["mismatched_accounts"]),
		},
		"issues": _unique_non_empty(issues),
		"messages": _unique_non_empty(messages + branch_result.get("messages", [])),
		"evidence_links": _unique_non_empty(evidence_links),
		"source": "read_only",
	}


def get_invoice_payment_audit_list(filters=None, limit=500):
	filters = frappe._dict(filters or {})
	settings = get_invoice_payment_audit_settings()
	rows = []
	for invoice_row in _get_candidate_invoices(filters, settings, limit=limit):
		result = audit_sales_invoice_payment(invoice_row.get("name"))
		if filters.get("audit_status") and result.get("payment_audit_status") != filters.get("audit_status"):
			continue
		if filters.get("risk_level") and result.get("payment_risk_level") != filters.get("risk_level"):
			continue
		if filters.get("payment_category") and filters.get("payment_category") not in result.get("payment_method_summary", {}):
			continue
		if cint(filters.get("only_issues")) and not result.get("issues"):
			continue
		rows.append(_summarise_invoice_payment_audit(result))
	return rows


def get_invoice_payment_audit_summary(filters=None):
	rows = get_invoice_payment_audit_list(filters=filters, limit=(frappe._dict(filters or {})).get("limit") or 500)
	summary = {
		"total_invoice_count": len(rows),
		"total_invoice_amount": 0.0,
		"credit_count": 0,
		"credit_amount": 0.0,
		"partially_paid_count": 0,
		"fully_paid_pending_audit_count": 0,
		"ready_for_verification_count": 0,
		"payment_rows_missing_count": 0,
		"payment_account_mismatch_count": 0,
		"payment_amount_mismatch_count": 0,
		"split_payment_count": 0,
		"overpaid_count": 0,
		"underpaid_count": 0,
		"variance_found_count": 0,
		"high_risk_count": 0,
		"medium_risk_count": 0,
		"low_risk_count": 0,
	}
	for row in rows:
		summary["total_invoice_amount"] += flt(row.get("grand_total"))
		status = row.get("payment_audit_status")
		if status == "Credit":
			summary["credit_count"] += 1
			summary["credit_amount"] += flt(row.get("grand_total"))
		if status == "Partially Paid":
			summary["partially_paid_count"] += 1
		if status == "Fully Paid Pending Audit":
			summary["fully_paid_pending_audit_count"] += 1
		if status == "Ready for Verification":
			summary["ready_for_verification_count"] += 1
		if status == "Payment Rows Missing":
			summary["payment_rows_missing_count"] += 1
		if status == "Payment Account Mismatch":
			summary["payment_account_mismatch_count"] += 1
		if status == "Payment Amount Mismatch":
			summary["payment_amount_mismatch_count"] += 1
		if status == "Split Payment":
			summary["split_payment_count"] += 1
		if status == "Overpaid":
			summary["overpaid_count"] += 1
		if status == "Underpaid":
			summary["underpaid_count"] += 1
		if row.get("payment_classification") == "Variance Found":
			summary["variance_found_count"] += 1
		risk = row.get("payment_risk_level")
		if risk == "High":
			summary["high_risk_count"] += 1
		elif risk == "Medium":
			summary["medium_risk_count"] += 1
		else:
			summary["low_risk_count"] += 1
	return summary


def _get_candidate_invoices(filters, settings, limit=500):
	if not has_doctype("Sales Invoice"):
		return []
	query_filters = {}
	if settings.get("include_draft_invoices") and (settings.get("include_cancelled_invoices") or cint(filters.get("include_cancelled"))):
		query_filters["docstatus"] = ["in", [0, 1, 2]]
	elif settings.get("include_draft_invoices"):
		query_filters["docstatus"] = ["in", [0, 1]]
	elif settings.get("include_cancelled_invoices") or cint(filters.get("include_cancelled")):
		query_filters["docstatus"] = ["in", [1, 2]]
	else:
		query_filters["docstatus"] = 1
	if filters.get("company") and has_field("Sales Invoice", "company"):
		query_filters["company"] = filters.get("company")
	if filters.get("customer") and has_field("Sales Invoice", "customer"):
		query_filters["customer"] = filters.get("customer")
	if filters.get("pos_profile") and has_field("Sales Invoice", "pos_profile"):
		query_filters["pos_profile"] = filters.get("pos_profile")
	if filters.get("cashier"):
		cashier_field = _first_existing_field("Sales Invoice", ("cashier", "owner"))
		if cashier_field:
			query_filters[cashier_field] = filters.get("cashier")
	_apply_date_filter(query_filters, filters)
	fields = [
		"name",
		"company",
		"customer",
		"posting_date",
		"grand_total",
		"rounded_total",
		"paid_amount",
		"outstanding_amount",
		"docstatus",
		"status",
	]
	for fieldname in ("is_pos", "retailedge_branch", "branch", "pos_profile", "owner"):
		if has_field("Sales Invoice", fieldname):
			fields.append(fieldname)
	rows = frappe.get_all(
		"Sales Invoice",
		filters=query_filters,
		fields=_unique_non_empty(fields),
		limit_page_length=cint(limit or 500),
		order_by="posting_date desc, creation desc",
	)
	matched = []
	for row in rows:
		branch = row.get("retailedge_branch") or row.get("branch")
		if not branch:
			branch = resolve_retailedge_branch_context(
				doctype="Sales Invoice",
				name=row.get("name"),
				company=row.get("company"),
				pos_profile=row.get("pos_profile"),
				user=row.get("owner"),
			).get("branch")
		if filters.get("branch") and branch != filters.get("branch"):
			continue
		row["resolved_branch"] = branch
		matched.append(row)
	return matched


def _resolve_invoice_branch(invoice_doc):
	messages = []
	branch = getattr(invoice_doc, "retailedge_branch", None) if has_field("Sales Invoice", "retailedge_branch") else None
	source = "Sales Invoice.retailedge_branch" if branch else None
	if not branch and has_field("Sales Invoice", "branch"):
		branch = getattr(invoice_doc, "branch", None)
		source = "Sales Invoice.branch" if branch else source
	if not branch:
		context = resolve_retailedge_branch_context(
			doctype="Sales Invoice",
			name=getattr(invoice_doc, "name", None),
			company=getattr(invoice_doc, "company", None),
			pos_profile=getattr(invoice_doc, "pos_profile", None),
			user=getattr(invoice_doc, "owner", None),
		)
		branch = context.get("branch")
		source = context.get("source_map", {}).get("branch") or context.get("source")
		messages.extend(context.get("messages") or [])
	return {"branch": branch, "branch_source": source, "messages": messages}


def _invoice_verified_in_daily_audit(invoice_name):
	if not has_doctype("RetailEdge Daily Sales Audit Invoice Line"):
		return False
	try:
		return bool(
			frappe.db.exists(
				"RetailEdge Daily Sales Audit Invoice Line",
				{"sales_invoice": invoice_name, "review_status": "Verified for Audit"},
			)
		)
	except Exception:
		return False


def _summarise_invoice_payment_audit(result):
	methods = ", ".join(sorted(result.get("payment_method_summary", {})))
	accounts = ", ".join(result.get("account_summary", {}).get("actual_accounts", []))
	expected_accounts = ", ".join(result.get("account_summary", {}).get("expected_accounts", []))
	return {
		"sales_invoice": result.get("invoice"),
		"posting_date": result.get("posting_date"),
		"company": result.get("company"),
		"branch": result.get("branch"),
		"customer": result.get("customer"),
		"grand_total": result.get("grand_total"),
		"paid_amount": result.get("paid_amount"),
		"outstanding_amount": result.get("outstanding_amount"),
		"payment_row_amount": result.get("net_payment_row_amount"),
		"payment_entry_amount": result.get("payment_entry_amount"),
		"difference": result.get("payment_difference"),
		"erp_status": result.get("erp_status"),
		"audit_status": result.get("payment_audit_status"),
		"payment_audit_status": result.get("payment_audit_status"),
		"risk_level": result.get("payment_risk_level"),
		"payment_risk_level": result.get("payment_risk_level"),
		"payment_classification": result.get("payment_classification"),
		"payment_methods": methods,
		"accounts_used": accounts,
		"expected_accounts": expected_accounts,
		"issues": "; ".join(result.get("issues") or []),
		"branch_source": result.get("branch_source"),
	}


def _score_payment_risk(
	audit_status=None,
	account_mismatch=False,
	amount_mismatch=False,
	overpaid=False,
	underpaid=False,
	split_payment=False,
	rows_missing=False,
	is_partially_paid=False,
	is_cancelled=False,
	issue_count=0,
):
	if account_mismatch or amount_mismatch or overpaid or underpaid or (is_cancelled and issue_count):
		return "High"
	if issue_count > 1:
		return "High"
	if split_payment or rows_missing or is_partially_paid or audit_status in {"Pending Verification", "Fully Paid Pending Audit"}:
		return "Medium"
	return "Low"


def _apply_date_filter(query_filters, filters):
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["posting_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["posting_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["posting_date"] = ["<=", filters.get("to_date")]


def _first_existing_field(doctype, fieldnames):
	for fieldname in fieldnames:
		if has_field(doctype, fieldname):
			return fieldname
	return None


def _unique_non_empty(values):
	seen = []
	for value in values or []:
		if value and value not in seen:
			seen.append(value)
	return seen


def cstr(value):
	if value is None:
		return ""
	return str(value)
