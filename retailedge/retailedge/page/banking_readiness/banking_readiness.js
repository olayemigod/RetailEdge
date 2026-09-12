(function installRetailEdgeBankingReadinessPage(global) {
	"use strict";

	const PAGE_NAME = "banking-readiness";
	const READINESS_FILTERS = [
		{ label: "All States", value: "All" },
		{ label: "Ready", value: "Ready" },
		{ label: "Warning", value: "Warning" },
		{ label: "Blocked", value: "Blocked" },
	];

	function runtime() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}

	function t(text, args) {
		return typeof global.__ === "function" ? global.__(text, args) : text;
	}

	function clean(value) {
		return String(value ?? "").trim();
	}

	let navigationContextPromise = null;

	async function getNavigationContext() {
		if (!navigationContextPromise) {
			navigationContextPromise = (async () => {
				if (typeof global.retailedgeGetBusinessHubContext === "function") {
					return (await global.retailedgeGetBusinessHubContext()) || {};
				}
				const response = await global.frappe.call({
					method: "retailedge.edgesuite_ui.get_retailedge_business_hub_context",
				});
				return response?.message || {};
			})();
		}
		return navigationContextPromise;
	}

	function routeForNavigationItem(item) {
		if (item?.target_type === "Page") return `/app/${item.target}`;
		if (item?.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
		if (item?.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
		return item?.target || "";
	}

	function mapNavigationGroups(groups) {
		return (groups || []).map((group) => ({
			...group,
			items: (group.items || []).map((item) => ({ ...item, route: routeForNavigationItem(item) })),
		}));
	}

	async function permissionAwareLinkSearch(doctype, query, filters = {}) {
		const response = await global.frappe.call({
			method: "frappe.desk.search.search_link",
			args: { doctype, txt: clean(query), filters, page_length: 20 },
		});
		return (response?.message || []).map((row) => ({
			value: row.value || row.name,
			label: row.label || row.value || row.name,
			description: row.description || "",
		}));
	}

	function issueItems(row) {
		const issues = Array.isArray(row?.issues) ? row.issues : [];
		const warnings = Array.isArray(row?.warnings) ? row.warnings : [];
		return [
			...issues.map((item) => ({ ...item, severity: item.severity || "Blocked" })),
			...warnings.map((item) => ({ ...item, severity: item.severity || "Warning" })),
		].filter((item) => clean(item.message));
	}

	function openNativeBankAccount(name) {
		if (!name) return;
		global.open(`/app/bank-account/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer");
	}

	frappe.pages[PAGE_NAME].on_page_load = function onPageLoad(wrapper) {
		const edge = runtime();
		if (!edge?.createEdgeApp || !edge?.Vue) {
			global.frappe.throw(t("EdgeSuite UI runtime is required for Banking Setup & Readiness."));
		}
		const required = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeFilterBar", "EdgeLinkField", "EdgeDropdown", "EdgeStatCard", "EdgeStatusBadge", "EdgeLoadingState", "EdgeEmptyState", "EdgeErrorState"];
		const missing = required.filter((name) => !edge.getComponent(name));
		if (missing.length) global.frappe.throw(t("EdgeSuite UI is missing required readiness components: {0}", [missing.join(", ")]));

		const page = global.frappe.ui.make_app_page({
			parent: wrapper,
			title: t("Banking Setup & Readiness"),
			single_column: true,
		});
		const { defineComponent, h, onMounted, reactive, computed } = edge.Vue;
		const EdgeAppShell = edge.getComponent("EdgeAppShell");
		const EdgePageLayout = edge.getComponent("EdgePageLayout");
		const EdgePageHeader = edge.getComponent("EdgePageHeader");
		const EdgeFilterBar = edge.getComponent("EdgeFilterBar");
		const EdgeLinkField = edge.getComponent("EdgeLinkField");
		const EdgeDropdown = edge.getComponent("EdgeDropdown");
		const EdgeStatCard = edge.getComponent("EdgeStatCard");
		const EdgeStatusBadge = edge.getComponent("EdgeStatusBadge");
		const EdgeLoadingState = edge.getComponent("EdgeLoadingState");
		const EdgeEmptyState = edge.getComponent("EdgeEmptyState");
		const EdgeErrorState = edge.getComponent("EdgeErrorState");

		const component = defineComponent({
			name: "RetailEdgeBankingReadinessEdgeSuite",
			setup() {
				const state = reactive({
					loading: false,
					error: "",
					company: "",
					menuItems: [],
					tenantName: "",
					branchName: "",
					userName: "",
					canUseNativeDesk: false,
					readinessFilter: "All",
					rows: [],
					summary: { ready: 0, warning: 0, blocked: 0 },
				});
				const total = computed(() => Number(state.summary.ready || 0) + Number(state.summary.warning || 0) + Number(state.summary.blocked || 0));
				const visibleRows = computed(() => {
					if (state.readinessFilter === "All") return state.rows;
					return state.rows.filter((row) => clean(row.readiness) === state.readinessFilter);
				});

				async function loadShellContext() {
					const context = await getNavigationContext();
					state.menuItems = mapNavigationGroups(context.navigation_groups || []);
					state.canUseNativeDesk = Boolean(context.access?.can_use_native_desk);
					state.tenantName = context.context?.company || "";
					state.branchName = context.context?.branch || "";
					state.userName = context.context?.user_name || context.context?.user || "";
					if (!state.company) state.company = context.context?.company || "";
				}

				function handleNavigation(route) {
					const item = state.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
					if (!item) return;
					if (["DocType", "Report"].includes(item.target_type) && !state.canUseNativeDesk) return;
					if (item.target_type === "Page") global.frappe.set_route(item.target);
					else if (item.target_type === "Report") global.frappe.set_route("query-report", item.target);
					else if (item.target_type === "DocType") global.frappe.set_route("List", item.target);
				}

				async function refresh() {
					state.loading = true;
					state.error = "";
					try {
						const response = await global.frappe.call({
							method: "retailedge.banking_readiness.get_banking_readiness",
							args: { company: state.company || "" },
						});
						const payload = response?.message || {};
						state.rows = payload.rows || [];
						state.summary = payload.summary || { ready: 0, warning: 0, blocked: 0 };
					} catch (error) {
						state.error = error?.message || t("Unable to evaluate banking readiness.");
					} finally {
						state.loading = false;
					}
				}

				function actionButton(label, variant, onClick, extra = {}) {
					return h("button", {
						type: "button",
						class: ["edge-button", `edge-button--${variant}`],
						onClick,
						...extra,
					}, label);
				}

				function metric(label, value, helper, tone) {
					return h(EdgeStatCard, { label, value: Number(value || 0), helper, tone });
				}

				function contextItem(label, value, status = "") {
					return h("div", { class: "retailedge-readiness-context-item" }, [
						h("span", t(label)),
						h("div", { class: "retailedge-readiness-context-value" }, [
							h("strong", value || t("Not configured")),
							status ? h(EdgeStatusBadge, { status }) : null,
						]),
					]);
				}

				function issueRow(item) {
					return h("li", { class: "retailedge-readiness-issue" }, [
						h(EdgeStatusBadge, { status: item.severity || "Warning" }),
						h("span", item.message),
					]);
				}

				function rowCard(row) {
					const items = issueItems(row);
					const modes = Array.isArray(row.mode_of_payments) ? row.mode_of_payments.filter(Boolean) : [];
					const branchScope = row.branch_scope || t("Company Wide / Central");
					const reconciliation = row.can_reconcile ? t("Allowed") : t("Blocked");
					return h("section", { class: ["retailedge-readiness-card", `is-${clean(row.readiness || "warning").toLowerCase()}`] }, [
						h("header", { class: "retailedge-readiness-card__header" }, [
							h("div", null, [
								h("h2", row.bank_account || t("Bank Account")),
								h("p", [row.bank, row.company].filter(Boolean).join(" · ")),
							]),
							h(EdgeStatusBadge, { status: row.readiness || "Warning" }),
						]),
						h("div", { class: "retailedge-readiness-context-grid" }, [
							contextItem("GL Account", row.resolved_gl_account),
							contextItem("Branch Scope", branchScope, row.branch ? "Scoped" : "Company Wide"),
							contextItem("Mode of Payment", modes.join(", ") || t("No default"), modes.length ? "Configured" : "Supporting only"),
							contextItem("Reconciliation", reconciliation, row.can_reconcile ? "Allowed" : "Blocked"),
						]),
						items.length ? h("div", { class: "retailedge-readiness-diagnostics" }, [
							h("h3", row.can_reconcile ? t("Readiness guidance") : t("Blocking issues")),
							h("ul", items.map(issueRow)),
						]) : h("p", { class: "retailedge-readiness-clear" }, t("No banking setup issues were detected for this account.")),
						h("footer", { class: "retailedge-readiness-card__actions" }, [
							state.canUseNativeDesk && row.resolved_gl_account ? actionButton(t("Open GL Account"), "secondary", () => global.frappe.set_route("Form", "Account", row.resolved_gl_account)) : null,
							state.canUseNativeDesk ? actionButton(t("Open ERPNext Bank Account"), "secondary", () => openNativeBankAccount(row.bank_account)) : null,
						]),
					]);
				}

				onMounted(async () => {
					await Promise.all([loadShellContext(), refresh()]);
				});

				return () => h(EdgeAppShell, {
					product: "RetailEdge",
					title: t("Banking Setup & Readiness"),
					tenantName: state.tenantName || state.company,
					branchName: state.branchName,
					userName: state.userName,
					menuItems: state.menuItems,
					activeRoute: "/app/banking-readiness",
					hideNativeSidebar: true,
					onNavigate: handleNavigation,
				}, {
					default: () => h(EdgePageLayout, { class: "retailedge-banking-readiness-shell" }, {
						header: () => h(EdgePageHeader, {
							eyebrow: t("RetailEdge Banking"),
							title: t("Banking Setup & Readiness"),
							subtitle: t("Verify ERPNext Bank Account, GL, company and supporting payment context before matching or reconciliation."),
						}, {
							actions: () => [
								actionButton(t("Bank Matching & Reconciliation"), "secondary", () => global.frappe.set_route("bank-matching-reconciliation")),
								actionButton(t("Refresh"), "primary", refresh, { disabled: state.loading }),
							],
						}),
						filters: () => h(EdgeFilterBar, { title: t("Context") }, {
							default: () => [
								h(EdgeLinkField, {
									label: t("Company"),
									modelValue: state.company,
									searcher: (query) => permissionAwareLinkSearch("Company", query),
									"onUpdate:modelValue": (value) => { state.company = value || ""; refresh(); },
								}),
								h(EdgeDropdown, {
									label: t("Readiness State"),
									modelValue: state.readinessFilter,
									options: READINESS_FILTERS.map((item) => ({ value: item.value, label: t(item.label) })),
									"onUpdate:modelValue": (value) => { state.readinessFilter = value || "All"; },
								}),
							],
							actions: () => (state.company || state.readinessFilter !== "All") ? [actionButton(t("Clear Filters"), "secondary", () => { state.company = ""; state.readinessFilter = "All"; refresh(); })] : [],
						}),
						default: () => [
							h("div", { class: "retailedge-readiness-summary" }, [
								metric(t("Bank Accounts"), total.value, state.company || t("All permitted companies"), "neutral"),
								metric(t("Ready"), state.summary.ready, t("No setup concerns"), "success"),
								metric(t("Warning"), state.summary.warning, t("Usable with guidance"), "warning"),
								metric(t("Blocked"), state.summary.blocked, t("Cannot reconcile safely"), "danger"),
							]),
							state.loading ? h(EdgeLoadingState, { message: t("Evaluating banking readiness...") }) : null,
							state.error ? h(EdgeErrorState, { message: state.error, actionLabel: t("Try again"), onRetry: refresh }) : null,
							!state.loading && !state.error && !visibleRows.value.length ? h(EdgeEmptyState, {
								title: state.readinessFilter === "All" ? t("No Bank Accounts found") : t("No bank accounts in this readiness state"),
								description: state.readinessFilter === "All" ? t("Select another company or configure an ERPNext Bank Account that you are permitted to use.") : t("Choose another readiness state or company to continue."),
							}) : null,
							!state.loading && !state.error ? h("div", { class: "retailedge-readiness-list" }, visibleRows.value.map(rowCard)) : null,
						],
					}),
				});
			},
		});

		const app = edge.createEdgeApp(component);
		app.mount(page.main[0]);
		wrapper.retailedgeBankingReadinessApp = app;
	};
})(window);
