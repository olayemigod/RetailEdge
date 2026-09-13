from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import business_expense_posting
from retailedge import business_expense_register
from retailedge import workflow_actions
from retailedge import workflow_readiness


ROOT = Path(__file__).resolve().parents[1]
BUSINESS_EXPENSE_PAGE = ROOT / "public/js/business_expenses/BusinessExpenses.vue"
EXPENSE_REGISTER_PAGE = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
DOC = ROOT.parent / "docs/rir2f3f31_business_expense_accounting_posting.md"


def test_post_action_is_locked_stale_safe_and_idempotent():
	source = inspect.getsource(business_expense_posting.post_business_expense_to_accounts)
	assert "_lock_business_expense(name)" in source
	assert source.index("_posting_reference_state(doc)") < source.index(
		"_assert_modified(doc, expected_modified)"
	)
	assert 'if existing["submitted"]:' in source
	assert "idempotent=True" in source
	assert "_assert_posting_access(doc)" in source
	assert "build_business_expense_posting_readiness(doc)" in source


def test_posting_uses_normal_erpnext_journal_entry_lifecycle():
	source = inspect.getsource(business_expense_posting)
	post_source = inspect.getsource(
		business_expense_posting.post_business_expense_to_accounts
	)
	assert 'POSTING_DOCUMENT_TYPE = "Journal Entry"' in source
	assert "frappe.new_doc(POSTING_DOCUMENT_TYPE)" in source
	assert "journal.insert()" in post_source
	assert 'journal.has_permission("submit")' in post_source
	assert "journal.submit()" in post_source
	assert post_source.index("journal.submit()") < post_source.index(
		'"posting_reference": journal.name'
	)
	assert 'frappe.new_doc("GL Entry")' not in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_journal_entry_mapping_is_balanced_direct_paid_spend():
	source = inspect.getsource(business_expense_posting._build_journal_entry)
	assert '"account": doc.expense_account' in source
	assert '"debit_in_account_currency": amount' in source
	assert '"account": doc.payment_account' in source
	assert '"credit_in_account_currency": amount' in source
	assert 'debit_row["cost_center"] = doc.cost_center' in source
	assert 'debit_row["project"] = doc.project' in source
	assert 'meta.has_field("retailedge_branch")' in source


def test_simplified_posting_fails_closed_on_foreign_currency_accounts():
	source = inspect.getsource(
		business_expense_posting._validate_company_currency_accounts
	)
	assert '"default_currency"' in source
	assert '"account_currency"' in source
	assert "account_currency != company_currency" in source
	assert "simplified Business Expense posting flow" in source


def test_posted_business_expense_is_first_class_register_row_and_dedupes_gl():
	source = inspect.getsource(business_expense_register)
	assert 'BUSINESS_EXPENSE_DOCTYPE = "RetailEdge Business Expense"' in source
	assert '"Business Expense",' in source
	assert "def _build_business_expense_where_sql" in source
	assert "CONCAT('BE:', be.name)" in source
	assert "be.posting_reference = be_je.name" in source
	assert "be_je.docstatus = 1" in source
	assert "be_post.posting_reference_type = gle.voucher_type" in source
	assert "be_post.posting_reference = gle.voucher_no" in source
	assert 'clauses.append("be_post.name IS NULL")' in source


def test_business_expense_register_row_preserves_original_operational_context():
	source = inspect.getsource(business_expense_register)
	assert "be.expense_category" in source
	assert "be.branch" in source
	assert "be.expense_account" in source
	assert "be.cost_center" in source
	assert "be.payment_account" in source
	assert 'row.get("source_type") not in {"Cashier / POS", "Business Expense"}' in source


def test_edgesuite_exposes_confirmed_post_action_without_native_handoff():
	source = BUSINESS_EXPENSE_PAGE.read_text(encoding="utf-8")
	assert "get_business_expense_posting_readiness" in source
	assert "post_business_expense_to_accounts" in source
	assert "Post to Accounts" in source
	assert "frappe.confirm(" in source
	assert "expected_modified: this.current.modified" in source
	assert "This will create and submit the accounting entry." in source
	assert 'frappe.set_route("Form", "RetailEdge Business Expense"' not in source


