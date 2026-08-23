from __future__ import annotations

from typing import Any

import frappe
from frappe import _
from frappe.utils import flt

from retailedge.inventory_health import _build_inventory_health_dataset
from retailedge.profitability_intelligence import get_profitability_intelligence
from retailedge.stock_position import _coerce_filters


@frappe.whitelist()
def get_inventory_profitability_signals(filters: dict[str, Any] | str | None = None) -> dict[str, Any]:
	"""Intersect R8 profitability evidence with R10 inventory health.

	This service deliberately owns no profitability formula or margin threshold.
	R8 remains the profitability contract. R10 only combines R8's published item
	classifications with current stock, movement, and replenishment intelligence.
	"""
	filters = _coerce_filters(filters)
	if not filters.get("company"):
		filters.company = str(frappe.defaults.get_user_default("Company") or "").strip()

	inventory = _build_inventory_health_dataset(filters)
	inventory_rows = list(inventory.get("rows") or [])
	profit_filters = {
		"company": filters.company,
		"branch": filters.get("branch") or "",
	}
	for fieldname in ("from_date", "to_date"):
		if filters.get(fieldname):
			profit_filters[fieldname] = str(filters.get(fieldname))
	try:
		profitability = get_profitability_intelligence(profit_filters)
	except frappe.PermissionError:
		return _unavailable_payload(
			inventory,
			profit_filters=profit_filters,
			reason="RetailEdge cost visibility does not allow profitability intelligence for this user.",
		)

	inventory_by_item = {
		str(row.get("item_code")): row
		for row in inventory_rows
		if row.get("item_code")
	}
	top_contributors = {
		str(row.get("item_code")): row
		for row in profitability.get("top_contributors") or []
		if row.get("item_code") and flt(row.get("gross_profit")) > 0
	}
	margin_leakage = {
		str(row.get("item_code")): row
		for row in profitability.get("margin_leakage") or []
		if row.get("item_code")
	}

	rows: list[dict[str, Any]] = []
	for item_code, inventory_row in inventory_by_item.items():
		profit_row = top_contributors.get(item_code)
		if profit_row and inventory_row.get("replenishment_status") == "Reorder Now":
			rows.append(
				_signal(
					kind="top_profit_contributor_reorder",
					severity=(
						"danger"
						if inventory_row.get("stock_status") in {"Out of Stock", "Fully Reserved", "Negative"}
						else "warning"
					),
					label=_("Top profit contributor requires replenishment"),
					item_code=item_code,
					inventory=inventory_row,
					profitability=profit_row,
				)
			)

		leakage_row = margin_leakage.get(item_code)
		if (
			leakage_row
			and inventory_row.get("movement_class") in {"Slow", "Non-moving"}
			and flt(inventory_row.get("actual_qty")) > 0
		):
			rows.append(
				_signal(
					kind="low_margin_slow_stock",
					severity="warning",
					label=_("Low-margin stock is moving slowly"),
					item_code=item_code,
					inventory=inventory_row,
					profitability=leakage_row,
				)
			)

	rows.sort(
		key=lambda row: (
			0 if row["severity"] == "danger" else 1,
			-abs(flt(row.get("gross_profit"))),
			row["item_code"],
			row["kind"],
		)
	)
	profit_scope = dict(profitability.get("scope") or {})
	return {
		"available": True,
		"rows": rows,
		"summary": _summary(rows),
		"scope": {
			"company": filters.company,
			"branch": filters.get("branch") or "",
			"from_date": profit_scope.get("from_date") or profit_filters.get("from_date"),
			"to_date": profit_scope.get("to_date") or profit_filters.get("to_date"),
			"inventory_item_count": len(inventory_rows),
			"inventory_evidence_from_date": inventory.get("scope", {}).get("from_date"),
			"inventory_evidence_to_date": inventory.get("scope", {}).get("to_date"),
		},
		"metadata": {
			"profitability_contract": "R8 get_profitability_intelligence",
			"profitability_truth": profitability.get("metadata", {}).get("financial_truth"),
			"profitability_period_contract": "Visible From Date / To Date are passed to R8 independently of the R10 inventory movement evidence window.",
			"top_contributor_contract": "R8 top_contributors; R10 does not recalculate contribution ranking",
			"low_margin_contract": "R8 margin_leakage; R10 does not own the low-margin threshold",
			"inventory_contract": "R10 Inventory Health / ERPNext Bin + bounded demand + ERPNext reorder rules",
			"read_only": True,
			"persistent_derived_truth": False,
		},
	}


def _signal(
	*,
	kind: str,
	severity: str,
	label: str,
	item_code: str,
	inventory: dict[str, Any],
	profitability: dict[str, Any],
) -> dict[str, Any]:
	return {
		"kind": kind,
		"severity": severity,
		"label": label,
		"item_code": item_code,
		"item_name": inventory.get("item_name") or profitability.get("item_name") or item_code,
		"item_group": inventory.get("item_group") or profitability.get("item_group") or "",
		"stock_status": inventory.get("stock_status"),
		"movement_class": inventory.get("movement_class"),
		"available_qty": inventory.get("available_qty"),
		"stock_cover_days": inventory.get("stock_cover_days"),
		"replenishment_status": inventory.get("replenishment_status"),
		"recommended_reorder_qty": inventory.get("recommended_reorder_qty"),
		"net_sales": profitability.get("net_sales"),
		"gross_profit": profitability.get("gross_profit"),
		"gross_margin_percent": profitability.get("gross_margin_percent"),
		"route": "/app/inventory-intelligence",
		"target_type": "Page",
		"target": "inventory-intelligence",
		"open_mode": "same_tab",
	}


def _summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
	return [
		{"label": _("Profit + Inventory Signals"), "value": len(rows), "datatype": "Int"},
		{
			"label": _("Top Profit Contributors Requiring Replenishment"),
			"value": sum(1 for row in rows if row.get("kind") == "top_profit_contributor_reorder"),
			"datatype": "Int",
		},
		{
			"label": _("Low-margin Slow Stock"),
			"value": sum(1 for row in rows if row.get("kind") == "low_margin_slow_stock"),
			"datatype": "Int",
		},
	]


def _unavailable_payload(
	inventory: dict[str, Any],
	*,
	profit_filters: dict[str, Any],
	reason: str,
) -> dict[str, Any]:
	return {
		"available": False,
		"rows": [],
		"summary": _summary([]),
		"scope": {
			"company": profit_filters.get("company") or inventory.get("scope", {}).get("company"),
			"branch": profit_filters.get("branch") or inventory.get("scope", {}).get("branch") or "",
			"from_date": profit_filters.get("from_date"),
			"to_date": profit_filters.get("to_date"),
			"inventory_evidence_from_date": inventory.get("scope", {}).get("from_date"),
			"inventory_evidence_to_date": inventory.get("scope", {}).get("to_date"),
		},
		"metadata": {
			"profitability_contract": "R8 get_profitability_intelligence",
			"inventory_contract": "R10 Inventory Health",
			"read_only": True,
			"reason": reason,
			"persistent_derived_truth": False,
		},
	}