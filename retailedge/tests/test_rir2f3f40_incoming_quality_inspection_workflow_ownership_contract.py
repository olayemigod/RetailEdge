from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import incoming_quality_inspection as quality


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/professional_purchasing/IncomingQualityInspection.vue"
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f40_incoming_quality_inspection_workflow_ownership.md"


def test_review_exposes_frappe_workflow_precedence_without_losing_no_workflow_path():
	source = inspect.getsource(quality)
	assert "from retailedge.workflow_readiness import get_workflow_readiness" in source
	assert '"workflow_readiness": workflow_readiness' in source
	assert '"workflow_controlled": workflow_controlled' in source
	assert '"can_start_workflow":' in source
	assert "quality_inspection.insert()" in source
	assert "quality_inspection.submit()" in source


def test_direct_submit_fails_closed_when_quality_inspection_workflow_is_active():
	source = inspect.getsource(quality.submit_incoming_quality_inspection_review)
	assert "get_workflow_readiness(" in source
	assert '"source") or "") == "frappe"' in source or '"source") == "frappe"' in source
	assert "Start Inspection Approval" in source
	assert "quality_inspection.submit()" in source


def test_workflow_start_relocks_source_and_prevents_duplicate_standard_drafts():
	source = inspect.getsource(quality.start_incoming_quality_inspection_approval)
	assert "FOR UPDATE" in source
	assert "expected_source_modified" in source
	assert "_find_linked_draft_quality_inspections" in source
	assert "_assert_standard_quality_inspection_equivalence" in source
	assert "quality_inspection.insert()" in source
	assert "get_workflow_readiness(" in source
	assert "frappe.db.commit" not in source
	assert "ignore_permissions" not in source


def test_duplicate_scan_is_exact_to_purchase_receipt_child_row():
	source = inspect.getsource(quality._find_linked_draft_quality_inspections)
	assert '"reference_type": PURCHASE_RECEIPT_DOCTYPE' in source
	assert '"reference_name": receipt_name' in source
	assert '"child_row_reference": child_row_reference' in source
	assert '"docstatus": 0' in source
	assert "limit=3" in source


def test_saved_draft_equivalence_preserves_erpnext_source_and_template_truth():
	source = inspect.getsource(quality._assert_standard_quality_inspection_equivalence)
	for token in (
		"inspection_type",
		"reference_type",
		"reference_name",
		"child_row_reference",
		"item_code",
		"sample_size",
		"quality_inspection_template",
		"specification",
	):
		assert token in source
	assert "Advanced ERPNext" in source


def test_scoped_quality_workflow_action_relocks_source_and_target_then_uses_f3f27():
	source = inspect.getsource(quality.apply_incoming_quality_inspection_workflow_action)
	assert "FOR UPDATE" in source
	assert "expected_source_modified" in source
	assert "expected_quality_inspection_modified" in source
	assert "expected_workflow_state" in source
	assert "_assert_standard_quality_inspection_equivalence" in source
	assert "apply_document_workflow_action(" in source
	assert "expected_modified=expected_quality_inspection_modified" in source
	assert "expected_state=str(expected_workflow_state or" in source


def test_edgesuite_switches_between_direct_submit_and_start_approval():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "start_incoming_quality_inspection_approval" in source
	assert "apply_incoming_quality_inspection_workflow_action" in source
	assert "Start Inspection Approval" in source
	assert "Submit Quality Inspections" in source
	assert "review.workflow_controlled" in source or "review?.workflow_controlled" in source
	assert "workflowInspections" in source


def test_edgesuite_renders_only_authoritative_workflow_actions():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "workflow_readiness?.available_actions" in source
	assert "applyWorkflow(inspection, action.action)" in source
	assert "expected_quality_inspection_modified" in source
	assert "expected_workflow_state" in source
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source
	assert ".status =" not in source


def test_native_advanced_fallback_remains_capability_gated():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "nativeFallbackEnabled" in source
	assert "Advanced: Prepare in ERPNext" in source
	assert 'frappe.boot?.edgesuite_ui_access?.mode !== "edgesuite_only"' in source


def test_shared_workflow_bridge_remains_frappe_authoritative():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "_assert_expected_snapshot(" in source


def test_contract_keeps_scope_bounded():
	source = DOC.read_text(encoding="utf-8")
	assert "No RetailEdge fallback workflow is invented for Quality Inspection" in source
	assert "Landed Cost Voucher ownership" in source
	assert "Quality Inspection Template administration" in source
	assert "Manual browser/persona QA" in source
