from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import standard_customer_payment_submit as customer_submit
from retailedge import standard_supplier_payment_submit as supplier_submit


ROOT = Path(__file__).resolve().parents[1]
PAYMENT_MANAGEMENT = ROOT / "public/js/payment_management/PaymentManagement.vue"
SIMPLE_PAYMENT = ROOT / "public/js/retailedge_business_hub/SimplePaymentDialog.vue"
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f35_payment_entry_workflow_precedence.md"


def test_customer_payment_preview_reads_frappe_workflow_readiness():
	source = inspect.getsource(customer_submit)
	assert "from retailedge.workflow_readiness import get_workflow_readiness" in source
	assert "workflow_readiness = get_workflow_readiness(" in source
	assert 'doctype=PAYMENT_ENTRY_DOCTYPE' in source
	assert '"workflow_readiness": workflow_readiness' in source
	assert '"workflow_eligible": workflow_eligible' in source


def test_supplier_payment_preview_reads_frappe_workflow_readiness():
	source = inspect.getsource(supplier_submit)
	assert "from retailedge.workflow_readiness import get_workflow_readiness" in source
	assert "workflow_readiness = get_workflow_readiness(" in source
	assert 'doctype=PAYMENT_ENTRY_DOCTYPE' in source
	assert '"workflow_readiness": workflow_readiness' in source
	assert '"workflow_eligible": workflow_eligible' in source


def test_active_payment_workflow_blocks_direct_customer_submit():
	source = inspect.getsource(customer_submit._standard_submit_blockers)
	assert "_workflow_submit_blocker(workflow_readiness)" in source
	assert "if workflow_blocker:" in source
	assert 'frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)' in source
	assert source.index("if workflow_blocker:") < source.index(
		'frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)'
	)
	submit_source = inspect.getsource(customer_submit.submit_standard_customer_payment)
	assert "_standard_submit_blockers(doc, payment_branch)" in submit_source
	assert "doc.submit()" in submit_source


def test_active_payment_workflow_blocks_direct_supplier_submit():
	source = inspect.getsource(supplier_submit._standard_submit_blockers)
	assert "_workflow_submit_blocker(workflow_readiness)" in source
	assert "if workflow_blocker:" in source
	assert 'frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)' in source
	assert source.index("if workflow_blocker:") < source.index(
		'frappe.has_permission(PAYMENT_ENTRY_DOCTYPE, "submit", doc=doc)'
	)
	submit_source = inspect.getsource(supplier_submit.submit_standard_supplier_payment)
	assert "_standard_submit_blockers(doc, payment_branch)" in submit_source
	assert "doc.submit()" in submit_source


def test_workflow_eligibility_requires_workflow_only_blocker():
	for module in (customer_submit, supplier_submit):
		source = inspect.getsource(module._build_preview)
		assert "workflow_blocker = _workflow_submit_blocker(workflow_readiness)" in source
		assert "workflow_eligible = bool(" in source
		assert "blocker for blocker in blockers if blocker != workflow_blocker" in source
		assert '"workflow_eligible": workflow_eligible' in source


def test_payment_workflow_blocker_identifies_active_frappe_workflow():
	for module in (customer_submit, supplier_submit):
		assert (
			module._workflow_submit_blocker(
				{"source": "frappe", "workflow": "Payment Approval"}
			)
			== "Payment Entry is controlled by active Workflow Payment Approval. Use the available workflow action in EdgeSuite."
		)
		assert module._workflow_submit_blocker({"source": "none"}) == ""


def test_payment_management_executes_shared_workflow_bridge_with_stale_snapshot():
	source = PAYMENT_MANAGEMENT.read_text(encoding="utf-8")
	assert "retailedge.workflow_actions.apply_document_workflow_action" in source
	assert "async applyPaymentWorkflow(action)" in source
	assert 'doctype: "Payment Entry"' in source
	assert "expected_modified: preview.payment_entry_modified" in source
	assert 'expected_state: preview.workflow_readiness?.current_state || ""' in source
	assert "draftReview.workflow_eligible" in source
	assert 'v-if="!draftReview.workflow_eligible"' in source


def test_business_hub_customer_and_supplier_reviews_execute_same_workflow_bridge():
	source = SIMPLE_PAYMENT.read_text(encoding="utf-8")
	assert 'const WORKFLOW_METHOD = "retailedge.workflow_actions.apply_document_workflow_action"' in source
	assert "async applyPaymentWorkflow(review, action, kind)" in source
	assert 'doctype: "Payment Entry"' in source
	assert "expected_modified: review.payment_entry_modified" in source
	assert 'expected_state: review.workflow_readiness?.current_state || ""' in source
	assert "customerReview.workflow_eligible" in source
	assert "supplierReview.workflow_eligible" in source
	assert 'v-if="!customerReview.workflow_eligible"' in source
	assert 'v-if="!supplierReview.workflow_eligible"' in source


def test_payment_ui_does_not_assign_workflow_state_or_docstatus_directly():
	for path in (PAYMENT_MANAGEMENT, SIMPLE_PAYMENT):
		source = path.read_text(encoding="utf-8")
		assert ".workflow_state =" not in source
		assert ".docstatus =" not in source
		assert "apply_document_workflow_action" in source


def test_shared_workflow_bridge_keeps_frappe_authoritative():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source
	assert "action not in available" in source
	assert "_assert_expected_snapshot(" in source


def test_contract_keeps_complex_payments_and_other_transaction_workflows_out_of_scope():
	doc = DOC.read_text(encoding="utf-8")
	assert "complex or unsupported Payment Entry shapes remain Advanced ERPNext" in doc
	assert "Purchase Order, Purchase Receipt, Purchase Invoice and purchase-return workflow parity are separate slices" in doc
	assert "No RetailEdge fallback workflow is invented for Payment Entry" in doc
	assert "Manual browser/persona QA remains deferred" in doc
