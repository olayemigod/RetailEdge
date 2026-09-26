const PRODUCT = "RetailEdge";
const SHARED_RUNTIME_ASSET = "edgeui.bundle.js";
const CONTEXT_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const CONTEXT_CACHE_TTL_MS = 30_000;
const MAX_INSTALL_ATTEMPTS = 6;
const GUIDED_CREATE_ACTION = "guided-create";
const BUSINESS_HUB_ROUTE = "retailedge-business-hub";
const GLOBAL_CREATE_BUTTON_ID = "retailedge-global-create-button";
const GLOBAL_CREATE_HOST_ID = "retailedge-global-create-host";
const GLOBAL_CREATE_STYLE_ID = "retailedge-global-create-style";

const GROUP_PRESENTATION = Object.freeze({
	home: { icon: "home", description: "Business home and command centre." },
	sell: { icon: "shopping-cart", description: "Sell, fulfil orders, invoice, and run point of sale." },
	buy: { icon: "shopping-bag", description: "Buy stock, services, and operating supplies." },
	stock: { icon: "stock", description: "Control products, warehouses, movement, counts, and stock health." },
	money: { icon: "credit-card", description: "Manage collections, payments, statements, and bank reconciliation." },
	expenses: { icon: "file-text", description: "Record and control day-to-day business expenses." },
	customers: { icon: "users", description: "Manage customers, receivables, statements, and collections." },
	"suppliers-payables": { icon: "users", description: "Manage suppliers, bills, payables, and payment obligations." },
	insights: { icon: "chart", description: "Understand business, branch, sales, stock, and cash performance." },
	"review-approvals": { icon: "shield", description: "Review approvals, exceptions, audits, and control issues." },
	accounting: { icon: "book-open", description: "Professional accounting reports and finance records." },
	setup: { icon: "settings", description: "Configure RetailEdge business rules and defaults." },
});

const ITEM_ICONS = Object.freeze({
	Page: "dashboard",
	Report: "chart",
	DocType: "list",
	URL: "external-link",
	Action: "plus",
});

const state = {
	installed: false,
	installing: null,
	attempts: 0,
	lastError: null,
	lastConfig: null,
};

function runtime() {
	return window.EdgeSuiteUI || null;
}

function requireAsset(asset) {
	return new Promise((resolve, reject) => {
		let settled = false;
		const finish = () => {
			if (settled) return;
			settled = true;
			resolve();
		};
		const fail = (error) => {
			if (settled) return;
			settled = true;
			reject(error instanceof Error ? error : new Error(String(error || asset)));
		};

		try {
			const pending = frappe.require(asset, finish);
			if (pending && typeof pending.then === "function") {
				pending.then(finish).catch(fail);
			}
		} catch (error) {
			fail(error);
		}
	});
}

async function ensureRuntime() {
	if (!runtime()) {
		await requireAsset(SHARED_RUNTIME_ASSET);
	}
	const edgeUI = runtime();
	if (!edgeUI || typeof edgeUI.registerProductMenu !== "function") {
		throw new Error("Standalone EdgeSuite UI product-menu runtime is unavailable.");
	}
	return edgeUI;
}

function readContextCache() {
	const cache = window.__retailedgeBusinessHubContextCache;
	if (!cache || !cache.data || !cache.fetchedAt) return null;
	if (Date.now() - cache.fetchedAt > CONTEXT_CACHE_TTL_MS) return null;
	return cache.data;
}

function cacheContext(data) {
	const normalized = data || {};
	window.__retailedgeBusinessHubContextCache = {
		data: normalized,
		fetchedAt: Date.now(),
	};
	return normalized;
}

function fetchContext({ force = false } = {}) {
	if (!force) {
		const cached = readContextCache();
		if (cached) return Promise.resolve(cached);
	}
	if (window.__retailedgeBusinessHubContextRequest) {
		return window.__retailedgeBusinessHubContextRequest;
	}

	const request = new Promise((resolve, reject) => {
		frappe.call({
			method: CONTEXT_METHOD,
			callback(response) {
				resolve(cacheContext(response.message || {}));
			},
			error(error) {
				reject(
					error instanceof Error
						? error
						: new Error("Unable to load RetailEdge product menu.")
				);
			},
		});
	});
	window.__retailedgeBusinessHubContextRequest = request;
	request.finally(() => {
		if (window.__retailedgeBusinessHubContextRequest === request) {
			window.__retailedgeBusinessHubContextRequest = null;
		}
	});
	return request;
}

