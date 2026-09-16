from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def test_all_four_draft_selling_documents_support_safe_edit_and_item_additions():
	helper = read("professional_draft_items.py")
	selling_service = read("standard_selling_completion.py")
	delivery_service = read("standard_delivery_completion.py")
	invoice_service = read("standard_sales_invoice_completion.py")
	selling_dialog = read("public/js/professional_selling/StandardSellingCompletionDialog.vue")
	delivery_dialog = read("public/js/professional_selling/StandardDeliveryCompletionDialog.vue")
	invoice_dialog = read("public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue")

	for contract in (
		'doc.append("items"',
		"Existing item identity cannot be replaced here.",
		"Source-linked item",
		"resolve_sales_item_pricing",
		"_validate_warehouse_branch",
		"MAX_DRAFT_ITEMS",
	):
		assert contract in helper

	assert "def update_standard_selling_draft(" in selling_service
	assert "SUPPORTED_DOCTYPES = {\"Quotation\", \"Sales Order\"}" in selling_service
	assert "update_draft_items(" in selling_service
	assert "def update_standard_delivery_draft(" in delivery_service
	assert "update_draft_items(" in delivery_service
	assert "def update_standard_sales_invoice_draft(" in invoice_service
	assert "update_draft_items(" in invoice_service

	for dialog in (selling_dialog, delivery_dialog, invoice_dialog):
		assert "Edit draft before completion" in dialog
		assert "Additional Items" in dialog
		assert "EdgeChildTable" in dialog
		assert "Save Draft Changes" in dialog


def test_submitted_rows_have_view_and_print_send_while_drafts_keep_edit_complete():
	records = read("public/js/professional_selling/ProfessionalSellingRecords.vue")
	workspace = read("public/js/professional_selling/ProfessionalSelling.vue")
	output = read("public/js/document_output_sharing/DocumentOutputSharing.vue")

	for contract in (
		'return this.canComplete(row) ? "Edit / Complete" : "View";',
		'label: "Print & Send"',
		'action: "view"',
		"record-more--fly-up",
		"bottom:calc(100% + .25rem)",
	):
		assert contract in records
	assert 'if (action === "view") { this.openDocumentOutput(document, row, "view"); return; }' in workspace
	assert 'if (action === "output") { this.openDocumentOutput(document, row, "share"); return; }' in workspace
	assert 'outputMode === "view"' in output
	assert 'outputMode !== \'view\'' in output


def test_customer_facing_professional_selling_errors_use_shared_sanitizer():
	for path in (
		"public/js/professional_selling/ProfessionalSelling.vue",
		"public/js/professional_selling/ProfessionalSellingRecords.vue",
		"public/js/professional_selling/StandardSellingCompletionDialog.vue",
		"public/js/professional_selling/StandardDeliveryCompletionDialog.vue",
		"public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue",
		"public/js/retailedge_business_hub/SimplePaymentDialog.vue",
		"public/js/retailedge_business_hub/guidedEntryUtils.js",
	):
		source = read(path)
		assert "userErrorMessage" in source


def test_payment_handoff_prefers_document_and_operating_branch():
	backend = read("guided_payment.py")
	selling = read("public/js/professional_selling/ProfessionalSelling.vue")
	list_service = read("professional_selling.py")

	assert "get_operating_context" in backend
	assert 'operating.get("branch")' in backend
	assert 'row.branch || row.retailedge_branch' in selling
	assert "branch_field = get_first_existing_field(doctype, BRANCH_FIELD_CANDIDATES)" in list_service
	assert 'payload["branch"]' in list_service


def test_direct_quote_invoice_and_invoice_delivery_are_idempotent():
	invoice = read("professional_sales_invoice.py")
	delivery = read("professional_delivery.py")

	for contract in (
		"def _lock_quotation_for_direct_invoice",
		"FOR UPDATE",
		"get_quotation_conversion",
		'"existing": True',
		'"requires_amend"',
	):
		assert contract in invoice
	for contract in (
		"def _lock_sales_invoice",
		"def _existing_draft_delivery_for_invoice",
		"item.against_sales_invoice = %s",
		"dn.docstatus = 0",
		"if existing:",
	):
		assert contract in delivery


def test_pedge_print_formats_are_namespaced_and_migrated():
	formats = read("professional_print_formats.py")
	patches = read("patches.txt")
	output = read("document_output.py")

	for name in (
		"PEdge Professional Quotation",
		"PEdge Professional Sales Order",
		"PEdge Professional Delivery Note",
		"PEdge Professional Sales Invoice",
		"PEdge Invoice Classic",
		"PEdge Sales Receipt 80mm",
		"PEdge POS Receipt 80mm",
	):
		assert name in formats
	for legacy in (
		'"Professional Quotation"',
		'"Professional Sales Invoice"',
		'"Invoice Classic"',
		'"Sales Receipt 80mm"',
	):
		assert legacy in formats
	assert "retailedge.patches.install_pedge_print_formats_v5" in patches
	assert 'return "PEdge POS Receipt 80mm"' in output
