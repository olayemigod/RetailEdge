from __future__ import annotations

from collections import defaultdict
from types import SimpleNamespace

import frappe
from frappe.utils import flt, get_first_day, getdate, nowdate

from retailedge.branch_context import (
	get_branch_query_filters,
	get_first_existing_field,
	has_doctype,
	has_field,
	resolve_branch_from_closing_shift,
	resolve_branch_from_opening_shift,
	resolve_retailedge_branch_context,
)
from retailedge.cashier_expense import user_has_any_role


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
BANK_SALES_PAYMENT_CATEGORIES = ("Bank Transfer", "Card / POS", "Mobile Money")
MAX_BRANCH_PERFORMANCE_RANGE_DAYS = 60


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
	rows = get_branch_performance_rows(filters)
	if filters.get("branch"):
		for row in rows:
			if row.get("branch") == filters.get("branch"):
				return row
	if rows:
		return _aggregate_branch_performance_rows(rows, filters)
	return _build_empty_row(filters, branch=filters.get("branch"))


def get_branch_performance_rows(filters=None):
	filters = _coerce_filters(filters)
	scope = _resolve_branch_scope(filters)
	filters = scope["filters"]

	sales_summary = get_branch_sales_summary(filters)
	payment_summary = get_branch_payment_breakdown(filters)
	expense_summary = get_branch_expense_summary(filters)
	variance_summary = get_branch_variance_summary(filters)
	stock_summary = get_branch_stock_activity_summary(filters)

	row_map: dict[str, dict] = {}
	for branch in _branch_order(filters, sales_summary, expense_summary, variance_summary, stock_summary):
		row_map[branch] = _build_empty_row(filters, branch=branch)

	for dataset in (sales_summary, payment_summary, expense_summary, variance_summary, stock_summary):
		for branch, payload in dataset.get("by_branch", {}).items():
			row = row_map.setdefault(branch, _build_empty_row(filters, branch=branch))
			row.update(payload)

	for row in row_map.values():
		row["cash_sales"] = flt(row.get("Cash"))
		row["bank_sales"] = get_bank_sales_total(row)
		row["bank_card_mobile_sales"] = row["bank_sales"]
		row["net_cash_expected"] = flt(row.get("cash_sales")) - flt(row.get("cashier_expenses"))
		row["payment_issues"] = (
			int(row.get("outstanding_invoice_count") or 0)
			+ int(row.get("pending_audit_count") or 0)
			+ int(row.get("high_variance_count") or 0)
			+ int(row.get("unattributed_invoice_count") or 0)
		)
		row["review_status"] = _derive_review_status(row)

	messages = _dedupe_messages(
		(scope.get("messages") or [])
		+ (sales_summary.get("messages") or [])
		+ (payment_summary.get("messages") or [])
		+ (expense_summary.get("messages") or [])
		+ (variance_summary.get("messages") or [])
		+ (stock_summary.get("messages") or [])
	)

	rows = [row_map[key] for key in sorted(row_map)]
	for row in rows:
		row["messages"] = messages
	return rows


