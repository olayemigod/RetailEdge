const PRODUCT = "RetailEdge";
const SHARED_RUNTIME_ASSET = "edgeui.bundle.js";
const CONTEXT_METHOD = "retailedge.edgesuite_ui.get_retailedge_business_hub_context";
const MAX_INSTALL_ATTEMPTS = 6;

const GROUP_PRESENTATION = Object.freeze({
	home: { icon: "home", description: "Business overview and performance." },
	sales: { icon: "shopping-cart", description: "Sell, serve customers, and review sales." },
	purchases: {
		icon: "shopping-bag",
		description: "Buy stock, services, and operating supplies.",
	},
	inventory: { icon: "stock", description: "Control items, warehouses, movements, and counts." },
	"cash-banking": {
		icon: "credit-card",
		description: "Manage collections, payments, shifts, and reconciliation.",
	},
	expenses: { icon: "file-text", description: "Record and review operating expenses." },
	"customers-suppliers": {
		icon: "users",
		description: "Manage business relationships and balances.",
	},
	"reports-insights": {
		icon: "chart",
		description: "Understand sales, stock, cash, and branch performance.",
	},
	setup: { icon: "settings", description: "Configure RetailEdge business rules and defaults." },
	administration: { icon: "shield", description: "Restricted technical and governance tools." },
});

const ITEM_ICONS = Object.freeze({
	Page: "dashboard",
	Report: "chart",
	DocType: "list",
	URL: "external-link",
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

function fetchContext() {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: CONTEXT_METHOD,
			callback(response) {
				resolve(response.message || {});
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
}

function itemDescription(item) {
	if (item.target_type === "Report") return "Open report";
	if (item.target_type === "DocType") return "Open records";
	if (item.target_type === "Page") return "Open workspace";
	if (item.target_type === "URL") return "Open application";
	return "Open";
}

function buildSections(groups) {
	return (Array.isArray(groups) ? groups : [])
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
				icon: presentation.icon,
				items,
			};
		})
		.filter((section) => section.items.length);
}

function navigate(item) {
	if (!item) return;
	if (item.link_type === "URL") {
		window.location.assign(item.route || item.link_to);
		return;
	}
	if (!window.frappe?.set_route) return;
	if (item.link_type === "Report") {
		frappe.set_route("query-report", item.link_to);
		return;
	}
	if (item.link_type === "DocType") {
		frappe.set_route("List", item.link_to);
		return;
	}
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
		const sections = buildSections(data.navigation_groups);
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
	return edgeUI.mountProductMenu?.() ?? true;
}

function scheduleRefresh() {
	const schedule =
		window.requestAnimationFrame || ((callback) => window.setTimeout(callback, 0));
	schedule(() => {
		if (state.installed) refreshProductMenu();
		else installProductMenu();
	});
}

["toolbar_setup", "page-change", "desktop_screen", "sidebar_setup"].forEach((eventName) => {
	document.addEventListener(eventName, scheduleRefresh);
});
window.frappe?.router?.on?.("change", scheduleRefresh);

window.retailedgeInstallProductMenu = installProductMenu;
window.retailedgeRefreshProductMenu = refreshProductMenu;
window.retailedgeProductMenuState = state;

installProductMenu();
