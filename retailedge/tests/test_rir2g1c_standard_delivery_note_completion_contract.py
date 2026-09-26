from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_delivery_completion.py"
WORKSPACE = ROOT / "public/js/professional_selling/ProfessionalSelling.vue"
DIALOG = ROOT / "public/js/professional_selling/StandardDeliveryCompletionDialog.vue"
DELIVERY = ROOT / "professional_delivery.py"
CONTRACT = ROOT.parent / "docs/rir2g1c_standard_delivery_note_completion.md"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_service_is_exactly_delivery_note_completion():
	source = _read(SERVICE)
	assert 'DELIVERY_NOTE_DOCTYPE = "Delivery Note"' in source
	assert 'SUPPORTED_DOCTYPES' not in source
	assert 'frappe.new_doc("Sales Invoice")' not in source
	assert 'frappe.get_doc("Sales Invoice", source_sales_invoice)' in source


def test_preview_is_persistence_free_and_stock_truth_is_not_reimplemented():
	source = _read(SERVICE)
	preview_start = source.index("def get_standard_delivery_completion_preview")
	submit_start = source.index('@frappe.whitelist(methods=["POST"])', preview_start)
	preview = source[preview_start:submit_start]
	for contract in (
		"_get_delivery_note",
		"_validate_delivery_context",
		"_standard_delivery_blockers",
		"_validate_source_and_stock_context",
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
		'frappe.new_doc("Stock Ledger Entry")',
	):
		assert forbidden not in preview


def test_standard_delivery_shape_fails_closed_for_advanced_stock_cases():
	source = _read(SERVICE)
	for contract in (
		"is_return",
		"return_against",
		"amended_from",
		"packed_items",
		"serial_no",
		"batch_no",
		"serial_and_batch_bundle",
		"is_internal_customer",
		"represents_company",
		"against_sales_order",
		"warehouse",
		"Advanced ERPNext",
	):
		assert contract in source


def test_standard_delivery_requires_one_submitted_matching_sales_order():
	source = _read(SERVICE)
	for contract in (
		'frappe.get_doc("Sales Order", source_name)',
		"source.docstatus != 1",
		"source_company != company",
		"source_customer != customer",
		"_validate_stored_operational_branch",
		"source_branch != effective_branch",
	):
		assert contract in source



def test_sales_invoice_sourced_delivery_revalidates_lineage_and_blocks_double_stock():
	source = _read(SERVICE)
	for contract in (
		"against_sales_invoice",
		"source_sales_invoice",
		'frappe.get_doc("Sales Invoice", source_sales_invoice)',
		"Source Sales Invoice Company does not match the Delivery Note",
		"Source Sales Invoice Customer does not match the Delivery Note",
		"already posted stock",
		"cannot mix unlinked or differently linked items",
	):
		assert contract in source


def test_invoice_linked_delivery_does_not_offer_duplicate_sales_invoice_action():
	selling = _read(ROOT / "professional_selling.py")
	dialog = _read(DIALOG)
	assert 'filters={"parent": name, "parenttype": "Delivery Note", "against_sales_invoice": ["!=", ""]}' in selling
	assert 'action.get("value") != "create-sales-invoice"' in selling
	assert 'frappe.get_doc("Delivery Note", name)' in selling
	assert 'row.get("against_sales_invoice")' in selling
	assert 'action.get("value") != "create-sales-invoice"' in selling
	assert '"source_sales_invoice": source_sales_invoice' not in selling
	assert 'preview.source_sales_invoice ? "Source Sales Invoice" : "Source Sales Order"' in dialog
	assert "resolved.source_sales_invoice" not in dialog


def test_warehouse_context_is_company_branch_and_permission_safe():
	source = _read(SERVICE)
	for contract in (
		'_assert_read("Warehouse", warehouse)',
		'frappe.db.get_value("Warehouse", warehouse, "company")',
		"resolve_branch_warehouse_selection",
		'preference="sales"',
		"_validate_stored_operational_branch",
		"resolved_branches",
		"multiple operational Branches",
		"enabled Branch Setup",
	):
		assert contract in source


