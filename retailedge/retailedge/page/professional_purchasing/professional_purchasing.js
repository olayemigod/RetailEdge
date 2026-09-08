const EDGEUI_ASSET = "edgeui.bundle.js";
const RESTRICTED_GUARD_ASSET = "retailedge_edgesuite_only_operational_guard.bundle.js";
const PURCHASING_ASSET = "professional_purchasing.bundle.js";
const PURCHASE_ORDER_ASSET = "professional_purchase_order.bundle.js";
const PURCHASE_RECEIPT_PREVIEW_ASSET = "professional_purchase_receipt_preview.bundle.js";
const PURCHASE_RECEIPT_HISTORY_ASSET = "professional_purchase_receipt_history.bundle.js";
const PAGE_ROUTE = "professional-purchasing";
const PAGE_TITLE = "Professional Purchasing";
const OPEN_PURCHASE_ORDER_EVENT = "retailedge-open-professional-purchase-order";
const OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT = "retailedge-open-professional-purchase-receipt-preview";
const OPEN_PURCHASE_RECEIPT_HISTORY_EVENT = "retailedge-open-professional-purchase-receipt-history";
const ADVANCED_PREPARE_RECEIPT_EVENT = "retailedge-advanced-prepare-purchase-receipt";
const PURCHASE_ORDER_TRIGGER_LABEL = "New Purchase Order";
const PREPARE_RECEIPT_TRIGGER_LABEL = "Prepare Receipt";
const REVIEW_RECEIPT_TRIGGER_LABEL = "Review Receipt";
const PURCHASE_RECEIPTS_TRIGGER_LABEL = "Purchase Receipts";
const RECEIPT_HISTORY_TRIGGER_LABEL = "Receipt History";
const ACCESS_MODE = "edgesuite_only";
const ADVANCED_PURCHASE_ORDER_LABEL = "Advanced: Open in ERPNext";
const ADVANCED_PURCHASE_RECEIPTS_LABEL = "Advanced: Purchase Receipts in ERPNext";
const PREPARE_RECEIPT_METHOD = "retailedge.professional_purchasing.prepare_purchase_receipt_draft";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => { if (completed) return; completed = true; resolve(); };
		const fail = (error) => { if (completed) return; completed = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); };
		try {
			const pending = frappe.require(assetName, finish);
			if (pending && typeof pending.then === "function") pending.then(finish).catch(fail);
		} catch (error) { fail(error); }
	});
}

function hideNativePageSidebar(wrapper) {
	const pageContainer = wrapper.closest?.(".page-container") || wrapper;
	const sideSection = pageContainer.querySelector?.(".layout-side-section");
	const mainWrapper = pageContainer.querySelector?.(".layout-main-section-wrapper");
	if (sideSection) {
		sideSection.hidden = true;
		sideSection.setAttribute("aria-hidden", "true");
	}
	if (mainWrapper) {
		mainWrapper.style.width = "100%";
		mainWrapper.style.maxWidth = "100%";
		mainWrapper.classList.add("retailedge-edgeui-main");
	}
}

function installRestrictedOperationalGuard() {
	if (typeof window.retailedgeInstallEdgesuiteOnlyOperationalGuard !== "function") {
		throw new Error("RetailEdge EdgeSuite-only operational guard is unavailable.");
	}
	window.retailedgeInstallEdgesuiteOnlyOperationalGuard({
		pageRoute: PAGE_ROUTE,
		rootSelector: ".retailedge-professional-purchasing-root",
		nativeDoctypes: [
			"Material Request",
			"Request for Quotation",
			"Supplier Quotation",
			"Purchase Order",
			"Purchase Receipt",
			"Purchase Invoice",
			"Landed Cost Voucher",
			"Quality Inspection",
			"Supplier Scorecard",
		],
		nativePathSlugs: [
			"material-request",
			"request-for-quotation",
			"supplier-quotation",
			"purchase-order",
			"purchase-receipt",
			"purchase-invoice",
			"landed-cost-voucher",
			"quality-inspection",
			"supplier-scorecard",
		],
		nativeReports: ["Supplier Quotation Comparison", "Purchase Order Analysis", "Procurement Tracker"],
		hiddenButtonLabels: [
			"RFQs",
			"Supplier Quotations",
			"Compare Quotations",
			"PO Analysis",
			"Procurement Tracker",
			"Material Requests",
			"Open",
			ADVANCED_PURCHASE_ORDER_LABEL,
			ADVANCED_PURCHASE_RECEIPTS_LABEL,
			"Open Purchase Receipt",
			"Scorecards",
			"New Native Scorecard",
			"Open Native Scorecard",
			"Open Full Form",
		],
		hiddenSelectors: [".landed-cost-panel", ".quality-created-links"],
		neutralizeSelectors: [".link-button"],
	});
}

function normaliseButtonLabel(button) {
	return String(button?.textContent || "").replace(/\s+/g, " ").trim();
}

function nativeDeskEnabled() {
	return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE;
}

