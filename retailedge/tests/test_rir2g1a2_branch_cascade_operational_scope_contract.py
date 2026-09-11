from __future__ import annotations

import inspect
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import cash_custody
from retailedge import guided_cash_transfer as cash_transfer
from retailedge import guided_payment as payment
from retailedge import professional_delivery as delivery
from retailedge import professional_sales_invoice as sales_invoice
from retailedge import professional_sales_order as sales_order
from retailedge import standard_customer_payment_submit as customer_submit
from retailedge import standard_supplier_payment_submit as supplier_submit
from retailedge.retailedge.doctype.retailedge_cashier_expense import (
	retailedge_cashier_expense as cashier_expense_doc,
)


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _raises(error_type):
	try:
		yield
	except error_type:
		return
	raise AssertionError(f"Expected {error_type.__name__} to be raised")


def _restricted(branches):
	return {
		"company": "Demo Company",
		"restricted": True,
		"allowed_branches": list(branches),
		"source": "branch_assignment",
	}


def _unrestricted():
	return {
		"company": "Demo Company",
		"restricted": False,
		"allowed_branches": [],
		"source": "global",
	}


def test_guided_payment_branch_search_restricted_zero_fails_closed():
	with patch.object(payment, "get_operational_branch_scope", return_value=_restricted([])):
		filters = payment._branch_search_filters("Demo Company", "pay@example.com")

	assert filters["name"] == "__never__"


def test_guided_payment_restricted_single_blank_can_auto_resolve():
	with (
		patch.object(payment, "get_operational_branch_scope", return_value=_restricted(["Lagos"])),
		patch.object(
			payment,
			"resolve_operational_branch",
			return_value={**_restricted(["Lagos"]), "branch": "Lagos"},
		) as resolve_branch,
	):
		branch = payment._resolve_guided_payment_branch(
			company="Demo Company",
			branch="",
			user="pay@example.com",
			require_when_restricted=True,
		)

	assert branch == "Lagos"
	resolve_branch.assert_called_once_with("Demo Company", "", user="pay@example.com")


def test_guided_payment_ambiguous_or_zero_blank_write_fails_closed():
	for branches in ([], ["Lagos", "Abuja"]):
		with (
			patch.object(payment, "get_operational_branch_scope", return_value=_restricted(branches)),
			patch.object(
				payment,
				"resolve_operational_branch",
				side_effect=frappe.PermissionError("branch required"),
			) as resolve_branch,
			_raises(frappe.PermissionError),
		):
			payment._resolve_guided_payment_branch(
				company="Demo Company",
				branch="",
				user="pay@example.com",
				require_when_restricted=True,
			)

		resolve_branch.assert_called_once_with("Demo Company", "", user="pay@example.com")


def test_guided_payment_reference_paths_revalidate_operational_scope():
	search_source = inspect.getsource(payment._search_outstanding_references)
	snapshot_source = inspect.getsource(payment._get_reference_snapshot)
	details_source = inspect.getsource(payment.get_simple_payment_reference_details)
	create_source = inspect.getsource(payment.create_simple_payment_draft)

	assert "_resolve_guided_payment_branch(" in search_source
	assert "resolve_operational_branch(" in snapshot_source
	assert "_resolve_guided_payment_branch(" in details_source
	assert "require_when_restricted=True" in details_source
	assert "_resolve_guided_payment_branch(" in create_source
	assert "require_when_restricted=True" in create_source


def test_guided_cash_transfer_restricted_single_blank_can_auto_resolve():
	with (
		patch.object(cash_transfer, "get_operational_branch_scope", return_value=_restricted(["Lagos"])),
		patch.object(
			cash_transfer,
			"resolve_operational_branch",
			return_value={**_restricted(["Lagos"]), "branch": "Lagos"},
		) as resolve_branch,
	):
		branch = cash_transfer._resolve_cash_transfer_branch(
			company="Demo Company",
			branch="",
			user="cash@example.com",
			require_when_restricted=True,
		)

	assert branch == "Lagos"
	resolve_branch.assert_called_once_with("Demo Company", "", user="cash@example.com")


def test_guided_cash_transfer_unrestricted_blank_preserves_company_wide_behavior():
	with patch.object(cash_transfer, "get_operational_branch_scope", return_value=_unrestricted()):
		assert (
			cash_transfer._resolve_cash_transfer_branch(
				company="Demo Company",
				branch="",
				user="cash@example.com",
				require_when_restricted=True,
			)
			== ""
		)


