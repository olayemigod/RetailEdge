from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import business_expense
from retailedge import master_experience


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/business_expenses/BusinessExpenses.vue"
REGISTER = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
PAGE_JSON = ROOT / "retailedge/page/business_expenses/business_expenses.json"
DOC = ROOT.parent / "docs/rir2f3f30_business_expenses_edgesuite_owner.md"


def test_business_expense_backend_has_scoped_paginated_queue():
	source = inspect.getsource(business_expense)
	assert "def get_business_expenses" in source
	assert "get_operational_branch_scope" in source
	assert '"branch": ["in", allowed] if allowed else "__never__"' in source
	assert "limit_start=(page - 1) * page_size" in source
	assert "MAX_DATE_RANGE_DAYS" in source
	assert "ignore_permissions" not in source


def test_saved_drafts_are_stale_safe_and_edit_only():
	source = inspect.getsource(business_expense.update_business_expense_draft)
	assert "doc.docstatus != 0" in source
	assert 'doc.has_permission("write")' in source
	assert "_assert_modified(doc, expected_modified)" in source
	assert "_apply_business_expense_values" in source
	assert "doc.save()" in source
	assert ".submit()" not in source


def test_evidence_link_is_verified_against_attached_file():
	source = inspect.getsource(business_expense.set_business_expense_attachment)
	assert '"File"' in source
	assert '"attached_to_doctype": BUSINESS_EXPENSE_DOCTYPE' in source
	assert '"attached_to_name": doc.name' in source
	assert "_assert_modified(doc, expected_modified)" in source
	assert "doc.attachment = file_url" in source


def test_category_defaults_are_server_validated():
	source = inspect.getsource(business_expense.get_business_expense_category_defaults)
	assert "_validate_expense_account" in source
	assert "_validate_cost_center" in source
	assert "row.company and row.company != company" in source


def test_business_expenses_page_is_edgesuite_only_and_workflow_dynamic():
	source = PAGE.read_text(encoding="utf-8")
	assert 'title="Business Expenses"' in source
	assert "get_business_expenses" in source
	assert "update_business_expense_draft" in source
	assert "set_business_expense_attachment" in source
	assert "apply_document_workflow_action" in source
	assert "workflow_readiness?.available_actions" in source
	assert "frappe.ui.FileUploader" in source
	assert 'frappe.set_route("Form", "RetailEdge Business Expense"' not in source
	assert 'frappe.set_route("List", "RetailEdge Business Expense"' not in source


def test_final_navigation_promotes_business_expenses_owner_and_removes_raw_category():
	source = inspect.getsource(master_experience)
	assert 'BUSINESS_EXPENSE_ITEM' in source
	assert '"target": "business-expenses"' in source
	assert "_promote_business_expense_ownership(navigation_groups)" in source
	assert "EXPENSE_CATEGORY_NATIVE_PEER_DOCTYPE" in source


def test_expense_register_no_longer_creates_cashier_expense_in_native_form():
	source = REGISTER.read_text(encoding="utf-8")
	assert "SimpleCashierExpenseDialog" in source
	assert ':nativeFallbackEnabled="false"' in source
	assert 'frappe.new_doc("RetailEdge Cashier Expense")' not in source
	assert 'frappe.set_route("List", "RetailEdge Expense Category")' not in source
	assert 'frappe.set_route("business-expenses")' in source
	assert "canUseNativeDesk" in source


def test_page_permissions_exclude_cashier_roles():
	page = PAGE_JSON.read_text(encoding="utf-8")
	assert "RetailEdge Manager" in page
	assert "Accounts User" in page
	assert "RetailEdge Auditor" in page
	assert '"RetailEdge Cashier"' not in page
	assert '"RetailEdgeCashier"' not in page


def test_slice_does_not_add_accounting_posting():
	doc = DOC.read_text(encoding="utf-8")
	assert "Accounting posting remains out of scope" in doc
	assert "active Frappe Workflow remains authoritative" in doc
	assert "No submitted accounting document is mutated" in doc
