(function installRetailEdgeBankingBranchSearch(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const DESK_LINK_SEARCH = "frappe.desk.search.search_link";
	const BANKING_BRANCH_SEARCH = "retailedge.banking_link_search.search_banking_branches";

	if (global.retailedgeBankingBranchSearchInstalled) return;
	if (!global.frappe?.call) return;

	const originalCall = global.frappe.call.bind(global.frappe);

	function clean(value) {
		return String(value ?? "").trim();
	}

	function isBankingPage() {
		const route = global.frappe.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function isBranchLinkSearch(request) {
		return request?.method === DESK_LINK_SEARCH
			&& request?.args?.doctype === "Branch"
			&& clean(request?.args?.filters?.company);
	}

	global.frappe.call = function retailedgeBankingBranchAwareCall(...args) {
		const request = args[0];
		if (!isBankingPage() || !isBranchLinkSearch(request)) {
			return originalCall(...args);
		}

		const replacement = {
			...request,
			method: BANKING_BRANCH_SEARCH,
			args: {
				txt: clean(request.args.txt),
				company: clean(request.args.filters.company),
				limit: request.args.page_length || 20,
			},
		};
		return originalCall(replacement, ...args.slice(1));
	};

	global.retailedgeBankingBranchSearchInstalled = true;
})(window);
