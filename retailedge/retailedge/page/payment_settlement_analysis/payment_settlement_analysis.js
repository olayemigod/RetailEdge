const EDGEUI_ASSET = "edgeui.bundle.js";
const ANALYSIS_ASSET = "payment_settlement_analysis.bundle.js";
const PAGE_ROUTE = "payment-settlement-analysis";
const PAGE_TITLE = "Payment & Settlement Analysis";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => {
			if (completed) return;
			completed = true;
			resolve();
		};
		const fail = (error) => {
			if (completed) return;
			completed = true;
			reject(error instanceof Error ? error : new Error(String(error || assetName)));
		};
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
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
	wrapper.page = page;
	try {
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("EdgeSuite UI runtime is unavailable.");
		await requireAsync(ANALYSIS_ASSET);
		if (typeof window.mountPaymentSettlementAnalysis !== "function") {
			throw new Error("Payment & Settlement Analysis bundle is unavailable.");
		}
		const root = document.createElement("div");
		root.className = "retailedge-payment-settlement-analysis-root";
		page.body.append(root);
		window.mountPaymentSettlementAnalysis(root);
	} catch (error) {
		const failure = document.createElement("div");
		failure.className = "alert alert-danger p-6 text-center";
		failure.textContent = error?.message || __("Payment & Settlement Analysis could not be loaded.");
		page.body.append(failure);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
};
