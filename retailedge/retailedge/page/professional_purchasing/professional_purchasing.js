const EDGEUI_ASSET = "edgeui.bundle.js";
const RESTRICTED_GUARD_ASSET = "retailedge_edgesuite_only_operational_guard.bundle.js";
const PURCHASING_ASSET = "professional_purchasing.bundle.js";
const PURCHASE_ORDER_ASSET = "professional_purchase_order.bundle.js";
const PAGE_ROUTE = "professional-purchasing";
const PAGE_TITLE = "Professional Purchasing";
const OPEN_PURCHASE_ORDER_EVENT = "retailedge-open-professional-purchase-order";
const PURCHASE_ORDER_TRIGGER_LABEL = "New Purchase Order";
const ACCESS_MODE = "edgesuite_only";
const ADVANCED_PURCHASE_ORDER_LABEL = "Advanced: Open in ERPNext";

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
			"Purchase Receipts",
			"Material Requests",
			"Open",
			ADVANCED_PURCHASE_ORDER_LABEL,
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
			if (normaliseButtonLabel(button) !== "Open") continue;
			if (!nativeDeskEnabled()) {
				button.hidden = true;
				button.setAttribute("aria-hidden", "true");
				continue;
			}
			button.textContent = __(ADVANCED_PURCHASE_ORDER_LABEL);
			button.setAttribute("title", __("Open the full ERPNext Purchase Order form for advanced review."));
			button.setAttribute("data-retailedge-advanced-native", "Purchase Order");
		}
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
		});
	};
	const handler = (event) => {
		const button = event.target?.closest?.("button");
		if (!button || !root.contains(button) || !button.closest(".purchasing-table--orders")) return;
		if (button.classList.contains("retailedge-po-reference")) {
			event.preventDefault();
			event.stopPropagation();
			event.stopImmediatePropagation();
			return;
		}
		if (normaliseButtonLabel(button) === ADVANCED_PURCHASE_ORDER_LABEL && !nativeDeskEnabled()) {
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
		await Promise.all([requireAsync(PURCHASING_ASSET), requireAsync(PURCHASE_ORDER_ASSET)]);
		if (typeof window.mountRetailEdgeProfessionalPurchasing !== "function") throw new Error("Professional Purchasing bundle is unavailable.");
		if (typeof window.mountRetailEdgeProfessionalPurchaseOrder !== "function") throw new Error("Professional Purchase Order bundle is unavailable.");
		bootLoading.remove();

		const root = document.createElement("div");
		root.className = "retailedge-professional-purchasing-root";
		page.body.append(root);
		wrapper._retailedgeProfessionalPurchasingApp = await window.mountRetailEdgeProfessionalPurchasing(root);
		installPurchaseOrderOwnership(wrapper, root);
		installGuidedPurchaseOrderTrigger(wrapper, root);

		const overlayRoot = document.createElement("div");
		overlayRoot.className = "retailedge-professional-purchase-order-overlay-root";
		page.body.append(overlayRoot);
		wrapper._retailedgeProfessionalPurchaseOrderApp = await window.mountRetailEdgeProfessionalPurchaseOrder(overlayRoot);
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
