from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import action_center


def _empty_summary() -> dict:
	return {"summary": []}


def test_action_center_prioritises_after_follow_up_decoration():
	frappe.session.user = "Administrator"
	stock_payload = {
		"summary": [
			{"label": "Negative Stock", "value": 0, "datatype": "Int"},
			{"label": "Out of Stock", "value": 4, "datatype": "Int"},
			{"label": "Fully Reserved", "value": 0, "datatype": "Int"},
		]
	}

	def decorate(items, **_kwargs):
		result = [dict(item) for item in items]
		for item in result:
			item["follow_up"] = {
				"effective_status": "Open",
				"is_due": item.get("source") == "stock",
			}
		return result

	with (
		patch("retailedge.action_center.get_stock_position", return_value=stock_payload),
		patch("retailedge.action_center.get_expense_register", return_value=_empty_summary()),
		patch("retailedge.action_center.get_cash_shift_verification", return_value=_empty_summary()),
		patch("retailedge.action_center.get_customer_receivables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_supplier_payables", return_value=_empty_summary()),
		patch("retailedge.action_center.get_bank_exception_summary", return_value=_empty_summary()),
		patch("retailedge.action_center.decorate_action_items", side_effect=decorate),
	):
		result = action_center.get_action_center_data(
			{"company": "Test Company", "from_date": "2026-08-01", "to_date": "2026-08-20"}
		)

	assert result["items"][0]["source"] == "stock"
	assert "follow-up due or overdue" in result["items"][0]["priority_reason"]
	assert result["metadata"]["prioritization_model"] == (
		"severity_then_due_follow_up_then_age_then_comparable_financial_exposure"
	)
	assert result["metadata"]["priority_score"] is None


def test_action_center_ui_displays_server_priority_reason_without_client_scoring():
	vue = Path(
		Path(action_center.__file__).parent / "public/js/action_center/ActionCenter.vue"
	).read_text(encoding="utf-8")
	assert "Why this is prioritised: {{ item.priority_reason }}" in vue
	assert "priority_score" not in vue
