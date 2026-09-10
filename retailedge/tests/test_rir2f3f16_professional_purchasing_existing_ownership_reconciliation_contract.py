from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPONENT = ROOT / "public/js/professional_purchasing/ProfessionalPurchasing.vue"
PAGE = ROOT / "retailedge/page/professional_purchasing/professional_purchasing.js"
BUNDLE = ROOT / "public/js/professional_purchasing.bundle.js"


def _read(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_component_uses_final_fail_closed_native_desk_capability():
	source = _read(COMPONENT)
	assert "canUseNativeDesk: false" in source
	assert "this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);" in source


def test_existing_edgesuite_owned_actions_are_delegated_by_component_source():
	source = _read(COMPONENT)
	for event_name in (
		"retailedge-open-professional-purchase-order",
		"retailedge-open-professional-rfq-preview",
		"retailedge-open-professional-rfq-history",
		"retailedge-open-professional-supplier-quotation-history",
		"retailedge-open-professional-purchase-receipt-preview",
		"retailedge-open-professional-purchase-receipt-history",
	):
		assert event_name in source
	assert "dispatchEdgeSuiteEvent(OPEN_PURCHASE_ORDER_EVENT)" in source
	assert "dispatchEdgeSuiteEvent(OPEN_RFQ_PREVIEW_EVENT" in source
	assert "dispatchEdgeSuiteEvent(OPEN_RFQ_HISTORY_EVENT)" in source
	assert "dispatchEdgeSuiteEvent(OPEN_SUPPLIER_QUOTATION_HISTORY_EVENT)" in source
	assert "dispatchEdgeSuiteEvent(OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT" in source
	assert "dispatchEdgeSuiteEvent(OPEN_PURCHASE_RECEIPT_HISTORY_EVENT)" in source


def test_stale_standard_native_draft_paths_are_not_used_by_component():
	source = _read(COMPONENT)
	assert 'const PREPARE_RFQ_METHOD = "retailedge.professional_purchasing.prepare_request_for_quotation_draft"' not in source
	assert 'const PREPARE_RECEIPT_METHOD = "retailedge.professional_purchasing.prepare_purchase_receipt_draft"' not in source
	assert 'frappe.new_doc("Purchase Order")' not in source
	assert 'frappe.set_route("Form", "Request for Quotation", result.name)' not in source

	prepare_receipt = source.split("\t\tprepareReceipt(row) {", 1)[1].split("\n\t\tasync preparePurchaseReturn()", 1)[0]
	assert "dispatchEdgeSuiteEvent(OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT" in prepare_receipt
	assert "prepare_purchase_receipt_draft" not in prepare_receipt
	assert 'frappe.set_route("Form", "Purchase Receipt", result.name)' not in prepare_receipt


def test_advanced_native_methods_and_menu_routes_fail_closed():
	source = _read(COMPONENT)
	assert 'if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;' in source
	assert 'openMaterialRequest(name) { if (this.canUseNativeDesk && name)' in source
	assert 'openMaterialRequests() { if (this.canUseNativeDesk)' in source
	assert 'openSupplierQuotationComparison() { if (!this.canUseNativeDesk) return;' in source
	assert 'openPurchaseOrderAnalysis() { if (!this.canUseNativeDesk) return;' in source
	assert 'openProcurementTracker() { if (!this.canUseNativeDesk || !this.procurementTracker?.available) return;' in source
	assert 'openPurchaseOrder(name) { if (this.canUseNativeDesk && name)' in source


def test_existing_page_controller_and_bundle_ownership_remain_defence_in_depth():
	page = _read(PAGE)
	bundle = _read(BUNDLE)
	assert "installGuidedPurchaseOrderTrigger(wrapper, root)" in page
	assert "installPurchaseOrderOwnership(wrapper, root)" in page
	assert "installRestrictedOperationalGuard()" in page
	assert "ProfessionalRfqPreviewOverlay" in bundle
	assert "ProfessionalRfqHistoryOverlay" in bundle
	assert "ProfessionalSupplierQuotationHistoryOverlay" in bundle
	assert "ProfessionalPurchaseOrderSubmitOverlay" in bundle


def test_unresolved_return_and_quality_ownership_is_not_silently_removed():
	source = _read(COMPONENT)
	assert "Returns & Supplier Credits" in source
	assert "preparePurchaseReturn" in source
	assert "prepareSupplierDebitNote" in source
	assert "IncomingQualityInspection" in source
	purchase_return = source.split("\t\tasync preparePurchaseReturn() {", 1)[1].split("\n\t\tasync prepareSupplierDebitNote()", 1)[0]
	assert 'frappe.set_route("Form", "Purchase Receipt", result.name)' in purchase_return
