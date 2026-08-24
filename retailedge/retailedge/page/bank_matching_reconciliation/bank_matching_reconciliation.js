(function bootRetailEdgeBankingPage() {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const OUTCOME_ASSET = "/assets/retailedge/js/bank_candidate_outcome_notifications.js";
	const ASSET = "/assets/retailedge/js/bank_matching_reconciliation.js";
	const REVIEW_ASSET = "/assets/retailedge/js/bank_match_review_ui.js";
	const CONFIRMATION_ASSET = "/assets/retailedge/js/bank_reconciliation_confirmation.js";

	function startWorkspace(wrapper) {
		if (typeof window.retailedgeBootBankingWorkspace !== "function") {
			frappe.throw(__("RetailEdge Banking workspace asset is unavailable. Rebuild assets and clear cache."));
		}
		window.retailedgeBootBankingWorkspace(wrapper);
		const page = wrapper.page;
		if (page?.add_inner_button) {
			page.add_inner_button(__("Banking Setup & Readiness"), () => frappe.set_route("banking-readiness"));
		}
	}

	function boot(wrapper) {
		Promise.resolve(frappe.require(OUTCOME_ASSET))
			.then(() => Promise.resolve(frappe.require(ASSET)))
			.then(() => Promise.resolve(frappe.require(REVIEW_ASSET)))
			.then(() => Promise.resolve(frappe.require(CONFIRMATION_ASSET)))
			.then(() => startWorkspace(wrapper))
			.catch((error) => {
				console.error("RetailEdge Banking workspace asset failed to load", error);
				frappe.throw(__("RetailEdge Banking workspace asset failed to load."));
			});
	}

	frappe.pages[PAGE_NAME].on_page_load = boot;
})();
