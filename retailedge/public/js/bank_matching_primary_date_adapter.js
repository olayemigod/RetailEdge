(function installRetailEdgeBankingPrimaryDateAdapter(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	let scheduled = false;

	if (global.retailedgeBankingPrimaryDateAdapterInstalled) return;

	function clean(value) {
		return String(value ?? "").trim().replace(/\s+/g, " ");
	}

	function t(text) {
		return typeof global.__ === "function" ? global.__(text) : text;
	}

	function isBankingPage() {
		const route = global.frappe?.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function edgeInputField(filterBar, labelText) {
		const wanted = clean(t(labelText));
		return Array.from(filterBar?.querySelectorAll(".edge-input") || []).find((field) => {
			const label = field.querySelector(".edge-input__label");
			return clean(label?.textContent) === wanted;
		}) || null;
	}

	function internalizeLegacyDateField(field) {
		if (!field) return;
		field.hidden = true;
		field.setAttribute("aria-hidden", "true");
		field.classList.add("retailedge-bank-internal-date-filter");
		const input = field.querySelector("input");
		if (input) input.tabIndex = -1;
	}

	function promoteSmartDate() {
		scheduled = false;
		if (!isBankingPage()) return;

		const root = document.querySelector(".retailedge-bank-layout");
		const filterBar = root?.querySelector(".edge-filter-bar");
		const fieldsHost = filterBar?.querySelector(".edge-filter-bar__fields");
		const smartDate = filterBar?.querySelector(".retailedge-bank-smart-date");
		const fromDate = edgeInputField(filterBar, "From Date");
		const toDate = edgeInputField(filterBar, "To Date");
		if (!filterBar || !fieldsHost || !smartDate || !fromDate || !toDate) return;

		// The exact From/To controls remain mounted only as internal query state.
		// The user sees one EdgeSuite smart-date selector, matching the Banking/Mint
		// interaction pattern without creating a second date authority.
		internalizeLegacyDateField(fromDate);
		internalizeLegacyDateField(toDate);

		if (smartDate.parentElement !== fieldsHost || smartDate.nextElementSibling !== fromDate) {
			fieldsHost.insertBefore(smartDate, fromDate);
		}
		smartDate.classList.add("retailedge-bank-smart-date--primary");

		const label = smartDate.querySelector(".edge-smart-date__label");
		if (label) label.textContent = t("Date");
		const input = smartDate.querySelector(".edge-smart-date__input");
		if (input) {
			input.placeholder = t("e.g. Last 3 weeks, This Month, Last 90 days");
			input.setAttribute("aria-label", t("Date period"));
		}
	}

	function schedule() {
		if (scheduled) return;
		scheduled = true;
		setTimeout(promoteSmartDate, 0);
	}

	const observer = new MutationObserver(schedule);
	observer.observe(document.documentElement, { childList: true, subtree: true });
	global.retailedgeBankingPrimaryDateAdapterInstalled = true;
	schedule();
})(window);
