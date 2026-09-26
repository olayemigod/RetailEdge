from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
	return (ROOT / path).read_text(encoding="utf-8")


def test_all_four_draft_completion_surfaces_allow_editing_and_new_items():
	contracts = (
		("public/js/professional_selling/StandardSellingCompletionDialog.vue", "Additional Items"),
		("public/js/professional_selling/StandardDeliveryCompletionDialog.vue", "Additional Items"),
		("public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue", "Additional Items"),
	)
	for path, label in contracts:
		source = read(path)
		assert "preview.can_edit" in source
		assert "Save Draft Changes" in source
		assert "EdgeChildTable" in source
		assert label in source
		assert "Add Item" in source


def test_professional_invoice_update_stock_choice_is_separate_from_make_a_sale_policy():
	guided = read("guided_sales_invoice.py")
	professional = read("professional_sales_invoice.py")
	dialog = read("public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue")

	assert "def _create_simple_sales_invoice_draft(" in guided
	assert "if allow_update_stock_edit is None:" in guided
	assert "allow_guided_sales_update_stock_edit" in guided
	assert "return _create_simple_sales_invoice_draft(values)" in guided
	assert "_create_simple_sales_invoice_draft(values, allow_update_stock_edit=True)" in professional
	assert 'v-model="values.update_stock"' in dialog
	assert ">Update Stock</strong>" in dialog


def test_managed_print_formats_have_a_distinct_pedge_prefix_and_retire_legacy_aliases():
	source = read("professional_print_formats.py")
	for name in (
		"PEdge Professional Quotation",
		"PEdge Professional Sales Order",
		"PEdge Professional Delivery Note",
		"PEdge Professional Sales Invoice",
		"PEdge Invoice Classic",
		"PEdge Invoice Modern",
		"PEdge Invoice Compact",
		"PEdge Invoice Minimal",
		"PEdge Invoice Executive",
	):
		assert name in source
	assert "LEGACY_PRINT_FORMAT_ALIASES" in source
	assert "legacy_doc.disabled = 1" in source


def test_quotation_to_invoice_duplicate_reopens_existing_document_instead_of_throwing_traceback():
	backend = read("professional_sales_invoice.py")
	frontend = read("public/js/professional_selling/ProfessionalSelling.vue")
	assert "existing_conversion = get_quotation_conversion(source.name)" in backend
	assert '"existing": True' in backend
	assert '"requires_amend": cint(existing_doc.docstatus) == 2' in backend
	assert "if (result.existing)" in frontend
	assert "already exists. Opening it instead." in frontend


def test_sales_order_mapping_populates_required_delivery_dates_before_insert():
	source = read("professional_sales_order.py")
	assert 'delivery_date = getdate(target.get("delivery_date") or source.get("valid_till") or nowdate())' in source
	assert "target.delivery_date = delivery_date" in source
	assert 'item.meta.has_field("delivery_date")' in source
	assert "item.delivery_date = delivery_date" in source
	assert source.index("target.delivery_date = delivery_date") < source.index("target.insert()")


def test_submitted_rows_use_view_while_drafts_use_edit_complete_and_output_is_print_send():
	source = read("public/js/professional_selling/ProfessionalSellingRecords.vue")
	assert 'return this.canComplete(row) ? "Edit / Complete" : "View";' in source
	assert 'label: "Print & Send"' in source
	assert 'action: "view"' in source
	assert 'action: "complete"' in source


def test_direct_invoice_to_delivery_is_idempotent_across_draft_and_submitted_states():
	source = read("professional_delivery.py")
	assert "def _existing_delivery_for_invoice(" in source
	assert "WHERE item.against_sales_invoice = %s" in source
	assert "dn.docstatus = 0" not in source
	assert "_lock_sales_invoice(source.name)" in source
	assert "existing = _existing_delivery_for_invoice(source.name)" in source
	assert '"existing": existing' in source
	assert "use Amend instead of creating another Delivery Note" in source


def test_payment_prefill_carries_operating_or_document_branch():
	workspace = read("public/js/professional_selling/ProfessionalSelling.vue")
	payment = read("public/js/retailedge_business_hub/SimplePaymentDialog.vue")
	assert "row.branch || row.retailedge_branch" in workspace
	assert "this.sellingContext?.operating?.branch || this.branchName" in workspace
	assert "if (branch) this.values.branch = branch" in payment
	assert "branch: this.values.branch" in payment


def test_more_actions_can_fly_up_when_viewport_space_is_tight():
	source = read("public/js/professional_selling/ProfessionalSellingRecords.vue")
	assert "prepareDropdownDirection" in source
	assert "spaceBelow < estimatedMenuHeight" in source
	assert "record-more--fly-up" in source
	assert "bottom:calc(100% + .25rem)" in source
