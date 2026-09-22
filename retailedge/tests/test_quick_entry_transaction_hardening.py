from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MASTER = ROOT / "master_experience.py"
REGISTRY = ROOT / "edgesuite_ui.py"
HUB = ROOT / "public" / "js" / "retailedge_business_hub" / "RetailEdgeBusinessHub.vue"
TRANSACTION_WORKSPACE = ROOT / "public" / "js" / "transaction_workspace" / "TransactionWorkspace.vue"
TRANSACTION_WORKSPACE_BACKEND = ROOT / "retailedge" / "page" / "transaction_workspace" / "transaction_workspace.py"

ENTRY_PAGES = {
	"make-sale": {
		"component": ROOT / "public" / "js" / "make_sale" / "MakeSale.vue",
		"bundle": ROOT / "public" / "js" / "make_sale.bundle.js",
		"loader": ROOT / "retailedge" / "page" / "make_sale" / "make_sale.js",
		"fixture": ROOT / "retailedge" / "page" / "make_sale" / "make_sale.json",
		"backend": "retailedge.guided_sales_invoice.create_simple_sales_invoice_draft",
	},
	"record-purchase": {
		"component": ROOT / "public" / "js" / "record_purchase" / "RecordPurchase.vue",
		"bundle": ROOT / "public" / "js" / "record_purchase.bundle.js",
		"loader": ROOT / "retailedge" / "page" / "record_purchase" / "record_purchase.js",
		"fixture": ROOT / "retailedge" / "page" / "record_purchase" / "record_purchase.json",
		"backend": "retailedge.guided_purchase_invoice.create_simple_purchase_invoice_draft",
	},
	"transfer-stock": {
		"component": ROOT / "public" / "js" / "transfer_stock" / "TransferStock.vue",
		"bundle": ROOT / "public" / "js" / "transfer_stock.bundle.js",
		"loader": ROOT / "retailedge" / "page" / "transfer_stock" / "transfer_stock.js",
		"fixture": ROOT / "retailedge" / "page" / "transfer_stock" / "transfer_stock.json",
		"backend": "retailedge.guided_stock_transfer.create_simple_stock_transfer_draft",
	},
	"stock-adjustment": {
		"component": ROOT / "public" / "js" / "stock_adjustment" / "StockAdjustment.vue",
		"bundle": ROOT / "public" / "js" / "stock_adjustment.bundle.js",
		"loader": ROOT / "retailedge" / "page" / "stock_adjustment" / "stock_adjustment.js",
		"fixture": ROOT / "retailedge" / "page" / "stock_adjustment" / "stock_adjustment.json",
		"backend": "retailedge.guided_stock_adjustment.create_simple_stock_adjustment_draft",
	},
}


def test_long_transaction_entry_pages_are_real_edgesuite_pages():
	for route, config in ENTRY_PAGES.items():
		for key in ("component", "bundle", "loader", "fixture"):
			assert config[key].exists(), f"Missing {route} {key}"
		component = config["component"].read_text(encoding="utf-8")
		loader = config["loader"].read_text(encoding="utf-8")
		bundle = config["bundle"].read_text(encoding="utf-8")
		for contract in ("EdgeAppShell", "EdgePageLayout", "EdgePageHeader", f'activeRoute="/app/{route}"'):
			assert contract in component
		assert "<EdgeModal" not in component
		assert "edgeui.bundle.js" in loader
		assert "createEdgeApp" in bundle
		assert "window.EdgeSuiteUI" in bundle
		assert "window.EdgeUI" not in bundle


def test_persistent_pages_reuse_existing_permission_aware_transaction_backends():
	for route, config in ENTRY_PAGES.items():
		component = config["component"].read_text(encoding="utf-8")
		assert config["backend"] in component
		assert "retailedge.master_experience.get_retailedge_business_hub_context" in component
		for forbidden in ("frappe.db.", "frappe.client.insert", "frappe.client.save", "frappe.client.submit", "frappe.db.commit"):
			assert forbidden not in component, f"{route} must not create an alternate accounting or stock write path"


def test_long_transaction_pages_keep_browser_session_recovery_until_draft_save():
	for route, config in ENTRY_PAGES.items():
		component = config["component"].read_text(encoding="utf-8")
		for contract in ("sessionStorage.setItem", "sessionStorage.getItem", "beforeunload", "hasUnsavedChanges", "clearRecovery()"):
			assert contract in component, f"{route} missing recovery contract {contract}"


