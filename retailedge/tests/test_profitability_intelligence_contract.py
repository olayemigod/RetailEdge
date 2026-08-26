from pathlib import Path


def test_profitability_backend_uses_submitted_sales_cost_truth_and_cost_policy():
	text = Path("retailedge/profitability_intelligence.py").read_text()
	assert "_get_permitted_invoice_headers" in text
	assert '"incoming_rate"' in text
	assert '"base_net_amount"' in text
	assert "should_hide_cost_price" in text
	assert "MAX_PROFITABILITY_ROWS" in text
	assert "allocated_percentage" in text
	assert "total_weight" in text
	assert "ignore_permissions" not in text
	assert "frappe.db.commit" not in text


def test_owner_dashboard_contains_profitability_section_and_attention():
	text = Path("retailedge/owner_dashboard.py").read_text()
	assert '"profitability"' in text
	assert "get_profitability_summary" in text
	assert '"Accounting Gross Profit"' in text
	assert '"Accounting Net Profit"' in text
	assert '"Transactional Gross Profit"' in text
	assert '"Negative Margin Items"' in text
	assert '"Low Margin Items"' in text
	assert '"Items Missing Recorded Cost"' in text


def test_profitability_page_uses_edgesuite_runtime_and_no_raw_html_injection():
	page = Path("retailedge/retailedge/page/profitability_intelligence/profitability_intelligence.js").read_text()
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()
	assert 'edgeui.bundle.js' in page
	assert "mountProfitabilityIntelligence" in page
	assert "EdgeAppShell" in component
	assert "EdgeDashboardShell" in component
	assert "Profitability by Salesperson" in component
	assert "Previous Period" in component
	assert "innerHTML" not in page
	assert "insertAdjacentHTML" not in page
