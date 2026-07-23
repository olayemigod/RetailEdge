# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import flt, get_first_day, getdate, nowdate

from retailedge.branch_context import (
	get_user_allowed_branches,
	has_field,
	user_has_global_branch_access,
)
from retailedge.branch_performance import assert_can_access_branch_performance
from retailedge.ui_identity import get_retailedge_ui_identity


LINK_SEARCH_LIMIT = 20
LINK_SEARCH_FIELDS = {
	"salesperson": "Sales Person",
	"customer": "Customer",
	"item": "Item",
}


def _resolve_dashboard_branch_access(filters):
	user = frappe.session.user
	company = filters.get("company")
	requested_branch = filters.get("branch")
	global_access = user_has_global_branch_access(user=user)

	if global_access:
		return {
			"global_access": True,
			"requested_branch": requested_branch,
			"allowed_branches": [],
		}

	allowed_info = get_user_allowed_branches(user=user, company=company)
	allowed_branches = [branch for branch in allowed_info.get("branches") or [] if branch]
	allowed_branches = list(dict.fromkeys(allowed_branches))

	if not allowed_branches:
		frappe.throw(
			_("No RetailEdge branch access is assigned to your user account."),
			frappe.PermissionError,
		)

	if requested_branch and requested_branch not in allowed_branches:
		frappe.throw(
			_("You do not have access to Branch {0}.").format(requested_branch),
			frappe.PermissionError,
		)

	return {
		"global_access": False,
		"requested_branch": requested_branch,
		"allowed_branches": allowed_branches,
	}


def _validate_date_range(filters):
	from_date = filters.get("from_date")
	to_date = filters.get("to_date")
	if from_date and to_date and getdate(from_date) > getdate(to_date):
		frappe.throw(_("From Date cannot be after To Date."))


def _validate_selected_link(doctype: str, value: str, enabled_field: str | None = None):
	if not value:
		return
	if not frappe.db.exists(doctype, value):
		frappe.throw(_("{0} {1} does not exist.").format(doctype, value))
	if not frappe.has_permission(doctype, ptype="read", doc=value):
		frappe.throw(_("You do not have permission to use {0} {1}.").format(doctype, value), frappe.PermissionError)
	if enabled_field and has_field(doctype, enabled_field):
		is_disabled = frappe.db.get_value(doctype, value, enabled_field)
		if is_disabled:
			frappe.throw(_("{0} {1} is disabled.").format(doctype, value))


def _validate_dashboard_filters(filters):
	_validate_date_range(filters)
	_validate_selected_link("Sales Person", filters.get("salesperson"), "disabled")
	_validate_selected_link("Customer", filters.get("customer"), "disabled")
	_validate_selected_link("Item", filters.get("item"), "disabled")


def _branch_options(company: str | None, query: str = "", limit: int = LINK_SEARCH_LIMIT):
	branch_access = _resolve_dashboard_branch_access({"company": company})
	if branch_access["global_access"]:
		from retailedge.branch_performance import get_candidate_branches

		branches = get_candidate_branches({"company": company})
	else:
		branches = branch_access["allowed_branches"]

	query = (query or "").strip().lower()
	branches = [branch for branch in branches if not query or query in branch.lower()]
	options = []
	for branch in branches[:limit]:
		branch_company = frappe.db.get_value("Branch", branch, "company") if has_field("Branch", "company") else company
		options.append(
			{
				"value": branch,
				"label": branch,
				"description": branch_company or "",
				"company": branch_company or "",
			}
		)
	return options