function itemDescription(item) {
	if (item.target_type === "Report") return "Open report";
	if (item.target_type === "DocType") return "Open records";
	if (item.target_type === "Page") return "Open workspace";
	if (item.target_type === "URL") return "Open application";
	return "Open";
}

function guidedCreateSection(quickActions) {
	const actions = Array.isArray(quickActions) ? quickActions : [];
	if (!actions.length) return null;
	return {
		label: "Create",
		description: "Start a permission-aware guided business entry.",
		icon: "plus",
		items: [
			{
				label: "+ Create",
				description: `${actions.length} permitted guided entr${actions.length === 1 ? "y" : "ies"}`,
				icon: "plus",
				link_type: "Action",
				link_to: GUIDED_CREATE_ACTION,
				route: "",
				visible: true,
			},
		],
	};
}

function buildSections(groups, quickActions = []) {
	const sections = (Array.isArray(groups) ? groups : [])
		.map((group) => {
			const presentation = GROUP_PRESENTATION[group.key] || {
				icon: "layers",
				description: "RetailEdge tools and records.",
			};
			const items = (Array.isArray(group.items) ? group.items : []).map((item) => ({
				label: item.label,
				description: item.description || itemDescription(item),
				icon: item.icon || ITEM_ICONS[item.target_type] || "list",
				link_type: item.target_type,
				link_to: item.target,
				route: item.target_type === "URL" ? item.target : "",
				visible: true,
			}));
			return {
				label: group.label,
				description: presentation.description,
				icon: group.icon || presentation.icon,
				items,
			};
		})
		.filter((section) => section.items.length);
	const createSection = guidedCreateSection(quickActions);
	return createSection ? [createSection, ...sections] : sections;
}

function requestGuidedCreate() {
	window.__retailedgeOpenGuidedCreate = true;
	const route = frappe.get_route?.() || [];
	if (route[0] === BUSINESS_HUB_ROUTE) {
		document.dispatchEvent(new CustomEvent("retailedge-open-guided-create"));
		return;
	}
	frappe.set_route(BUSINESS_HUB_ROUTE);
}

function withDocTypeMeta(doctype) {
	return new Promise((resolve, reject) => {
		let settled = false;
		const finish = () => {
			if (settled) return;
			settled = true;
			resolve(frappe.get_meta?.(doctype) || null);
		};
		try {
			if (typeof frappe.model?.with_doctype !== "function") {
				finish();
				return;
			}
			const pending = frappe.model.with_doctype(doctype, finish);
			if (pending && typeof pending.then === "function") {
				pending.then(finish).catch(reject);
			}
		} catch (error) {
			reject(error);
		}
	});
}

function canCreateDocType(doctype) {
	try {
		return typeof frappe.model?.can_create === "function"
			? Boolean(frappe.model.can_create(doctype))
			: false;
	} catch (_error) {
		return false;
	}
}

async function openDocTypeMenuTarget(doctype) {
	const target = String(doctype || "").trim();
	if (!target) return false;
	try {
		const meta = await withDocTypeMeta(target);
		if (meta?.quick_entry && canCreateDocType(target) && typeof frappe.new_doc === "function") {
			frappe.new_doc(target);
			return true;
		}
	} catch (error) {
		console.warn(`[RetailEdge Product Menu] quick-entry detection failed for ${target}`, error);
	}
	frappe.set_route("List", target);
	return true;
}

function openNativeDeskTarget(linkType, linkTo) {
	const target = String(linkTo || "").trim();
	if (!target) return false;
	if (linkType === "Report") {
		frappe.set_route("query-report", target);
		return true;
	}
	if (linkType === "DocType") {
		void openDocTypeMenuTarget(target);
		return true;
	}
	return false;
}

