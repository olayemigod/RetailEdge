(function bootRetailEdgeBusinessHubControllerWhenDeskReady(global) {
	"use strict";

	const CONTROLLER_ASSET = "/assets/retailedge/js/retailedge_business_hub_page.js";
	const POLL_INTERVAL_MS = 50;
	const MAX_WAIT_MS = 30000;
	const startedAt = Date.now();
	let loading = false;

	function currentUser() {
		return (
			global.frappe?.session?.user ||
			global.frappe?.boot?.user?.name ||
			(typeof global.frappe?.boot?.user === "string" ? global.frappe.boot.user : "") ||
			""
		);
	}

	function isFullDeskRuntimeReady() {
		return Boolean(
			global.frappe &&
			currentUser() &&
			currentUser() !== "Guest" &&
			typeof global.__ === "function" &&
			typeof global.frappe.require === "function" &&
			global.frappe.pages &&
			global.frappe.ui &&
			typeof global.frappe.ui.make_app_page === "function"
		);
	}

	function controllerAlreadyLoaded() {
		return typeof global.retailedgeRegisterBusinessHubPage === "function";
	}

	function bootController() {
		if (loading || controllerAlreadyLoaded()) return;

		const user = currentUser();
		if (user === "Guest") {
			// The controller is Desk-only. Login / website contexts intentionally do nothing.
			return;
		}

		if (!isFullDeskRuntimeReady()) {
			if (Date.now() - startedAt < MAX_WAIT_MS) {
				global.setTimeout(bootController, POLL_INTERVAL_MS);
			}
			return;
		}

		loading = true;
		try {
			const pending = global.frappe.require(CONTROLLER_ASSET);
			if (pending && typeof pending.catch === "function") {
				pending.catch((error) => {
					loading = false;
					console.error("[RetailEdge Business Hub] Desk controller failed to load", error);
				});
			}
		} catch (error) {
			loading = false;
			console.error("[RetailEdge Business Hub] Desk controller failed to load", error);
		}
	}

	if (global.document?.readyState === "loading") {
		global.document.addEventListener("DOMContentLoaded", bootController, { once: true });
	} else {
		bootController();
	}
	global.addEventListener?.("load", bootController, { once: true });
})(window);
