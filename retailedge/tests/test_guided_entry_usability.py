from __future__ import annotations

import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
HUB_ROOT = APP_ROOT / "public" / "js" / "retailedge_business_hub"


class TestGuidedEntryUsability(unittest.TestCase):
	def read(self, path: Path) -> str:
		return path.read_text(encoding="utf-8")

	def test_branch_warehouse_resolver_is_targeted_and_permission_aware(self):
		source = self.read(APP_ROOT / "guided_entry_context.py")
		for contract in (
			"resolve_branch_warehouse_selection",
			"resolve_branch_from_warehouse",
			"validate_operating_branch",
			"get_branch_profile_defaults",
			"get_branch_profile(",
			"_assert_read_permission",
			'"sales": ("default_source_warehouse", "default_warehouse", "default_target_warehouse")',
			'"purchase": ("default_target_warehouse", "default_warehouse", "default_source_warehouse")',
		):
			self.assertIn(contract, source)

		self.assertNotIn("frappe.get_all(", source)
		self.assertNotIn("frappe.db.get_all(", source)

	def test_initial_guided_context_normalises_default_warehouse_and_branch_both_ways(self):
		utils = self.read(HUB_ROOT / "guidedEntryUtils.js")
		for contract in (
			"GUIDED_CONTEXT_METHODS",
			"normaliseGuidedContext",
			"get_simple_sales_invoice_context",
			"get_simple_purchase_invoice_context",
			"get_simple_stock_transfer_context",
			'{ branch: "branch", warehouse: "warehouse", preference: "sales" }',
			'{ branch: "branch", warehouse: "warehouse", preference: "purchase" }',
			'{ branch: "source_branch", warehouse: "source_warehouse", preference: "source" }',
			'{ branch: "target_branch", warehouse: "target_warehouse", preference: "target" }',
			"BRANCH_WAREHOUSE_METHOD",
		):
			self.assertIn(contract, utils)

	def test_sales_purchase_and_stock_use_two_way_branch_warehouse_cascades(self):
		contracts = {
			"SimpleSalesInvoiceDialog.vue": ("setBranch", "setWarehouse", 'preference: "sales"'),
			"SimplePurchaseInvoiceDialog.vue": (
				"setBranch",
				"setWarehouse",
				'preference: "purchase"',
			),
			"SimpleStockTransferDialog.vue": (
				"setSourceBranch",
				"setSourceWarehouse",
				"setTargetBranch",
				"setTargetWarehouse",
				'preference: "source"',
				'preference: "target"',
			),
		}
		for filename, expected in contracts.items():
			with self.subTest(filename=filename):
				source = self.read(HUB_ROOT / filename)
				self.assertIn("resolveBranchWarehouse", source)
				for contract in expected:
					self.assertIn(contract, source)

	def test_guided_entries_create_native_masters_on_demand_when_permitted(self):
		utils = self.read(HUB_ROOT / "guidedEntryUtils.js")
		for contract in (
			"frappe.ui.form",
			"make_quick_entry(",
			'quickCreateMaster("Customer"',
			'quickCreateMaster("Supplier"',
			'quickCreateMaster("Item"',
		):
			self.assertIn(contract, utils)

		sales = self.read(HUB_ROOT / "SimpleSalesInvoiceDialog.vue")
		purchase = self.read(HUB_ROOT / "SimplePurchaseInvoiceDialog.vue")
		stock = self.read(HUB_ROOT / "SimpleStockTransferDialog.vue")
		for source, contracts in (
			(sales, ("Create Customer", "Create Item", ":canCreate=\"canCreateCustomer\"")),
			(purchase, ("Create Supplier", "Create Item", ":canCreate=\"canCreateSupplier\"")),
			(stock, ("Create Stock Item", "quickCreateItem", "canCreateItemLink")),
		):
			for contract in contracts:
				self.assertIn(contract, source)

	def test_all_multi_item_guided_entries_request_newest_first_display(self):
		for filename in (
			"SimpleSalesInvoiceDialog.vue",
			"SimplePurchaseInvoiceDialog.vue",
			"SimpleStockTransferDialog.vue",
		):
			with self.subTest(filename=filename):
				self.assertIn(':newRowsFirst="true"', self.read(HUB_ROOT / filename))

	def test_salesperson_performance_hides_only_its_native_page_sidebar(self):
		host = self.read(
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "salesperson_performance_dashboard"
			/ "salesperson_performance_dashboard.js"
		)
		for contract in (
			"hideNativePageSidebar",
			'querySelector?.(".layout-side-section")',
			'querySelector?.(".layout-main-section-wrapper")',
			"sideSection.hidden = true",
			"window.EdgeSuiteUI?.components",
		):
			self.assertIn(contract, host)
		self.assertNotIn("[BOOT] TRACE", host)
		self.assertNotIn("window.EdgeUI", host)

	def test_searches_remain_bounded_and_on_demand(self):
		for module in (
			"guided_sales_invoice.py",
			"guided_purchase_invoice.py",
			"guided_stock_transfer.py",
		):
			with self.subTest(module=module):
				source = self.read(APP_ROOT / module)
				self.assertIn("MAX_LINK_RESULTS = 20", source)
				self.assertIn("search_link(", source)


if __name__ == "__main__":
	unittest.main()
