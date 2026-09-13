from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from retailedge.profitability_intelligence import (
	_add_to_bucket,
	_dimension_rows,
	_get_costed_items,
	_get_invoice_dimension_metadata,
	_get_sales_allocations,
	_new_bucket,
	_normalise_filters,
	get_profitability_intelligence,
)
from retailedge.sales_reporting import _get_permitted_invoice_headers


def build_profitability_export_dataset(
	filters: dict[str, Any] | str | None = None,
	*,
	all_filtered: bool = True,
) -> dict[str, Any]:
	result = get_profitability_intelligence(filters)
	if all_filtered:
		result["dimensions"] = _build_full_dimensions(filters)
	rows: list[dict[str, Any]] = []

	for row in result.get("rows") or []:
		rows.append(
			{
				"section": _("Item Profitability"),
				"dimension": row.get("item_code") or "",
				"net_sales": row.get("net_sales"),
				"cost_of_sales": row.get("cost_of_sales"),
				"gross_profit": row.get("gross_profit"),
				"gross_margin_percent": row.get("gross_margin_percent"),
				"invoice_count": row.get("invoice_count"),
			}
		)

	labels = {
		"branch": _("Branch"),
		"item_group": _("Item Group"),
		"customer": _("Customer"),
		"salesperson": _("Salesperson"),
	}
	for key, label in labels.items():
		for row in (result.get("dimensions") or {}).get(key) or []:
			rows.append(
				{
					"section": label,
					"dimension": row.get("key") or "",
					"net_sales": row.get("net_sales"),
					"cost_of_sales": row.get("cost_of_sales"),
					"gross_profit": row.get("gross_profit"),
					"gross_margin_percent": row.get("gross_margin_percent"),
					"invoice_count": row.get("invoice_count"),
				}
			)

	return {
		"title": _("Profitability Intelligence"),
		"columns": [
			{"fieldname": "section", "label": _("Section"), "fieldtype": "Data", "width": 150},
			{"fieldname": "dimension", "label": _("Item / Dimension"), "fieldtype": "Data", "width": 220},
			{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "cost_of_sales", "label": _("Cost of Sales"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "gross_profit", "label": _("Gross Profit"), "fieldtype": "Currency", "width": 140},
			{"fieldname": "gross_margin_percent", "label": _("Gross Margin %"), "fieldtype": "Percent", "width": 120},
			{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int", "width": 90},
		],
		"rows": rows,
		"summary": result.get("summary") or [],
		"filters": result.get("scope") or {},
	}


def _build_full_dimensions(filters: dict[str, Any] | str | None) -> dict[str, list[dict[str, Any]]]:
	"""Rebuild export dimensions without the 25-row UI presentation cap.

	The underlying invoice/item scan remains bounded by the profitability engine's
	existing safety ceilings and starts from the permission-filtered invoice set.
	"""
	filters = _normalise_filters(filters)
	headers = _get_permitted_invoice_headers(filters)
	invoice_names = [row.name for row in headers]
	header_map = _get_invoice_dimension_metadata(invoice_names)
	sales_allocations = _get_sales_allocations(invoice_names)
	items = _get_costed_items(invoice_names)

	branch_buckets: dict[str, dict[str, Any]] = {}
	group_buckets: dict[str, dict[str, Any]] = {}
	customer_buckets: dict[str, dict[str, Any]] = {}
	salesperson_buckets: dict[str, dict[str, Any]] = {}
	for row in items:
		invoice = str(row.get("parent") or "")
		header = header_map.get(invoice) or frappe._dict()
		for buckets, key in (
			(branch_buckets, str(header.get("branch") or _("Unassigned Branch"))),
			(group_buckets, str(row.get("item_group") or _("Unspecified Item Group"))),
			(customer_buckets, str(header.get("customer_name") or header.get("customer") or _("Unspecified Customer"))),
		):
			_add_to_bucket(buckets.setdefault(key, _new_bucket(key)), row, invoice)
		for salesperson, weight in sales_allocations.get(invoice) or [(_("Unassigned Salesperson"), 1.0)]:
			_add_to_bucket(
				salesperson_buckets.setdefault(salesperson, _new_bucket(salesperson)),
				row,
				invoice,
				weight=weight,
			)

	return {
		"branch": _dimension_rows(branch_buckets, limit=None),
		"item_group": _dimension_rows(group_buckets, limit=None),
		"customer": _dimension_rows(customer_buckets, limit=None),
		"salesperson": _dimension_rows(salesperson_buckets, limit=None),
	}
