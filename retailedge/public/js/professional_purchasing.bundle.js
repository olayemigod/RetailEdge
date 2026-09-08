import ProfessionalPurchasing from "./professional_purchasing/ProfessionalPurchasing.vue";
import ProfessionalRfqPreviewOverlay from "./professional_purchasing/ProfessionalRfqPreviewOverlay.vue";
import ProfessionalRfqHistoryOverlay from "./professional_purchasing/ProfessionalRfqHistoryOverlay.vue";
import ProfessionalSupplierQuotationHistoryOverlay from "./professional_purchasing/ProfessionalSupplierQuotationHistoryOverlay.vue";
import ProfessionalSupplierQuotationPurchaseOrderOverlay from "./professional_purchasing/ProfessionalSupplierQuotationPurchaseOrderOverlay.vue";

const START_RFQ_LABEL = "Start RFQ";
const RFQS_LABEL = "RFQs";
const RFQ_HISTORY_LABEL = "RFQ History";
const SUPPLIER_QUOTATIONS_LABEL = "Supplier Quotations";
const SUPPLIER_QUOTATION_HISTORY_LABEL = "Supplier Quote History";
const COMPARE_QUOTATIONS_LABEL = "Compare Quotations";
const ADVANCED_COMPARE_QUOTATIONS_LABEL = "Advanced: Compare Quotations in ERPNext";
const ADVANCED_MATERIAL_REQUEST_LABEL = "Advanced: Open in ERPNext";
const OPEN_RFQ_PREVIEW_EVENT = "retailedge-open-professional-rfq-preview";
const OPEN_RFQ_HISTORY_EVENT = "retailedge-open-professional-rfq-history";
const OPEN_SUPPLIER_QUOTATION_HISTORY_EVENT = "retailedge-open-professional-supplier-quotation-history";
const ADVANCED_RFQ_EVENT = "retailedge-advanced-prepare-rfq";
const PREPARE_RFQ_METHOD = "retailedge.professional_sourcing.prepare_request_for_quotation_draft_advanced";
const ACCESS_MODE = "edgesuite_only";

function normaliseButtonLabel(button) {
	return String(button?.textContent || "").replace(/\s+/g, " ").trim();
}

function nativeDeskEnabled() {
	return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE;
}

function materialRequestFromRow(button) {
	const row = button?.closest?.(".sourcing-panel tbody tr");
	if (!row) return "";
	const reference = row.querySelector("td .retailedge-material-request-reference, td .link-button");
	return String(reference?.textContent || "").trim();
}

function applySourcingOwnership(target) {
	if (!target) return;
	for (const button of target.querySelectorAll("button")) {
		const label = normaliseButtonLabel(button);
		if (label === RFQS_LABEL) {
			button.hidden = false;
			button.removeAttribute("aria-hidden");
			button.textContent = __(RFQ_HISTORY_LABEL);
			button.setAttribute("title", __("Review Requests for Quotation inside RetailEdge."));
			button.setAttribute("data-retailedge-rfq-history", "true");
			continue;
		}
		if (label === SUPPLIER_QUOTATIONS_LABEL) {
			button.hidden = false;
			button.removeAttribute("aria-hidden");
			button.textContent = __(SUPPLIER_QUOTATION_HISTORY_LABEL);
			button.setAttribute("title", __("Review Supplier Quotations inside RetailEdge."));
			button.setAttribute("data-retailedge-supplier-quotation-history", "true");
			continue;
		}
		if ([COMPARE_QUOTATIONS_LABEL, ADVANCED_COMPARE_QUOTATIONS_LABEL].includes(label)) {
			if (!nativeDeskEnabled()) {
				button.hidden = true;
				button.setAttribute("aria-hidden", "true");
				continue;
			}
			button.hidden = false;
			button.removeAttribute("aria-hidden");
			button.textContent = __(ADVANCED_COMPARE_QUOTATIONS_LABEL);
			button.setAttribute("title", __("Open ERPNext's Supplier Quotation Comparison report for advanced analysis."));
			button.setAttribute("data-retailedge-advanced-native", "Supplier Quotation Comparison");
		}
	}
	for (const row of target.querySelectorAll(".sourcing-panel tbody tr")) {
		const reference = row.querySelector("td .link-button");
		if (reference) {
			reference.classList.remove("link-button");
			reference.classList.add("retailedge-material-request-reference");
			reference.setAttribute("aria-disabled", "true");
			reference.setAttribute("title", __("Material Request reference. Use Start RFQ for the normal sourcing workflow."));
			reference.tabIndex = -1;
		}
		for (const button of row.querySelectorAll(".actions-cell button")) {
			const label = normaliseButtonLabel(button);
			if (label !== "Open") continue;
			if (!nativeDeskEnabled()) {
				button.hidden = true;
				button.setAttribute("aria-hidden", "true");
				continue;
			}
			button.hidden = false;
			button.removeAttribute("aria-hidden");
			button.textContent = __(ADVANCED_MATERIAL_REQUEST_LABEL);
			button.setAttribute("title", __("Open the full ERPNext Material Request form for advanced review."));
			button.setAttribute("data-retailedge-advanced-native", "Material Request");
		}
	}
}

