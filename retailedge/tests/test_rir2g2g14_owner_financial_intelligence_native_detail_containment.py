from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
PROFITABILITY = ROOT / "profitability_intelligence/ProfitabilityIntelligence.vue"
FILES = (
	PROFITABILITY,
	ROOT / "cash_flow_outlook/CashFlowOutlookReport.vue",
	ROOT / "money_overview/MoneyOverview.vue",
	ROOT / "owner_dashboard/OwnerDashboard.vue",
)


def test_owner_financial_pages_consume_capability_and_guard_shell_routes():
	for path in FILES:
		source = path.read_text(encoding="utf-8")
		assert "canUseNativeDesk: false" in source, path
		assert "Boolean(navigation.access?.can_use_native_desk)" in source, path
		assert '["DocType", "Report"].includes(item.target_type)' in source, path
		assert "!this.canUseNativeDesk" in source, path


def test_profitability_evidence_keeps_identity_and_contains_native_invoice_action():
	source = PROFITABILITY.read_text(encoding="utf-8")
	assert '{ fieldtype: "Select", fieldname: "invoice", label: __("Sales Invoice")' in source
	assert "...(this.canUseNativeDesk ? {" in source
	assert 'primary_action_label: __("Open Salesriel Invoice")'.replace("Salesriel", "Sales") in source
	assert "if (!this.canUseNativeDesk) return" in source
	assert 'if (selected?.route) window.open(selected.route, "_blank", "noopener,noreferrer")' in source


def test_owner_and_money_drill_through_remains_edgesuite_owned():
	for path in FILES[2:]:
		source = path.read_text(encoding="utf-8")
		assert "this.openRoute(section?.route)" in source
