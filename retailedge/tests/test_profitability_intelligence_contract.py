from pathlib import Path


def test_profitability_backend_uses_submitted_sales_cost_truth_and_cost_policy():
	text = Path("retailedge/profitability_intelligence.py").read_text()
	assert "_get_permitted_invoice_headers" in text
	assert '"incoming_rate"' in text
	assert '"base_net_amount"' in text
	assert "should_hide_cost_price" in text
	assert "MAX_PROFITABILITY_ROWS" in text
	assert "ignore_permissions" not in text
	assert "frappe.db.commit" not in text


def test_profitability_page_uses_edgesuite_runtime_and_no_raw_html_injection():
	page = Path("retailedge/retailedge/page/profitability_intelligence/profitability_intelligence.js").read_text()
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()
	assert 'edgeui.bundle.js' in page
	assert "mountProfitabilityIntelligence" in page
	assert "EdgeAppShell" in component
	assert "EdgeDashboardShell" in component
	assert "innerHTML" not in page
	assert "insertAdjacentHTML" not in page
