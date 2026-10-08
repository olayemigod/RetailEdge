const EDGEUI_ASSET = "edgeui.bundle.js";
const STATEMENT_ASSET = "bank_statement_imports.bundle.js";
const PAGE_ROUTE = "bank-statement-imports";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let done = false;
		const finish = () => { if (!done) { done = true; resolve(); } };
		const fail = (error) => { if (!done) { done = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); } };
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

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const loading = document.createElement("div");
	loading.className = "edge-boot-loading p-6 text-center text-muted";
	loading.textContent = __("Loading Bank Statement Imports...");
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Bank Statement Imports"), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("This page could not start. Refresh the page or contact your administrator.");
		await requireAsync(STATEMENT_ASSET);
		if (typeof window.mountRetailEdgeBankStatementImports !== "function") {
			throw new Error("Bank Statement Imports bundle is unavailable.");
		}
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-bank-statement-imports-root";
		page.body.append(root);
		wrapper.__retailedgeStatementImportApp = await window.mountRetailEdgeBankStatementImports(root);
	} catch (error) {
		loading.remove();
		const block = document.createElement("div");
		block.className = "alert alert-danger p-6";
		block.textContent = window.retailedge?.userErrorMessage?.(error, __("Bank Statement Imports failed to load.")) || __("Bank Statement Imports failed to load.");
		wrapper.appendChild(block);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	window.dispatchEvent(new CustomEvent("retailedge-bank-statement-imports-page-show"));
};
