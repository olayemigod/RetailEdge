from pathlib import Path


def test_profitability_export_uses_shared_dashboard_pipeline():
	dashboard_files = Path("retailedge/dashboard_files.py").read_text()
	capabilities = Path("retailedge/dashboard_capabilities.py").read_text()
	export_module = Path("retailedge/profitability_export.py").read_text()
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()

	assert '"profitability-intelligence"' in dashboard_files
	assert "build_profitability_export_dataset" in dashboard_files
	assert 'key="profitability-intelligence"' in capabilities
	assert "get_profitability_intelligence" in export_module
	assert "exportDashboard(DASHBOARD_KEY" in component
	assert "printDashboard(DASHBOARD_KEY" in component
	assert "defaultDashboardExportOptions" in component
