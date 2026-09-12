from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import expense_review


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/expense_review/ExpenseReviewReport.vue"


def test_cashier_option_filters_reuse_authoritative_cashier_expense_read_scope():
	with patch.object(
		expense_review,
		"apply_cashier_expense_read_scope",
		return_value={
			"company": "Scope Co",
			"branch": "Branch A",
			"expense_date": ["between", ["2026-09-01", "2026-09-12"]],
		},
	) as apply_scope:
		filters = expense_review._expense_review_cashier_filters(
			company="Scope Co",
			branch="Branch A",
			from_date="2026-09-01",
			to_date="2026-09-12",
		)

	apply_scope.assert_called_once_with(
		{
			"company": "Scope Co",
			"branch": "Branch A",
			"expense_date": ["between", ["2026-09-01", "2026-09-12"]],
		}
	)
	assert filters["company"] == "Scope Co"
	assert filters["branch"] == "Branch A"


def test_cashier_option_filters_support_one_sided_review_dates():
	with patch.object(
		expense_review,
		"apply_cashier_expense_read_scope",
		side_effect=lambda filters: filters,
	):
		from_only = expense_review._expense_review_cashier_filters(
			company="Scope Co",
			from_date="2026-09-01",
		)
		to_only = expense_review._expense_review_cashier_filters(
			company="Scope Co",
			to_date="2026-09-12",
		)

	assert from_only["expense_date"] == [">=", "2026-09-01"]
	assert to_only["expense_date"] == ["<=", "2026-09-12"]


def test_cashier_options_originate_from_scoped_cashier_expense_evidence():
	expense_rows = [
		frappe._dict(cashier="cashier1@example.com"),
		frappe._dict(cashier="cashier2@example.com"),
	]
	user_rows = [
		frappe._dict(name="cashier1@example.com", full_name="Cashier One"),
	]
	with (
		patch.object(expense_review.frappe, "get_list", side_effect=[expense_rows, user_rows]) as get_list,
	):
		result = expense_review._search_scoped_expense_cashiers(
			"Cashier",
			{"company": "Scope Co", "branch": "Branch A"},
		)

	expense_call = get_list.call_args_list[0]
	assert expense_call.args[0] == "RetailEdge Cashier Expense"
	assert expense_call.kwargs["filters"] == {"company": "Scope Co", "branch": "Branch A"}
	assert expense_call.kwargs["fields"] == ["cashier"]
	assert expense_call.kwargs["group_by"] == "cashier"
	assert expense_call.kwargs["limit_page_length"] == expense_review.MAX_CASHIER_OPTION_SCAN + 1

	user_call = get_list.call_args_list[1]
	assert user_call.args[0] == "User"
	assert user_call.kwargs["filters"] == {
		"enabled": 1,
		"name": ["in", ["cashier1@example.com", "cashier2@example.com"]],
	}
	assert result == [
		{
			"value": "cashier1@example.com",
			"label": "Cashier One",
			"description": "cashier1@example.com",
		}
	]


def test_cashier_option_search_passes_company_branch_and_dates_to_scope():
	with (
		patch.object(
			expense_review,
			"_expense_review_cashier_filters",
			return_value={"company": "Scope Co", "branch": "Branch A"},
		) as build_filters,
		patch.object(
			expense_review,
			"_search_scoped_expense_cashiers",
			return_value=[],
		) as search,
	):
		expense_review.search_expense_review_options(
			"cashier",
			"cash",
			company="Scope Co",
			branch="Branch A",
			from_date="2026-09-01",
			to_date="2026-09-12",
		)

	build_filters.assert_called_once_with(
		company="Scope Co",
		branch="Branch A",
		from_date="2026-09-01",
		to_date="2026-09-12",
	)
	search.assert_called_once_with(
		"cash",
		{"company": "Scope Co", "branch": "Branch A"},
	)


def test_active_expense_review_page_passes_scope_and_clears_stale_cashier():
	source = VUE.read_text(encoding="utf-8")

	search_start = source.index("async searchOptions")
	search_block = source[search_start : search_start + 700]
	assert "branch: this.filters.branch" in search_block
	assert "from_date: this.filters.from_date" in search_block
	assert "to_date: this.filters.to_date" in search_block

	assert '@change="onReviewDateChange"' in source

	company_start = source.index("onCompanySelected(option)")
	company_block = source[company_start : company_start + 500]
	assert "this.clearCashier();" in company_block

	branch_start = source.index("onBranchSelected(option)")
	branch_block = source[branch_start : branch_start + 500]
	assert "this.clearCashier();" in branch_block

	clear_branch_start = source.index("clearBranch()")
	clear_branch_block = source[clear_branch_start : clear_branch_start + 400]
	assert "this.clearCashier();" in clear_branch_block

	date_start = source.index("onReviewDateChange()")
	date_block = source[date_start : date_start + 300]
	assert "this.clearCashier();" in date_block


def test_g2g26_does_not_rewire_review_mutations_or_add_bypasses():
	source = Path(expense_review.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
	assert "mark_cashier_expense_included_for_daily_audit" in source
	assert "mark_cashier_expense_excluded_from_daily_audit" in source
	assert "mark_cashier_expense_needs_clarification" in source
