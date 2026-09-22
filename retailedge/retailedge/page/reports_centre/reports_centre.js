const EDGEUI_ASSET = "edgeui.bundle.js";
const REPORTS_CENTRE_ASSET = "reports_centre.bundle.js";
const PAGE_ROUTE = "reports-centre";
const PAGE_TITLE = "Reports Centre";

function requireAsset(assetName) {
	return new Promise((resolve, reject) => {
		try {
			const pending = frappe.require(assetName, resolve);
			if (pending && typeof pending.then === "function") pending.then(resolve).catch(reject);
		} catch (error) {
			reject(error);
		}
	});
}

function hideNativeSidebar(wrapper) {
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
	hideNativeSidebar(wrapper);
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
	wrapper.page = page;
	try {
		await requireAsset(EDGEUI_ASSET);
		await requireAsset(REPORTS_CENTRE_ASSET);
		if (typeof window.mountReportsCentre !== "function") throw new Error("Reports Centre bundle is unavailable.");
		const root = document.createElement("div");
		root.className = "retailedge-reports-centre-root";
		page.body.append(root);
		window.mountReportsCentre(root);
	} catch (error) {
		const failure = document.createElement("div");
		failure.className = "alert alert-danger p-6 text-center";
		failure.textContent = error?.message || __("Reports Centre could not be loaded.");
		page.body.append(failure);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativeSidebar(wrapper);
};
