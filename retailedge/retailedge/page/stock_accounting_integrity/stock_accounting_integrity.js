const EDGEUI_ASSET = "edgeui.bundle.js";
const INTEGRITY_ASSET = "stock_accounting_integrity.bundle.js";
const PAGE_ROUTE = "stock-accounting-integrity";
const PAGE_TITLE = "Stock & Accounting Integrity";
const LOAD_TIMEOUT_MS = 15000;
const FRAPPE_REQUIRE_POLL_MS = 50;

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		let pollTimer = null;
		const deadlineTimer = window.setTimeout(
			() => fail(new Error(__("Timed out waiting for the Frappe asset loader while loading {0}", [assetName]))),
			LOAD_TIMEOUT_MS
		);
		const clearTimers = () => {
			window.clearTimeout(deadlineTimer);
			if (pollTimer) window.clearTimeout(pollTimer);
		};
		const finish = () => {
			if (completed) return;
			completed = true;
			clearTimers();
			resolve();
		};
		const fail = (error) => {
			if (completed) return;
			completed = true;
			clearTimers();
			reject(error instanceof Error ? error : new Error(String(error || assetName)));
		};
		const attemptRequire = () => {
			if (completed) return;
			if (!window.frappe || typeof window.frappe.require !== "function") {
				pollTimer = window.setTimeout(attemptRequire, FRAPPE_REQUIRE_POLL_MS);
				return;
			}
			try {
				const pending = window.frappe.require(assetName, finish);
				if (pending && typeof pending.then === "function") pending.then(finish).catch(fail);
			} catch (error) {
				fail(error);
			}
		};

		attemptRequire();
	});
}

function hideNativePageSidebar(wrapper) {
	const pageContainer = wrapper.closest?.(".page-container") || wrapper;
	const sideSection = pageContainer.querySelector?.(".layout-side-section");
	const mainWrapper = pageContainer.querySelector?.(".layout-main-section-wrapper");
	if (sideSection) {
		sideSection.hidden = true;
		sideSection.setAttribute("aria-hidden", "true");
	}
	if (mainWrapper) {
		mainWrapper.style.width = "100%";
		mainWrapper.style.maxWidth = "100%";
		mainWrapper.classList.add("retailedge-edgeui-main");
	}
}

function renderLoadError(wrapper, error) {
	const existing = wrapper.querySelector?.(".retailedge-stock-accounting-integrity-load-error");
	if (existing) existing.remove();
	const errorDiv = document.createElement("div");
	errorDiv.className = "retailedge-stock-accounting-integrity-load-error alert alert-danger p-6 text-center";
	const title = document.createElement("strong");
	title.textContent = __(`${PAGE_TITLE} failed to load`);
	const detail = document.createElement("div");
	detail.textContent = error?.message || __("Unknown page load error");
	errorDiv.append(title, detail);
	wrapper.appendChild(errorDiv);
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const bootLoading = document.createElement("div");
	bootLoading.className = "edge-boot-loading p-6 text-center text-muted";
	bootLoading.textContent = __(`Loading ${PAGE_TITLE}...`);
	wrapper.appendChild(bootLoading);

	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await requireAsync(EDGEUI_ASSET);
		if (!window.EdgeSuiteUI?.components) throw new Error("EdgeSuite UI runtime is unavailable.");
		await requireAsync(INTEGRITY_ASSET);
		if (typeof window.mountStockAccountingIntegrity !== "function") {
			throw new Error("Stock & Accounting Integrity bundle is unavailable.");
		}
		bootLoading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-stock-accounting-integrity-root";
		page.body.append(root);
		await window.mountStockAccountingIntegrity(root);
		wrapper._retailedgeStockAccountingIntegrityMounted = true;
	} catch (error) {
		bootLoading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
};
