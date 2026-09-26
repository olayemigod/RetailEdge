from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_sales_invoice_completion.py"
DIALOG = ROOT / "public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue"
SELLING = ROOT / "public/js/professional_selling/ProfessionalSelling.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
PROFESSIONAL_INVOICE = ROOT / "professional_sales_invoice.py"
GUIDED_INVOICE = ROOT / "guided_sales_invoice.py"
CONTRACT = ROOT.parent / "docs/rir2g1d_standard_sales_invoice_completion.md"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_service_is_sales_invoice_only():
	source = _read(SERVICE)
	assert 'SALES_INVOICE_DOCTYPE = "Sales Invoice"' in source
	assert 'DELIVERY_NOTE_DOCTYPE = "Delivery Note"' in source
	assert 'SALES_ORDER_DOCTYPE = "Sales Order"' in source
	assert "SUPPORTED_DOCTYPES" not in source


def test_preview_is_persistence_free_and_erpnext_authoritative():
	source = _read(SERVICE)
	start = source.index("def get_standard_sales_invoice_completion_preview")
	end = source.index('@frappe.whitelist(methods=["POST"])', start)
	preview = source[start:end]
	for contract in (
		"_get_sales_invoice",
		"_validate_invoice_context",
		"_standard_invoice_blockers",
		"_completion_source_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		'"persistence": "none"',
		'"source_of_truth": "ERPNext"',
	):
		assert contract in source
	for forbidden in (
		".save()",
		".insert()",
		".submit()",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
	):
		assert forbidden not in preview


def test_advanced_accounting_shapes_fail_closed():
	source = _read(SERVICE)
	for contract in (
		"is_return",
		"return_against",
		"amended_from",
		"is_pos",
		"is_consolidated",
		"is_internal_customer",
		"represents_company",
		"write_off_amount",
		"write_off_outstanding_amount_automatically",
		"advances",
		"allocate_advances_automatically",
		"Advanced ERPNext",
	):
		assert contract in source


def test_accounting_only_invoice_does_not_require_warehouse():
	source = _read(SERVICE)
	assert 'if not cint(doc.get("update_stock")):' in source
	assert '"mode": "accounting_only"' in source


def test_update_stock_invoice_revalidates_stock_context_and_blocks_advanced_stock():
	source = _read(SERVICE)
	for contract in (
		'cint(doc.get("update_stock"))',
		'row.get("warehouse")',
		'_assert_read("Warehouse", warehouse)',
		'frappe.db.get_value("Warehouse", warehouse, "company")',
		"resolve_branch_warehouse_selection",
		"serial_no",
		"batch_no",
		"serial_and_batch_bundle",
		"packed_items",
		"multiple operational Branches",
	):
		assert contract in source


def test_delivery_linked_invoice_cannot_double_post_stock():
	source = _read(SERVICE)
	assert 'source_type == DELIVERY_NOTE_DOCTYPE and cint(doc.get("update_stock"))' in source
	assert "already records fulfilment stock movement" in source


def test_linked_sources_are_submitted_same_company_customer_and_branch():
	source = _read(SERVICE)
	for contract in (
		'"delivery_note"',
		'"sales_order"',
		"source.docstatus != 1",
		"source_company != company",
		"source_customer != customer",
		"_validate_stored_operational_branch",
		"source_branch != invoice_branch",
	):
		assert contract in source



def test_sales_invoice_item_access_is_revalidated_in_preview_edit_submit_and_workflow():
	source = _read(SERVICE)
	assert "def _validate_sales_item_access(doc)" in source
	assert '_assert_read("Item", item_code)' in source
	for function_name in (
		"def _build_preview",
		"def update_standard_sales_invoice_draft",
		"def submit_standard_sales_invoice",
		"def apply_standard_sales_invoice_workflow_action",
	):
		start = source.index(function_name)
		end = source.find("\ndef ", start + len(function_name))
		segment = source[start:end if end >= 0 else len(source)]
		assert "_validate_sales_item_access(doc)" in segment


def test_direct_submit_locks_stale_checks_revalidates_then_native_submits():
	source = _read(SERVICE)
	start = source.index("def submit_standard_sales_invoice")
	end = source.index('@frappe.whitelist(methods=["POST"])', start + 10)
	method = source[start:end]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"_validate_invoice_context",
		"_standard_invoice_blockers",
		"_completion_source_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		'_clean(workflow_readiness.get("source")) == "frappe"',
		'frappe.has_permission(SALES_INVOICE_DOCTYPE, "submit", doc=doc)',
		"doc.submit()",
	):
		assert contract in method
	for forbidden in (
		".docstatus =",
		".workflow_state =",
		"frappe.db.commit",
		"ignore_permissions=True",
	):
		assert forbidden not in method