function purchaseOrderFromRow(button) {
	const row = button?.closest?.(".purchasing-table--orders tbody tr");
	if (!row) return "";
	const reference = row.querySelector("td .retailedge-po-reference, td .link-button");
	return String(reference?.textContent || "").trim();
}

function applyPurchaseOrderOwnership(root) {
	if (!root) return;
	for (const row of root.querySelectorAll(".purchasing-table--orders tbody tr")) {
		const reference = row.querySelector("td .link-button");
		if (reference) {
			reference.classList.remove("link-button");
			reference.classList.add("retailedge-po-reference");
			reference.setAttribute("aria-disabled", "true");
			reference.setAttribute("title", __("Purchase Order reference. Use the explicit Advanced action only when native ERPNext review is required."));
			reference.tabIndex = -1;
		}
		for (const button of row.querySelectorAll(".actions-cell button")) {
			const label = normaliseButtonLabel(button);
			if (label === "Open") {
				if (!nativeDeskEnabled()) {
					button.hidden = true;
					button.setAttribute("aria-hidden", "true");
					continue;
				}
				button.textContent = __(ADVANCED_PURCHASE_ORDER_LABEL);
				button.setAttribute("title", __("Open the full ERPNext Purchase Order form for advanced review."));
				button.setAttribute("data-retailedge-advanced-native", "Purchase Order");
			}
			if (label === PREPARE_RECEIPT_TRIGGER_LABEL) {
				button.hidden = false;
				button.removeAttribute("aria-hidden");
				button.removeAttribute("data-retailedge-parity-blocked");
				button.textContent = __(REVIEW_RECEIPT_TRIGGER_LABEL);
				button.setAttribute("title", __("Preview ERPNext's Purchase Receipt mapping in RetailEdge. No draft or stock movement is created."));
				button.setAttribute("data-retailedge-receipt-preview", "true");
			}
		}
	}
}

function applyPurchaseReceiptParityGate(root) {
	if (!root) return;
	for (const button of root.querySelectorAll("button")) {
		const label = normaliseButtonLabel(button);
		if (![PURCHASE_RECEIPTS_TRIGGER_LABEL, RECEIPT_HISTORY_TRIGGER_LABEL].includes(label)) continue;
		button.hidden = false;
		button.removeAttribute("aria-hidden");
		button.removeAttribute("data-retailedge-parity-blocked");
		button.removeAttribute("data-retailedge-advanced-native");
		button.textContent = __(RECEIPT_HISTORY_TRIGGER_LABEL);
		button.setAttribute("title", __("Review submitted Purchase Receipts inside RetailEdge."));
		button.setAttribute("data-retailedge-receipt-history", "true");
	}
}

function installPurchaseOrderOwnership(wrapper, root) {
	if (!root || wrapper._retailedgePurchaseOrderOwnershipInstalled) return;
	let scheduled = false;
	const scheduleApply = () => {
		if (scheduled) return;
		scheduled = true;
		window.requestAnimationFrame(() => {
			scheduled = false;
			applyPurchaseOrderOwnership(root);
			applyPurchaseReceiptParityGate(root);
		});
	};
	const handler = (event) => {
		const button = event.target?.closest?.("button");
		if (!button || !root.contains(button)) return;
		const label = normaliseButtonLabel(button);
		if (button.closest(".purchasing-table--orders") && button.classList.contains("retailedge-po-reference")) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			return;
		}
		if ([PREPARE_RECEIPT_TRIGGER_LABEL, REVIEW_RECEIPT_TRIGGER_LABEL].includes(label) || button.getAttribute("data-retailedge-receipt-preview") === "true") {
			const purchaseOrder = purchaseOrderFromRow(button);
			if (!purchaseOrder) return;
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			window.dispatchEvent(new CustomEvent(OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT, { detail: { purchase_order: purchaseOrder } }));
			return;
		}
		if ([PURCHASE_RECEIPTS_TRIGGER_LABEL, RECEIPT_HISTORY_TRIGGER_LABEL].includes(label) || button.getAttribute("data-retailedge-receipt-history") === "true") {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			window.dispatchEvent(new CustomEvent(OPEN_PURCHASE_RECEIPT_HISTORY_EVENT));
			return;
		}
		if (!nativeDeskEnabled() && [ADVANCED_PURCHASE_ORDER_LABEL, ADVANCED_PURCHASE_RECEIPTS_LABEL].includes(label)) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
		}
	};
	root.addEventListener("click", handler, true);
	const observer = new MutationObserver(scheduleApply);
	observer.observe(root, { childList: true, subtree: true });
	wrapper._retailedgePurchaseOrderOwnershipInstalled = true;
	wrapper._retailedgePurchaseOrderOwnershipCleanup = () => {
		observer.disconnect();
		root.removeEventListener("click", handler, true);
		wrapper._retailedgePurchaseOrderOwnershipInstalled = false;
	};
	scheduleApply();
}

