const EDGEUI_ASSET = "edgeui.bundle.js";
const PROJECT_ASSET = "project_operations.bundle.js";
const PAGE_ROUTE = "project-operations";
const PAGE_TITLE = "Project Operations";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => { if (completed) return; completed = true; resolve(); };
		const fail = (error) => { if (completed) return; completed = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); };
		try { const pending = frappe.require(assetName, finish); if (pending && typeof pending.then === "function") pending.then(finish).catch(fail); } catch (error) { fail(error); }
	});
}

function hideNativePageSidebar(wrapper) {
	const pageContainer = wrapper.closest?.(".page-container") || wrapper;
	const sideSection = pageContainer.querySelector?.(".layout-side-section");
	const mainWrapper = pageContainer.querySelector?.(".layout-main-section-wrapper");
	if (sideSection) { sideSection.hidden = true; sideSection.setAttribute("aria-hidden", "true"); }
	if (mainWrapper) { mainWrapper.style.width = "100%"; mainWrapper.style.maxWidth = "100%"; mainWrapper.classList.add("retailedge-edgeui-main"); }
}

function renderLoadError(wrapper, error) {
	const errorDiv = document.createElement("div");
	errorDiv.className = "retailedge-project-operations-load-error alert alert-danger p-6 text-center";
	const title = document.createElement("strong"); title.textContent = __(`${PAGE_TITLE} failed to load`);
	const detail = document.createElement("div"); detail.textContent = error?.message || __("Unknown page load error");
	errorDiv.append(title, detail); wrapper.appendChild(errorDiv);
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
		await requireAsync(PROJECT_ASSET);
		if (typeof window.mountProjectOperationsPage !== "function") throw new Error("Project Operations bundle is unavailable.");
		bootLoading.remove();
		const root = document.createElement("div"); root.className = "retailedge-project-operations-root";
		page.body.append(root);
		await window.mountProjectOperationsPage(root);
	} catch (error) {
		bootLoading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) { hideNativePageSidebar(wrapper); };
