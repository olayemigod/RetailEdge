const EDGEUI_ASSET = "edgesuite_ui.bundle.js";
const CASH_DEPOSIT_REGISTER_ASSET = "cash_deposit_register.bundle.js";
const PAGE_ROUTE = "cash-deposit-register";
const PAGE_TITLE = "Cash Deposit Register";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => { if (completed) return; completed = true; resolve(); };
		const fail = (error) => { if (completed) return; completed = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); };
		try {
			const pending = frappe.require(assetName, finish);
			if (pending && typeof pending.then === "function") pending.then(finish).catch(fail);
		} catch (error) {
			fail(error);
		}
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

function renderLoadError(wrapper, error) {
	const errorDiv = document.createElement("div");
	errorDiv.className = "retailedge-cash-deposit-register-load-error alert alert-danger p-6 text-center";
	const title = document.createElement("strong");
	title.textContent = __(`${PAGE_TITLE} failed to load`);
	const detail = document.createElement("div");
	detail.textContent = window.retailedge?.userErrorMessage?.(error, __("Unknown page load error")) || __("Unknown page load error");
	errorDiv.append(title, detail);
	wrapper.appendChild(errorDiv);
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
		if (!window.EdgeSuiteUI?.components) throw new Error("This page could not start. Refresh the page or contact your administrator.");
		await requireAsync(CASH_DEPOSIT_REGISTER_ASSET);
		if (typeof window.mountCashDepositRegisterPage !== "function") throw new Error("Cash Deposit Register bundle is unavailable.");
		bootLoading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-cash-deposit-register-page-root";
		page.body.append(root);
		wrapper._retailedgeCashDepositRegisterApp = await window.mountCashDepositRegisterPage(root);
	} catch (error) {
		bootLoading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	window.dispatchEvent(new CustomEvent("retailedge-cash-deposit-register-page-show"));
};
