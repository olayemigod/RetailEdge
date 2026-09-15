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
		".record-actions { display:grid; grid-template-columns:minmax(9.5rem,1fr) 7rem;",
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
		'"View / Print / Send"',
		'"Advanced: Open in ERPNext"',
		'{{ loadingMore ? "Loading..." : "Load more" }}',
		"runPrimaryAction(row)",
		'this.$emit("action", { action: "output", document: this.activeDocument, row });',
	):
		assert contract in records

	for contract in (
		"openDocumentOutput(document, row)",
		"window.retailedgeDocumentOutputTarget = { document: document.key, name: row.name };",
		'frappe.set_route("document-output-sharing");',
	):
		assert contract in workspace


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
