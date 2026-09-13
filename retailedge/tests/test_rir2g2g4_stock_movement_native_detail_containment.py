from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/stock_movement_history/StockMovementHistory.vue"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_stock_movement_defaults_native_fallback_closed():
	source = _source()
	assert "nativeFallbackEnabled: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source


def test_item_and_voucher_identity_survive_without_native_links():
	source = _source()
	assert 'v-if="nativeFallbackEnabled" href="#" class="doc-link" @click.prevent="openDoc(\'Item\', row.item_code)"' in source
	assert '<span v-else class="doc-identity">{{ row.item_code }}</span>' in source
	assert 'v-if="nativeFallbackEnabled && row.voucher_type && row.voucher_no"' in source
	assert '<span v-else-if="row.voucher_type && row.voucher_no" class="doc-identity">{{ row.voucher_no }}</span>' in source
	assert '<div v-if="row.voucher_type" class="subtle">{{ row.voucher_type }}</div>' in source


def test_stock_movement_native_routes_fail_closed():
	source = _source()
	assert 'if (["DocType", "Report"].includes(item.target_type) && !this.nativeFallbackEnabled) return;' in source
	assert 'openDoc(doctype, name) {\n\t\t\tif (!this.nativeFallbackEnabled) return;' in source
	assert 'if (doctype && name) frappe.set_route("Form", doctype, name);' in source


def test_edgesuite_and_url_navigation_are_preserved():
	source = _source()
	assert 'if (item.target_type === "Page") frappe.set_route(item.target);' in source
	assert 'else if (item.target_type === "URL" && item.target) window.location.assign(item.target);' in source