function installSourcingOwnership(target) {
	if (!target || target._retailedgeSourcingOwnershipInstalled) return () => {};
	let scheduled = false;
	const scheduleApply = () => {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(() => {
			scheduled = false;
			applySourcingOwnership(target);
		});
	};
	const handler = (event) => {
		const button = event.target?.closest?.("button");
		if (!button || !target.contains(button)) return;
		const label = normaliseButtonLabel(button);
		if (button.classList.contains("retailedge-material-request-reference")) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			return;
		}
		if (label === START_RFQ_LABEL) {
			const materialRequest = materialRequestFromRow(button);
			if (!materialRequest) return;
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			window.dispatchEvent(new CustomEvent(OPEN_RFQ_PREVIEW_EVENT, { detail: { material_request: materialRequest } }));
			return;
		}
		if ([RFQS_LABEL, RFQ_HISTORY_LABEL].includes(label) || button.getAttribute("data-retailedge-rfq-history") === "true") {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			window.dispatchEvent(new CustomEvent(OPEN_RFQ_HISTORY_EVENT));
			return;
		}
		if ([SUPPLIER_QUOTATIONS_LABEL, SUPPLIER_QUOTATION_HISTORY_LABEL].includes(label) || button.getAttribute("data-retailedge-supplier-quotation-history") === "true") {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			window.dispatchEvent(new CustomEvent(OPEN_SUPPLIER_QUOTATION_HISTORY_EVENT));
			return;
		}
		if (!nativeDeskEnabled() && [ADVANCED_MATERIAL_REQUEST_LABEL, COMPARE_QUOTATIONS_LABEL, ADVANCED_COMPARE_QUOTATIONS_LABEL].includes(label)) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
		}
	};
	target.addEventListener("click", handler, true);
	const observer = new MutationObserver(scheduleApply);
	observer.observe(target, { childList: true, subtree: true });
	target._retailedgeSourcingOwnershipInstalled = true;
	scheduleApply();
	return () => {
		observer.disconnect();
		target.removeEventListener("click", handler, true);
		target._retailedgeSourcingOwnershipInstalled = false;
	};
}

function installAdvancedRfqHandoff() {
	const handler = (event) => {
		if (!nativeDeskEnabled()) return;
		const materialRequest = String(event?.detail?.material_request || "").trim();
		const suppliers = Array.isArray(event?.detail?.suppliers) ? event.detail.suppliers.filter(Boolean) : [];
		if (!materialRequest || !suppliers.length) return;
		frappe.call({
			method: PREPARE_RFQ_METHOD,
			type: "POST",
			args: { material_request: materialRequest, suppliers },
			callback(response) {
				const result = response.message || {};
				if (result.name) frappe.set_route("Form", "Request for Quotation", result.name);
			},
		});
	};
	window.addEventListener(ADVANCED_RFQ_EVENT, handler);
	return () => window.removeEventListener(ADVANCED_RFQ_EVENT, handler);
}

