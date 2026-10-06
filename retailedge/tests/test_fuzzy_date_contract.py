from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPORTING_ACTIONS = ROOT / "retailedge" / "public" / "js" / "retailedge_reporting_actions.js"
BUSINESS_HUB = (
	ROOT
	/ "retailedge"
	/ "public"
	/ "js"
	/ "retailedge_business_hub"
	/ "RetailEdgeBusinessHub.vue"
)


def test_retailedge_installs_one_global_smart_date_policy():
	text = REPORTING_ACTIONS.read_text()
	assert "installSmartDatePolicy" in text
	assert 'runtime.registerComponent("EdgeSmartDateRange", RetailEdgeSmartDateRange, { replace: true })' in text
	assert 'window.addEventListener("edgesuite:report-runtime-ready"' in text
	assert "installSmartDatePolicy(window.EdgeSuiteUI)" in text


def test_retailedge_smart_date_policy_removes_visual_quick_presets():
	text = REPORTING_ACTIONS.read_text()
	assert "showPresets: false" in text
	assert "presets: []" in text
	assert "May to June 2026" in text
	assert "last 2 months" in text
	assert "previous 2 months" in text
	assert "YTD" in text


def test_retailedge_policy_does_not_translate_periods_back_to_free_text_dates():
	text = REPORTING_ACTIONS.read_text()
	assert "baseSmartDateRange" in text
	assert "...attrs" in text
	assert "from_date" not in text[text.index("function installSmartDatePolicy"):text.index("function installShellGovernance")]
	assert "to_date" not in text[text.index("function installSmartDatePolicy"):text.index("function installShellGovernance")]


def test_business_hub_uses_shared_smart_date_control_not_transaction_date_inputs():
	text = BUSINESS_HUB.read_text()
	assert "<EdgeSmartDateRange" in text
	assert 'label="Period"' in text
	assert '@resolved="handleHomeDateResolved"' in text
