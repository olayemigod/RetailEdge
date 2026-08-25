from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOperatingReportDefaultsPhase3(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_context_search_data_and_export_endpoints_are_scoped_through_wrapper(self):
		hooks = self.read("hooks.py")
		for contract in (
			'"retailedge.sales_reporting.get_sales_reporting_context": "retailedge.operating_report_defaults.get_sales_reporting_context"',
			'"retailedge.sales_reporting.search_sales_reporting_options": "retailedge.operating_report_defaults.search_sales_reporting_options"',
			'"retailedge.sales_reporting.get_sales_by_item": "retailedge.operating_report_defaults.get_sales_by_item"',
			'"retailedge.sales_reporting.get_sales_invoice_register_export": "retailedge.operating_report_defaults.get_sales_invoice_register_export"',
			'"retailedge.purchase_reporting.get_purchase_reporting_context": "retailedge.operating_report_defaults.get_purchase_reporting_context"',
			'"retailedge.purchase_reporting.search_purchase_reporting_options": "retailedge.operating_report_defaults.search_purchase_reporting_options"',
			'"retailedge.purchase_reporting.get_supplier_payables": "retailedge.operating_report_defaults.get_supplier_payables"',
			'"retailedge.purchase_reporting.get_purchase_register_export": "retailedge.operating_report_defaults.get_purchase_register_export"',
			'"retailedge.stock_position.get_stock_position_context": "retailedge.operating_report_defaults.get_stock_position_context"',
			'"retailedge.stock_position.search_stock_position_options": "retailedge.operating_report_defaults.search_stock_position_options"',
			'"retailedge.stock_position.get_stock_position": "retailedge.operating_report_defaults.get_stock_position"',
			'"retailedge.stock_position.get_stock_position_export": "retailedge.operating_report_defaults.get_stock_position_export"',
		):
			self.assertIn(contract, hooks)

	def test_operating_context_sets_initial_defaults_without_persisting_user_defaults(self):
		source = self.read("operating_report_defaults.py")
		for contract in (
			"get_operating_context",
			'filters = dict(context.get("default_filters") or {})',
			'filters["company"] = company',
			'filters["branch"] = branch',
			'filters["warehouse"] = ""',
			'context["default_filters"] = filters',
			'context["operating_context_defaulted"] = bool(company or branch)',
		):
			self.assertIn(contract, source)
		for forbidden in (
			"frappe.defaults.set_user_default",
			"frappe.db.set_value",
			"frappe.db.commit",
			"ignore_permissions",
		):
			self.assertNotIn(forbidden, source)

	def test_branch_setup_membership_restricts_non_global_report_scope_and_fails_closed(self):
		source = self.read("operating_report_defaults.py")
		for contract in (
			"user_has_global_branch_access",
			"get_user_branch_profiles",
			"def _assigned_profile_scope(company: str)",
			'row.get("enabled")',
			"Your assigned Branch reporting scope could not be verified",
			"You do not have an active Branch Setup assignment for this Company",
			"def _constrain_report_filters(",
			"Choose one of your assigned Branches",
			"Cross-branch reporting is available only to authorized managers",
			"You do not have reporting access to Branch {0}",
			"def _filter_branch_options(",
		):
			self.assertIn(contract, source)

	def test_sales_purchase_and_stock_keep_user_clearable_branch_controls(self):
		for relative in (
			"public/js/sales_reporting/SalesReportingReport.vue",
			"public/js/purchase_reporting/PurchaseReportingReport.vue",
			"public/js/stock_position/StockPositionReport.vue",
		):
			source = self.read(relative)
			self.assertIn('v-model="filters.branch"', source)
			self.assertIn('@clear="clearBranch"', source)
			self.assertIn("clearBranch()", source)
			self.assertIn('this.filters.branch = ""', source)
			self.assertIn("context.default_filters || {}", source)

	def test_governed_export_and_print_dataset_dispatch_uses_constrained_wrappers(self):
		source = self.read("reporting_actions.py")
		for contract in (
			"from retailedge.operating_report_defaults import get_sales_by_item_export",
			"from retailedge.operating_report_defaults import get_sales_invoice_register_export",
			"from retailedge.operating_report_defaults import get_purchase_register_export",
			"from retailedge.operating_report_defaults import get_governed_supplier_payables_export",
			"from retailedge.operating_report_defaults import get_stock_position_export",
		):
			self.assertIn(contract, source)
		for forbidden in (
			"from retailedge.sales_reporting import get_sales_by_item_export",
			"from retailedge.sales_reporting import get_sales_invoice_register_export",
			"from retailedge.purchase_reporting import get_purchase_register_export",
			"from retailedge.supplier_payables import get_supplier_payables_export",
			"from retailedge.stock_position import get_stock_position_export",
		):
			self.assertNotIn(forbidden, source)
		self.assertIn("handler = _export_handler(report_key)", source)
		self.assertIn("return handler(filters=resolved_filters)", source)

	def test_supplier_payables_governed_export_preserves_current_outstanding_contract(self):
		source = self.read("operating_report_defaults.py")
		for contract in (
			"from retailedge.supplier_payables import get_supplier_payables_export as _base_current_supplier_payables_export",
			"def get_governed_supplier_payables_export(filters=None):",
			"_base_current_supplier_payables_export(filters=_constrain_report_filters(filters))",
		):
			self.assertIn(contract, source)
		supplier_source = self.read("supplier_payables.py")
		for contract in (
			"current_outstanding",
			"historical_balance_supported",
			"Historical payables as of a past date require ledger reconstruction",
		):
			self.assertIn(contract, supplier_source)

	def test_wrapper_reuses_existing_report_engines_and_preserves_stock_cost_visibility(self):
		source = self.read("operating_report_defaults.py")
		for contract in (
			"_base_sales_reporting_context",
			"_base_purchase_reporting_context",
			"_base_stock_position_context",
			"_base_get_sales_by_item",
			"_base_get_purchase_register",
			"_base_get_stock_position",
			"preserve_hidden_currency=True",
			'context.get("show_costs", 1)',
		):
			self.assertIn(contract, source)


if __name__ == "__main__":
	unittest.main()