def test_quick_actions_are_named_as_quick_and_pages_are_named_as_primary_actions():
	registry = REGISTRY.read_text(encoding="utf-8")
	master = MASTER.read_text(encoding="utf-8")
	for quick_label in ("Quick Sale", "Quick Purchase", "Quick Transfer", "Quick Adjustment"):
		assert f'"label": "{quick_label}"' in registry
	for page_label, route in (
		("Make Sale", "make-sale"),
		("Record Purchase", "record-purchase"),
		("Transfer Stock", "transfer-stock"),
		("Stock Adjustment", "stock-adjustment"),
	):
		assert f'"label": "{page_label}"' in master
		assert f'"target": "{route}"' in master
	assert "_promote_make_sale(navigation_groups)" in master
	assert "_promote_long_transaction_pages(navigation_groups)" in master



def test_master_promotions_can_recreate_sell_buy_and_stock_groups_after_native_containment():
	master = MASTER.read_text(encoding="utf-8")
	for contract in (
		'sell_group = next((group for group in navigation_groups if group.get("key") == "sell"), None)',
		'sell_group = {"key": "sell", "label": _("Sell"), "icon": "shopping-cart", "items": []}',
		'group = next((row for row in navigation_groups if row.get("key") == group_key), None)',
		'"buy": {"label": _("Buy"), "icon": "shopping-bag"}',
		'"stock": {"label": _("Stock"), "icon": "layers"}',
	):
		assert contract in master


def test_business_hub_primary_shortcuts_use_pages_not_large_modals():
	hub = HUB.read_text(encoding="utf-8")
	for route, label in (
		("make-sale", "Make Sale"),
		("record-purchase", "Record Purchase"),
		("transfer-stock", "Transfer Stock"),
	):
		assert f'addPage("{route}", "{label}"' in hub
	assert 'addAction("new-sales-invoice", "Make Sale")' not in hub
	assert 'addAction("record-purchase")' not in hub
	assert 'addAction("transfer-stock")' not in hub


def test_quick_modals_warn_before_discard_and_continue_to_full_pages():
	dialogs = {
		ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleSalesInvoiceDialog.vue": ("Discard the unsaved Quick Sale changes?", "Continue in Make Sale", "open-page"),
		ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePurchaseInvoiceDialog.vue": ("Discard the unsaved Quick Purchase changes?", "Continue in Record Purchase", "open-page"),
		ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleStockTransferDialog.vue": ("Discard the unsaved Quick Transfer changes?", "Continue in Transfer Stock", "open-page"),
		ROOT / "public" / "js" / "retailedge_business_hub" / "SimpleStockAdjustmentDialog.vue": ("Discard the unsaved Quick Adjustment changes?", "Continue in Stock Adjustment", "open-page"),
	}
	for path, contracts in dialogs.items():
		source = path.read_text(encoding="utf-8")
		assert "hasUnsavedChanges" in source
		for contract in contracts:
			assert contract in source


def test_business_hub_handoffs_preserve_entered_transaction_context():
	hub = HUB.read_text(encoding="utf-8")
	for route in ("make-sale", "record-purchase", "transfer-stock", "stock-adjustment"):
		assert f'"retailedge:{route}:handoff:"' in hub
		assert f'frappe.set_route("{route}")' in hub
	assert 'encodeURIComponent(frappe.session?.user || "Guest")' in hub


def test_transaction_workspace_exposes_full_page_primary_and_quick_companions():
	source = TRANSACTION_WORKSPACE.read_text(encoding="utf-8")
	backend = TRANSACTION_WORKSPACE_BACKEND.read_text(encoding="utf-8")
	for label in ("Quick Sale", "Quick Purchase", "Quick Transfer", "Quick Adjustment"):
		assert f">{label}<" in source
	for route in ("make-sale", "record-purchase", "transfer-stock", "stock-adjustment"):
		assert route in source
	assert '"doctype": "Stock Reconciliation"' in backend


def test_payment_quick_entry_has_full_page_complex_allocation_escape_paths():
	dialog = (ROOT / "public" / "js" / "retailedge_business_hub" / "SimplePaymentDialog.vue").read_text(encoding="utf-8")
	payment_management = (ROOT / "public" / "js" / "payment_management" / "PaymentManagement.vue").read_text(encoding="utf-8")
	for contract in (
		"Discard the unsaved Quick Payment changes?",
		"Open {{ managedPageLabel }}",
		'"supplier-payables"',
		'"payment-management"',
		"retailedge_business_hub_handoff",
	):
		assert contract in dialog
	assert 'retailedgeConsumeBusinessHubRouteOptions?.("payment-management")' in payment_management
	assert "routeCustomer" in payment_management
	assert "routeBranch" in payment_management




