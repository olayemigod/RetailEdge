from pathlib import Path

from retailedge import inventory_health


APP_ROOT = Path(__file__).resolve().parents[1]


def test_inventory_health_export_reuses_stock_position_entitlement_and_bounded_dataset():
	text = Path(inventory_health.__file__).read_text(encoding="utf-8")
	assert 'require_report_action(\n\t\t"stock-position"' in text
	assert 'action="export"' in text
	assert "_build_stock_position_dataset" in text
	assert "get_historical_inventory_demand" in text
	assert "persistent_derived_truth" in text
	assert "frappe.db.commit" not in text
	assert "ignore_permissions=True" not in text
	assert ".submit(" not in text


def test_inventory_intelligence_page_uses_edgesuite_shell_and_shared_stock_searches():
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

	assert 'const EDGEUI_ASSET = "edgeui.bundle.js"' in page
	assert 'const INVENTORY_INTELLIGENCE_ASSET = "inventory_intelligence.bundle.js"' in page
	assert "mountInventoryIntelligence" in page
	assert "EdgeAppShell" in component
	assert "EdgeReportShell" in component
	assert "EdgeLinkField" in component
	assert "EdgeExportMenu" in component
	assert "retailedge.stock_position.search_stock_position_options" in component
	assert "resolve_branch_warehouse_selection" in component
	assert 'movement_class: "All"' in component
	assert "lookback_days: 90" in component
	assert "Last {{ days }} days" in component
	assert "historical estimation, not a forecast" in component
	assert 'window.open(`/app/item/${encodeURIComponent(payload.value)}`' in component
	assert "sortable: true" in component
	assert "get_inventory_health_export" in bundle
	assert "innerHTML" not in page
	assert "insertAdjacentHTML" not in page


def test_inventory_intelligence_page_roles_match_stock_operational_scope():
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
		assert role in page_json
