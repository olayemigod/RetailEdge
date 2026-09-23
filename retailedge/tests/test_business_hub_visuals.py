from __future__ import annotations

from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import frappe

from retailedge.business_hub_visuals import (
	_cash_visual,
	_granularity,
	_period_rows,
	_sales_mix,
	_sales_trend,
	_top_mix_rows,
	get_business_hub_visuals,
)


ROOT = Path(__file__).resolve().parents[1]
PROVIDER = ROOT / "business_hub_visuals.py"
SALES = ROOT / "sales_reporting.py"
CASH = ROOT / "cash_movement.py"
HUB = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
CHART = ROOT / "public" / "js" / "retailedge_business_hub" / "BusinessHubChartCard.vue"




class TestBusinessHubVisualRuntimeRegression(TestCase):
	@patch("retailedge.business_hub_visuals.get_sales_visual_aggregates")
	def test_sales_trend_does_not_shadow_frappe_translation(self, aggregates):
		aggregates.return_value = {
			"trend": [{"posting_date": "2026-09-01", "net_sales": 120000, "transactions": 4}]
		}
		result = _sales_trend(
			{"company": "Demo Company", "from_date": "2026-09-01", "to_date": "2026-09-01"},
			start=frappe.utils.getdate("2026-09-01"),
			end=frappe.utils.getdate("2026-09-01"),
			currency="NGN",
		)
		self.assertTrue(result["description"])
		self.assertEqual(result["rows"][0]["net_sales"], 120000)

	@patch("retailedge.business_hub_visuals.get_sales_by_item_export")
	@patch("retailedge.business_hub_visuals.get_sales_visual_aggregates")
	def test_sales_mix_exposes_branch_category_and_brand_views(self, sales_aggregates, item_export):
		sales_aggregates.return_value = {
			"trend": [{"posting_date": "2026-09-01", "net_sales": 150000, "transactions": 3}],
			"branch_mix": [
				{"branch": "Lagos", "net_sales": 100000},
				{"branch": "Ikeja", "net_sales": 50000},
			],
			"branch_mix_supported": True,
		}
		item_export.return_value = {
			"rows": [
				{"item_group": "Beverages", "brand": "Acme", "net_sales": 90000},
				{"item_group": "Groceries", "brand": "Prime", "net_sales": 60000},
			]
		}
		result = _sales_mix(
			{"company": "Demo Company", "branch": "", "from_date": "2026-09-01", "to_date": "2026-09-30"},
			branch="",
			currency="NGN",
		)
		self.assertEqual(result["default_view"], "branch")
		self.assertEqual([row["value"] for row in result["view_options"]], ["branch", "category", "brand"])
		self.assertEqual(result["views"]["branch"]["title"], "Sales by Branch")
		self.assertEqual(result["views"]["category"]["rows"][0]["drill_field"], "item_group")
		self.assertEqual(result["views"]["brand"]["title"], "Sales by Brand")
		self.assertEqual(result["views"]["brand"]["route"], "")
		self.assertNotIn("drill_field", result["views"]["brand"]["rows"][0])

	@patch("retailedge.business_hub_visuals.get_cash_movement_visual_aggregates")
	def test_cash_visual_does_not_shadow_frappe_translation(self, aggregates):
		aggregates.return_value = {
			"rows": [{"posting_date": "2026-09-01", "money_in": 100000, "money_out": 25000}]
		}
		result = _cash_visual(
			{"company": "Demo Company", "from_date": "2026-09-01", "to_date": "2026-09-01"},
			start=frappe.utils.getdate("2026-09-01"),
			end=frappe.utils.getdate("2026-09-01"),
			currency="NGN",
		)
		self.assertTrue(result["description"])
		self.assertEqual(result["rows"][0]["money_in"], 100000)
		self.assertEqual(result["rows"][0]["money_out"], 25000)


def test_business_hub_visuals_are_composed_from_existing_reporting_authorities():
	source = PROVIDER.read_text(encoding="utf-8")
	for token in (
		"get_sales_visual_aggregates",
		"get_sales_by_item_export",
		"get_cash_movement_visual_aggregates",
		"get_expense_register_export",
		"get_customer_receivables_export",
		"get_supplier_payables_export",
		"get_stock_position",
		"get_operational_branch_scope",
		"validate_operating_branch",
	):
		assert token in source

	assert "get_sales_invoice_register_export" not in source
	assert "get_cash_movement_export" not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source
	assert "frappe.db.sql" not in source


def test_sales_and_cash_visuals_use_lightweight_aggregate_providers():
	sales = SALES.read_text(encoding="utf-8")
	cash = CASH.read_text(encoding="utf-8")

	assert "def get_sales_visual_aggregates" in sales
	assert 'group_by="posting_date, is_return"' in sales
	assert '"branch_mix_supported": bool(branch_field)' in sales
	assert "def get_cash_movement_visual_aggregates" in cash
	assert "GROUP BY gle.posting_date" in cash
	assert "_prepare_query(_coerce_filters(filters))" in cash