def debug_branch_performance_cashier_filter(filters=None, **kwargs):
	if kwargs:
		payload = dict(filters or {})
		payload.update(kwargs)
		filters = payload
	filters = _coerce_filters(filters)
	query_parts = _sales_invoice_query_parts(filters, alias="si", include_branch_filter=True, need_cashier=True)
	cashier_source_expr = _sales_invoice_cashier_source_expression("si")
	cashier_expr = query_parts["cashier_expr"]
	available_cashier_fields = _available_sales_invoice_cashier_sources()

	rows = frappe.db.sql(
		f"""
		SELECT
			COUNT(si.name) AS sales_invoice_count,
			{cashier_source_expr} AS resolved_cashier_source,
			{cashier_expr} AS resolved_cashier,
			SUM(COALESCE(si.grand_total, 0)) AS gross_sales
		FROM `tabSales Invoice` si
		{query_parts["join_sql"]}
		WHERE {query_parts["where_sql"]}
		GROUP BY resolved_cashier_source, resolved_cashier
		ORDER BY sales_invoice_count DESC, gross_sales DESC
		""",
		query_parts["params"],
		as_dict=True,
	)

	sample_invoices = frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.posting_date,
			COALESCE(si.grand_total, 0) AS grand_total,
			si.owner,
			{_sales_invoice_optional_field('si', 'pos_profile')} AS pos_profile,
			COALESCE(si.is_pos, 0) AS is_pos,
			{_sales_invoice_optional_field('si', 'posa_pos_opening_shift')} AS posa_pos_opening_shift,
			{_sales_invoice_optional_field('si', 'pos_opening_shift')} AS pos_opening_shift,
			{_sales_invoice_optional_field('si', 'retailedge_branch')} AS retailedge_branch,
			{cashier_expr} AS resolved_cashier,
			{cashier_source_expr} AS resolved_cashier_source
		FROM `tabSales Invoice` si
		{query_parts["join_sql"]}
		WHERE {query_parts["where_sql"]}
		ORDER BY si.posting_date DESC, si.creation DESC
		LIMIT 20
		""",
		query_parts["params"],
		as_dict=True,
	)

	source_summary = defaultdict(dict)
	for row in rows:
		source = row.get("resolved_cashier_source") or "None"
		cashier = row.get("resolved_cashier") or "Unattributed Cashier"
		source_summary[source][cashier] = {
			"invoice_count": int(row.get("sales_invoice_count") or 0),
			"gross_sales": flt(row.get("gross_sales")),
		}

	return {
		"filters": dict(filters),
		"sales_invoice_count": sum(int(row.get("sales_invoice_count") or 0) for row in rows),
		"cashier_filter": filters.get("cashier"),
		"available_cashier_fields": available_cashier_fields,
		"sales_invoice_cashier_sources": dict(source_summary),
		"sample_invoices": sample_invoices,
	}


def get_branch_payment_breakdown(filters=None):
	filters = _coerce_filters(filters)
	by_branch = defaultdict(lambda: {category: 0.0 for category in PAYMENT_CATEGORY_ORDER})
	messages = []

	if not has_doctype("Sales Invoice Payment") or not has_doctype("Sales Invoice"):
		messages.append("Sales Invoice Payment is not available on this site.")
		return {"by_branch": {}, "messages": messages}

	amount_expr = _sales_invoice_payment_amount_expression("sip")
	if not amount_expr:
		messages.append("Sales Invoice Payment has no supported amount field.")
		return {"by_branch": {}, "messages": messages}

	query_parts = _sales_invoice_query_parts(filters, alias="si", include_branch_filter=True, need_cashier=bool(filters.get("cashier")))
	branch_expr = query_parts["branch_expr"]
	where_sql, params = query_parts["where_sql"], query_parts["params"]
	payment_case = _payment_category_sql("sip")
	rows = frappe.db.sql(
		f"""
		SELECT
			{branch_expr} AS branch,
			{payment_case} AS payment_category,
			SUM({amount_expr}) AS total_amount
		FROM `tabSales Invoice` si
		{query_parts["join_sql"]}
		INNER JOIN `tabSales Invoice Payment` sip
			ON sip.parent = si.name
		WHERE {where_sql}
		GROUP BY branch, payment_category
		""",
		params,
		as_dict=True,
	)

	fallback_rows = []
	if filters.get("include_fallback_branch_resolution"):
		fallback_rows = _get_unattributed_sales_invoice_rows(filters, only_with_payments=True)

	for row in rows:
		branch = _normalise_branch_key(row.get("branch"), filters)
		if not branch:
			continue
		category = row.get("payment_category") or "Other"
		if filters.get("payment_method") and category != filters.get("payment_method"):
			continue
		by_branch[branch][category] = flt(by_branch[branch][category]) + flt(row.get("total_amount"))

	for row in fallback_rows:
		branch = _normalise_branch_key(row.get("resolved_branch"), filters)
		if not branch:
			continue
		for payment in row.get("payments", []):
			category = payment.get("category") or "Other"
			if filters.get("payment_method") and category != filters.get("payment_method"):
				continue
			by_branch[branch][category] = flt(by_branch[branch][category]) + flt(payment.get("amount"))

	return {"by_branch": dict(by_branch), "messages": messages}


def get_branch_sales_summary(filters=None):
	filters = _coerce_filters(filters)
	by_branch = defaultdict(dict)
	messages = []

	if not has_doctype("Sales Invoice"):
		return {"by_branch": {}, "messages": ["Sales Invoice is not available on this site."]}

	query_parts = _sales_invoice_query_parts(filters, alias="si", include_branch_filter=True, need_cashier=bool(filters.get("cashier")))
	branch_expr = query_parts["branch_expr"]
	where_sql, params = query_parts["where_sql"], query_parts["params"]
	net_total_expr = _sales_invoice_net_total_expression("si")
	paid_amount_expr = _sales_invoice_paid_amount_expression("si")
	rows = frappe.db.sql(
		f"""
		SELECT
			{branch_expr} AS branch,
			COUNT(si.name) AS invoice_count,
			SUM(COALESCE(si.grand_total, 0)) AS gross_sales,
			SUM({net_total_expr}) AS net_total,
			SUM(COALESCE(si.outstanding_amount, 0)) AS outstanding_amount,
			SUM({paid_amount_expr}) AS paid_amount,
			SUM(CASE WHEN COALESCE(si.outstanding_amount, 0) <= 0 AND COALESCE(si.grand_total, 0) > 0 THEN 1 ELSE 0 END) AS paid_invoice_count,
			SUM(CASE WHEN {paid_amount_expr} > 0 AND COALESCE(si.outstanding_amount, 0) > 0 THEN 1 ELSE 0 END) AS partially_paid_invoice_count,
			SUM(CASE WHEN {paid_amount_expr} <= 0 AND COALESCE(si.outstanding_amount, 0) > 0 THEN 1 ELSE 0 END) AS unpaid_invoice_count
		FROM `tabSales Invoice` si
		{query_parts["join_sql"]}
		WHERE {where_sql}
		GROUP BY branch
		""",
		params,
		as_dict=True,
	)

	fallback_rows = []
	if filters.get("include_fallback_branch_resolution"):
		fallback_rows = _get_unattributed_sales_invoice_rows(filters)

	for row in rows:
		branch = _normalise_branch_key(row.get("branch"), filters)
		if not branch:
			continue
		by_branch[branch] = {
			"invoice_count": int(row.get("invoice_count") or 0),
			"gross_sales": flt(row.get("gross_sales")),
			"net_total": flt(row.get("net_total")),
			"outstanding_amount": flt(row.get("outstanding_amount")),
			"paid_amount": flt(row.get("paid_amount")),
			"paid_invoice_count": int(row.get("paid_invoice_count") or 0),
			"partially_paid_invoice_count": int(row.get("partially_paid_invoice_count") or 0),
			"outstanding_invoice_count": int(row.get("unpaid_invoice_count") or 0),
			"unattributed_invoice_count": 0,
		}

	unattributed_invoice_count = 0
	for row in fallback_rows:
		branch = _normalise_branch_key(row.get("resolved_branch"), filters)
		if not branch:
			unattributed_invoice_count += 1
			continue
		payload = by_branch.setdefault(
			branch,
			{
				"invoice_count": 0,
				"gross_sales": 0.0,
				"net_total": 0.0,
				"outstanding_amount": 0.0,
				"paid_amount": 0.0,
				"paid_invoice_count": 0,
				"partially_paid_invoice_count": 0,
				"outstanding_invoice_count": 0,
				"unattributed_invoice_count": 0,
			},
		)
		payload["invoice_count"] += 1
		payload["gross_sales"] += flt(row.get("grand_total"))
		payload["net_total"] += flt(row.get("net_total"))
		payload["outstanding_amount"] += flt(row.get("outstanding_amount"))
		payload["paid_amount"] += flt(row.get("paid_amount"))
		if flt(row.get("outstanding_amount")) <= 0 and flt(row.get("grand_total")) > 0:
			payload["paid_invoice_count"] += 1
		elif flt(row.get("paid_amount")) > 0 and flt(row.get("outstanding_amount")) > 0:
			payload["partially_paid_invoice_count"] += 1
		else:
			payload["outstanding_invoice_count"] += 1

	if unattributed_invoice_count and not filters.get("include_unattributed"):
		messages.append(f"{unattributed_invoice_count} unattributed invoice(s) were excluded. Enable fallback branch resolution to include them.")

	return {"by_branch": dict(by_branch), "messages": messages}


def get_branch_expense_summary(filters=None):
	filters = _coerce_filters(filters)
	by_branch = defaultdict(dict)
	messages = []
	doctype = "RetailEdge Cashier Expense"
	if not has_doctype(doctype):
		return {"by_branch": {}, "messages": messages}

	branch_expr = _doctype_branch_expression(doctype, "ce")
	status_field = "expense_status" if has_field(doctype, "expense_status") else None
	docstatus_sql = " AND COALESCE(ce.docstatus, 0) != 2" if has_field(doctype, "docstatus") else ""
	where_sql, params = _doctype_where_sql(doctype, filters, alias="ce", date_candidates=("expense_date", "posting_date"), include_branch_filter=True)
	status_case = f"LOWER(COALESCE(ce.`{status_field}`, ''))" if status_field else "''"
	rows = frappe.db.sql(
		f"""
		SELECT
			{branch_expr} AS branch,
			COUNT(ce.name) AS expense_count,
			SUM(COALESCE(ce.amount, 0)) AS expense_total,
			SUM(CASE WHEN {status_case} = 'approved' THEN COALESCE(ce.amount, 0) ELSE 0 END) AS approved_total,
			SUM(CASE WHEN {status_case} IN ('draft', 'submitted', 'pending', 'in review') THEN COALESCE(ce.amount, 0) ELSE 0 END) AS pending_total,
			SUM(CASE WHEN {status_case} = 'rejected' THEN COALESCE(ce.amount, 0) ELSE 0 END) AS rejected_total
		FROM `tab{doctype}` ce
		WHERE {where_sql}{docstatus_sql}
		GROUP BY branch
		""",
		params,
		as_dict=True,
	)
	for row in rows:
		branch = _normalise_branch_key(row.get("branch"), filters)
		if not branch:
			continue
		by_branch[branch] = {
			"cashier_expenses": flt(row.get("expense_total")),
			"cashier_expense_count": int(row.get("expense_count") or 0),
			"approved_expense_total": flt(row.get("approved_total")),
			"pending_expense_total": flt(row.get("pending_total")),
			"rejected_expense_total": flt(row.get("rejected_total")),
		}
	return {"by_branch": dict(by_branch), "messages": messages}


def get_branch_variance_summary(filters=None):
	filters = _coerce_filters(filters)
	by_branch = defaultdict(dict)
	messages = []
	doctype = "RetailEdge Daily Sales Audit"
	if not has_doctype(doctype):
		return {"by_branch": {}, "messages": messages}

	branch_expr = _doctype_branch_expression(doctype, "dsa")
	status_expr = "LOWER(COALESCE(dsa.audit_status, ''))" if has_field(doctype, "audit_status") else "''"
	result_expr = "LOWER(COALESCE(dsa.audit_result, ''))" if has_field(doctype, "audit_result") else "''"
	expected_expr = "COALESCE(dsa.expected_cash_amount, 0)" if has_field(doctype, "expected_cash_amount") else "0"
	actual_expr = "COALESCE(dsa.actual_closing_cash_amount, 0)" if has_field(doctype, "actual_closing_cash_amount") else "0"
	variance_expr = "COALESCE(dsa.cash_variance_amount, 0)" if has_field(doctype, "cash_variance_amount") else "0"
	where_sql, params = _doctype_where_sql(doctype, filters, alias="dsa", date_candidates=("audit_date", "posting_date"), include_branch_filter=True)
	rows = frappe.db.sql(
		f"""
		SELECT
			{branch_expr} AS branch,
			COUNT(dsa.name) AS audit_count,
			SUM({expected_expr}) AS expected_cash_amount,
			SUM({actual_expr}) AS actual_closing_cash_amount,
			SUM({variance_expr}) AS audit_variance,
			SUM(CASE WHEN {status_expr} IN ('draft', 'ready for review', 'in review', 'clarification required', 'reopened') THEN 1 ELSE 0 END) AS pending_audit_count,
			SUM(CASE WHEN {status_expr} = 'approved' THEN 1 ELSE 0 END) AS approved_audit_count,
			SUM(CASE WHEN {status_expr} = 'variance found' OR {result_expr} IN ('shortage', 'overage', 'mixed variance', 'requires clarification') THEN 1 ELSE 0 END) AS high_variance_count
		FROM `tab{doctype}` dsa
		WHERE {where_sql}
		GROUP BY branch
		""",
		params,
		as_dict=True,
	)
	for row in rows:
		branch = _normalise_branch_key(row.get("branch"), filters)
		if not branch:
			continue
		by_branch[branch] = {
			"expected_cash": flt(row.get("expected_cash_amount")),
			"actual_closing_cash": flt(row.get("actual_closing_cash_amount")),
			"audit_variance": flt(row.get("audit_variance")),
			"daily_audit_count": int(row.get("audit_count") or 0),
			"pending_audit_count": int(row.get("pending_audit_count") or 0),
			"approved_audit_count": int(row.get("approved_audit_count") or 0),
			"high_variance_count": int(row.get("high_variance_count") or 0),
		}
	return {"by_branch": dict(by_branch), "messages": messages}


def get_branch_stock_activity_summary(filters=None):
	filters = _coerce_filters(filters)
	by_branch = defaultdict(dict)
	messages = []
	for doctype, target_field in (
		("Material Request", "material_request_count"),
		("Stock Entry", "stock_entry_count"),
	):
		if not has_doctype(doctype):
			continue
		branch_expr = _doctype_branch_expression(doctype, "doc")
		where_sql, params = _doctype_where_sql(doctype, filters, alias="doc", date_candidates=("posting_date", "transaction_date", "schedule_date"), include_branch_filter=True)
		docstatus_sql = " AND COALESCE(doc.docstatus, 0) != 2" if has_field(doctype, "docstatus") else ""
		rows = frappe.db.sql(
			f"""
			SELECT
				{branch_expr} AS branch,
				COUNT(doc.name) AS row_count
			FROM `tab{doctype}` doc
			WHERE {where_sql}{docstatus_sql}
			GROUP BY branch
			""",
			params,
			as_dict=True,
		)
		for row in rows:
			branch = _normalise_branch_key(row.get("branch"), filters)
			if not branch:
				continue
			by_branch.setdefault(branch, {})[target_field] = int(row.get("row_count") or 0)
	return {"by_branch": dict(by_branch), "messages": messages}


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
	return {"filters": frappe._dict(effective), "messages": scope.get("messages") or [], "allowed_branches": scope.get("allowed_branches") or []}


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


def _coerce_filters(filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	if isinstance(filters, frappe._dict):
		filters = dict(filters)
	normalised = frappe._dict(filters)
	normalised["from_date"] = str(getdate(normalised.get("from_date") or get_first_day(nowdate())))
	normalised["to_date"] = str(getdate(normalised.get("to_date") or nowdate()))
	normalised["include_fallback_branch_resolution"] = _truthy(normalised.get("include_fallback_branch_resolution"))
	normalised["include_unattributed"] = 1 if normalised.get("include_unattributed") in (None, "") else _truthy(normalised.get("include_unattributed"))
	normalised["only_pos_invoices"] = 0 if normalised.get("only_pos_invoices") in (None, "") else _truthy(normalised.get("only_pos_invoices"))
	if getdate(normalised.from_date) > getdate(normalised.to_date):
		frappe.throw("From Date cannot be after To Date.")
	if (getdate(normalised.to_date) - getdate(normalised.from_date)).days > MAX_BRANCH_PERFORMANCE_RANGE_DAYS:
		frappe.throw("Date range too wide for live report. Please use 60 days or less.")
	return normalised


def get_branch_performance_debug_summary(filters=None, **kwargs):
	if kwargs:
		payload = dict(filters or {})
		payload.update(kwargs)
		filters = payload
	filters = _coerce_filters(filters)
	sales_where_sql, sales_params = _sales_invoice_where_sql(filters, alias="si", include_branch_filter=False)
	submitted_sales_invoice_count = 0
	sales_invoice_with_retailedge_branch_count = 0
	if has_doctype("Sales Invoice"):
		submitted_sales_invoice_count = frappe.db.sql(
			f"SELECT COUNT(si.name) FROM `tabSales Invoice` si WHERE {sales_where_sql}",
			sales_params,
		)[0][0]
		if has_field("Sales Invoice", "retailedge_branch"):
			sales_invoice_with_retailedge_branch_count = frappe.db.sql(
				f"""
				SELECT COUNT(si.name)
				FROM `tabSales Invoice` si
				WHERE {sales_where_sql}
				AND NULLIF(si.retailedge_branch, '') IS NOT NULL
				""",
				sales_params,
			)[0][0]

	expense_count = _doctype_debug_count("RetailEdge Cashier Expense", filters, ("expense_date", "posting_date"))
	daily_sales_audit_count = _doctype_debug_count("RetailEdge Daily Sales Audit", filters, ("audit_date", "posting_date"))
	return {
		"submitted_sales_invoice_count": int(submitted_sales_invoice_count or 0),
		"sales_invoice_with_retailedge_branch_count": int(sales_invoice_with_retailedge_branch_count or 0),
		"cashier_expense_count": int(expense_count or 0),
		"daily_sales_audit_count": int(daily_sales_audit_count or 0),
		"filters_used": dict(filters),
	}


def resolve_sales_invoice_cashier(invoice_row_or_doc):
	doc = invoice_row_or_doc
	if isinstance(invoice_row_or_doc, dict):
		doc = SimpleNamespace(**invoice_row_or_doc)

	for fieldname in ("cashier", "user"):
		value = getattr(doc, fieldname, None)
		if value:
			return {"cashier": value, "source": f"Sales Invoice.{fieldname}", "messages": []}

	posa_shift = getattr(doc, "posa_pos_opening_shift", None)
	if posa_shift:
		shift_result = resolve_branch_from_opening_shift(posa_shift, company=getattr(doc, "company", None))
		if shift_result.get("cashier"):
			return {"cashier": shift_result.get("cashier"), "source": "POS Opening Shift.user", "messages": shift_result.get("messages") or []}

	pos_opening_shift = getattr(doc, "pos_opening_shift", None)
	if pos_opening_shift:
		shift_result = resolve_branch_from_opening_shift(pos_opening_shift, company=getattr(doc, "company", None))
		if shift_result.get("cashier"):
			return {"cashier": shift_result.get("cashier"), "source": "POS Opening Shift.user", "messages": shift_result.get("messages") or []}

	pos_closing_shift = getattr(doc, "pos_closing_shift", None)
	if pos_closing_shift:
		closing_result = resolve_branch_from_closing_shift(pos_closing_shift, company=getattr(doc, "company", None))
		if closing_result.get("cashier"):
			return {"cashier": closing_result.get("cashier"), "source": "POS Closing Shift.user", "messages": closing_result.get("messages") or []}

	owner = getattr(doc, "owner", None)
	if owner:
		return {"cashier": owner, "source": "Sales Invoice.owner", "messages": []}
	return {"cashier": None, "source": "None", "messages": []}


def _doctype_debug_count(doctype, filters, date_candidates):
	if not has_doctype(doctype):
		return 0
	where_sql, params = _doctype_where_sql(doctype, filters, alias="doc", date_candidates=date_candidates, include_branch_filter=False)
	return frappe.db.sql(f"SELECT COUNT(doc.name) FROM `tab{doctype}` doc WHERE {where_sql}", params)[0][0]


def _sales_invoice_where_sql(filters, alias="si", include_branch_filter=True):
	query_parts = _sales_invoice_query_parts(filters, alias=alias, include_branch_filter=include_branch_filter, need_cashier=bool(filters.get("cashier")))
	return query_parts["where_sql"], query_parts["params"]


def _sales_invoice_query_parts(filters, alias="si", include_branch_filter=True, need_cashier=False):
	branch_expr = _sales_invoice_branch_expression(alias)
	cashier_parts = _sales_invoice_cashier_sql_parts(alias, need_cashier=need_cashier)
	conditions = [f"{alias}.docstatus = 1"]
	params = []

	if filters.get("company") and has_field("Sales Invoice", "company"):
		conditions.append(f"{alias}.company = %s")
		params.append(filters.get("company"))
	if filters.get("only_pos_invoices") and has_field("Sales Invoice", "is_pos"):
		conditions.append(f"COALESCE({alias}.is_pos, 0) = 1")
	if filters.get("pos_profile") and has_field("Sales Invoice", "pos_profile"):
		conditions.append(f"{alias}.pos_profile = %s")
		params.append(filters.get("pos_profile"))
	if filters.get("cashier"):
		conditions.append(f"{cashier_parts['cashier_expr']} = %s")
		params.append(filters.get("cashier"))
	if has_field("Sales Invoice", "posting_date"):
		conditions.append(f"{alias}.posting_date BETWEEN %s AND %s")
		params.extend([filters.get("from_date"), filters.get("to_date")])

	if filters.get("payment_method") and has_doctype("Sales Invoice Payment"):
		payment_case = _payment_category_sql("sip_filter")
		conditions.append(
			f"""EXISTS (
				SELECT 1 FROM `tabSales Invoice Payment` sip_filter
				WHERE sip_filter.parent = {alias}.name
				AND {payment_case} = %s
			)"""
		)
		params.append(filters.get("payment_method"))

	if include_branch_filter and filters.get("branch"):
		conditions.append(f"{branch_expr} = %s")
		params.append(filters.get("branch"))
	elif include_branch_filter and not filters.get("include_unattributed"):
		conditions.append(f"{branch_expr} IS NOT NULL")

	return {
		"join_sql": cashier_parts["join_sql"],
		"cashier_expr": cashier_parts["cashier_expr"],
		"branch_expr": branch_expr,
		"where_sql": " AND ".join(conditions),
		"params": params,
	}


def _doctype_where_sql(doctype, filters, alias="doc", date_candidates=("posting_date",), include_branch_filter=True):
	conditions = ["1=1"]
	params = []
	if filters.get("company") and has_field(doctype, "company"):
		conditions.append(f"{alias}.company = %s")
		params.append(filters.get("company"))
	if filters.get("cashier"):
		cashier_field = _first_existing_field(doctype, ("cashier", "owner", "user"))
		if cashier_field:
			conditions.append(f"{alias}.`{cashier_field}` = %s")
			params.append(filters.get("cashier"))
	if filters.get("pos_profile"):
		pos_field = _first_existing_field(doctype, ("pos_profile", "pos_profile_name"))
		if pos_field:
			conditions.append(f"{alias}.`{pos_field}` = %s")
			params.append(filters.get("pos_profile"))
	date_field = _first_existing_field(doctype, date_candidates)
	if date_field:
		conditions.append(f"DATE({alias}.`{date_field}`) BETWEEN %s AND %s")
		params.extend([filters.get("from_date"), filters.get("to_date")])
	branch_expr = _doctype_branch_expression(doctype, alias)
	if include_branch_filter and filters.get("branch"):
		conditions.append(f"{branch_expr} = %s")
		params.append(filters.get("branch"))
	elif include_branch_filter and not filters.get("include_unattributed"):
		conditions.append(f"{branch_expr} IS NOT NULL")
	return " AND ".join(conditions), params


def _sales_invoice_branch_expression(alias="si"):
	parts = []
	if has_field("Sales Invoice", "retailedge_branch"):
		parts.append(f"NULLIF({alias}.retailedge_branch, '')")
	if has_field("Sales Invoice", "branch"):
		parts.append(f"NULLIF({alias}.branch, '')")
	return f"COALESCE({', '.join(parts)})" if parts else "NULL"


def _sales_invoice_cashier_sql_parts(alias="si", need_cashier=False):
	joins = []
	expressions = []
	if has_field("Sales Invoice", "cashier"):
		expressions.append(f"NULLIF({alias}.cashier, '')")
	if has_field("Sales Invoice", "user"):
		expressions.append(f"NULLIF({alias}.`user`, '')")

	if need_cashier and has_doctype("POS Opening Shift"):
		if has_field("Sales Invoice", "posa_pos_opening_shift"):
			joins.append(f"LEFT JOIN `tabPOS Opening Shift` {alias}_posa_opening_shift ON {alias}_posa_opening_shift.name = {alias}.posa_pos_opening_shift")
			if has_field("POS Opening Shift", "user"):
				expressions.append(f"NULLIF({alias}_posa_opening_shift.user, '')")
			elif has_field("POS Opening Shift", "cashier"):
				expressions.append(f"NULLIF({alias}_posa_opening_shift.cashier, '')")
		if has_field("Sales Invoice", "pos_opening_shift"):
			joins.append(f"LEFT JOIN `tabPOS Opening Shift` {alias}_pos_opening_shift ON {alias}_pos_opening_shift.name = {alias}.pos_opening_shift")
			if has_field("POS Opening Shift", "user"):
				expressions.append(f"NULLIF({alias}_pos_opening_shift.user, '')")
			elif has_field("POS Opening Shift", "cashier"):
				expressions.append(f"NULLIF({alias}_pos_opening_shift.cashier, '')")

	expressions.append(f"NULLIF({alias}.owner, '')")
	return {
		"join_sql": " ".join(dict.fromkeys(joins)),
		"cashier_expr": f"COALESCE({', '.join(expressions)})" if expressions else "NULL",
	}


def _sales_invoice_cashier_source_expression(alias="si"):
	source_parts = []
	if has_field("Sales Invoice", "cashier"):
		source_parts.append(f"WHEN NULLIF({alias}.cashier, '') IS NOT NULL THEN 'Sales Invoice.cashier'")
	if has_field("Sales Invoice", "user"):
		source_parts.append(f"WHEN NULLIF({alias}.`user`, '') IS NOT NULL THEN 'Sales Invoice.user'")
	if has_doctype("POS Opening Shift") and has_field("Sales Invoice", "posa_pos_opening_shift"):
		if has_field("POS Opening Shift", "user"):
			source_parts.append(f"WHEN NULLIF({alias}_posa_opening_shift.user, '') IS NOT NULL THEN 'POS Opening Shift.user'")
		elif has_field("POS Opening Shift", "cashier"):
			source_parts.append(f"WHEN NULLIF({alias}_posa_opening_shift.cashier, '') IS NOT NULL THEN 'POS Opening Shift.cashier'")
	if has_doctype("POS Opening Shift") and has_field("Sales Invoice", "pos_opening_shift"):
		if has_field("POS Opening Shift", "user"):
			source_parts.append(f"WHEN NULLIF({alias}_pos_opening_shift.user, '') IS NOT NULL THEN 'POS Opening Shift.user'")
		elif has_field("POS Opening Shift", "cashier"):
			source_parts.append(f"WHEN NULLIF({alias}_pos_opening_shift.cashier, '') IS NOT NULL THEN 'POS Opening Shift.cashier'")
	source_parts.append(f"WHEN NULLIF({alias}.owner, '') IS NOT NULL THEN 'Sales Invoice.owner'")
	return f"CASE {' '.join(source_parts)} ELSE 'None' END"


def _available_sales_invoice_cashier_sources():
	sources = []
	if has_field("Sales Invoice", "cashier"):
		sources.append("Sales Invoice.cashier")
	if has_field("Sales Invoice", "user"):
		sources.append("Sales Invoice.user")
	if has_doctype("POS Opening Shift") and has_field("Sales Invoice", "posa_pos_opening_shift") and has_field("POS Opening Shift", "user"):
		sources.append("POS Opening Shift.user")
	if has_doctype("POS Opening Shift") and has_field("Sales Invoice", "pos_opening_shift") and has_field("POS Opening Shift", "user"):
		sources.append("POS Opening Shift.user")
	sources.append("Sales Invoice.owner")
	return list(dict.fromkeys(sources))


def _sales_invoice_net_total_expression(alias="si"):
	if has_field("Sales Invoice", "net_total"):
		return f"COALESCE({alias}.net_total, 0)"
	if has_field("Sales Invoice", "base_net_total"):
		return f"COALESCE({alias}.base_net_total, 0)"
	return "0"


def _sales_invoice_paid_amount_expression(alias="si"):
	if has_field("Sales Invoice", "paid_amount"):
		return f"COALESCE({alias}.paid_amount, 0)"
	return "0"


def _doctype_branch_expression(doctype, alias="doc"):
	parts = []
	if has_field(doctype, "retailedge_branch"):
		parts.append(f"NULLIF({alias}.retailedge_branch, '')")
	if has_field(doctype, "branch"):
		parts.append(f"NULLIF({alias}.branch, '')")
	return f"COALESCE({', '.join(parts)})" if parts else "NULL"


def _sales_invoice_payment_amount_expression(alias="sip"):
	if has_field("Sales Invoice Payment", "base_amount"):
		return f"COALESCE({alias}.base_amount, 0)"
	if has_field("Sales Invoice Payment", "amount"):
		return f"COALESCE({alias}.amount, 0)"
	return None


def get_bank_sales_total(row):
	return sum(flt(row.get(category)) for category in BANK_SALES_PAYMENT_CATEGORIES)


def _payment_category_sql(alias="sip"):
	mode_expr = f"LOWER(COALESCE({alias}.mode_of_payment, ''))" if has_field("Sales Invoice Payment", "mode_of_payment") else "''"
	account_expr = f"LOWER(COALESCE({alias}.account, ''))" if has_field("Sales Invoice Payment", "account") else "''"
	return (
		f"CASE "
		f"WHEN {mode_expr} LIKE '%%cash%%' OR {account_expr} LIKE '%%cash%%' THEN 'Cash' "
		f"WHEN {mode_expr} LIKE '%%bank%%' OR {mode_expr} LIKE '%%transfer%%' OR {mode_expr} LIKE '%%monnify%%' OR {mode_expr} LIKE '%%moniepoint%%' OR {account_expr} LIKE '%%bank%%' THEN 'Bank Transfer' "
		f"WHEN {mode_expr} LIKE '%%card%%' OR {mode_expr} LIKE '%%pos%%' OR {mode_expr} LIKE '%%terminal%%' THEN 'Card / POS' "
		f"WHEN {mode_expr} LIKE '%%mobile%%' OR {mode_expr} LIKE '%%wallet%%' OR {mode_expr} LIKE '%%money%%' THEN 'Mobile Money' "
		f"ELSE 'Other' END"
	)


def _get_unattributed_sales_invoice_rows(filters, only_with_payments=False):
	if not filters.get("include_fallback_branch_resolution"):
		return []
	where_sql, params = _sales_invoice_where_sql(filters, alias="si", include_branch_filter=False)
	rows = frappe.db.sql(
		f"""
		SELECT
			si.name,
			si.company,
			{_sales_invoice_optional_field('si', 'pos_profile')} AS pos_profile,
			{_sales_invoice_optional_field('si', 'owner')} AS owner,
			si.grand_total,
			{_sales_invoice_net_total_expression('si')} AS net_total,
			COALESCE(si.outstanding_amount, 0) AS outstanding_amount,
			{_sales_invoice_paid_amount_expression('si')} AS paid_amount
		FROM `tabSales Invoice` si
		WHERE {where_sql}
		AND {_sales_invoice_branch_expression('si')} IS NULL
		""",
		params,
		as_dict=True,
	)
	resolved_rows = []
	for row in rows:
		context = resolve_retailedge_branch_context(
			doctype="Sales Invoice",
			name=row.get("name"),
			company=row.get("company"),
			pos_profile=row.get("pos_profile") or filters.get("pos_profile"),
			cashier=row.get("owner") or filters.get("cashier"),
			user=row.get("owner") or filters.get("cashier"),
		)
		branch = context.get("branch")
		if not branch and not filters.get("include_unattributed"):
			continue
		row["resolved_branch"] = branch
		if only_with_payments:
			row["payments"] = _get_invoice_payment_breakdown(row.get("name"), filters)
		resolved_rows.append(row)
	return resolved_rows


def _get_invoice_payment_breakdown(invoice_name, filters):
	if not has_doctype("Sales Invoice Payment"):
		return []
	amount_expr = _sales_invoice_payment_amount_expression("sip")
	if not amount_expr:
		return []
	payment_case = _payment_category_sql("sip")
	rows = frappe.db.sql(
		f"""
		SELECT
			{payment_case} AS payment_category,
			SUM({amount_expr}) AS total_amount
		FROM `tabSales Invoice Payment` sip
		WHERE sip.parent = %s
		GROUP BY payment_category
		""",
		[invoice_name],
		as_dict=True,
	)
	results = []
	for row in rows:
		category = row.get("payment_category") or "Other"
		if filters.get("payment_method") and category != filters.get("payment_method"):
			continue
		results.append({"category": category, "amount": flt(row.get("total_amount"))})
	return results


def _branch_order(filters, *datasets):
	keys = []
	if filters.get("branch"):
		keys.append(filters.get("branch"))
	for dataset in datasets:
		keys.extend((dataset.get("by_branch") or {}).keys())
	return [key for key in dict.fromkeys([branch for branch in keys if branch])]


def _normalise_branch_key(branch, filters):
	if branch:
		return branch
	if filters.get("include_unattributed"):
		return "Unattributed"
	return None


def _build_empty_row(filters, branch=None, messages=None):
	return {
		"branch": branch or ("Unattributed" if filters.get("include_unattributed") else None),
		"period": f"{filters.get('from_date')} to {filters.get('to_date')}",
		"invoice_count": 0,
		"gross_sales": 0.0,
		"net_total": 0.0,
		"outstanding_amount": 0.0,
		"paid_amount": 0.0,
		"cash_sales": 0.0,
		"Cash": 0.0,
		"bank_sales": 0.0,
		"bank_card_mobile_sales": 0.0,
		"cashier_expenses": 0.0,
		"net_cash_expected": 0.0,
		"audit_variance": 0.0,
		"payment_issues": 0,
		"review_status": "No Activity",
		"paid_invoice_count": 0,
		"partially_paid_invoice_count": 0,
		"outstanding_invoice_count": 0,
		"unattributed_invoice_count": 0,
		"daily_audit_count": 0,
		"pending_audit_count": 0,
		"approved_audit_count": 0,
		"high_variance_count": 0,
		"material_request_count": 0,
		"stock_entry_count": 0,
		"Bank Transfer": 0.0,
		"Card / POS": 0.0,
		"Mobile Money": 0.0,
		"Other": 0.0,
		"messages": messages or [],
	}


def _aggregate_branch_performance_rows(rows, filters):
	summary = _build_empty_row(filters, branch=filters.get("branch") or "All Branches")
	summary["review_status"] = "No Activity"
	summary["messages"] = _dedupe_messages(message for row in rows for message in (row.get("messages") or []))
	sum_fields = (
		"invoice_count",
		"gross_sales",
		"net_total",
		"outstanding_amount",
		"paid_amount",
		"cash_sales",
		"Cash",
		"bank_sales",
		"bank_card_mobile_sales",
		"cashier_expenses",
		"net_cash_expected",
		"audit_variance",
		"payment_issues",
		"paid_invoice_count",
		"partially_paid_invoice_count",
		"outstanding_invoice_count",
		"unattributed_invoice_count",
		"daily_audit_count",
		"pending_audit_count",
		"approved_audit_count",
		"high_variance_count",
		"material_request_count",
		"stock_entry_count",
		"Bank Transfer",
		"Card / POS",
		"Mobile Money",
		"Other",
		"expected_cash",
		"actual_closing_cash",
		"cashier_expense_count",
		"approved_expense_total",
		"pending_expense_total",
		"rejected_expense_total",
	)
	for row in rows:
		for fieldname in sum_fields:
			summary[fieldname] = flt(summary.get(fieldname)) + flt(row.get(fieldname))

	statuses = [row.get("review_status") for row in rows if row.get("review_status")]
	if "Needs Review" in statuses:
		summary["review_status"] = "Needs Review"
	elif "Variance Review" in statuses:
		summary["review_status"] = "Variance Review"
	elif "Reviewed" in statuses:
		summary["review_status"] = "Reviewed"
	return summary


def _derive_review_status(row):
	if int(row.get("pending_audit_count") or 0) or int(row.get("outstanding_invoice_count") or 0):
		return "Needs Review"
	if int(row.get("high_variance_count") or 0):
		return "Variance Review"
	if int(row.get("invoice_count") or 0) or int(row.get("daily_audit_count") or 0):
		return "Reviewed"
	return "No Activity"


def _first_existing_field(doctype, fieldnames):
	return get_first_existing_field(doctype, list(fieldnames))


def _truthy(value):
	if isinstance(value, str):
		return value.strip().lower() in {"1", "true", "yes", "on"}
	return bool(value)


def _sales_invoice_optional_field(alias, fieldname):
	return f"{alias}.`{fieldname}`" if has_field("Sales Invoice", fieldname) else "NULL"


def _dedupe_messages(messages):
	return [message for message in dict.fromkeys([msg for msg in messages if msg])]
