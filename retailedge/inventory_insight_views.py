from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.inventory_ageing import get_inventory_ageing
from retailedge.inventory_profitability_signals import get_inventory_profitability_signals
from retailedge.inventory_transfer_opportunities import get_inventory_transfer_opportunities
from retailedge.stock_position import DEFAULT_PAGE_SIZE, _coerce_filters, _page_response

INSIGHT_VIEWS = {"ageing", "transfer-opportunities", "profitability"}
NUMERIC_FIELDTYPES = {"Currency", "Float", "Int", "Percent", "Check"}


@frappe.whitelist()
def get_inventory_insight_view(
	view: str,
	filters: dict[str, Any] | str | None = None,
	page: int | str = 1,
	page_size: int | str = DEFAULT_PAGE_SIZE,
	sort_field: str = "",
	sort_direction: str = "",
) -> dict[str, Any]:
	"""Return a paginated R10 secondary insight using its existing authoritative service."""
	view = str(view or "").strip().lower()
	if view not in INSIGHT_VIEWS:
		frappe.throw(_("Unsupported Inventory Intelligence view."))
	filters = _coerce_filters(filters)

	if view == "ageing":
		payload = get_inventory_ageing(filters)
		columns = list(payload.get("columns") or [])
	elif view == "transfer-opportunities":
		payload = get_inventory_transfer_opportunities(filters)
		columns = _transfer_columns()
	else:
		payload = get_inventory_profitability_signals(filters)
		columns = _profitability_columns()

	rows = list(payload.get("rows") or [])
	resolved_sort = _resolve_sort(columns, sort_field=sort_field, sort_direction=sort_direction)
	if resolved_sort:
		rows = _sort_rows(rows, resolved_sort)

	dataset = {
		"view": view,
		"columns": columns,
		"rows": rows,
		"summary": list(payload.get("summary") or []),
		"scope": dict(payload.get("scope") or {}),
		"scan": dict(payload.get("scan") or {}),
		"metadata": {
			**dict(payload.get("metadata") or {}),
			"insight_view": view,
			"lazy_loaded": True,
			"sort": resolved_sort,
		},
		"show_costs": payload.get("show_costs"),
		"available": payload.get("available", True),
	}
	return _page_response(dataset, page=page, page_size=page_size)


def _resolve_sort(
	columns: list[dict[str, Any]], *, sort_field: str, sort_direction: str
) -> dict[str, str] | None:
	field = str(sort_field or "").strip()
	direction = str(sort_direction or "").strip().lower()
	if not field and not direction:
		return None
	if not field or direction not in {"asc", "desc"}:
		frappe.throw(_("Invalid Inventory Intelligence sort request."))
	by_field = {
		str(column.get("fieldname") or ""): column
		for column in columns
		if column.get("fieldname")
	}
	column = by_field.get(field)
	if not column:
		frappe.throw(_("Unsupported Inventory Intelligence sort field."))
	return {
		"field": field,
		"direction": direction,
		"fieldtype": str(column.get("fieldtype") or "Data"),
	}


def _sort_rows(rows: list[dict[str, Any]], sort: dict[str, str]) -> list[dict[str, Any]]:
	field = sort["field"]
	fieldtype = sort.get("fieldtype") or "Data"
	reverse = sort.get("direction") == "desc"
	present = [row for row in rows if row.get(field) not in (None, "")]
	missing = [row for row in rows if row.get(field) in (None, "")]

	def key(row: dict[str, Any]):
		value = row.get(field)
		if fieldtype in NUMERIC_FIELDTYPES:
			return flt(value)
		return str(value or "").casefold()

	return [*sorted(present, key=key, reverse=reverse), *missing]


def _transfer_columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item"},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data"},
		{"fieldname": "source_warehouse", "label": _("Source Warehouse"), "fieldtype": "Link", "options": "Warehouse"},
		{"fieldname": "target_warehouse", "label": _("Target Warehouse"), "fieldtype": "Link", "options": "Warehouse"},
		{"fieldname": "suggested_transfer_qty", "label": _("Suggested Transfer Qty"), "fieldtype": "Float"},
		{"fieldname": "source_available_qty", "label": _("Source Available"), "fieldtype": "Float"},
		{"fieldname": "source_reorder_level", "label": _("Source Reorder Level"), "fieldtype": "Float"},
		{"fieldname": "target_projected_qty", "label": _("Target Projected Qty"), "fieldtype": "Float"},
		{"fieldname": "target_reorder_level", "label": _("Target Reorder Level"), "fieldtype": "Float"},
		{"fieldname": "target_reorder_need", "label": _("Target Reorder Need"), "fieldtype": "Float"},
		{"fieldname": "requires_full_stock_entry", "label": _("Full Stock Entry Required"), "fieldtype": "Check"},
	]


def _profitability_columns() -> list[dict[str, Any]]:
	return [
		{"fieldname": "severity", "label": _("Priority"), "fieldtype": "Data"},
		{"fieldname": "label", "label": _("Signal"), "fieldtype": "Data"},
		{"fieldname": "item_code", "label": _("Item"), "fieldtype": "Link", "options": "Item"},
		{"fieldname": "item_name", "label": _("Item Name"), "fieldtype": "Data"},
		{"fieldname": "stock_status", "label": _("Stock Status"), "fieldtype": "Data"},
		{"fieldname": "movement_class", "label": _("Movement Class"), "fieldtype": "Data"},
		{"fieldname": "available_qty", "label": _("Available Qty"), "fieldtype": "Float"},
		{"fieldname": "stock_cover_days", "label": _("Stock Cover (Days)"), "fieldtype": "Float"},
		{"fieldname": "replenishment_status", "label": _("Replenishment"), "fieldtype": "Data"},
		{"fieldname": "recommended_reorder_qty", "label": _("Recommended Reorder Qty"), "fieldtype": "Float"},
		{"fieldname": "net_sales", "label": _("Net Sales"), "fieldtype": "Currency"},
		{"fieldname": "gross_profit", "label": _("Gross Profit"), "fieldtype": "Currency"},
		{"fieldname": "gross_margin_percent", "label": _("Gross Margin"), "fieldtype": "Percent"},
	]
