from __future__ import annotations

from pathlib import Path


SOURCE = (
	Path(__file__).resolve().parents[1]
	/ "public/js/stock_accounting_integrity/StockAccountingIntegrityReport.vue"
)


def test_stock_accounting_integrity_consumes_native_desk_capability_and_guards_shell_routes():
	source = SOURCE.read_text(encoding="utf-8")
	assert "canUseNativeDesk: false" in source
	assert "Boolean(navigation.access?.can_use_native_desk)" in source
	assert '(item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk' in source


def test_native_detail_clickability_and_handlers_fail_closed_without_native_desk():
	source = SOURCE.read_text(encoding="utf-8")
	assert 'clickable: this.canUseNativeDesk && ["name", "voucher_no"].includes(column.fieldname)' in source
	assert "openReportCell(payload) {" in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'frappe.set_route("Form", payload.row.voucher_type, payload.value)' in source
	assert 'frappe.set_route("Form", payload.row.ledger_type, payload.value)' in source


def test_advanced_native_report_respects_backend_permission_and_native_desk_capability():
	source = SOURCE.read_text(encoding="utf-8")
	assert 'v-if="canOpenNativeReport"' in source
	assert ':disabled="!canUseNativeDesk"' in source
	assert "Advanced: ERPNext Report" in source
	assert "if (!this.canUseNativeDesk || !this.canOpenNativeReport || !this.nativeReportName) return;" in source
