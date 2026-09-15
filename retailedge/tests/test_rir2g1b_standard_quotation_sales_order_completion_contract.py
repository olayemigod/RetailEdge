from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "standard_selling_completion.py"
WORKSPACE = ROOT / "public/js/professional_selling/ProfessionalSelling.vue"
DIALOG = ROOT / "public/js/professional_selling/StandardSellingCompletionDialog.vue"
CONTRACT = ROOT.parent / "docs/rir2g1b_standard_quotation_sales_order_completion.md"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_backend_scope_is_exactly_quotation_and_sales_order():
	source = _read(SERVICE)
	assert 'SUPPORTED_DOCTYPES = {"Quotation", "Sales Order"}' in source
	assert "Delivery Note" not in source
	assert "Sales Invoice" not in source


def test_preview_is_permission_aware_branch_safe_and_persistence_free():
	source = _read(SERVICE)
	for contract in (
		"get_standard_selling_completion_preview",
		"_get_supported_document",
		"_validate_standard_context",
		"_validate_stored_operational_branch",
		"get_operating_context",
		"get_workflow_readiness",
		'"persistence": "none"',
		'"source_of_truth": "ERPNext"',
	):
		assert contract in source
	for forbidden in (
		".insert()",
		".save()",
		".submit()",
		"frappe.db.commit",
		"ignore_permissions=True",
	):
		preview = source[
			source.index("def get_standard_selling_completion_preview"):
			source.index("@frappe.whitelist(methods=[\"POST\"])", source.index("def get_standard_selling_completion_preview"))
		]
		assert forbidden not in preview


def test_standard_shape_fails_closed_for_advanced_quotation_and_sales_order():
	source = _read(SERVICE)
	for contract in (
		'_clean(doc.get("quotation_to")) != "Customer"',
		"amended_from",
		"order_type",
		"is_internal_customer",
		"represents_company",
		"inter_company_order_reference",
		"Advanced ERPNext",
	):
		assert contract in source


def test_direct_submit_locks_stale_checks_revalidates_and_delegates_to_erpnext():
	source = _read(SERVICE)
	start = source.index("def submit_standard_selling_document")
	end = source.index("@frappe.whitelist(methods=[\"POST\"])", start + 10)
	method = source[start:end]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"_validate_standard_context",
		"_standard_shape_blockers",
		"get_workflow_readiness",
		'_clean(workflow_readiness.get("source")) == "frappe"',
		'frappe.has_permission(doctype, "submit", doc=doc)',
		"doc.submit()",
	):
		assert contract in method
	assert ".docstatus =" not in method
	assert ".workflow_state =" not in method


def test_workflow_action_locks_stale_checks_and_uses_f3f27_bridge():
	source = _read(SERVICE)
	method = source[source.index("def apply_standard_selling_workflow_action"):]
	for contract in (
		"FOR UPDATE",
		"expected_modified",
		"expected_workflow_state",
		"_validate_standard_context",
		"_standard_shape_blockers",
		"get_workflow_readiness",
		'_clean(workflow_readiness.get("source")) != "frappe"',
		"apply_document_workflow_action(",
		"expected_modified=expected_modified",
		"expected_state=str(expected_workflow_state or",
	):
		assert contract in method
	assert ".workflow_state =" not in method
	assert ".docstatus =" not in method


def test_backend_never_writes_accounting_or_stock_truth_directly():
	source = _read(SERVICE)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		"frappe.db.set_value",
	):
		assert forbidden not in source


def test_completion_dialog_uses_only_server_authoritative_actions():
	source = _read(DIALOG)
	for contract in (
		"get_standard_selling_completion_preview",
		"submit_standard_selling_document",
		"apply_standard_selling_workflow_action",
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
	for forbidden in (
		".workflow_state =",
		".docstatus =",
		".status =",
	):
		assert forbidden not in source


def test_professional_selling_opens_completion_after_saved_quote_or_order():
	source = _read(WORKSPACE)
	assert 'import StandardSellingCompletionDialog from "./StandardSellingCompletionDialog.vue"' in source
	assert "handleQuotationSaved(result)" in source
	assert "handleSalesOrderSaved(result)" in source
	assert "openStandardCompletion(" in source
	assert 'doctype: "Quotation"' in source
	assert 'doctype: "Sales Order"' in source


def test_tabbed_draft_completion_routes_quote_and_order_to_standard_completion():
	source = _read(WORKSPACE)
	assert 'if (document.key === "quotation")' in source
	assert 'this.openStandardCompletion({ doctype: "Quotation", name: row.name });' in source
	assert 'if (document.key === "sales-order")' in source
	assert 'this.openStandardCompletion({ doctype: "Sales Order", name: row.name });' in source


def test_delivery_and_invoice_keep_their_own_completion_dialogs():
	source = _read(WORKSPACE)
	assert 'this.openDeliveryCompletion({ doctype: "Delivery Note", name: row.name });' in source
	assert 'this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: row.name });' in source


def test_contract_stays_bounded_to_commitment_documents():
	source = _read(CONTRACT)
	assert "Delivery Note submit" in source
	assert "Sales Invoice submit" in source
	assert "separate checkpoints" in source
