# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cstr, flt, get_first_day, nowdate

from retailedge.branch_context import get_branch_query_filters, has_field
from retailedge.branch_performance import assert_can_access_branch_performance
from retailedge.sales_reporting import MAX_INVOICE_SCAN_ROWS, MAX_ITEM_SCAN_ROWS
from retailedge.sales_team_allocation import get_sales_team_allocations, resolve_sales_team_allocations

MAX_PAGE_SIZE = 100
MAX_EXPORT_ROWS = 500
MAX_LINK_RESULTS = 20


def _default_company() -> str:
	return cstr(
		frappe.defaults.get_user_default("Company")
		or frappe.defaults.get_global_default("company")
		or ""
	)


def _assert_company_access(company: str) -> None:
	if company and not frappe.has_permission("Company", "read", doc=company):
		frappe.throw(_("You do not have access to this Company."), frappe.PermissionError)


@frappe.whitelist()
def get_salesperson_performance(filters=None):
	"""Aggregate salesperson performance from submitted, permission-scoped Sales Invoices.

	R11 uses the same Sales Team allocation contract as profitability intelligence. Invoice
	amounts are allocated in Python after a bounded invoice scan so missing allocation
	percentages cannot cause every Sales Team row to receive 100% of the invoice.
	"""
	assert_can_access_branch_performance(frappe.session.user)
	filters = frappe.parse_json(filters) if isinstance(filters, str) else dict(filters or {})

	preset = filters.get("date_range_preset")
	if preset and preset != "Custom Period":
		from retailedge.reporting.date_ranges import get_preset_dates

		preset_from, preset_to = get_preset_dates(preset)
		if preset_from and preset_to:
			filters["from_date"] = str(preset_from)
			filters["to_date"] = str(preset_to)

	from_date = filters.get("from_date") or get_first_day(nowdate())
	to_date = filters.get("to_date") or nowdate()
	company = cstr(filters.get("company") or _default_company()).strip()
	_assert_company_access(company)

	conditions = ["si.docstatus = 1"]
	params: list[Any] = []
	if company:
		conditions.append("si.company = %s")
		params.append(company)
	if from_date:
		conditions.append("si.posting_date >= %s")
		params.append(from_date)
	if to_date:
		conditions.append("si.posting_date <= %s")
		params.append(to_date)
	if filters.get("customer"):
		conditions.append("si.customer = %s")
		params.append(filters.get("customer"))

	scope = get_branch_query_filters(
		"Sales Invoice",
		user=frappe.session.user,
		company=company or None,
		branch=filters.get("branch"),
	)
	branch_field = (
		"retailedge_branch"
		if has_field("Sales Invoice", "retailedge_branch")
		else ("branch" if has_field("Sales Invoice", "branch") else None)
	)
	effective_branch = filters.get("branch") or scope.get("branch")
	if branch_field and effective_branch:
		conditions.append(f"si.{branch_field} = %s")
		params.append(effective_branch)
	elif branch_field and scope.get("allowed_branches"):
		allowed = [branch for branch in scope.get("allowed_branches") if branch]
		if allowed:
			conditions.append(f"si.{branch_field} in ({', '.join(['%s'] * len(allowed))})")
			params.extend(allowed)

	if filters.get("item"):
		conditions.append(
			"""EXISTS (
				SELECT 1 FROM `tabSales Invoice Item` sii_filter
				WHERE sii_filter.parent = si.name AND sii_filter.item_code = %s
			)"""
		)
		params.append(filters.get("item"))
	if filters.get("item_group"):
		conditions.append(
			"""EXISTS (
				SELECT 1 FROM `tabSales Invoice Item` sii_filter
				WHERE sii_filter.parent = si.name AND sii_filter.item_group = %s
			)"""
		)
		params.append(filters.get("item_group"))

	where_sql = " AND ".join(conditions)
	invoice_query = f"""
		SELECT
			si.name,
			si.posting_date,
			si.creation,
			si.customer,
			COALESCE(si.grand_total, 0) AS grand_total,
			COALESCE(si.discount_amount, 0) AS discount_amount,
			COALESCE(si.net_total, 0) AS net_total,
			COALESCE(si.outstanding_amount, 0) AS outstanding_amount,
			si.status
		FROM `tabSales Invoice` si
		WHERE {where_sql}
		ORDER BY si.posting_date DESC, si.creation DESC, si.name DESC
		LIMIT %s
	"""
	invoices = frappe.db.sql(invoice_query, [*params, MAX_INVOICE_SCAN_ROWS + 1], as_dict=True)
	if len(invoices) > MAX_INVOICE_SCAN_ROWS:
		frappe.throw(
			_("More than {0} submitted Sales Invoices match this salesperson scope. Narrow the date range or filters.").format(
				MAX_INVOICE_SCAN_ROWS
			)
		)

	invoice_names = [str(row.name) for row in invoices]
	allocations = get_sales_team_allocations(invoice_names)
	item_context = _get_invoice_item_context(
		invoice_names,
		item=cstr(filters.get("item") or "").strip(),
		item_group=cstr(filters.get("item_group") or "").strip(),
	)
	all_rows = allocate_salesperson_invoice_rows(
		invoices,
		allocations=allocations,
		item_context=item_context,
		salesperson_filter=cstr(filters.get("salesperson") or "").strip(),
	)

	summary = _salesperson_summary(all_rows)
	requested_limit = int(filters.get("limit") or 50)
	limit_cap = MAX_EXPORT_ROWS if filters.get("export_mode") else MAX_PAGE_SIZE
	limit = min(max(1, requested_limit), limit_cap)
	offset = max(0, int(filters.get("offset") or 0))
	rows = all_rows[offset : offset + limit]
	return {
		"summary": summary,
		"rows": rows,
		"limit": limit,
		"offset": offset,
		"total_rows": len(all_rows),
		"company": company,
		"metadata": {
			"sales_truth": "Submitted ERPNext Sales Invoice",
			"salesperson_truth": "ERPNext Sales Team using the shared R8/R11 allocation contract",
			"allocation_rule": "Positive percentages are respected; residual is unallocated; zero/missing allocations split evenly; invoices without Sales Team are unassigned",
		},
	}


