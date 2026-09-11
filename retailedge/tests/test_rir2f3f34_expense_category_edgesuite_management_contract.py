from __future__ import annotations

import inspect
from pathlib import Path

from retailedge import expense_category_setup


ROOT = Path(__file__).resolve().parents[1]
SETUP_BACKEND = ROOT / "retailedge/page/retailedge_setup/retailedge_setup.py"
SETUP_UI = ROOT / "public/js/retailedge_setup/RetailEdgeSetup.vue"
MANAGER_UI = ROOT / "public/js/retailedge_setup/ExpenseCategoryManager.vue"
CATEGORY_CONTROLLER = (
	ROOT
	/ "retailedge/doctype/retailedge_expense_category/retailedge_expense_category.py"
)
DOC = ROOT.parent / "docs/rir2f3f34_expense_category_edgesuite_management.md"


def test_setup_resource_declares_edgesuite_expense_category_manager():
	source = SETUP_BACKEND.read_text(encoding="utf-8")
	assert '"key": "expense-categories"' in source
	assert '"doctype": "RetailEdge Expense Category"' in source
	assert '"manager": "expense-categories"' in source
	assert "Business Expenses, Cashier Expenses and expense reporting" in source


def test_category_manager_reads_are_permission_aware_and_bounded():
	source = inspect.getsource(expense_category_setup)
	assert "MAX_CATEGORY_ROWS = 1000" in source
	assert "MAX_SEARCH_RESULTS = 20" in source
	assert "frappe.get_list(" in source
	assert "limit_page_length=MAX_CATEGORY_ROWS + 1" in source
	assert "More than {0} Expense Categories match this view" in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source


def test_category_create_and_edit_keep_native_permissions_authoritative():
	source = inspect.getsource(expense_category_setup.save_expense_category)
	assert 'frappe.has_permission(EXPENSE_CATEGORY_DOCTYPE, "create")' in source
	assert 'doc.has_permission("write")' in source
	assert "_assert_modified(doc, expected_modified)" in source
	assert "frappe.new_doc(EXPENSE_CATEGORY_DOCTYPE)" in source
	assert "doc.insert()" in source
	assert "doc.save()" in source
	assert "doc.db_update" not in source
	assert "ignore_permissions" not in source


def test_category_name_is_stable_in_edgesuite_edit_flow():
	source = inspect.getsource(expense_category_setup.save_expense_category)
	assert "requested_name" in source
	assert "Category Name is stable after creation in RetailEdge Setup" in source
	manager = MANAGER_UI.read_text(encoding="utf-8")
	assert ':disabled="Boolean(editingName)"' in manager
	assert "rename" not in inspect.getsource(expense_category_setup.save_expense_category).lower()


def test_new_edgesuite_category_requires_explicit_company():
	source = inspect.getsource(expense_category_setup.save_expense_category)
	assert "Company is required when creating an Expense Category in RetailEdge Setup." in source
	manager = MANAGER_UI.read_text(encoding="utf-8")
	assert "Category Name and Company are required." in manager


def test_account_and_cost_center_queries_are_company_dependent_and_filtered():
	source = inspect.getsource(
		expense_category_setup.search_expense_category_manager_options
	)
	assert '"root_type": "Expense"' in source
	assert '"is_group": 0' in source
	assert '"disabled": 0' in source
	assert '"company": company' in source
	assert "Select Company before choosing accounting defaults." in source
	manager = MANAGER_UI.read_text(encoding="utf-8")
	assert "if (!this.form.company) return [];" in manager
	assert 'return this.search("expense_account", txt, this.form.company)' in manager
	assert 'return this.search("cost_center", txt, this.form.company)' in manager


def test_company_change_clears_accounting_dependents():
	manager = MANAGER_UI.read_text(encoding="utf-8")
	assert 'this.form.expense_account = ""' in manager
	assert 'this.form.default_cost_center = ""' in manager
	assert "selectFormCompany(option)" in manager
	assert "clearFormCompany()" in manager


def test_server_revalidates_link_permissions_and_company_consistency():
	source = inspect.getsource(expense_category_setup._validate_link_permissions)
	assert '_assert_named_permission("Company", company, "read")' in source
	assert '_assert_named_permission("Account", expense_account, "read")' in source
	assert '_assert_named_permission("Cost Center", default_cost_center, "read")' in source
	assert "Expense Account belongs to another Company." in source
	assert "Default Cost Center belongs to another Company." in source
	controller = CATEGORY_CONTROLLER.read_text(encoding="utf-8")
	assert "def _validate_expense_account" in controller
	assert "root_type" in controller
	assert "def _validate_default_cost_center" in controller


def test_setup_consumes_expense_category_route_options_inside_edgesuite():
	source = SETUP_UI.read_text(encoding="utf-8")
	assert 'options.setup_resource === "expense-categories"' in source
	assert "options.expense_category" in source
	assert "options.setup_action" in source
	assert "this.openExpenseCategoryManager(" in source
	assert "frappe.route_options = null" in source
	assert '<ExpenseCategoryManager' in source


def test_expense_category_resource_does_not_use_native_list_or_new_form():
	source = SETUP_UI.read_text(encoding="utf-8")
	assert 'resource?.manager === "expense-categories"' in source
	assert 'resource.manager === "expense-categories"' in source
	assert 'this.openExpenseCategoryManager("list")' in source
	assert 'this.openExpenseCategoryManager("new")' in source
	manager = MANAGER_UI.read_text(encoding="utf-8")
	assert "window.open(" not in manager
	assert 'frappe.set_route("Form", "RetailEdge Expense Category"' not in manager


def test_manager_supports_list_create_edit_and_deactivation_without_delete():
	source = MANAGER_UI.read_text(encoding="utf-8")
	assert "get_expense_categories" in source
	assert "get_expense_category" in source
	assert "save_expense_category" in source
	assert "Add Category" in source
	assert "Edit Expense Category" in source
	assert "Active category" in source
	assert "delete" not in source.lower()


def test_f3f34_contract_preserves_master_and_accounting_truth():
	doc = DOC.read_text(encoding="utf-8")
	assert "RetailEdge Expense Category remains the system of record" in doc
	assert "does not broaden DocType permissions" in doc
	assert "No accounting document is created or mutated" in doc
	assert "Other RetailEdge Setup resources remain unchanged" in doc
	assert "Manual browser/persona QA remains deferred" in doc
