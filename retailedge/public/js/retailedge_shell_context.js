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
			mounted.teardown?.();
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
		if (!String(title.textContent || "").trim()) title.textContent = "ProcessEdge Retail";
	}

	function positionBranchPopover(trigger, popover) {
		if (!trigger?.isConnected || !popover?.isConnected) return;
		const rect = trigger.getBoundingClientRect();
		const viewportGap = 12;
		const width = Math.min(384, Math.max(260, window.innerWidth - viewportGap * 2));
		popover.style.width = `${width}px`;
		popover.style.maxWidth = `calc(100vw - ${viewportGap * 2}px)`;
		let left = rect.left + rect.width / 2 - width / 2;
		left = Math.max(viewportGap, Math.min(left, window.innerWidth - width - viewportGap));
		popover.style.left = `${Math.round(left)}px`;

		const measuredHeight = Math.min(popover.scrollHeight || 420, Math.max(220, window.innerHeight - viewportGap * 2));
		const below = window.innerHeight - rect.bottom - viewportGap;
		const above = rect.top - viewportGap;
		if (below >= Math.min(measuredHeight, 320) || below >= above) {
			popover.style.top = `${Math.round(rect.bottom + 8)}px`;
			popover.style.bottom = "auto";
			popover.style.maxHeight = `${Math.max(180, below)}px`;
		} else {
			popover.style.top = "auto";
			popover.style.bottom = `${Math.round(window.innerHeight - rect.top + 8)}px`;
			popover.style.maxHeight = `${Math.max(180, above)}px`;
		}
	}

	function createBranchPopover(shell, host, current, branches, signature) {
		const activeBranch = String(current.active_branch || "").trim();
		const canSwitch = Boolean(current.can_switch_branch) && branches.length > 1;
		const trigger = document.createElement("button");
		trigger.type = "button";
		trigger.className = "retailedge-topbar-branch-trigger";
		trigger.setAttribute("aria-haspopup", "dialog");
		trigger.setAttribute("aria-expanded", "false");
		trigger.disabled = !canSwitch;
		trigger.innerHTML = `
			<span class="retailedge-topbar-branch-trigger__icon" aria-hidden="true">⌘</span>
			<span class="retailedge-topbar-branch-trigger__copy">
				<small>Working Branch</small>
				<strong></strong>
			</span>
			<span class="retailedge-topbar-branch-trigger__chevron" aria-hidden="true">▾</span>
		`;
		trigger.querySelector("strong").textContent = activeBranch;
		host.appendChild(trigger);

		let popover = null;
		let outsideHandler = null;
		let keyHandler = null;
		let positionHandler = null;

		function closePopover() {
			if (!popover) return;
			popover.remove();
			popover = null;
			trigger.setAttribute("aria-expanded", "false");
			if (outsideHandler) document.removeEventListener("pointerdown", outsideHandler, true);
			if (keyHandler) document.removeEventListener("keydown", keyHandler, true);
			if (positionHandler) {
				window.removeEventListener("resize", positionHandler);
				window.removeEventListener("scroll", positionHandler, true);
			}
			outsideHandler = null;
			keyHandler = null;
			positionHandler = null;
		}

		function openPopover() {
			if (!canSwitch || popover) return;
			popover = document.createElement("section");
			popover.className = "retailedge-branch-popover";
			popover.setAttribute("role", "dialog");
			popover.setAttribute("aria-label", "Choose working branch");

			const header = document.createElement("header");
			header.className = "retailedge-branch-popover__header";
			header.innerHTML = "<strong>Working Branch</strong><small>Choose a permitted Branch for this session.</small>";
			popover.appendChild(header);

			const list = document.createElement("div");
			list.className = "retailedge-branch-popover__list";
			list.setAttribute("role", "listbox");
			for (const branch of branches) {
				const option = document.createElement("button");
				option.type = "button";
				option.className = "retailedge-branch-popover__option";
				option.setAttribute("role", "option");
				option.setAttribute("aria-selected", branch === activeBranch ? "true" : "false");
				if (branch === activeBranch) option.classList.add("is-active");
				const label = document.createElement("span");
				label.textContent = branch;
				const state = document.createElement("small");
				state.textContent = branch === activeBranch ? "Current" : "Switch";
				option.append(label, state);
				option.addEventListener("click", async () => {
					if (branch === activeBranch) {
						closePopover();
						return;
					}
					closePopover();
					await switchBranch({ value: branch });
				});
				list.appendChild(option);
			}
			popover.appendChild(list);
			document.body.appendChild(popover);
			trigger.setAttribute("aria-expanded", "true");
			positionBranchPopover(trigger, popover);

			outsideHandler = (event) => {
				if (!popover || popover.contains(event.target) || trigger.contains(event.target)) return;
				closePopover();
			};
			keyHandler = (event) => {
				if (event.key !== "Escape") return;
				event.preventDefault();
				closePopover();
				trigger.focus();
			};
			positionHandler = () => positionBranchPopover(trigger, popover);
			document.addEventListener("pointerdown", outsideHandler, true);
			document.addEventListener("keydown", keyHandler, true);
			window.addEventListener("resize", positionHandler);
			window.addEventListener("scroll", positionHandler, true);
			popover.querySelector(".retailedge-branch-popover__option")?.focus?.();
		}

		trigger.addEventListener("click", () => {
			if (popover) closePopover();
			else openPopover();
		});

		return {
			host,
			signature,
			teardown() {
				closePopover();
				trigger.remove();
			},
		};
	}

	function ensureShell(shell) {
		if (!shell?.isConnected) {
			cleanup(shell);
			return;
		}

		ensureRetailEdgeBrand(shell);
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
		host.setAttribute("aria-label", "Working Branch");
		topbarContext.appendChild(host);

		mounts.set(shell, createBranchPopover(shell, host, current, branches, signature));
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
		if (runtime()) {
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
