from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import frappe

from retailedge import purchase_reporting


ROOT = Path(__file__).resolve().parents[1]
VUE = ROOT / "public/js/purchase_reporting/PurchaseReportingReport.vue"


def test_purchase_register_supplier_filters_reuse_purchase_branch_authority():
	with (
		patch.object(purchase_reporting, "_assert_report_access") as assert_access,
		patch.object(
			purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", ["in", ["Branch A", "Branch B"]]),
		) as branch_scope,
	):
		filters = purchase_reporting._purchase_supplier_invoice_filters(
			company="Scope Co",
			branch="",
			supplier_group="Local",
			report_type="purchase_register",
			from_date="2026-09-01",
			to_date="2026-09-12",
			invoice_kind="Purchases",
			status="Unpaid",
		)

	assert filters == {
		"docstatus": 1,
		"company": "Scope Co",
		"posting_date": ["between", ["2026-09-01", "2026-09-12"]],
		"supplier_group": "Local",
		"status": "Unpaid",
		"is_return": 0,
		"retailedge_branch": ["in", ["Branch A", "Branch B"]],
	}
	scope = assert_access.call_args.args[0]
	assert scope.company == "Scope Co"
	assert scope.supplier_group == "Local"
	branch_scope.assert_called_once_with(scope)


def test_supplier_payables_option_filters_require_current_outstanding_non_return_bills():
	with (
		patch.object(purchase_reporting, "_assert_report_access"),
		patch.object(
			purchase_reporting,
			"_invoice_branch_scope",
			return_value=("retailedge_branch", "Branch A"),
		),
	):
		filters = purchase_reporting._purchase_supplier_invoice_filters(
			company="Scope Co",
			branch="Branch A",
			supplier_group="",
			report_type="supplier_payables",
			as_of_date="2026-09-12",
		)

	assert filters["posting_date"] == ["<=", "2026-09-12"]
	assert filters["outstanding_amount"] == [">", 0]
	assert filters["is_return"] == 0
	assert filters["retailedge_branch"] == "Branch A"


def test_supplier_options_originate_from_scoped_purchase_invoice_evidence():
	invoice_rows = [
		frappe._dict(supplier="SUP-1", supplier_name="Alpha Supply", supplier_group="Local"),
		frappe._dict(supplier="SUP-2", supplier_name="Beta Supply", supplier_group="Local"),
	]
	supplier_rows = [
		frappe._dict(name="SUP-1", supplier_name="Alpha Supply", supplier_group="Local"),
	]
	with patch.object(
		purchase_reporting.frappe,
		"get_list",
		side_effect=[invoice_rows, supplier_rows],
	) as get_list:
		result = purchase_reporting._search_purchase_suppliers(
			"supply",
			{
				"docstatus": 1,
				"company": "Scope Co",
				"posting_date": ["between", ["2026-09-01", "2026-09-12"]],
				"retailedge_branch": "Branch A",
			},
		)

	invoice_call = get_list.call_args_list[0]
	assert invoice_call.args[0] == "Purchase Invoice"
	assert invoice_call.kwargs["limit_page_length"] == purchase_reporting.MAX_SUPPLIER_OPTION_SCAN
	assert invoice_call.kwargs["filters"]["retailedge_branch"] == "Branch A"

	supplier_call = get_list.call_args_list[1]
	assert supplier_call.args[0] == "Supplier"
	assert supplier_call.kwargs["filters"] == {"name": ["in", ["SUP-1", "SUP-2"]]}
	assert result == [
		{
			"value": "SUP-1",
			"label": "Alpha Supply",
			"description": "SUP-1 · Local",
		}
	]


def test_supplier_search_passes_active_report_context():
	with (
		patch.object(
			purchase_reporting,
			"_purchase_supplier_invoice_filters",
			return_value={"company": "Scope Co"},
		) as build_filters,
		patch.object(purchase_reporting, "_search_purchase_suppliers", return_value=[]) as search,
	):
		purchase_reporting.search_purchase_reporting_options(
			"supplier",
			"alpha",
			company="Scope Co",
			branch="Branch A",
			supplier_group="Local",
			report_type="purchase_register",
			from_date="2026-09-01",
			to_date="2026-09-12",
			as_of_date="2026-09-12",
			invoice_kind="All",
			status="Unpaid",
		)

	build_filters.assert_called_once_with(
		company="Scope Co",
		branch="Branch A",
		supplier_group="Local",
		report_type="purchase_register",
		from_date="2026-09-01",
		to_date="2026-09-12",
		as_of_date="2026-09-12",
		invoice_kind="All",
		status="Unpaid",
	)
	search.assert_called_once_with("alpha", {"company": "Scope Co"})


def test_active_purchase_page_passes_context_and_clears_stale_supplier():
	source = VUE.read_text(encoding="utf-8")

	search_start = source.index("async searchOptions")
	search_block = source[search_start : search_start + 1100]
	for expected in (
		"branch: this.filters.branch",
		"supplier_group: this.filters.supplier_group",
		"report_type: this.reportType",
		"from_date: this.filters.from_date",
		"to_date: this.filters.to_date",
		"as_of_date: this.filters.as_of_date",
		"invoice_kind: this.filters.invoice_kind",
		"status: this.filters.status",
	):
		assert expected in search_block

	assert '@select="onSupplierGroupSelected"' in source
	assert '@clear="clearSupplierGroup"' in source
	assert '@change="onPurchaseDateChange"' in source

	company_start = source.index("onCompanySelected(option)")
	assert "this.clearSupplier();" in source[company_start : company_start + 500]

	branch_start = source.index("onBranchSelected(option)")
	assert "this.clearSupplier();" in source[branch_start : branch_start + 450]

	group_start = source.index("onSupplierGroupSelected(option)")
	assert "this.clearSupplier();" in source[group_start : group_start + 400]

	date_start = source.index("onPurchaseDateChange()")
	assert "this.clearSupplier();" in source[date_start : date_start + 300]

	warehouse_start = source.index("async onWarehouseSelected(option)")
	warehouse_block = source[warehouse_start : warehouse_start + 1000]
	assert "previousBranch" in warehouse_block
	assert "this.clearSupplier();" in warehouse_block


def test_g2g29_does_not_add_permission_or_transaction_bypasses():
	source = Path(purchase_reporting.__file__).read_text(encoding="utf-8")
	assert "ignore_permissions=True" not in source
	assert "frappe.db.commit()" not in source
