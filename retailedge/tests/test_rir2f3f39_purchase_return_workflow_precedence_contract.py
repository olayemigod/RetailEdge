from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import professional_purchase_returns as return_flow


ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (
	ROOT
	/ "public/js/professional_purchasing/ProfessionalPurchaseReturnReviewOverlay.vue"
)
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f39_purchase_return_workflow_precedence.md"


def test_preview_remains_persistence_free_and_uses_canonical_mappers():
	preview = inspect.getsource(return_flow.get_purchase_return_review)
	module = inspect.getsource(return_flow)
	assert "make_purchase_return(source.name)" in module
	assert "make_debit_note(source.name)" in module
	assert "_build_review(source, workflow_summary)" in preview
	assert ".insert()" not in preview
	assert ".submit()" not in preview


def test_review_detects_target_workflow_without_enabling_direct_submit():
	source = inspect.getsource(return_flow._build_review)
	assert "_return_workflow_summary(source.doctype)" in source
	assert "workflow_controlled" in source
	assert "not workflow_controlled" in source
	assert '"can_start_workflow": bool(workflow_controlled and not blockers)' in source
	assert '"workflow_started": False' in source
	assert '"persistence": "none"' in source


def test_workflow_preview_reuses_exact_linked_draft_without_requiring_create_permission():
	source = inspect.getsource(return_flow.get_purchase_return_review)
	assert "require_create=False" in source
	assert "_get_single_linked_draft_return(source)" in source
	assert "_validate_standard_return_draft(" in source
	assert "_workflow_draft_payload(" in source
	assert "_assert_create(source.doctype)" in source


def test_duplicate_guard_is_return_against_scoped_and_fails_closed_on_multiple():
	names = inspect.getsource(return_flow._linked_draft_return_names)
	single = inspect.getsource(return_flow._get_single_linked_draft_return)
	assert "docstatus = 0" in names
	assert "COALESCE(is_return, 0) = 1" in names
	assert "return_against = %s" in names
	assert "LIMIT 3" in names
	assert "if len(names) > 1:" in single
	assert "Multiple draft" in single
	assert 'frappe.has_permission(source.doctype, "read", doc=draft)' in single


def test_saved_return_equivalence_preserves_canonical_return_shape():
	source = inspect.getsource(return_flow._validate_standard_return_draft)
	signature = inspect.getsource(return_flow._return_item_signature)
	for contract in (
		"docstatus",
		"is_return",
		"return_against",
		"company",
		"supplier",
		"branch_mismatch",
		"update_stock_changed",
		"non_return_quantity",
		"mapped_return_changed",
	):
		assert contract in source
	for fieldname in (
		"purchase_receipt_item",
		"purchase_invoice_item",
		"item_code",
		"qty",
		"warehouse",
		"rate",
		"conversion_factor",
	):
		assert fieldname in signature


def test_existing_serial_and_batch_blockers_apply_to_saved_workflow_draft():
	source = inspect.getsource(return_flow._validate_standard_return_draft)
	preview = inspect.getsource(return_flow._preview_items)
	assert "_preview_items(draft, negative_rows)" in source
	assert "Serial Number handling requires Advanced ERPNext" in preview
	assert "Batch handling requires Advanced ERPNext" in preview


def test_start_workflow_locks_stale_checks_remaps_and_persists_one_draft_only():
	source = inspect.getsource(return_flow.start_purchase_return_workflow)
	assert "lock=True" in source
	assert "require_create=False" in source
	assert "_return_workflow_summary(source.doctype)" in source
	assert "expected_source_modified" in source
	assert "_build_review(source, workflow_summary)" in source
	assert "_get_single_linked_draft_return(source)" in source
	assert "_assert_create(source.doctype)" in source
	assert "expected_target.insert()" in source
	assert "expected_target.submit()" not in source
	assert 'idempotent=True' in source
	assert 'idempotent=False' in source


def test_direct_submit_is_preserved_only_without_active_target_workflow():
	source = inspect.getsource(return_flow.submit_purchase_return_review)
	assert "_get_source(source_type, source_name, lock=True)" in source
	assert '_return_workflow_summary(source.doctype).get("enabled")' in source
	assert "Start return approval instead of direct submission." in source
	assert source.index('_return_workflow_summary(source.doctype).get("enabled")') < source.index(
		"target.insert()"
	)
	assert "target.insert()" in source
	assert "target.submit()" in source


def test_saved_draft_workflow_action_relocks_source_and_target_and_revalidates_mapping():
	source = inspect.getsource(return_flow.apply_purchase_return_workflow_action)
	assert "lock=True" in source
	assert "require_create=False" in source
	assert "expected_source_modified" in source
	assert "expected_target_modified" in source
	assert "FOR UPDATE" in source
	assert "_get_single_linked_draft_return(source)" in source
	assert "_return_workflow_summary(source.doctype)" in source
	assert "_build_review(source, workflow_summary)" in source
	assert "_validate_standard_return_draft(" in source
	assert "apply_document_workflow_action(" in source
	assert "expected_modified=expected_target_version" in source
	assert 'expected_state=str(expected_workflow_state or "")' in source


def test_edge_ui_separates_start_workflow_actions_and_direct_submit():
	source = OVERLAY.read_text(encoding="utf-8")
	assert "start_purchase_return_workflow" in source
	assert "apply_purchase_return_workflow_action" in source
	assert "Start Return Approval" in source
	assert "Start Debit Note Approval" in source
	assert "workflowActions()" in source
	assert "review?.workflow_readiness?.available_actions || []" in source
	assert "!this.review?.workflow_controlled" in source
	assert "expected_source_modified: this.review.source_modified" in source
	assert "expected_target_modified: this.review.target_modified" in source
	assert 'expected_workflow_state: this.review.workflow_readiness?.current_state || ""' in source
	assert ".workflow_state =" not in source
	assert ".docstatus =" not in source


def test_submitting_workflow_transition_reports_exact_return_and_refreshes_queue():
	source = OVERLAY.read_text(encoding="utf-8")
	method = source[source.index("async applyWorkflow(action)") :]
	assert "Number(result.docstatus || 0) === 1" in method
	assert "submitted through Frappe Workflow" in method
	assert 'new CustomEvent(REFRESH_EVENT)' in method


def test_shared_f3f27_bridge_remains_frappe_workflow_authority():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "action not in available" in source
	assert "_assert_expected_snapshot(" in source


def test_f3f39_contract_keeps_return_intents_separate_and_erpnext_authoritative():
	doc = DOC.read_text(encoding="utf-8")
	assert "Purchase Return and Supplier Debit Note remain separate explicit business intents" in doc
	assert "ERPNext remains the return, stock, valuation and accounting truth" in doc
	assert "No schema migration is required" in doc
	assert "Serial Number" in doc
	assert "Batch" in doc
	assert "Manual browser/persona QA remains deferred" in doc


def test_standard_return_workflow_adds_no_direct_accounting_or_stock_writes():
	backend = inspect.getsource(return_flow)
	for forbidden in (
		"ignore_permissions=True",
		"frappe.db.commit",
		'frappe.new_doc("GL Entry")',
		'frappe.new_doc("Stock Ledger Entry")',
		'frappe.new_doc("Payment Entry")',
		'frappe.new_doc("Journal Entry")',
	):
		assert forbidden not in backend
