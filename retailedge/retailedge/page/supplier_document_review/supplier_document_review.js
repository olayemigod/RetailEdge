const EDGEUI_ASSET = "edgeui.bundle.js";
const REVIEW_ASSET = "supplier_document_review.bundle.js";
const PAGE_ROUTE = "supplier-document-review";
const PAGE_TITLE = "Supplier Document Review";

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
	const errorDiv = document.createElement("div"); errorDiv.className = "edge-boot-error";
	const title = document.createElement("strong"); title.textContent = __(`${PAGE_TITLE} failed to load`);
	const detail = document.createElement("div"); detail.textContent = error?.message || __("Unknown page load error");
	errorDiv.append(title, detail); wrapper.appendChild(errorDiv);
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const bootLoading = document.createElement("div"); bootLoading.className = "edge-boot-loading"; bootLoading.textContent = __(`Loading ${PAGE_TITLE}...`); wrapper.appendChild(bootLoading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true }); wrapper.page = page; hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components || typeof window.EdgeSuiteUI?.createEdgeApp !== "function") throw new Error("EdgeSuite UI runtime is unavailable.");
		await requireAsync(REVIEW_ASSET);
		if (typeof window.mountSupplierDocumentReviewPage !== "function") throw new Error("Supplier Document Review EdgeSuite bundle is unavailable.");
		bootLoading.remove(); const root = document.createElement("div"); root.className = "retailedge-supplier-document-review-root"; page.body.append(root); await window.mountSupplierDocumentReviewPage(root);
	} catch (error) { bootLoading.remove(); renderLoadError(wrapper, error); }
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) { hideNativePageSidebar(wrapper); };
