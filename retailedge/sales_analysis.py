from __future__ import annotations

from collections import defaultdict
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.sales_reporting import (
	MAX_ITEM_SCAN_ROWS,
	_assert_report_access,
	_coerce_filters,
	_company_currency,
	_export_response,
	_filter_headers_by_salesperson,
	_get_permitted_invoice_headers,
	_page_response,
	_signed_for_return,
	_validate_filters,
)
from retailedge.sales_team_allocation import get_sales_team_allocations

DEFAULT_GROUP_BY = "Month"
SUPPORTED_GROUP_BY = (
	"Day",
	"Week",
	"Month",
	"Quarter",
	"Year",
	"Item",
	"Item Group",
	"Customer",
	"Customer Group",
	"Branch",
	"Salesperson",
	"Warehouse",
)

GROUP_LABELS = {
	"Day": "Day",
	"Week": "Week",
	"Month": "Month",
	"Quarter": "Quarter",
	"Year": "Year",
	"Item": "Item",
	"Item Group": "Item Group",
	"Customer": "Customer",
	"Customer Group": "Customer Group",
	"Branch": "Branch",
	"Salesperson": "Salesperson",
	"Warehouse": "Warehouse",
}


@frappe.whitelist()
def get_sales_analysis(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = 50,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	filters = _coerce_filters(filters)
	dataset = _build_sales_analysis_dataset(filters)
	apply_materialized_report_sort(dataset, sort, "sales-analysis")
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_sales_analysis_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_sales_analysis_dataset(filters)
	return {
		**_export_response(dataset),
		"group_by": dataset.get("group_by") or DEFAULT_GROUP_BY,
		"show_costs": int(bool(dataset.get("show_costs"))),
		"metadata": dataset.get("metadata") or {},
	}


def _build_sales_analysis_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_filters(filters)
	_assert_report_access(filters)
	group_by = _normalise_group_by(filters.get("group_by"))
	show_costs = _can_show_profitability()

	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))
	header_map = {str(row.name): row for row in headers}
	items = _get_analysis_items(list(header_map), filters, include_cost=show_costs)

	customer_groups = _customer_group_map(headers) if group_by == "Customer Group" else {}
	sales_allocations = (
		get_sales_team_allocations(list(header_map))
		if group_by == "Salesperson"
		else {}
	)

	buckets: dict[str, dict[str, Any]] = {}
	for item in items:
		header = header_map.get(str(item.parent))
		if not header:
			continue
		for group_key, group_label, weight in _group_entries(
			group_by,
			header,
			item,
			customer_groups=customer_groups,
			sales_allocations=sales_allocations,
		):
			bucket = buckets.setdefault(
				group_key,
				_new_bucket(group_key, group_label),
			)
			_add_line_to_bucket(
				bucket,
				header,
				item,
				weight=weight,
				include_cost=show_costs,
			)

	rows = [_finalise_bucket(bucket, include_cost=show_costs) for bucket in buckets.values()]
	rows.sort(key=lambda row: (-flt(row.get("net_sales")), str(row.get("group_label") or "")))

	currency = _company_currency(filters.company)
	summary = _summary(rows, invoice_count=len(headers), include_cost=show_costs)
	return {
		"title": _("Sales Analysis"),
		"columns": _sales_analysis_columns(currency, group_by, include_cost=show_costs),
		"rows": rows,
		"summary": summary,
		"company_currency": currency,
		"group_by": group_by,
		"show_costs": int(show_costs),
		"scan": {
			"invoices": len(headers),
			"item_rows": len(items),
			"invoice_limit": 2000,
			"item_limit": MAX_ITEM_SCAN_ROWS,
		},
		"metadata": {
			"source": "Submitted ERPNext Sales Invoice / Sales Invoice Item",
			"sales_truth": "Submitted Sales Invoice item base net amounts with returns reversed",
			"profitability_truth": (
				"R8 transactional recorded-cost contribution"
				if show_costs
				else "Hidden by profitability access or cost-visibility policy"
			),
			"accounting_profit_truth": "ERPNext Profit and Loss remains authoritative accounting profit",
			"salesperson_truth": "ERPNext Sales Team shared allocation contract",
			"branch_truth": "RetailEdge authoritative transaction branch attribution",
			"cashier_dimension": "Not exposed; document owner is not treated as cashier",
			"quantity_note": "Quantity is additive operational volume and may mix stock units outside item-level analysis.",
		},
	}


