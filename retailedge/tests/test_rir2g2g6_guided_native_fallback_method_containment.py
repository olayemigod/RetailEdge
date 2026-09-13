from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUB = ROOT / "public/js/retailedge_business_hub"

DIALOGS = (
	"SimpleSalesInvoiceDialog.vue",
	"SimplePurchaseInvoiceDialog.vue",
	"SimplePaymentDialog.vue",
	"SimpleStockTransferDialog.vue",
	"SimpleStockAdjustmentDialog.vue",
	"SimpleCashDepositDialog.vue",
	"SimpleCashTransferDialog.vue",
	"SimpleCashierExpenseDialog.vue",
)


def test_guided_full_form_fallbacks_fail_closed_in_child_methods():
	for filename in DIALOGS:
		source = (HUB / filename).read_text(encoding="utf-8")
		assert 'v-if="nativeFallbackEnabled"' in source, filename
		start = source.index("openFullForm()")
		block = source[start : start + 420]
		assert "nativeFallbackEnabled" in block, filename
		assert 'this.$emit("open-native"' in block, filename