function nativeSidebarTarget(label) {
	const normalized = String(label || "").trim();
	if (!normalized) return null;
	const matches = (state.lastConfig?.sections || [])
		.flatMap((section) => section.items || [])
		.filter((item) => item.label === normalized);
	if (matches.length !== 1) return null;
	const item = matches[0];
	return item.link_type === "Report" || item.link_type === "DocType" ? item : null;
}

function handleNativeSidebarClick(event) {
	const button = event.target?.closest?.(".edge-app-shell .edge-sidebar-item");
	if (!button) return;
	const labelNode = button.querySelector?.(".edge-sidebar-item__label");
	const item = nativeSidebarTarget(labelNode?.textContent || button.textContent);
	if (!item) return;
	event.preventDefault();
	event.stopPropagation();
	event.stopImmediatePropagation();
	openNativeDeskTarget(item.link_type, item.link_to);
}

function navigate(item) {
	if (!item) return;
	if (item.link_type === "Action" && item.link_to === GUIDED_CREATE_ACTION) {
		requestGuidedCreate();
		return;
	}
	if (item.link_type === "URL") {
		window.location.assign(item.route || item.link_to);
		return;
	}
	if (item.link_type === "Report" || item.link_type === "DocType") {
		openNativeDeskTarget(item.link_type, item.link_to);
		return;
	}
	if (!window.frappe?.set_route) return;
	frappe.set_route(item.link_to);
}

function profileFromContext(context = {}) {
	return {
		name: context.user_name || context.user || "RetailEdge User",
		email: context.user || "",
		company: context.company || "",
		branch: context.branch || "All Branches",
	};
}

async function installProductMenu({ force = false } = {}) {
	if (state.installing) return state.installing;
	if (state.installed && !force) {
		refreshProductMenu();
		return state.lastConfig;
	}

	state.installing = (async () => {
		state.attempts += 1;
		const edgeUI = await ensureRuntime();
		const data = await fetchContext();
		const sections = buildSections(data.navigation_groups, data.quick_actions);
		if (!sections.length) {
			throw new Error("No permitted RetailEdge product-menu sections are available.");
		}

		const config = {
			product: PRODUCT,
			subtitle: "Retail operations, actions, reports, and controls",
			sections,
			profile: profileFromContext(data.context),
			menu_source: "retailedge_navigation_registry",
			navigate,
		};
		edgeUI.registerProductMenu(config);
		edgeUI.refreshProductMenu?.();
		edgeUI.mountProductMenu?.();
		state.installed = true;
		state.lastError = null;
		state.lastConfig = config;
		installGlobalCreateMountObserver();
		mountGlobalCreateButton();
		return config;
	})()
		.catch((error) => {
			state.installed = false;
			state.lastError = error;
			console.error("[RetailEdge Product Menu] installation failed", error);
			if (state.attempts < MAX_INSTALL_ATTEMPTS) {
				window.setTimeout(() => installProductMenu({ force: true }), state.attempts * 500);
			}
			return null;
		})
		.finally(() => {
			state.installing = null;
		});

	return state.installing;
}

function refreshProductMenu() {
	const edgeUI = runtime();
	if (!edgeUI || !state.lastConfig) return false;
	edgeUI.refreshProductMenu?.();
	const mounted = edgeUI.mountProductMenu?.() ?? true;
	mountGlobalCreateButton();
	return mounted;
}

const PRODUCT_MENU_DROPDOWN_ID = "edge-product-menu-dropdown";
const PRODUCT_MENU_TRIGGER_SELECTOR = [
	'[aria-controls="edge-product-menu-dropdown"]',
	"#edge-product-menu-trigger",
	".edge-product-menu__trigger",
	".edge-topbar__launcher",
	".edge-topbar__waffle",
	"[data-edge-product-menu-trigger]",
].join(", ");

function hasGuidedCreateAction() {
	return Boolean(
		(state.lastConfig?.sections || []).some((section) =>
			(section.items || []).some(
				(item) => item.link_type === "Action" && item.link_to === GUIDED_CREATE_ACTION
			)
		)
	);
}

