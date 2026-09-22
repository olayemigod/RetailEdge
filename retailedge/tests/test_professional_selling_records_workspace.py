from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
BACKEND = APP_ROOT / "professional_selling.py"
WORKSPACE = APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSelling.vue"
RECORDS = APP_ROOT / "public" / "js" / "professional_selling" / "ProfessionalSellingRecords.vue"


def read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_professional_selling_uses_one_four_tab_records_workspace():
	workspace = read(WORKSPACE)
	records = read(RECORDS)

	for contract in (
		"ProfessionalSellingRecords",
		'ref="sellingRecords"',
		':documents="documents"',
		'@action="handleRecordAction"',
		"openRecords(document)",
		"handleRecordAction(payload)",
	):
		assert contract in workspace

	for label in ("Quotation", "Sales Order", "Delivery Note", "Sales Invoice"):
		assert label in records or label in read(BACKEND)

	assert "Latest records" not in workspace
	assert "recent-row" not in workspace


def test_records_table_has_fixed_columns_and_single_actions_slot():
	source = read(RECORDS)

	for contract in (
		"<th scope=\"col\">Document</th>",
		"<th scope=\"col\">Customer</th>",
		"<th scope=\"col\">Date</th>",
		"<th scope=\"col\">Status</th>",
		'class="amount-column">Total</th>',
		'class="actions-column">Actions</th>',
		"table-layout:fixed;",
		".actions-column { width:20rem; }",
		".record-actions { display:grid; grid-template-columns:minmax(8.5rem,1fr) 9.25rem;",
		".record-primary-action { width:100%; white-space:nowrap; font-size:.76rem;",
		".edge-dropdown__trigger.record-more + .edge-dropdown__menu",
		"width:min(15rem,calc(100vw - 2rem));",
		"white-space:normal;",
	):
		assert contract in source

	assert "recent-completion" not in source
	assert "recent-advanced" not in source


def test_records_filters_are_edgesuite_owned_and_server_applied():
	frontend = read(RECORDS)
	backend = read(BACKEND)

	for contract in (
		"<EdgeInput",
		"<EdgeDropdown",
		'label="Search"',
		'label="Status"',
		'label="From Date"',
		'label="To Date"',
		'LIST_METHOD = "retailedge.professional_selling.get_professional_selling_list"',
		"scheduleReload()",
		"page_length: 20",
	):
		assert contract in frontend

	for contract in (
		"def get_professional_selling_list(",
		"_operating_document_filters(doctype, company=company, branch=branch)",
		"_selling_list_status_filter(meta, status, filters)",
		'or_filters.append(["name", "like", like])',
		'filters[date_field] = ["between", [getdate(from_text), to_value]]',
		"limit_start=start",
		"limit_page_length=page_length + 1",
		'"has_more": has_more',
		'"next_start": start + len(rows)',
	):
		assert contract in backend


def test_row_actions_are_stable_and_output_supports_all_four_document_types():
	records = read(RECORDS)
	workspace = read(WORKSPACE)

	for contract in (
		'placeholder="More"',
		"moreActions(row)",
		'"Print & Send"',
		'"Advanced: Open in ERPNext"',
		'{{ loadingMore ? "Loading..." : "Load more" }}',
		"runPrimaryAction(row)",
		'this.$emit("action", { action: "view", document: this.activeDocument, row });',
		'"Edit / Complete"',
		'"View"',
		"shouldFlyUp(row, index)",
		'"record-more--fly-up"',
		"prepareDropdownDirection($event, row, index)",
		"window.innerHeight - rect.bottom",
		"estimatedMenuHeight",
		"bottom:calc(100% + .25rem);",
	):
		assert contract in records

	assert 'description: action.description' not in records
	assert 'description: "Preview, download PDF, email or prepare WhatsApp sharing."' not in records
	assert 'description: "Open the full ERPNext document for advanced work."' not in records

	for contract in (
		'openDocumentOutput(document, row, mode = "share")',
		"window.retailedgeDocumentOutputTarget = { document: document.key, name: row.name, mode };",
		'if (action === "view") { this.openDocumentOutput(document, row, "view"); return; }',
		'if (action === "output") { this.openDocumentOutput(document, row, "share"); return; }',
		'frappe.set_route("document-output-sharing");',
	):
		assert contract in workspace


