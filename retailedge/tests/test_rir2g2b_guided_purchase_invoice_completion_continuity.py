from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_purchase_invoice_completion.py"
DIALOG = ROOT / "public/js/professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue"
HUB = ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue"
PURCHASING = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
GUIDED = ROOT / "guided_purchase_invoice.py"
HANDOFF = ROOT / "supplier_document_review.py"
CONTRACT = ROOT.parent / "docs/rir2g2b_guided_purchase_invoice_completion_continuity.md"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_service_is_purchase_invoice_only_and_preview_is_persistence_free():
	source = _read(SERVICE)
	assert 'PURCHASE_INVOICE_DOCTYPE = "Purchase Invoice"' in source
	assert 'HANDOFF_DOCTYPE = "Supplier Document Purchase Invoice Handoff"' in source
	start = source.index("def get_standard_purchase_invoice_completion_preview")
	end = source.index('@frappe.whitelist(methods=["POST"])', start)
	preview = source[start:end]
	for marker in (
		"_get_purchase_invoice",
		"_validate_invoice_context",
		"_standard_invoice_blockers",
		"_validate_source_less_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		'"persistence": "none"',
	):
		assert marker in source
	for forbidden in (".save()", ".insert()", ".submit()", "frappe.db.commit"):
		assert forbidden not in preview


def test_generic_completion_rejects_source_driven_and_supplier_document_invoices():
	source = _read(SERVICE)
	for marker in (
		"purchase_order",
		"purchase_receipt",
		"HANDOFF_DOCTYPE",
		'{"purchase_invoice": doc.name}',
		"Source-linked Purchase Invoices are owned by Professional Purchasing",
		"Supplier Document Purchase Invoice",
	):
		assert marker in source


def test_advanced_purchase_invoice_shapes_fail_closed():
	source = _read(SERVICE)
	for marker in (
		"amended_from",
		"is_return",
		"return_against",
		"is_internal_supplier",
		"represents_company",
		"inter_company_invoice_reference",
		"is_paid",
		"is_opening",
		"advances",
		"allocate_advances_automatically",
		"is_subcontracted",
		"supplied_items",
		"Advanced ERPNext",
	):
		assert marker in source


def test_company_branch_supplier_and_items_are_revalidated():
	source = _read(SERVICE)
	for marker in (
		'_assert_read("Company", company)',
		'_assert_read("Supplier", supplier)',
		"_validate_stored_operational_branch",
		"get_operating_context",
		"Purchase Invoice must contain at least one item",
	):
		assert marker in source


def test_accounting_only_does_not_require_warehouse():
	source = _read(SERVICE)
	assert 'if not cint(doc.get("update_stock")):' in source
	assert '"mode": "accounting_only"' in source
	assert "Every stock-updating Purchase Invoice item must have a Warehouse" in source


def test_update_stock_is_branch_safe_and_advanced_stock_complexity_fails_closed():
	source = _read(SERVICE)
	for marker in (
		"resolve_branch_from_warehouse",
		'_assert_read("Warehouse", warehouse)',
		"does not belong to Company",
		"multiple operational Branches",
		"serial_no",
		"batch_no",
		"serial_and_batch_bundle",
		"Serial/Batch controlled stock-updating Purchase Invoice requires Advanced ERPNext review",
	):
		assert marker in source


def test_direct_submit_locks_stale_checks_revalidates_and_calls_native_submit_only():
	source = _read(SERVICE)
	start = source.index("def submit_standard_purchase_invoice")
	end = source.index('@frappe.whitelist(methods=["POST"])', start + 10)
	method = source[start:end]
	for marker in (
		"FOR UPDATE",
		"expected_modified",
		"_validate_invoice_context",
		"_standard_invoice_blockers",
		"_validate_source_less_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		'frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "submit", doc=doc)',
		"doc.submit()",
	):
		assert marker in method
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		'frappe.new_doc("Payment Ledger Entry")',
		".docstatus =",
		".workflow_state =",
	):
		assert forbidden not in method


def test_workflow_action_uses_shared_f3f27_bridge():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_purchase_invoice_workflow_action"):]
	for marker in (
		"FOR UPDATE",
		"expected_modified",
		"expected_workflow_state",
		"_validate_source_less_context",
		"_validate_stock_context",
		"get_workflow_readiness",
		"apply_document_workflow_action(",
	):
		assert marker in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_resumable_queue_is_bounded_permission_aware_and_scope_safe():
	source = _read(SERVICE)
	for marker in (
		"MAX_DRAFT_QUEUE = 50",
		"get_standard_purchase_invoice_completion_queue",
		'frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "read")',
		"get_operational_branch_scope",
		"BRANCH_FIELD_CANDIDATES",
		"limit_page_length=row_limit",
		"order_by=\"modified desc, name desc\"",
		"_eligible_queue_row",
	):
		assert marker in source


def test_dialog_uses_server_authoritative_submit_and_workflow_actions():
	source = _read(DIALOG)
	for marker in (
		"get_standard_purchase_invoice_completion_preview",
		"submit_standard_purchase_invoice",
		"apply_standard_purchase_invoice_workflow_action",
		"workflow_readiness?.available_actions",
		"expected_modified",
		"expected_workflow_state",
		"Advanced: Open in ERPNext",
	):
		assert marker in source
	assert 'v-if="canUseNativeDesk && document?.name"' in source


def test_business_hub_record_purchase_opens_purchase_invoice_completion():
	source = _read(HUB)
	assert 'import StandardPurchaseInvoiceCompletionDialog from "../professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue"' in source
	assert "handleSimplePurchaseInvoiceSaved(result)" in source
	assert 'this.openPurchaseInvoiceCompletion({ doctype: "Purchase Invoice", name: result.name })' in source
	assert "purchaseInvoiceCompletionOpen" in source
	assert "purchaseInvoiceCompletionDocument" in source


def test_professional_purchasing_exposes_resumable_draft_review():
	source = _read(PURCHASING)
	for marker in (
		"StandardPurchaseInvoiceCompletionDialog",
		"get_standard_purchase_invoice_completion_queue",
		"Draft Purchase Invoices Awaiting Completion",
		"draftPurchaseInvoices",
		"openPurchaseInvoiceCompletion",
		"refreshDraftPurchaseInvoices",
	):
		assert marker in source


def test_guided_creator_remains_draft_only():
	source = _read(GUIDED)
	assert "doc.insert()" in source
	assert "doc.submit()" not in source


def test_supplier_document_owner_remains_intact():
	source = _read(HANDOFF)
	assert "submit_supplier_document_purchase_invoice" in source
	assert "apply_supplier_document_purchase_invoice_workflow_action" in source


def test_backend_never_creates_accounting_or_stock_ledgers_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		'frappe.new_doc("Payment Ledger Entry")',
		"frappe.db.set_value",
	):
		assert forbidden not in source


def test_contract_preserves_source_driven_and_supplier_document_owners():
	source = _read(CONTRACT)
	assert "Supplier Document → Purchase Invoice immutable handoff" in source
	assert "Purchase Order-linked Purchase Invoice" in source
	assert "Purchase Receipt-linked Purchase Invoice" in source