function mountRetailEdgeProfessionalPurchasing(target) {
	if (typeof window === "undefined") return null;
	const edgeUI = window.EdgeSuiteUI;
	if (!edgeUI?.createEdgeApp) throw new Error("EdgeSuite UI runtime compatibility error: createEdgeApp is missing");
	if (!target) throw new Error("Professional Purchasing mount target is required");
	const app = edgeUI.createEdgeApp(ProfessionalPurchasing);
	app.mount(target);

	const overlayRoot = document.createElement("div");
	overlayRoot.className = "retailedge-professional-rfq-preview-overlay-root";
	(target.parentNode || target).appendChild(overlayRoot);
	const overlayApp = edgeUI.createEdgeApp(ProfessionalRfqPreviewOverlay);
	overlayApp.mount(overlayRoot);

	const historyRoot = document.createElement("div");
	historyRoot.className = "retailedge-professional-rfq-history-overlay-root";
	(target.parentNode || target).appendChild(historyRoot);
	const historyApp = edgeUI.createEdgeApp(ProfessionalRfqHistoryOverlay);
	historyApp.mount(historyRoot);

	const supplierQuotationHistoryRoot = document.createElement("div");
	supplierQuotationHistoryRoot.className = "retailedge-professional-supplier-quotation-history-overlay-root";
	(target.parentNode || target).appendChild(supplierQuotationHistoryRoot);
	const supplierQuotationHistoryApp = edgeUI.createEdgeApp(ProfessionalSupplierQuotationHistoryOverlay);
	supplierQuotationHistoryApp.mount(supplierQuotationHistoryRoot);

	const supplierQuotationPurchaseOrderRoot = document.createElement("div");
	supplierQuotationPurchaseOrderRoot.className = "retailedge-supplier-quotation-purchase-order-overlay-root";
	(target.parentNode || target).appendChild(supplierQuotationPurchaseOrderRoot);
	const supplierQuotationPurchaseOrderApp = edgeUI.createEdgeApp(ProfessionalSupplierQuotationPurchaseOrderOverlay);
	supplierQuotationPurchaseOrderApp.mount(supplierQuotationPurchaseOrderRoot);

	const cleanupSourcing = installSourcingOwnership(target);
	const cleanupAdvanced = installAdvancedRfqHandoff();
	const originalUnmount = typeof app.unmount === "function" ? app.unmount.bind(app) : null;
	if (originalUnmount) {
		app.unmount = () => {
			cleanupSourcing();
			cleanupAdvanced();
			overlayApp.unmount?.();
			historyApp.unmount?.();
			supplierQuotationHistoryApp.unmount?.();
			supplierQuotationPurchaseOrderApp.unmount?.();
			overlayRoot.remove();
			historyRoot.remove();
			supplierQuotationHistoryRoot.remove();
			supplierQuotationPurchaseOrderRoot.remove();
			originalUnmount();
		};
	}
	app._retailedgeRfqPreviewApp = overlayApp;
	app._retailedgeRfqHistoryApp = historyApp;
	app._retailedgeSupplierQuotationHistoryApp = supplierQuotationHistoryApp;
	app._retailedgeSupplierQuotationPurchaseOrderApp = supplierQuotationPurchaseOrderApp;
	return app;
}

if (typeof window !== "undefined") {
	window.RetailEdgeProfessionalPurchasing = ProfessionalPurchasing;
	window.mountRetailEdgeProfessionalPurchasing = mountRetailEdgeProfessionalPurchasing;
}

export { mountRetailEdgeProfessionalPurchasing };
export default ProfessionalPurchasing;
