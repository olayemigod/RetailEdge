(function () {
	"use strict";

	if (typeof window === "undefined") return;

	const PRODUCT = "RetailEdge";
	const HOME_ITEM = Object.freeze({
		label: "RetailEdge Home",
		description: "Open the retail operations command centre.",
		icon: "home",
		link_type: "Page",
		link_to: "retailedge-home",
		route: "/app/retailedge-home",
	});
	const SETUP_WORKSPACE_ITEM = Object.freeze({
		label: "RetailEdge Setup Workspace",
		description: "Manage Branch Profiles and RetailEdge Settings through the shared EdgeSuite document experience.",
		icon: "settings",
		link_type: "Page",
		link_to: "retailedge-document-workspace",
		route: "/app/retailedge-document-workspace?resource=branch-profiles",
		roles: [
			"System Manager",
			"RetailEdge Manager",
			"RetailEdgeManager",
			"RetailEdge Branch Manager",
			"RetailEdgeBranchManager",
			"RetailEdge Auditor",
			"RetailEdgeAuditor",
			"Accounts Manager",
			"Accounts User",
		],
	});
	const SECTION_META = Object.freeze({
		Operations: { icon: "activity", description: "Sales, cash, stock and statement operations." },
		"Reports & Review": { icon: "chart", description: "Performance, bank matching and control reports." },
		"Setup / Configuration": { icon: "settings", description: "RetailEdge setup and operating defaults." },
	});
	const ITEM_DESCRIPTIONS = Object.freeze({
		"Cashier Expense": "Record branch cash expenses against existing shift controls.",
		"Daily Sales Audit": "Review daily sales, collections, expenses and variances.",
		"Payment Statement Import": "Import statement evidence for bank matching.",
		"Branch Performance Summary": "Compare branch sales, collections and operational results.",
		"Bank Transaction Matching": "Review intelligent payment and bank transaction candidates.",
		"Reconciliation Readiness": "Check whether reviewed matches are ready for ERPNext reconciliation.",
		"Reconciliation Handoff": "Move verified review evidence to the native reconciliation workflow.",
		Settings: "Configure RetailEdge behaviour and controls.",
		"Branch Profile": "Manage branch-specific defaults and operating context.",
	});

	function edgeRuntime() {
		return window.EdgeSuiteUI || window.EdgeUI || null;
	}

	function sidebar() {
		const collection = window.frappe?.boot?.workspace_sidebar_item || {};
		return collection.retailedge || collection.RetailEdge || null;
	}

	function normalizeItem(item) {
		return {
			label: item.label,
			description: ITEM_DESCRIPTIONS[item.label] || "Open this RetailEdge workspace item.",
			icon: item.icon || (item.link_type === "Report" ? "chart" : "list"),
			link_type: item.link_type || "Page",
			link_to: item.link_to || "",
			route: item.route || "",
			roles: item.roles || [],
			visible: item.hidden !== 1,
		};
	}

	function sections() {
		const result = [
			{
				label: "Home",
				description: "RetailEdge command centre and working context.",
				icon: "home",
				items: [HOME_ITEM],
			},
		];
		let current = null;
		for (const item of sidebar()?.items || []) {
			if (item.type === "Section Break") {
				const meta = SECTION_META[item.label] || {};
				current = {
					label: item.label,
					description: meta.description || "RetailEdge workspace links.",
					icon: meta.icon || "layers",
					items: [],
				};
				result.push(current);
				continue;
			}
			if (item.type === "Link" && item.label !== "Home" && current && item.hidden !== 1) {
				current.items.push(normalizeItem(item));
			}
		}
		let setupSection = result.find((section) => section.label === "Setup / Configuration");
		if (!setupSection) {
			setupSection = {
				label: "Setup / Configuration",
				description: SECTION_META["Setup / Configuration"].description,
				icon: "settings",
				items: [],
			};
			result.push(setupSection);
		}
		if (!setupSection.items.some((item) => item.link_to === SETUP_WORKSPACE_ITEM.link_to)) {
			setupSection.items.unshift(SETUP_WORKSPACE_ITEM);
		}
		return result.filter((section) => section.items.length);
	}

	function profile() {
		const boot = window.frappe?.boot || {};
		const identity = boot.retailedge?.ui || {};
		const user = identity.user || {};
		return {
			name: user.full_name || boot.user?.full_name || window.frappe?.session?.user || "RetailEdge User",
			email: user.email || window.frappe?.session?.user || "",
			company: identity.company || boot.sysdefaults?.company || "",
			branch: identity.branch || boot.edgesuite_product_menu?.branch || "",
		};
	}

	function register() {
		const edgeUI = edgeRuntime();
		if (!edgeUI?.registerProductMenu) return false;
		const config = {
			product: PRODUCT,
			subtitle: "Retail operations and business intelligence",
			sections: sections(),
			profile: profile(),
			menu_source: "workspace_sidebar",
			navigate(item) {
				if (window.RetailEdgeUIBridge?.openItem?.(item)) return;
				if (item.route) window.location.assign(item.route);
			},
		};
		edgeUI.registerProductMenu(config);
		edgeUI.refreshProductMenu?.();
		return true;
	}

	window.RetailEdgeProductMenu = Object.assign(window.RetailEdgeProductMenu || {}, {
		register,
		sections,
	});

	if (!register()) {
		document.addEventListener("DOMContentLoaded", register, { once: true });
		window.setTimeout(register, 250);
		window.setTimeout(register, 1000);
	}
})();
