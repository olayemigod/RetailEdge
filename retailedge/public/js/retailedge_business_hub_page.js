(function registerRetailEdgeBusinessHubController(global) {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const RUNTIME_ASSET = "edgeui.bundle.js";
	const PRODUCT_ASSET = "retailedge_business_hub.bundle.js";
	const PRODUCT_MENU_ASSET = "retailedge_product_menu.bundle.js";
	const ROUTE_BRIDGE_ASSET = "/assets/retailedge/js/retailedge_business_hub_route_bridge.js";
	const LOAD_TIMEOUT_MS = 15000;
	let productMenuBootPromise = null;
	let routeBridgeBootPromise = null;
	let activeWrapper = null;

	function isBusinessHubRoute() {
		const route = global.frappe?.get_route?.();
		return Array.isArray(route) && route[0] === PAGE_NAME;
	}

	function registerPage() {
		if (!global.frappe || !frappe.pages) {
			return false;
		}

		const wrapper = frappe.pages[PAGE_NAME];
		if (!(wrapper instanceof global.HTMLElement)) {
			return false;
		}
		if (wrapper.__retailedge_business_hub_registered) {
			return true;
		}
		wrapper.__retailedge_business_hub_registered = true;

		wrapper.on_page_load = function onPageLoad(currentWrapper) {
			ensurePage(currentWrapper);
			return bootBusinessHub(currentWrapper);
		};

		wrapper.on_page_show = function onPageShow(currentWrapper) {
			ensurePage(currentWrapper);
			bootProductMenu();
			if (!currentWrapper._retailedgeBusinessHub) {
				return bootBusinessHub(currentWrapper);
			}

			const component = getMountedComponent(currentWrapper);
			if (component && typeof component.refreshContext === "function") {
				return component.refreshContext();
			}
			return undefined;
		};

		return true;
	}

	function suppressNativePageChrome(wrapper) {
		if (!wrapper) return;
		$(wrapper).addClass("retailedge-edge-shell-page");
		const pageHead = $(wrapper).find(".page-head").first();
		if (!pageHead.length) return;
		pageHead.attr("data-retailedge-shell-suppressed", "1");
		pageHead.hide();
	}

	function ensurePage(wrapper) {
		if (wrapper.page && wrapper._retailedgeBusinessHubTarget) {
			suppressNativePageChrome(wrapper);
			return wrapper.page;
		}

		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("RetailEdge Business Hub"),
			single_column: true,
		});
		wrapper.page = page;
		wrapper._retailedgeBusinessHubTarget = resolvePageBody(page, wrapper);
		suppressNativePageChrome(wrapper);
		return page;
	}

	function bootBusinessHub(wrapper) {
		activeWrapper = wrapper;
		if (wrapper._retailedgeBusinessHubBootPromise) {
			return wrapper._retailedgeBusinessHubBootPromise;
		}

		wrapper._retailedgeBusinessHubBootPromise = mountBusinessHub(wrapper).finally(() => {
			wrapper._retailedgeBusinessHubBootPromise = null;
		});
		return wrapper._retailedgeBusinessHubBootPromise;
	}

	async function mountBusinessHub(wrapper) {
		ensurePage(wrapper);
		const target =
			wrapper._retailedgeBusinessHubTarget || resolvePageBody(wrapper.page, wrapper);
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
				throw new Error(
					__(
						"RetailEdge Business Hub bundle loaded without exposing its mount function: {0}",
						[PRODUCT_ASSET]
					)
				);
			}

			if (!isBusinessHubRoute() || activeWrapper !== wrapper) {
				loading.remove();
				return null;
			}

			loading.remove();
			const root = $('<div class="retailedge-business-hub-root"></div>').appendTo(target);
			wrapper._retailedgeBusinessHubRoot = root;
			wrapper._retailedgeBusinessHub = global.mountRetailEdgeBusinessHub(root[0]);
			global.retailedgeRefreshProductMenu?.();
			return wrapper._retailedgeBusinessHub;
		} catch (mountError) {
			loading.remove();
			if (!isBusinessHubRoute()) return null;
			console.error("[RetailEdge Business Hub] mount failed", mountError);
			renderFailure(target, mountError);
			return null;
		}
	}

	function teardownBusinessHub() {
		const wrapper = activeWrapper;
		activeWrapper = null;
		if (wrapper) {
			const target =
				wrapper._retailedgeBusinessHubTarget || resolvePageBody(wrapper.page, wrapper);
			clearPreviousMount(wrapper, target);
			wrapper._retailedgeBusinessHubBootPromise = null;
		}
		$(global.document)
			.find(
				".retailedge-business-hub-root, .retailedge-business-hub-error, .edge-boot-loading"
			)
			.remove();
		return true;
	}

	function bootProductMenu() {
		if (typeof global.retailedgeInstallProductMenu === "function") {
			return global.retailedgeInstallProductMenu();
		}
		if (productMenuBootPromise) return productMenuBootPromise;

		productMenuBootPromise = requireAsset(PRODUCT_MENU_ASSET)
			.then(() => {
				if (typeof global.retailedgeInstallProductMenu !== "function") {
					throw new Error(
						__(
							"RetailEdge product-menu bundle loaded without exposing its installer: {0}",
							[PRODUCT_MENU_ASSET]
						)
					);
				}
				return global.retailedgeInstallProductMenu();
			})
			.catch((menuError) => {
				console.error("[RetailEdge Product Menu] boot failed", menuError);
				return null;
			})
			.finally(() => {
				productMenuBootPromise = null;
			});
		return productMenuBootPromise;
	}

	function bootRouteBridge() {
		if (global.retailedgeBusinessHubRouteBridge) {
			return global.retailedgeBusinessHubRouteBridge.boot();
		}
		if (routeBridgeBootPromise) return routeBridgeBootPromise;

		routeBridgeBootPromise = requireAsset(ROUTE_BRIDGE_ASSET)
			.then(() => {
				if (!global.retailedgeBusinessHubRouteBridge) {
					throw new Error(
						__("RetailEdge Business Hub route bridge failed to register: {0}", [
							ROUTE_BRIDGE_ASSET,
						])
					);
				}
				return global.retailedgeBusinessHubRouteBridge.boot();
			})
			.catch((bridgeError) => {
				console.error(
					"[RetailEdge Business Hub] route bridge failed to load",
					bridgeError
				);
				return null;
			})
			.finally(() => {
				routeBridgeBootPromise = null;
			});
		return routeBridgeBootPromise;
	}

	function getMountedComponent(wrapper) {
		const instance = wrapper._retailedgeBusinessHub;
		return instance && instance._instance && instance._instance.proxy;
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
			} catch (unmountError) {
				console.warn(
					"[RetailEdge Business Hub] previous app unmount failed",
					unmountError
				);
			}
		}
		wrapper._retailedgeBusinessHub = null;
		wrapper._retailedgeBusinessHubRoot = null;
		$(target)
			.find(
				".retailedge-business-hub-root, .retailedge-business-hub-error, .edge-boot-loading"
			)
			.remove();
	}

	function renderLoading(target) {
		return $('<div class="edge-boot-loading p-6 text-center text-muted"></div>')
			.text(__("Loading RetailEdge Business Hub..."))
			.appendTo(target);
	}

	function requireAsset(asset) {
		return new Promise((resolve, reject) => {
			let settled = false;
			const finish = () => {
				if (settled) return;
				settled = true;
				global.clearTimeout(timer);
				resolve();
			};
			const fail = (error) => {
				if (settled) return;
				settled = true;
				global.clearTimeout(timer);
				reject(error instanceof Error ? error : new Error(String(error || asset)));
			};
			const timer = global.setTimeout(() => {
				fail(new Error(__("Timed out loading {0}", [asset])));
			}, LOAD_TIMEOUT_MS);

			try {
				const pending = frappe.require(asset, finish);
				if (pending && typeof pending.then === "function") {
					pending.then(finish).catch(fail);
				}
			} catch (requireError) {
				fail(requireError);
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
			throw new Error(
				__("EdgeSuite UI is missing required components: {0}", [missing.join(", ")])
			);
		}
	}

	function renderFailure(target, failure) {
		const message =
			failure && failure.message ? failure.message : __("Unknown loading error.");
		const errorBox = $(
			'<div class="retailedge-business-hub-error alert alert-danger p-6 text-center"></div>'
		);
		errorBox.append($("<strong></strong>").text(__("RetailEdge Business Hub failed to load")));
		errorBox.append($('<div class="mt-2"></div>').text(message));
		errorBox.appendTo(target);
	}

	function initialiseDeskFeatures() {
		const pageRegistered = registerPage();
		bootProductMenu();
		bootRouteBridge();
		return pageRegistered;
	}

	global.retailedgeRegisterBusinessHubPage = registerPage;
	global.retailedgeBootBusinessHubPage = bootBusinessHub;
	global.retailedgeTeardownBusinessHubPage = teardownBusinessHub;
	global.retailedgeBootProductMenu = bootProductMenu;
	global.retailedgeBootBusinessHubRouteBridge = bootRouteBridge;
	if (!initialiseDeskFeatures() && global.document) {
		global.document.addEventListener("DOMContentLoaded", initialiseDeskFeatures, {
			once: true,
		});
	}
})(window);
