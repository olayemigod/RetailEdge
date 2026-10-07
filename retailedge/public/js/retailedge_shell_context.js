(function () {
	"use strict";

	const PRODUCT_SELECTOR = ".edge-app-shell[data-edge-product]";
	const HOST_CLASS = "retailedge-topbar-branch-switcher";
	const SHELL_ADAPTER_NAME = "shell:retailedge";
	const BUSINESS_HUB_CONTEXT_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
	const SHELL_CONTEXT_CACHE_TTL_MS = 30_000;
	const mounts = new Map();
	let observer = null;
	let scheduled = false;
	let identityRequest = null;
	let identityRefreshedAt = 0;
	let shellContextRequest = null;
	let shellAdapterRuntime = null;

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
		shellContextRequest = null;
		try {
			sessionStorage.removeItem("retailedge.operating_context");
		} catch (_error) {
			// Session storage is optional.
		}
	}

	function cachedBusinessHubContext() {
		const cache = window.__retailedgeBusinessHubContextCache;
		if (!cache?.data || !cache.fetchedAt) return null;
		if (Date.now() - Number(cache.fetchedAt || 0) > SHELL_CONTEXT_CACHE_TTL_MS) return null;
		return cache.data;
	}

	function cacheBusinessHubContext(data) {
		if (typeof window.retailedgeCacheBusinessHubContext === "function") {
			return window.retailedgeCacheBusinessHubContext(data || {});
		}
		const normalized = data || {};
		window.__retailedgeBusinessHubContextCache = { data: normalized, fetchedAt: Date.now() };
		return normalized;
	}

	function fetchBusinessHubContext() {
		if (typeof window.retailedgeGetBusinessHubContext === "function") {
			return window.retailedgeGetBusinessHubContext();
		}
		const cached = cachedBusinessHubContext();
		if (cached) return Promise.resolve(cached);
		if (shellContextRequest) return shellContextRequest;
		shellContextRequest = new Promise((resolve, reject) => {
			frappe.call({
				method: BUSINESS_HUB_CONTEXT_METHOD,
				callback: (response) => resolve(cacheBusinessHubContext(response.message || {})),
				error: reject,
			});
		}).finally(() => { shellContextRequest = null; });
		return shellContextRequest;
	}

	function shellRouteForTarget(item, nativeFallbackEnabled) {
		if (!item) return "";
		if (!nativeFallbackEnabled && ["DocType", "Report"].includes(item.target_type)) return "";
		if (item.target_type === "URL") return String(item.target || "").trim();
		if (item.target_type === "DocType") {
			const slug = frappe.router?.slug?.(item.target)
				|| String(item.target || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
			return slug ? `/app/${slug}` : "";
		}
		if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
		if (item.target_type === "Page") return `/app/${item.target}`;
		return "";
	}

	function shellMenuItems(data = {}) {
		const nativeFallbackEnabled = Boolean(data.access?.can_use_native_desk)
			&& data.feature_flags?.native_document_fallback_enabled !== false;
		return (data.navigation_groups || [])
			.map((group) => ({
				key: group.key,
				label: group.label,
				icon: group.icon || "layers",
				defaultCollapsed: group.key !== "home",
				items: (group.items || [])
					.filter((item) => nativeFallbackEnabled || !["DocType", "Report"].includes(item.target_type))
					.map((item) => ({
						label: item.label,
						description: item.description || "",
						route: shellRouteForTarget(item, nativeFallbackEnabled),
						icon: item.icon || "list",
						link_type: item.target_type,
						link_to: item.target,
						source: item,
					}))
					.filter((item) => item.route),
			}))
			.filter((group) => group.items.length);
	}

	function openShellRoute(route) {
		const value = String(route || "").trim();
		if (!value) return false;
		if (/^https?:\/\//i.test(value)) {
			window.location.assign(value);
			return true;
		}
		let url = null;
		try {
			url = new URL(value, window.location.origin);
		} catch (_error) {
			// Fall back to normal Frappe routing below.
		}
		if (url?.search || url?.hash) {
			window.location.assign(`${url.pathname}${url.search}${url.hash}`);
			return true;
		}
		const path = url?.pathname || value;
		if (path.startsWith("/app/") || path.startsWith("/desk/")) {
			const normalized = path.replace(/^\/(?:app|desk)\//, "");
			let parts = normalized.split("/").filter(Boolean).map((part) => {
				try {
					return decodeURIComponent(part);
				} catch (_error) {
					return part;
				}
			});
			// Frappe v16 may serialize Page routes as /desk/retailedge/<page>.
			// Keep RetailEdge's established public page routes stable when the shared shell adapter opens them.
			if (parts.length > 1 && String(parts[0] || "").toLowerCase() === "retailedge") {
				parts = parts.slice(1);
			}
			if (parts.length) {
				frappe.set_route(...parts);
				return true;
			}
		}
		frappe.set_route(value);
		return true;
	}

	function registerRetailEdgeShellAdapter() {
		const edgeUI = runtime();
		if (!edgeUI || typeof edgeUI.registerAdapter !== "function") return false;
		if (shellAdapterRuntime === edgeUI && edgeUI.getAdapter?.(SHELL_ADAPTER_NAME)) return true;
		const adapter = {
			async getContext() {
				const data = await fetchBusinessHubContext();
				const context = data.context || {};
				if (typeof window.retailedgeSyncShellIdentity === "function") {
					window.retailedgeSyncShellIdentity({
						active_company: context.company || "",
						active_branch: context.branch || "",
						branch_options: Array.isArray(context.branch_options) ? context.branch_options : [],
						can_switch_branch: Boolean(context.can_switch_branch),
					});
				}
				return {
					title: "ProcessEdge Retail",
					tenantName: context.company_label || context.company || "",
					branchName: context.branch || "",
					userName: context.user_name || "",
					menuItems: shellMenuItems(data),
				};
			},
			open(route) {
				return openShellRoute(route);
			},
		};
		try {
			edgeUI.registerAdapter(SHELL_ADAPTER_NAME, adapter, { replace: true });
			shellAdapterRuntime = edgeUI;
			return true;
		} catch (error) {
			if (shellAdapterRuntime === edgeUI) shellAdapterRuntime = null;
			console.warn("[RetailEdge shell] shared shell adapter registration failed", error);
			return false;
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
				message:
					window.retailedge?.userErrorMessage?.(
						error,
						__("The selected Branch could not be activated.")
					) || __("The selected Branch could not be activated."),
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
		host.setAttribute("aria-label", "Working branch");
		topbarContext.appendChild(host);

		mounts.set(shell, createBranchPopover(shell, host, current, branches, signature));
	}

	function apply() {
		scheduled = false;
		registerRetailEdgeShellAdapter();
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
		registerRetailEdgeShellAdapter();
		if (observer || !document.body) return;
		observer = new MutationObserver(schedule);
		observer.observe(document.body, { childList: true, subtree: true });
		document.addEventListener("page-change", () => {
			registerRetailEdgeShellAdapter();
			refreshIdentity().finally(schedule);
		});
		document.addEventListener("edgesuite-context-changed", () => {
			registerRetailEdgeShellAdapter();
			refreshIdentity({ force: true }).finally(schedule);
		});
		document.addEventListener("retailedge-operating-context-changed", () => {
			registerRetailEdgeShellAdapter();
			refreshIdentity({ force: true }).finally(schedule);
		});
		window.frappe?.router?.on?.("change", () => {
			registerRetailEdgeShellAdapter();
			refreshIdentity().finally(schedule);
		});
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