def test_workflow_action_uses_f3f27_authority():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_sales_invoice_workflow_action"):]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"expected_workflow_state",
		"_validate_invoice_context",
		"_validate_source_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		"apply_document_workflow_action(",
		"expected_modified=expected_modified",
		"expected_state=str(expected_workflow_state or",
	):
		assert contract in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_backend_never_writes_gl_stock_or_outstanding_truth_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		"frappe.db.set_value",
		"outstanding_amount =",
		"update_stock_ledger",
	):
		assert forbidden not in source


def test_completion_dialog_uses_only_server_authoritative_actions():
	source = _read(DIALOG)
	for contract in (
		"get_standard_sales_invoice_completion_preview",
		"submit_standard_sales_invoice",
		"apply_standard_sales_invoice_workflow_action",
		"workflow_readiness?.available_actions",
		"expected_modified",
		"expected_workflow_state",
		"Print",
		"PDF",
		"get_professional_selling_record_actions",
		"completedResult.next_actions",
		'emitNextAction(action)',
	):
		assert contract in source
	for forbidden in (".workflow_state =", ".docstatus =", ".status ="):
		assert forbidden not in source


def test_draft_dates_can_be_corrected_without_weakening_erpnext_validation():
	service = _read(SERVICE)
	dialog = _read(DIALOG)
	for contract in (
		"def update_standard_sales_invoice_dates(",
		"expected_modified",
		'frappe.has_permission(SALES_INVOICE_DOCTYPE, "write", doc=doc)',
		"getdate(due_text) if due_text else None",
		"due_value < posting_value",
		"Due Date cannot be before Posting Date.",
		'doc.set("posting_date", posting_value)',
		'doc.set("due_date", due_value)',
		"def _sync_manual_due_date_with_payment_schedule",
		'len(schedule) == 1 and not _clean(doc.get("payment_terms_template"))',
		"schedule[0].due_date = due_value",
		"Due Date is controlled by this invoice's Payment Terms schedule.",
		"def _assert_saved_invoice_dates",
		"doc.save()",
		"doc.reload()",
	):
		assert contract in service
	for contract in (
		"update_standard_sales_invoice_draft",
		'Save Draft Changes',
		'<EdgeInput',
		'id="invoice-posting-date"',
		'id="invoice-due-date"',
		'id="invoice-po-number"',
		'id="invoice-remarks"',
		'type="date"',
		':min="draftPostingDate || undefined"',
		"draftValid()",
		"draftItems",
		'expected_modified: this.preview.modified',
		'}, "POST");',
	):
		assert contract in dialog
	assert '<input id="invoice-posting-date"' not in dialog
	assert '<input id="invoice-due-date"' not in dialog


def test_tabbed_sales_invoice_exposes_output_and_draft_edit_paths():
	source = _read(SELLING)
	assert "window.retailedgeDocumentOutputTarget" in source
	assert 'frappe.set_route("document-output-sharing")' in source
	assert "openSalesInvoiceCompletion(" in source
	assert 'row.is_return ? "sales_return" : "standard"' in source


def test_professional_selling_opens_governed_completion_for_invoices_and_returns():
	source = _read(SELLING)
	assert 'import StandardSalesInvoiceCompletionDialog from "./StandardSalesInvoiceCompletionDialog.vue"' in source
	assert "handleSalesInvoiceSaved(result)" in source
	assert 'result?.is_return ? "sales_return" : "standard"' in source
	assert ':sourceMode="salesInvoiceCompletionSourceMode"' in source
	assert ':showNextActions="true"' in source
	assert "create-return-credit-note" in source
	assert "create_sales_return_credit_note_draft" in source




def test_sales_return_completion_is_explicit_canonical_and_review_only():
	service = _read(SERVICE)
	dialog = _read(DIALOG)
	for marker in (
		'SOURCE_MODE_SALES_RETURN = "sales_return"',
		"def _validate_sales_return_context(",
		"erpnext_make_sales_return(source.name)",
		"Standard Sales Return completion requires negative return quantities",
		"canonical remaining return quantities",
		'if source_mode == SOURCE_MODE_SALES_RETURN:',
		'Sales Return quantities remain owned by ERPNext canonical return mapping.',
		'"is_return": bool(cint(doc.get("is_return")))',
		'"return_against": _clean(doc.get("return_against"))',
	):
		assert marker in service
	assert "Return / Credit Note completion requires the governed Sales Return workflow." in service
	assert "Return / Credit Note dates remain owned by the governed Sales Return workflow." in service
	for marker in (
		'sourceMode: { type: String, default: "standard" }',
		'source_mode: this.sourceMode || "standard"',
		"Submit Return / Credit Note",
	):
		assert marker in dialog


