(function () {
	if (typeof window === "undefined") return;

	const PERSISTENT_TRANSACTION_PAGES = new Set([
		"make-sale",
		"record-purchase",
		"transfer-stock",
		"stock-adjustment",
	]);
	const MODULE_PREFIX_RE = /^\/(?:app|desk)\/retailedge\/([^/?#]+)\/?$/i;

	function normalisePage(page) {
		const value = String(page || "").trim().toLowerCase();
		return PERSISTENT_TRANSACTION_PAGES.has(value) ? value : "";
	}

	function barePagePath(page) {
		const target = normalisePage(page);
		return target ? `/app/${target}` : "";
	}

	function correctedPersistentPagePath(pathname = window.location?.pathname || "") {
		const match = MODULE_PREFIX_RE.exec(String(pathname || ""));
		if (!match) return "";
		return barePagePath(match[1]);
	}

	function correctModulePrefixedPersistentPage() {
		const target = correctedPersistentPagePath();
		if (!target) return false;
		const suffix = `${window.location?.search || ""}${window.location?.hash || ""}`;
		window.location.replace(`${target}${suffix}`);
		return true;
	}

	window.retailedge = window.retailedge || {};
	window.retailedge.openPersistentTransactionPage = function openPersistentTransactionPage(page) {
		const target = barePagePath(page);
		if (!target) return false;
		window.location.assign(target);
		return true;
	};
	window.retailedge.correctPersistentTransactionPageRoute = correctModulePrefixedPersistentPage;

	if (!correctModulePrefixedPersistentPage()) {
		document.addEventListener("page-change", correctModulePrefixedPersistentPage);
		window.frappe?.router?.on?.("change", correctModulePrefixedPersistentPage);
	}
})();