def _normalise_group_by(value: Any) -> str:
	raw = str(value or DEFAULT_GROUP_BY).strip()
	lookup = {item.casefold(): item for item in SUPPORTED_GROUP_BY}
	resolved = lookup.get(raw.casefold())
	if not resolved:
		frappe.throw(
			_("Group By must be one of: {0}.").format(", ".join(SUPPORTED_GROUP_BY))
		)
	return resolved


def _can_show_profitability() -> bool:
	try:
		if should_hide_cost_price():
			return False
		if not frappe.db.exists("Page", "profitability-intelligence"):
			return False
		return bool(frappe.get_doc("Page", "profitability-intelligence").is_permitted())
	except Exception:
		return False


def _get_analysis_items(
	invoice_names: list[str],
	filters: frappe._dict,
	*,
	include_cost: bool,
) -> list[frappe._dict]:
	if not invoice_names:
		return []

	query_filters: dict[str, Any] = {
		"parenttype": "Sales Invoice",
		"parent": ["in", invoice_names],
	}
	if filters.get("item_code"):
		query_filters["item_code"] = filters.item_code
	if filters.get("item_group"):
		query_filters["item_group"] = filters.item_group
	if filters.get("warehouse"):
		query_filters["warehouse"] = filters.warehouse

	fields = [
		"parent",
		"item_code",
		"item_name",
		"item_group",
		"stock_uom",
		"qty",
		"stock_qty",
		"base_net_amount",
		"warehouse",
	]
	if include_cost:
		fields.append("incoming_rate")

	rows = frappe.get_all(
		"Sales Invoice Item",
		filters=query_filters,
		fields=fields,
		order_by="parent asc, idx asc",
		limit=MAX_ITEM_SCAN_ROWS + 1,
	)
	if len(rows) > MAX_ITEM_SCAN_ROWS:
		frappe.throw(
			_(
				"More than {0} Sales Invoice item rows match this analysis. Narrow the date range, Item, Item Group, Branch, or Warehouse."
			).format(MAX_ITEM_SCAN_ROWS)
		)
	return rows


def _customer_group_map(headers: list[frappe._dict]) -> dict[str, str]:
	customers = sorted(
		{
			str(row.get("customer") or "").strip()
			for row in headers
			if str(row.get("customer") or "").strip()
		}
	)
	if not customers:
		return {}
	rows = frappe.get_list(
		"Customer",
		filters={"name": ["in", customers]},
		fields=["name", "customer_group"],
		order_by="name asc",
		limit=max(len(customers), 1),
	)
	return {
		str(row.name): str(row.customer_group or "").strip()
		for row in rows
	}