def test_direct_submit_locks_stale_checks_revalidates_then_uses_native_submit():
	source = _read(SERVICE)
	start = source.index("def submit_standard_delivery_note")
	end = source.index('@frappe.whitelist(methods=["POST"])', start + 10)
	method = source[start:end]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"_validate_delivery_context",
		"_standard_delivery_blockers",
		"_validate_source_and_stock_context",
		"get_workflow_readiness",
		'_clean(workflow_readiness.get("source")) == "frappe"',
		'frappe.has_permission(DELIVERY_NOTE_DOCTYPE, "submit", doc=doc)',
		"doc.submit()",
	):
		assert contract in method
	for forbidden in (".docstatus =", ".workflow_state =", "frappe.db.commit", "ignore_permissions=True"):
		assert forbidden not in method


def test_workflow_action_uses_f3f27_and_never_assigns_workflow_truth():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_delivery_workflow_action"):]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"expected_workflow_state",
		"_validate_delivery_context",
		"_validate_source_and_stock_context",
		"get_workflow_readiness",
		"apply_document_workflow_action(",
		"expected_modified=expected_modified",
		"expected_state=str(expected_workflow_state or",
	):
		assert contract in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_backend_never_writes_stock_or_accounting_truth_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		"frappe.db.set_value",
		"update_stock_ledger",
	):
		assert forbidden not in source


def test_delivery_draft_editor_allows_safe_item_edits_and_additions():
	service = _read(SERVICE)
	dialog = _read(DIALOG)
	for contract in (
		"def update_standard_delivery_draft(",
		"update_draft_items(",
		'"editable_items": editable_items(doc)',
		'"can_edit": bool(',
	):
		assert contract in service
	for contract in (
		"Edit draft before completion",
		"Save Draft Changes",
		"Additional Items",
		"EdgeChildTable",
		"EdgeLinkField",
		"update_standard_delivery_draft",
	):
		assert contract in dialog


def test_delivery_dialog_uses_only_server_authoritative_completion_actions():
	source = _read(DIALOG)
	for contract in (
		"get_standard_delivery_completion_preview",
		"submit_standard_delivery_note",
		"apply_standard_delivery_workflow_action",
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


def test_workspace_opens_delivery_completion_after_saved_delivery():
	source = _read(WORKSPACE)
	assert 'import StandardDeliveryCompletionDialog from "./StandardDeliveryCompletionDialog.vue"' in source
	assert "handleDeliverySaved(result)" in source
	assert 'this.openDeliveryCompletion({ doctype: "Delivery Note", name: result.name })' in source
	assert "deliveryCompletionOpen" in source
	assert "deliveryCompletionDocument" in source


def test_tabbed_delivery_completion_is_separate_from_quote_order_and_invoice():
	source = _read(WORKSPACE)
	assert 'if (document.key === "delivery-note")' in source
	assert 'this.openDeliveryCompletion({ doctype: "Delivery Note", name: row.name });' in source
	assert 'this.openStandardCompletion({ doctype: "Quotation", name: row.name });' in source
	assert 'this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: row.name });' in source


def test_delivery_completion_exposes_post_submit_invoice_and_output_actions():
	dialog = _read(DIALOG)
	assert "get_professional_selling_record_actions" in dialog
	assert "completedResult.next_actions" in dialog
	assert "Print & Send" in dialog
	assert 'this.$emit("next-action"' in dialog


def test_existing_delivery_creation_remains_native_mapper_and_draft_only():
	source = _read(DELIVERY)
	assert "erpnext_make_delivery_note(source.name)" in source
	assert "target.insert()" in source
	assert "target.submit()" not in source
	assert "No stock ledger entry is created until normal ERPNext" in source


def test_contract_preserves_separate_sales_invoice_accounting_boundary():
	source = _read(CONTRACT)
	assert "Sales Invoice accounting submission" in source
	assert "separate later checkpoint" in source
	assert "Stock Ledger" in source
