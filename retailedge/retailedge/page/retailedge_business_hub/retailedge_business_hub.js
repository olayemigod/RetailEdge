(function bootRetailEdgeBusinessHubPage() {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const ROUTE_BRIDGE_ASSET = "/assets/retailedge/js/retailedge_business_hub_route_bridge.js";

	function bootCurrentWrapper() {
		if (typeof window.retailedgeRegisterBusinessHubPage !== "function") {
			console.error(
				"[RetailEdge Business Hub] Desk controller is unavailable. Rebuild RetailEdge assets and clear the site cache."
			);
			return false;
		}

		window.retailedgeRegisterBusinessHubPage();
		const wrapper = window.frappe?.pages?.[PAGE_NAME]?.wrapper;
		if (!wrapper || typeof window.retailedgeBootBusinessHubPage !== "function") {
			return false;
		}

		window.retailedgeBootProductMenu?.();
		window.retailedgeBootBusinessHubPage(wrapper);
		return true;
	}

	function loadRouteBridge() {
		if (window.retailedgeBusinessHubRouteBridge) {
			window.retailedgeBusinessHubRouteBridge.boot();
			return;
		}

		try {
			const pending = frappe.require(ROUTE_BRIDGE_ASSET, () => {
				window.retailedgeBusinessHubRouteBridge?.boot();
			});
			if (pending && typeof pending.then === "function") {
				pending.then(() => window.retailedgeBusinessHubRouteBridge?.boot());
			}
		} catch (error) {
			console.error("[RetailEdge Business Hub] route bridge failed to load", error);
		}
	}

	bootCurrentWrapper();
	loadRouteBridge();
})();