def test_business_hub_quick_sale_and_purchase_continue_after_submission():
	hub = HUB.read_text(encoding="utf-8")
	for contract in (
		'StandardDeliveryCompletionDialog',
		':showNextActions="true"',
		'@next-action="handleSalesInvoiceCompletionNextAction"',
		'@next-action="handlePurchaseInvoiceCompletionNextAction"',
		'CREATE_DELIVERY_METHOD',
		'simplePaymentInitialContext',
		'"receive-customer-payment"',
		'"pay-supplier"',
		'"supplier-payables"',
		'"document-output-sharing"',
	):
		assert contract in hub
	assert "handleSalesInvoiceCompletionCompleted() {\n\t\t\tthis.refreshContext" in hub
	assert "handlePurchaseInvoiceCompletionCompleted() {\n\t\t\tthis.refreshContext" in hub


def test_guided_api_helper_preserves_explicit_http_method():
	utils = (ROOT / "public" / "js" / "retailedge_business_hub" / "guidedEntryUtils.js").read_text(encoding="utf-8")
	assert 'function rawCall(method, args = {}, type = "POST")' in utils
	assert "frappe.call({" in utils
	assert "\n\t\t\ttype," in utils
	assert 'export function callMethod(method, args = {}, type = "POST")' in utils
	assert 'if (type === "POST") return rawCall(method, args);' in utils
	assert "return rawCall(method, args, type);" in utils


def test_quick_entry_is_explicitly_bounded_to_small_line_counts():
	utils = (ROOT / "public" / "js" / "retailedge_business_hub" / "guidedEntryUtils.js").read_text(encoding="utf-8")
	assert "export const QUICK_ENTRY_MAX_LINES = 10;" in utils

	for filename in (
		"SimpleSalesInvoiceDialog.vue",
		"SimplePurchaseInvoiceDialog.vue",
		"SimpleStockTransferDialog.vue",
		"SimpleStockAdjustmentDialog.vue",
	):
		source = (ROOT / "public" / "js" / "retailedge_business_hub" / filename).read_text(encoding="utf-8")
		assert "QUICK_ENTRY_MAX_LINES" in source
		assert "quickEntryTooLarge" in source
		assert "populatedItemCount" in source
		assert "Continue in" in source
		assert "quickEntryTooLarge" in source
		assert '|| quickEntryTooLarge' in source


def test_persistent_transaction_pages_fail_closed_for_native_desk_and_scope_handoffs_to_user():
	for route, config in ENTRY_PAGES.items():
		source = config["component"].read_text(encoding="utf-8")
		assert 'Boolean(shell.access?.can_use_native_desk)' in source
		assert '&& shell.feature_flags?.native_document_fallback_enabled !== false' in source
		assert 'if (!this.canUseNativeDesk) return;' in source
		assert 'encodeURIComponent(frappe.session?.user || "Guest")' in source
		assert f'retailedge:{route}:handoff:' in source
		assert 'window.EdgeUI' not in source

	workspace = TRANSACTION_WORKSPACE.read_text(encoding="utf-8")
	assert ':nativeFallbackEnabled="false"' in workspace
	assert "openNativePurchaseInvoice" not in workspace





def test_persistent_pages_do_not_auto_open_completion_after_first_save():
	for route in ("make-sale", "record-purchase", "transfer-stock", "stock-adjustment"):
		source = ENTRY_PAGES[route]["component"].read_text(encoding="utf-8")
		assert "Continue Editing on Page" in source
		assert "Review / Complete" in source
		create_segment = source[source.index("async saveDraft()"):source.index("openCompletion", source.index("async saveDraft()")) if "openCompletion" in source[source.index("async saveDraft()"):] else len(source)]
		assert "this.completionOpen = false" in create_segment


