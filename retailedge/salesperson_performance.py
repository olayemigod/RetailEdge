# Copyright (c) 2026, ProcessEdge Solutions and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import flt, get_first_day, getdate, nowdate

from retailedge.branch_context import get_branch_query_filters, has_field
from retailedge.branch_performance import assert_can_access_branch_performance


@frappe.whitelist()
def get_salesperson_performance(filters=None):
	"""Aggregates salesperson sales performance metrics from submitted invoices."""
	# Assert page security permissions
	assert_can_access_branch_performance(frappe.session.user)

	# Parse filters
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})

	preset = filters.get("date_range_preset")
	if preset and preset != "Custom Period":
		from retailedge.reporting.date_ranges import get_preset_dates

		preset_from, preset_to = get_preset_dates(preset)
		if preset_from and preset_to:
			filters["from_date"] = str(preset_from)
			filters["to_date"] = str(preset_to)

	# Coerce dates
	from_date = filters.get("from_date") or get_first_day(nowdate())
	to_date = filters.get("to_date") or nowdate()

	# Only fetch submitted Sales Invoices (docstatus = 1)
	conditions = ["si.docstatus = 1"]
	params = []

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

	# Branch context enforcement
	scope = get_branch_query_filters("Sales Invoice", user=frappe.session.user, branch=filters.get("branch"))

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
		allowed = [b for b in scope.get("allowed_branches") if b]
		if allowed:
			conditions.append(f"si.{branch_field} in ({', '.join(['%s'] * len(allowed))})")
			params.extend(allowed)

	# Item level EXIST checks
	if filters.get("item"):
		conditions.append("""EXISTS (
			SELECT 1 FROM `tabSales Invoice Item` sii_filter
			WHERE sii_filter.parent = si.name AND sii_filter.item_code = %s
		)""")
		params.append(filters.get("item"))

	if filters.get("item_group"):
		conditions.append("""EXISTS (
			SELECT 1 FROM `tabSales Invoice Item` sii_filter
			WHERE sii_filter.parent = si.name AND sii_filter.item_group = %s
		)""")
		params.append(filters.get("item_group"))

	where_sql = " AND ".join(conditions)

	# 1. Summary aggregations (allocated proportional split)
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

	# 2. Main table query (allocated proportional split)
	limit = min(int(filters.get("limit") or 50), 500)
	offset = int(filters.get("offset") or 0)

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
	"""Fetches filter options and user default context for the salesperson performance dashboard."""
	# Assert page security permissions
	assert_can_access_branch_performance(frappe.session.user)

	# Fetch candidate branches using the internal helper
	from retailedge.branch_performance import get_candidate_branches

	branches = get_candidate_branches()

	# Fetch active salespeople
	salespeople = (
		frappe.get_all(
			"Sales Person", filters={"enabled": 1}, fields=["name"], pluck="name", limit_page_length=500
		)
		or []
	)

	default_filters = {
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

	# Resolve user fullname and company details
	user_fullname = frappe.db.get_value("User", frappe.session.user, "full_name") or frappe.session.user
	company = (
		frappe.defaults.get_user_default("Company")
		or frappe.db.get_single_value("Global Defaults", "default_company")
		or "RetailEdge Tenant"
	)

	# Resolve active branch from user context
	active_branch = ""
	try:
		from retailedge.branch_context import resolve_retailedge_branch_context

		branch_ctx = resolve_retailedge_branch_context(user=frappe.session.user)
		if branch_ctx and branch_ctx.get("branch"):
			active_branch = branch_ctx.get("branch")
	except Exception:
		pass

	return {
		"branches": branches,
		"salespeople": salespeople,
		"default_filters": default_filters,
		"tenant_name": company,
		"branch_name": active_branch or (branches[0] if branches else ""),
		"user_name": user_fullname,
	}