def test_submitted_rows_receive_server_authoritative_conversion_and_payment_actions():
	backend = read(BACKEND)
	records = read(RECORDS)
	workspace = read(WORKSPACE)

	for contract in (
		"def _selling_record_actions(",
		'"create-sales-order"',
		'"create-delivery-note"',
		'"create-sales-invoice"',
		'"create-return-credit-note"',
		'"make-payment"',
		'flt(row.get("per_delivered")) < 99.999',
		'flt(row.get("per_billed")) < 99.999',
		'not cint(row.get("update_stock"))',
		'flt(row.get("outstanding_amount")) > 0.005',
		'payload["actions"] = _selling_record_actions',
	):
		assert contract in backend

	assert "Array.isArray(row?.actions)" in records
	for contract in (
		'if (action === "make-payment")',
		'["create-sales-order", "create-delivery-note", "create-sales-invoice", "create-return-credit-note"].includes(action)',
		"runConversionAction(action, document, row)",
		"openCustomerPayment(document, row)",
		"create_sales_order_from_quotation",
		"create_sales_invoice_from_quotation",
		"create_sales_invoice_from_sales_order",
		"create_sales_invoice_from_delivery_note",
		"create_delivery_note_from_sales_order",
		"create_delivery_note_from_sales_invoice",
		"create_sales_return_credit_note_draft",
	):
		assert contract in workspace



def test_delivery_note_invoice_hint_is_removed_for_invoice_sourced_or_direct_order_billed_delivery():
	backend = read(BACKEND)
	for contract in (
		"def _delivery_has_direct_sales_order_billing",
		"si.docstatus = 1",
		"COALESCE(si.is_return, 0) = 0",
		"COALESCE(item.delivery_note, '') = ''",
		"direct_order_billing = _delivery_has_direct_sales_order_billing(delivery)",
		"if invoice_sourced or direct_order_billing:",
		'action.get("value") != "create-sales-invoice"',
	):
		assert contract in backend


def test_completion_next_actions_preserve_authoritative_company_and_branch_context():
	workspace = read(WORKSPACE)
	for marker in (
		'company: payload.company || ""',
		'branch: payload.branch || ""',
		'company: row.company || this.sellingContext?.operating?.company',
		'branch: row.branch || row.retailedge_branch || this.sellingContext?.operating?.branch',
	):
		assert marker in workspace

	for dialog in (
		APP_ROOT / "public/js/professional_selling/StandardSellingCompletionDialog.vue",
		APP_ROOT / "public/js/professional_selling/StandardDeliveryCompletionDialog.vue",
		APP_ROOT / "public/js/professional_selling/StandardSalesInvoiceCompletionDialog.vue",
	):
		source = read(dialog)
		assert 'company: this.completedResult.company || this.preview?.company || ""' in source
		assert 'branch: this.completedResult.branch || this.preview?.branch || ""' in source


def test_professional_selling_keeps_submitted_completion_open_for_next_workflow():
	workspace = read(WORKSPACE)
	for contract in (
		'@next-action="handleCompletionNextAction"',
		"handleCompletionNextAction(payload)",
		'paymentIntent = document.key === "sales-order" ? "receive-sales-order-payment" : "receive-customer-payment"',
		"<SimplePaymentDialog",
		':showNextActions="true"',
	):
		assert contract in workspace

	completed = workspace[workspace.index("handleCompletionCompleted()"):workspace.index("openDeliveryCompletion", workspace.index("handleCompletionCompleted()"))]
	assert "closeStandardCompletion()" not in completed

def test_draft_completion_actions_remain_document_specific_and_accounting_safe():
	records = read(RECORDS)
	workspace = read(WORKSPACE)

	assert 'return Number(row?.docstatus || 0) === 0;' in records
	for contract in (
		'if (document.key === "quotation")',
		'this.openStandardCompletion({ doctype: "Quotation", name: row.name });',
		'if (document.key === "sales-order")',
		'this.openStandardCompletion({ doctype: "Sales Order", name: row.name });',
		'if (document.key === "delivery-note")',
		'this.openDeliveryCompletion({ doctype: "Delivery Note", name: row.name });',
		'if (document.key === "sales-invoice")',
		'this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: row.name });',
	):
		assert contract in workspace


def test_sales_return_next_action_requires_professional_selling_page_access():
	source = (APP_ROOT / "professional_selling.py").read_text(encoding="utf-8")
	assert 'def _can_open_page(page_name: str) -> bool:' in source
	assert 'frappe.get_doc("Page", page_name).is_permitted()' in source
	assert '_can_open_page("professional-selling")' in source
	return_index = source.index('actions.append({"value": "create-return-credit-note"')
	gate_index = source.rfind('_can_open_page("professional-selling")', 0, return_index)
	assert gate_index >= 0

