(function installRetailEdgeBusinessHubRouteBridgeV2(global) {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const MAX_ATTEMPTS = 40;
	const RETRY_MS = 150;
	const state = {
		attempts: 0,
		booted: false,
		lastError: null,
		lastWrapperSource: "",
	};

	function isActiveRoute() {
		const route = global.frappe?.get_route?.();
		return Array.isArray(route) && route[0] === PAGE_NAME;
	}

	function resolveWrapper() {
		const definition = global.frappe?.pages?.[PAGE_NAME];
		if (definition instanceof global.HTMLElement && definition.isConnected) {
			state.lastWrapperSource = "frappe.pages page container";
			return definition;
		}

		const selectors = [
			`.page-container[data-page-route="${PAGE_NAME}"]`,
			`.page-container[data-page-name="${PAGE_NAME}"]`,
			`[data-page-route="${PAGE_NAME}"]`,
			`[data-page-name="${PAGE_NAME}"]`,
			`.page-container[data-route="${PAGE_NAME}"]`,
		];
		for (const selector of selectors) {
			const matchedNode = global.document?.querySelector(selector);
			if (matchedNode?.isConnected) {
				state.lastWrapperSource = selector;
				return matchedNode;
			}
		}
		return null;
	}

	function bootActiveRoute() {
		if (!isActiveRoute()) {
			state.attempts = 0;
			state.booted = false;
			state.lastWrapperSource = "";
			global.retailedgeTeardownBusinessHubPage?.();
			return false;
		}

		state.attempts += 1;
		try {
			global.retailedgeRegisterBusinessHubPage?.();
			const wrapper = resolveWrapper();
			if (!wrapper) {
				if (state.attempts < MAX_ATTEMPTS) {
					global.setTimeout(bootActiveRoute, RETRY_MS);
				}
				return false;
			}

			global.retailedgeBootProductMenu?.();
			const pending = global.retailedgeBootBusinessHubPage?.(wrapper);
			state.booted = true;
			state.lastError = null;
			return pending || true;
		} catch (error) {
			state.booted = false;
			state.lastError = error;
			console.error("[RetailEdge Business Hub Route Bridge] boot failed", error);
			if (state.attempts < MAX_ATTEMPTS) {
				global.setTimeout(bootActiveRoute, RETRY_MS);
			}
			return false;
		}
	}

	function scheduleBoot() {
		global.requestAnimationFrame?.(bootActiveRoute) || global.setTimeout(bootActiveRoute, 0);
	}

	["DOMContentLoaded", "page-change", "desktop_screen", "sidebar_setup"].forEach((eventName) => {
		global.document?.addEventListener(eventName, scheduleBoot);
	});
	global.frappe?.router?.on?.("change", scheduleBoot);

	global.retailedgeBusinessHubRouteBridge = {
		boot: bootActiveRoute,
		state,
	};

	scheduleBoot();
})(window);
