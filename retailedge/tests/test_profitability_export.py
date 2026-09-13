from pathlib import Path


def test_profitability_export_uses_shared_dashboard_pipeline():
	dashboard_files = Path("retailedge/dashboard_files.py").read_text()
	capabilities = Path("retailedge/dashboard_capabilities.py").read_text()
	export_module = Path("retailedge/profitability_export.py").read_text()
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()

	assert '"profitability-intelligence"' in dashboard_files
	assert "build_profitability_export_dataset" in dashboard_files
	assert "all_filtered=all_filtered" in dashboard_files
	assert 'key="profitability-intelligence"' in capabilities
	assert "get_profitability_intelligence" in export_module
	assert "_build_full_dimensions" in export_module
	assert "_dimension_rows(branch_buckets, limit=None)" in export_module
	assert "_get_permitted_invoice_headers" in export_module
	assert "exportDashboard(DASHBOARD_KEY" in component
	assert "printDashboard(DASHBOARD_KEY" in component
	assert "defaultDashboardExportOptions" in component


def test_profitability_page_uses_permission_aware_company_and_branch_filters():
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()
	assert 'label="Company"' in component
	assert 'label="Branch"' in component
	assert "search_sales_reporting_options" in component
	assert 'kind: "company"' in component
	assert 'kind: "branch"' in component
	assert "this.filters.branch = \"\"" in component


def test_profitability_page_exposes_accounting_reconciliation_and_missing_cost_warning():
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()
	assert "ERPNext Accounting Reconciliation" in component
	assert "reconciliation.transaction_gross_profit" in component
	assert "reconciliation.accounting_gross_profit" in component
	assert "Missing Recorded Cost" in component
	assert "missingCostRows" in component
