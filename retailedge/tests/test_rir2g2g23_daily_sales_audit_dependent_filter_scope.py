from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import daily_sales_audit_page as page


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/daily_sales_audit/DailySalesAuditReport.vue"


def test_pos_profile_search_reuses_existing_operational_pos_scope():
	with (
		patch.object(page, "_resolve_pos_option_branch_scope", return_value={"restricted": True, "branches": ["Branch A"]}) as resolve_scope,
		patch.object(page, "_search_scoped_pos_profiles", return_value=[{"value": "POS-A", "label": "POS-A"}]) as search,
	):
		result = page.search_daily_sales_audit_page_options(
			"pos_profile",
			"POS",
			company="Scope Co",
			branch="Branch A",
		)

	resolve_scope.assert_called_once_with("Scope Co", "Branch A")
	search.assert_called_once_with("%POS%", "Scope Co", {"restricted": True, "branches": ["Branch A"]})
	assert result == [{"value": "POS-A", "label": "POS-A"}]


def test_cashier_search_reuses_existing_branch_and_pos_profile_scope():
	with (
		patch.object(page, "_resolve_pos_option_branch_scope", return_value={"restricted": True, "branches": ["Branch A"]}) as resolve_scope,
		patch.object(
			page,
			"_search_scoped_cashiers",
			return_value=[{"value": "cashier@example.com", "label": "Cashier One", "description": "cashier@example.com"}],
		) as search,
	):
		result = page.search_daily_sales_audit_page_options(
			"cashier",
			"cash",
			company="Scope Co",
			branch="Branch A",
			pos_profile="POS-A",
		)

	resolve_scope.assert_called_once_with("Scope Co", "Branch A")
	search.assert_called_once_with("%cash%", "Scope Co", {"restricted": True, "branches": ["Branch A"]}, pos_profile="POS-A")
	assert result[0]["value"] == "cashier@example.com"


def test_branch_search_stays_on_existing_permission_aware_branch_query():
	with patch.object(page, "branch_query", return_value=[["Branch A"]]) as branch_query:
		result = page.search_daily_sales_audit_page_options(
			"branch",
			"A",
			company="Scope Co",
		)

	branch_query.assert_called_once_with(
		"Branch",
		"A",
		"name",
		0,
		page.MAX_LINK_RESULTS,
		{"company": "Scope Co"},
	)
	assert result == [{"value": "Branch A", "label": "Branch A"}]


def test_active_daily_audit_page_passes_dependent_context_and_clears_stale_values():
	source = VUE.read_text(encoding="utf-8")

	assert "branch: this.filters.branch" in source
	assert "pos_profile: this.filters.pos_profile" in source
	assert '@select="onPosProfileSelected"' in source
	assert '@clear="clearPosProfile"' in source

	assert 'this.filters.pos_profile = "";' in source
	assert 'this.filters.cashier = "";' in source
	assert 'this.cashierLabel = "";' in source

	company_start = source.index("onCompanySelected(option)")
	company_block = source[company_start : company_start + 500]
	assert 'this.filters.branch = "";' in company_block
	assert 'this.filters.pos_profile = "";' in company_block
	assert "this.clearCashier();" in company_block

	branch_start = source.index("onBranchSelected(option)")
	branch_block = source[branch_start : branch_start + 400]
	assert 'this.filters.pos_profile = "";' in branch_block
	assert "this.clearCashier();" in branch_block

	profile_start = source.index("onPosProfileSelected(option)")
	profile_block = source[profile_start : profile_start + 300]
	assert "this.clearCashier();" in profile_block


def test_daily_audit_option_scope_does_not_add_permission_or_transaction_bypass():
	source = Path(page.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
	assert "frappe.db.sql" not in source
