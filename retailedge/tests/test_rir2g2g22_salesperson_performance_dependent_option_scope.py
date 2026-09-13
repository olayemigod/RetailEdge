from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import salesperson_performance_dashboard as dashboard


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/salesperson_performance_dashboard/SalespersonPerformanceDashboardV2.vue"


def test_option_invoice_scope_reuses_salesperson_performance_branch_authority():
	with (
		patch.object(
			dashboard,
			"resolve_salesperson_performance_read_scope",
			return_value=frappe._dict(
				company="Scope Co",
				branch="Branch A",
				_branch_scope_restricted=True,
				_allowed_branches=["Branch A"],
			),
		) as resolve_scope,
		patch.object(
			dashboard,
			"has_field",
			side_effect=lambda doctype, fieldname: doctype == "Sales Invoice"
			and fieldname == "retailedge_branch",
		),
	):
		filters = dashboard._salesperson_option_invoice_filters(
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
	resolve_scope.assert_called_once_with(
		{"company": "Scope Co", "branch": "Branch A"},
		user=frappe.session.user,
	)


def test_option_invoice_scope_fails_closed_for_restricted_zero_branch():
	with (
		patch.object(
			dashboard,
			"resolve_salesperson_performance_read_scope",
			return_value=frappe._dict(
				company="Scope Co",
				branch="",
				_branch_scope_restricted=True,
				_allowed_branches=[],
			),
		),
		patch.object(dashboard, "has_field", return_value=True),
	):
		assert (
			dashboard._salesperson_option_invoice_filters(
				company="Scope Co",
				branch="",
				from_date="2026-08-01",
				to_date="2026-08-31",
			)
			is None
		)


def test_customer_options_originate_from_scoped_submitted_invoices_before_master_search():
	invoice_rows = [
		frappe._dict(customer="CUST-1", customer_name="Alpha"),
		frappe._dict(customer="CUST-2", customer_name="Beta"),
	]
	with (
		patch.object(dashboard.frappe, "get_list", return_value=invoice_rows) as get_list,
		patch.object(
			dashboard,
			"_search_doctype",
			return_value=[{"value": "CUST-1", "label": "Alpha", "description": "CUST-1"}],
		) as search_master,
	):
		result = dashboard._search_scoped_customers(
			"a",
			{
				"docstatus": 1,
				"company": "Scope Co",
				"posting_date": ["between", ["2026-08-01", "2026-08-31"]],
				"retailedge_branch": "Branch A",
			},
		)

	call = get_list.call_args
	assert call.args[0] == "Sales Invoice"
	assert call.kwargs["filters"]["docstatus"] == 1
	assert call.kwargs["filters"]["retailedge_branch"] == "Branch A"
	assert call.kwargs["limit_page_length"] == dashboard.MAX_LINK_RESULTS
	assert search_master.call_args.args[0] == "Customer"
	assert search_master.call_args.kwargs["filters"] == {"name": ["in", ["CUST-1", "CUST-2"]]}
	assert result[0]["value"] == "CUST-1"


def test_salesperson_options_read_sales_team_only_after_scoped_invoice_parents():
	invoices = [frappe._dict(name="SINV-1"), frappe._dict(name="SINV-2")]
	team_rows = [
		frappe._dict(sales_person="Ada Sales"),
		frappe._dict(sales_person="Bola Sales"),
	]
	with (
		patch.object(dashboard.frappe, "get_list", return_value=invoices) as get_list,
		patch.object(dashboard.frappe, "get_all", return_value=team_rows) as get_all,
		patch.object(
			dashboard,
			"_search_doctype",
			return_value=[{"value": "Ada Sales", "label": "Ada Sales", "description": ""}],
		) as search_master,
	):
		result = dashboard._search_scoped_salespeople(
			"sales",
			{"docstatus": 1, "company": "Scope Co", "retailedge_branch": "Branch A"},
		)

	assert get_list.call_args.args[0] == "Sales Invoice"
	assert get_list.call_args.kwargs["limit_page_length"] == dashboard.MAX_INVOICE_SCAN_ROWS + 1
	child_filters = get_all.call_args.kwargs["filters"]
	assert child_filters["parenttype"] == "Sales Invoice"
	assert child_filters["parent"] == ["in", ["SINV-1", "SINV-2"]]
	assert search_master.call_args.args[0] == "Sales Person"
	assert ["Sales Person", "enabled", "=", 1] in search_master.call_args.kwargs["filters"]
	assert ["Sales Person", "name", "in", ["Ada Sales", "Bola Sales"]] in search_master.call_args.kwargs["filters"]
	assert result[0]["value"] == "Ada Sales"


def test_active_dashboard_passes_branch_dates_and_clears_stale_customer_salesperson():
	source = VUE.read_text(encoding="utf-8")

	assert "branch: this.filters.branch" in source
	assert "from_date: this.filters.from_date" in source
	assert "to_date: this.filters.to_date" in source
	assert "onCompanySelected(option)" in source
	assert "onBranchSelected(option)" in source
	assert "onCustomDateChange()" in source
	assert 'this.filters.salesperson = "";' in source
	assert 'this.filters.customer = "";' in source


def test_g2g22_does_not_introduce_permission_or_transaction_bypasses():
	source = Path(dashboard.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
	assert "frappe.db.sql" not in source
