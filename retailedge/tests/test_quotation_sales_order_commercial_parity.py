from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
QUOTATION = ROOT / "professional_quotation.py"
SALES_ORDER = ROOT / "professional_sales_order.py"
PREVIEW = ROOT / "sales_document_commercial_preview.py"
TERMS = ROOT / "sales_commercial_terms.py"
PROMOTION_GUARD = ROOT / "sales_commercial_promotion_guard.py"
QUOTATION_UI = ROOT / "public/js/professional_selling/ProfessionalQuotationDialog.vue"
SALES_ORDER_UI = ROOT / "public/js/professional_selling/ProfessionalSalesOrderDialog.vue"
PANEL = ROOT / "public/js/professional_selling/ProfessionalSalesCommercialPanel.vue"
LINE_EDITOR = ROOT / "public/js/selling/manualDiscountEditor.js"
CONTROLS = ROOT / "public/js/selling/SalesCommercialTermsControls.vue"
SUMMARY = ROOT / "public/js/selling/SalesCommercialSummary.vue"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_commercial_term_governance_supports_all_three_sales_documents_without_weakening_invoice_default():
	text = read(TERMS)
	for contract in (
		'SALES_INVOICE_DOCTYPE = "Sales Invoice"',
		'"Quotation"',
		'"Sales Order"',
		"SUPPORTED_SALES_COMMERCIAL_DOCTYPES",
		"document_type: str = SALES_INVOICE_DOCTYPE",
		"_assert_sales_term_search_access",
		"reference_doctype=doctype",
	):
		assert contract in text
	assert "frappe.has_permission(doctype, \"create\")" in text
	assert "frappe.has_permission(doctype, \"write\", doc=doc)" in text


def test_generic_preview_is_persistence_free_and_delegates_calculation_to_erpnext():
	text = read(PREVIEW)
	for contract in (
		"get_sales_document_commercial_preview",
		'PREVIEWABLE_DOCTYPES = {"Quotation", "Sales Order"}',
		'_prepare_preview_document(doc)',
		"resolve_price_list_context",
		"resolve_sales_item_pricing",
		"apply_manual_item_discount",
		"apply_sales_commercial_terms(doc, values)",
		"validate_manual_item_discounts_after_pricing",
		"validate_manual_document_discount_against_promotions",
		'preview["document_total"] = preview.get("invoice_total")',
	):
		assert contract in text
	for forbidden in (
		"doc.insert(",
		"doc.save(",
		"doc.submit(",
		"frappe.db.commit(",
		"ignore_permissions=True",
	):
		assert forbidden not in text


def test_shared_promotion_guard_is_document_neutral_and_cycle_free():
	text = read(PROMOTION_GUARD)
	for contract in (
		"transaction_promotion_names",
		"validate_manual_document_discount_against_promotions",
		"additional_discount_percentage",
		"discount_amount",
		"document_label",
	):
		assert contract in text
	assert "sales_commercial_preview" not in text
	assert "professional_quotation" not in text
	assert "professional_sales_order" not in text


def test_quotation_save_uses_same_commercial_helpers_before_native_draft_insert():
	text = read(QUOTATION)
	for contract in (
		"normalise_manual_item_discount",
		"apply_manual_item_discount",
		"apply_sales_commercial_terms(doc, values)",
		"validate_manual_item_discounts_after_pricing(doc, items)",
		"validate_manual_document_discount_against_promotions",
		'document_label="Quotation"',
		"sales_commercial_terms_from_doc(doc)",
		"get_sales_commercial_term_capabilities(doc)",
	):
		assert contract in text
	assert text.index("apply_sales_commercial_terms(doc, values)") < text.index("doc.insert()")
	assert "sales_commercial_preview import" not in text
	assert "doc.submit()" not in text
	assert "frappe.db.commit" not in text


def test_standalone_sales_order_uses_same_commercial_helpers_but_native_quotation_mapper_stays_separate():
	text = read(SALES_ORDER)
	for contract in (
		"apply_manual_item_discount",
		"apply_sales_commercial_terms(doc, values)",
		"validate_manual_item_discounts_after_pricing(doc, items)",
		"validate_manual_document_discount_against_promotions",
		'document_label="Sales Order"',
		"target = erpnext_make_sales_order(source.name)",
		"accepted commercial terms",
	):
		assert contract in text
	assert text.index("apply_sales_commercial_terms(doc, values)") < text.index("doc.insert()")
	assert "sales_commercial_preview import" not in text
	mapping_start = text.index("def create_sales_order_from_quotation")
	mapping_text = text[mapping_start:]
	assert "apply_sales_commercial_terms(target" not in mapping_text
	assert "resolve_sales_item_pricing(" not in mapping_text


def test_professional_quote_and_order_share_one_live_commercial_panel_and_collapsed_line_discount_editor():
	for path, label in ((QUOTATION_UI, "Quotation"), (SALES_ORDER_UI, "Sales Order")):
		text = read(path)
		assert "ProfessionalSalesCommercialPanel" in text
		assert f'documentType="{label}"' in text
		assert f'documentLabel="{label}"' in text
		assert "withManualDiscountEditorColumns" in text
		assert "normaliseManualDiscountRows" in text
		assert 'fieldname: "rate"' in text
		for field in (
			"coupon_code",
			"tax_category",
			"taxes_and_charges",
			"additional_discount_percentage",
			"discount_amount",
			"apply_discount_on",
		):
			assert field in text
		assert "commercialState.blocked" in text
		assert "EdgeInput" in text
		assert 'type="date"' in text
		assert "EdgeTextarea" in text
		assert '<input v-model="values.transaction_date"' not in text
		assert '<textarea v-model="values.terms"' not in text

	line_editor = read(LINE_EDITOR)
	assert 'label: "Discount"' in line_editor
	assert 'label: "Value"' in line_editor
	assert 'label: "Percentage"' in line_editor
	assert 'label: "Amount / unit"' in line_editor
	assert "manual_discount_percentage" in line_editor
	assert "manual_discount_amount" in line_editor


def test_shared_panel_fails_closed_on_stale_calculation_and_uses_get_for_term_searches():
	text = read(PANEL)
	for contract in (
		"COMMERCIAL_PREVIEW_METHOD",
		"COMMERCIAL_TERM_SEARCH_METHOD",
		"commercialPreviewSignature",
		"previewAppliedSignature",
		"const token = ++this.previewToken",
		"token !== this.previewToken || signature !== this.commercialPreviewSignature",
		'"POST"',
		'"GET"',
		"The selected delivery charge is applied when the draft is saved",
	):
		assert contract in text
	assert "commercialPreviewBlocked" in text


def test_shared_commercial_components_keep_invoice_default_while_supporting_document_labels():
	controls = read(CONTROLS)
	summary = read(SUMMARY)
	for text in (controls, summary):
		assert 'documentLabel: { type: String, default: "Invoice" }' in text
	assert '"No invoice discount"' in controls
	assert '"Automatic invoice promotion"' in controls
	assert '"Invoice Total"' in summary
	assert "`${this.documentLabel} Total`" in summary


def test_sales_order_submitted_quotation_mode_does_not_depend_on_new_order_preview():
	text = read(SALES_ORDER_UI)
	assert "From Submitted Quotation" in text
	assert "create_sales_order_from_quotation" in text
	assert 'this.mode === "new" && this.commercialState.blocked' in text
	assert "mode === 'quotation' && !sourceQuotation" in text
