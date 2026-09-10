from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.operating_context import get_operational_branch_scope

EXPENSE_DOCTYPE = "RetailEdge Cashier Expense"
BUSINESS_EXPENSE_DOCTYPE = "RetailEdge Business Expense"
CATEGORY_DOCTYPE = "RetailEdge Expense Category"

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_EXPORT_ROWS = 5000
MAX_DATE_RANGE_DAYS = 366
MAX_CATEGORY_MAP_ROWS = 1000

CONSOLIDATED_SOURCE_TYPES = (
	"Cashier / POS",
	"Business Expense",
	"Supplier / Business",
	"Employee Expense",
	"Accounting Adjustment",
)

_CONSOLIDATED_ROLES = {
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

_ACCOUNTING_VOUCHER_TYPES = {
	"Purchase Invoice": "Supplier / Business",
	"Expense Claim": "Employee Expense",
	"Journal Entry": "Accounting Adjustment",
}

_EXPENSE_STATUSES = {
	"Draft",
	"Submitted",
	"Pending Ledger",
	"Rejected",
	"Posted",
	"Cancelled",
}


def can_view_consolidated_business_expenses(user: str | None = None) -> bool:
	user = user or frappe.session.user
	return bool(set(frappe.get_roles(user)).intersection(_CONSOLIDATED_ROLES))


def get_consolidated_expense_register(
	filters: dict[str, Any] | frappe._dict,
	*,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	query = _prepare_query(_coerce_filters(filters))
	page = max(1, cint(page) or 1)
	page_size = max(1, min(cint(page_size) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE))

	summary = _query_summary(query)
	total_rows = cint(summary.get("count"))
	total_pages = max(1, ceil(total_rows / page_size)) if total_rows else 1
	if page > total_pages:
		page = total_pages
	rows = _query_rows(query, limit=page_size, offset=(page - 1) * page_size)
	rows = _map_account_categories(rows, company=query["company"])
	return {
		"columns": _columns(),
		"rows": rows,
		"summary": _summary_cards(summary),
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total_rows,
			"total_pages": total_pages,
			"has_previous": page > 1,
			"has_next": page < total_pages,
		},
		"scope": {
			"company": query["company"],
			"branch": query["requested_branch"],
			"cashier_scope": "permitted",
			"view_mode": "consolidated",
			"branch_scope": query["branch_scope_label"],
			"includes_unattributed": int(query["includes_unattributed"]),
			"include_unposted_cashier_expenses": int(
				query["include_unposted_cashier_expenses"]
			),
		},
		"metadata": {
			"view_mode": "consolidated",
			"sources": list(query["source_types"]),
			"accounting_voucher_types": list(query["accounting_voucher_types"]),
			"policy": _(
				"Posted expenses are the financial reporting truth. Unposted Cashier Expenses "
				"are excluded by default and appear only when explicitly included as operational exposure."
			),
		},
	}


def get_consolidated_expense_export(
	filters: dict[str, Any] | frappe._dict,
) -> dict[str, Any]:
	query = _prepare_query(_coerce_filters(filters))
	rows = _query_rows(query, limit=MAX_EXPORT_ROWS + 1, offset=0)
	if len(rows) > MAX_EXPORT_ROWS:
		frappe.throw(
			_(
				"More than {0} consolidated expenses match this export. "
				"Narrow the date, Branch, Category, Status, or Source filters first."
			).format(MAX_EXPORT_ROWS)
		)
	rows = _map_account_categories(rows, company=query["company"])
	summary = _query_summary(query)
	return {
		"columns": _columns(),
		"rows": rows,
		"summary": _summary_cards(summary),
		"scope": {
			"company": query["company"],
			"branch": query["requested_branch"],
			"view_mode": "consolidated",
			"branch_scope": query["branch_scope_label"],
			"include_unposted_cashier_expenses": int(
				query["include_unposted_cashier_expenses"]
			),
		},
		"metadata": {
			"view_mode": "consolidated",
			"sources": list(query["source_types"]),
		},
	}


def _prepare_query(filters: frappe._dict) -> dict[str, Any]:
	_assert_access()
	company = str(
		filters.get("company")
		or frappe.defaults.get_user_default("Company")
		or ""
	).strip()
	if not company:
		frappe.throw(_("Company is required."), frappe.ValidationError)
	_assert_company_read_access(company)

	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None
	if from_date and to_date:
		if from_date > to_date:
			frappe.throw(_("From Date cannot be after To Date."))
		if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
			frappe.throw(
				_(
					"Expense Register supports up to {0} days per request. "
					"Narrow the date range."
				).format(MAX_DATE_RANGE_DAYS)
			)

	status = str(filters.get("expense_status") or "").strip()
	if status and status not in _EXPENSE_STATUSES:
		frappe.throw(_("Unsupported Expense Status."))

	source_type = str(filters.get("source_type") or "").strip()
	if source_type and source_type not in CONSOLIDATED_SOURCE_TYPES:
		frappe.throw(_("Unsupported Expense Source."))

	include_unposted_cashier_expenses = bool(
		cint(filters.get("include_unposted_cashier_expenses") or 0)
	)

	category = str(filters.get("expense_category") or "").strip()
	category_account = ""
	if category:
		category_account = _resolve_category_account(
			category=category,
			company=company,
		)

	requested_branch = str(filters.get("branch") or "").strip()
	branch_scope = _resolve_branch_scope(
		company=company,
		requested_branch=requested_branch,
	)
	sql_context = _build_sql_context()

	cashier_where, cashier_values = _build_cashier_where_sql(
		company=company,
		from_date=from_date,
		to_date=to_date,
		category=category,
		status=status,
		source_type=source_type,
		include_unposted_cashier_expenses=include_unposted_cashier_expenses,
		branch_scope=branch_scope,
	)
	business_expense_where, business_expense_values = _build_business_expense_where_sql(
		company=company,
		from_date=from_date,
		to_date=to_date,
		category=category,
		status=status,
		source_type=source_type,
		branch_scope=branch_scope,
	)
	ledger_where, ledger_values, voucher_types = _build_ledger_where_sql(
		company=company,
		from_date=from_date,
		to_date=to_date,
		category_account=category_account,
		status=status,
		source_type=source_type,
		branch_scope=branch_scope,
		branch_expression=sql_context["branch_expression"],
	)

	source_types = []
	if cashier_where:
		source_types.append("Cashier / POS")
	if business_expense_where:
		source_types.append("Business Expense")
	for voucher_type in voucher_types:
		label = _ACCOUNTING_VOUCHER_TYPES[voucher_type]
		if label not in source_types:
			source_types.append(label)

	return {
		"company": company,
		"requested_branch": requested_branch,
		"branch_scope_label": branch_scope["label"],
		"includes_unattributed": branch_scope["global_access"] and not requested_branch,
		"include_unposted_cashier_expenses": include_unposted_cashier_expenses,
		"cashier_where": cashier_where,
		"cashier_values": cashier_values,
		"business_expense_where": business_expense_where,
		"business_expense_values": business_expense_values,
		"ledger_where": ledger_where,
		"ledger_values": ledger_values,
		"ledger_joins": sql_context["joins"],
		"branch_expression": sql_context["branch_expression"],
		"remarks_expression": sql_context["remarks_expression"],
		"cost_center_expression": sql_context["cost_center_expression"],
		"source_types": source_types,
		"accounting_voucher_types": voucher_types,
	}


def _query_rows(
	query: dict[str, Any],
	*,
	limit: int,
	offset: int,
) -> list[dict[str, Any]]:
	union_sql, values = _union_sql(query)
	if not union_sql:
		return []
	rows = frappe.db.sql(
		f"""
			SELECT
				expense_rows.name,
				expense_rows.expense_date,
				expense_rows.branch,
				expense_rows.cashier,
				expense_rows.expense_category,
				expense_rows.amount,
				expense_rows.expense_status,
				expense_rows.ledger_status,
				expense_rows.posting_ready,
				expense_rows.description,
				expense_rows.source_type,
				expense_rows.source_doctype,
				expense_rows.source_reference,
				expense_rows.expense_account,
				expense_rows.cost_center,
				expense_rows.payment_account
			FROM ({union_sql}) expense_rows
			ORDER BY
				expense_rows.expense_date DESC,
				expense_rows.sort_creation DESC,
				expense_rows.name DESC
			LIMIT %s OFFSET %s
		""",
		values=[*values, cint(limit), cint(offset)],
		as_dict=True,
	)
	return [_serialise_row(row) for row in rows]


def _query_summary(query: dict[str, Any]) -> dict[str, Any]:
	union_sql, values = _union_sql(query)
	if not union_sql:
		return {
			"count": 0,
			"total_amount": 0,
			"posted_expense_total": 0,
			"unposted_cashier_total": 0,
			"cashier_count": 0,
			"business_count": 0,
			"business_spend": 0,
			"business_credits": 0,
			"submitted_count": 0,
			"posting_blocked_count": 0,
		}
	rows = frappe.db.sql(
		f"""
			SELECT
				COUNT(*) AS count,
				COALESCE(SUM(expense_rows.amount), 0) AS total_amount,
				COALESCE(SUM(
					CASE
						WHEN expense_rows.source_type <> 'Cashier / POS'
							OR expense_rows.ledger_status = 'Posted'
						THEN expense_rows.amount
						ELSE 0
					END
				), 0) AS posted_expense_total,
				COALESCE(SUM(
					CASE
						WHEN expense_rows.source_type = 'Cashier / POS'
							AND COALESCE(expense_rows.ledger_status, '') <> 'Posted'
						THEN expense_rows.amount
						ELSE 0
					END
				), 0) AS unposted_cashier_total,
				COALESCE(SUM(
					CASE WHEN expense_rows.source_type = 'Cashier / POS' THEN 1 ELSE 0 END
				), 0) AS cashier_count,
				COALESCE(SUM(
					CASE WHEN expense_rows.source_type <> 'Cashier / POS' THEN 1 ELSE 0 END
				), 0) AS business_count,
				COALESCE(SUM(
					CASE
						WHEN expense_rows.source_type <> 'Cashier / POS'
							AND expense_rows.amount > 0
						THEN expense_rows.amount
						ELSE 0
					END
				), 0) AS business_spend,
				COALESCE(SUM(
					CASE
						WHEN expense_rows.source_type <> 'Cashier / POS'
							AND expense_rows.amount < 0
						THEN ABS(expense_rows.amount)
						ELSE 0
					END
				), 0) AS business_credits,
				COALESCE(SUM(
					CASE WHEN expense_rows.expense_status = 'Submitted' THEN 1 ELSE 0 END
				), 0) AS submitted_count,
				COALESCE(SUM(
					CASE
						WHEN expense_rows.source_type = 'Cashier / POS'
							AND expense_rows.posting_ready = 0
						THEN 1
						ELSE 0
					END
				), 0) AS posting_blocked_count
			FROM ({union_sql}) expense_rows
		""",
		values=values,
		as_dict=True,
	)
	return dict(rows[0]) if rows else {}


def _union_sql(query: dict[str, Any]) -> tuple[str, list[Any]]:
	parts: list[str] = []
	values: list[Any] = []
	if query["cashier_where"]:
		parts.append(
			f"""
				SELECT
					CONCAT('CE:', ce.name) AS name,
					ce.expense_date AS expense_date,
					COALESCE(ce.branch, '') AS branch,
					COALESCE(ce.cashier, '') AS cashier,
					COALESCE(ce.expense_category, '') AS expense_category,
					ce.amount AS amount,
					COALESCE(ce.expense_status, 'Draft') AS expense_status,
					COALESCE(ce.ledger_status, 'Not Applicable') AS ledger_status,
					COALESCE(ce.posting_ready, 0) AS posting_ready,
					COALESCE(ce.description, '') AS description,
					'Cashier / POS' AS source_type,
					'{EXPENSE_DOCTYPE}' AS source_doctype,
					ce.name AS source_reference,
					COALESCE(ce.expense_account, '') AS expense_account,
					COALESCE(ce.cost_center, '') AS cost_center,
					COALESCE(ce.payment_account, '') AS payment_account,
					ce.creation AS sort_creation
				FROM `tab{EXPENSE_DOCTYPE}` ce
				WHERE {query["cashier_where"]}
			"""
		)
		values.extend(query["cashier_values"])

	if query["business_expense_where"]:
		parts.append(
			f"""
				SELECT
					CONCAT('BE:', be.name) AS name,
					be.expense_date AS expense_date,
					COALESCE(be.branch, '') AS branch,
					'' AS cashier,
					COALESCE(be.expense_category, '') AS expense_category,
					be.amount AS amount,
					'Posted' AS expense_status,
					'Posted' AS ledger_status,
					1 AS posting_ready,
					COALESCE(be.description, '') AS description,
					'Business Expense' AS source_type,
					'{BUSINESS_EXPENSE_DOCTYPE}' AS source_doctype,
					be.name AS source_reference,
					COALESCE(be.expense_account, '') AS expense_account,
					COALESCE(be.cost_center, '') AS cost_center,
					COALESCE(be.payment_account, '') AS payment_account,
					be.creation AS sort_creation
				FROM `tab{BUSINESS_EXPENSE_DOCTYPE}` be
				INNER JOIN `tabJournal Entry` be_je
					ON be.posting_reference_type = 'Journal Entry'
					AND be.posting_reference = be_je.name
					AND be_je.docstatus = 1
				WHERE {query["business_expense_where"]}
			"""
		)
		values.extend(query["business_expense_values"])

	if query["ledger_where"]:
		parts.append(
			f"""
				SELECT
					CONCAT('GL:', gle.name) AS name,
					gle.posting_date AS expense_date,
					{query["branch_expression"]} AS branch,
					'' AS cashier,
					COALESCE(NULLIF(acc.account_name, ''), gle.account) AS expense_category,
					(gle.debit - gle.credit) AS amount,
					'Posted' AS expense_status,
					'Posted' AS ledger_status,
					1 AS posting_ready,
					{query["remarks_expression"]} AS description,
					CASE
						WHEN gle.voucher_type = 'Purchase Invoice' THEN 'Supplier / Business'
						WHEN gle.voucher_type = 'Expense Claim' THEN 'Employee Expense'
						WHEN gle.voucher_type = 'Journal Entry' THEN 'Accounting Adjustment'
						ELSE 'Business Expense'
					END AS source_type,
					gle.voucher_type AS source_doctype,
					gle.voucher_no AS source_reference,
					gle.account AS expense_account,
					{query["cost_center_expression"]} AS cost_center,
					'' AS payment_account,
					gle.creation AS sort_creation
				FROM `tabGL Entry` gle
				INNER JOIN `tabAccount` acc ON acc.name = gle.account
				{query["ledger_joins"]}
				WHERE {query["ledger_where"]}
			"""
		)
		values.extend(query["ledger_values"])

	return "\nUNION ALL\n".join(parts), values


def _build_business_expense_where_sql(
	*,
	company: str,
	from_date,
	to_date,
	category: str,
	status: str,
	source_type: str,
	branch_scope: dict[str, Any],
) -> tuple[str, list[Any]]:
	if source_type and source_type != "Business Expense":
		return "", []
	if status and status != "Posted":
		return "", []

	clauses = [
		"be.company = %s",
		"be.docstatus = 1",
		"be.ledger_status = 'Posted'",
		"be.posting_reference_type = 'Journal Entry'",
		"COALESCE(be.posting_reference, '') <> ''",
	]
	values: list[Any] = [company]
	if from_date:
		clauses.append("be.expense_date >= %s")
		values.append(from_date)
	if to_date:
		clauses.append("be.expense_date <= %s")
		values.append(to_date)
	if category:
		clauses.append("be.expense_category = %s")
		values.append(category)
	_apply_branch_sql(
		clauses,
		values,
		branch_expression="COALESCE(be.branch, '')",
		branch_scope=branch_scope,
	)
	return " AND ".join(clauses), values


def _build_cashier_where_sql(
	*,
	company: str,
	from_date,
	to_date,
	category: str,
	status: str,
	source_type: str,
	include_unposted_cashier_expenses: bool,
	branch_scope: dict[str, Any],
) -> tuple[str, list[Any]]:
	if source_type and source_type != "Cashier / POS":
		return "", []
	clauses = ["ce.company = %s"]
	values: list[Any] = [company]
	if from_date:
		clauses.append("ce.expense_date >= %s")
		values.append(from_date)
	if to_date:
		clauses.append("ce.expense_date <= %s")
		values.append(to_date)
	if category:
		clauses.append("ce.expense_category = %s")
		values.append(category)
	if status == "Cancelled":
		clauses.append("ce.docstatus = 2")
	elif status:
		clauses.extend(["ce.docstatus <> 2", "ce.expense_status = %s"])
		values.append(status)
	else:
		clauses.extend(
			[
				"ce.docstatus <> 2",
				"COALESCE(ce.expense_status, '') <> 'Cancelled'",
			]
		)

	if not include_unposted_cashier_expenses:
		if status and status != "Posted":
			return "", []
		clauses.extend(
			[
				"COALESCE(ce.ledger_status, '') = 'Posted'",
				"COALESCE(ce.posting_reference, '') <> ''",
			]
		)
	_apply_branch_sql(
		clauses,
		values,
		branch_expression="COALESCE(ce.branch, '')",
		branch_scope=branch_scope,
	)
	return " AND ".join(clauses), values


def _build_ledger_where_sql(
	*,
	company: str,
	from_date,
	to_date,
	category_account: str,
	status: str,
	source_type: str,
	branch_scope: dict[str, Any],
	branch_expression: str,
) -> tuple[str, list[Any], list[str]]:
	if status and status != "Posted":
		return "", [], []

	voucher_types = _available_accounting_voucher_types()
	if source_type:
		voucher_types = [
			voucher_type
			for voucher_type in voucher_types
			if _ACCOUNTING_VOUCHER_TYPES[voucher_type] == source_type
		]
	if not voucher_types:
		return "", [], []

	clauses = [
		"gle.company = %s",
		"acc.company = %s",
		"acc.root_type = 'Expense'",
		"acc.is_group = 0",
		"COALESCE(acc.disabled, 0) = 0",
		"(gle.debit <> 0 OR gle.credit <> 0)",
		"(gle.debit - gle.credit) <> 0",
	]
	values: list[Any] = [company, company]
	if _doctype_has_field("GL Entry", "is_cancelled"):
		clauses.append("COALESCE(gle.is_cancelled, 0) = 0")
	if from_date:
		clauses.append("gle.posting_date >= %s")
		values.append(from_date)
	if to_date:
		clauses.append("gle.posting_date <= %s")
		values.append(to_date)
	placeholders = ", ".join(["%s"] * len(voucher_types))
	clauses.append(f"gle.voucher_type IN ({placeholders})")
	values.extend(voucher_types)
	if category_account:
		clauses.append("gle.account = %s")
		values.append(category_account)

	if _doctype_has_field(EXPENSE_DOCTYPE, "posting_reference"):
		clauses.append("ce_post.name IS NULL")
	if _doctype_has_field(BUSINESS_EXPENSE_DOCTYPE, "posting_reference"):
		clauses.append("be_post.name IS NULL")

	_apply_branch_sql(
		clauses,
		values,
		branch_expression=branch_expression,
		branch_scope=branch_scope,
	)
	return " AND ".join(clauses), values, voucher_types


def _apply_branch_sql(
	clauses: list[str],
	values: list[Any],
	*,
	branch_expression: str,
	branch_scope: dict[str, Any],
) -> None:
	branches = list(branch_scope.get("effective_branches") or [])
	if branches:
		placeholders = ", ".join(["%s"] * len(branches))
		clauses.append(f"({branch_expression}) IN ({placeholders})")
		values.extend(branches)
	elif not branch_scope.get("global_access"):
		clauses.append("1 = 0")


def _build_sql_context() -> dict[str, str]:
	joins: list[str] = []
	branch_parts: list[str] = []
	for index, voucher_type in enumerate(_ACCOUNTING_VOUCHER_TYPES, start=1):
		if not _doctype_has_field(voucher_type, "retailedge_branch"):
			continue
		alias = f"src_{index}"
		joins.append(
			f"LEFT JOIN `tab{voucher_type}` {alias} "
			f"ON gle.voucher_type = '{voucher_type}' "
			f"AND gle.voucher_no = {alias}.name"
		)
		branch_parts.append(f"NULLIF({alias}.retailedge_branch, '')")

	if _doctype_has_field(EXPENSE_DOCTYPE, "posting_reference"):
		joins.append(
			f"LEFT JOIN `tab{EXPENSE_DOCTYPE}` ce_post "
			"ON ce_post.posting_reference_type = gle.voucher_type "
			"AND ce_post.posting_reference = gle.voucher_no "
			"AND ce_post.docstatus <> 2"
		)
	if _doctype_has_field(BUSINESS_EXPENSE_DOCTYPE, "posting_reference"):
		joins.append(
			f"LEFT JOIN `tab{BUSINESS_EXPENSE_DOCTYPE}` be_post "
			"ON be_post.posting_reference_type = gle.voucher_type "
			"AND be_post.posting_reference = gle.voucher_no "
			"AND be_post.docstatus <> 2"
		)

	branch_expression = (
		f"COALESCE({', '.join(branch_parts)}, '')"
		if branch_parts
		else "''"
	)
	remarks_expression = (
		"COALESCE(gle.remarks, '')"
		if _doctype_has_field("GL Entry", "remarks")
		else "''"
	)
	cost_center_expression = (
		"COALESCE(gle.cost_center, '')"
		if _doctype_has_field("GL Entry", "cost_center")
		else "''"
	)
	return {
		"joins": "\n".join(joins),
		"branch_expression": branch_expression,
		"remarks_expression": remarks_expression,
		"cost_center_expression": cost_center_expression,
	}


def _available_accounting_voucher_types() -> list[str]:
	return [
		voucher_type
		for voucher_type in _ACCOUNTING_VOUCHER_TYPES
		if frappe.db.exists("DocType", voucher_type)
	]


def _resolve_branch_scope(
	*,
	company: str,
	requested_branch: str,
) -> dict[str, Any]:
	scope = get_operational_branch_scope(company, user=frappe.session.user)
	restricted = bool(scope.get("restricted"))
	allowed = sorted(
		str(branch).strip()
		for branch in dict.fromkeys(scope.get("allowed_branches") or [])
		if str(branch or "").strip()
	)
	if requested_branch:
		if restricted and requested_branch not in allowed:
			frappe.throw(
				_(
					"You do not have active RetailEdge Branch access to Branch {0}."
				).format(requested_branch),
				frappe.PermissionError,
			)
		effective = [requested_branch]
		label = requested_branch
	elif not restricted:
		effective = []
		label = _("Company-wide")
	else:
		effective = allowed
		label = allowed[0] if len(allowed) == 1 else _("Permitted branches")
	return {
		"global_access": not restricted,
		"restricted": restricted,
		"allowed_branches": allowed,
		"effective_branches": effective,
		"label": label,
		"source": scope.get("source"),
	}


def _resolve_category_account(*, category: str, company: str) -> str:
	if not frappe.db.exists(CATEGORY_DOCTYPE, category):
		frappe.throw(_("Expense Category {0} does not exist.").format(category))
	if not frappe.has_permission(CATEGORY_DOCTYPE, "read", doc=category):
		frappe.throw(
			_("You do not have permission to use Expense Category {0}.").format(category),
			frappe.PermissionError,
		)
	row = frappe.db.get_value(
		CATEGORY_DOCTYPE,
		category,
		["company", "is_active", "expense_account"],
		as_dict=True,
	)
	if not row or not cint(row.is_active):
		frappe.throw(_("Expense Category {0} is inactive.").format(category))
	if row.company and row.company != company:
		frappe.throw(
			_("Expense Category {0} is outside Company {1}.").format(
				category,
				company,
			),
			frappe.PermissionError,
		)
	return str(row.expense_account or "").strip()


def _map_account_categories(
	rows: list[dict[str, Any]],
	*,
	company: str,
) -> list[dict[str, Any]]:
	accounts = sorted(
		{
			str(row.get("expense_account") or "").strip()
			for row in rows
			if row.get("source_type") not in {"Cashier / POS", "Business Expense"}
			and str(row.get("expense_account") or "").strip()
		}
	)
	if not accounts:
		return rows
	try:
		category_rows = frappe.get_list(
			CATEGORY_DOCTYPE,
			filters={
				"is_active": 1,
				"expense_account": ["in", accounts],
			},
			or_filters=[
				[CATEGORY_DOCTYPE, "company", "=", company],
				[CATEGORY_DOCTYPE, "company", "is", "not set"],
			],
			fields=["name", "company", "expense_account"],
			limit_page_length=MAX_CATEGORY_MAP_ROWS,
		)
	except Exception:
		return rows

	by_account: dict[str, set[str]] = {}
	for category in category_rows:
		account = str(category.expense_account or "").strip()
		if account:
			by_account.setdefault(account, set()).add(str(category.name))
	for row in rows:
		if row.get("source_type") in {"Cashier / POS", "Business Expense"}:
			continue
		account = str(row.get("expense_account") or "").strip()
		mapped = by_account.get(account) or set()
		if len(mapped) == 1:
			row["expense_category"] = next(iter(mapped))
	return rows


def _serialise_row(row) -> dict[str, Any]:
	return {
		"name": row.name,
		"expense_date": row.expense_date,
		"branch": row.branch or "",
		"cashier": row.cashier or "",
		"expense_category": row.expense_category or "",
		"amount": flt(row.amount),
		"expense_status": row.expense_status or "",
		"ledger_status": row.ledger_status or "",
		"posting_ready": cint(row.posting_ready),
		"description": row.description or "",
		"source_type": row.source_type or "",
		"source_doctype": row.source_doctype or "",
		"source_reference": row.source_reference or "",
		"expense_account": row.expense_account or "",
		"cost_center": row.cost_center or "",
		"payment_account": row.payment_account or "",
	}


def _columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Date"), "fieldname": "expense_date", "type": "Date"},
		{"label": _("Branch"), "fieldname": "branch", "type": "Data"},
		{"label": _("Cashier"), "fieldname": "cashier", "type": "Data"},
		{"label": _("Category"), "fieldname": "expense_category", "type": "Data"},
		{"label": _("Amount"), "fieldname": "amount", "type": "Currency"},
		{"label": _("Status"), "fieldname": "expense_status", "type": "Data"},
		{"label": _("Source Type"), "fieldname": "source_type", "type": "Data"},
		{"label": _("Source"), "fieldname": "source_reference", "type": "Data"},
		{"label": _("Expense Account"), "fieldname": "expense_account", "type": "Data"},
		{"label": _("Cost Center"), "fieldname": "cost_center", "type": "Data"},
		{"label": _("Description"), "fieldname": "description", "type": "Data"},
	]


