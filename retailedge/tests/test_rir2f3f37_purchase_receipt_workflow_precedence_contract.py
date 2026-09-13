from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import professional_purchase_receipt as receipt_flow


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "professional_purchase_receipt.py"
OVERLAY = (
	ROOT
	/ "public/js/professional_purchasing/ProfessionalPurchaseReceiptPreviewOverlay.vue"
)
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f37_purchase_receipt_workflow_precedence.md"


def test_preview_keeps_erpnext_mapper_read_only_and_reports_workflow_mode():
	source = inspect.getsource(receipt_flow.get_professional_purchase_receipt_preview)
	assert "_map_receipt(po, branch)" in source
	assert "_purchase_receipt_workflow_summary()" in source
	assert '"workflow_controlled": workflow_controlled' in source
	assert '"can_start_workflow": bool(workflow_controlled and not blockers)' in source
	assert '"persistence": "none"' in source
	assert "receipt.insert(" not in source
	assert "receipt.submit(" not in source


def test_no_workflow_direct_receipt_submit_remains_existing_erpnext_path():
	source = inspect.getsource(receipt_flow.submit_standard_purchase_receipt)
	assert '_purchase_receipt_workflow_summary().get("enabled")' in source
	assert source.index('_purchase_receipt_workflow_summary().get("enabled")') < source.index(
		"_assert_receipt_permissions(require_submit=True)"
	)
	assert "_get_purchase_order_for_receipt(purchase_order, lock=True)" in source
	assert "_map_receipt(po, branch)" in source
	assert "receipt.insert()" in source
	assert "receipt.submit()" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_workflow_start_persists_exactly_one_standard_draft_under_po_lock():
	source = inspect.getsource(receipt_flow.start_standard_purchase_receipt_workflow)
	assert "_get_purchase_order_for_receipt(purchase_order, lock=True)" in source
	assert "_validate_open_po(po)" in source
	assert "changed after the receipt preview" in source
	assert "_map_receipt(po, branch)" in source
	assert "_get_single_linked_draft_receipt(po)" in source
	assert "_assert_receipt_permissions()" in source
	assert "expected_receipt.insert()" in source
	assert "expected_receipt.submit()" not in source
	assert "Workflow-controlled Purchase Receipt must begin as a saved draft." in source


def test_duplicate_detection_reuses_one_draft_and_fails_closed_on_multiple():
	names_source = inspect.getsource(receipt_flow._linked_draft_receipt_names)
	single_source = inspect.getsource(receipt_flow._get_single_linked_draft_receipt)
	start_source = inspect.getsource(receipt_flow.start_standard_purchase_receipt_workflow)
	assert "SELECT DISTINCT pr.name" in names_source
	assert "pr.docstatus = 0" in names_source
	assert "pri.purchase_order = %s" in names_source
	assert "LIMIT 3" in names_source
	assert "if len(names) > 1:" in single_source
	assert "Multiple draft Purchase Receipts already exist" in single_source
	assert 'idempotent=True' in start_source
	assert "expected_receipt.insert()" in start_source


def test_existing_draft_requires_read_permission_before_reuse():
	source = inspect.getsource(receipt_flow._get_single_linked_draft_receipt)
	assert 'frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "read", doc=draft)' in source
	assert "you do not have permission to review it" in source


def test_standard_draft_equivalence_is_strict_and_single_po():
	source = inspect.getsource(receipt_flow._validate_standard_receipt_draft)
	signature = inspect.getsource(receipt_flow._receipt_item_signature)
	assert "docstatus" in source
	assert "is_return" in source
	assert "company" in source
	assert "supplier" in source
	assert "purchase_order" in source
	assert "expected_receipt" in source
	assert "mapped_quantity_changed" in source
	for fieldname in (
		"purchase_order_item",
		"item_code",
		"qty",
		"warehouse",
		"rejected_qty",
		"rate",
		"conversion_factor",
	):
		assert fieldname in signature


def test_saved_draft_reuses_existing_advanced_stock_blockers():
	source = inspect.getsource(receipt_flow._validate_standard_receipt_draft)
	for contract in (
		"_receipt_item_preview(row)",
		"missing_warehouse",
		"warehouse_company",
	):
		assert contract in source
	backend = BACKEND.read_text(encoding="utf-8")
	for advanced in (
		"has_serial_no",
		"has_batch_no",
		"inspection_required_before_purchase",
		"rejected_quantity",
		"subcontracting",
	):
		assert advanced in backend


def test_receipt_workflow_action_relocks_and_revalidates_saved_draft():
	source = inspect.getsource(
		receipt_flow.apply_standard_purchase_receipt_workflow_action
	)
	assert "FOR UPDATE" in source
	assert 'frappe.has_permission(PURCHASE_RECEIPT_DOCTYPE, "read", doc=draft)' in source
	assert "Only a draft Purchase Receipt can use the standard workflow action path." in source
	assert "exactly one linked Purchase Order" in source
	assert "_get_purchase_order_for_receipt(purchase_order, lock=True)" in source
	assert "_get_single_linked_draft_receipt(po)" in source
	assert "_map_receipt(po, branch)" in source
	assert "_validate_standard_receipt_draft(" in source
	assert "changed after it was reviewed" in source
	assert "apply_document_workflow_action(" in source
	assert "expected_modified=expected_modified" in source
	assert 'expected_state=str(expected_workflow_state or "")' in source


def test_edge_ui_distinguishes_start_workflow_from_direct_receive_stock():
	source = OVERLAY.read_text(encoding="utf-8")
	assert "start_standard_purchase_receipt_workflow" in source
	assert "apply_standard_purchase_receipt_workflow_action" in source
	assert "Start Receipt Approval" in source
	assert "No stock is posted until Frappe Workflow reaches a submitting state." in source
	assert "canStartWorkflow()" in source
	assert "canSubmitStandard()" in source
	assert "&& !this.preview?.workflow_controlled" in source


def test_edge_ui_renders_only_returned_receipt_workflow_actions():
	source = OVERLAY.read_text(encoding="utf-8")
	assert 'preview.workflow_readiness?.available_actions || []' in source
	assert '@click="applyWorkflow(action.action)"' in source
	assert "expected_purchase_receipt_modified: this.preview.purchase_receipt_modified" in source
	assert 'expected_workflow_state: this.preview.workflow_readiness?.current_state || ""' in source
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source


def test_submitting_workflow_transition_reports_stock_received_and_refreshes_queue():
	source = OVERLAY.read_text(encoding="utf-8")
	method = source[source.index("async applyWorkflow(action)") :]
	assert "Number(result.docstatus || 0) === 1" in method
	assert "Stock has been received." in method
	assert 'new CustomEvent("retailedge-professional-purchasing-page-show")' in method


def test_shared_f3f27_bridge_remains_frappe_workflow_authority():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "action not in available" in source
	assert "_assert_expected_snapshot(" in source


def test_contract_preserves_stock_truth_and_defers_advanced_receipt_work():
	doc = DOC.read_text(encoding="utf-8")
	assert "ERPNext Purchase Receipt remains the stock and accounting truth" in doc
	assert "No RetailEdge fallback workflow is invented for Purchase Receipt" in doc
	assert "Partial quantity editing remains out of scope" in doc
	assert "Purchase Invoice workflow parity remains out of scope" in doc
	assert "Manual browser/persona QA remains deferred" in doc
