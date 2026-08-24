from __future__ import annotations

from math import ceil
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, getdate, today

from retailedge.branch_context import (
	get_user_allowed_branches,
	user_has_global_branch_access,
	validate_user_branch_access,
)

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100
MAX_LINK_RESULTS = 20
MAX_EXPORT_ROWS = 5000
MAX_DATE_RANGE_DAYS = 366

_ALLOWED_ROLES = {
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
_ACCOUNT_TYPES = ("Cash", "Bank")
_MOVEMENT_TYPES = ("Money In", "Money Out", "Transfer", "Adjustment")
_BRANCH_VOUCHER_SPECS = (
	("Payment Entry", "pe"),
	("Sales Invoice", "si"),
	("POS Invoice", "posi"),
	("Purchase Invoice", "pi"),
)


@frappe.whitelist()
def get_cash_movement_context() -> dict[str, Any]:
	_assert_cash_movement_access()
	user = frappe.session.user
	company = str(frappe.defaults.get_user_default("Company") or "").strip()
	if company:
		_assert_company_read_access(company)
	branch_scope = _resolve_branch_scope(company=company, requested_branch="") if company else _empty_branch_scope()
	default_branch = str(
		frappe.defaults.get_user_default("RetailEdge Branch")
		or frappe.defaults.get_user_default("Branch")
		or ""
	).strip()
	if default_branch and company:
		try:
			validate_user_branch_access(default_branch, user=user, company=company, throw=True)
		except (frappe.PermissionError, frappe.ValidationError):
			default_branch = ""
	if not default_branch and len(branch_scope["allowed_branches"]) == 1:
		default_branch = branch_scope["allowed_branches"][0]

	return {
		"default_filters": {
			"company": company,
			"branch": default_branch,
			"from_date": str(get_first_day(today())),
			"to_date": today(),
			"account": "",
			"movement_type": "",
			"page_size": DEFAULT_PAGE_SIZE,
		},
		"tenant_name": company,
		"branch_name": default_branch,
		"user_name": frappe.db.get_value("User", user, "full_name") or user,
		"movement_types": list(_MOVEMENT_TYPES),
		"limits": {
			"page_size": MAX_PAGE_SIZE,
			"link_results": MAX_LINK_RESULTS,
			"export_rows": MAX_EXPORT_ROWS,
			"date_range_days": MAX_DATE_RANGE_DAYS,
		},
		"scope": {
			"global_branch_access": int(branch_scope["global_access"]),
			"allowed_branch_count": len(branch_scope["allowed_branches"]),
		},
		"data_policy": {
			"source": _("Posted ERPNext General Ledger entries for Cash and Bank accounts."),
			"branch_scope": _(
				"Branch views include only accounting vouchers with a resolved RetailEdge Branch. "
				"Unattributed adjustments remain visible only in authorized company-wide views."
			),
			"transfers": _(
				"Transfers between Cash/Bank accounts can appear once on each account; their company-wide net effect is zero."
			),
		},
	}


@frappe.whitelist()
def search_cash_movement_options(
	kind: str,
	txt: str = "",
	company: str = "",
) -> list[dict[str, Any]]:
	_assert_cash_movement_access()
	kind = str(kind or "").strip().lower()
	txt = str(txt or "").strip()
	company = str(company or frappe.defaults.get_user_default("Company") or "").strip()

	if kind == "company":
		return _search_companies(txt)
	if company:
		_assert_company_read_access(company)
	if kind == "branch":
		return _search_branches(txt=txt, company=company)
	if kind == "account":
		return _search_cash_accounts(txt=txt, company=company)
	frappe.throw(_("Unsupported Cash Movement search type."))


@frappe.whitelist()
def get_cash_movement(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	query = _prepare_query(filters)
	page = max(1, cint(page) or 1)
	page_size = max(
		1,
		min(cint(page_size) or cint(filters.get("page_size")) or DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE),
	)

	summary = _query_summary(query)
	total_rows = cint(summary.get("movement_count"))
	total_pages = max(1, ceil(total_rows / page_size)) if total_rows else 1
	if page > total_pages:
		page = total_pages
	rows = _query_rows(query, limit=page_size, offset=(page - 1) * page_size)
	return {
		"columns": _columns(),
		"rows": rows,
		"summary": _summary_cards(summary, currency=query["currency"]),
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
			"branch_scope": query["branch_scope_label"],
			"includes_unattributed": int(query["includes_unattributed"]),
			"currency": query["currency"],
		},
	}


@frappe.whitelist()
def get_cash_movement_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	query = _prepare_query(_coerce_filters(filters))
	rows = _query_rows(query, limit=MAX_EXPORT_ROWS + 1, offset=0)
	if len(rows) > MAX_EXPORT_ROWS:
		frappe.throw(
			_(
				"More than {0} cash movements match this export. "
				"Narrow the date, Branch, Account, or Movement Type filters first."
			).format(MAX_EXPORT_ROWS)
		)
	summary = _query_summary(query)
	return {
		"columns": _columns(),
		"rows": rows,
		"summary": _summary_cards(summary, currency=query["currency"]),
		"scope": {
			"company": query["company"],
			"branch": query["requested_branch"],
			"branch_scope": query["branch_scope_label"],
			"currency": query["currency"],
		},
	}


def _prepare_query(filters: frappe._dict) -> dict[str, Any]:
	_assert_cash_movement_access()
	company = str(filters.get("company") or frappe.defaults.get_user_default("Company") or "").strip()
	if not company:
		frappe.throw(_("Company is required."))
	_assert_company_read_access(company)

	from_date = getdate(filters.get("from_date")) if filters.get("from_date") else None
	to_date = getdate(filters.get("to_date")) if filters.get("to_date") else None
	if from_date and to_date:
		if from_date > to_date:
			frappe.throw(_("From Date cannot be after To Date."))
		if (to_date - from_date).days + 1 > MAX_DATE_RANGE_DAYS:
			frappe.throw(
				_("Cash Movement supports up to {0} days per request. Narrow the date range.").format(
					MAX_DATE_RANGE_DAYS
				)
			)

	account = str(filters.get("account") or "").strip()
	if account:
		_assert_cash_account(account=account, company=company)
	movement_type = str(filters.get("movement_type") or "").strip()
	if movement_type and movement_type not in _MOVEMENT_TYPES:
		frappe.throw(_("Unsupported Movement Type."))

	requested_branch = str(filters.get("branch") or "").strip()
	branch_scope = _resolve_branch_scope(company=company, requested_branch=requested_branch)
	sql_context = _get_sql_context()
	where_sql, values = _build_where_sql(
		company=company,
		from_date=from_date,
		to_date=to_date,
		account=account,
		movement_type=movement_type,
		branch_scope=branch_scope,
		branch_expression=sql_context["branch_expression"],
		movement_expression=sql_context["movement_expression"],
	)
	currency = frappe.db.get_value("Company", company, "default_currency") or ""
	return {
		"company": company,
		"requested_branch": requested_branch,
		"branch_scope_label": branch_scope["label"],
		"includes_unattributed": branch_scope["global_access"] and not requested_branch,
		"currency": currency,
		"joins": sql_context["joins"],
		"branch_expression": sql_context["branch_expression"],
		"movement_expression": sql_context["movement_expression"],
		"payment_method_expression": sql_context["payment_method_expression"],
		"where_sql": where_sql,
		"values": values,
	}


def _query_rows(query: dict[str, Any], *, limit: int, offset: int) -> list[dict[str, Any]]:
	sql = f"""
		SELECT
			gle.posting_date,
			gle.account,
			gle.voucher_type,
			gle.voucher_no,
			{query['branch_expression']} AS branch,
			{query['movement_expression']} AS movement_type,
			{query['payment_method_expression']} AS payment_method,
			gle.debit AS money_in,
			gle.credit AS money_out,
			(gle.debit - gle.credit) AS net_change
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		{query['joins']}
		WHERE {query['where_sql']}
		ORDER BY gle.posting_date DESC, gle.creation DESC, gle.name DESC
		LIMIT %s OFFSET %s
	"""
	rows = frappe.db.sql(
		sql,
		values=[*query["values"], cint(limit), cint(offset)],
		as_dict=True,
	)
	return [
		{
			"posting_date": row.posting_date,
			"account": row.account,
			"branch": row.branch or "",
			"movement_type": row.movement_type or "",
			"payment_method": row.payment_method or "",
			"money_in": flt(row.money_in),
			"money_out": flt(row.money_out),
			"net_change": flt(row.net_change),
			"voucher_type": row.voucher_type or "",
			"voucher_no": row.voucher_no or "",
		}
		for row in rows
	]


def _query_summary(query: dict[str, Any]) -> dict[str, Any]:
	sql = f"""
		SELECT
			COUNT(gle.name) AS movement_count,
			COALESCE(SUM(gle.debit), 0) AS money_in,
			COALESCE(SUM(gle.credit), 0) AS money_out,
			COALESCE(SUM(gle.debit - gle.credit), 0) AS net_change,
			COUNT(DISTINCT gle.account) AS account_count
		FROM `tabGL Entry` gle
		INNER JOIN `tabAccount` acc ON acc.name = gle.account
		{query['joins']}
		WHERE {query['where_sql']}
	"""
	rows = frappe.db.sql(sql, values=query["values"], as_dict=True)
	return (
		dict(rows[0])
		if rows
		else {
			"movement_count": 0,
			"money_in": 0,
			"money_out": 0,
			"net_change": 0,
			"account_count": 0,
		}
	)


def _get_sql_context() -> dict[str, str]:
	cached = getattr(frappe.local, "retailedge_cash_movement_sql_context", None)
	if cached is None:
		cached = _build_sql_context()
		frappe.local.retailedge_cash_movement_sql_context = cached
	return cached


def _build_sql_context() -> dict[str, str]:
	joins: list[str] = []
	branch_parts: list[str] = []
	joined_aliases: set[str] = set()

	for doctype, alias in _BRANCH_VOUCHER_SPECS:
		if not _doctype_has_field(doctype, "retailedge_branch"):
			continue
		joins.append(
			f"LEFT JOIN `tab{doctype}` {alias} "
			f"ON gle.voucher_type = '{doctype}' AND gle.voucher_no = {alias}.name"
		)
		joined_aliases.add(alias)
		branch_parts.append(f"NULLIF({alias}.retailedge_branch, '')")

	payment_type_expression = "''"
	payment_method_expression = "''"
	if _doctype_has_field("Payment Entry", "payment_type"):
		if "pe" not in joined_aliases:
			joins.append(
				"LEFT JOIN `tabPayment Entry` pe "
				"ON gle.voucher_type = 'Payment Entry' AND gle.voucher_no = pe.name"
			)
		payment_type_expression = "COALESCE(pe.payment_type, '')"
		if _doctype_has_field("Payment Entry", "mode_of_payment"):
			payment_method_expression = "COALESCE(pe.mode_of_payment, '')"

	branch_expression = f"COALESCE({', '.join(branch_parts)}, '')" if branch_parts else "''"
	movement_expression = f"""
		CASE
			WHEN gle.voucher_type = 'Payment Entry'
				AND {payment_type_expression} = 'Internal Transfer' THEN 'Transfer'
			WHEN gle.voucher_type = 'Journal Entry' THEN 'Adjustment'
			WHEN (gle.debit - gle.credit) > 0 THEN 'Money In'
			WHEN (gle.debit - gle.credit) < 0 THEN 'Money Out'
			ELSE ''
		END
	""".strip()
	return {
		"joins": "\n".join(joins),
		"branch_expression": branch_expression,
		"movement_expression": movement_expression,
		"payment_method_expression": payment_method_expression,
	}


def _build_where_sql(
	*,
	company: str,
	from_date,
	to_date,
	account: str,
	movement_type: str,
	branch_scope: dict[str, Any],
	branch_expression: str,
	movement_expression: str,
) -> tuple[str, list[Any]]:
	clauses = [
		"gle.company = %s",
		"acc.company = %s",
		"acc.is_group = 0",
		"acc.disabled = 0",
		"acc.account_type IN ('Cash', 'Bank')",
		"(gle.debit <> 0 OR gle.credit <> 0)",
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
	if account:
		clauses.append("gle.account = %s")
		values.append(account)
	if movement_type:
		clauses.append(f"({movement_expression}) = %s")
		values.append(movement_type)

	branches = list(branch_scope.get("effective_branches") or [])
	if branches:
		placeholders = ", ".join(["%s"] * len(branches))
		clauses.append(f"({branch_expression}) IN ({placeholders})")
		values.extend(branches)
	elif not branch_scope.get("global_access"):
		clauses.append("1 = 0")
	return " AND ".join(clauses), values


def _resolve_branch_scope(*, company: str, requested_branch: str) -> dict[str, Any]:
	user = frappe.session.user
	global_access = user_has_global_branch_access(user=user)
	if global_access:
		if requested_branch:
			validate_user_branch_access(requested_branch, user=user, company=company, throw=True)
		return {
			"global_access": True,
			"allowed_branches": [],
			"effective_branches": [requested_branch] if requested_branch else [],
			"label": requested_branch or _("Company-wide"),
		}

	allowed = sorted(
		str(branch)
		for branch in (get_user_allowed_branches(user=user, company=company).get("branches") or [])
		if branch
	)
	if requested_branch:
		validate_user_branch_access(requested_branch, user=user, company=company, throw=True)
		effective = [requested_branch]
		label = requested_branch
	else:
		effective = allowed
		label = _("Permitted branches") if len(allowed) != 1 else allowed[0]
	return {
		"global_access": False,
		"allowed_branches": allowed,
		"effective_branches": effective,
		"label": label,
	}


def _empty_branch_scope() -> dict[str, Any]:
	return {
		"global_access": False,
		"allowed_branches": [],
		"effective_branches": [],
		"label": "",
	}


def _search_companies(txt: str) -> list[dict[str, Any]]:
	rows = frappe.get_list(
		"Company",
		or_filters={"name": ["like", f"%{txt}%"], "company_name": ["like", f"%{txt}%"]},
		fields=["name", "company_name", "default_currency"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [
		{
			"value": row.name,
			"label": row.company_name or row.name,
			"description": row.default_currency or "",
		}
		for row in rows
	]


def _search_branches(*, txt: str, company: str) -> list[dict[str, Any]]:
	if not company:
		return []
	scope = _resolve_branch_scope(company=company, requested_branch="")
	filters: dict[str, Any] = {"company": company}
	if not scope["global_access"]:
		if not scope["allowed_branches"]:
			return []
		filters["name"] = ["in", scope["allowed_branches"]]
	rows = frappe.get_list(
		"Branch",
		filters=filters,
		or_filters={"name": ["like", f"%{txt}%"]},
		fields=["name"],
		order_by="name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [{"value": row.name, "label": row.name} for row in rows]


def _search_cash_accounts(*, txt: str, company: str) -> list[dict[str, Any]]:
	if not company:
		return []
	rows = frappe.get_list(
		"Account",
		filters={
			"company": company,
			"is_group": 0,
			"disabled": 0,
			"account_type": ["in", list(_ACCOUNT_TYPES)],
		},
		or_filters={"name": ["like", f"%{txt}%"], "account_name": ["like", f"%{txt}%"]},
		fields=["name", "account_name", "account_type", "account_currency"],
		order_by="account_name asc, name asc",
		limit_page_length=MAX_LINK_RESULTS,
	)
	return [
		{
			"value": row.name,
			"label": row.account_name or row.name,
			"description": " · ".join(filter(None, [row.account_type, row.account_currency])),
		}
		for row in rows
	]


def _assert_cash_account(*, account: str, company: str) -> None:
	row = frappe.db.get_value(
		"Account",
		account,
		["company", "account_type", "is_group", "disabled"],
		as_dict=True,
	)
	if not row:
		frappe.throw(_("Account {0} does not exist.").format(account))
	if not frappe.has_permission("Account", "read", doc=account):
		frappe.throw(
			_("You do not have permission to use Account {0}.").format(account),
			frappe.PermissionError,
		)
	if row.company != company:
		frappe.throw(
			_("Account {0} is outside Company {1}.").format(account, company),
			frappe.PermissionError,
		)
	if row.account_type not in _ACCOUNT_TYPES or cint(row.is_group) or cint(row.disabled):
		frappe.throw(_("Account {0} is not an active Cash or Bank ledger account.").format(account))


def _columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Date"), "fieldname": "posting_date", "type": "Date"},
		{"label": _("Account"), "fieldname": "account", "type": "Link", "doctype": "Account"},
		{"label": _("Branch"), "fieldname": "branch", "type": "Data"},
		{"label": _("Movement"), "fieldname": "movement_type", "type": "Data"},
		{"label": _("Payment Method"), "fieldname": "payment_method", "type": "Data"},
		{"label": _("Money In"), "fieldname": "money_in", "type": "Currency"},
		{"label": _("Money Out"), "fieldname": "money_out", "type": "Currency"},
		{"label": _("Net Change"), "fieldname": "net_change", "type": "Currency"},
		{"label": _("Source Type"), "fieldname": "voucher_type", "type": "Data"},
		{
			"label": _("Source"),
			"fieldname": "voucher_no",
			"type": "Dynamic Link",
			"options": "voucher_type",
		},
	]


def _summary_cards(summary: dict[str, Any], *, currency: str) -> list[dict[str, Any]]:
	return [
		{
			"key": "money_in",
			"label": _("Money In"),
			"value": flt(summary.get("money_in")),
			"type": "Currency",
			"currency": currency,
		},
		{
			"key": "money_out",
			"label": _("Money Out"),
			"value": flt(summary.get("money_out")),
			"type": "Currency",
			"currency": currency,
		},
		{
			"key": "net_change",
			"label": _("Net Change"),
			"value": flt(summary.get("net_change")),
			"type": "Currency",
			"currency": currency,
		},
		{
			"key": "movement_count",
			"label": _("Movements"),
			"value": cint(summary.get("movement_count")),
			"type": "Int",
		},
	]


def _doctype_has_field(doctype: str, fieldname: str) -> bool:
	cache = getattr(frappe.local, "retailedge_cash_movement_meta_cache", None)
	if cache is None:
		cache = {}
		frappe.local.retailedge_cash_movement_meta_cache = cache
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


def _assert_cash_movement_access() -> None:
	roles = set(frappe.get_roles(frappe.session.user))
	if not roles.intersection(_ALLOWED_ROLES):
		frappe.throw(_("You do not have permission to view Cash Movement."), frappe.PermissionError)


def _assert_company_read_access(company: str) -> None:
	if not frappe.db.exists("Company", company):
		frappe.throw(_("Company {0} does not exist.").format(company))
	if not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(
			_("You do not have permission to use Company {0}.").format(company),
			frappe.PermissionError,
		)


def _coerce_filters(filters: dict[str, Any] | str | None) -> frappe._dict:
	if not filters:
		return frappe._dict()
	parsed = frappe.parse_json(filters) if isinstance(filters, str) else filters
	if isinstance(parsed, frappe._dict):
		return parsed
	if isinstance(parsed, dict):
		return frappe._dict(parsed)
	frappe.throw(_("Invalid Cash Movement filters."))
	return frappe._dict()
