(() => {
	"use strict";

	const GLOBAL_KEY = "__retailedgeEdgesuiteOnlyOperationalGuard";
	const ACCESS_BOOT_KEY = "edgesuite_ui_access";
	const RESTRICTED_MODE = "edgesuite_only";
	const BLOCK_NOTICE = "Advanced ERPNext Desk is not available for this account. Continue in EdgeSuite or ask an authorised advanced user for this native action.";

	const existing = window[GLOBAL_KEY];
	if (existing?.install) {
		window.retailedgeInstallEdgesuiteOnlyOperationalGuard = existing.install;
		return;
	}

	const state = {
		configs: new Map(),
		observer: null,
		patchedWindowOpen: false,
		patchedSetRoute: false,
		lastNoticeAt: 0,
	};

	function restricted() {
		return window.frappe?.boot?.[ACCESS_BOOT_KEY]?.mode === RESTRICTED_MODE;
	}

	function normalize(value) {
		return String(value || "").trim().toLowerCase();
	}

	function normalizeRoutePart(value) {
		return normalize(value).replace(/[_\s]+/g, "-");
	}

	function currentPageRoute() {
		const route = window.frappe?.get_route?.();
		if (Array.isArray(route) && route.length === 1) return normalizeRoutePart(route[0]);
		const path = String(window.location?.pathname || "").replace(/^\/(?:app|desk)\/?/i, "");
		return normalizeRoutePart(path.split(/[/?#]/)[0]);
	}

	function activeConfigs() {
		if (!restricted()) return [];
		const current = currentPageRoute();
		if (!current) return [];
		return Array.from(state.configs.values()).filter((config) => current === config.pageRoute);
	}

	function shouldShowBlockedNotice() {
		return Boolean(window.event?.isTrusted);
	}

	function showBlockedNotice() {
		if (!shouldShowBlockedNotice()) return;
		const now = Date.now();
		if (now - state.lastNoticeAt < 1200) return;
		state.lastNoticeAt = now;
		if (typeof window.frappe?.show_alert === "function") {
			window.frappe.show_alert({ message: __(BLOCK_NOTICE), indicator: "orange" }, 8);
			return;
		}
		console.info(`[RetailEdge] ${BLOCK_NOTICE}`);
	}

	function urlPath(value) {
		try {
			return new URL(String(value || ""), window.location?.origin || "http://localhost").pathname.toLowerCase();
		} catch (_error) {
			return String(value || "").split(/[?#]/)[0].toLowerCase();
		}
	}

	function urlMatchesConfig(value, config) {
		const path = urlPath(value);
		if (!path) return false;
		const appPath = path.replace(/^\/(?:app|desk)\/?/i, "");
		return config.nativePathSlugs.some((slug) => {
			const normalizedSlug = normalizeRoutePart(slug);
			return appPath === normalizedSlug || appPath.startsWith(`${normalizedSlug}/`);
		});
	}

	function routeMatchesConfig(args, config) {
		const parts = Array.from(args || []).map((part) => String(part || ""));
		if (!parts.length) return false;
		const family = normalize(parts[0]);
		if (family !== "form" && family !== "list") return false;
		const target = normalize(parts[1]);
		return config.nativeDoctypes.some((doctype) => normalize(doctype) === target);
	}

	function patchWindowOpen() {
		if (state.patchedWindowOpen || typeof window.open !== "function") return;
		const originalOpen = window.open.bind(window);
		window.open = function retailedgeRestrictedWindowOpen(url, ...args) {
			if (activeConfigs().some((config) => urlMatchesConfig(url, config))) {
				showBlockedNotice();
				return null;
			}
			return originalOpen(url, ...args);
		};
		state.patchedWindowOpen = true;
	}

	function patchSetRoute() {
		if (state.patchedSetRoute || typeof window.frappe?.set_route !== "function") return;
		const originalSetRoute = window.frappe.set_route.bind(window.frappe);
		window.frappe.set_route = function retailedgeRestrictedSetRoute(...args) {
			if (activeConfigs().some((config) => routeMatchesConfig(args, config))) {
				showBlockedNotice();
				return false;
			}
			return originalSetRoute(...args);
		};
		state.patchedSetRoute = true;
	}

	function buttonLabel(node) {
		return String(node?.textContent || "").replace(/\s+/g, " ").trim();
	}

	function restoreMarkedControls() {
		document.querySelectorAll("[data-retailedge-native-hidden='true']").forEach((node) => {
			node.hidden = node.getAttribute("data-retailedge-native-was-hidden") === "true";
			node.removeAttribute("aria-hidden");
			node.removeAttribute("data-retailedge-native-hidden");
			node.removeAttribute("data-retailedge-native-was-hidden");
		});
		document.querySelectorAll("[data-retailedge-native-disabled='true']").forEach((node) => {
			if (node instanceof HTMLButtonElement) {
				node.disabled = node.getAttribute("data-retailedge-native-was-disabled") === "true";
			}
			node.removeAttribute("aria-disabled");
			node.removeAttribute("data-retailedge-native-disabled");
			node.removeAttribute("data-retailedge-native-was-disabled");
		});
	}

	function hideMatchingButtons(scope, config) {
		if (!scope || !config.hiddenButtonLabels.length) return;
		scope.querySelectorAll("button").forEach((button) => {
			if (!config.hiddenButtonLabels.includes(buttonLabel(button))) return;
			if (!button.hasAttribute("data-retailedge-native-hidden")) {
				button.setAttribute("data-retailedge-native-was-hidden", button.hidden ? "true" : "false");
			}
			button.hidden = true;
			button.setAttribute("aria-hidden", "true");
			button.setAttribute("data-retailedge-native-hidden", "true");
		});
	}

	function applyConfig(config) {
		const root = document.querySelector(config.rootSelector);
		if (!root) return;

		hideMatchingButtons(root, config);
		document.querySelectorAll(".modal").forEach((scope) => hideMatchingButtons(scope, config));

		config.neutralizeSelectors.forEach((selector) => {
			root.querySelectorAll(selector).forEach((node) => {
				if (node instanceof HTMLButtonElement) {
					if (!node.hasAttribute("data-retailedge-native-disabled")) {
						node.setAttribute("data-retailedge-native-was-disabled", node.disabled ? "true" : "false");
					}
					node.disabled = true;
				}
				node.setAttribute("aria-disabled", "true");
				node.setAttribute("data-retailedge-native-disabled", "true");
			});
		});
	}

	function applyPresentationGuard() {
		const configs = activeConfigs();
		if (!configs.length) {
			restoreMarkedControls();
			return;
		}
		configs.forEach(applyConfig);
	}

	function scheduleApply() {
		(window.requestAnimationFrame || window.setTimeout)(applyPresentationGuard);
	}

	function ensureObserver() {
		if (state.observer || !document?.documentElement || typeof MutationObserver === "undefined") return;
		state.observer = new MutationObserver(scheduleApply);
		state.observer.observe(document.documentElement, { childList: true, subtree: true });
	}

	function normalizeConfig(raw = {}) {
		return {
			pageRoute: normalizeRoutePart(raw.pageRoute),
			rootSelector: String(raw.rootSelector || "").trim(),
			nativeDoctypes: Array.isArray(raw.nativeDoctypes) ? raw.nativeDoctypes.filter(Boolean).map(String) : [],
			nativePathSlugs: Array.isArray(raw.nativePathSlugs) ? raw.nativePathSlugs.filter(Boolean).map(String) : [],
			hiddenButtonLabels: Array.isArray(raw.hiddenButtonLabels) ? raw.hiddenButtonLabels.filter(Boolean).map(String) : [],
			neutralizeSelectors: Array.isArray(raw.neutralizeSelectors) ? raw.neutralizeSelectors.filter(Boolean).map(String) : [],
		};
	}

	function install(rawConfig) {
		const config = normalizeConfig(rawConfig);
		if (!config.pageRoute || !config.rootSelector) throw new Error("RetailEdge restricted operational guard requires pageRoute and rootSelector.");
		state.configs.set(config.pageRoute, config);
		patchWindowOpen();
		patchSetRoute();
		ensureObserver();
		scheduleApply();
		return config;
	}

	["page-change", "toolbar_setup"].forEach((eventName) => document.addEventListener(eventName, scheduleApply));
	window.frappe?.router?.on?.("change", scheduleApply);

	window[GLOBAL_KEY] = { install, state, restricted };
	window.retailedgeInstallEdgesuiteOnlyOperationalGuard = install;
})();
