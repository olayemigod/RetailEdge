from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/cash_movement/CashMovementReport.vue"
DOC = ROOT.parent / "docs/rir2f3f22_cash_movement_native_detail_containment.md"


def _source() -> str:
	return COMPONENT.read_text(encoding="utf-8")


def test_cash_movement_uses_final_access_context_and_fails_closed():
	source = _source()
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);" in source
	assert "retailedge.master_experience.get_retailedge_business_hub_context" in source
	assert "retailedge.edgesuite_ui.get_retailedge_business_hub_context" not in source


def test_voucher_drillthrough_requires_native_desk():
	source = _source()
	assert 'clickable: this.canUseNativeDesk && column.fieldname === "voucher_no"' in source
	assert "openReportCell(payload)" in source
	assert "openSource(row)" in source
	assert "if (!this.canUseNativeDesk) return;" in source
	assert 'frappe.set_route("Form", row.voucher_type, row.voucher_no)' in source


def test_payments_handoff_prefers_edgesuite_payment_management():
	source = _source()
	assert 'return this.hasPageTarget("payment-management");' in source
	assert "return this.paymentManagementAvailable || this.canUseNativeDesk;" in source
	assert 'frappe.set_route("payment-management");' in source
	assert 'if (this.canUseNativeDesk) frappe.set_route("List", "Payment Entry");' in source
	assert '"Advanced: Payments in ERPNext"' in source


def test_generic_native_navigation_is_defensively_gated():
	source = _source()
	assert 'if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;' in source


def test_slice_changes_no_cash_movement_accounting_or_scope_backend():
	doc = DOC.read_text(encoding="utf-8")
	assert "No Cash Movement backend file is changed" in doc
	assert "ERPNext General Ledger remains the accounting truth" in doc
	assert "B4B11 Branch/read-scope contract remains unchanged" in doc
