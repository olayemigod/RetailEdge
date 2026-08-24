from __future__ import annotations

from collections import defaultdict
from itertools import combinations
from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt

from retailedge.customer_sales_intelligence import _normalise_filters
from retailedge.sales_reporting import (
	DEFAULT_PAGE_SIZE,
	MAX_INVOICE_SCAN_ROWS,
	MAX_ITEM_SCAN_ROWS,
	MAX_PAGE_SIZE,
	_assert_report_access,
	_filter_headers_by_salesperson,
	_get_invoice_items,
	_get_permitted_invoice_headers,
	_validate_filters,
)

MAX_ITEMS_PER_BASKET = 50
MAX_UNIQUE_PAIRS = 5000


@frappe.whitelist()
def get_basket_affinity(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
) -> dict[str, Any]:
	dataset = _build_basket_affinity_dataset(filters)
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_basket_affinity_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	dataset = _build_basket_affinity_dataset(filters)
	return {
		"title": _("Basket & Product Affinity"),
		"columns": dataset["columns"],
		"rows": dataset["rows"],
		"summary": dataset["summary"],
		"metadata": dataset["metadata"],
		"scan": dataset["scan"],
	}


def _build_basket_affinity_dataset(filters: dict[str, Any] | str | None) -> dict[str, Any]:
	filters = _normalise_filters(filters)
	filters.invoice_kind = "Sales"
	_validate_filters(filters)
	_assert_report_access(filters)

	headers = _get_permitted_invoice_headers(filters)
	headers = _filter_headers_by_salesperson(headers, filters.get("salesperson"))
	invoice_names = [str(row.name) for row in headers]

	# Item / Item Group are affinity anchors, not source-row filters. Fetch the full
	# permitted baskets so companion products are not removed before pair creation.
	basket_filters = frappe._dict(dict(filters))
	basket_filters.item_code = ""
	basket_filters.item_group = ""
	items = _get_invoice_items(invoice_names, basket_filters)

	rows, stats = build_basket_affinity_rows(
		items,
		anchor_item=str(filters.get("item_code") or "").strip(),
		anchor_item_group=str(filters.get("item_group") or "").strip(),
	)
	minimum_pair_count = max(cint(filters.get("minimum_pair_count") or 1), 1)
	rows = [row for row in rows if cint(row.get("pair_invoice_count")) >= minimum_pair_count]

	return {
		"title": _("Basket & Product Affinity"),
		"columns": _columns(),
		"rows": rows,
		"summary": [
			{"label": _("Sale Invoices Scanned"), "value": len(headers), "datatype": "Int"},
			{"label": _("Multi-item Baskets"), "value": stats["eligible_baskets"], "datatype": "Int"},
			{"label": _("Unique Products"), "value": stats["unique_items"], "datatype": "Int"},
			{"label": _("Product Pairs"), "value": len(rows), "datatype": "Int"},
		],
		"scan": {
			"invoices": len(headers),
			"item_rows": len(items),
			"generated_unique_pairs": stats["generated_unique_pairs"],
			"invoice_limit": MAX_INVOICE_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCAN_ROWS,
			"items_per_basket_limit": MAX_ITEMS_PER_BASKET,
			"unique_pair_limit": MAX_UNIQUE_PAIRS,
		},
		"metadata": {
			"sales_truth": "Submitted non-return ERPNext Sales Invoice / Sales Invoice Item",
			"pair_definition": "Two distinct products appearing on the same submitted sale invoice; duplicate lines count once per basket",
			"basket_share_definition": "Pair invoice count divided by multi-item basket count",
			"confidence_definition": "Pair invoice count divided by invoices containing the source product",
			"returns": "Return invoices never create co-purchase pairs",
			"anchor_filters": "Item and Item Group filter displayed pairs after full permitted basket construction",
			"recommendation_claimed": False,
		},
	}


