from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, get_first_day, today

from retailedge.cost_visibility import should_hide_cost_price
from retailedge.sales_reporting import (
	_assert_report_access,
	_coerce_filters,
	_get_permitted_invoice_headers,
	_validate_filters,
)

MAX_LEAKAGE_EVIDENCE_ROWS = 100


@frappe.whitelist()
def get_margin_leakage_evidence(
	item_code: str,
	filters: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	"""Return bounded submitted-invoice evidence for one profitability leakage item."""
	item_code = str(item_code or "").strip()
	if not item_code:
		frappe.throw(_("Item is required."))
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()
	filters.from_date = str(filters.get("from_date") or get_first_day(today()))
	filters.to_date = str(filters.get("to_date") or today())
	_validate_filters(filters)
	_assert_report_access(filters)
	if should_hide_cost_price():
		raise frappe.PermissionError(_("Your current RetailEdge cost-visibility policy does not allow margin evidence."))

	headers = _get_permitted_invoice_headers(filters)
	invoice_names = [row.name for row in headers]
	if not invoice_names:
		return _empty_response(item_code, filters)

	rows = frappe.get_all(
		"Sales Invoice Item",
		filters={
			"parent": ["in", invoice_names],
			"parenttype": "Sales Invoice",
			"item_code": item_code,
		},
		fields=[
			"parent",
			"item_code",
			"item_name",
			"stock_qty",
			"base_net_amount",
			"incoming_rate",
			"discount_percentage",
			"base_price_list_rate",
		],
		order_by="parent desc, idx asc",
		limit=MAX_LEAKAGE_EVIDENCE_ROWS + 1,
	)
	truncated = len(rows) > MAX_LEAKAGE_EVIDENCE_ROWS
	rows = rows[:MAX_LEAKAGE_EVIDENCE_ROWS]
	header_map = _header_metadata([row.parent for row in rows])

	evidence = []
	for row in rows:
		header = header_map.get(row.parent) or frappe._dict()
		stock_qty = flt(row.stock_qty)
		net_sales = flt(row.base_net_amount)
		cost = flt(row.incoming_rate) * stock_qty
		profit = net_sales - cost
		margin = (profit / net_sales * 100.0) if net_sales else 0.0
		evidence.append(
			{
				"invoice": row.parent,
				"posting_date": header.get("posting_date"),
				"customer": header.get("customer_name") or header.get("customer") or "",
				"branch": header.get("branch") or "",
				"qty": stock_qty,
				"net_sales": net_sales,
				"cost_of_sales": cost,
				"gross_profit": profit,
				"gross_margin_percent": margin,
				"discount_percentage": flt(row.discount_percentage),
				"price_list_rate": flt(row.base_price_list_rate),
				"route": f"/app/sales-invoice/{row.parent}",
			}
		)

	return {
		"item_code": item_code,
		"item_name": rows[0].item_name if rows else item_code,
		"rows": evidence,
		"row_count": len(evidence),
		"truncated": cint(truncated),
		"limit": MAX_LEAKAGE_EVIDENCE_ROWS,
		"scope": {
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"from_date": filters.from_date,
			"to_date": filters.to_date,
		},
	}


def _header_metadata(invoice_names: list[str]) -> dict[str, frappe._dict]:
	invoice_names = sorted({str(name) for name in invoice_names if name})
	if not invoice_names:
		return {}
	rows = frappe.get_list(
		"Sales Invoice",
		filters={"name": ["in", invoice_names], "docstatus": 1},
		fields=["name", "posting_date", "customer", "customer_name", "branch"],
		limit=max(len(invoice_names), 1),
	)
	return {row.name: row for row in rows}


def _empty_response(item_code: str, filters: frappe._dict) -> dict[str, Any]:
	return {
		"item_code": item_code,
		"item_name": item_code,
		"rows": [],
		"row_count": 0,
		"truncated": 0,
		"limit": MAX_LEAKAGE_EVIDENCE_ROWS,
		"scope": {
			"company": filters.company,
			"branch": str(filters.get("branch") or ""),
			"from_date": filters.from_date,
			"to_date": filters.to_date,
		},
	}
