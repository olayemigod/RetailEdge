(function () {
	"use strict";

	const PRODUCT_SELECTOR = ".edge-app-shell[data-edge-product]";
	const HOST_CLASS = "retailedge-topbar-branch-switcher";
	const mounts = new Map();
	let observer = null;
	let scheduled = false;

	function runtime() {
		return window.EdgeSuiteUI || window.EdgeUI || null;
	}

	function identity() {
		const boot = window.frappe?.boot || {};
		return boot.edgesuite_ui_identity?.retailedge || boot.retailedge_ui_identity || {};
	}

	function normalizeBranches(values) {
		return [...new Set((Array.isArray(values) ? values : []).map((value) => String(value || "").trim()).filter(Boolean))];
	}

	function cleanup(shell) {
		const mounted = mounts.get(shell);
		if (!mounted) return;
		try {
			mounted.app?.unmount?.();
		} catch (_error) {
			// A detached Desk route should not block cleanup.
		}
		try {
			mounted.host?.remove?.();
		} catch (_error) {
			// Ignore already-removed route nodes.
		}
		mounts.delete(shell);
	}

	function clearRetailEdgeContextCaches() {
		window.__retailedgeBusinessHubContextCache = null;
		window.__retailedgeBusinessHubContextRequest = null;
		try {
			sessionStorage.removeItem("retailedge.operating_context");
		} catch (_error) {
			// Session storage is optional.
		}
	}

	async function switchBranch(option) {
		const value = String(option?.value || option || "").trim();
		const current = identity();
		const company = String(current.active_company || "").trim();
		if (!value || !company || value === String(current.active_branch || "").trim()) return;

		try {
			await frappe.call({
				method: "retailedge.operating_context.switch_operating_context",
				args: { company, branch: value },
				freeze: true,
				freeze_message: __("Switching working branch..."),
			});
			clearRetailEdgeContextCaches();
			document.dispatchEvent(new CustomEvent("edgesuite-context-changed", {
				detail: { product: "retailedge", company, branch: value },
			}));
			window.location.reload();
		} catch (error) {
			frappe.msgprint({
				title: __("Unable to switch branch"),
				message: error?.message || error?.exc || __("The selected Branch could not be activated."),
				indicator: "red",
			});
		}
	}

	function ensureShell(shell) {
		if (!shell?.isConnected) {
			cleanup(shell);
			return;
		}

		const edge = runtime();
		const Dropdown = edge?.components?.EdgeDropdown;
		if (!edge?.createEdgeApp || !Dropdown) return;

		const topbarContext = shell.querySelector(".edge-topbar-context");
		if (!topbarContext) return;

		const current = identity();
		const branches = normalizeBranches(current.branch_options);
		const activeBranch = String(current.active_branch || "").trim();
		if (!branches.length || !activeBranch) return;

		const signature = JSON.stringify({
			activeBranch,
			branches,
			canSwitch: Boolean(current.can_switch_branch),
		});
		const mounted = mounts.get(shell);
		if (mounted?.signature === signature && mounted.host?.isConnected) return;
		cleanup(shell);

		topbarContext.replaceChildren();
		const host = document.createElement("div");
		host.className = HOST_CLASS;
		host.setAttribute("aria-label", "Working branch");
		topbarContext.appendChild(host);

		const app = edge.createEdgeApp(Dropdown, {
			modelValue: activeBranch,
			options: branches,
			placeholder: "Select branch",
			disabled: !current.can_switch_branch || branches.length <= 1,
			class: "retailedge-topbar-branch-dropdown",
			onChange: switchBranch,
		});
		app.mount(host);
		mounts.set(shell, { app, host, signature });
	}

	function apply() {
		scheduled = false;
		for (const [shell] of mounts) {
			if (!shell?.isConnected) cleanup(shell);
		}
		document.querySelectorAll(PRODUCT_SELECTOR).forEach((shell) => {
			if (String(shell.getAttribute("data-edge-product") || "").trim().toLowerCase() === "retailedge") {
				ensureShell(shell);
			}
		});
	}

	function schedule() {
		if (scheduled) return;
		scheduled = true;
		(window.requestAnimationFrame || window.setTimeout)(apply);
	}

	function start() {
		if (observer || !document.body) return;
		observer = new MutationObserver(schedule);
		observer.observe(document.body, { childList: true, subtree: true });
		document.addEventListener("page-change", schedule);
		document.addEventListener("edgesuite-context-changed", schedule);
		window.frappe?.router?.on?.("change", schedule);
		schedule();
	}

	function boot() {
		const edge = runtime();
		if (edge?.components?.EdgeDropdown && edge?.createEdgeApp) {
			start();
			return;
		}
		try {
			frappe.require("edgeui.bundle.js", start);
		} catch (_error) {
			window.setTimeout(boot, 100);
		}
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot, { once: true });
	} else {
		boot();
	}
})();
