from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
CASHIER_DETAIL = APP_ROOT / "cashier_expense_detail.py"
REGISTER_COMPONENT = APP_ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
DETAIL_COMPONENT = APP_ROOT / "public/js/expense_register/CashierExpenseDetailDialog.vue"
REVIEW_COMPONENT = APP_ROOT / "public/js/expense_review/ExpenseReviewReport.vue"
GUIDED_UTILS = APP_ROOT / "public/js/retailedge_business_hub/guidedEntryUtils.js"
QUICK_DIALOGS = (
	"SimpleCashDepositDialog.vue",
	"SimpleCashTransferDialog.vue",
	"SimpleCashierExpenseDialog.vue",
	"SimplePaymentDialog.vue",
	"SimplePurchaseInvoiceDialog.vue",
	"SimpleSalesInvoiceDialog.vue",
	"SimpleStockAdjustmentDialog.vue",
	"SimpleStockTransferDialog.vue",
)


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_cashier_expense_detail_endpoint_is_permission_and_branch_scoped():
	source = _read(CASHIER_DETAIL)

	assert "apply_cashier_expense_read_scope(filters)" in source
	assert 'frappe.get_list(' in source
	assert 'EXPENSE_DOCTYPE' in source
	assert '"name": expense_name' in source
	assert "ignore_permissions" not in source
	assert "frappe.db.commit" not in source
	assert "frappe.db.set_value" not in source


def test_cashier_expense_lists_use_shared_edgesuite_workflow_form():
	register = _read(REGISTER_COMPONENT)
	review = _read(REVIEW_COMPONENT)
	detail = _read(DETAIL_COMPONENT)
	backend = _read(CASHIER_DETAIL)

	assert 'import CashierExpenseDetailDialog from "./CashierExpenseDetailDialog.vue";' in register
	assert 'this.openCashierExpenseDetail(sourceReference);' in register
	assert 'this.filters.view_mode === "cashier" || this.config.cashierOnly' in register
	assert 'import CashierExpenseDetailDialog from "../expense_register/CashierExpenseDetailDialog.vue";' in review
	assert 'if (column.fieldname === "name") { this.openCashierExpenseDetail(value); return; }' in review
	assert 'retailedge.cashier_expense_detail.get_cashier_expense_detail' in detail
	assert 'retailedge.cashier_expense_detail.apply_cashier_expense_workflow_action' in detail
	assert '@updated="fetchData"' in register
	assert '@updated="fetchData"' in review
	assert 'Advanced: Open Full Record' not in detail
	assert 'frappe.set_route("Form", "RetailEdge Cashier Expense"' not in detail
	assert "apply_cashier_expense_workflow_action" in backend
	assert "submit_cashier_expense" in backend
	assert "approve_cashier_expense" in backend
	assert "reject_cashier_expense" in backend
	assert "reopen_cashier_expense" in backend
	assert "refresh_cashier_expense_posting_readiness" in backend
	assert "post_cashier_expense_to_accounts" in backend


def test_nested_quick_entry_confirmations_use_elevated_shared_helper():
	utils = _read(GUIDED_UTILS)
	assert "export function confirmAboveEdgeModal" in utils
	assert 'wrapper.style.setProperty("z-index", "100000", "important")' in utils
	assert 'backdrop.style.setProperty("z-index", "99990", "important")' in utils
	assert 'document.querySelectorAll(".modal")' in utils
	assert 'data-retailedge-overlay-confirm' in utils

	for filename in QUICK_DIALOGS:
		source = _read(APP_ROOT / "public/js/retailedge_business_hub" / filename)
		assert "confirmAboveEdgeModal(" in source, filename
		assert "frappe.confirm(" not in source, filename
		assert "confirmAboveEdgeModal" in source.split("</script>", 1)[0], filename



def test_cashier_expense_workflow_does_not_bypass_document_permissions():
	source = (APP_ROOT / "cashier_expense.py").read_text(encoding="utf-8")
	for function_name in ("approve_cashier_expense", "reject_cashier_expense", "reopen_cashier_expense"):
		start = source.index(f"def {function_name}(")
		next_def = source.find("\ndef ", start + 1)
		block = source[start:] if next_def == -1 else source[start:next_def]
		assert "doc.has_permission(\"write\")" in block
		assert "doc.save()" in block
		assert "ignore_permissions=True" not in block


def test_cashier_expense_quick_create_has_no_native_form_escape():
	quick = _read(APP_ROOT / "public/js/retailedge_business_hub/SimpleCashierExpenseDialog.vue")
	hub = _read(APP_ROOT / "public/js/retailedge_business_hub/RetailEdgeBusinessHub.vue")

	assert "Open Full Form" not in quick
	assert "openFullForm()" not in quick
	assert "open-native" not in quick
	assert "nativeFallbackEnabled" not in quick
	assert "openNativeCashierExpense" not in hub
	assert 'CashierExpenseDetailDialog' in hub
	assert ':expenseName="cashierExpenseWorkflowName"' in hub


def test_cashier_expense_accounting_posts_through_submitted_journal_entry_only():
	accounting = _read(APP_ROOT / "cashier_expense_accounting.py")
	settings_json = _read(
		APP_ROOT / "retailedge/doctype/retailedge_settings/retailedge_settings.json"
	)
	settings_py = _read(
		APP_ROOT / "retailedge/doctype/retailedge_settings/retailedge_settings.py"
	)

	assert 'POSTING_DOCUMENT_TYPE = "Journal Entry"' in accounting
	assert 'journal = frappe.new_doc(POSTING_DOCUMENT_TYPE)' in accounting
	assert 'journal.insert()' in accounting
	assert 'journal.has_permission("submit")' in accounting
	assert 'journal.submit()' in accounting
	assert '"debit_in_account_currency": amount' in accounting
	assert '"credit_in_account_currency": amount' in accounting
	assert '"options": "Journal Entry"' in settings_json
	assert 'Journal Entry posting only' in settings_py
	assert '"Payment Entry"' not in settings_json[
		settings_json.index('"fieldname": "cashier_expense_posting_document_type"') - 300:
		settings_json.index('"fieldname": "cashier_expense_posting_document_type"') + 500
	]


def test_guided_customer_and_supplier_payments_submit_native_payment_entries():
	customer = _read(APP_ROOT / "standard_customer_payment_submit.py")
	supplier = _read(APP_ROOT / "standard_supplier_payment_submit.py")

	assert "def submit_standard_customer_payment(" in customer
	assert "doc.submit()" in customer
	assert 'source_of_truth": "ERPNext Payment Entry submit"' in customer
	assert "def submit_standard_supplier_payment(" in supplier
	assert "doc.submit()" in supplier
	assert 'source_of_truth": "ERPNext Payment Entry submit"' in supplier