def _master_link_options(fieldname: str, query: str, limit: int):
	doctype = LINK_SEARCH_FIELDS[fieldname]
	if not frappe.has_permission(doctype, ptype="read"):
		return []

	like_value = f"%{(query or '').strip()}%"
	if fieldname == "salesperson":
		filters = {"enabled": 1} if has_field(doctype, "enabled") else {}
		rows = frappe.get_list(
			doctype,
			filters=filters,
			or_filters=[[doctype, "name", "like", like_value]],
			fields=["name", "parent_sales_person"],
			order_by="name asc",
			limit_page_length=limit,
		)
		return [
			{
				"value": row.name,
				"label": row.name,
				"description": row.get("parent_sales_person") or "Enabled salesperson",
			}
			for row in rows
		]

	if fieldname == "customer":
		filters = {"disabled": 0} if has_field(doctype, "disabled") else {}
		or_filters = [[doctype, "name", "like", like_value]]
		if has_field(doctype, "customer_name"):
			or_filters.append([doctype, "customer_name", "like", like_value])
		rows = frappe.get_list(
			doctype,
			filters=filters,
			or_filters=or_filters,
			fields=["name", "customer_name", "customer_group"],
			order_by="modified desc",
			limit_page_length=limit,
		)
		return [
			{
				"value": row.name,
				"label": row.get("customer_name") or row.name,
				"description": " · ".join(part for part in (row.name, row.get("customer_group")) if part),
			}
			for row in rows
		]

	filters = {"disabled": 0}
	if has_field(doctype, "is_sales_item"):
		filters["is_sales_item"] = 1
	or_filters = [[doctype, "name", "like", like_value]]
	if has_field(doctype, "item_name"):
		or_filters.append([doctype, "item_name", "like", like_value])
	rows = frappe.get_list(
		doctype,
		filters=filters,
		or_filters=or_filters,
		fields=["name", "item_name", "item_group"],
		order_by="modified desc",
		limit_page_length=limit,
	)
	return [
		{
			"value": row.name,
			"label": row.get("item_name") or row.name,
			"description": " · ".join(part for part in (row.name, row.get("item_group")) if part),
		}
		for row in rows
	]


@frappe.whitelist()
def search_salesperson_dashboard_link(fieldname: str, txt: str = "", context=None, limit: int = LINK_SEARCH_LIMIT):
	"""Return a small permission-aware option set for dashboard Link fields."""
	assert_can_access_branch_performance(frappe.session.user)
	context = frappe.parse_json(context) if isinstance(context, str) else (context or {})
	limit = max(1, min(int(limit or LINK_SEARCH_LIMIT), 30))
	if fieldname == "branch":
		return _branch_options(context.get("company"), txt, limit)
	if fieldname not in LINK_SEARCH_FIELDS:
		frappe.throw(_("Unsupported dashboard Link field: {0}").format(fieldname))
	return _master_link_options(fieldname, txt, limit)


