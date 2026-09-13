from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
OWNERSHIP = ROOT / "public/js/professional_purchasing/professionalPurchaseReturnOwnership.js"
OVERLAY = ROOT / "public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue"


def _method_block(source: str, name: str) -> str:
	start = source.index(f"async {name}()")
	return source[start : start + 900]


def test_legacy_return_handlers_require_native_desk():
	source = PAGE.read_text(encoding="utf-8")
	for method in ("preparePurchaseReturn", "prepareSupplierDebitNote"):
		block = _method_block(source, method)
		assert "!this.canUseNativeDesk" in block, method
		assert 'frappe.set_route("Form"' in block, method


def test_standard_return_actions_remain_owned_by_edgesuite_review():
	ownership = OWNERSHIP.read_text(encoding="utf-8")
	overlay = OVERLAY.read_text(encoding="utf-8")
	assert 'root.addEventListener("click", handler, true)' in ownership
	assert "event.stopImmediatePropagation()" in ownership
	assert "Review & Submit Return" in ownership
	assert "Review & Submit Debit Note" in ownership
	assert "retailedge.professional_purchase_returns.get_purchase_return_review" in overlay
	assert "retailedge.professional_purchase_returns.submit_purchase_return_review" in overlay


def test_advanced_return_fallback_remains_capability_gated():
	overlay = OVERLAY.read_text(encoding="utf-8")
	assert 'v-if="nativeFallbackEnabled"' in overlay
	start = overlay.index("async openAdvanced()")
	block = overlay[start : start + 1400]
	assert "!this.nativeFallbackEnabled" in block
	assert 'frappe.set_route("Form"' in block
