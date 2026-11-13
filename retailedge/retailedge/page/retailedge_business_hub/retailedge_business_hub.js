(function bootRetailEdgeBusinessHubPage() {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const CASHIER_HOME = "cashier-my-work";
	const ROUTE_BRIDGE_ASSET = "/assets/retailedge/js/retailedge_business_hub_route_bridge.js";
	const CASHIER_ROLES = new Set(["RetailEdgeCashier", "RetailEdge Cashier"]);
	const MANAGEMENT_ROLES = new Set([
		"System Manager",
		"RetailEdgeManager",
		"RetailEdge Manager",
		"RetailEdgeBranchManager",
		"RetailEdge Branch Manager",
		"RetailEdgeAuditor",
		"RetailEdge Auditor",
	]);

	function shouldUseCashierHome() {
		const roles = new Set(window.frappe?.user_roles || []);
		const isCashier = [...CASHIER_ROLES].some((role) => roles.has(role));
		const isManagement = [...MANAGEMENT_ROLES].some((role) => roles.has(role));
		return isCashier && !isManagement;
	}

	function bootCurrentWrapper() {
		if (shouldUseCashierHome()) {
			window.frappe?.set_route?.(CASHIER_HOME);
			return true;
		}

		if (typeof window.retailedgeRegisterBusinessHubPage !== "function") {
			console.error(
				"[RetailEdge Business Hub] Desk controller is unavailable. Rebuild RetailEdge assets and clear the site cache."
			);
			return false;
		}

		window.retailedgeRegisterBusinessHubPage();
		const wrapper = window.frappe?.pages?.[PAGE_NAME];
		if (!wrapper || typeof window.retailedgeBootBusinessHubPage !== "function") {
			return false;
		}

		window.retailedgeBootProductMenu?.();
		window.retailedgeBootBusinessHubPage(wrapper);
		return true;
	}

	function loadRouteBridge() {
		if (shouldUseCashierHome()) return;
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
