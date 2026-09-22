from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_experience.py"
REGISTRY = ROOT / "edgesuite_ui.py"
HUB = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
QUICK_SALE = ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue"
MAKE_SALE = ROOT / "public" / "js" / "make_sale" / "MakeSale.vue"
MAKE_SALE_BUNDLE = ROOT / "public" / "js" / "make_sale.bundle.js"
MAKE_SALE_PAGE = ROOT / "retailedge" / "page" / "make_sale" / "make_sale.js"
MAKE_SALE_FIXTURE = ROOT / "retailedge" / "page" / "make_sale" / "make_sale.json"
TRANSACTION_WORKSPACE = ROOT / "public" / "js" / "transaction_workspace" / "TransactionWorkspace.vue"


def test_make_sale_is_a_real_edgesuite_page():
	assert MAKE_SALE.exists()
	assert MAKE_SALE_BUNDLE.exists()
	assert MAKE_SALE_PAGE.exists()
	assert MAKE_SALE_FIXTURE.exists()

	component = MAKE_SALE.read_text(encoding="utf-8")
	loader = MAKE_SALE_PAGE.read_text(encoding="utf-8")
	bundle = MAKE_SALE_BUNDLE.read_text(encoding="utf-8")

	for contract in (
		"EdgeAppShell",
		"EdgePageLayout",
		"EdgePageHeader",
		'activeRoute="/app/make-sale"',
		"StandardSalesInvoiceCompletionDialog",
	):
		assert contract in component
	assert "edgeui.bundle.js" in loader
	assert "make_sale.bundle.js" in loader
	assert "createEdgeApp" in bundle
	assert "<EdgeModal" not in component


def test_make_sale_reuses_guided_sales_invoice_backend_truth():
	component = MAKE_SALE.read_text(encoding="utf-8")
	for contract in (
		"retailedge.guided_sales_invoice.get_simple_sales_invoice_context",
		"retailedge.guided_sales_invoice.search_simple_sales_invoice_options",
		"retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing",
		"retailedge.guided_sales_invoice.create_simple_sales_invoice_draft",
		"resolveBranchWarehouse",
		"quickCreateCustomer",
		"quickCreateItem",
	):
		assert contract in component

	for forbidden in (
		"frappe.db.",
		"frappe.client.insert",
		"frappe.client.save",
		"frappe.client.submit",
		"frappe.db.commit",
	):
		assert forbidden not in component


def test_quick_sale_and_make_sale_have_separate_user_intents():
	registry = REGISTRY.read_text(encoding="utf-8")
	master = MASTER.read_text(encoding="utf-8")
	hub = HUB.read_text(encoding="utf-8")
	workspace = TRANSACTION_WORKSPACE.read_text(encoding="utf-8")

	assert '"key": "new-sales-invoice", "label": "Quick Sale"' in registry
	assert '"label": "Make Sale"' in master
	assert '"target": "make-sale"' in master
	assert '_promote_make_sale(navigation_groups)' in master
	assert 'addPage("make-sale", "Make Sale"' in hub
	assert 'addAction("new-sales-invoice", "Make Sale")' not in hub
	assert 'return "Make Sale"' in workspace
	assert '>Quick Sale<' in workspace


def test_quick_sale_protects_unsaved_modal_work_and_can_continue_in_page():
	source = QUICK_SALE.read_text(encoding="utf-8")
	for contract in (
		"initialValuesSnapshot",
		"hasUnsavedChanges",
		"Discard the unsaved Quick Sale changes?",
		"Continue in Make Sale",
		'this.$emit("open-page"',
	):
		assert contract in source

	hub = HUB.read_text(encoding="utf-8")
	assert '@open-page="openMakeSaleFromQuick"' in hub
	assert '"retailedge:make-sale:handoff"' in hub


def test_make_sale_keeps_browser_session_recovery_until_erpnext_draft_exists():
	source = MAKE_SALE.read_text(encoding="utf-8")
	for contract in (
		'"retailedge:make-sale:recovery:"',
		"sessionStorage.setItem",
		"sessionStorage.getItem",
		"beforeunload",
		"Unsaved work found",
		"Recovered unsaved Make Sale work",
		"clearRecovery()",
	):
		assert contract in source
	assert "create_simple_sales_invoice_draft" in source
	assert "savedDocument" in source
