from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import guided_purchase_invoice, supplier_document_review


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/supplier_document_review/SupplierDocumentReview.vue"
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f38_purchase_invoice_workflow_precedence.md"


def test_guided_purchase_invoice_remains_draft_only():
	source = inspect.getsource(guided_purchase_invoice.create_simple_purchase_invoice_draft)
	assert "doc.insert()" in source
	assert "doc.submit()" not in source
	assert '"docstatus": doc.docstatus' in source


def test_supplier_document_review_exposes_purchase_invoice_workflow_readiness():
	source = inspect.getsource(
		supplier_document_review._supplier_document_purchase_invoice_review_payload
	)
	assert 'get_workflow_readiness(' in source
	assert 'doctype="Purchase Invoice"' in source
	assert 'workflow_controlled = str(workflow_readiness.get("source") or "") == "frappe"' in source
	assert '"workflow_readiness": workflow_readiness' in source
	assert '"workflow_eligible": workflow_eligible' in source


def test_active_workflow_blocks_direct_submit_without_becoming_an_advanced_shape():
	source = inspect.getsource(
		supplier_document_review._supplier_document_purchase_invoice_blockers
	)
	helper = inspect.getsource(supplier_document_review._purchase_invoice_workflow_blocker)
	assert 'row.get("key") != "workflow"' not in source
	assert '"key": "workflow"' in helper
	assert 'workflow_readiness.get("source")' in helper
	assert "workflow_blocker" in source
	assert '"submit_permission"' in source


def test_workflow_eligibility_requires_only_the_workflow_blocker():
	source = inspect.getsource(
		supplier_document_review._supplier_document_purchase_invoice_review_payload
	)
	assert "workflow_eligible = bool(" in source
	assert "workflow_controlled" in source
	assert "docstatus == 0" in source
	assert 'row.get("key") != "workflow"' in source


def test_direct_supplier_document_submit_rejects_active_workflow_before_erpnext_submit():
	source = inspect.getsource(
		supplier_document_review.submit_supplier_document_purchase_invoice
	)
	assert "lock_purchase_invoice=True" in source
	assert 'review.get("workflow_readiness")' in source
	assert '== "frappe"' in source
	assert "Use the available workflow action in EdgeSuite." in source
	assert source.index('review.get("workflow_readiness")') < source.index(
		"purchase_invoice.submit()"
	)
	assert "purchase_invoice.submit()" in source


def test_purchase_invoice_workflow_action_relocks_and_revalidates_exact_handoff():
	source = inspect.getsource(
		supplier_document_review.apply_supplier_document_purchase_invoice_workflow_action
	)
	assert "lock_purchase_invoice=True" in source
	assert "expected_purchase_invoice_modified" in source
	assert "changed after review" in source
	assert "_supplier_document_purchase_invoice_review_payload(" in source
	assert 'review.get("workflow_eligible")' in source
	assert "apply_document_workflow_action(" in source
	assert 'doctype="Purchase Invoice"' in source
	assert "expected_modified=expected_modified" in source
	assert 'expected_state=str(expected_workflow_state or "")' in source


def test_existing_f3f20_standard_reconciliation_remains_authoritative():
	source = inspect.getsource(
		supplier_document_review._supplier_document_purchase_invoice_blockers
	)
	for contract in (
		"extracted_currency",
		"currency_mismatch",
		"extracted_total",
		"total_difference",
		"update_stock",
		"purchase_order_linkage",
	):
		assert contract in source
	assert "abs(total_difference) > 0.01" in source


def test_edgesuite_renders_only_frappe_returned_purchase_invoice_actions():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "invoiceReview.workflow_readiness?.available_actions || []" in source
	assert "invoiceReview.workflow_eligible" in source
	assert "@click=\"applyPurchaseInvoiceWorkflow(action)\"" in source
	assert "apply_supplier_document_purchase_invoice_workflow_action" in source
	assert "expected_purchase_invoice_modified: this.invoiceReview.purchase_invoice_modified" in source
	assert 'expected_workflow_state: this.invoiceReview.workflow_readiness?.current_state || ""' in source


def test_edgesuite_hides_direct_purchase_invoice_submit_in_workflow_mode():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "Submit Purchase Invoice" in source
	assert "invoiceReview.workflow_readiness?.source !== 'frappe'" in source
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source


def test_shared_f3f27_bridge_remains_frappe_workflow_authority():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "action not in available" in source
	assert "_assert_expected_snapshot(" in source


def test_f3f38_contract_preserves_erpnext_accounting_truth_and_scope():
	doc = DOC.read_text(encoding="utf-8")
	assert "ERPNext Purchase Invoice remains the accounting and payable truth" in doc
	assert "Generic Guided Purchase Invoice flow remains draft-only" in doc
	assert "No schema migration is required" in doc
	assert "Update Stock remains outside the standard F3F38 path" in doc
	assert "Purchase Return workflow parity" in doc
	assert "Manual browser/persona QA remains deferred" in doc


def test_standard_completion_paths_do_not_create_direct_accounting_rows():
	backend = inspect.getsource(supplier_document_review)
	for forbidden in (
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		'frappe.new_doc("Payment Entry")',
		"frappe.db.commit()",
	):
		assert forbidden not in backend
