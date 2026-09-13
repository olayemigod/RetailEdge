from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import business_expense_register as consolidated
from retailedge import expense_register


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/expense_register/ExpenseRegisterReport.vue"
DOC = ROOT.parent / "docs/rir2f3f26_consolidated_business_expense_register.md"


def test_consolidated_view_is_privileged_and_explicit():
	with patch.object(
		consolidated.frappe,
		"get_roles",
		return_value=["RetailEdge Manager"],
	):
		assert consolidated.can_view_consolidated_business_expenses(
			"manager@example.com"
		)
	with patch.object(
		consolidated.frappe,
		"get_roles",
		return_value=["RetailEdge Cashier"],
	):
		assert not consolidated.can_view_consolidated_business_expenses(
			"cashier@example.com"
		)


def test_expense_register_defaults_privileged_users_to_consolidated_without_changing_cashier_api():
	source = inspect.getsource(expense_register)
	assert '"view_mode": "consolidated" if can_view_consolidated_business_expenses' in source
	assert "if _use_consolidated_view(filters):" in source
	assert "get_consolidated_expense_register(" in source
	assert "get_consolidated_expense_export(filters)" in source


def test_accounting_sources_are_expense_account_only_and_exclude_cogs_vouchers():
	source = inspect.getsource(consolidated)
	assert '"Purchase Invoice": "Supplier / Business"' in source
	assert '"Expense Claim": "Employee Expense"' in source
	assert '"Journal Entry": "Accounting Adjustment"' in source
	assert "acc.root_type = 'Expense'" in source
	assert "Sales Invoice" not in consolidated._ACCOUNTING_VOUCHER_TYPES
	assert "POS Invoice" not in consolidated._ACCOUNTING_VOUCHER_TYPES
	assert "Stock Entry" not in consolidated._ACCOUNTING_VOUCHER_TYPES


def test_cashier_posting_reference_is_deduplicated_from_accounting_rows():
	source = inspect.getsource(consolidated)
	assert "ce_post.posting_reference_type = gle.voucher_type" in source
	assert "ce_post.posting_reference = gle.voucher_no" in source
	assert 'clauses.append("ce_post.name IS NULL")' in source


def test_restricted_branch_scope_fails_closed_for_unattributed_accounting_rows():
	clauses = []
	values = []
	consolidated._apply_branch_sql(
		clauses,
		values,
		branch_expression="branch_expression",
		branch_scope={
			"global_access": False,
			"effective_branches": [],
		},
	)
	assert "1 = 0" in clauses


def test_expense_register_ui_exposes_consolidated_and_cashier_only_modes():
	source = COMPONENT.read_text(encoding="utf-8")
	assert "Consolidated business expenses" in source
	assert "Cashier / POS expenses only" in source
	assert "All expense sources" in source
	assert "consolidatedViewAvailable" in source
	assert "sourceTypes" in source


def test_contract_preserves_accounting_truth_and_frontline_scope():
	doc = DOC.read_text(encoding="utf-8")
	assert "No duplicate expense ledger is created" in doc
	assert "Cashier-only users keep the existing self-scoped Cashier Expense view" in doc
	assert "unattributed accounting rows are company-wide only" in doc
