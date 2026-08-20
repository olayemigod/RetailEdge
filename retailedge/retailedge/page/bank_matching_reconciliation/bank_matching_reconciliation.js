(function bootRetailEdgeBankingPage() {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const ASSET = "/assets/retailedge/js/bank_matching_reconciliation.js";
	const REVIEW_ASSET = "/assets/retailedge/js/bank_match_review_ui.js";

	function startWorkspace(wrapper) {
		if (typeof window.retailedgeBootBankingWorkspace !== "function") {
			frappe.throw(__("RetailEdge Banking workspace asset is unavailable. Rebuild assets and clear cache."));
		}
		window.retailedgeBootBankingWorkspace(wrapper);
	}

	function boot(wrapper) {
		Promise.resolve(frappe.require(ASSET))
			.then(() => Promise.resolve(frappe.require(REVIEW_ASSET)))
			.then(() => startWorkspace(wrapper))
			.catch((error) => {
				console.error("RetailEdge Banking workspace asset failed to load", error);
				frappe.throw(__("RetailEdge Banking workspace asset failed to load."));
			});
	}

	frappe.pages[PAGE_NAME].on_page_load = boot;
})();