def test_visual_period_granularity_and_zero_fill_contract():
	start = frappe.utils.getdate("2026-09-01")
	assert _granularity(start, frappe.utils.getdate("2026-09-30")) == "day"
	assert _granularity(start, frappe.utils.getdate("2026-12-15")) == "week"
	assert _granularity(start, frappe.utils.getdate("2027-08-01")) == "month"

	rows = _period_rows(
		frappe.utils.getdate("2026-09-01"),
		frappe.utils.getdate("2026-09-03"),
		"day",
		("net_sales",),
	)
	assert [row["label"] for row in rows] == ["01 Sep", "02 Sep", "03 Sep"]
	assert [row["net_sales"] for row in rows] == [0.0, 0.0, 0.0]
	assert rows[0]["from_date"] == "2026-09-01"
	assert rows[-1]["to_date"] == "2026-09-03"


def test_top_mix_is_bounded_and_keeps_drill_metadata():
	rows = _top_mix_rows(
		{f"Category {index}": float(index) for index in range(1, 10)},
		drill_field="item_group",
	)
	assert len(rows) == 7
	assert rows[0]["label"] == "Category 9"
	assert rows[0]["drill_field"] == "item_group"
	assert rows[0]["drill_value"] == "Category 9"
	assert rows[-1]["key"] == "__other__"


@patch("retailedge.business_hub_visuals.frappe.get_cached_value", return_value="NGN")
@patch("retailedge.business_hub_visuals.user_has_global_branch_access", return_value=True)
@patch(
	"retailedge.business_hub_visuals.get_operational_branch_scope",
	return_value={"restricted": False, "allowed_branches": []},
)
@patch("retailedge.business_hub_visuals.get_stock_position")
@patch("retailedge.business_hub_visuals.get_supplier_payables_export")
@patch("retailedge.business_hub_visuals.get_customer_receivables_export")
@patch("retailedge.business_hub_visuals.get_expense_register_export")
@patch("retailedge.business_hub_visuals.get_cash_movement_visual_aggregates")
@patch("retailedge.business_hub_visuals.get_sales_by_item_export")
@patch("retailedge.business_hub_visuals.get_sales_visual_aggregates")
def test_visual_payload_exposes_six_drillable_owner_views(
	sales,
	sales_items,
	cash,
	expenses,
	receivables,
	payables,
	stock,
	scope,
	global_access,
	currency,
):
	sales.return_value = {
		"trend": [{"posting_date": "2026-09-01", "net_sales": 120000, "transactions": 4}],
		"branch_mix": [{"branch": "Lagos", "net_sales": 120000}],
		"branch_mix_supported": True,
	}
	sales_items.return_value = {"rows": []}
	cash.return_value = {
		"rows": [{"posting_date": "2026-09-01", "money_in": 100000, "money_out": 25000}]
	}
	expenses.return_value = {
		"rows": [{"expense_category": "Transport", "amount": 15000}]
	}
	receivables.return_value = {
		"rows": [{"ageing_bucket": "Current", "outstanding": 50000}]
	}
	payables.return_value = {
		"rows": [{"ageing_bucket": "1-30 Days", "outstanding": 30000}]
	}
	stock.return_value = {
		"summary": [
			{"label": "Available Items", "value": 20},
			{"label": "Reorder Due", "value": 2},
			{"label": "Out of Stock", "value": 1},
			{"label": "Negative Stock", "value": 0},
			{"label": "Fully Reserved", "value": 1},
		]
	}

	result = get_business_hub_visuals(
		company="Demo Company",
		branch="",
		from_date="2026-09-01",
		to_date="2026-09-07",
	)

	assert result["currency"] == "NGN"
	assert [row["key"] for row in result["visuals"]] == [
		"sales_trend",
		"sales_mix",
		"expense_mix",
		"exposure",
		"stock_health",
		"cash_flow",
	]
	assert all(row["available"] for row in result["visuals"])
	assert result["visuals"][0]["chart_type"] == "line"
	assert result["visuals"][1]["title"] == "Sales by Branch"
	assert result["visuals"][2]["key"] == "expense_mix"
	assert result["visuals"][3]["time_basis"] == "current"
	assert result["visuals"][4]["rows"][1]["drill_value"] == "Reorder Due"
	assert result["visuals"][5]["chart_type"] == "grouped_bar"


def test_business_hub_frontend_renders_visual_layer_and_drill_through():
	hub = HUB.read_text(encoding="utf-8")
	chart = CHART.read_text(encoding="utf-8")

	for token in (
		"retailedge.business_hub_visuals.get_business_hub_visuals",
		"Business overview",
		"BusinessHubChartCard",
		"homeVisuals",
		"refreshHomeVisuals",
		"drillHomeVisual",
		"home-visual-grid",
		"visualRequestId",
	):
		assert token in hub

	for token in (
		"hub-line-chart",
		"hub-bar-chart",
		"@click=\"$emit('drill', chart, row, series)\"",
		"var(--edge-color-surface",
		"prefers-reduced-motion",
		"aria-label",
		"lineExtent",
	):
		assert token in chart


def test_placeholder_mix_labels_are_not_false_drill_targets(monkeypatch):
	monkeypatch.setattr(
		"retailedge.business_hub_visuals.get_sales_visual_aggregates",
		lambda _filters: {
			"trend": [],
			"branch_mix": [{"branch": "", "net_sales": 1250}],
			"branch_mix_supported": True,
		},
	)
	sales = _sales_mix(
		{"company": "Demo Company", "branch": "", "from_date": "2026-09-01", "to_date": "2026-09-30"},
		branch="",
		currency="NGN",
	)
	row = next(item for item in sales["rows"] if item["label"] == "Unattributed")
	assert "drill_field" not in row
	assert "drill_value" not in row