def _group_entries(
	group_by: str,
	header: frappe._dict,
	item: frappe._dict,
	*,
	customer_groups: dict[str, str],
	sales_allocations: dict[str, list[tuple[str, float]]],
) -> list[tuple[str, str, float]]:
	invoice = str(header.get("name") or item.get("parent") or "")
	if group_by == "Salesperson":
		return [
			(str(name), str(name), flt(weight))
			for name, weight in (
				sales_allocations.get(invoice)
				or [(_("Unassigned Salesperson"), 1.0)]
			)
		]

	if group_by in {"Day", "Week", "Month", "Quarter", "Year"}:
		key, label = _period_group(header.get("posting_date"), group_by)
		return [(key, label, 1.0)]

	if group_by == "Item":
		key = str(item.get("item_code") or "").strip() or _("Unspecified Item")
		label = str(item.get("item_name") or key)
	elif group_by == "Item Group":
		key = str(item.get("item_group") or "").strip() or _("Unspecified Item Group")
		label = key
	elif group_by == "Customer":
		key = str(header.get("customer") or "").strip() or _("Unspecified Customer")
		label = str(header.get("customer_name") or key)
	elif group_by == "Customer Group":
		customer = str(header.get("customer") or "").strip()
		key = customer_groups.get(customer) or _("Unspecified Customer Group")
		label = key
	elif group_by == "Branch":
		key = str(header.get("branch") or "").strip() or _("Unattributed Branch")
		label = key
	elif group_by == "Warehouse":
		key = str(item.get("warehouse") or "").strip() or _("Unspecified Warehouse")
		label = key
	else:
		frappe.throw(_("Unsupported Sales Analysis dimension."))

	return [(key, label, 1.0)]


