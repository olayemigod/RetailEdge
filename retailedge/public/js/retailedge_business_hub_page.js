(function registerRetailEdgeBusinessHubController(global) {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const RUNTIME_ASSET = "edgesuite_ui.bundle.js";
	const PRODUCT_ASSET = "retailedge_business_hub.bundle.js";
	const LOAD_TIMEOUT_MS = 15000;

	function registerPage() {
		if (!global.frappe || !frappe.pages) {
			return false;
		}

		const definition = (frappe.pages[PAGE_NAME] = frappe.pages[PAGE_NAME] || {});
		if (definition.__retailedge_business_hub_registered) {
			return true;
		}
		definition.__retailedge_business_hub_registered = true;

		definition.on_page_load = async function onPageLoad(wrapper) {
			const page = frappe.ui.make_app_page({
				parent: wrapper,
				title: __("RetailEdge Business Hub"),
				single_column: true,
			});
			wrapper.page = page;

			const target = resolvePageBody(page, wrapper);
			clearPreviousMount(wrapper, target);
			const loading = renderLoading(target);

			try {
				if (!global.EdgeSuiteUI) {
					await requireAsset(RUNTIME_ASSET);
				}
				assertEdgeSuiteUIRuntime();

				if (typeof global.mountRetailEdgeBusinessHub !== "function") {
					await requireAsset(PRODUCT_ASSET);
				}
				if (typeof global.mountRetailEdgeBusinessHub !== "function") {
					throw new Error(__("RetailEdge Business Hub mount function is unavailable."));
				}

				loading.remove();
				const root = $("<div class=\"retailedge-business-hub-root\"></div>").appendTo(target);
				wrapper._retailedgeBusinessHubRoot = root;
				wrapper._retailedgeBusinessHub = global.mountRetailEdgeBusinessHub(root[0]);
			} catch (error) {
				loading.remove();
				console.error("[RetailEdge Business Hub] mount failed", error);
				renderFailure(target, error);
			}
		};

		definition.on_page_show = function onPageShow(wrapper) {
			const instance = wrapper._retailedgeBusinessHub;
			const component = instance && instance._instance && instance._instance.proxy;
			if (component && typeof component.refreshContext === "function") {
				component.refreshContext();
			}
		};

		return true;
	}

	function resolvePageBody(page, wrapper) {
		if (page && page.body) {
			return page.body;
		}
		if (page && page.main) {
			return page.main;
		}
		const fallback = $(wrapper).find(".layout-main-section").first();
		return fallback.length ? fallback : $(wrapper);
	}

	function clearPreviousMount(wrapper, target) {
		const instance = wrapper._retailedgeBusinessHub;
		if (instance && typeof instance.unmount === "function") {
			try {
				instance.unmount();
			} catch (error) {
				console.warn("[RetailEdge Business Hub] previous app unmount failed", error);
			}
		}
		wrapper._retailedgeBusinessHub = null;
		wrapper._retailedgeBusinessHubRoot = null;
		$(target).find(".retailedge-business-hub-root, .retailedge-business-hub-error, .edge-boot-loading").remove();
	}

	function renderLoading(target) {
		return $("<div class=\"edge-boot-loading p-6 text-center text-muted\"></div>")
			.text(__("Loading RetailEdge Business Hub..."))
			.appendTo(target);
	}

	function requireAsset(asset) {
		return new Promise((resolve, reject) => {
			let completed = false;
			const timer = global.setTimeout(() => {
				if (!completed) {
					reject(new Error(__("Timed out loading {0}", [asset])));
				}
			}, LOAD_TIMEOUT_MS);

			try {
				frappe.require(asset, () => {
					completed = true;
					global.clearTimeout(timer);
					resolve();
				});
			} catch (error) {
				completed = true;
				global.clearTimeout(timer);
				reject(error);
			}
		});
	}

	function assertEdgeSuiteUIRuntime() {
		const runtime = global.EdgeSuiteUI;
		if (!runtime || typeof runtime.createEdgeApp !== "function") {
			throw new Error(__("Standalone EdgeSuite UI runtime is unavailable or incompatible."));
		}

		const components = runtime.components || runtime;
		const required = [
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeLoadingState",
			"EdgeErrorState",
			"EdgeEmptyState",
			"EdgeStatusBadge",
		];
		const missing = required.filter((name) => !components[name]);
		if (missing.length) {
			throw new Error(__("EdgeSuite UI is missing required components: {0}", [missing.join(", ")]));
		}
	}

	function renderFailure(target, error) {
		const message = error && error.message ? error.message : __("Unknown loading error.");
		const errorBox = $("<div class=\"retailedge-business-hub-error alert alert-danger p-6 text-center\"></div>");
		errorBox.append($("<strong></strong>").text(__("RetailEdge Business Hub failed to load")));
		errorBox.append($("<div class=\"mt-2\"></div>").text(message));
		errorBox.appendTo(target);
	}

	global.retailedgeRegisterBusinessHubPage = registerPage;
	if (!registerPage() && global.document) {
		global.document.addEventListener("DOMContentLoaded", registerPage, { once: true });
	}
})(window);
