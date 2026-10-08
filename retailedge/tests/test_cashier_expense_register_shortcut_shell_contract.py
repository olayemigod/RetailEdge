from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE_JS = ROOT / "retailedge/page/cashier_expenses/cashier_expenses.js"
REPORT_VUE = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"


def _page_source() -> str:
	return PAGE_JS.read_text(encoding="utf-8")


def _report_source() -> str:
	return REPORT_VUE.read_text(encoding="utf-8")


def test_expense_register_shortcut_is_not_rendered_in_native_frappe_page_header():
	source = _page_source()
	assert "addExpenseRegisterButton" not in source
	assert "page.add_inner_button" not in source
	assert "can_open_expense_register" not in source


def test_cashier_expenses_exposes_permission_aware_register_shortcut_inside_edgesuite_actions():
	source = _report_source()
	assert '<template #actions>' in source
	assert 'v-if="config.cashierOnly && hasPageTarget(\'expense-register\')"' in source
	assert '@click="openExpenseRegister">Expense Register</button>' in source
	assert 'openExpenseRegister()' in source
	assert 'frappe.set_route("expense-register");' in source


def test_cashier_expense_primary_and_setup_actions_remain_available():
	source = _report_source()
	assert '@click="openExpenseCategories">Expense Categories</button>' in source
	assert 'config.cashierOnly ? "Record Cashier Expense"' in source