def test_bounded_invoice_draft_editor_preserves_identity_and_allows_safe_new_items():
	service = _read(SERVICE)
	dialog = _read(DIALOG)
	helper = _read(ROOT / "professional_draft_items.py")
	for contract in (
		"def update_standard_sales_invoice_draft(",
		"update_draft_items(",
		'"editable_items": editable_items(doc)',
		"doc.save()",
	):
		assert contract in service
	for forbidden in (
		'doc.set("company"',
		'doc.set("customer"',
		'doc.set("branch"',
		'doc.set("update_stock"',
	):
		assert forbidden not in service[
			service.index("def update_standard_sales_invoice_draft("):
			service.index("def update_standard_sales_invoice_dates(")
		]
	for contract in (
		'doc.append("items"',
		"Existing item identity cannot be replaced here.",
		"Source-linked item",
		"resolve_sales_item_pricing",
		'pricing.get("source") == "pos_profile"',
		'not pricing.get("allow_rate_change", True)',
		"_validate_warehouse_branch",
	):
		assert contract in helper
	for contract in (
		"Edit draft before completion",
		"Customer PO / Reference",
		"Selling Price List",
		"addDraftItem",
		"removeDraftItem",
		"refreshDraftItemPricing",
		"Source-linked items stay attached",
		"busy || !canOverrideRate",
		"Stock Location",
		"ERPNext recalculates taxes, totals",
	):
		assert contract in dialog
	assert "Additional Items" not in dialog
	assert "EdgeChildTable" not in dialog
	assert "ERPNext posting authority" not in dialog




def test_edit_preview_resolves_price_list_governance_and_default_stock_location():
	service = _read(SERVICE)
	for contract in (
		"resolve_price_list_context",
		'"selling_price_list": selling_price_list',
		'"pricing": {',
		'"allow_rate_change": bool(pricing.get("allow_rate_change", True))',
		'"default_warehouse": default_warehouse',
	):
		assert contract in service


def test_invoice_completion_requires_saving_dirty_editor_before_submit_or_workflow():
	dialog = _read(DIALOG)
	for contract in (
		':disabled="busy || draftDirty"',
		':disabled="busy || draftDirty || !preview?.workflow_eligible"',
		'if (!this.preview?.can_submit || this.busy || this.draftDirty) return;',
		'if (!action || !this.preview?.workflow_eligible || this.busy || this.draftDirty) return;',
		'Discard unsaved Sales Invoice draft changes?',
		'this.preview?.can_edit && !this.completedResult && this.draftDirty',
	):
		assert contract in dialog


def test_invoice_completion_print_pdf_and_post_submit_actions_are_compact():
	dialog = _read(DIALOG)
	for contract in (
		">Print</button>",
		">PDF</button>",
		"get_professional_selling_record_actions",
		"completedResult.next_actions",
		"Print & Send",
		'this.$emit("next-action"',
		"completedResult",
	):
		assert contract in dialog
	assert "Advanced: Open in ERPNext" not in dialog


def test_business_hub_simple_invoice_opens_same_completion_review():
	source = _read(HUB)
	assert 'import StandardSalesInvoiceCompletionDialog from "../professional_selling/StandardSalesInvoiceCompletionDialog.vue"' in source
	assert "handleSimpleSalesInvoiceSaved(result)" in source
	assert 'this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: result.name })' in source
	assert "salesInvoiceCompletionOpen" in source
	assert "salesInvoiceCompletionDocument" in source


def test_existing_invoice_creation_paths_remain_draft_only():
	for path in (PROFESSIONAL_INVOICE, GUIDED_INVOICE):
		source = _read(path)
		assert "doc.submit()" not in source
	assert "target.insert()" in _read(PROFESSIONAL_INVOICE)
	assert "doc.insert()" in _read(GUIDED_INVOICE)


def test_contract_preserves_payment_and_return_boundaries():
	source = _read(CONTRACT)
	assert "Return / Credit Note completion" in source
	assert "Payment Entry creation/collection" in source
	assert "Payment Reconciliation" in source
