from __future__ import annotations

from pathlib import Path


SOURCE = (
	Path(__file__).resolve().parents[1]
	/ "public/js/payment_management/PaymentManagement.vue"
)


def test_payment_management_shell_native_navigation_fails_closed():
	source = SOURCE.read_text(encoding="utf-8")
	assert "canUseNativeDesk" in source
	assert "Boolean(navigation?.access?.can_use_native_desk)" in source
	assert '(item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk' in source


def test_payment_management_existing_native_detail_handlers_remain_guarded():
	source = SOURCE.read_text(encoding="utf-8")
	assert "openPaymentEntries() { if (!this.canUseNativeDesk) return;" in source
	assert "openPayment(name) { if (!this.canUseNativeDesk) return;" in source
	assert "openInvoice(name) { if (!this.canUseNativeDesk) return;" in source