def _summary_cards(summary: dict[str, Any]) -> list[dict[str, Any]]:
	return [
		{
			"label": _("Posted Expenses"),
			"value": flt(summary.get("posted_expense_total")),
			"type": "Currency",
		},
		{
			"label": _("Unposted Cashier Exposure"),
			"value": flt(summary.get("unposted_cashier_total")),
			"type": "Currency",
		},
		{
			"label": _("Expense Lines"),
			"value": cint(summary.get("count")),
			"type": "Int",
		},
		{
			"label": _("Posted Business Expenses"),
			"value": flt(summary.get("business_spend")),
			"type": "Currency",
		},
		{
			"label": _("Business Credits / Reversals"),
			"value": flt(summary.get("business_credits")),
			"type": "Currency",
		},
		{
			"label": _("Submitted for Review"),
			"value": cint(summary.get("submitted_count")),
			"type": "Int",
		},
		{
			"label": _("Posting Blocked"),
			"value": cint(summary.get("posting_blocked_count")),
			"type": "Int",
		},
	]


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
	cache = getattr(
		frappe.local,
		"retailedge_consolidated_expense_meta_cache",
		None,
	)
	if cache is None:
		cache = {}
		frappe.local.retailedge_consolidated_expense_meta_cache = cache
	key = (doctype, fieldname)
	if key not in cache:
		try:
			cache[key] = bool(
				frappe.db.exists("DocType", doctype)
				and frappe.get_meta(doctype).has_field(fieldname)
			)
		except Exception:
			cache[key] = False
	return cache[key]


def _assert_access() -> None:
	if can_view_consolidated_business_expenses():
		return
	frappe.throw(
		_("You do not have permission to view consolidated business expenses."),
		frappe.PermissionError,
	)


def _assert_company_read_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _coerce_filters(
	filters: dict[str, Any] | frappe._dict | str | None,
) -> frappe._dict:
	if not filters:
		return frappe._dict()
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters
	if isinstance(parsed, frappe._dict):
		return parsed
	if isinstance(parsed, dict):
		return frappe._dict(parsed)
	frappe.throw(_("Invalid Expense Register filters."))
	return frappe._dict()
