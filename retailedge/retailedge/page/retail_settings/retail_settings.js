const EDGEUI_ASSET = "edgeui.bundle.js";
const SETTINGS_ASSET = "retail_settings.bundle.js";
const PAGE_ROUTE = "retail-settings";

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
	if (sideSection) { sideSection.hidden = true; sideSection.setAttribute("aria-hidden", "true"); }
	if (mainWrapper) { mainWrapper.style.width = "100%"; mainWrapper.style.maxWidth = "100%"; mainWrapper.classList.add("retailedge-edgeui-main"); }
}

function safeMessage(error) {
	return window.retailedge?.userErrorMessage?.(error, __("Settings failed to load.")) || __("Settings failed to load.");
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const loading = document.createElement("div");
	loading.className = "edge-boot-loading p-6 text-center text-muted";
	loading.textContent = __("Loading Settings...");
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Settings"), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("Required interface components are unavailable.");
		await requireAsync(SETTINGS_ASSET);
		if (typeof window.mountRetailSettings !== "function") throw new Error("Settings interface is unavailable.");
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-settings-root";
		page.body.append(root);
		await window.mountRetailSettings(root);
	} catch (error) {
		loading.remove();
		const block = document.createElement("div");
		block.className = "alert alert-danger p-6";
		block.textContent = safeMessage(error);
		wrapper.appendChild(block);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	window.dispatchEvent(new CustomEvent("retailedge-settings-page-show"));
};
