from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import landed_cost_allocation as landed


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
PAGE_CONTROLLER = ROOT / "retailedge/page/professional_purchasing/professional_purchasing.js"
WORKFLOW_ACTIONS = ROOT / "workflow_actions.py"
DOC = ROOT.parent / "docs/rir2f3f41_landed_cost_voucher_edgesuite_ownership.md"


def test_standard_contract_has_bounded_source_distribution_and_charge_inputs():
	source = inspect.getsource(landed)
	assert 'STANDARD_DISTRIBUTION_METHODS = {"Amount", "Qty"}' in source
	assert "_ALLOWED_STANDARD_CHARGE_KEYS" in source
	assert '"expense_account"' in source
	assert '"description"' in source
	assert '"amount"' in source
	assert "Distribute Manually" in source


def test_account_search_mirrors_erpnext_company_and_account_type_guard():
	source = inspect.getsource(landed.search_landed_cost_expense_accounts)
	assert "ALLOWED_LANDED_COST_ACCOUNT_TYPES" in source
	assert '"company": resolved_company' in source
	assert '"is_group": 0' in source
	assert '"disabled": 0' in source
	assert "MAX_LINK_RESULTS" in source
	assert 'reference_doctype=LANDED_COST_VOUCHER_DOCTYPE' in source


def test_standard_review_is_persistence_free_and_native_validated():
	source = inspect.getsource(landed.review_standard_landed_cost_allocation)
	assert "_prepare_standard_landed_cost_voucher" in source
	assert '"persisted": False' in source
	assert '"source_modified"' in source
	assert '"workflow_readiness"' in source
	assert ".insert(" not in source
	assert ".save(" not in source
	assert ".submit(" not in source


def test_standard_prepare_uses_native_make_lcv_and_native_validate():
	source = inspect.getsource(landed._prepare_standard_landed_cost_voucher)
	assert "make_lcv(" in source or "_native_landed_cost_voucher" in source
	assert "run_method("validate")" in source
	assert "_validate_standard_charge_account" in source
	assert "update_landed_cost(" not in source
	assert "frappe.new_doc("GL Entry")" not in source
	assert "frappe.new_doc("Stock Ledger Entry")" not in source


def test_standard_shape_fails_unrepresented_accounting_dimension_overrides_closed():
	source = inspect.getsource(landed._assert_standard_landed_cost_shape)
	assert "_dimension_values" in source
	assert "Custom Landed Cost item dimensions require Advanced ERPNext." in source
	assert "Landed Cost charge accounting-dimension overrides require Advanced ERPNext." in source


def test_start_is_locked_duplicate_safe_and_reuses_only_standard_equivalent_draft():
	source = inspect.getsource(landed.start_standard_landed_cost_voucher)
	assert "FOR UPDATE" in source
	assert "expected_source_modified" in source
	assert "_find_linked_draft_landed_cost_vouchers" in source
	assert "_assert_standard_landed_cost_equivalence" in source
	assert "landed_cost_voucher.insert()" in source
	assert "frappe.db.commit" not in source
	assert "ignore_permissions" not in source


def test_standard_submit_is_named_document_idempotent_and_workflow_aware():
	source = inspect.getsource(landed.submit_standard_landed_cost_voucher)
	assert "FOR UPDATE" in source
	assert "docstatus" in source
	assert '"already_submitted": True' in source
	assert "_assert_standard_landed_cost_equivalence" in source
	assert "get_workflow_readiness(" in source
	assert "landed_cost_voucher.submit()" in source


def test_workflow_action_revalidates_and_delegates_to_f3f27():
	source = inspect.getsource(landed.apply_landed_cost_workflow_action)
	assert "FOR UPDATE" in source
	assert "expected_source_modified" in source
	assert "expected_landed_cost_modified" in source
	assert "expected_workflow_state" in source
	assert "_assert_standard_landed_cost_equivalence" in source
	assert "apply_document_workflow_action(" in source
	assert "expected_state=str(expected_workflow_state or" in source


def test_edgesuite_owns_standard_landed_cost_without_client_allocation_math():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "review_standard_landed_cost_allocation" in source
	assert "start_standard_landed_cost_voucher" in source
	assert "submit_standard_landed_cost_voucher" in source
	assert "apply_landed_cost_workflow_action" in source
	assert "search_landed_cost_expense_accounts" in source
	assert "Review Landed Cost" in source
	assert "Prepare Landed Cost Draft" in source
	assert "Advanced: Prepare in ERPNext" in source
	assert "applicable_charges =" not in source
	assert "base_amount =" not in source
	assert "workflow_state =" not in source
	assert "docstatus =" not in source


def test_edgesuite_only_guard_no_longer_hides_standard_landed_cost_panel():
	source = PAGE_CONTROLLER.read_text(encoding="utf-8")
	assert 'nativeDoctypes: [' in source
	assert '"Landed Cost Voucher"' in source
	assert '".landed-cost-panel"' not in source


def test_advanced_native_handoff_remains_persistence_free():
	source = inspect.getsource(landed.prepare_landed_cost_voucher_draft)
	assert "make_lcv(" in source or "_native_landed_cost_voucher" in source
	assert '"persisted": False' in source
	assert ".insert(" not in source
	assert ".save(" not in source
	assert ".submit(" not in source


def test_shared_workflow_bridge_remains_frappe_authoritative():
	source = WORKFLOW_ACTIONS.read_text(encoding="utf-8")
	assert "from frappe.model.workflow import apply_workflow" in source
	assert "result = apply_workflow(doc, action)" in source


def test_contract_keeps_high_risk_cases_advanced():
	source = DOC.read_text(encoding="utf-8")
	for phrase in (
		"manual item-level allocation",
		"vendor invoice landed-cost claims",
		"fixed-asset landed cost",
		"custom accounting-dimension input UI",
		"cancellation/amendment",
		"multi-source voucher composition",
	):
		assert phrase in source
