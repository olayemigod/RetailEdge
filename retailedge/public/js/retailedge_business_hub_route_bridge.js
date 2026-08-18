(function installRetailEdgeBusinessHubRouteBridge(global) {
	"use strict";

	const PAGE_NAME = "retailedge-business-hub";
	const MAX_ATTEMPTS = 40;
	const RETRY_MS = 150;
	const SIMPLE_MASTER_DOCTYPES = new Set(["Customer", "Supplier", "Item"]);
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

	function getMountedProxy(wrapper) {
		return wrapper?._retailedgeBusinessHub?._instance?.proxy || null;
	}

	function launchMasterQuickEntry(action) {
		const doctype = action?.doctype;
		if (!SIMPLE_MASTER_DOCTYPES.has(doctype)) return false;
		if (!global.frappe?.ui?.form?.make_quick_entry || !global.frappe?.model?.get_new_doc) {
			global.frappe?.new_doc?.(doctype);
			return true;
		}
		const doc = global.frappe.model.get_new_doc(doctype, null, null, true);
		global.frappe.ui.form.make_quick_entry(
			doctype,
			(created) => {
				if (created?.name) {
					global.frappe.show_alert?.({
						message: `${action.label || doctype} ${created.name} created`,
						indicator: "green",
					});
				}
			},
			null,
			doc,
			true
		);
		return true;
	}

	function installMasterQuickEntryBridge(wrapper) {
		const proxy = getMountedProxy(wrapper);
		if (!proxy || proxy.__retailedgeMasterQuickEntryBridge) return Boolean(proxy);
		const originalRunQuickAction = proxy.runQuickAction?.bind(proxy);
		const originalActionModeLabel = proxy.actionModeLabel?.bind(proxy);
		if (typeof originalRunQuickAction !== "function") return false;

		proxy.runQuickAction = (action) => {
			if (action?.master_entry && SIMPLE_MASTER_DOCTYPES.has(action.doctype)) {
				proxy.closeCreatePicker?.();
				return launchMasterQuickEntry(action);
			}
			return originalRunQuickAction(action);
		};
		proxy.actionModeLabel = (action) => {
			if (action?.master_entry && SIMPLE_MASTER_DOCTYPES.has(action.doctype)) return "Quick entry";
			return typeof originalActionModeLabel === "function" ? originalActionModeLabel(action) : "Full form";
		};
		proxy.__retailedgeMasterQuickEntryBridge = true;
		return true;
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
			Promise.resolve(pending).finally(() => installMasterQuickEntryBridge(wrapper));
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
