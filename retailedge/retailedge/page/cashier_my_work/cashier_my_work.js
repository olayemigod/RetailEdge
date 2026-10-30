const EDGEUI_ASSET = "edgeui.bundle.js";
const MY_WORK_ASSET = "cashier_my_work.bundle.js";
const PAGE_ROUTE = "cashier-my-work";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => { if (!completed) { completed = true; resolve(); } };
		const fail = (error) => { if (!completed) { completed = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); } };
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
	loading.textContent = __("Loading My Work...");
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("My Work"), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		await requireAsync(MY_WORK_ASSET);
		if (typeof window.mountCashierMyWork !== "function") throw new Error("RetailEdge My Work bundle is unavailable.");
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-cashier-my-work-root";
		page.body.append(root);
		window.mountCashierMyWork(root);
	} catch (error) {
		loading.textContent = error?.message || __("My Work failed to load.");
		loading.classList.add("text-danger");
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) { hideNativePageSidebar(wrapper); };
