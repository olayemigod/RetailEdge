from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]


class TestOperatingReportDefaultsPhase3(unittest.TestCase):
	def read(self, relative: str) -> str:
		return (APP_ROOT / relative).read_text(encoding="utf-8")

	def test_only_report_context_endpoints_are_overridden(self):
		hooks = self.read("hooks.py")
		for contract in (
			'"retailedge.sales_reporting.get_sales_reporting_context": "retailedge.operating_report_defaults.get_sales_reporting_context"',
			'"retailedge.purchase_reporting.get_purchase_reporting_context": "retailedge.operating_report_defaults.get_purchase_reporting_context"',
			'"retailedge.stock_position.get_stock_position_context": "retailedge.operating_report_defaults.get_stock_position_context"',
		):
			self.assertIn(contract, hooks)
		for forbidden in (
			'"retailedge.sales_reporting.get_sales_by_item":',
			'"retailedge.sales_reporting.get_sales_invoice_register":',
			'"retailedge.purchase_reporting.get_purchase_register":',
			'"retailedge.purchase_reporting.get_supplier_payables":',
			'"retailedge.stock_position.get_stock_position":',
		):
			self.assertNotIn(forbidden, hooks)

	def test_operating_context_changes_default_filters_only(self):
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
			"permission_query_conditions",
		):
			self.assertNotIn(forbidden, source)

	def test_sales_purchase_and_stock_keep_clearable_branch_filters(self):
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

	def test_wrapper_reuses_existing_report_contexts_and_preserves_stock_cost_visibility(self):
		source = self.read("operating_report_defaults.py")
		for contract in (
			"_base_sales_reporting_context",
			"_base_purchase_reporting_context",
			"_base_stock_position_context",
			"preserve_hidden_currency=True",
			'context.get("show_costs", 1)',
		):
			self.assertIn(contract, source)


if __name__ == "__main__":
	unittest.main()
