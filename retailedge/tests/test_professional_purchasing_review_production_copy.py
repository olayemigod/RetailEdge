from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def _assert_absent(text: str, phrases: tuple[str, ...]) -> None:
	for phrase in phrases:
		assert phrase not in text


def test_purchase_order_review_hides_platform_implementation_copy():
	text = _read("public/js/professional_purchasing/ProfessionalPurchaseOrderSubmitOverlay.vue")

	_assert_absent(
		text,
		(
			"saved ERPNext order",
			"Frappe Workflow",
			"Ready for standard ERPNext submission",
			"ERPNext recalculates and validates",
			"Frappe's permitted transitions",
			"ERPNext's normal submit path",
			"Advanced: ERPNext",
			"submitted ERPNext Purchase Order",
			"current ERPNext draft",
		),
	)
	assert "Advanced: Open Purchase Order" in text
	assert "customerFacingCopy(preview.workflow_readiness?.workflow" in text
	assert "customerFacingCopy(blocker" in text
	assert "customerFacingCopy(preview.workflow_readiness?.message" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert 'frappe.set_route("Form", "Purchase Order", this.purchaseOrder)' in text


def test_purchase_receipt_history_page_hides_platform_implementation_copy():
	text = _read("public/js/professional_purchasing/PurchaseReceiptHistoryPage.vue")

	_assert_absent(
		text,
		(
			"submitted ERPNext Purchase Receipts",
			"Advanced: ERPNext",
		),
	)
	assert "Advanced: Open Purchase Receipt" in text
	assert "Review submitted Purchase Receipts" in text
	assert "customerFacingCopy(message, fallback)" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert 'frappe.set_route("Form", "Purchase Receipt", name)' in text
