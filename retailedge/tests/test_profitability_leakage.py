from pathlib import Path


def test_leakage_evidence_is_bounded_and_permission_scoped():
	text = Path("retailedge/profitability_leakage.py").read_text()
	assert "_get_permitted_invoice_headers" in text
	assert "_assert_report_access" in text
	assert "should_hide_cost_price" in text
	assert "MAX_LEAKAGE_EVIDENCE_ROWS = 100" in text
	assert '"discount_percentage"' in text
	assert '"base_price_list_rate"' in text
	assert '"incoming_rate"' in text
	assert "ignore_permissions" not in text
	assert "frappe.db.commit" not in text


def test_leakage_invoice_drillthrough_opens_native_document_in_new_tab():
	component = Path("retailedge/public/js/profitability_intelligence/ProfitabilityIntelligence.vue").read_text()
	assert "Review Evidence" in component
	assert "get_margin_leakage_evidence" in component
	assert 'window.open(selected.route, "_blank", "noopener,noreferrer")' in component
	assert 'fieldtype: "HTML"' not in component
	assert "innerHTML" not in component
