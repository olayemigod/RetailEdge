(function () {
	"use strict";

	const PRODUCT_SELECTOR = ".edge-app-shell[data-edge-product]";
	const HOST_CLASS = "retailedge-topbar-branch-switcher";
	const mounts = new Map();
	let observer = null;
	let scheduled = false;
	let identityRequest = null;
	let identityRefreshedAt = 0;

	function runtime() {
		return window.EdgeSuiteUI || window.EdgeUI || null;
	}

	function identity() {
		const boot = window.frappe?.boot || {};
		return boot.edgesuite_ui_identity?.retailedge || boot.retailedge_ui_identity || {};
	}

	function applyIdentity(payload = {}) {
		const boot = window.frappe?.boot;
		if (!boot || !payload || typeof payload !== "object") return identity();
		boot.retailedge_ui_identity = { ...(boot.retailedge_ui_identity || {}), ...payload };
		boot.edgesuite_ui_identity = boot.edgesuite_ui_identity || {};
		boot.edgesuite_ui_identity.retailedge = { ...(boot.edgesuite_ui_identity.retailedge || {}), ...payload };
		return boot.edgesuite_ui_identity.retailedge;
	}

	async function refreshIdentity({ force = false } = {}) {
		const now = Date.now();
		if (!force && identityRefreshedAt && now - identityRefreshedAt < 5000) return identity();
		if (identityRequest) return identityRequest;
		identityRequest = new Promise((resolve) => {
			frappe.call({
				method: "retailedge.company_profile.get_shell_identity",
				callback: (response) => {
					identityRefreshedAt = Date.now();
					resolve(applyIdentity(response.message || {}));
				},
				error: () => resolve(identity()),
			});
		}).finally(() => { identityRequest = null; });
		return identityRequest;
	}

	window.retailedgeSyncShellIdentity = function (payload = {}) {
		identityRefreshedAt = Date.now();
		const next = applyIdentity(payload);
		schedule();
		return next;
	};

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

	function ensureRetailEdgeBrand(shell) {
		const brand = shell?.querySelector?.(".edge-sidebar__brand");
		if (!brand) return;
		let copy = brand.querySelector(".edge-sidebar__brand-copy");
		if (!copy) {
			copy = document.createElement("span");
			copy.className = "edge-sidebar__brand-copy retailedge-sidebar-brand-fallback";
			brand.appendChild(copy);
		}
		let title = copy.querySelector("strong");
		if (!title) {
			title = document.createElement("strong");
			copy.prepend(title);
		}
		if (!String(title.textContent || "").trim()) title.textContent = "RetailEdge";
	}

	function ensureShell(shell) {
		if (!shell?.isConnected) {
			cleanup(shell);
			return;
		}

		ensureRetailEdgeBrand(shell);
		const edge = runtime();
		const Dropdown = edge?.components?.EdgeDropdown;
		if (!edge?.createEdgeApp || !Dropdown) return;

		const topbarContext = shell.querySelector(".edge-topbar-context");
		if (!topbarContext) return;

		const current = identity();
		const branches = normalizeBranches(current.branch_options);
		const activeBranch = String(current.active_branch || "").trim();
		const needsExplicitBranch = !activeBranch && branches.length > 1 && Boolean(current.can_switch_branch);
		if (!branches.length || (!activeBranch && !needsExplicitBranch)) return;

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
			placeholder: activeBranch ? "Select branch" : "Choose working branch",
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
		document.addEventListener("page-change", () => { refreshIdentity().finally(schedule); });
		document.addEventListener("edgesuite-context-changed", () => { refreshIdentity({ force: true }).finally(schedule); });
		document.addEventListener("retailedge-operating-context-changed", () => { refreshIdentity({ force: true }).finally(schedule); });
		window.frappe?.router?.on?.("change", () => { refreshIdentity().finally(schedule); });
		refreshIdentity({ force: true }).finally(schedule);
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
