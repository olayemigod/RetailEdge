from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def test_professional_selling_shell_hides_platform_implementation_copy():
	text = _read("public/js/professional_selling/ProfessionalSelling.vue")

	assert "ERPNext" not in text
	assert "Advanced: Open in ERPNext" not in text
	assert "Configured default" in text
	assert "Advanced: Open {{ document.label }}" in text
	assert "using configured pricing, taxes and an optional Shipping Rule" in text
	assert "using remaining quantities and current stock records" in text
	assert "while preserving accounting controls" in text
	assert "use advanced review when a replacement is required" in text
	assert "The requested downstream document could not be created." in text

	# Presentation copy changes must not alter native fallback or conversion ownership.
	assert "if (!this.canUseNativeDesk || !document?.doctype) return;" in text
	assert "window.open(document.native_route" in text
	assert '"create-sales-order": { method: "retailedge.professional_sales_order.create_sales_order_from_quotation"' in text
	assert '"create-delivery-note": document.key === "sales-invoice"' in text
	assert '"create-return-credit-note": { method: "retailedge.professional_sales_invoice.create_sales_return_credit_note_draft"' in text


def test_professional_delivery_dialog_uses_business_copy_and_preserves_handoff():
	text = _read("public/js/professional_selling/ProfessionalDeliveryDialog.vue")

	assert "ERPNext" not in text
	assert "native mapping" not in text
	assert "Advanced: Open Delivery Note" in text
	assert "The submitted order remains the source for delivery." in text
	assert "This workflow creates a draft only and never changes the submitted Sales Order." in text

	# Native access remains explicitly permission-gated and uses the same event contract.
	assert 'v-if="canUseNativeDesk"' in text
	assert "$emit('open-native', 'Delivery Note')" in text
	assert 'const CREATE_METHOD = "retailedge.professional_delivery.create_delivery_note_from_sales_order"' in text


def test_professional_quotation_dialog_uses_business_copy_and_preserves_handoff():
	text = _read("public/js/professional_selling/ProfessionalQuotationDialog.vue")

	assert "ERPNext" not in text
	assert "Advanced: Open in ERPNext" not in text
	assert "using governed pricing, Shipping Rules and the current Operating Context" in text
	assert "Only enabled Selling Shipping Rules for this Company are shown." in text
	assert "Delivery charges are calculated from the selected Shipping Rule when the draft is saved." in text
	assert "Advanced: Open Quotation" in text

	# Pricing, save and native handoff contracts remain unchanged.
	assert 'v-if="canUseNativeDesk"' in text
	assert "$emit('open-native', 'Quotation')" in text
	assert 'const CREATE_METHOD = "retailedge.professional_quotation.create_professional_quotation_draft"' in text
	assert 'const PRICING_METHOD = "retailedge.professional_selling.get_professional_selling_item_pricing"' in text
	assert 'const PRICE_CONTEXT_METHOD = "retailedge.guided_pricing.get_allowed_price_list_context"' in text