def test_persistent_pages_keep_saved_draft_editing_on_the_page():
	contracts = {
		"make-sale": "update_standard_sales_invoice_draft",
		"record-purchase": "update_standard_purchase_invoice_draft",
		"transfer-stock": "update_standard_stock_document_draft",
		"stock-adjustment": "update_standard_stock_document_draft",
	}
	for route, update_method in contracts.items():
		source = ENTRY_PAGES[route]["component"].read_text(encoding="utf-8")
		assert "editingSavedDraft" in source
		assert "Continue Editing on Page" in source
		assert "Review / Complete" in source
		assert update_method in source
		assert "expected_modified: this.savedDocument.modified" in source
		assert "this.initialSnapshot = JSON.stringify(this.values)" in source
		assert "Cancel Edit" in source
		assert "savedDocument && !editingSavedDraft" in source
		assert "!savedDocument || editingSavedDraft" in source


def test_persistent_page_creators_return_modified_for_stale_safe_updates():
	creators = (
		ROOT / "guided_sales_invoice.py",
		ROOT / "guided_purchase_invoice.py",
		ROOT / "guided_stock_transfer.py",
		ROOT / "guided_stock_adjustment.py",
	)
	for path in creators:
		source = path.read_text(encoding="utf-8")
		assert '"modified": str(doc.modified or "")' in source


def test_saved_draft_page_editing_locks_business_context_after_first_save():
	make_sale = ENTRY_PAGES["make-sale"]["component"].read_text(encoding="utf-8")
	assert ':disabled="editingSavedDraft"' in make_sale
	assert ':disabled="editingSavedDraft || !canEditUpdateStock"' in make_sale
	assert ':disabled="editingSavedDraft || (requiresBranchSelection && !values.branch)"' in make_sale

	purchase = ENTRY_PAGES["record-purchase"]["component"].read_text(encoding="utf-8")
	assert ':disabled="editingSavedDraft"' in purchase
	assert ':disabled="editingSavedDraft || !canEditUpdateStock"' in purchase
	assert ':disabled="editingSavedDraft || (requiresBranchSelection && !values.branch)"' in purchase

	transfer = ENTRY_PAGES["transfer-stock"]["component"].read_text(encoding="utf-8")
	assert ':disabled="editingSavedDraft"' in transfer
	assert ':disabled="editingSavedDraft || (requiresBranchSelection && !values.source_branch)"' in transfer
	assert ':disabled="editingSavedDraft || (requiresBranchSelection && !values.target_branch)"' in transfer

	adjustment = ENTRY_PAGES["stock-adjustment"]["component"].read_text(encoding="utf-8")
	assert ':disabled="editingSavedDraft"' in adjustment


def test_stock_full_pages_preserve_submitted_result_and_hide_edit_complete_after_submit():
	for route in ("transfer-stock", "stock-adjustment"):
		source = ENTRY_PAGES[route]["component"].read_text(encoding="utf-8")
		assert 'Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved"' in source
		assert 'v-if="Number(savedDocument.docstatus || 0) === 0"' in source
		assert "handleCompletionCompleted(result)" in source
		assert "this.savedDocument = { ...this.savedDocument, ...result" in source



def test_sales_and_purchase_draft_editors_fail_closed_on_noneditable_completion_blockers():
	sales = (ROOT / "standard_sales_invoice_completion.py").read_text(encoding="utf-8")
	purchase = (ROOT / "standard_purchase_invoice_completion.py").read_text(encoding="utf-8")

	assert "def _standard_invoice_blockers(doc, *, include_date_validation: bool = True)" in sales
	assert "_standard_invoice_blockers(doc, include_date_validation=False)" in sales
	assert 'Sales Invoice draft editing is blocked:' in sales
	assert "and not edit_blockers" in sales
	assert "include_date_validation and posting_date and due_date" in sales

	assert 'Purchase Invoice draft editing is blocked:' in purchase
	assert 'and not blockers and frappe.has_permission(PURCHASE_INVOICE_DOCTYPE, "write", doc=doc)' in purchase



def test_browser_recovery_revalidates_current_branch_and_warehouse_access():
	for route, config in ENTRY_PAGES.items():
		source = config["component"].read_text(encoding="utf-8")
		assert "async restoreRecovery()" in source
		assert "resolveBranchWarehouse({" in source
		assert "access could not be revalidated" in source or "no longer available" in source
		assert 'this.recoveryCandidate = null' in source


def test_quick_entry_change_does_not_mutate_submitted_accounting_truth():
	for config in ENTRY_PAGES.values():
		source = config["component"].read_text(encoding="utf-8")
		for forbidden in (
			".submit()",
			"frappe.client.submit",
			"frappe.db.set_value",
			"Stock Ledger Entry",
			"GL Entry",
		):
			assert forbidden not in source
