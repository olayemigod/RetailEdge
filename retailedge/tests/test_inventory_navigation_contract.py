from retailedge import edgesuite_ui


def _group(key):
	return next(group for group in edgesuite_ui.NAVIGATION_GROUPS if group["key"] == key)


def test_r10_inventory_pages_are_classified_without_hiding_native_detail_report():
	stock = _group("stock")
	stock_items = {item["label"]: item for item in stock["items"]}
	assert stock_items["Inventory Intelligence"]["target"] == "inventory-intelligence"
	assert stock_items["Transfer Opportunities"]["target"] == "inventory-transfer-opportunities"
	assert stock_items["Inventory Ageing"]["target"] == "inventory-ageing"
	assert stock_items["Stock Ageing (Detailed)"]["target_type"] == "Report"
	assert stock_items["Stock Ageing (Detailed)"]["target"] == "Stock Ageing"

	insights = _group("insights")
	insight_items = {item["label"]: item for item in insights["items"]}
	assert insight_items["Inventory + Profitability"]["target_type"] == "Page"
	assert insight_items["Inventory + Profitability"]["target"] == "inventory-profitability"