def _period_group(value: Any, group_by: str) -> tuple[str, str]:
	resolved = getdate(value)
	if group_by == "Day":
		key = resolved.isoformat()
		return key, key
	if group_by == "Week":
		iso_year, iso_week, _weekday = resolved.isocalendar()
		key = f"{iso_year}-W{iso_week:02d}"
		return key, _("Week {0}, {1}").format(iso_week, iso_year)
	if group_by == "Month":
		key = f"{resolved.year}-{resolved.month:02d}"
		return key, resolved.strftime("%b %Y")
	if group_by == "Quarter":
		quarter = ((resolved.month - 1) // 3) + 1
		key = f"{resolved.year}-Q{quarter}"
		return key, _("Q{0} {1}").format(quarter, resolved.year)
	if group_by == "Year":
		key = str(resolved.year)
		return key, key
	frappe.throw(_("Unsupported Sales Analysis period."))


def _new_bucket(group_key: str, group_label: str) -> dict[str, Any]:
	return {
		"group_key": group_key,
		"group_label": group_label,
		"sold_qty": 0.0,
		"returned_qty": 0.0,
		"net_qty": 0.0,
		"sales_value": 0.0,
		"returns_value": 0.0,
		"net_sales": 0.0,
		"recorded_cost": 0.0,
		"gross_profit": 0.0,
		"_invoices": set(),
		"_missing_recorded_cost": False,
	}


def _add_line_to_bucket(
	bucket: dict[str, Any],
	header: frappe._dict,
	item: frappe._dict,
	*,
	weight: float = 1.0,
	include_cost: bool = False,
) -> None:
	weight = flt(weight)
	is_return = cint(header.get("is_return"))
	qty = flt(item.get("qty"))
	stock_qty = flt(item.get("stock_qty"))
	net_amount = flt(item.get("base_net_amount"))

	signed_qty = -abs(qty) if is_return else qty
	signed_net = _signed_for_return(net_amount, is_return)
	bucket["sold_qty"] += (0.0 if is_return else max(qty, 0.0)) * weight
	bucket["returned_qty"] += (abs(qty) if is_return else 0.0) * weight
	bucket["net_qty"] += signed_qty * weight
	bucket["sales_value"] += (0.0 if is_return else net_amount) * weight
	bucket["returns_value"] += (abs(net_amount) if is_return else 0.0) * weight
	bucket["net_sales"] += signed_net * weight

	if include_cost:
		incoming_rate = flt(item.get("incoming_rate"))
		signed_stock_qty = -abs(stock_qty) if is_return else stock_qty
		recorded_cost = incoming_rate * signed_stock_qty * weight
		bucket["recorded_cost"] += recorded_cost
		bucket["gross_profit"] += signed_net * weight - recorded_cost
		if not is_return and signed_net > 0 and incoming_rate <= 0:
			bucket["_missing_recorded_cost"] = True

	invoice = str(header.get("name") or item.get("parent") or "")
	if invoice:
		bucket["_invoices"].add(invoice)


def _finalise_bucket(bucket: dict[str, Any], *, include_cost: bool) -> dict[str, Any]:
	row = dict(bucket)
	row["invoice_count"] = len(row.pop("_invoices", set()))
	row["average_selling_price"] = (
		flt(row["net_sales"]) / flt(row["net_qty"])
		if flt(row["net_qty"])
		else 0.0
	)
	missing_cost = bool(row.pop("_missing_recorded_cost", False))
	if include_cost:
		row["missing_recorded_cost"] = int(missing_cost)
		row["gross_margin_percent"] = (
			flt(row["gross_profit"]) / flt(row["net_sales"]) * 100.0
			if flt(row["net_sales"]) > 0
			else 0.0
		)
	else:
		row.pop("recorded_cost", None)
		row.pop("gross_profit", None)
	return row


def _summary(
	rows: list[dict[str, Any]],
	*,
	invoice_count: int,
	include_cost: bool,
) -> list[dict[str, Any]]:
	net_sales = sum(flt(row.get("net_sales")) for row in rows)
	summary = [
		{
			"label": _("Net Sales"),
			"value": net_sales,
			"datatype": "Currency",
		},
		{
			"label": _("Sales Value"),
			"value": sum(flt(row.get("sales_value")) for row in rows),
			"datatype": "Currency",
		},
		{
			"label": _("Returns"),
			"value": sum(flt(row.get("returns_value")) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Invoices"), "value": invoice_count, "datatype": "Int"},
	]
	if include_cost:
		recorded_cost = sum(flt(row.get("recorded_cost")) for row in rows)
		gross_profit = net_sales - recorded_cost
		summary.extend(
			[
				{
					"label": _("Recorded Item Cost"),
					"value": recorded_cost,
					"datatype": "Currency",
				},
				{
					"label": _("Transactional Gross Profit"),
					"value": gross_profit,
					"datatype": "Currency",
				},
				{
					"label": _("Transactional Gross Margin"),
					"value": (
						gross_profit / net_sales * 100.0
						if net_sales > 0
						else 0.0
					),
					"datatype": "Percent",
				},
			]
		)
	return summary


def _sales_analysis_columns(
	currency: str,
	group_by: str,
	*,
	include_cost: bool,
) -> list[dict[str, Any]]:
	columns = [
		{
			"fieldname": "group_label",
			"label": _(GROUP_LABELS[group_by]),
			"fieldtype": "Data",
		},
		{"fieldname": "sold_qty", "label": _("Sold Qty"), "fieldtype": "Float"},
		{
			"fieldname": "returned_qty",
			"label": _("Returned Qty"),
			"fieldtype": "Float",
		},
		{"fieldname": "net_qty", "label": _("Net Qty"), "fieldtype": "Float"},
		{
			"fieldname": "sales_value",
			"label": _("Sales Value"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "returns_value",
			"label": _("Returns Value"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{
			"fieldname": "net_sales",
			"label": _("Net Sales"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int"},
		{
			"fieldname": "average_selling_price",
			"label": _("Avg Selling Price"),
			"fieldtype": "Currency",
			"options": currency,
		},
	]
	if include_cost:
		columns.extend(
			[
				{
					"fieldname": "recorded_cost",
					"label": _("Recorded Item Cost"),
					"fieldtype": "Currency",
					"options": currency,
				},
				{
					"fieldname": "gross_profit",
					"label": _("Transactional Gross Profit"),
					"fieldtype": "Currency",
					"options": currency,
				},
				{
					"fieldname": "gross_margin_percent",
					"label": _("Gross Margin"),
					"fieldtype": "Percent",
				},
				{
					"fieldname": "missing_recorded_cost",
					"label": _("Missing Recorded Cost"),
					"fieldtype": "Check",
				},
			]
		)
	return columns
