from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import cint, flt, getdate

from retailedge.purchase_reporting import (
	MAX_INVOICE_SCAN_ROWS,
	MAX_ITEM_SCAN_ROWS,
	_assert_report_access,
	_coerce_filters,
	_company_currency,
	_export_response,
	_get_invoice_items,
	_get_permitted_invoice_headers,
	_page_response,
	_signed_for_return,
	_validate_purchase_filters,
)

DEFAULT_GROUP_BY = "Month"
PERIOD_GROUPS = frozenset({"Day", "Week", "Month", "Quarter", "Year"})
SUPPORTED_GROUP_BY = (
	"Day",
	"Week",
	"Month",
	"Quarter",
	"Year",
	"Item",
	"Item Group",
	"Supplier",
	"Supplier Group",
	"Branch",
	"Warehouse",
)

GROUP_LABELS = {value: value for value in SUPPORTED_GROUP_BY}


@frappe.whitelist()
def get_purchase_analysis(
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = 50,
	sort: dict[str, Any] | str | None = None,
) -> dict[str, Any]:
	from retailedge.report_sorting import apply_materialized_report_sort

	filters = _coerce_filters(filters)
	dataset = _build_purchase_analysis_dataset(filters)
	apply_materialized_report_sort(dataset, sort, "purchase-analysis")
	return _page_response(dataset, page=page, page_size=page_size)


