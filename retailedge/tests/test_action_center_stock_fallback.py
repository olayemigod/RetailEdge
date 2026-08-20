from __future__ import annotations

from unittest.mock import patch

import frappe

from retailedge import action_center


def _empty_summary() -> dict:
	return {"summary": []}


def test_stock_manager_gets_stock_exceptions_when_owner_dashboard_is_not_permitted():
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
		patch("retailedge.action_center.get_owner_dashboard_data", side_effect=frappe.PermissionError),
		patch("retailedge.action_center.get_stock_position", return_value=stock_payload) as stock,
		patch("retailedge.action_center.get_expense_register", return_value=_empty_summary()),
		patch("retailedge.action_center.get_cash_shift_verification", return_value=_empty_summary()),
		patch("retailedge.action_center.get_customer_receivables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_supplier_payables", return_value=_empty_summary()),
		patch("retailedge.action_center.decorate_action_items", side_effect=lambda items, **kwargs: items),
		patch("retailedge.action_center.frappe.get_roles", return_value=["Stock Manager"]),
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "branch": "HQ", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)

	stock.assert_called_once_with(
		filters={"company": "Test Company", "branch": "HQ"},
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
	assert all(row["time_basis"] == "current" for row in stock_items)
	assert all(row["datatype"] == "Int" for row in stock_items)
	assert not any(row.get("value") == 250000 for row in stock_items)
	assert result["sources"]["stock_position"]["available"] is True
	assert result["metadata"]["read_only"] is True


def test_owner_dashboard_stock_source_does_not_trigger_duplicate_stock_scan():
	frappe.session.user = "manager@example.com"
	owner_payload = {
		"attention": [
			{
				"section": "stock",
				"label": "Items are out of stock",
				"value": 4,
				"datatype": "Int",
				"tone": "warning",
				"route": "/app/stock-position",
				"time_basis": "current",
			}
		]
	}
	with (
		patch("retailedge.action_center.get_owner_dashboard_data", return_value=owner_payload),
		patch("retailedge.action_center.get_stock_position") as stock,
		patch("retailedge.action_center.get_expense_register", return_value=_empty_summary()),
		patch("retailedge.action_center.get_cash_shift_verification", return_value=_empty_summary()),
		patch("retailedge.action_center.get_customer_receivables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_supplier_payables", return_value=_empty_summary()),
		patch("retailedge.action_center.decorate_action_items", side_effect=lambda items, **kwargs: items),
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)

	stock.assert_not_called()
	assert len([row for row in result["items"] if row["source"] == "stock"]) == 1
