(function installRetailEdgeBankMatchingBankAccountCascade(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const LINK_SEARCH_METHOD = "frappe.desk.search.search_link";
	const WORKSPACE_METHOD = "retailedge.banking_workspace.get_banking_workspace_rows";
	const BANK_ACCOUNT_SEARCH_METHOD = "retailedge.bank_matching_bank_account_cascade.search_bank_matching_bank_accounts";
	const VALIDATE_FILTER_METHOD = "retailedge.bank_matching_bank_account_cascade.validate_bank_matching_bank_account_filter";
	const validatedContexts = new Set();
	let lastWorkspaceBranch = "";

	if (global.retailedgeBankMatchingBankAccountCascadeInstalled) return;
	if (!global.frappe?.call) return;

	const originalCall = global.frappe.call.bind(global.frappe);

	function clean(value) {
		return String(value ?? "").trim();
	}

	function isBankingPage() {
		const route = global.frappe?.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function requestMethod(request) {
		if (typeof request === "string") return request;
		return request?.method || "";
	}

	function linkFieldByLabel(label) {
		const wanted = clean(typeof global.__ === "function" ? global.__(label) : label);
		return Array.from(document.querySelectorAll(".retailedge-bank-layout .edge-filter-bar .edge-link-field"))
			.find((field) => clean(field.querySelector(".edge-link-field__label")?.textContent) === wanted) || null;
	}

	function filterValue(label) {
		return clean(linkFieldByLabel(label)?.querySelector(".edge-link-field__input")?.value);
	}

	function isMainBankAccountSearch() {
		const active = document.activeElement;
		const field = active?.closest?.(".retailedge-bank-layout .edge-filter-bar .edge-link-field");
		if (!field) return false;
		const label = clean(field.querySelector(".edge-link-field__label")?.textContent);
		const expected = clean(typeof global.__ === "function" ? global.__("Bank Account") : "Bank Account");
		return label === expected;
	}

	function clearMainBankAccountSelection() {
		const field = linkFieldByLabel("Bank Account");
		if (!field) return;
		const clearButton = field.querySelector(".edge-link-field__clear");
		if (clearButton) {
			clearButton.click();
			return;
		}
		const input = field.querySelector(".edge-link-field__input");
		if (!input || !clean(input.value)) return;
		const setter = Object.getOwnPropertyDescriptor(global.HTMLInputElement.prototype, "value")?.set;
		if (setter) setter.call(input, "");
		else input.value = "";
		input.dispatchEvent(new Event("input", { bubbles: true }));
	}

	function bankAccountContextKey(args) {
		return [clean(args?.company), clean(args?.branch), clean(args?.bank_account)].join("::");
	}

	async function validateWorkspaceBankAccount(args) {
		if (!clean(args?.bank_account)) return;
		const key = bankAccountContextKey(args);
		if (validatedContexts.has(key)) return;
		await originalCall({
			method: VALIDATE_FILTER_METHOD,
			args: {
				company: clean(args?.company),
				branch: clean(args?.branch),
				bank_account: clean(args?.bank_account),
			},
		});
		validatedContexts.add(key);
	}

	global.frappe.call = function retailedgeBankAccountCascadeCall(...args) {
		const request = args[0];
		const method = requestMethod(request);

		if (
			isBankingPage()
			&& method === LINK_SEARCH_METHOD
			&& request
			&& typeof request === "object"
			&& request.args?.doctype === "Bank Account"
			&& isMainBankAccountSearch()
		) {
			const company = clean(request.args?.filters?.company || filterValue("Company"));
			const branch = clean(filterValue("Branch") || lastWorkspaceBranch);
			return originalCall({
				...request,
				method: BANK_ACCOUNT_SEARCH_METHOD,
				args: {
					company,
					branch,
					txt: clean(request.args?.txt),
					limit: Number(request.args?.page_length || 20),
				},
			});
		}

		if (
			isBankingPage()
			&& method === WORKSPACE_METHOD
			&& request
			&& typeof request === "object"
		) {
			const requestArgs = { ...(request.args || {}) };
			const nextBranch = clean(requestArgs.branch);

			// Branch changes invalidate an existing Bank Account selection immediately.
			// Clear the EdgeLinkField (which emits update:modelValue) and also clear this
			// in-flight request so stale company-wide/other-branch context cannot leak.
			if (nextBranch !== lastWorkspaceBranch && clean(requestArgs.bank_account)) {
				requestArgs.bank_account = "";
				lastWorkspaceBranch = nextBranch;
				clearMainBankAccountSelection();
				return originalCall({ ...request, args: requestArgs });
			}
			lastWorkspaceBranch = nextBranch;

			if (!clean(requestArgs.bank_account)) {
				return originalCall({ ...request, args: requestArgs });
			}

			return validateWorkspaceBankAccount(requestArgs)
				.then(() => originalCall({ ...request, args: requestArgs }));
		}

		return originalCall(...args);
	};

	global.retailedgeBankMatchingBankAccountCascadeInstalled = true;
})(window);