def test_expense_register_routes_business_expense_source_back_to_edgesuite_owner():
	source = EXPENSE_REGISTER_PAGE.read_text(encoding="utf-8")
	assert 'row.source_doctype === "RetailEdge Business Expense"' in source
	assert 'frappe.route_options = { business_expense: row.source_reference || "" }' in source
	assert 'frappe.set_route("business-expenses")' in source


def test_slice_has_additive_workflow_setting_and_preserves_accounting_boundaries():
	doc = DOC.read_text(encoding="utf-8")
	assert "Workflow State Allowed for Accounting Posting" in doc
	assert "normal site migration" in doc
	assert "No submitted accounting document is mutated" in doc
	assert "Supplier credit bills remain Purchase Invoice" in doc
	assert "Cashier Expenses remain their separate POS/shift workflow" in doc


def test_posted_business_expense_is_terminal_for_active_and_fallback_workflows():
	action_source = inspect.getsource(workflow_actions.apply_document_workflow_action)
	readiness_source = inspect.getsource(workflow_readiness)
	assert "Posted Business Expenses cannot take further workflow actions" in action_source
	assert 'getattr(doc, "posting_reference", None)' in action_source
	assert "posting_final" in readiness_source
	assert "Further workflow actions are blocked" in readiness_source



def test_active_workflow_posting_requires_configured_submitted_state():
	source = inspect.getsource(business_expense_posting)
	assert "_workflow_posting_reasons" in source
	assert "_get_active_workflow(BUSINESS_EXPENSE_DOCTYPE)" in source
	assert "posting_workflow_state" in source
	assert '"doc_status": "1"' in source
	assert "current_state != allowed_state" in source


def test_posting_finalisation_never_directly_mutates_active_workflow_state():
	source = inspect.getsource(business_expense_posting.post_business_expense_to_accounts)
	assert '"posting_ready": 0' in source
	assert 'if not _get_active_workflow(BUSINESS_EXPENSE_DOCTYPE):' in source
	assert 'result_fields["expense_status"] = "Posted"' in source
	assert "workflow_state" not in source


def test_posting_requires_real_journal_read_create_submit_permissions():
	source = inspect.getsource(business_expense_posting)
	assert 'frappe.has_permission(POSTING_DOCUMENT_TYPE, "read")' in source
	assert 'frappe.has_permission(POSTING_DOCUMENT_TYPE, "create")' in source
	assert 'frappe.has_permission(POSTING_DOCUMENT_TYPE, "submit")' in source


def test_workflow_posting_setting_is_smart_and_server_validated():
	settings_json = (
		ROOT
		/ "retailedge/doctype/retailedge_settings/retailedge_settings.json"
	).read_text(encoding="utf-8")
	settings_js = (
		ROOT
		/ "retailedge/doctype/retailedge_settings/retailedge_settings.js"
	).read_text(encoding="utf-8")
	settings_py = (
		ROOT
		/ "retailedge/doctype/retailedge_settings/retailedge_settings.py"
	).read_text(encoding="utf-8")
	assert "business_expense_posting_workflow_state" in settings_json
	assert "Workflow State Allowed for Accounting Posting" in settings_json
	assert "search_business_expense_posting_workflow_states" in settings_js
	assert "_validate_business_expense_posting_workflow_state" in settings_py
	assert '"doc_status": "1"' in settings_py

def test_register_uses_accounting_truth_not_fallback_expense_status_for_posted_rows():
	source = inspect.getsource(
		business_expense_register._build_business_expense_where_sql
	)
	assert '"be.ledger_status = \'Posted\'"' in source
	assert '"be.expense_status = \'Posted\'"' not in source
	assert '"be.posting_reference_type = \'Journal Entry\'"' in source
	assert '"COALESCE(be.posting_reference, \'\') <> \'\'"' in source