def _get_invoice_item_context(
	invoice_names: list[str], *, item: str = "", item_group: str = ""
) -> dict[str, dict[str, Any]]:
	if not invoice_names:
		return {}
	query_filters: dict[str, Any] = {
		"parent": ["in", invoice_names],
		"parenttype": "Sales Invoice",
	}
	if item:
		query_filters["item_code"] = item
	if item_group:
		query_filters["item_group"] = item_group
	rows = frappe.get_all(
		"Sales Invoice Item",
		filters=query_filters,
		fields=["parent", "item_code", "qty"],
		order_by="parent asc, idx asc",
		limit=MAX_ITEM_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_ITEM_SCAN_ROWS:
		frappe.throw(
			_("More than {0} Sales Invoice Item rows match this salesperson scope. Narrow the date range or filters.").format(
				MAX_ITEM_SCAN_ROWS
			)
		)
	context: dict[str, dict[str, Any]] = {}
	for row in rows:
		invoice = str(row.parent)
		bucket = context.setdefault(invoice, {"items": set(), "total_qty": 0.0})
		if row.get("item_code"):
			bucket["items"].add(str(row.item_code))
		bucket["total_qty"] += flt(row.get("qty"))
	return {
		invoice: {
			"items": ", ".join(sorted(bucket["items"])),
			"total_qty": flt(bucket["total_qty"]),
		}
		for invoice, bucket in context.items()
	}


def allocate_salesperson_invoice_rows(
	invoices: list[frappe._dict] | list[dict[str, Any]],
	*,
	allocations: dict[str, list[tuple[str, float]]],
	item_context: dict[str, dict[str, Any]] | None = None,
	salesperson_filter: str = "",
) -> list[dict[str, Any]]:
	"""Expand invoice amounts into salesperson rows using the shared allocation contract."""
	item_context = item_context or {}
	rows: list[dict[str, Any]] = []
	for invoice in invoices:
		invoice_name = str(invoice.get("name") or "")
		resolved_allocations = allocations.get(invoice_name)
		if resolved_allocations is None:
			resolved_allocations = resolve_sales_team_allocations([], invoice=invoice_name)
		for salesperson, weight in resolved_allocations:
			if salesperson_filter and salesperson != salesperson_filter:
				continue
			items = item_context.get(invoice_name) or {}
			rows.append(
				{
					"salesperson": salesperson,
					"sales_invoice": invoice_name,
					"posting_date": invoice.get("posting_date"),
					"customer": invoice.get("customer"),
					"items": items.get("items") or "",
					"total_qty": flt(items.get("total_qty")) * weight,
					"allocation_percentage": weight * 100.0,
					"gross_amount": flt(invoice.get("grand_total")) * weight,
					"discount": flt(invoice.get("discount_amount")) * weight,
					"net_amount": flt(invoice.get("net_total")) * weight,
					"outstanding_amount": flt(invoice.get("outstanding_amount")) * weight,
					"payment_status": invoice.get("status") or "",
				}
			)
	return rows


def _salesperson_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
	invoice_names = {str(row.get("sales_invoice") or "") for row in rows if row.get("sales_invoice")}
	gross_sales = sum(flt(row.get("gross_amount")) for row in rows)
	total_invoices = len(invoice_names)
	return {
		"gross_sales": gross_sales,
		"net_sales": sum(flt(row.get("net_amount")) for row in rows),
		"total_invoices": total_invoices,
		"total_discount": sum(flt(row.get("discount")) for row in rows),
		"total_outstanding": sum(flt(row.get("outstanding_amount")) for row in rows),
		"avg_invoice_value": gross_sales / total_invoices if total_invoices else 0.0,
	}


@frappe.whitelist()
def get_salesperson_dashboard_options():
	"""Return backward-compatible dashboard defaults without broad master preloading."""
	assert_can_access_branch_performance(frappe.session.user)
	from retailedge.branch_performance import get_candidate_branches

	branches = get_candidate_branches()
	company = _default_company() or "RetailEdge Tenant"
	default_filters = {
		"company": company if company != "RetailEdge Tenant" else "",
		"date_range_preset": "This Month",
		"from_date": get_first_day(nowdate()),
		"to_date": nowdate(),
		"branch": "",
		"salesperson": "",
		"customer": "",
		"item": "",
		"limit": 50,
		"offset": 0,
	}
	user_fullname = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	active_branch = ""
	try:
		from retailedge.branch_context import resolve_retailedge_branch_context

		branch_ctx = resolve_retailedge_branch_context(user=frappe.session.user, company=company)
		if branch_ctx and branch_ctx.get("branch"):
			active_branch = branch_ctx.get("branch")
	except (frappe.PermissionError, frappe.DoesNotExistError):
		active_branch = ""

	return {
		"branches": branches,
		"salespeople": [],
		"default_filters": default_filters,
		"tenant_name": company,
		"branch_name": active_branch or (branches[0] if branches else ""),
		"user_name": user_fullname,
	}
