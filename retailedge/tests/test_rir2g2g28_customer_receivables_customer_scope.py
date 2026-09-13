from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import customer_receivables as receivables


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/customer_receivables/CustomerReceivablesReport.vue"


def test_customer_option_filters_reuse_receivables_branch_authority():
	with (
		patch.object(receivables, "_assert_report_access") as assert_access,
		patch.object(
			receivables,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", ["in", ["Branch A", "Branch B"]]),
		) as branch_scope,
	):
		filters = receivables._receivable_customer_invoice_filters(
			company="Scope Co",
			branch="",
			customer_group="Retail",
		)

	assert filters == {
		"docstatus": 1,
		"company": "Scope Co",
		"is_return": 0,
		"outstanding_amount": [">", 0],
		"customer_group": "Retail",
		"retailedge_branch": ["in", ["Branch A", "Branch B"]],
	}
	scope_filters = assert_access.call_args.args[0]
	assert scope_filters.company == "Scope Co"
	assert scope_filters.customer_group == "Retail"
	branch_scope.assert_called_once_with(scope_filters)


def test_customer_options_originate_from_current_outstanding_invoice_evidence():
	invoice_rows = [
		frappe._dict(customer="CUST-1", customer_name="Alpha", customer_group="Retail"),
		frappe._dict(customer="CUST-2", customer_name="Beta", customer_group="Retail"),
	]
	customer_rows = [
		frappe._dict(name="CUST-1", customer_name="Alpha", customer_group="Retail"),
	]
	with patch.object(
		receivables.frappe,
		"get_list",
		side_effect=[invoice_rows, customer_rows],
	) as get_list:
		result = receivables._search_receivable_customers(
			"a",
			{
				"docstatus": 1,
				"company": "Scope Co",
				"is_return": 0,
				"outstanding_amount": [">", 0],
				"retailedge_branch": "Branch A",
			},
		)

	invoice_call = get_list.call_args_list[0]
	assert invoice_call.args[0] == "Sales Invoice"
	assert invoice_call.kwargs["filters"]["outstanding_amount"] == [">", 0]
	assert invoice_call.kwargs["filters"]["retailedge_branch"] == "Branch A"
	assert invoice_call.kwargs["limit_page_length"] == receivables.MAX_CUSTOMER_OPTION_SCAN

	customer_call = get_list.call_args_list[1]
	assert customer_call.args[0] == "Customer"
	assert customer_call.kwargs["filters"] == {"name": ["in", ["CUST-1", "CUST-2"]]}
	assert result == [
		{
			"value": "CUST-1",
			"label": "Alpha",
			"description": "CUST-1 · Retail",
		}
	]


def test_customer_search_passes_company_branch_and_customer_group_scope():
	with (
		patch.object(
			receivables,
			"_receivable_customer_invoice_filters",
			return_value={"company": "Scope Co", "retailedge_branch": "Branch A"},
		) as build_filters,
		patch.object(receivables, "_search_receivable_customers", return_value=[]) as search,
	):
		receivables.search_customer_receivables_options(
			"customer",
			"alpha",
			company="Scope Co",
			branch="Branch A",
			customer_group="Retail",
		)

	build_filters.assert_called_once_with(
		company="Scope Co",
		branch="Branch A",
		customer_group="Retail",
	)
	search.assert_called_once_with(
		"alpha",
		{"company": "Scope Co", "retailedge_branch": "Branch A"},
	)


def test_active_receivables_page_passes_dependent_context_and_clears_stale_customer():
	source = VUE.read_text(encoding="utf-8")

	search_start = source.index("async searchOptions")
	search_block = source[search_start : search_start + 700]
	assert "branch: this.filters.branch" in search_block
	assert "customer_group: this.filters.customer_group" in search_block

	company_start = source.index("onCompanySelected(option)")
	company_block = source[company_start : company_start + 450]
	assert "this.clearCustomer();" in company_block

	branch_start = source.index("onBranchSelected(option)")
	branch_block = source[branch_start : branch_start + 400]
	assert "this.clearCustomer();" in branch_block

	assert '@select="onCustomerGroupSelected"' in source
	assert '@clear="clearCustomerGroup"' in source

	group_start = source.index("onCustomerGroupSelected(option)")
	group_block = source[group_start : group_start + 400]
	assert "this.clearCustomer();" in group_block

	clear_group_start = source.index("clearCustomerGroup()")
	clear_group_block = source[clear_group_start : clear_group_start + 300]
	assert "this.clearCustomer();" in clear_group_block


def test_g2g28_does_not_add_permission_or_transaction_bypasses():
	source = Path(receivables.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
