from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def test_professional_purchasing_shell_uses_business_facing_copy():
	text = _read("retailedge/page/professional_purchasing/professional_purchasing.js")

	for phrase in (
		"Advanced: Open in ERPNext",
		"Advanced: Purchase Receipts in ERPNext",
		"native ERPNext review",
		"full ERPNext Purchase Order form",
		"Preview ERPNext's Purchase Receipt mapping",
		"EdgeSuite-only operational guard is unavailable",
		"EdgeSuite UI runtime is unavailable",
		"bundle is unavailable",
	):
		assert phrase not in text

	assert 'ADVANCED_PURCHASE_ORDER_LABEL = "Advanced: Open Purchase Order"' in text
	assert 'ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts"' in text
	assert "window.retailedge?.userErrorMessage?.(error" in text


def test_rfq_history_overlay_sanitizes_static_and_runtime_copy():
	text = _read("public/js/professional_purchasing/ProfessionalRfqHistoryOverlay.vue")

	for phrase in (
		"using ERPNext quotation truth",
		"ERPNext recorded the quotation",
		"ERPNext's RFQ → Supplier Quotation mapper",
		"Advanced ERPNext",
		"Advanced: Open in ERPNext",
		"Advanced: RFQs in ERPNext",
		"ERPNext could not record and submit",
	):
		assert phrase not in text

	assert "Advanced: Open RFQ" in text
	assert "Advanced: RFQ List" in text
	assert "customerFacingCopy(message" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text


def test_purchase_receipt_review_hides_platform_implementation_copy():
	text = _read("public/js/professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue")

	for phrase in (
		"Review ERPNext's receipt mapping",
		"ERPNext has posted the receipt stock movement",
		"Frappe Workflow reaches a submitting state",
		"create and submit the ERPNext Purchase Receipt",
		"ERPNext remains responsible",
		"Advanced: Prepare in ERPNext",
		"submits an ERPNext Purchase Receipt",
	):
		assert phrase not in text

	assert "Advanced: Prepare Purchase Receipt" in text
	assert "customerFacingCopy(blocker.label" in text
	assert "customerFacingCopy(preview.workflow_readiness?.message" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text


def test_purchase_return_review_hides_platform_implementation_copy():
	text = _read("public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue")

	for phrase in (
		"bypass ERPNext stock controls",
		"controlled by Frappe Workflow",
		"canonical ERPNext return draft",
		"permitted by Frappe",
		"ERPNext's canonical return document",
		"Advanced: Prepare in ERPNext",
		"submitted through Frappe Workflow",
		"Submit this ERPNext",
		"advanced ERPNext return draft",
	):
		assert phrase not in text

	assert "Advanced: Prepare Purchase Return" in text
	assert "Advanced: Prepare Debit Note" in text
	assert "customerFacingCopy(blocker.label" in text
	assert "customerFacingCopy(review.workflow_readiness?.message" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