@frappe.whitelist()
def get_purchase_analysis_export(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	filters = _coerce_filters(filters)
	dataset = _build_purchase_analysis_dataset(filters)
	return {
		**_export_response(dataset),
		"group_by": dataset.get("group_by") or DEFAULT_GROUP_BY,
		"metadata": dataset.get("metadata") or {},
	}


def _build_purchase_analysis_dataset(filters: frappe._dict) -> dict[str, Any]:
	_validate_purchase_filters(filters)
	_assert_report_access(filters)
	group_by = _normalise_group_by(filters.get("group_by"))

	headers = _get_permitted_invoice_headers(filters, as_of=False)
	header_map = {str(row.name): row for row in headers}
	items = _get_invoice_items(list(header_map), filters)

	buckets: dict[str, dict[str, Any]] = {}
	for item in items:
		header = header_map.get(str(item.parent))
		if not header:
			continue
		group_key, group_label = _group_entry(group_by, header, item)
		bucket = buckets.setdefault(group_key, _new_bucket(group_key, group_label))
		_add_line_to_bucket(bucket, header, item)

	rows = [_finalise_bucket(bucket) for bucket in buckets.values()]
	if group_by in PERIOD_GROUPS:
		rows.sort(key=lambda row: str(row.get("group_key") or ""))
	else:
		rows.sort(key=lambda row: (-flt(row.get("net_purchased")), str(row.get("group_label") or "")))

	matched_invoice_count = len(
		{
			str(item.get("parent") or "")
			for item in items
			if str(item.get("parent") or "") in header_map
		}
	)
	currency = _company_currency(filters.company)
	return {
		"title": _("Purchase Analysis"),
		"columns": _purchase_analysis_columns(currency, group_by),
		"rows": rows,
		"summary": _summary(rows, invoice_count=matched_invoice_count),
		"company_currency": currency,
		"group_by": group_by,
		"scan": {
			"invoices": len(headers),
			"item_rows": len(items),
			"invoice_limit": MAX_INVOICE_SCAN_ROWS,
			"item_limit": MAX_ITEM_SCAN_ROWS,
		},
		"metadata": {
			"source": "Submitted ERPNext Purchase Invoice / Purchase Invoice Item",
			"purchase_truth": "Submitted Purchase Invoice item base net amounts with returns reversed",
			"branch_truth": "RetailEdge authoritative Purchase Invoice branch attribution",
			"outstanding_policy": (
				"Outstanding remains in Supplier Payables because invoice balances cannot be safely allocated "
				"to partial Item, Item Group, or Warehouse selections."
			),
			"tax_policy": (
				"Taxes and grand total remain invoice-level in Purchase Register; this grouped analysis uses "
				"additive item base net amounts only."
			),
			"supplier_scoring": "No supplier score is invented by this report.",
			"quantity_note": "Quantity is additive operational volume and may mix units of measure outside item-level analysis.",
		},
	}


def _normalise_group_by(value: Any) -> str:
	raw = str(value or DEFAULT_GROUP_BY).strip()
	lookup = {item.casefold(): item for item in SUPPORTED_GROUP_BY}
	resolved = lookup.get(raw.casefold())
	if not resolved:
		frappe.throw(_("Group By must be one of: {0}.").format(", ".join(SUPPORTED_GROUP_BY)))
	return resolved


def _group_entry(
	group_by: str,
	header: frappe._dict,
	item: frappe._dict,
) -> tuple[str, str]:
	if group_by in PERIOD_GROUPS:
		return _period_group(header.get("posting_date"), group_by)
	if group_by == "Item":
		key = str(item.get("item_code") or "").strip() or _("Unspecified Item")
		return key, str(item.get("item_name") or key)
	if group_by == "Item Group":
		key = str(item.get("item_group") or "").strip() or _("Unspecified Item Group")
		return key, key
	if group_by == "Supplier":
		key = str(header.get("supplier") or "").strip() or _("Unspecified Supplier")
		return key, str(header.get("supplier_name") or key)
	if group_by == "Supplier Group":
		key = str(header.get("supplier_group") or "").strip() or _("Unspecified Supplier Group")
		return key, key
	if group_by == "Branch":
		key = str(header.get("branch") or "").strip() or _("Unattributed Branch")
		return key, key
	if group_by == "Warehouse":
		key = str(item.get("warehouse") or "").strip() or _("Unspecified Warehouse")
		return key, key
	frappe.throw(_("Unsupported Purchase Analysis dimension."))


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
	frappe.throw(_("Unsupported Purchase Analysis period."))


def _new_bucket(group_key: str, group_label: str) -> dict[str, Any]:
	return {
		"group_key": group_key,
		"group_label": group_label,
		"purchased_qty": 0.0,
		"returned_qty": 0.0,
		"net_qty": 0.0,
		"purchase_value": 0.0,
		"returns_value": 0.0,
		"net_purchased": 0.0,
		"_invoices": set(),
	}


def _add_line_to_bucket(bucket: dict[str, Any], header: frappe._dict, item: frappe._dict) -> None:
	is_return = cint(header.get("is_return"))
	qty = flt(item.get("qty"))
	net_amount = flt(item.get("base_net_amount"))
	signed_qty = -abs(qty) if is_return else qty
	signed_net = _signed_for_return(net_amount, is_return)

	bucket["purchased_qty"] += 0.0 if is_return else max(qty, 0.0)
	bucket["returned_qty"] += abs(qty) if is_return else 0.0
	bucket["net_qty"] += signed_qty
	bucket["purchase_value"] += 0.0 if is_return else net_amount
	bucket["returns_value"] += abs(net_amount) if is_return else 0.0
	bucket["net_purchased"] += signed_net

	invoice = str(header.get("name") or item.get("parent") or "")
	if invoice:
		bucket["_invoices"].add(invoice)


def _finalise_bucket(bucket: dict[str, Any]) -> dict[str, Any]:
	row = dict(bucket)
	row["invoice_count"] = len(row.pop("_invoices", set()))
	row["average_transaction_value"] = (
		flt(row["net_purchased"]) / row["invoice_count"] if row["invoice_count"] else 0.0
	)
	row["average_unit_cost"] = (
		flt(row["net_purchased"]) / flt(row["net_qty"]) if flt(row["net_qty"]) else 0.0
	)
	return row


def _summary(rows: list[dict[str, Any]], *, invoice_count: int) -> list[dict[str, Any]]:
	net_purchased = sum(flt(row.get("net_purchased")) for row in rows)
	return [
		{"label": _("Net Purchased"), "value": net_purchased, "datatype": "Currency"},
		{
			"label": _("Purchase Value"),
			"value": sum(flt(row.get("purchase_value")) for row in rows),
			"datatype": "Currency",
		},
		{
			"label": _("Returns"),
			"value": sum(flt(row.get("returns_value")) for row in rows),
			"datatype": "Currency",
		},
		{"label": _("Invoices"), "value": invoice_count, "datatype": "Int"},
		{
			"label": _("Average Transaction Value"),
			"value": net_purchased / invoice_count if invoice_count else 0.0,
			"datatype": "Currency",
		},
	]


def _purchase_analysis_columns(currency: str, group_by: str) -> list[dict[str, Any]]:
	columns = [
		{"fieldname": "group_label", "label": _(GROUP_LABELS[group_by]), "fieldtype": "Data"},
		{"fieldname": "purchased_qty", "label": _("Purchased Qty"), "fieldtype": "Float"},
		{"fieldname": "returned_qty", "label": _("Returned Qty"), "fieldtype": "Float"},
		{"fieldname": "net_qty", "label": _("Net Qty"), "fieldtype": "Float"},
		{
			"fieldname": "purchase_value",
			"label": _("Purchase Value"),
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
			"fieldname": "net_purchased",
			"label": _("Net Purchased"),
			"fieldtype": "Currency",
			"options": currency,
		},
		{"fieldname": "invoice_count", "label": _("Invoices"), "fieldtype": "Int"},
		{
			"fieldname": "average_transaction_value",
			"label": _("Avg Transaction Value"),
			"fieldtype": "Currency",
			"options": currency,
		},
	]
	if group_by == "Item":
		columns.append(
			{
				"fieldname": "average_unit_cost",
				"label": _("Avg Unit Cost"),
				"fieldtype": "Currency",
				"options": currency,
			}
		)
	return columns
