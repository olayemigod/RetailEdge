(function bootRetailEdgeBankingPage() {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const OUTCOME_ASSET = "/assets/retailedge/js/bank_candidate_outcome_notifications.js";
	const REVIEW_CATEGORY_ASSET = "/assets/retailedge/js/bank_review_category_adapter.js";
	const FUZZY_DISCOVERY_ASSET = "/assets/retailedge/js/bank_matching_fuzzy_discovery_adapter.js";
	const BRANCH_SEARCH_ASSET = "/assets/retailedge/js/bank_matching_branch_search_adapter.js";
	const DENSE_WORKSPACE_CSS = "/assets/retailedge/css/bank_matching_dense_workspace.css";
	const COMPLETION_CSS = "/assets/retailedge/css/bank_matching_edgesuite_completion.css";
	const STYLE_VERSION = "20260826-5";
	const WORKSPACE_ASSET = "/assets/retailedge/js/bank_matching_edgesuite_workspace.js";
	const COMPLETION_ASSET = "/assets/retailedge/js/bank_matching_edgesuite_completion_adapter.js";

	function loadVersionedStylesheet(href, marker) {
		return new Promise((resolve, reject) => {
			const selector = `link[data-retailedge-banking-style="${marker}"]`;
			document.querySelectorAll(selector).forEach((node) => node.remove());

			// Remove an older page-scoped copy that may have been inserted by
			// frappe.require before this loader became version-aware.
			document.querySelectorAll('link[rel="stylesheet"]').forEach((node) => {
				const currentHref = node.getAttribute("href") || "";
				if (currentHref.split("?")[0] === href) {
					node.remove();
				}
			});

			const link = document.createElement("link");
			link.rel = "stylesheet";
			link.href = `${href}?v=${STYLE_VERSION}`;
			link.dataset.retailedgeBankingStyle = marker;
			link.onload = () => resolve();
			link.onerror = () => reject(new Error(`Unable to load stylesheet: ${href}`));
			document.head.appendChild(link);
		});
	}

	function loadBankingStyles() {
		return Promise.all([
			loadVersionedStylesheet(DENSE_WORKSPACE_CSS, "dense-workspace"),
			loadVersionedStylesheet(COMPLETION_CSS, "completion"),
		]);
	}

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
			.then(() => Promise.resolve(frappe.require(BRANCH_SEARCH_ASSET)))
			.then(() => loadBankingStyles())
			.then(() => Promise.resolve(frappe.require(WORKSPACE_ASSET)))
			.then(() => Promise.resolve(frappe.require(COMPLETION_ASSET)))
			.then(() => startWorkspace(wrapper))
			.catch((error) => {
				console.error("RetailEdge Banking EdgeSuite workspace asset failed to load", error);
				frappe.throw(__("RetailEdge Banking EdgeSuite workspace asset failed to load."));
			});
	}

	frappe.pages[PAGE_NAME].on_page_load = boot;
})();
