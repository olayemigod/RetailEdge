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
		"_validate_source_context",
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
		"resolve_branch_from_warehouse",
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
		"_validate_source_context",
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
		"Advanced: Open in ERPNext",
	):
		assert contract in source
	for forbidden in (".workflow_state =", ".docstatus =", ".status ="):
		assert forbidden not in source


def test_professional_selling_opens_invoice_completion_except_returns():
	source = _read(SELLING)
	assert 'import StandardSalesInvoiceCompletionDialog from "./StandardSalesInvoiceCompletionDialog.vue"' in source
	assert "handleSalesInvoiceSaved(result)" in source
	assert "!result?.is_return" in source
	assert 'this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: result.name })' in source
	assert "canReviewSalesInvoiceCompletion(row)" in source
	assert 'this.recentDocument?.key === "sales-invoice"' in source


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
