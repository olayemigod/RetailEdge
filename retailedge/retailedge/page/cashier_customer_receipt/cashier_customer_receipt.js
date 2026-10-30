const EDGEUI_ASSET = "edgeui.bundle.js";
const RECEIPT_ASSET = "cashier_customer_receipt.bundle.js";
const PAGE_ROUTE = "cashier-customer-receipt";

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

function refreshMountedReceipt(wrapper) {
	const component = wrapper?._retailedgeCashierReceiptApp?._instance?.proxy;
	if (component && typeof component.load === "function") return component.load();
	return null;
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const loading = document.createElement("div");
	loading.className = "edge-boot-loading p-6 text-center text-muted";
	loading.textContent = __("Loading Receive Payment...");
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __("Receive Payment"), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		await requireAsync(RECEIPT_ASSET);
		if (typeof window.mountCashierCustomerReceipt !== "function") throw new Error("Receive Payment bundle is unavailable.");
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-cashier-customer-receipt-root";
		page.body.append(root);
		wrapper._retailedgeCashierReceiptApp = window.mountCashierCustomerReceipt(root);
	} catch (error) {
		loading.textContent = error?.message || __("Receive Payment failed to load.");
		loading.classList.add("text-danger");
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	refreshMountedReceipt(wrapper);
};