function ensureGlobalCreateStyle() {
	if (document.getElementById(GLOBAL_CREATE_STYLE_ID)) return;
	const style = document.createElement("style");
	style.id = GLOBAL_CREATE_STYLE_ID;
	style.textContent = `
		#${GLOBAL_CREATE_HOST_ID} {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			list-style: none;
			margin: 0;
			padding: 0;
		}
		#${GLOBAL_CREATE_BUTTON_ID} {
			display: inline-flex;
			align-items: center;
			justify-content: center;
			gap: 0.35rem;
			min-height: 32px;
			padding: 0 0.7rem;
			margin-inline: 0.25rem;
			border: 1px solid var(--edge-border-color, var(--border-color));
			border-radius: 999px;
			background: var(--edge-surface, var(--card-bg));
			color: var(--edge-text, var(--text-color));
			font: inherit;
			font-size: 0.82rem;
			font-weight: 600;
			line-height: 1;
			cursor: pointer;
			white-space: nowrap;
		}
		#${GLOBAL_CREATE_BUTTON_ID}:hover {
			background: var(--edge-surface-subtle, var(--subtle-fg));
		}
		#${GLOBAL_CREATE_BUTTON_ID} .retailedge-global-create__plus {
			font-size: 1.05rem;
			line-height: 1;
		}
		@media (max-width: 768px) {
			#${GLOBAL_CREATE_BUTTON_ID} {
				width: 32px;
				min-width: 32px;
				padding: 0;
			}
			#${GLOBAL_CREATE_BUTTON_ID} .retailedge-global-create__label {
				display: none;
			}
		}
	`;
	document.head?.appendChild(style);
}

function createGlobalCreateButton() {
	const button = document.createElement("button");
	button.id = GLOBAL_CREATE_BUTTON_ID;
	button.type = "button";
	button.setAttribute("aria-label", "Create");
	button.setAttribute("title", "Create");
	button.setAttribute("data-retailedge-global-create", "1");

	const plus = document.createElement("span");
	plus.className = "retailedge-global-create__plus";
	plus.setAttribute("aria-hidden", "true");
	plus.textContent = "+";

	const label = document.createElement("span");
	label.className = "retailedge-global-create__label";
	label.textContent = "Create";

	button.append(plus, label);
	button.addEventListener("click", (event) => {
		event.preventDefault();
		event.stopPropagation();
		requestGuidedCreate();
	});
	return button;
}

function locateGlobalCreateAnchor() {
	const trigger = document.querySelector(PRODUCT_MENU_TRIGGER_SELECTOR);
	if (trigger) {
		return {
			node: trigger.closest("li, .dropdown, .edge-topbar__action") || trigger,
			position: "afterend",
		};
	}

	const notification = document.querySelector(
		".dropdown-notifications, .notifications, .navbar .notifications-icon, [data-original-title*='Notification'], [aria-label*='Notification']"
	);
	if (notification) {
		return {
			node: notification.closest("li, .dropdown, .edge-topbar__action") || notification,
			position: "beforebegin",
		};
	}

	const toolbar = document.querySelector(
		".navbar .navbar-nav:last-child, .navbar .navbar-right, .navbar .ml-auto, .edge-topbar__actions"
	);
	return toolbar ? { node: toolbar, position: "prepend" } : null;
}

function createGlobalCreateHost(anchor) {
	const parentTag = String(anchor?.node?.parentElement?.tagName || "").toUpperCase();
	const host = document.createElement(parentTag === "UL" || parentTag === "OL" ? "li" : "div");
	host.id = GLOBAL_CREATE_HOST_ID;
	host.className = "retailedge-global-create-host";
	host.setAttribute("data-retailedge-global-create-host", "1");
	host.appendChild(createGlobalCreateButton());
	return host;
}

function mountGlobalCreateButton() {
	const existingHost = document.getElementById(GLOBAL_CREATE_HOST_ID);
	if (!hasGuidedCreateAction()) {
		existingHost?.remove();
		return false;
	}

	ensureGlobalCreateStyle();
	const anchor = locateGlobalCreateAnchor();
	if (!anchor?.node) return false;

	const host = existingHost || createGlobalCreateHost(anchor);
	if (anchor.position === "prepend") {
		if (host.parentElement !== anchor.node || anchor.node.firstElementChild !== host) {
			anchor.node.prepend(host);
		}
	} else if (host.parentElement !== anchor.node.parentElement || host.previousElementSibling !== anchor.node) {
		anchor.node.insertAdjacentElement(anchor.position, host);
	}
	return Boolean(document.getElementById(GLOBAL_CREATE_BUTTON_ID));
}

