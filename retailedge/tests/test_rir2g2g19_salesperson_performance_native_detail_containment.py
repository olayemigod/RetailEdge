from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1] / "public/js"
DASHBOARD = ROOT / "salesperson_performance_dashboard/SalespersonPerformanceDashboardV2.vue"
BUNDLE = ROOT / "salesperson_performance.bundle.js"


def test_active_bundle_mounts_the_contained_v2_dashboard():
	assert "SalespersonPerformanceDashboardV2.vue" in BUNDLE.read_text(encoding="utf-8")


def test_salesperson_dashboard_consumes_capability_and_guards_native_routes():
	source = DASHBOARD.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source
	assert '["DocType", "Report"].includes(item.target_type)' in source
	assert "if (!this.canUseNativeDesk) return" in source


def test_native_detail_affordances_are_capability_gated():
	source = DASHBOARD.read_text(encoding="utf-8")
	assert "Advanced: Sales Invoices" in source
	assert ':disabled="!canUseNativeDesk"' in source
	assert 'clickable: this.canUseNativeDesk && ["salesperson", "sales_invoice", "customer"].includes(column.fieldname)' in source
	assert 'openSalesInvoices() { if (this.canUseNativeDesk) openNative("Sales Invoice"); }' in source
