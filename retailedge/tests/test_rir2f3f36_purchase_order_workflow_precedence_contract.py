from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import professional_purchase_order_submit as po_submit


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (
	ROOT
	/ "public/js/professional_purchasing/ProfessionalPurchaseOrderSubmitOverlay.vue"
)
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f36_purchase_order_workflow_precedence.md"


def test_purchase_order_preview_reads_shared_workflow_readiness():
	source = inspect.getsource(po_submit)
	assert "from retailedge.workflow_readiness import get_workflow_readiness" in source
	assert "workflow_readiness = get_workflow_readiness(" in source
	assert "doctype=PURCHASE_ORDER_DOCTYPE" in source
	assert '"workflow_readiness": workflow_readiness' in source
	assert '"workflow_eligible": workflow_eligible' in source


def test_active_workflow_blocks_direct_po_submit_before_submit_permission():
	source = inspect.getsource(po_submit._standard_submit_blockers)
	assert "_workflow_submit_blocker(workflow_readiness)" in source
	assert "if workflow_blocker:" in source
	assert '_permission(PURCHASE_ORDER_DOCTYPE, "submit", doc.name)' in source
	assert source.index("if workflow_blocker:") < source.index(
		'_permission(PURCHASE_ORDER_DOCTYPE, "submit", doc.name)'
	)
	submit_source = inspect.getsource(po_submit.submit_standard_purchase_order)
	assert "_standard_submit_blockers(doc)" in submit_source
	assert "doc.submit()" in submit_source


def test_workflow_eligibility_requires_workflow_only_blocker():
	source = inspect.getsource(po_submit._build_preview)
	assert "workflow_blocker = _workflow_submit_blocker(workflow_readiness)" in source
	assert "workflow_eligible = bool(" in source
	assert "blocker for blocker in blockers if blocker != workflow_blocker" in source
	assert '"workflow_eligible": workflow_eligible' in source


def test_advanced_po_shapes_remain_edge_workflow_ineligible():
	source = inspect.getsource(po_submit._standard_submit_blockers)
	assert "is_subcontracted" in source
	assert "is_old_subcontracting_flow" in source
	assert "is_internal_supplier" in source
	assert "inter_company_order_reference" in source
	assert "BLOCKED_DRAFT_STATUSES" in source


def test_scoped_workflow_action_relocks_and_revalidates_po():
	source = inspect.getsource(
		po_submit.apply_standard_purchase_order_workflow_action
	)
	assert "FOR UPDATE" in source
	assert "_get_purchase_order(purchase_order)" in source
	assert "_validate_purchase_order_branch(doc)" in source
	assert "_item_preview(doc)" in source
	assert "changed after the review" in source
	assert "_build_preview(doc)" in source
	assert 'if not preview.get("workflow_eligible"):' in source
	assert "apply_document_workflow_action(" in source
	assert "expected_modified=expected_modified" in source
	assert 'expected_state=str(expected_workflow_state or "")' in source


def test_direct_standard_submit_keeps_erpnext_authoritative_without_workflow():
	source = inspect.getsource(po_submit.submit_standard_purchase_order)
	assert "FOR UPDATE" in source
	assert "_validate_purchase_order_branch(doc)" in source
	assert "_item_preview(doc)" in source
	assert "changed after the review" in source
	assert "_standard_submit_blockers(doc)" in source
	assert "doc.submit()" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_purchase_order_overlay_renders_only_returned_workflow_actions():
	source = OVERLAY.read_text(encoding="utf-8")
	assert "apply_standard_purchase_order_workflow_action" in source
	assert "preview.workflow_eligible" in source
	assert "preview.workflow_readiness?.available_actions" in source
	assert "@click="applyWorkflow(action.action)"" in source
	assert "expected_purchase_order_modified: this.preview.purchase_order_modified" in source
	assert 'expected_workflow_state: this.preview.workflow_readiness?.current_state || ""' in source


def test_direct_submit_is_hidden_when_workflow_owns_po():
	source = OVERLAY.read_text(encoding="utf-8")
	assert 'preview?.can_submit && !preview?.workflow_eligible && !submitted' in source
	assert "if (!this.preview?.can_submit || this.preview?.workflow_eligible || this.submitting) return;" in source


def test_workflow_transition_refreshes_preview_and_purchasing_queue():
	source = OVERLAY.read_text(encoding="utf-8")
	workflow_method = source[source.index("async applyWorkflow(action)") :]
	assert "this.preview = await callMethod(PREVIEW_METHOD" in workflow_method
	assert 'new CustomEvent("retailedge-professional-purchasing-page-show")' in workflow_method
	assert "Number(result.docstatus || 0) === 1" in workflow_method


def test_ui_does_not_assign_workflow_state_or_docstatus():
	source = OVERLAY.read_text(encoding="utf-8")
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source


def test_shared_f3f27_bridge_remains_frappe_authoritative():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "action not in available" in source
	assert "_assert_expected_snapshot(" in source


def test_contract_keeps_receipt_invoice_return_workflow_parity_separate():
	doc = DOC.read_text(encoding="utf-8")
	assert "No RetailEdge fallback workflow is invented for Purchase Order" in doc
	assert "Purchase Receipt workflow parity is out of scope" in doc
	assert "Purchase Invoice workflow parity is out of scope" in doc
	assert "Purchase Return workflow parity is out of scope" in doc
	assert "Manual browser/persona QA remains deferred" in doc
