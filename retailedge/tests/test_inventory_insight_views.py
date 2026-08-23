from unittest.mock import patch

import frappe

from retailedge import inventory_insight_views


def test_invalid_inventory_insight_view_is_rejected():
	try:
		inventory_insight_views.get_inventory_insight_view("unknown", {"company": "Test Company"})
	except frappe.ValidationError:
		pass
	else:
		raise AssertionError("Unsupported inventory insight view should fail")


@patch("retailedge.inventory_insight_views.get_inventory_ageing")
def test_ageing_view_preserves_service_columns_and_paginates(ageing):
	ageing.return_value = {
		"columns": [{"fieldname": "item_code", "label": "Item", "fieldtype": "Link"}],
		"rows": [{"item_code": "A"}, {"item_code": "B"}],
		"summary": [{"label": "Items with Aged Stock", "value": 1, "datatype": "Int"}],
		"scope": {"company": "Test Company"},
		"scan": {"sle_rows": 20},
		"metadata": {"ageing_truth": "ERPNext v16 Stock Ageing FIFOSlots"},
		"show_costs": 1,
	}
	result = inventory_insight_views.get_inventory_insight_view(
		"ageing", {"company": "Test Company"}, page=1, page_size=25
	)
	assert result["columns"][0]["fieldname"] == "item_code"
	assert result["pagination"]["total_rows"] == 2
	assert result["metadata"]["lazy_loaded"] is True
	assert result["metadata"]["ageing_truth"] == "ERPNext v16 Stock Ageing FIFOSlots"
	assert result["show_costs"] == 1
	ageing.assert_called_once()


@patch("retailedge.inventory_insight_views.get_inventory_transfer_opportunities")
def test_transfer_view_adds_standard_columns_without_changing_rows(transfers):
	transfers.return_value = {
		"rows": [
			{
				"item_code": "ITEM-1",
				"source_warehouse": "A - TC",
				"target_warehouse": "B - TC",
				"suggested_transfer_qty": 5,
			}
		],
		"summary": [{"label": "Transfer Opportunities", "value": 1, "datatype": "Int"}],
		"metadata": {"read_only": True, "creates_stock_entry": False},
	}
	result = inventory_insight_views.get_inventory_insight_view(
		"transfer-opportunities", {"company": "Test Company"}
	)
	assert result["rows"][0]["suggested_transfer_qty"] == 5
	assert {column["fieldname"] for column in result["columns"]} >= {
		"source_warehouse",
		"target_warehouse",
		"suggested_transfer_qty",
	}
	assert result["metadata"]["creates_stock_entry"] is False


@patch("retailedge.inventory_insight_views.get_inventory_transfer_opportunities")
def test_sort_is_applied_before_pagination_and_validated_against_columns(transfers):
	transfers.return_value = {
		"rows": [
			{"item_code": "B", "suggested_transfer_qty": 2},
			{"item_code": "A", "suggested_transfer_qty": 10},
			{"item_code": "C", "suggested_transfer_qty": 5},
		],
		"summary": [],
		"metadata": {},
	}
	result = inventory_insight_views.get_inventory_insight_view(
		"transfer-opportunities",
		{"company": "Test Company"},
		page=1,
		page_size=25,
		sort_field="suggested_transfer_qty",
		sort_direction="desc",
	)
	assert [row["item_code"] for row in result["rows"]] == ["A", "C", "B"]
	assert result["metadata"]["sort"]["field"] == "suggested_transfer_qty"
	assert result["metadata"]["sort"]["direction"] == "desc"

	try:
		inventory_insight_views.get_inventory_insight_view(
			"transfer-opportunities",
			{"company": "Test Company"},
			sort_field="not_a_column",
			sort_direction="asc",
		)
	except frappe.ValidationError:
		pass
	else:
		raise AssertionError("Unsupported insight sort field should fail")


@patch("retailedge.inventory_insight_views.get_inventory_profitability_signals")
def test_profitability_view_keeps_unavailable_reason_and_empty_rows(profitability):
	profitability.return_value = {
		"available": False,
		"rows": [],
		"summary": [],
		"scope": {"company": "Test Company"},
		"metadata": {"reason": "Cost visibility denied", "read_only": True},
	}
	result = inventory_insight_views.get_inventory_insight_view(
		"profitability", {"company": "Test Company"}
	)
	assert result["available"] is False
	assert result["rows"] == []
	assert result["metadata"]["reason"] == "Cost visibility denied"
	assert any(column["fieldname"] == "gross_profit" for column in result["columns"])
