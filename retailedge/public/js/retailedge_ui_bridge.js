(function () {
	"use strict";

	if (typeof window === "undefined") return;

	const MINIMUM_VERSION = "0.5.0";
	const state = {
		installed: false,
		runtimeVersion: "",
		lastError: "",
	};

	function runtime() {
		return window.EdgeSuiteUI || window.EdgeUI || null;
	}

	function versionParts(version) {
		return String(version || "0.0.0")
			.split(".")
			.slice(0, 3)
			.map((part) => Number.parseInt(part, 10) || 0);
	}

	function versionAtLeast(version, minimum) {
		const current = versionParts(version);
		const required = versionParts(minimum);
		for (let index = 0; index < 3; index += 1) {
			if (current[index] > required[index]) return true;
			if (current[index] < required[index]) return false;
		}
		return true;
	}

	function openItem(item) {
		if (!item) return false;
		if (typeof item === "string") return openRoute(item);
		if (item.route && item.link_type === "URL") {
			window.location.assign(item.route);
			return true;
		}
		if (!window.frappe?.set_route) return false;
		if (item.link_type === "Report") {
			window.frappe.set_route("query-report", item.link_to);
			return true;
		}
		if (item.link_type === "DocType") {
			window.frappe.set_route("List", item.link_to);
			return true;
		}
		if (item.route) return openRoute(item.route);
		if (item.link_to) {
			window.frappe.set_route(item.link_to);
			return true;
		}
		return false;
	}

	function openRoute(route) {
		const value = String(route || "").trim();
		if (!value) return false;
		if (/^https?:\/\//i.test(value) || value.startsWith("/pos/")) {
			window.location.assign(value);
			return true;
		}
		if (value.startsWith("/app/") || value.startsWith("app/")) {
			const parts = value
				.replace(/^\//, "")
				.split("/")
				.filter(Boolean)
				.map((part) => decodeURIComponent(part));
			window.frappe?.set_route?.(...parts.slice(1));
			return true;
		}
		window.frappe?.set_route?.(...value.replace(/^\/+/, "").split("/").filter(Boolean));
		return true;
	}

	function navigationAdapter() {
		return {
			open(route) {
				return typeof route === "object" ? openItem(route) : openRoute(route);
			},
		};
	}

	function install() {
		state.lastError = "";
		const edgeUI = runtime();
		state.runtimeVersion = edgeUI?.version || "";
		if (!edgeUI?.registerAdapter) return false;
		if (!versionAtLeast(edgeUI.version, MINIMUM_VERSION)) {
			state.lastError = `RetailEdge requires EdgeSuite UI ${MINIMUM_VERSION} or newer; found ${edgeUI.version || "unknown"}.`;
			return false;
		}

		try {
			edgeUI.registerAdapter("navigation:retailedge", navigationAdapter(), { replace: true });
			state.installed = true;
			return true;
		} catch (error) {
			state.installed = false;
			state.lastError = error?.message || String(error);
			return false;
		}
	}

	function diagnose() {
		return { ...state, minimumVersion: MINIMUM_VERSION };
	}

	window.RetailEdgeUIBridge = Object.assign(window.RetailEdgeUIBridge || {}, {
		install,
		diagnose,
		openItem,
		openRoute,
	});

	if (!install()) {
		document.addEventListener("DOMContentLoaded", install, { once: true });
		window.setTimeout(install, 250);
		window.setTimeout(install, 1000);
	}
})();
