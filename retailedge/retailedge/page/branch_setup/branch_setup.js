const EDGEUI_ASSET = "edgeui.bundle.js";
const PAGE_ASSET = "branch_setup.bundle.js";
const PAGE_ROUTE = "branch-setup";
const PAGE_TITLE = "Branch Setup";

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

function renderLoadError(wrapper, error) {
	const errorDiv = document.createElement("div");
	errorDiv.className = "alert alert-danger p-6 text-center";
	errorDiv.textContent = error?.message || __(`${PAGE_TITLE} failed to load`);
	wrapper.appendChild(errorDiv);
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const loading = document.createElement("div");
	loading.className = "edge-boot-loading p-6 text-center text-muted";
	loading.textContent = __(`Loading ${PAGE_TITLE}...`);
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("EdgeSuite UI runtime is unavailable.");
		await requireAsync(PAGE_ASSET);
		if (typeof window.mountRetailEdgeBranchSetup !== "function") throw new Error("Branch Setup bundle is unavailable.");
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-branch-setup-root";
		page.body.append(root);
		wrapper._retailedgeBranchSetupApp = await window.mountRetailEdgeBranchSetup(root);
	} catch (error) {
		loading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	window.dispatchEvent(new CustomEvent("retailedge-branch-setup-page-show"));
};
