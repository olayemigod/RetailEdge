from __future__ import annotations

from unittest.mock import patch

import frappe

from retailedge import action_center


def _empty_summary() -> dict:
	return {"summary": []}


def test_stock_manager_gets_stock_exceptions_from_inventory_health_source():
	frappe.session.user = "stock.manager@example.com"
	stock_payload = {
		"summary": [
			{"label": "Negative Stock", "value": 2, "datatype": "Int"},
			{"label": "Out of Stock", "value": 5, "datatype": "Int"},
			{"label": "Fully Reserved", "value": 3, "datatype": "Int"},
			{"label": "Stock Value", "value": 250000, "datatype": "Currency"},
		]
	}
	with (
		patch("retailedge.action_center.get_inventory_health", return_value=stock_payload) as stock,
		patch("retailedge.action_center.get_expense_register", return_value=_empty_summary()),
		patch("retailedge.action_center.get_cash_shift_verification", return_value=_empty_summary()),
		patch("retailedge.action_center.get_customer_receivables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_supplier_payables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_bank_exception_summary", return_value=_empty_summary()),
		patch("retailedge.action_center.decorate_action_items", side_effect=lambda items, **kwargs: items),
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "branch": "HQ", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)

	stock.assert_called_once_with(
		filters={"company": "Test Company", "branch": "HQ", "include_zero": 1},
		page=1,
		page_size=action_center.DEFAULT_PAGE_SIZE,
	)
	stock_items = [row for row in result["items"] if row["source"] == "stock"]
	assert {row["kind"] for row in stock_items} == {
		"negative_stock",
		"out_of_stock",
		"fully_reserved_stock",
	}
	assert stock_items[0]["severity"] == "danger"
	assert all(row["route"] == "/app/stock-position" for row in stock_items)
	assert all(row["target_type"] == "Page" for row in stock_items)
	assert all(row["target"] == "stock-position" for row in stock_items)
	assert all(row["open_mode"] == "same_tab" for row in stock_items)
	assert all(row["time_basis"] == "current" for row in stock_items)
	assert all(row["datatype"] == "Int" for row in stock_items)
	assert not any(row.get("value") == 250000 for row in stock_items)
	assert result["sources"]["stock_position"]["available"] is True
	assert result["metadata"]["stock_provider"].startswith("Inventory Health")
	assert result["metadata"]["read_only"] is True


def test_inventory_health_adds_r10_actions_without_changing_legacy_fingerprints():
	items = []
	action_center._append_stock_exceptions(
		items,
		{
			"summary": [
				{"label": "Out of Stock", "value": 2, "datatype": "Int"},
				{"label": "Items Requiring Reorder", "value": 4, "datatype": "Int"},
				{"label": "Reorder Rules Requiring Review", "value": 1, "datatype": "Int"},
				{"label": "Non-moving", "value": 7, "datatype": "Int"},
			]
		},
	)

	by_kind = {row["kind"]: row for row in items}
	assert by_kind["out_of_stock"]["semantic_key"] == "out_of_stock"
	assert by_kind["out_of_stock"]["route"] == "/app/stock-position"
	assert by_kind["inventory_reorder_required"]["route"] == "/app/inventory-intelligence"
	assert by_kind["inventory_reorder_rule_review"]["target"] == "inventory-intelligence"
	assert by_kind["inventory_non_moving"]["value"] == 7
	assert len(items) == 4


def test_stock_source_is_loaded_once_and_not_through_owner_dashboard_attention():
	frappe.session.user = "manager@example.com"
	stock_payload = {
		"summary": [
			{"label": "Negative Stock", "value": 0, "datatype": "Int"},
			{"label": "Out of Stock", "value": 4, "datatype": "Int"},
			{"label": "Fully Reserved", "value": 0, "datatype": "Int"},
		]
	}
	with (
		patch("retailedge.action_center.get_inventory_health", return_value=stock_payload) as stock,
		patch("retailedge.action_center.get_expense_register", return_value=_empty_summary()),
		patch("retailedge.action_center.get_cash_shift_verification", return_value=_empty_summary()),
		patch("retailedge.action_center.get_customer_receivables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_supplier_payables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_bank_exception_summary", return_value=_empty_summary()),
		patch("retailedge.action_center.decorate_action_items", side_effect=lambda items, **kwargs: items),
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)

	stock.assert_called_once()
	assert len([row for row in result["items"] if row["source"] == "stock"]) == 1
	assert "owner" not in result["sources"]