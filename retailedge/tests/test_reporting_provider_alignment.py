from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
JS_ROOT = APP_ROOT / "public" / "js"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_true_paginated_reports_use_query_level_provider_contract():
	cases = (
		("cash_movement.bundle.js", "cash-movement", "get_cash_movement", "get_cash_movement_export"),
		("expense_register.bundle.js", "expense-register", "get_expense_register", "get_expense_register_export"),
	)
	for filename, report_key, page_method, export_method in cases:
		source = read(JS_ROOT / filename)
		assert f'const REPORT_KEY = "{report_key}"' in source
		assert "createPaginatedReportProvider" in source
		assert "createBoundedPaginatedReportProvider" not in source
		assert "defaultPageLength: 50" in source
		assert "maxPageLength: 100" in source
		assert page_method in source
		assert export_method in source
		assert "for (let page" not in source
		assert "setInterval(" not in source


def test_sales_reports_use_bounded_materialized_provider_contract_with_real_caps():
	source = read(JS_ROOT / "sales_reporting.bundle.js")
	assert "createBoundedPaginatedReportProvider" in source
	assert 'key: "sales-by-item"' in source
	assert 'key: "sales-invoice-register"' in source
	assert "maxDatasetRows: 10000" in source
	assert "maxDatasetRows: 2000" in source
	assert "get_sales_by_item" in source
	assert "get_sales_by_item_export" in source
	assert "get_sales_invoice_register" in source
	assert "get_sales_invoice_register_export" in source
	assert "createPaginatedReportProvider" not in source
	assert "for (let page" not in source


def test_stock_reports_use_bounded_materialized_provider_contract_with_real_caps():
	cases = (
		("stock_position.bundle.js", "stock-position", 10000, "get_stock_position", "get_stock_position_export"),
		(
			"stock_movement_history.bundle.js",
			"stock-movement-history",
			1000,
			"get_stock_movement_page",
			"get_stock_movement_export",
		),
	)
	for filename, report_key, dataset_cap, page_method, export_method in cases:
		source = read(JS_ROOT / filename)
		assert f'const REPORT_KEY = "{report_key}"' in source
		assert "createBoundedPaginatedReportProvider" in source
		assert f"maxDatasetRows: {dataset_cap}" in source
		assert "defaultPageLength: 50" in source
		assert "maxPageLength: 100" in source
		assert page_method in source
		assert export_method in source
		assert "createPaginatedReportProvider" not in source
		assert "for (let page" not in source


def test_provider_alignment_preserves_separate_full_export_paths():
	for filename in (
		"cash_movement.bundle.js",
		"expense_register.bundle.js",
		"sales_reporting.bundle.js",
		"stock_position.bundle.js",
		"stock_movement_history.bundle.js",
	):
		source = read(JS_ROOT / filename)
		assert "exportReport:" in source
		assert "page_length" in source
		assert "page_size" in source
		assert "setInterval(" not in source
