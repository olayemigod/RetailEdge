from __future__ import annotations

from collections import defaultdict

import frappe
from frappe.utils import flt, getdate

from retailedge.branch_context import (
	get_branch_query_filters,
	has_doctype,
	has_field,
	resolve_retailedge_branch_context,
)
from retailedge.cashier_expense import user_has_any_role
from retailedge.cashier_expense_audit import get_cashier_expenses_for_daily_audit
from retailedge.invoice_payment_audit import get_invoice_payment_audit_summary


BRANCH_PERFORMANCE_ROLES = {
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
PAYMENT_CATEGORY_ORDER = ("Cash", "Bank Transfer", "Card / POS", "Mobile Money", "Other")


def get_branch_performance_roles() -> set[str]:
	return set(BRANCH_PERFORMANCE_ROLES)


def assert_can_access_branch_performance(user: str | None = None):
	if user_has_any_role(user=user, roles=get_branch_performance_roles()):
		return
	frappe.throw(
		"You do not have permission to access RetailEdge branch performance summaries.",
		frappe.PermissionError,
	)


def get_branch_performance_summary(filters=None):
	filters = _coerce_filters(filters)
	scope = _resolve_branch_scope(filters)
	filters = scope["filters"]

	sales = get_branch_sales_summary(filters)
	payments = get_branch_payment_breakdown(filters)
	variance = get_branch_variance_summary(filters)
	stock = get_branch_stock_activity_summary(filters)
	expense_rows = get_cashier_expenses_for_daily_audit(filters=filters)
	invoice_audit = get_invoice_payment_audit_summary({**filters, "limit": 500})

	cashier_expense_amount = 0.0
	cashier_expense_count = 0
	for row in expense_rows:
		if (row.get("expense_status") or "") == "Cancelled":
			continue
		cashier_expense_amount += flt(row.get("amount"))
		cashier_expense_count += 1

	messages = []
	messages.extend(scope.get("messages") or [])
	messages.extend(sales.get("messages") or [])
	messages.extend(payments.get("messages") or [])
	messages.extend(variance.get("messages") or [])
	messages.extend(stock.get("messages") or [])

	return {
		"company": filters.get("company"),
		"branch": filters.get("branch"),
		"from_date": filters.get("from_date"),
		"to_date": filters.get("to_date"),
		"total_sales_amount": sales.get("total_sales_amount", 0.0),
		"sales_invoice_count": sales.get("sales_invoice_count", 0),
		"paid_invoice_count": sales.get("paid_invoice_count", 0),
		"unpaid_invoice_count": sales.get("unpaid_invoice_count", 0),
		"partially_paid_invoice_count": sales.get("partially_paid_invoice_count", 0),
		"credit_sales_amount": sales.get("credit_sales_amount", 0.0),
		"cash_sales_amount": payments.get("Cash", 0.0),
		"bank_transfer_amount": payments.get("Bank Transfer", 0.0),
		"card_pos_amount": payments.get("Card / POS", 0.0),
		"mobile_money_amount": payments.get("Mobile Money", 0.0),
		"other_payment_amount": payments.get("Other", 0.0),
		"cashier_expense_amount": cashier_expense_amount,
		"cashier_expense_count": cashier_expense_count,
		"expected_cash_amount": variance.get("expected_cash_amount", 0.0),
		"actual_closing_cash_amount": variance.get("actual_closing_cash_amount", 0.0),
		"cash_variance_amount": variance.get("cash_variance_amount", 0.0),
		"daily_audit_count": variance.get("daily_audit_count", 0),
		"daily_audit_pending_count": variance.get("daily_audit_pending_count", 0),
		"daily_audit_approved_count": variance.get("daily_audit_approved_count", 0),
		"daily_audit_variance_count": variance.get("daily_audit_variance_count", 0),
		"material_request_count": stock.get("material_request_count", 0),
		"stock_entry_count": stock.get("stock_entry_count", 0),
		"invoice_payment_audit_issue_count": (
			invoice_audit.get("payment_account_mismatch_count", 0)
			+ invoice_audit.get("payment_amount_mismatch_count", 0)
			+ invoice_audit.get("payment_rows_missing_count", 0)
			+ invoice_audit.get("overpaid_count", 0)
			+ invoice_audit.get("underpaid_count", 0)
		),
		"payment_account_mismatch_count": invoice_audit.get("payment_account_mismatch_count", 0),
		"payment_amount_mismatch_count": invoice_audit.get("payment_amount_mismatch_count", 0),
		"payment_rows_missing_count": invoice_audit.get("payment_rows_missing_count", 0),
		"ready_for_verification_count": invoice_audit.get("ready_for_verification_count", 0),
		"credit_invoice_count": invoice_audit.get("credit_count", 0),
		"high_risk_invoice_count": invoice_audit.get("high_risk_count", 0),
		"exception_count": (
			sales.get("unpaid_invoice_count", 0)
			+ sales.get("partially_paid_invoice_count", 0)
			+ variance.get("daily_audit_pending_count", 0)
			+ variance.get("daily_audit_variance_count", 0)
			+ invoice_audit.get("payment_account_mismatch_count", 0)
			+ invoice_audit.get("payment_amount_mismatch_count", 0)
			+ invoice_audit.get("payment_rows_missing_count", 0)
		),
		"messages": _dedupe_messages(messages),
	}


def get_branch_payment_breakdown(filters=None):
	filters = _coerce_filters(filters)
	invoices, messages = _get_matching_sales_invoices(filters)
	breakdown = {category: 0.0 for category in PAYMENT_CATEGORY_ORDER}
	for row in invoices:
		try:
			invoice_doc = frappe.get_doc("Sales Invoice", row.get("name"))
		except Exception:
			continue
		for payment_row in getattr(invoice_doc, "payments", []) or []:
			payment = payment_row.as_dict() if hasattr(payment_row, "as_dict") else dict(payment_row)
			amount = flt(payment.get("base_amount") if payment.get("base_amount") is not None else payment.get("amount"))
			if amount <= 0:
				continue
			category = _classify_payment(payment.get("mode_of_payment"), payment.get("account") or payment.get("default_account"))
			breakdown[category] = breakdown.get(category, 0.0) + amount
	breakdown["messages"] = _dedupe_messages(messages)
	return breakdown


def get_branch_sales_summary(filters=None):
	filters = _coerce_filters(filters)
	invoices, messages = _get_matching_sales_invoices(filters)
	summary = {
		"invoice_count": 0,
		"sales_invoice_count": 0,
		"total_sales_amount": 0.0,
		"paid_invoice_count": 0,
		"unpaid_invoice_count": 0,
		"partially_paid_invoice_count": 0,
		"credit_sales_amount": 0.0,
		"messages": list(messages),
	}
	for row in invoices:
		grand_total = flt(row.get("grand_total"))
		outstanding = flt(row.get("outstanding_amount"))
		paid_amount = flt(row.get("paid_amount"))
		summary["invoice_count"] += 1
		summary["sales_invoice_count"] += 1
		summary["total_sales_amount"] += grand_total
		summary["credit_sales_amount"] += outstanding
		if outstanding <= 0 and grand_total > 0:
			summary["paid_invoice_count"] += 1
		elif paid_amount > 0 and outstanding > 0:
			summary["partially_paid_invoice_count"] += 1
		else:
			summary["unpaid_invoice_count"] += 1
	summary["messages"] = _dedupe_messages(summary["messages"])
	return summary


def get_branch_variance_summary(filters=None):
	filters = _coerce_filters(filters)
	rows = _get_matching_daily_sales_audits(filters)
	messages = []
	summary = {
		"expected_cash_amount": 0.0,
		"actual_closing_cash_amount": 0.0,
		"cash_variance_amount": 0.0,
		"daily_audit_count": 0,
		"daily_audit_pending_count": 0,
		"daily_audit_approved_count": 0,
		"daily_audit_variance_count": 0,
		"messages": messages,
	}
	for row in rows:
		status = row.get("audit_status") or "Draft"
		result = row.get("audit_result") or "Not Checked"
		summary["daily_audit_count"] += 1
		summary["expected_cash_amount"] += flt(row.get("expected_cash_amount"))
		summary["actual_closing_cash_amount"] += flt(row.get("actual_closing_cash_amount"))
		summary["cash_variance_amount"] += flt(row.get("cash_variance_amount"))
		if status in {"Draft", "Ready for Review", "In Review", "Clarification Required", "Reopened"}:
			summary["daily_audit_pending_count"] += 1
		if status == "Approved":
			summary["daily_audit_approved_count"] += 1
		if status == "Variance Found" or result in {"Shortage", "Overage", "Mixed Variance", "Requires Clarification"}:
			summary["daily_audit_variance_count"] += 1
	summary["messages"] = _dedupe_messages(messages)
	return summary


def get_branch_stock_activity_summary(filters=None):
	filters = _coerce_filters(filters)
	return {
		"material_request_count": _count_attributed_docs("Material Request", filters),
		"stock_entry_count": _count_attributed_docs("Stock Entry", filters),
		"purchase_receipt_count": _count_attributed_docs("Purchase Receipt", filters),
		"delivery_note_count": _count_attributed_docs("Delivery Note", filters),
		"messages": [],
	}


def _get_matching_sales_invoices(filters):
	if not has_doctype("Sales Invoice"):
		return [], ["Sales Invoice is not available on this site."]
	query_filters = {"docstatus": 1}
	if filters.get("company") and has_field("Sales Invoice", "company"):
		query_filters["company"] = filters.get("company")
	if has_field("Sales Invoice", "is_pos"):
		query_filters["is_pos"] = 1
	if filters.get("pos_profile") and has_field("Sales Invoice", "pos_profile"):
		query_filters["pos_profile"] = filters.get("pos_profile")
	if filters.get("cashier"):
		cashier_field = _first_existing_field("Sales Invoice", ("cashier", "owner"))
		if cashier_field:
			query_filters[cashier_field] = filters.get("cashier")
	_posting_date_filter("Sales Invoice", query_filters, filters)
	fields = ["name", "company", "grand_total", "outstanding_amount"]
	for fieldname in ("paid_amount", "retailedge_branch", "branch", "pos_profile", "owner", "posting_date"):
		if has_field("Sales Invoice", fieldname):
			fields.append(fieldname)
	rows = frappe.get_all("Sales Invoice", filters=query_filters, fields=_dedupe(fields), limit_page_length=0)
	messages = []
	matched_rows = []
	for row in rows:
		branch = _resolve_row_branch("Sales Invoice", row, filters, messages)
		if _row_matches_branch(branch, filters):
			row["resolved_branch"] = branch
			matched_rows.append(row)
	return matched_rows, messages


def _get_matching_daily_sales_audits(filters):
	if not has_doctype("RetailEdge Daily Sales Audit"):
		return []
	query_filters = {}
	query_filters.update(
		(get_branch_query_filters(
			"RetailEdge Daily Sales Audit",
			user=getattr(getattr(frappe, "session", None), "user", "Administrator"),
			company=filters.get("company"),
			branch=filters.get("branch"),
		).get("filters") or {})
	)
	for fieldname in ("company", "branch", "pos_profile", "cashier"):
		value = filters.get(fieldname)
		if value and fieldname not in query_filters and has_field("RetailEdge Daily Sales Audit", fieldname):
			query_filters[fieldname] = value
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["audit_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["audit_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["audit_date"] = ["<=", filters.get("to_date")]
	return frappe.get_all(
		"RetailEdge Daily Sales Audit",
		filters=query_filters,
		fields=[
			"name",
			"audit_status",
			"audit_result",
			"expected_cash_amount",
			"actual_closing_cash_amount",
			"cash_variance_amount",
		],
		limit_page_length=0,
	)


def _count_attributed_docs(doctype, filters):
	if not has_doctype(doctype):
		return 0
	query_filters = {}
	if filters.get("company") and has_field(doctype, "company"):
		query_filters["company"] = filters.get("company")
	if filters.get("cashier"):
		cashier_field = _first_existing_field(doctype, ("cashier", "owner"))
		if cashier_field:
			query_filters[cashier_field] = filters.get("cashier")
	_date_filter(doctype, query_filters, filters)
	fields = ["name"]
	for fieldname in ("retailedge_branch", "branch", "pos_profile", "owner"):
		if has_field(doctype, fieldname):
			fields.append(fieldname)
	rows = frappe.get_all(doctype, filters=query_filters, fields=_dedupe(fields), limit_page_length=0)
	messages = []
	count = 0
	for row in rows:
		branch = _resolve_row_branch(doctype, row, filters, messages)
		if _row_matches_branch(branch, filters):
			count += 1
	return count


def _resolve_row_branch(doctype, row, filters, messages):
	if row.get("retailedge_branch"):
		return row.get("retailedge_branch")
	if row.get("branch"):
		return row.get("branch")
	context = resolve_retailedge_branch_context(
		doctype=doctype,
		name=row.get("name"),
		company=row.get("company") or filters.get("company"),
		branch=row.get("branch"),
		pos_profile=row.get("pos_profile") or filters.get("pos_profile"),
		cashier=row.get("cashier") or row.get("owner") or filters.get("cashier"),
		user=row.get("cashier") or row.get("owner") or filters.get("cashier"),
	)
	messages.extend(context.get("messages") or [])
	return context.get("branch")


def _resolve_branch_scope(filters):
	scope = get_branch_query_filters(
		"RetailEdge Daily Sales Audit",
		user=getattr(getattr(frappe, "session", None), "user", "Administrator"),
		company=filters.get("company"),
		branch=filters.get("branch"),
	)
	effective = dict(filters)
	if not effective.get("branch") and scope.get("branch"):
		effective["branch"] = scope.get("branch")
	return {"filters": effective, "messages": scope.get("messages") or [], "allowed_branches": scope.get("allowed_branches") or []}


def get_candidate_branches(filters=None):
	filters = _coerce_filters(filters)
	scope = _resolve_branch_scope(filters)
	if scope["filters"].get("branch"):
		return [scope["filters"]["branch"]]
	if scope.get("allowed_branches"):
		return list(scope["allowed_branches"])
	if not has_doctype("Branch"):
		return []
	query_filters = {}
	if filters.get("company") and has_field("Branch", "company"):
		query_filters["company"] = filters.get("company")
	return frappe.get_all("Branch", filters=query_filters, pluck="name", limit_page_length=0) or []


def _row_matches_branch(branch, filters):
	if filters.get("branch"):
		return branch == filters.get("branch")
	return True


def _posting_date_filter(doctype, query_filters, filters):
	if not has_field(doctype, "posting_date"):
		return
	if filters.get("from_date") and filters.get("to_date"):
		query_filters["posting_date"] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters["posting_date"] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters["posting_date"] = ["<=", filters.get("to_date")]


def _date_filter(doctype, query_filters, filters):
	date_field = _first_existing_field(doctype, ("posting_date", "transaction_date", "schedule_date"))
	if not date_field:
		return
	if filters.get("from_date") and filters.get("to_date"):
		query_filters[date_field] = ["between", [filters.get("from_date"), filters.get("to_date")]]
	elif filters.get("from_date"):
		query_filters[date_field] = [">=", filters.get("from_date")]
	elif filters.get("to_date"):
		query_filters[date_field] = ["<=", filters.get("to_date")]


def _classify_payment(mode_of_payment, account):
	mode = (mode_of_payment or "").strip().lower()
	account_name = (account or "").strip().lower()
	if "cash" in mode or "cash" in account_name:
		return "Cash"
	if "bank" in mode or "transfer" in mode or "bank" in account_name:
		return "Bank Transfer"
	if "card" in mode or "pos" in mode or "terminal" in mode:
		return "Card / POS"
	if "mobile" in mode or "wallet" in mode or "money" in mode:
		return "Mobile Money"
	return "Other"


def _first_existing_field(doctype, fieldnames):
	for fieldname in fieldnames:
		if has_field(doctype, fieldname):
			return fieldname
	return None


def _coerce_filters(filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if isinstance(filters, frappe._dict):
		filters = dict(filters)
	normalised = frappe._dict(filters)
	for fieldname in ("from_date", "to_date"):
		if normalised.get(fieldname):
			normalised[fieldname] = str(getdate(normalised.get(fieldname)))
	return normalised


def _dedupe(values):
	return list(dict.fromkeys(values))


def _dedupe_messages(messages):
	return [message for message in dict.fromkeys([msg for msg in messages if msg])]
