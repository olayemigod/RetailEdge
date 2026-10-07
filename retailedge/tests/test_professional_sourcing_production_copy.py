from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def _assert_no_platform_copy(text: str, phrases: tuple[str, ...]) -> None:
	for phrase in phrases:
		assert phrase not in text


def test_rfq_preview_uses_business_facing_copy_and_sanitized_errors():
	text = _read("public/js/professional_purchasing/ProfessionalRfqPreviewOverlay.vue")

	_assert_no_platform_copy(
		text,
		(
			"Preview ERPNext's sourcing mapping",
			"submitted in ERPNext",
			"ERPNext RFQ",
			"submitted ERPNext Request for Quotation",
			"your ERPNext role",
			"Advanced: Prepare Draft in ERPNext",
			"ERPNext could not submit this Request for Quotation",
		),
	)
	assert "Advanced: Prepare RFQ" in text
	assert "Request for Quotation {{ submitted.name }} submitted." in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert "customerFacingCopy(message, fallback)" in text


def test_supplier_quotation_history_overlay_hides_platform_names():
	text = _read("public/js/professional_purchasing/ProfessionalSupplierQuotationHistoryOverlay.vue")

	_assert_no_platform_copy(
		text,
		(
			"Advanced: Open in ERPNext",
			"Advanced: Supplier Quotations in ERPNext",
		),
	)
	assert "Advanced: Open Supplier Quotation" in text
	assert "Advanced: Supplier Quotations" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text


def test_rfq_history_page_uses_business_advanced_action_and_sanitized_errors():
	text = _read("public/js/professional_purchasing/RfqHistoryPage.vue")

	assert "Advanced: ERPNext" not in text
	assert "Advanced: Open RFQ" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert "customerFacingCopy(message,fallback)" in text


def test_supplier_quotation_history_page_uses_business_advanced_action_and_sanitized_errors():
	text = _read("public/js/professional_purchasing/SupplierQuotationHistoryPage.vue")

	assert "Advanced: ERPNext" not in text
	assert "Advanced: Open Supplier Quotation" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert "customerFacingCopy(message,fallback)" in text


def test_supplier_quotation_purchase_order_preview_hides_mapper_implementation_copy():
	text = _read("public/js/professional_purchasing/ProfessionalSupplierQuotationPurchaseOrderOverlay.vue")

	_assert_no_platform_copy(
		text,
		(
			"Review ERPNext's Supplier Quotation mapping",
			"ERPNext mapping preview passed",
			"ERPNext's standard mapper",
		),
	)
	assert "Purchase Order preview passed." in text
	assert "using standard purchasing rules" in text
	assert "window.retailedge?.userErrorMessage?.(error" in text
	assert "customerFacingCopy(message, fallback)" in text
