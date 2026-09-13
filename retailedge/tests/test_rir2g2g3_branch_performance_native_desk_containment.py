from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/branch_performance_dashboard/BranchPerformanceDashboard.vue"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_branch_performance_defaults_native_fallback_closed():
	source = _source()
	assert "nativeFallbackEnabled: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source


def test_detailed_report_action_is_capability_gated():
	source = _source()
	assert '<button v-if="nativeFallbackEnabled" type="button" class="edge-button edge-button--secondary" @click="openDetailReport">' in source
	assert 'openDetailReport() { if (!this.nativeFallbackEnabled) return; frappe.set_route("query-report", "RetailEdge Branch Performance Summary"); }' in source


def test_page_navigation_fails_closed_for_native_targets():
	source = _source()
	guard = 'if (["DocType", "Report"].includes(item.target_type) && !this.nativeFallbackEnabled) return;'
	assert guard in source
	assert 'if (item.target_type === "Page") frappe.set_route(item.target);' in source
	assert 'else if (item.target_type === "Report") frappe.set_route("query-report", item.target);' in source
	assert 'else if (item.target_type === "DocType") frappe.set_route("List", item.target);' in source