def test_guided_cash_transfer_branch_search_and_write_use_operational_scope():
	source = inspect.getsource(cash_transfer)
	assert "get_operational_branch_scope" in source
	assert "resolve_operational_branch" in source
	assert "get_user_allowed_branches" not in source
	assert "user_has_global_branch_access" not in source
	assert "validate_user_branch_access" not in source
	create_source = inspect.getsource(cash_transfer.create_simple_cash_transfer_draft)
	assert "_resolve_cash_transfer_branch(" in create_source
	assert "require_when_restricted=True" in create_source


def test_cash_deposit_revalidates_shift_branch_with_operational_authority():
	source = inspect.getsource(cash_custody)
	assert "_validate_cash_custody_branch" in source
	assert "resolve_operational_branch" in source
	assert "get_operational_branch_scope" in source
	assert "validate_user_branch_access" not in source
	for target in (
		cash_custody.get_cash_deposit_context,
		cash_custody.create_cash_deposit_draft,
		cash_custody.validate_cash_deposit_before_submit,
	):
		assert "_validate_cash_custody_branch(" in inspect.getsource(target)


def test_cashier_expense_document_revalidates_derived_branch_operationally():
	source = inspect.getsource(cashier_expense_doc)
	assert "get_operational_branch_scope" in source
	assert "resolve_operational_branch" in source
	assert "validate_operational_branch_scope" in source
	validate_source = inspect.getsource(cashier_expense_doc.RetailEdgeCashierExpense.validate)
	assert "self.validate_operational_branch_scope()" in validate_source


def test_standard_payment_completion_uses_operational_scope_not_legacy_branch_gate():
	for module in (customer_submit, supplier_submit):
		source = inspect.getsource(module)
		assert "get_operational_branch_scope" in source
		assert "resolve_operational_branch" in source
		assert "user_has_global_branch_access" not in source
		assert "validate_user_branch_access" not in source
		validate_source = inspect.getsource(module._validate_payment_branch)
		assert "resolve_operational_branch(" in validate_source
		assert "has no Branch attribution for your restricted access" in validate_source


def test_mapped_selling_paths_revalidate_explicit_branch_with_operational_authority():
	for module in (sales_order, delivery, sales_invoice):
		source = inspect.getsource(module)
		assert "_validate_stored_operational_branch" in source
		assert "validate_user_branch_access" not in source


def test_frontend_payment_branch_change_invalidates_reference_and_review_state():
	source = (
		ROOT
		/ "public/js/retailedge_business_hub/SimplePaymentDialog.vue"
	).read_text(encoding="utf-8")
	start = source.index("setBranch(next)")
	end = source.index("async setModeOfPayment", start)
	method = source[start:end]
	assert "this.values.references = [emptyReference()]" in method
	assert "this.customerReview = null" in method
	assert "this.supplierReview = null" in method


def test_frontend_cash_transfer_does_not_fake_branch_exclusive_accounts():
	source = (
		ROOT
		/ "public/js/retailedge_business_hub/SimpleCashTransferDialog.vue"
	).read_text(encoding="utf-8")
	start = source.index("setBranch(option)")
	end = source.index("setFromAccount", start)
	method = source[start:end]
	assert "this.values.branch = optionValue(option)" in method
	assert "from_account" not in method
	assert "to_account" not in method


def test_frontend_stock_and_selling_branch_cascade_remains_parent_first():
	paths = [
		ROOT / "public/js/retailedge_business_hub/SimpleStockAdjustmentDialog.vue",
		ROOT / "public/js/retailedge_business_hub/SimpleSalesInvoiceDialog.vue",
		ROOT / "public/js/retailedge_business_hub/SimplePurchaseInvoiceDialog.vue",
		ROOT / "public/js/professional_selling/ProfessionalQuotationDialog.vue",
		ROOT / "public/js/professional_selling/ProfessionalSalesOrderDialog.vue",
		ROOT / "public/js/professional_selling/ProfessionalSalesInvoiceDialog.vue",
	]
	for path in paths:
		source = path.read_text(encoding="utf-8")
		start = source.index("setBranch(")
		method = source[start : start + 2200]
		assert 'warehouse = ""' in method or 'warehouse = "";' in method
		assert "resolveBranchWarehouse" in method


def test_branch_cascade_hardening_does_not_write_accounting_or_stock_truth_directly():
	for module in (
		payment,
		cash_transfer,
		cash_custody,
		customer_submit,
		supplier_submit,
		sales_order,
		delivery,
		sales_invoice,
	):
		source = inspect.getsource(module)
		assert "ignore_permissions=True" not in source
		assert "frappe.db.commit()" not in source
		assert 'frappe.new_doc("GL Entry")' not in source
		assert 'frappe.new_doc("Stock Ledger Entry")' not in source
