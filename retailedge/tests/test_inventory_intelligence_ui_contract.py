import unittest
from pathlib import Path

from retailedge import inventory_health


APP_ROOT = Path(__file__).resolve().parents[1]


class TestInventoryIntelligenceUIContract(unittest.TestCase):
	def test_inventory_health_export_reuses_stock_position_entitlement_and_bounded_dataset(self):
		text = Path(inventory_health.__file__).read_text(encoding="utf-8")
		self.assertIn('require_report_action(\n\t\t"stock-position"', text)
		self.assertIn('action="export"', text)
		self.assertIn("_build_stock_position_dataset", text)
		self.assertIn("get_historical_inventory_demand", text)
		self.assertIn("get_inventory_replenishment", text)
		self.assertIn("persistent_derived_truth", text)
		self.assertIn("zero_balance_contract", text)
		self.assertIn("_apply_sort", text)
		self.assertNotIn("frappe.db.commit", text)
		self.assertNotIn("ignore_permissions=True", text)
		self.assertNotIn(".submit(", text)

	def test_inventory_intelligence_page_uses_edgesuite_shell_and_shared_stock_searches(self):
		page = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "inventory_intelligence"
			/ "inventory_intelligence.js"
		).read_text(encoding="utf-8")
		component = (
			APP_ROOT
			/ "public"
			/ "js"
			/ "inventory_intelligence"
			/ "InventoryIntelligenceCentre.vue"
		).read_text(encoding="utf-8")
		bundle = (APP_ROOT / "public" / "js" / "inventory_intelligence.bundle.js").read_text(encoding="utf-8")

		self.assertIn('const EDGEUI_ASSET = "edgeui.bundle.js"', page)
		self.assertIn('const INVENTORY_INTELLIGENCE_ASSET = "inventory_intelligence.bundle.js"', page)
		self.assertIn("mountInventoryIntelligence", page)
		self.assertIn("EdgeAppShell", component)
		self.assertIn("EdgeReportShell", component)
		self.assertIn("EdgeLinkField", component)
		self.assertIn("EdgeExportMenu", component)
		self.assertIn("retailedge.stock_position.search_stock_position_options", component)
		self.assertIn("resolve_branch_warehouse_selection", component)
		self.assertIn('movement_class: "All"', component)
		self.assertIn('replenishment_status: "All"', component)
		self.assertIn("Replenishment Status", component)
		self.assertIn("Reorder Now", component)
		self.assertIn("Review warehouse group", component)
		self.assertIn("ERPNext Item Reorder configuration", component)
		self.assertIn("lookback_days: 90", component)
		self.assertIn("include_zero: 1", component)
		self.assertIn("Include zero-stock items", component)
		self.assertIn("synthetic_zero_items", component)
		self.assertIn("Last {{ days }} days", component)
		self.assertIn("historical estimation, not a forecast", component)
		self.assertIn('window.open(`/app/item/${encodeURIComponent(payload.value)}`', component)
		self.assertIn("sortable: true", component)
		self.assertIn(':sort="sort"', component)
		self.assertIn('@sort-change="changeSort"', component)
		self.assertIn('sort_field: this.sort?.field || ""', component)
		self.assertIn('sort_direction: this.sort?.direction || ""', component)
		self.assertIn(
			'movementClasses: ["All", "Normal", "Slow", "Non-moving", "No demand in window"]',
			component,
		)
		self.assertIn("get_inventory_health_export", bundle)
		self.assertNotIn("innerHTML", page)
		self.assertNotIn("insertAdjacentHTML", page)

	def test_inventory_intelligence_page_roles_match_stock_operational_scope(self):
		page_json = (
			APP_ROOT
			/ "retailedge"
			/ "page"
			/ "inventory_intelligence"
			/ "inventory_intelligence.json"
		).read_text(encoding="utf-8")
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
