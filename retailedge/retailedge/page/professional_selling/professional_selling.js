const EDGEUI_ASSET = "edgeui.bundle.js";
const RESTRICTED_GUARD_ASSET = "retailedge_edgesuite_only_operational_guard.bundle.js";
const SELLING_ASSET = "professional_selling.bundle.js";
const PAGE_ROUTE = "professional-selling";
const PAGE_TITLE = "Professional Selling";

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
		rootSelector: ".retailedge-professional-selling-root",
		nativeDoctypes: ["Quotation", "Sales Order", "Delivery Note", "Sales Invoice"],
		nativePathSlugs: ["quotation", "sales-order", "delivery-note", "sales-invoice"],
		hiddenButtonLabels: ["View Records", "Open Full Form"],
		neutralizeSelectors: [".recent-row"],
	});
}

function renderLoadError(wrapper, error) {
	const node = document.createElement("div");
	node.className = "professional-selling-load-error alert alert-danger p-6 text-center";
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
		await requireAsync(SELLING_ASSET);
		if (typeof window.mountRetailEdgeProfessionalSelling !== "function") throw new Error("Professional Selling bundle is unavailable.");
		bootLoading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-professional-selling-root";
		page.body.append(root);
		wrapper._retailedgeProfessionalSellingApp = await window.mountRetailEdgeProfessionalSelling(root);
	} catch (error) {
		bootLoading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	installRestrictedOperationalGuard();
	window.dispatchEvent(new CustomEvent("retailedge-professional-selling-page-show"));
};
