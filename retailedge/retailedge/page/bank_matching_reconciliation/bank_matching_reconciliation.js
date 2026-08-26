(function bootRetailEdgeBankingPage() {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const OUTCOME_ASSET = "/assets/retailedge/js/bank_candidate_outcome_notifications.js";
	const REVIEW_CATEGORY_ASSET = "/assets/retailedge/js/bank_review_category_adapter.js";
	const FUZZY_DISCOVERY_ASSET = "/assets/retailedge/js/bank_matching_fuzzy_discovery_adapter.js";
	const DENSE_WORKSPACE_CSS = "/assets/retailedge/css/bank_matching_dense_workspace.css";
	const WORKSPACE_ASSET = "/assets/retailedge/js/bank_matching_edgesuite_workspace.js";

	function startWorkspace(wrapper) {
		if (typeof window.retailedgeBootBankingWorkspace !== "function") {
			frappe.throw(__("RetailEdge Banking EdgeSuite workspace asset is unavailable. Rebuild assets and clear cache."));
		}
		window.retailedgeBootBankingWorkspace(wrapper);
	}

	function boot(wrapper) {
		Promise.resolve(frappe.require(OUTCOME_ASSET))
			.then(() => Promise.resolve(frappe.require(REVIEW_CATEGORY_ASSET)))
			.then(() => Promise.resolve(frappe.require(FUZZY_DISCOVERY_ASSET)))
			.then(() => Promise.resolve(frappe.require(DENSE_WORKSPACE_CSS)))
			.then(() => Promise.resolve(frappe.require(WORKSPACE_ASSET)))
			.then(() => startWorkspace(wrapper))
			.catch((error) => {
				console.error("RetailEdge Banking EdgeSuite workspace asset failed to load", error);
				frappe.throw(__("RetailEdge Banking EdgeSuite workspace asset failed to load."));
			});
	}

	frappe.pages[PAGE_NAME].on_page_load = boot;
})();
