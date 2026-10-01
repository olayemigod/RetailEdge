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
	start = source.index("def get_cashier_expense_detail(")
	detail_endpoint = source[start:]

	assert "apply_cashier_expense_read_scope(filters)" in detail_endpoint
	assert 'frappe.get_list(' in detail_endpoint
	assert 'EXPENSE_DOCTYPE' in detail_endpoint
	assert '"name": expense_name' in detail_endpoint
	assert "ignore_permissions" not in detail_endpoint
	assert "frappe.db.commit" not in detail_endpoint
	assert "frappe.db.set_value" not in detail_endpoint


def test_cashier_expense_lists_use_shared_edgesuite_detail_viewer():
	register = _read(REGISTER_COMPONENT)
	review = _read(REVIEW_COMPONENT)
	detail = _read(DETAIL_COMPONENT)

	assert 'import CashierExpenseDetailDialog from "./CashierExpenseDetailDialog.vue";' in register
	assert 'this.openCashierExpenseDetail(sourceReference);' in register
	assert 'this.filters.view_mode === "cashier" || this.config.cashierOnly' in register
	assert 'import CashierExpenseDetailDialog from "../expense_register/CashierExpenseDetailDialog.vue";' in review
	assert 'if (column.fieldname === "name") { this.openCashierExpenseDetail(value); return; }' in review
	assert 'retailedge.cashier_expense_detail.get_cashier_expense_detail' in detail
	assert ':canUseNativeDesk="canUseNativeDesk"' in register
	assert ':canUseNativeDesk="canUseNativeDesk"' in review
	assert "apply_expense_review_action" not in detail
	assert "frappe.set_route(\"Form\", \"RetailEdge Cashier Expense\"" in detail


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


def test_cashier_expense_detail_exposes_server_derived_workflow_actions():
	source = _read(CASHIER_DETAIL)
	for expected in (
		"def _workflow_actions(",
		'"can_submit_for_review"',
		'"can_approve"',
		'"can_reject"',
		'"can_reopen"',
		'"can_refresh_posting"',
		'"can_post_to_accounts"',
		"get_cashier_expense_posting_settings",
		"CONTROLLED_POSTING_ROLES",
		"POSTING_REFRESH_ROLES",
		'frappe.has_permission(EXPENSE_DOCTYPE, "write"',
		'frappe.has_permission("Journal Entry", "read")',
		'frappe.has_permission("Journal Entry", "create")',
		'frappe.has_permission("Journal Entry", "submit")',
	):
		assert expected in source
	assert '"actions": _workflow_actions(expense)' in source
	assert "ignore_permissions" not in source


def test_edgesuite_cashier_detail_owns_review_and_accounting_actions():
	detail = _read(DETAIL_COMPONENT)
	for expected in (
		"Workflow Actions",
		"Submit for Review",
		"Approve",
		"Reject",
		"Reopen",
		"Refresh Posting Readiness",
		"Post to Accounts",
		"retailedge.cashier_expense_detail.submit_cashier_expense_for_review",
		"retailedge.api.approve_cashier_expense",
		"retailedge.api.reject_cashier_expense",
		"retailedge.api.reopen_cashier_expense",
		"retailedge.api.refresh_cashier_expense_posting_readiness",
		"retailedge.cashier_expense_accounting.post_cashier_expense_to_accounts",
		"expected_modified: this.detail.modified",
		"confirmAboveEdgeModal(",
		'reviewAction === "reject"',
	):
		assert expected in detail
	assert "frappe.prompt(" not in detail
	assert "frappe.confirm(" not in detail


def test_cashier_workflow_actions_refresh_edgesuite_reports_in_place():
	register = _read(REGISTER_COMPONENT)
	review = _read(REVIEW_COMPONENT)
	for source in (register, review):
		assert '@changed="handleCashierExpenseChanged"' in source
		assert "handleCashierExpenseChanged" in source
		assert "await this.fetchData()" in source


def test_draft_cashier_expense_can_enter_review_from_edgesuite():
	backend = _read(CASHIER_DETAIL)
	detail = _read(DETAIL_COMPONENT)
	for expected in (
		"def submit_cashier_expense_for_review(",
		'doc.has_permission("submit")',
		"doc.submit()",
		'"persistence"] = "native_submit"',
	):
		assert expected in backend
	assert "Submit for Review" in detail
	assert "submitForReview()" in detail
	assert "actions.reasons" in detail
	assert "workflowVisible" in detail
