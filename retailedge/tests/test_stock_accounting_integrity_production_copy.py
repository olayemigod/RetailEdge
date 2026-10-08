from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/stock_accounting_integrity/StockAccountingIntegrityReport.vue"


def test_stock_accounting_integrity_uses_business_copy_and_preserves_native_report_authority():
	text = COMPONENT.read_text(encoding="utf-8")

	for marker in (
		"Read-only stock-versus-accounting exceptions.",
		"Stock and Account Value Comparison report",
		"No stock-versus-accounting exceptions were returned",
		"Checking stock and accounting integrity…",
		"Open Stock and Account Value Comparison",
		"Advanced report access is required",
		"Open Advanced Report",
		"Advanced Report Unavailable",
		"exception row",
		"authorised accounting workflows",
		'{ label: "Source", value: "Stock and Account Value Comparison" }',
	):
		assert marker in text

	for forbidden in (
		"Read-only ERPNext stock-versus-accounting exceptions",
		"ERPNext returned no stock-versus-accounting exceptions",
		"Checking ERPNext stock and accounting integrity",
		"Open ERPNext Stock and Account Value Comparison",
		"Native Desk access is required",
		"Open ERPNext Advanced Report",
		"Advanced: ERPNext Report",
		"ERPNext exception row",
		"authorised ERPNext workflows",
		"ERPNext Stock and Account Value Comparison",
	):
		assert forbidden not in text

	for marker in (
		'window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)',
		'window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)',
		'nativeReportName: "Stock and Account Value Comparison"',
		"canUseNativeDesk: false",
		"canOpenNativeReport: false",
		'clickable: this.canUseNativeDesk && ["name", "voucher_no"].includes(column.fieldname)',
		'v-if="canOpenNativeReport"',
		':disabled="!canUseNativeDesk"',
		"if (!this.canUseNativeDesk || !this.canOpenNativeReport || !this.nativeReportName) return;",
		'frappe.set_route("query-report", this.nativeReportName);',
		'frappe.set_route("Form", payload.row.voucher_type, payload.value);',
		'frappe.set_route("Form", payload.row.ledger_type, payload.value);',
	):
		assert marker in text