function installGuidedPurchaseOrderTrigger(wrapper, root) {
	if (!root || wrapper._retailedgePurchaseOrderTriggerInstalled) return;
	const handler = (event) => {
		const button = event.target?.closest?.("button");
		if (!button || !root.contains(button)) return;
		if (normaliseButtonLabel(button) !== PURCHASE_ORDER_TRIGGER_LABEL) return;
		event.preventDefault();
		event.stopPropagation();
		event.stopImmediatePropagation();
		window.dispatchEvent(new CustomEvent(OPEN_PURCHASE_ORDER_EVENT));
	};
	root.addEventListener("click", handler, true);
	wrapper._retailedgePurchaseOrderTriggerInstalled = true;
	wrapper._retailedgePurchaseOrderTriggerCleanup = () => {
		root.removeEventListener("click", handler, true);
		wrapper._retailedgePurchaseOrderTriggerInstalled = false;
	};
}

function installAdvancedReceiptHandoff(wrapper) {
	if (wrapper._retailedgeAdvancedReceiptHandoffInstalled) return;
	const handler = (event) => {
		if (!nativeDeskEnabled()) return;
		const purchaseOrder = String(event?.detail?.purchase_order || "").trim();
		if (!purchaseOrder) return;
		frappe.call({
			method: PREPARE_RECEIPT_METHOD,
			type: "POST",
			args: { purchase_order: purchaseOrder },
			callback(response) {
				const result = response.message || {};
				if (result.name) frappe.set_route("Form", "Purchase Receipt", result.name);
			},
		});
	};
	window.addEventListener(ADVANCED_PREPARE_RECEIPT_EVENT, handler);
	wrapper._retailedgeAdvancedReceiptHandoffInstalled = true;
	wrapper._retailedgeAdvancedReceiptHandoffCleanup = () => {
		window.removeEventListener(ADVANCED_PREPARE_RECEIPT_EVENT, handler);
		wrapper._retailedgeAdvancedReceiptHandoffInstalled = false;
	};
}

function renderLoadError(wrapper, error) {
	const node = document.createElement("div");
	node.className = "professional-purchasing-load-error alert alert-danger p-6 text-center";
	const title = document.createElement("strong");
	title.textContent = __(`${PAGE_TITLE} failed to load`);
	const detail = document.createElement("div");
	detail.textContent = error?.message || __("Unknown page load error");
	node.append(title, detail);
	wrapper.appendChild(node);
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const bootLoading = document.createElement("div");
	bootLoading.className = "edge-boot-loading p-6 text-center text-muted";
	bootLoading.textContent = __(`Loading ${PAGE_TITLE}...`);
	wrapper.appendChild(bootLoading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("EdgeSuite UI runtime is unavailable.");
		await requireAsync(RESTRICTED_GUARD_ASSET);
		installRestrictedOperationalGuard();
		await Promise.all([requireAsync(PURCHASING_ASSET), requireAsync(PURCHASE_ORDER_ASSET), requireAsync(PURCHASE_RECEIPT_PREVIEW_ASSET), requireAsync(PURCHASE_RECEIPT_HISTORY_ASSET)]);
		if (typeof window.mountRetailEdgeProfessionalPurchasing !== "function") throw new Error("Professional Purchasing bundle is unavailable.");
		if (typeof window.mountRetailEdgeProfessionalPurchaseOrder !== "function") throw new Error("Professional Purchase Order bundle is unavailable.");
		if (typeof window.mountRetailEdgeProfessionalPurchaseReceiptPreview !== "function") throw new Error("Professional Purchase Receipt preview bundle is unavailable.");
		if (typeof window.mountRetailEdgeProfessionalPurchaseReceiptHistory !== "function") throw new Error("Professional Purchase Receipt history bundle is unavailable.");
		bootLoading.remove();

		const root = document.createElement("div");
		root.className = "retailedge-professional-purchasing-root";
		page.body.append(root);
		wrapper._retailedgeProfessionalPurchasingApp = await window.mountRetailEdgeProfessionalPurchasing(root);
		installPurchaseOrderOwnership(wrapper, root);
		installGuidedPurchaseOrderTrigger(wrapper, root);
		installAdvancedReceiptHandoff(wrapper);

		const overlayRoot = document.createElement("div");
		overlayRoot.className = "retailedge-professional-purchase-order-overlay-root";
		page.body.append(overlayRoot);
		wrapper._retailedgeProfessionalPurchaseOrderApp = await window.mountRetailEdgeProfessionalPurchaseOrder(overlayRoot);

		const receiptPreviewRoot = document.createElement("div");
		receiptPreviewRoot.className = "retailedge-professional-purchase-receipt-preview-overlay-root";
		page.body.append(receiptPreviewRoot);
		wrapper._retailedgeProfessionalPurchaseReceiptPreviewApp = await window.mountRetailEdgeProfessionalPurchaseReceiptPreview(receiptPreviewRoot);

		const receiptHistoryRoot = document.createElement("div");
		receiptHistoryRoot.className = "retailedge-professional-purchase-receipt-history-overlay-root";
		page.body.append(receiptHistoryRoot);
		wrapper._retailedgeProfessionalPurchaseReceiptHistoryApp = await window.mountRetailEdgeProfessionalPurchaseReceiptHistory(receiptHistoryRoot);
	} catch (error) {
		bootLoading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	installRestrictedOperationalGuard();
	window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
};
