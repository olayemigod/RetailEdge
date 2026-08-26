(function installRetailEdgeBankingPageEnhancements(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const IMPORT_DOCTYPE = "Bank Statement Import";
	const DEFAULT_TOLERANCE_DAYS = 3;
	const ALLOWED_TOLERANCES = [0, 1, 3, 7];
	let scheduled = false;

	if (global.retailedgeBankingPageEnhancementsInstalled) return;

	function clean(value) {
		return String(value ?? "").trim().replace(/\s+/g, " ");
	}

	function t(text, args) {
		return typeof global.__ === "function" ? global.__(text, args) : text;
	}

	function isBankingPage() {
		const route = global.frappe?.get_route?.() || [];
		return route[0] === PAGE_NAME;
	}

	function pageRoot() {
		return document.querySelector(".retailedge-bank-layout");
	}

	function findButton(root, labels) {
		const wanted = new Set(labels.map((label) => clean(t(label))));
		return Array.from(root?.querySelectorAll("button") || []).find((button) => wanted.has(clean(button.textContent))) || null;
	}

	function removeFilterHeading(filterBar) {
		Array.from(filterBar?.querySelectorAll("*") || [])
			.filter((element) => element.children.length === 0 && clean(element.textContent) === clean(t("Filters")))
			.forEach((element) => element.remove());
	}

	function restyleReset(filterBar) {
		const reset = findButton(filterBar, ["Clear Filters", "Reset filters", "Reset Filters"]);
		if (!reset) return null;
		reset.textContent = t("Reset filters");
		reset.classList.add("retailedge-bank-reset-link");
		return reset;
	}

	function currentTolerance() {
		const value = Number(global.retailedgeBankingFuzzyDateToleranceDays ?? DEFAULT_TOLERANCE_DAYS);
		return ALLOWED_TOLERANCES.includes(value) ? value : DEFAULT_TOLERANCE_DAYS;
	}

	function refreshWorkspace(root) {
		const refresh = findButton(root, ["Refresh"]);
		refresh?.click();
	}

	function addSmartMatchControl(filterBar, root, resetButton) {
		if (filterBar.querySelector(".retailedge-bank-smart-match")) return;

		const wrapper = document.createElement("div");
		wrapper.className = "retailedge-bank-smart-match";
		wrapper.setAttribute("role", "group");
		wrapper.setAttribute("aria-label", t("Smart Match date tolerance"));

		const label = document.createElement("span");
		label.className = "retailedge-bank-smart-match__label";
		label.textContent = t("Smart Match");

		const select = document.createElement("select");
		select.className = "retailedge-bank-smart-match__select";
		select.setAttribute("aria-label", t("Smart Match date tolerance"));
		[
			[0, t("Same day")],
			[1, t("±1 day")],
			[3, t("±3 days")],
			[7, t("±7 days")],
		].forEach(([value, text]) => {
			const option = document.createElement("option");
			option.value = String(value);
			option.textContent = text;
			select.appendChild(option);
		});
		select.value = String(currentTolerance());
		select.addEventListener("change", () => {
			global.retailedgeBankingFuzzyDateToleranceDays = Number(select.value);
			refreshWorkspace(root);
		});

		const note = document.createElement("small");
		note.className = "retailedge-bank-smart-match__note";
		note.textContent = t("Date proximity is supplemental only; bank/accounting eligibility still controls.");

		wrapper.append(label, select, note);
		const host = resetButton?.parentElement || filterBar;
		if (resetButton && resetButton.parentElement === host) host.insertBefore(wrapper, resetButton);
		else host.appendChild(wrapper);
	}

	function fieldValueByLabel(filterBar, wantedLabel) {
		const wanted = clean(t(wantedLabel));
		const labelNodes = Array.from(filterBar?.querySelectorAll("label, [class*='label']") || [])
			.filter((element) => clean(element.textContent) === wanted);
		for (const label of labelNodes) {
			let node = label;
			for (let depth = 0; depth < 5 && node; depth += 1, node = node.parentElement) {
				const input = node.querySelector?.("input");
				const value = clean(input?.value);
				if (value) return value;
			}
		}
		return "";
	}

	function openNativeStatementImport(root) {
		const filterBar = root.querySelector(".edge-filter-bar");
		const company = fieldValueByLabel(filterBar, "Company");
		const bankAccount = fieldValueByLabel(filterBar, "Bank Account");
		if (!company || !bankAccount) {
			global.frappe?.msgprint?.({
				title: t("Upload Bank Statement"),
				message: t("Select a Company and Bank Account first. The native ERPNext importer will then open with that banking context."),
				indicator: "orange",
			});
			return;
		}
		if (typeof global.frappe?.new_doc !== "function") {
			global.frappe?.throw?.(t("ERPNext Bank Statement Import is unavailable on this site."));
			return;
		}
		global.frappe.new_doc(IMPORT_DOCTYPE, {
			company,
			bank_account: bankAccount,
			reference_doctype: "Bank Transaction",
			import_type: "Insert New Records",
		});
	}

	function addUploadStatementAction(root) {
		if (root.querySelector(".retailedge-bank-upload-statement")) return;
		const refresh = findButton(root, ["Refresh"]);
		if (!refresh?.parentElement) return;
		const button = document.createElement("button");
		button.type = "button";
		button.className = "edge-button edge-button--secondary retailedge-bank-upload-statement";
		button.textContent = t("Upload Statement");
		button.title = t("Use ERPNext Bank Statement Import with the standard Bank Transaction template and preview.");
		button.addEventListener("click", () => openNativeStatementImport(root));
		refresh.parentElement.insertBefore(button, refresh);
	}

	function enhancePage() {
		scheduled = false;
		if (!isBankingPage()) return;
		const root = pageRoot();
		if (!root) return;
		const filterBar = root.querySelector(".edge-filter-bar");
		if (filterBar) {
			removeFilterHeading(filterBar);
			const reset = restyleReset(filterBar);
			addSmartMatchControl(filterBar, root, reset);
		}
		addUploadStatementAction(root);
	}

	function scheduleEnhancement() {
		if (scheduled) return;
		scheduled = true;
		setTimeout(enhancePage, 0);
	}

	const observer = new MutationObserver(scheduleEnhancement);
	observer.observe(document.documentElement, { childList: true, subtree: true });
	global.retailedgeBankingPageEnhancementsInstalled = true;
	scheduleEnhancement();
})(window);
