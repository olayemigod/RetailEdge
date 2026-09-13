from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import patch

from retailedge import expense_budget_api
from retailedge import expense_dashboard
from retailedge import expense_period_context
from retailedge import expense_register


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "public/js/expense_dashboard/ExpenseDashboard.vue"
DOC = ROOT.parent / "docs/rir2f3f33_expenses_dashboard_posted_truth.md"


def test_dashboard_period_filters_force_consolidated_posted_truth():
	filters = expense_dashboard._period_filters(
		expense_dashboard.frappe._dict(
			{
				"from_date": "2026-09-01",
				"to_date": "2026-09-10",
				"expense_category": "Fuel",
			}
		),
		company="Demo Company",
		branch="Main",
	)
	assert filters["view_mode"] == "consolidated"
	assert filters["include_unposted_cashier_expenses"] == 0
	assert filters["company"] == "Demo Company"
	assert filters["branch"] == "Main"
	assert filters["expense_category"] == "Fuel"


def test_period_context_requests_same_consolidated_posted_truth():
	with (
		patch.object(
			expense_period_context,
			"require_dashboard_action",
			return_value={"can_view": True},
		),
		patch.object(
			expense_period_context,
			"get_expense_register_export",
			return_value={"rows": []},
		) as export,
	):
		expense_period_context.get_expense_period_context(
			{
				"company": "Demo Company",
				"branch": "Main",
				"to_date": "2026-09-10",
			}
		)
	assert export.call_count == 2
	for call in export.call_args_list:
		filters = call.args[0]
		assert filters["view_mode"] == "consolidated"
		assert filters["include_unposted_cashier_expenses"] == 0


def test_budget_actuals_request_same_consolidated_posted_truth():
	with (
		patch.object(
			expense_budget_api,
			"get_expense_register_export",
			return_value={"rows": []},
		) as export,
		patch.object(
			expense_budget_api,
			"build_expense_budget_insight",
			return_value={"available": False},
		),
	):
		expense_budget_api.get_expense_budget_insight(
			{
				"company": "Demo Company",
				"branch": "Main",
				"from_date": "2026-09-01",
				"to_date": "2026-09-10",
			}
		)
	filters = export.call_args.args[0]
	assert filters["view_mode"] == "consolidated"
	assert filters["include_unposted_cashier_expenses"] == 0


def test_dashboard_account_context_reuses_scoped_register_rows_without_cashier_reread():
	source = inspect.getsource(expense_dashboard._account_context)
	assert 'frappe.has_permission("Account", "read")' in source
	assert "RetailEdge Cashier Expense" not in source
	assert "frappe.get_list" not in source
	rows = [
		{
			"name": "BE:BE-1",
			"amount": 100,
			"payment_account": "Bank - D",
			"expense_account": "Fuel - D",
			"cost_center": "Main - D",
		},
		{
			"name": "GL:GL-1",
			"amount": 20,
			"payment_account": "",
			"expense_account": "Fees - D",
			"cost_center": "",
		},
	]
	with patch.object(expense_dashboard.frappe, "has_permission", return_value=True):
		assert expense_dashboard._account_context(rows) == rows


def test_cashier_and_account_breakdowns_ignore_blank_non_applicable_values():
	rows = [
		{"cashier": "cashier@example.com", "amount": 100},
		{"cashier": "", "amount": 250},
	]
	cashiers = expense_dashboard._aggregate_nonempty(rows, "cashier")
	assert len(cashiers) == 1
	assert cashiers[0]["label"] == "cashier@example.com"
	assert cashiers[0]["amount"] == 100

	account_rows = [
		{"payment_account": "Bank - D", "amount": 100},
		{"payment_account": "", "amount": -100},
	]
	funding = expense_dashboard._aggregate_account_context(
		account_rows,
		"payment_account",
	)
	assert len(funding) == 1
	assert funding[0]["label"] == "Bank - D"


def test_dashboard_metadata_identifies_consolidated_posted_truth():
	source = inspect.getsource(expense_dashboard.get_expense_dashboard_data)
	assert '"composition": "consolidated_posted_truth_expense_register"' in source
	assert '"financial_view_mode": "consolidated"' in source
	assert '"include_unposted_cashier_expenses": 0' in source


def test_expense_register_shared_status_metadata_includes_reversed():
	assert "Reversed" in expense_register._EXPENSE_STATUSES


def test_dashboard_recent_drilldown_is_source_aware_and_edgesuite_first():
	source = PAGE.read_text(encoding="utf-8")
	assert '@click="openExpense(row)"' in source
	assert 'row.source_doctype === "RetailEdge Business Expense"' in source
	assert 'frappe.route_options = { business_expense: row.source_reference || "" }' in source
	assert 'frappe.set_route("business-expenses")' in source
	assert 'row.source_doctype === "Purchase Invoice"' in source
	assert 'frappe.set_route("purchase-register")' in source
	assert "canUseNativeDesk" in source
	assert 'frappe.set_route("Form", row.source_doctype, row.source_reference)' in source
	assert 'frappe.set_route("Form", "RetailEdge Cashier Expense"' not in source


def test_dashboard_filters_are_pinned_to_financial_truth_after_context_load():
	source = PAGE.read_text(encoding="utf-8")
	assert 'view_mode: "consolidated"' in source
	assert "include_unposted_cashier_expenses: 0" in source
	assert 'this.filters.view_mode = "consolidated"' in source
	assert "this.filters.include_unposted_cashier_expenses = 0" in source


def test_contract_preserves_single_financial_authority_and_no_dashboard_redesign():
	doc = DOC.read_text(encoding="utf-8")
	assert "Expense Register remains the single financial row authority" in doc
	assert "Business Expense Reversal" in doc
	assert "No new dashboard query engine" in doc
	assert "route promotion remains unchanged" in doc
	assert "Manual browser/persona QA remains deferred" in doc
