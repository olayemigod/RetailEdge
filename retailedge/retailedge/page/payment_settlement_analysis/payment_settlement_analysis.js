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


function refreshPendingBusinessHubHandoff(wrapper) {
	if (!wrapper._retailedgePageHasShown) {
		wrapper._retailedgePageHasShown = true;
		return;
	}
	const routeOptions = frappe.route_options || {};
	const handoff = window.__retailedgeBusinessHubRouteHandoff || {};
	const routeOptionMatches = Boolean(
		routeOptions.retailedge_business_hub_handoff
		&& String(routeOptions.retailedge_business_hub_target || "") === PAGE_ROUTE
	);
	const handoffMatches = Boolean(
		handoff
		&& String(handoff.target || "") === PAGE_ROUTE
		&& Date.now() - Number(handoff.createdAt || 0) <= 60_000
	);
	if (!routeOptionMatches && !handoffMatches) return;
	if (wrapper._retailedgeBusinessHubHandoffRefreshPromise) {
		return wrapper._retailedgeBusinessHubHandoffRefreshPromise;
	}
	const component = wrapper._retailedgeVueApp?._instance?.proxy;
	if (!component || typeof component.fetchMetadata !== "function") return;
	const refreshPromise = Promise.resolve(component.fetchMetadata())
		.catch((error) => {
			console.error(`[RetailEdge ${PAGE_TITLE}] Business Hub handoff refresh failed`, error);
		})
		.finally(() => {
			if (wrapper._retailedgeBusinessHubHandoffRefreshPromise === refreshPromise) {
				wrapper._retailedgeBusinessHubHandoffRefreshPromise = null;
			}
		});
	wrapper._retailedgeBusinessHubHandoffRefreshPromise = refreshPromise;
	return refreshPromise;
}

function bindBusinessHubHandoffRouteRefresh(wrapper) {
	if (wrapper._retailedgeBusinessHubHandoffRouteRefresh) return;
	const refresh = () => {
		const route = frappe.get_route?.();
		if (!Array.isArray(route) || String(route[0] || "") !== PAGE_ROUTE) return;
		refreshPendingBusinessHubHandoff(wrapper);
	};
	wrapper._retailedgeBusinessHubHandoffRouteRefresh = refresh;
	document.addEventListener("page-change", refresh);
	frappe.router?.on?.("change", refresh);
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
		wrapper._retailedgeVueApp = window.mountPaymentSettlementAnalysis(root);
		wrapper._retailedgePageHasShown = true;
		bindBusinessHubHandoffRouteRefresh(wrapper);
	} catch (error) {
		const failure = document.createElement("div");
		failure.className = "alert alert-danger p-6 text-center";
		failure.textContent = error?.message || __("Payment & Settlement Analysis could not be loaded.");
		page.body.append(failure);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	refreshPendingBusinessHubHandoff(wrapper);
};