def build_basket_affinity_rows(
	items: list[frappe._dict] | list[dict[str, Any]],
	*,
	anchor_item: str = "",
	anchor_item_group: str = "",
) -> tuple[list[dict[str, Any]], dict[str, int]]:
	"""Build bounded, invoice-level product affinity from submitted sale item rows."""
	basket_items: dict[str, dict[str, str]] = defaultdict(dict)
	for row in items:
		invoice = str(row.get("parent") or "").strip()
		item_code = str(row.get("item_code") or "").strip()
		if not invoice or not item_code or flt(row.get("qty")) <= 0:
			continue
		basket_items[invoice][item_code] = str(row.get("item_group") or "").strip()

	item_invoice_count: dict[str, int] = defaultdict(int)
	item_groups: dict[str, str] = {}
	pair_invoice_count: dict[tuple[str, str], int] = defaultdict(int)
	eligible_baskets = 0

	for invoice, products in basket_items.items():
		item_codes = sorted(products)
		if len(item_codes) > MAX_ITEMS_PER_BASKET:
			frappe.throw(
				_("Sales Invoice {0} contains more than {1} distinct products for basket analysis. Narrow the scope or review the invoice before continuing.").format(
					invoice, MAX_ITEMS_PER_BASKET
				)
			)
		for item_code in item_codes:
			item_invoice_count[item_code] += 1
			item_groups[item_code] = products.get(item_code) or item_groups.get(item_code, "")
		if len(item_codes) < 2:
			continue
		eligible_baskets += 1
		for pair in combinations(item_codes, 2):
			if pair not in pair_invoice_count and len(pair_invoice_count) >= MAX_UNIQUE_PAIRS:
				frappe.throw(
					_("Basket analysis produced more than {0} unique product pairs. Narrow the date range, Branch, Customer, or Salesperson before continuing.").format(
						MAX_UNIQUE_PAIRS
					)
				)
			pair_invoice_count[pair] += 1

	anchor_item = str(anchor_item or "").strip()
	anchor_item_group = str(anchor_item_group or "").strip()
	rows: list[dict[str, Any]] = []
	for (item_a, item_b), pair_count in pair_invoice_count.items():
		group_a = item_groups.get(item_a, "")
		group_b = item_groups.get(item_b, "")
		if anchor_item and anchor_item not in {item_a, item_b}:
			continue
		if anchor_item_group and anchor_item_group not in {group_a, group_b}:
			continue
		a_count = item_invoice_count[item_a]
		b_count = item_invoice_count[item_b]
		rows.append(
			{
				"item_a": item_a,
				"item_a_group": group_a,
				"item_b": item_b,
				"item_b_group": group_b,
				"pair_invoice_count": pair_count,
				"basket_share_percent": (pair_count / eligible_baskets * 100.0) if eligible_baskets else 0.0,
				"item_a_invoice_count": a_count,
				"item_b_invoice_count": b_count,
				"confidence_a_to_b_percent": (pair_count / a_count * 100.0) if a_count else 0.0,
				"confidence_b_to_a_percent": (pair_count / b_count * 100.0) if b_count else 0.0,
			}
		)

	rows.sort(
		key=lambda row: (
			-cint(row["pair_invoice_count"]),
			-flt(row["basket_share_percent"]),
			str(row["item_a"]),
			str(row["item_b"]),
		)
	)
	return rows, {
		"eligible_baskets": eligible_baskets,
		"unique_items": len(item_invoice_count),
		"generated_unique_pairs": len(pair_invoice_count),
	}


def _columns() -> list[dict[str, Any]]:
	return [
		{"label": _("Product A"), "fieldname": "item_a", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("A Group"), "fieldname": "item_a_group", "fieldtype": "Data", "width": 130},
		{"label": _("Product B"), "fieldname": "item_b", "fieldtype": "Link", "options": "Item", "width": 180},
		{"label": _("B Group"), "fieldname": "item_b_group", "fieldtype": "Data", "width": 130},
		{"label": _("Together"), "fieldname": "pair_invoice_count", "fieldtype": "Int", "width": 95},
		{"label": _("Basket Share %"), "fieldname": "basket_share_percent", "fieldtype": "Percent", "width": 120},
		{"label": _("A Invoices"), "fieldname": "item_a_invoice_count", "fieldtype": "Int", "width": 95},
		{"label": _("B Invoices"), "fieldname": "item_b_invoice_count", "fieldtype": "Int", "width": 95},
		{"label": _("A → B %"), "fieldname": "confidence_a_to_b_percent", "fieldtype": "Percent", "width": 105},
		{"label": _("B → A %"), "fieldname": "confidence_b_to_a_percent", "fieldtype": "Percent", "width": 105},
	]


def _page_response(dataset: dict[str, Any], *, page: int | str, page_size: int | str) -> dict[str, Any]:
	page = max(cint(page), 1)
	page_size = min(max(cint(page_size) or DEFAULT_PAGE_SIZE, 1), MAX_PAGE_SIZE)
	start = (page - 1) * page_size
	end = start + page_size
	total = len(dataset["rows"])
	return {
		**dataset,
		"rows": dataset["rows"][start:end],
		"pagination": {
			"page": page,
			"page_size": page_size,
			"total_rows": total,
			"has_previous": page > 1,
			"has_next": end < total,
		},
	}
