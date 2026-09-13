from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/sales_dashboard/SalesDashboard.vue"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_sales_overview_defaults_native_fallback_closed():
	source = _source()
	assert "nativeFallbackEnabled: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source


def test_recent_invoice_identity_is_preserved_without_native_form_action():
	source = _source()
	assert '<template v-for="row in recentInvoices" :key="row.invoice">' in source
	assert '<button v-if="nativeFallbackEnabled" type="button" class="sales-list-row" @click="openInvoice(row.invoice)">' in source
	assert '<div v-else class="sales-list-row sales-list-row--static">' in source
	assert "{{ row.invoice }}" in source
	assert "{{ row.customer_name || row.customer }}" in source
	assert "{{ formatDate(row.posting_date) }}" in source
	assert "{{ formatCurrency(row.grand_total) }}" in source


def test_sales_overview_native_routes_fail_closed():
	source = _source()
	assert 'if (["DocType", "Report"].includes(item.target_type) && !this.nativeFallbackEnabled) return;' in source
	assert 'openInvoice(name) { if (!this.nativeFallbackEnabled) return; if (name) frappe.set_route("Form", "Sales Invoice", name); }' in source


def test_edgesuite_dashboard_routes_remain_available():
	source = _source()
	for contract in (
		'openRoute(routes.invoice_register)',
		'openRoute(routes.sales_by_item)',
		'openRoute(routes.salesperson_performance)',
		'openRoute(routes.branch_performance)',
	):
		assert contract in source