@frappe.whitelist()
def get_salesperson_performance(filters=None):
	"""Aggregate proportional salesperson performance from submitted invoices."""
	assert_can_access_branch_performance(frappe.session.user)
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

	preset = filters.get("date_range_preset")
	if preset and preset != "Custom Period":
		from retailedge.reporting.date_ranges import get_preset_dates

		preset_from, preset_to = get_preset_dates(preset)
		if preset_from and preset_to:
			filters["from_date"] = str(preset_from)
			filters["to_date"] = str(preset_to)

	filters.setdefault("company", frappe.defaults.get_user_default("Company") or "")
	_validate_dashboard_filters(filters)
	from_date = filters.get("from_date") or get_first_day(nowdate())
	to_date = filters.get("to_date") or nowdate()

	conditions = ["si.docstatus = 1"]
	params = []
	if filters.get("company"):
		conditions.append("si.company = %s")
		params.append(filters.get("company"))
	if from_date:
		conditions.append("si.posting_date >= %s")
		params.append(from_date)
	if to_date:
		conditions.append("si.posting_date <= %s")
		params.append(to_date)
	if filters.get("salesperson"):
		conditions.append("st.sales_person = %s")
		params.append(filters.get("salesperson"))
	if filters.get("customer"):
		conditions.append("si.customer = %s")
		params.append(filters.get("customer"))

	branch_access = _resolve_dashboard_branch_access(filters)
	branch_field = "retailedge_branch" if has_field("Sales Invoice", "retailedge_branch") else ("branch" if has_field("Sales Invoice", "branch") else None)
	if not branch_field and not branch_access["global_access"]:
		frappe.throw(
			_("Sales Invoice has no supported branch field, so branch-restricted dashboard access cannot be enforced."),
			frappe.PermissionError,
		)

	requested_branch = branch_access["requested_branch"]
	allowed_branches = branch_access["allowed_branches"]
	if branch_field and requested_branch:
		conditions.append(f"si.{branch_field} = %s")
		params.append(requested_branch)
	elif branch_field and not branch_access["global_access"]:
		conditions.append(f"si.{branch_field} in ({', '.join(['%s'] * len(allowed_branches))})")
		params.extend(allowed_branches)

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
	summary_query = f"""
		SELECT
			SUM(COALESCE(si.grand_total, 0) * (COALESCE(st.allocated_percentage, 100) / 100)) AS gross_sales,
			SUM(COALESCE(si.net_total, 0) * (COALESCE(st.allocated_percentage, 100) / 100)) AS net_sales,
			COUNT(DISTINCT si.name) AS total_invoices,
			SUM(COALESCE(si.discount_amount, 0) * (COALESCE(st.allocated_percentage, 100) / 100)) AS total_discount,
			SUM(COALESCE(si.outstanding_amount, 0) * (COALESCE(st.allocated_percentage, 100) / 100)) AS total_outstanding
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Team` st ON st.parent = si.name AND st.parenttype = 'Sales Invoice'
		WHERE {where_sql}
	"""
	summary_results = frappe.db.sql(summary_query, params, as_dict=True)
	summary = summary_results[0] if summary_results else {}
	total_invoices = flt(summary.get("total_invoices") or 0)
	gross_sales = flt(summary.get("gross_sales") or 0)
	summary["avg_invoice_value"] = gross_sales / total_invoices if total_invoices > 0 else 0.0

	limit = max(1, min(int(filters.get("limit") or 50), 500))
	offset = max(0, int(filters.get("offset") or 0))
	rows_query = f"""
		SELECT
			st.sales_person AS salesperson,
			si.name AS sales_invoice,
			si.posting_date,
			si.customer,
			GROUP_CONCAT(DISTINCT sii.item_code ORDER BY sii.item_code SEPARATOR ', ') AS items,
			SUM(sii.qty) AS total_qty,
			si.grand_total * (COALESCE(st.allocated_percentage, 100) / 100) AS gross_amount,
			si.discount_amount * (COALESCE(st.allocated_percentage, 100) / 100) AS discount,
			si.net_total * (COALESCE(st.allocated_percentage, 100) / 100) AS net_amount,
			si.outstanding_amount * (COALESCE(st.allocated_percentage, 100) / 100) AS outstanding_amount,
			si.status AS payment_status
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Team` st ON st.parent = si.name AND st.parenttype = 'Sales Invoice'
		LEFT JOIN `tabSales Invoice Item` sii ON sii.parent = si.name
		WHERE {where_sql}
		GROUP BY si.name, st.sales_person
		ORDER BY si.posting_date DESC, si.creation DESC
		LIMIT %s OFFSET %s
	"""
	rows = frappe.db.sql(rows_query, [*params, limit, offset], as_dict=True)
	return {"summary": summary, "rows": rows, "limit": limit, "offset": offset}


@frappe.whitelist()
def get_salesperson_dashboard_options():
	"""Return dashboard identity, permitted branches and safe defaults."""
	assert_can_access_branch_performance(frappe.session.user)
	identity = get_retailedge_ui_identity()
	company = (
		identity.get("company")
		or frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or ""
	)
	branch_options = _branch_options(company, "", 30)
	branches = [option["value"] for option in branch_options]
	active_branch = identity.get("branch") if identity.get("branch") in branches else ""
	if not active_branch and len(branches) == 1:
		active_branch = branches[0]

	default_filters = {
		"company": company,
		"date_range_preset": "This Month",
		"from_date": str(get_first_day(nowdate())),
		"to_date": str(nowdate()),
		"branch": active_branch,
		"salesperson": "",
		"customer": "",
		"item": "",
		"limit": 50,
		"offset": 0,
	}
	user = identity.get("user") or {}
	return {
		"branches": branches,
		"branch_options": branch_options,
		"salespeople": [],
		"default_filters": default_filters,
		"tenant_name": identity.get("tenant_name") or company,
		"company": company,
		"branch_name": active_branch,
		"user_name": user.get("full_name") or frappe.session.user,
		"user_image": user.get("image") or "",
		"identity": identity,
		"lazy_link_search": True,
	}
