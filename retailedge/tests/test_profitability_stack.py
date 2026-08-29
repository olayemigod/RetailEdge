from pathlib import Path


def test_r8_keeps_predecessor_component_contract_names():
	sales = Path("retailedge/tests/test_sales_reporting_edgeui.py").read_text()
	stock = Path("retailedge/tests/test_stock_position_edgeui.py").read_text()
	assert 'SalesReportingReport.vue' in sales
	assert 'StockPositionReport.vue' in stock
