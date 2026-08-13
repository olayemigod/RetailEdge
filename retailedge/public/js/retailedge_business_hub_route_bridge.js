(function installRetailEdgeBusinessHubRouteBridge(global) {
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
		if (definition?.wrapper) {
			state.lastWrapperSource = "frappe.pages wrapper";
			return definition.wrapper;
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
			if (matchedNode) {
				state.lastWrapperSource = selector;
				return matchedNode;
			}
		}

		const visiblePages = Array.from(
			global.document?.querySelectorAll?.(".page-container") || []
		).filter((pageNode) => {
			const style = global.getComputedStyle?.(pageNode);
			return (
				pageNode.isConnected && style?.display !== "none" && style?.visibility !== "hidden"
			);
		});
		if (visiblePages.length === 1) {
			state.lastWrapperSource = "single visible .page-container";
			return visiblePages[0];
		}
		return null;
	}

	function bootActiveRoute() {
		if (!isActiveRoute()) {
			state.attempts = 0;
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
