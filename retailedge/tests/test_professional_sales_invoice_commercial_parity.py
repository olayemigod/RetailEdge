from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIALOG = ROOT / "public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue"


def source() -> str:
	return DIALOG.read_text(encoding="utf-8")


def test_new_professional_invoice_reuses_shared_commercial_preview_and_controls():
	text = source()

	for contract in (
		'import SalesCommercialSummary from "../selling/SalesCommercialSummary.vue"',
		'import SalesCommercialTermsControls from "../selling/SalesCommercialTermsControls.vue"',
		'const COMMERCIAL_PREVIEW_METHOD = "retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview"',
		"<SalesCommercialTermsControls",
		"<SalesCommercialSummary",
		"commercialTermCapabilities()",
		"commercialPreviewSignature()",
		"commercialPreviewBlocked()",
		"previewAppliedSignature",
		"const token = ++this.previewToken",
		"signature !== this.commercialPreviewSignature",
		'callMethod(COMMERCIAL_PREVIEW_METHOD, { values: this.values }, "POST")',
	):
		assert contract in text


def test_new_professional_invoice_fails_closed_until_current_preview_is_ready():
	text = source()

	assert '(mode === \'new\' && commercialPreviewBlocked)' in text
	assert 'if (this.mode === "new" && this.commercialPreviewBlocked)' in text
	assert 'this.saveError = this.previewError || "Wait for the current invoice total to finish updating before saving.";' in text
	assert "this.queueCommercialPreview(0);" in text
	assert "this.previewAppliedSignature !== this.commercialPreviewSignature" in text


def test_professional_invoice_commercial_fields_stay_on_existing_guarded_sales_path():
	text = source()

	for field in (
		'coupon_code: ""',
		'tax_category: ""',
		'taxes_and_charges: ""',
		"additional_discount_percentage: 0",
		"discount_amount: 0",
		'apply_discount_on: "Grand Total"',
	):
		assert field in text

	assert "updateCommercialTerms(patch)" in text
	assert "searchCommercialTerm(fieldname, query)" in text
	assert 'this.values.tax_category = "";' in text
	assert 'this.values.taxes_and_charges = "";' in text


def test_source_conversion_and_return_paths_do_not_depend_on_new_sale_preview():
	text = source()

	for contract in (
		'if (this.mode === "quotation") { method = CREATE_FROM_QUOTATION; args = { quotation: this.sourceDocument }; }',
		'if (this.mode === "sales-order") { method = CREATE_FROM_ORDER; args = { sales_order: this.sourceDocument }; }',
		'if (this.mode === "delivery-note") { method = CREATE_FROM_DELIVERY; args = { delivery_note: this.sourceDocument }; }',
		'if (this.mode === "return") { method = CREATE_RETURN; args = { sales_invoice: this.sourceDocument }; }',
		'if (this.mode !== "new") return false;',
	):
		assert contract in text


def test_preview_display_fields_are_not_promoted_to_save_authority():
	text = source()

	for field in (
		'{ fieldname: "uom", label: "UOM", fieldtype: "Data", read_only: 1 }',
		'{ fieldname: "discount_percentage", label: "Discount %", fieldtype: "Float", read_only: 1 }',
		'{ fieldname: "amount", label: "Amount", fieldtype: "Currency", read_only: 1 }',
		"applyCommercialPreviewItems(items)",
	):
		assert field in text

	# The backend creation path still receives the governed request values rather
	# than a browser-computed invoice total or tax row payload.
	assert "let args = { values: this.values };" in text
	assert "invoice_total:" not in text
	assert "grand_total:" not in text


def test_touched_form_uses_shared_edgesuite_semantic_primitives():
	text = source()

	for component in ("EdgeInput", "EdgeCheckbox", "EdgeTextarea", "EdgeLinkField", "EdgeChildTable"):
		assert f"{component}: runtime.{component}" in text or component in {
			"EdgeLinkField",
			"EdgeChildTable",
		}
	assert '<EdgeInput\n\t\t\t\t\t:modelValue="values.posting_date"' in text
	assert 'type="date"' in text
	assert '<EdgeCheckbox' in text
	assert '<EdgeTextarea' in text
	assert '<input v-model="values.posting_date"' not in text
	assert '<textarea v-model="values.remarks"' not in text


def test_shipping_and_loyalty_finalization_are_disclosed_without_faking_preview_totals():
	text = source()

	assert "commercialFinalizationNote()" in text
	assert "The selected delivery charge is applied" in text
	assert "is not included in this live discount/tax preview" in text
	assert "Loyalty redemption is revalidated and applied when the draft is saved." in text