let globalCreateObserver = null;
let globalCreateMountScheduled = false;

function scheduleGlobalCreateMount() {
	if (globalCreateMountScheduled) return;
	globalCreateMountScheduled = true;
	const schedule = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
	schedule(() => {
		globalCreateMountScheduled = false;
		mountGlobalCreateButton();
	});
}

function installGlobalCreateMountObserver() {
	if (globalCreateObserver || !document.body) {
		scheduleGlobalCreateMount();
		return;
	}
	globalCreateObserver = new MutationObserver(() => {
		if (!hasGuidedCreateAction()) return;
		const button = document.getElementById(GLOBAL_CREATE_BUTTON_ID);
		if (!button?.isConnected) scheduleGlobalCreateMount();
	});
	globalCreateObserver.observe(document.body, { childList: true, subtree: true });
	scheduleGlobalCreateMount();
}

function productMenuIsOpen() {
	const dropdown = document.getElementById(PRODUCT_MENU_DROPDOWN_ID);
	return Boolean(dropdown && !dropdown.hidden && dropdown.getAttribute("aria-hidden") !== "true");
}

function requestProductMenuOpen() {
	if (productMenuIsOpen()) return true;
	const edgeUI = runtime();
	for (const method of ["openProductMenu", "showProductMenu", "toggleProductMenu"]) {
		if (typeof edgeUI?.[method] !== "function") continue;
		try {
			edgeUI[method]();
			return true;
		} catch (error) {
			console.warn(`[RetailEdge Product Menu] ${method} failed`, error);
		}
	}
	// EdgeSuite UI owns Ctrl+K as the canonical product-menu shortcut. Reuse
	// that public interaction as a final recovery path instead of maintaining
	// a second RetailEdge flyout implementation.
	document.dispatchEvent(new KeyboardEvent("keydown", {
		key: "k",
		code: "KeyK",
		ctrlKey: true,
		bubbles: true,
		cancelable: true,
	}));
	return true;
}

function recoverProductMenuTrigger(event) {
	const trigger = event.target?.closest?.(PRODUCT_MENU_TRIGGER_SELECTOR);
	if (!trigger) return;
	// Allow the EdgeSuite UI trigger to handle the click first. If its mounted
	// flyout was lost during a Desk/Vue remount, restore the registered product
	// menu and open it on the next frame.
	const schedule = window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
	schedule(() => {
		if (productMenuIsOpen()) return;
		Promise.resolve(state.installed ? refreshProductMenu() : installProductMenu())
			.finally(() => schedule(() => {
				if (!productMenuIsOpen()) requestProductMenuOpen();
			}));
	});
}

function scheduleRefresh() {
	const schedule =
		window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
	schedule(() => {
		if (state.installed) refreshProductMenu();
		else installProductMenu();
		scheduleGlobalCreateMount();
	});
}

["toolbar_setup", "page-change", "desktop_screen", "sidebar_setup"].forEach((eventName) => {
	document.addEventListener(eventName, scheduleRefresh);
});
document.addEventListener("click", handleNativeSidebarClick, true);
document.addEventListener("click", recoverProductMenuTrigger, true);
window.frappe?.router?.on?.("change", scheduleRefresh);

window.retailedgeGetBusinessHubContext = fetchContext;
window.retailedgeCacheBusinessHubContext = cacheContext;
window.retailedgeInstallProductMenu = installProductMenu;
window.retailedgeRefreshProductMenu = refreshProductMenu;
window.retailedgeRequestProductMenuOpen = requestProductMenuOpen;
window.retailedgeMountGlobalCreateButton = mountGlobalCreateButton;
window.retailedgeOpenDocTypeMenuTarget = openDocTypeMenuTarget;
window.retailedgeOpenNativeTarget = openNativeDeskTarget;
window.retailedgeProductMenuState = state;

installProductMenu();