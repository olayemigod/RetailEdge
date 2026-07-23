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
		description: "Manage branch defaults, expense categories, statement mappings and RetailEdge settings through EdgeSuite UI.",
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
		"Review & Approvals": { icon: "check", description: "Review exceptions, evidence and reconciliation readiness." },
		"Reports & Analytics": { icon: "chart", description: "Branch, cash, stock and bank intelligence." },
		"Accounting / Ledger Bridge": { icon: "book", description: "Controlled access to native accounting records." },
		"Setup / Configuration": { icon: "settings", description: "RetailEdge setup and operating defaults." },
		"Admin / Maintenance": { icon: "shield", description: "Technical diagnostics and maintenance records." },
	});
	const ITEM_DESCRIPTIONS = Object.freeze({
		"Cashier Expense": "Record branch cash expenses against existing shift controls.",
		"Daily Sales Audit": "Review daily sales, collections, expenses and variances.",
		"Payment Statement Import": "Import statement evidence for bank matching.",
		"Branch Performance Summary": "Compare branch sales, collections and operational results.",
		"Bank Transaction Matching": "Review intelligent payment and bank transaction candidates.",
		"Reconciliation Readiness Review": "Check whether reviewed matches are ready for native reconciliation.",
		"Reconciliation Handoff": "Review approved evidence prepared for the native ERPNext reconciliation workflow.",
		"Invoice Payment Audit": "Inspect invoice payment evidence, account mismatches and risk.",
		"Cashier Expense Review": "Review expense decisions, clarification and ledger readiness.",
		"Cash Shift Verification": "Compare expected cash, closing cash and shift exceptions.",
		"Daily Sales Audit Register": "Review daily audit results and cash-control exceptions.",
		"Unmatched Bank Transactions": "Review Bank Transactions that do not yet have reliable payment evidence.",
		"Unmatched Bank Payment Events": "Review payment events that do not yet have reliable Bank Transaction evidence.",
		"POS Closing Variance vs Expenses": "Compare POS closing shortages with ERPNext and RetailEdge expense evidence.",
		"Salesperson Performance Dashboard": "Review proportional salesperson results from submitted invoices.",
		"Journal Entry": "Open native ERPNext journal records; posting permissions remain authoritative.",
		Settings: "Configure RetailEdge behaviour and controls.",
		"Branch Profile": "Manage branch-specific defaults and operating context.",
		"Expense Category": "Maintain approved expense classifications and ledger defaults.",
		"Statement Mapping Template": "Define reusable statement column mappings for bank and payment imports.",
		"Error Log": "Inspect technical errors for administrator troubleshooting.",
	});
	const HIDDEN_NAVIGATION_TARGETS = new Set([
		"DocType:RetailEdge Branch Profile User",
	]);

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

	function navigationKey(item) {
		const linkType = String(item?.link_type || "").trim();
		const target = String(item?.link_to || item?.route || "").trim();
		return linkType && target ? `${linkType}:${target}` : "";
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
		const seenTargets = new Set([navigationKey(HOME_ITEM)]);
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
			if (item.type !== "Link" || item.label === "Home" || !current || item.hidden === 1) {
				continue;
			}
			const normalized = normalizeItem(item);
			const key = navigationKey(normalized);
			if (!key || HIDDEN_NAVIGATION_TARGETS.has(key) || seenTargets.has(key)) {
				continue;
			}
			seenTargets.add(key);
			current.items.push(normalized);
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
