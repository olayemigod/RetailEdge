import unittest
from pathlib import Path


APP_ROOT = Path(__file__).resolve().parents[1]


class TestInventoryInsightUIContract(unittest.TestCase):
	def test_shared_inventory_insight_component_reuses_edgesuite_and_guided_transfer(self):
		component = (
			APP_ROOT / "public" / "js" / "inventory_insights" / "InventoryInsightView.vue"
		).read_text(encoding="utf-8")
		dialog = (
			APP_ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleStockTransferDialog.vue"
		).read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public" / "js" / "inventory_insights.bundle.js").read_text(encoding="utf-8")

		for token in ("EdgeAppShell", "EdgeReportShell", "EdgeLinkField"):
			self.assertIn(token, component)
		self.assertIn("SimpleStockTransferDialog", component)
		self.assertIn("../retailedge_business_hub/SimpleStockTransferDialog.vue", component)
		self.assertIn(':prefill="guidedTransferPrefill"', component)
		for token in (
			"source_warehouse: row.source_warehouse",
			"target_warehouse: row.target_warehouse",
			"item_code: row.item_code",
			"qty: Number(row.suggested_transfer_qty",
		):
			self.assertIn(token, component)
		self.assertIn('prefill: { type: Object, default: () => ({}) }', dialog)
		self.assertIn("await this.applyPrefill()", dialog)
		self.assertIn("await this.setSourceWarehouse(sourceWarehouse)", dialog)
		self.assertIn("await this.setTargetWarehouse(targetWarehouse)", dialog)
		self.assertIn("this.values.items = [{ item_code: itemCode, qty }]", dialog)
		self.assertIn("retailedge.stock_position.search_stock_position_options", component)
		self.assertIn("resolve_branch_warehouse_selection", component)
		self.assertIn("from_date", component)
		self.assertIn("to_date", component)
		self.assertIn("Age Bands (Days)", component)
		self.assertIn('age_ranges: "30,60,90,180"', component)
		self.assertIn("Aged Stock Threshold (Days)", component)
		self.assertIn("aged_threshold_days: 90", component)
		self.assertIn("delete filters.age_ranges", component)
		self.assertIn('@sort-change="changeSort"', component)
		self.assertIn("sort_field", component)
		self.assertIn("sort_direction", component)
		self.assertIn('window.open(`/app/item/${encodeURIComponent(payload.value)}`', component)
		self.assertIn('window.open(`/app/warehouse/${encodeURIComponent(payload.value)}`', component)
		self.assertIn('window.open("/app/stock-entry", "_blank", "noopener,noreferrer")', component)
		self.assertIn("never create or submit Stock Entries automatically", component)
		self.assertIn("R10 does not recalculate margin", component)
		self.assertIn("mountInventoryInsightView", bundle)
		self.assertIn("get_inventory_insight_view", bundle)

	def test_inventory_insight_pages_use_shared_bundle_and_expected_views(self):
		pages = {
			"inventory_ageing": ("ageing", "Inventory Ageing"),
			"inventory_transfer_opportunities": ("transfer-opportunities", "Transfer Opportunities"),
			"inventory_profitability": ("profitability", "Inventory + Profitability"),
		}
		for directory, (view, title) in pages.items():
			with self.subTest(directory=directory):
				page_dir = APP_ROOT / "retailedge" / "page" / directory
				js = (page_dir / f"{directory}.js").read_text(encoding="utf-8")
				page_json = (page_dir / f"{directory}.json").read_text(encoding="utf-8")
				self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', js)
				self.assertIn('const INVENTORY_INSIGHTS_ASSET = "inventory_insights.bundle.js"', js)
				self.assertIn(f'const INSIGHT_VIEW = "{view}"', js)
				self.assertIn("mountInventoryInsightView", js)
				self.assertIn("document.createElement", js)
				self.assertNotIn("innerHTML", js)
				self.assertIn(title, page_json)
				for role in (
					"System Manager",
					"Stock User",
					"Stock Manager",
					"RetailEdge Manager",
					"RetailEdge Branch Manager",
					"RetailEdge Auditor",
				):
					self.assertIn(role, page_json)


if __name__ == "__main__":
	unittest.main()
