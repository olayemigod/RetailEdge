from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import sales_reporting


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "public/js/sales_reporting/SalesReportingReport.vue"
FORECAST = ROOT / "public/js/sales_forecast/SalesForecast.vue"
CUSTOMER_SALES = ROOT / "public/js/customer_sales_intelligence/CustomerSalesIntelligence.vue"
CUSTOMER_OPPORTUNITY = ROOT / "public/js/customer_opportunity_intelligence/CustomerOpportunityIntelligence.vue"


def test_option_scope_reuses_operational_branch_authority():
	with (
		patch.object(sales_reporting, "_assert_named_read") as assert_read,
		patch.object(
			sales_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", "Branch A"),
		) as branch_scope,
	):
		filters = sales_reporting._sales_option_invoice_filters(
			company="Scope Co",
			branch="Branch A",
			from_date="2026-08-01",
			to_date="2026-08-31",
		)
	assert filters == {
		"docstatus": 1,
		"company": "Scope Co",
		"posting_date": ["between", ["2026-08-01", "2026-08-31"]],
		"retailedge_branch": "Branch A",
	}
	assert_read.assert_called_once_with("Company", "Scope Co")
	branch_scope.assert_called_once()


def test_customer_options_originate_from_permitted_invoice_scope_then_customer_permission():
	invoice_rows = [
		frappe._dict(customer="CUST-1", customer_name="Alpha"),
		frappe._dict(customer="CUST-2", customer_name="Beta"),
	]
	customer_rows = [
		frappe._dict(name="CUST-1", customer_name="Alpha", customer_group="Commercial"),
	]
	with patch.object(
		sales_reporting.frappe,
		"get_list",
		side_effect=[invoice_rows, customer_rows],
	) as get_list:
		result = sales_reporting._search_sales_customers(
			"a",
			{"docstatus": 1, "company": "Scope Co", "retailedge_branch": "Branch A"},
		)
	first = get_list.call_args_list[0]
	second = get_list.call_args_list[1]
	assert first.args[0] == "Sales Invoice"
	assert first.kwargs["group_by"] == "customer, customer_name"
	assert first.kwargs["filters"]["retailedge_branch"] == "Branch A"
	assert second.args[0] == "Customer"
	assert result == [
		{
			"value": "CUST-1",
			"label": "Alpha",
			"description": "CUST-1 · Commercial",
		}
	]


def test_salesperson_options_read_child_rows_only_after_permitted_invoice_names():
	invoices = [frappe._dict(name="SINV-1"), frappe._dict(name="SINV-2")]
	team_rows = [
		frappe._dict(sales_person="Ada Sales"),
		frappe._dict(sales_person="Bola Sales"),
	]
	masters = [frappe._dict(name="Ada Sales")]
	with (
		patch.object(
			sales_reporting.frappe,
			"get_list",
			side_effect=[invoices, masters],
		) as get_list,
		patch.object(sales_reporting.frappe, "get_all", return_value=team_rows) as get_all,
	):
		result = sales_reporting._search_salespeople(
			"sales",
			{"docstatus": 1, "company": "Scope Co", "retailedge_branch": "Branch A"},
		)
	assert get_list.call_args_list[0].args[0] == "Sales Invoice"
	child_filters = get_all.call_args.kwargs["filters"]
	assert child_filters["parenttype"] == "Sales Invoice"
	assert child_filters["parent"] == ["in", ["SINV-1", "SINV-2"]]
	assert get_list.call_args_list[1].args[0] == "Sales Person"
	assert result == [{"value": "Ada Sales", "label": "Ada Sales"}]


def test_shared_sales_frontends_pass_authoritative_option_context_and_clear_stale_dependents():
	report = REPORT.read_text(encoding="utf-8")
	forecast = FORECAST.read_text(encoding="utf-8")
	customer_sales = CUSTOMER_SALES.read_text(encoding="utf-8")
	opportunity = CUSTOMER_OPPORTUNITY.read_text(encoding="utf-8")

	assert "from_date: this.filters.from_date, to_date: this.filters.to_date" in report
	assert 'from_date: this.scope.history_from_date || "", to_date: this.scope.history_to_date || ""' in forecast
	assert "from_date: this.filters.from_date" in customer_sales
	assert "to_date: this.filters.to_date" in customer_sales

	assert 'this.filters.customer = "";' in report
	assert 'this.customerLabel = "";' in report
	assert 'this.filters.salesperson = "";' in report

	# Comparison intelligence keeps all-time Company/Branch customer discovery so
	# customers visible only in its immediately-prior comparison period remain selectable.
	search_start = opportunity.index("async searchOptions")
	search_block = opportunity[search_start : search_start + 650]
	assert "company: this.filters.company" in search_block
	assert "branch: this.filters.branch" in search_block
	assert "from_date:" not in search_block
	assert "to_date:" not in search_block


def test_option_search_avoids_permission_bypasses_and_raw_sql():
	source = Path(sales_reporting.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
	assert "frappe.db.sql" not in source
