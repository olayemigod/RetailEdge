const EDGEUI_ASSET = "edgeui.bundle.js";
const PAGE_ASSET = "branch_assignments.bundle.js";
const PAGE_ROUTE = "branch-assignments";
const PAGE_TITLE = "Branch Assignments";
const ASSET_MANIFEST_URL = "/assets/assets.json";

function requireAsync(assetName) {
	return new Promise((resolve, reject) => {
		let completed = false;
		const finish = () => { if (completed) return; completed = true; resolve(); };
		const fail = (error) => { if (completed) return; completed = true; reject(error instanceof Error ? error : new Error(String(error || assetName))); };
		try {
			const pending = frappe.require(assetName, finish);
			if (pending && typeof pending.then === "function") pending.then(finish).catch(fail);
		} catch (error) { fail(error); }
	});
}

async function getFreshBundledAsset(assetName) {
	const response = await fetch(`${ASSET_MANIFEST_URL}?v=${Date.now()}`, {
		cache: "no-store",
		credentials: "same-origin",
	});
	if (!response.ok) throw new Error(`${PAGE_TITLE} could not refresh the asset manifest.`);
	const manifest = await response.json();
	const resolved = manifest?.[assetName];
	if (!resolved) throw new Error(`${assetName} is missing from the current asset manifest.`);
	if (frappe.boot?.assets_json) frappe.boot.assets_json[assetName] = resolved;
	return resolved;
}

function loadScriptStrict(url, assetName) {
	return new Promise((resolve, reject) => {
		const script = document.createElement("script");
		script.type = "text/javascript";
		script.src = new URL(url, window.location.origin).toString();
		script.dataset.retailedgeAsset = assetName;
		script.onload = () => resolve();
		script.onerror = () => reject(new Error(`${assetName} could not be loaded from the current asset manifest.`));
		document.head.appendChild(script);
	});
}

async function ensureBundledAsset(assetName, isReady, label) {
	if (isReady()) return;
	await requireAsync(assetName);
	if (isReady()) return;

	// Frappe v16 deliberately resolves frappe.require() even when a script fails.
	// Refresh the manifest and retry the exact current hashed asset with real
	// onerror handling so an open Desk session survives a local/production rebuild.
	const resolved = await getFreshBundledAsset(assetName);
	await loadScriptStrict(resolved, assetName);
	if (!isReady()) throw new Error(`${label} loaded but did not register its runtime.`);
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
	const errorDiv = document.createElement("div");
	errorDiv.className = "alert alert-danger p-6 text-center";
	errorDiv.textContent = error?.message || __(`${PAGE_TITLE} failed to load`);
	wrapper.appendChild(errorDiv);
}

frappe.pages[PAGE_ROUTE].on_page_load = async function (wrapper) {
	hideNativePageSidebar(wrapper);
	const loading = document.createElement("div");
	loading.className = "edge-boot-loading p-6 text-center text-muted";
	loading.textContent = __(`Loading ${PAGE_TITLE}...`);
	wrapper.appendChild(loading);
	try {
		const page = frappe.ui.make_app_page({ parent: wrapper, title: __(PAGE_TITLE), single_column: true });
		wrapper.page = page;
		hideNativePageSidebar(wrapper);
		await ensureBundledAsset(EDGEUI_ASSET, () => Boolean(window.EdgeSuiteUI?.components), "EdgeSuite UI");
		await ensureBundledAsset(PAGE_ASSET, () => typeof window.mountRetailEdgeBranchAssignments === "function", PAGE_TITLE);
		loading.remove();
		const root = document.createElement("div");
		root.className = "retailedge-branch-assignments-root";
		page.body.append(root);
		wrapper._retailedgeBranchAssignmentsApp = await window.mountRetailEdgeBranchAssignments(root);
	} catch (error) {
		loading.remove();
		renderLoadError(wrapper, error);
	}
};

frappe.pages[PAGE_ROUTE].on_page_show = function (wrapper) {
	hideNativePageSidebar(wrapper);
	window.dispatchEvent(new CustomEvent("retailedge-branch-assignments-page-show"));
};
