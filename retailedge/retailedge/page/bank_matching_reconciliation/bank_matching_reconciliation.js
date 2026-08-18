(function bootRetailEdgeBankingPage() {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const ASSET = "/assets/retailedge/js/bank_matching_reconciliation.js";

	function boot(wrapper) {
		if (typeof window.retailedgeBootBankingWorkspace === "function") {
			window.retailedgeBootBankingWorkspace(wrapper);
			return;
		}
		frappe.require(ASSET, () => {
			if (typeof window.retailedgeBootBankingWorkspace !== "function") {
				frappe.throw(__("RetailEdge Banking workspace asset is unavailable. Rebuild assets and clear cache."));
			}
			window.retailedgeBootBankingWorkspace(wrapper);
		});
	}

	frappe.pages[PAGE_NAME].on_page_load = boot;
})();
