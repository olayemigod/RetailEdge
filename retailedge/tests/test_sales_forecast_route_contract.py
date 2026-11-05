from __future__ import annotations

import json
from pathlib import Path

from retailedge.navigation_consolidation import (
	LEGACY_SALES_FORECAST_TARGET,
	RETAILEDGE_SALES_FORECAST_TARGET,
	_normalize_sales_forecast_route,
)


ROOT = Path(__file__).resolve().parents[1]
ALIAS_PAGE = ROOT / "retailedge" / "page" / "retailedge_sales_forecast"
ALIAS_JSON = ALIAS_PAGE / "retailedge_sales_forecast.json"
ALIAS_JS = ALIAS_PAGE / "retailedge_sales_forecast.js"
SALES_FORECAST_UI = ROOT / "public" / "js" / "sales_forecast" / "SalesForecast.vue"


def test_sales_forecast_page_uses_non_colliding_retailedge_route():
	page = json.loads(ALIAS_JSON.read_text(encoding="utf-8"))
	loader = ALIAS_JS.read_text(encoding="utf-8")
	ui = SALES_FORECAST_UI.read_text(encoding="utf-8")

	assert page["name"] == RETAILEDGE_SALES_FORECAST_TARGET
	assert page["page_name"] == RETAILEDGE_SALES_FORECAST_TARGET
	assert page["title"] == "Sales Forecast"
	assert {row["role"] for row in page["roles"]} >= {"Sales User", "Sales Manager", "RetailEdgeManager"}
	assert f'const PAGE_ROUTE = "{RETAILEDGE_SALES_FORECAST_TARGET}";' in loader
	assert 'const SALES_FORECAST_ASSET = "sales_forecast.bundle.js";' in loader
	assert "window.mountSalesForecast" in loader
	assert f'activeRoute="/app/{RETAILEDGE_SALES_FORECAST_TARGET}"' in ui


def test_final_navigation_remaps_only_retailedge_page_not_native_doctype():
	groups = [
		{
			"key": "insights",
			"items": [
				{"label": "Sales Forecast", "target_type": "Page", "target": LEGACY_SALES_FORECAST_TARGET},
				{"label": "Native Sales Forecast", "target_type": "DocType", "target": "Sales Forecast"},
			],
		}
	]

	_normalize_sales_forecast_route(groups)

	assert groups[0]["items"][0]["target"] == RETAILEDGE_SALES_FORECAST_TARGET
	assert groups[0]["items"][1]["target"] == "Sales Forecast"
