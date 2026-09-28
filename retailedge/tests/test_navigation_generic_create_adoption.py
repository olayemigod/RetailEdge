from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

GENERIC_CREATE_SURFACES = {
	"native_workspace": ROOT / "public/js/native_visual_workspaces/NativeERPNextWorkspace.vue",
	"pricing_promotions": ROOT / "public/js/pricing_promotions/PricingPromotionsWorkspace.vue",
	"setup": ROOT / "public/js/retailedge_setup/RetailEdgeSetup.vue",
	"forecasting_planning": ROOT / "public/js/forecasting_planning/ForecastingPlanning.vue",
	"supplier_scorecard": ROOT / "public/js/professional_purchasing/SupplierScorecardGovernance.vue",
	"project_operations": ROOT / "public/js/project_operations/ProjectOperations.vue",
}


def test_generic_embedded_create_surfaces_use_edgesuite_contract():
	for name, path in GENERIC_CREATE_SURFACES.items():
		source = path.read_text(encoding="utf-8")
		assert "window.EdgeSuiteUI?.openCreateSurface" in source, f"{name} must delegate generic creation to EdgeSuite"
		assert "EdgeSuite create navigation is unavailable." in source, f"{name} must fail closed when the shared runtime is missing"


def test_native_workspace_create_keeps_existing_access_gate():
	source = GENERIC_CREATE_SURFACES["native_workspace"].read_text(encoding="utf-8")
	assert 'if (!this.canUseNativeDesk || source.kind !== "doctype" || !source.can_create) return;' in source
	assert "return openCreateSurface(source.target);" in source
	assert "frappe.new_doc(source.target)" not in source


def test_pricing_create_preserves_single_allowed_price_list_default():
	source = GENERIC_CREATE_SURFACES["pricing_promotions"].read_text(encoding="utf-8")
	assert 'this.activeArea.doctype === "Item Price" && this.priceListOptions.length === 1' in source
	assert "defaults.price_list = this.priceListOptions[0].value;" in source
	assert "return openCreateSurface(this.activeArea.doctype, defaults);" in source
	assert "frappe.new_doc(this.activeArea.doctype)" not in source


def test_setup_create_uses_native_surface_decision_instead_of_hardcoded_new_url():
	source = GENERIC_CREATE_SURFACES["setup"].read_text(encoding="utf-8")
	assert "if (!this.canUseNativeDesk) return;" in source
	assert "return openCreateSurface(resource.doctype);" in source
	assert 'doctypeSlug(resource.doctype)}/new' not in source


def test_planning_scenario_create_preserves_defaults_and_access_gate():
	source = GENERIC_CREATE_SURFACES["forecasting_planning"].read_text(encoding="utf-8")
	assert "if (!this.canUseNativeDesk || !this.canCreateScenario || !this.filters.company) return;" in source
	assert 'return openCreateSurface("RetailEdge Planning Scenario", {' in source
	for field in (
		"company",
		"branch",
		"as_of_date",
		"history_months",
		"horizon_months",
		"sales_adjustment_percent",
		"expense_adjustment_percent",
		"cash_adjustment_percent",
		"inventory_safety_percent",
	):
		assert f"{field}:" in source
	assert 'frappe.new_doc("RetailEdge Planning Scenario"' not in source


def test_supplier_scorecard_create_preserves_supplier_default_and_permission_capability():
	source = GENERIC_CREATE_SURFACES["supplier_scorecard"].read_text(encoding="utf-8")
	assert "this.capability.can_create_scorecard && this.supplier && !this.summary.scorecard_exists" in source
	assert 'return openCreateSurface("Supplier Scorecard", { supplier: this.supplier });' in source
	assert 'frappe.new_doc("Supplier Scorecard"' not in source


def test_project_task_and_budget_creation_use_shared_contract_but_native_spend_escape_stays_explicit():
	source = GENERIC_CREATE_SURFACES["project_operations"].read_text(encoding="utf-8")
	assert 'return openCreateSurface("Task", { project: this.project });' in source
	assert 'return openCreateSurface("Budget", { budget_against: "Project", project: this.project, company: this.context.company });' in source
	assert 'frappe.new_doc("Task"' not in source
	assert 'frappe.new_doc("Budget"' not in source
	assert 'primary_action_label: __("Open Native Entry")' in source
	assert "frappe.new_doc(route.doctype, route.defaults || {});" in source


def test_guided_advanced_transaction_escapes_remain_outside_generic_create_contract():
	contracts = {
		ROOT / "public/js/make_sale/MakeSale.vue": 'frappe.new_doc("Sales Invoice")',
		ROOT / "public/js/record_purchase/RecordPurchase.vue": 'frappe.new_doc("Purchase Invoice")',
		ROOT / "public/js/transfer_stock/TransferStock.vue": 'frappe.new_doc("Stock Entry", { purpose: "Material Transfer" })',
		ROOT / "public/js/stock_adjustment/StockAdjustment.vue": 'frappe.new_doc("Stock Reconciliation")',
	}
	for path, marker in contracts.items():
		source = path.read_text(encoding="utf-8")
		assert "if (!this.canUseNativeDesk) return;" in source
		assert marker in source
