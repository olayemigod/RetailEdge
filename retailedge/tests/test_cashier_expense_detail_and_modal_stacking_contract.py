from __future__ import annotations

from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]
EXPENSE_REGISTER = APP_ROOT / "expense_register.py"
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
	source = _read(EXPENSE_REGISTER)
	start = source.index("def get_cashier_expense_detail(")
	end = source.index("\n@frappe.whitelist()\ndef get_expense_register_context", start)
	detail_endpoint = source[start:end]

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
	assert 'retailedge.expense_register.get_cashier_expense_detail' in detail
	assert ':canUseNativeDesk="canUseNativeDesk"' in register
	assert ':canUseNativeDesk="canUseNativeDesk"' in review
	assert "apply_expense_review_action" not in detail
	assert "save" not in detail.lower()


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
