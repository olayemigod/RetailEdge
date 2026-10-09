(function bootRetailEdgeBusinessHubPage() {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const ROUTE_BRIDGE_ASSET = "/assets/retailedge/js/retailedge_business_hub_route_bridge.js";
	const MOUNT_CONTENT_SELECTOR = ".retailedge-business-hub, .hub-state";
	let recoveryScheduled = false;

	function activeRoute() {
		const route = window.frappe?.get_route?.();
		return Array.isArray(route) && route[0] === PAGE_NAME;
	}

	function pageWrapper() {
		return window.frappe?.pages?.[PAGE_NAME] || null;
	}

	function rootElement(wrapper) {
		const root = wrapper?._retailedgeBusinessHubRoot;
		if (!root) return null;
		if (root instanceof Element) return root;
		if (root.jquery) return root[0] || null;
		return root[0] instanceof Element ? root[0] : null;
	}

	function staleMountedHub(wrapper) {
		const root = rootElement(wrapper);
		if (!wrapper?._retailedgeBusinessHub || !root?.isConnected) return false;
		return !root.querySelector(MOUNT_CONTENT_SELECTOR);
	}

	function bootCurrentWrapper() {
		if (typeof window.retailedgeRegisterBusinessHubPage !== "function") {
			console.error(
				"[RetailEdge Business Hub] Desk controller is unavailable. Rebuild RetailEdge assets and clear the site cache."
			);
			return false;
		}

		window.retailedgeRegisterBusinessHubPage();
		const wrapper = pageWrapper();
		if (!wrapper || typeof window.retailedgeBootBusinessHubPage !== "function") {
			return false;
		}

		window.retailedgeBootProductMenu?.();
		window.retailedgeBootBusinessHubPage(wrapper);
		return true;
	}

	function recoverBackNavigationMount() {
		recoveryScheduled = false;
		if (!activeRoute()) return false;
		const wrapper = pageWrapper();
		if (!wrapper) return false;

		if (staleMountedHub(wrapper)) {
			window.retailedgeTeardownBusinessHubPage?.();
		}
		return bootCurrentWrapper();
	}

	function scheduleBackNavigationRecovery() {
		if (recoveryScheduled) return;
		recoveryScheduled = true;
		const schedule = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
		schedule(() => window.setTimeout(recoverBackNavigationMount, 0));
	}

	function installBackNavigationRecovery() {
		if (window.__retailedgeBusinessHubBackRecoveryInstalled) return;
		window.__retailedgeBusinessHubBackRecoveryInstalled = true;

		["page-change", "desktop_screen", "sidebar_setup"].forEach((eventName) => {
			document.addEventListener(eventName, scheduleBackNavigationRecovery);
		});
		["popstate", "hashchange", "pageshow"].forEach((eventName) => {
			window.addEventListener(eventName, scheduleBackNavigationRecovery);
		});
		window.frappe?.router?.on?.("change", scheduleBackNavigationRecovery);
	}

	function loadRouteBridge() {
		if (window.retailedgeBusinessHubRouteBridge) {
			window.retailedgeBusinessHubRouteBridge.boot();
			return;
		}

		try {
			const pending = frappe.require(ROUTE_BRIDGE_ASSET, () => {
				window.retailedgeBusinessHubRouteBridge?.boot();
			});
			if (pending && typeof pending.then === "function") {
				pending.then(() => window.retailedgeBusinessHubRouteBridge?.boot());
			}
		} catch (error) {
			console.error("[RetailEdge Business Hub] route bridge failed to load", error);
		}
	}

	installBackNavigationRecovery();
	bootCurrentWrapper();
	loadRouteBridge();
})();
