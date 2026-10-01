(function installRetailEdgeUsageReconciliationPage(global) {
	"use strict";

	const PAGE_NAME = "usage-reconciliation";
	const PAGE_LENGTH = 50;

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
		if (item?.target_type === "Report") {
			return `/app/query-report/${encodeURIComponent(item.target)}`;
		}
		if (item?.target_type === "DocType") {
			return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
		}
		return item?.target || "";
	}

	function mapNavigationGroups(groups) {
		return (groups || []).map((group) => ({
			...group,
			items: (group.items || []).map((item) => ({
				...item,
				route: routeForNavigationItem(item),
			})),
		}));
	}

	function dropdownOptions(values, blankLabel) {
		const rows = (values || []).map((value) => ({ value, label: value }));
		return blankLabel ? [{ value: "", label: t(blankLabel) }, ...rows] : rows;
	}

	frappe.pages[PAGE_NAME].on_page_load = function onPageLoad(wrapper) {
		const edge = runtime();
		if (!edge?.createEdgeApp || !edge?.Vue) {
			global.frappe.throw(t("Required interface components are unavailable for Usage Reconciliation."));
		}

		const required = [
			"EdgeAppShell",
			"EdgePageLayout",
			"EdgePageHeader",
			"EdgeFilterBar",
			"EdgeDropdown",
			"EdgeStatCard",
			"EdgeStatusBadge",
			"EdgeLoadingState",
			"EdgeEmptyState",
			"EdgeErrorState",
		];
		const missing = required.filter((name) => !edge.getComponent(name));
		if (missing.length) {
			global.frappe.throw(
				t("Required reconciliation components are unavailable. Refresh the page or contact your administrator.")
			);
		}

		const page = global.frappe.ui.make_app_page({
			parent: wrapper,
			title: t("Usage Reconciliation"),
			single_column: true,
		});
		const { defineComponent, h, onMounted, reactive } = edge.Vue;
		const EdgeAppShell = edge.getComponent("EdgeAppShell");
		const EdgePageLayout = edge.getComponent("EdgePageLayout");
		const EdgePageHeader = edge.getComponent("EdgePageHeader");
		const EdgeFilterBar = edge.getComponent("EdgeFilterBar");
		const EdgeDropdown = edge.getComponent("EdgeDropdown");
		const EdgeStatCard = edge.getComponent("EdgeStatCard");
		const EdgeStatusBadge = edge.getComponent("EdgeStatusBadge");
		const EdgeLoadingState = edge.getComponent("EdgeLoadingState");
		const EdgeEmptyState = edge.getComponent("EdgeEmptyState");
		const EdgeErrorState = edge.getComponent("EdgeErrorState");

		const component = defineComponent({
			name: "RetailEdgeUsageReconciliation",
			setup() {
				const state = reactive({
					loading: false,
					error: "",
					menuItems: [],
					tenantName: "",
					branchName: "",
					userName: "",
					canUseNativeDesk: false,
					company: "",
					branch: "",
					status: "Needs Review",
					sourceDoctype: "",
					search: "",
					rows: [],
					summary: {
						needs_review: 0,
						pending_finalize: 0,
						finalized: 0,
						open: 0,
					},
					options: {
						companies: [],
						branches: [],
						statuses: ["Needs Review", "Pending Finalize", "Finalized", "All"],
						source_doctypes: ["Sales Invoice", "POS Invoice"],
					},
					canRetry: false,
					hasMore: false,
					limitStart: 0,
					requiresCompany: false,
					noBranchAccess: false,
				});

				async function loadShellContext() {
					const context = await getNavigationContext();
					state.menuItems = mapNavigationGroups(context.navigation_groups || []);
					state.canUseNativeDesk = Boolean(context.access?.can_use_native_desk);
					state.tenantName = context.context?.company || "";
					state.branchName = context.context?.branch || "";
					state.userName = context.context?.user_name || context.context?.user || "";
					if (!state.company) state.company = context.context?.company || "";
					if (!state.branch) state.branch = context.context?.branch || "";
				}

				function handleNavigation(route) {
					const item = state.menuItems
						.flatMap((group) => group.items || [])
						.find((candidate) => candidate.route === route);
					if (!item) return;
					if (["DocType", "Report"].includes(item.target_type) && !state.canUseNativeDesk) return;
					if (item.target_type === "Page") global.frappe.set_route(item.target);
					else if (item.target_type === "Report") global.frappe.set_route("query-report", item.target);
					else if (item.target_type === "DocType") global.frappe.set_route("List", item.target);
				}

				function filtersPayload() {
					return {
						company: state.company || "",
						branch: state.branch || "",
						status: state.status || "Needs Review",
						source_doctype: state.sourceDoctype || "",
						search: clean(state.search),
					};
				}

				async function refresh(reset = true) {
					state.loading = true;
					state.error = "";
					if (reset) state.limitStart = 0;
					try {
						const response = await global.frappe.call({
							method: "retailedge.usage_reconciliation.get_usage_reconciliation",
							args: {
								filters: filtersPayload(),
								limit_start: state.limitStart,
								page_length: PAGE_LENGTH,
							},
						});
						const payload = response?.message || {};
						state.rows = reset
							? (payload.rows || [])
							: [...state.rows, ...(payload.rows || [])];
						state.summary = payload.summary || state.summary;
						state.options = payload.options || state.options;
						state.canRetry = Boolean(payload.access?.can_retry);
						state.hasMore = Boolean(payload.pagination?.has_more);
						state.requiresCompany = Boolean(payload.metadata?.requires_company);
						state.noBranchAccess = Boolean(payload.metadata?.no_branch_access);
						state.company = payload.filters?.company ?? state.company;
						state.branch = payload.filters?.branch ?? state.branch;
					} catch (error) {
						state.error = error?.message || t("Unable to load usage reconciliation.");
					} finally {
						state.loading = false;
					}
				}

				async function loadMore() {
					state.limitStart = state.rows.length;
					await refresh(false);
				}

				function openSource(row) {
					if (!row.source_doctype || !row.source_name) return;
					global.frappe.set_route("Form", row.source_doctype, row.source_name);
				}

				function retryFinalization(row) {
					if (!row.retry_allowed || row._retrying) return;
					global.frappe.confirm(
						t("Retry finalization against the existing platform reservation? No new reservation will be created."),
						async () => {
							row._retrying = true;
							try {
								const response = await global.frappe.call({
									method: "retailedge.usage_reconciliation.retry_usage_finalization",
									type: "POST",
									args: { operation_name: row.name },
								});
								const result = response?.message || {};
								if (result.status === "Finalized") {
									global.frappe.show_alert({
										message: t("Usage finalization confirmed."),
										indicator: "green",
									});
								} else {
									global.frappe.show_alert({
										message: t("The usage exception still requires review."),
										indicator: "orange",
									});
								}
								await refresh(true);
							} catch (error) {
								state.error = error?.message || t("Unable to retry usage finalization.");
							} finally {
								row._retrying = false;
							}
						}
					);
				}

				function actionButton(label, variant, onClick, extra = {}) {
					return h(
						"button",
						{
							type: "button",
							class: ["edge-button", `edge-button--${variant}`],
							onClick,
							...extra,
						},
						label
					);
				}

				function metric(label, value, helper, tone) {
					return h(EdgeStatCard, {
						label,
						value: Number(value || 0),
						helper,
						tone,
					});
				}

				function contextItem(label, value) {
					return h("div", { class: "retailedge-usage-context-item" }, [
						h("span", t(label)),
						h("strong", value || t("Not available")),
					]);
				}

				function rowCard(row) {
					return h("section", { class: ["retailedge-usage-card", `is-${row.severity || "warning"}`] }, [
						h("header", { class: "retailedge-usage-card__header" }, [
							h("div", null, [
								h("h2", `${row.source_doctype || t("Sale")} · ${row.source_name || row.name}`),
								h("p", [row.company, row.branch].filter(Boolean).join(" · ")),
							]),
							h(EdgeStatusBadge, { status: row.status || "Needs Review" }),
						]),
						h("div", { class: "retailedge-usage-context-grid" }, [
							contextItem("Reason", row.reason_code || row.status),
							contextItem("Reservation", row.reservation_reference || t("None")),
							contextItem("Attempts", row.attempt_count || 0),
							contextItem("Reserved On", row.reserved_on || ""),
						]),
						h("div", { class: "retailedge-usage-guidance" }, [
							h("strong", row.requires_platform_reconciliation ? t("Platform review required") : t("Next action")),
							h("p", row.guidance || ""),
							row.last_error ? h("small", [t("Latest error"), ": ", row.last_error]) : null,
						]),
						h("footer", { class: "retailedge-usage-card__actions" }, [
							actionButton(t("Open Sale"), "secondary", () => openSource(row)),
							row.retry_allowed
								? actionButton(
									t(row._retrying ? "Retrying..." : "Retry Finalization"),
									"primary",
									() => retryFinalization(row),
									{ disabled: Boolean(row._retrying) }
								)
								: null,
						]),
					]);
				}

				onMounted(async () => {
					await loadShellContext();
					await refresh(true);
				});

				return () => h(
					EdgeAppShell,
					{
						product: "RetailEdge",
						title: t("Usage Reconciliation"),
						tenantName: state.tenantName || state.company,
						branchName: state.branchName,
						userName: state.userName,
						menuItems: state.menuItems,
						activeRoute: "/app/usage-reconciliation",
						hideNativeSidebar: true,
						onNavigate: handleNavigation,
					},
					{
						default: () => h(
							EdgePageLayout,
							{ class: "retailedge-usage-reconciliation-shell" },
							{
								header: () => h(
									EdgePageHeader,
									{
										eyebrow: t("Operations Review"),
										title: t("Usage Reconciliation"),
										subtitle: t("Review committed sales whose platform usage finalization needs confirmation or escalation."),
									},
									{
										actions: () => [
											actionButton(t("Refresh"), "primary", () => refresh(true), {
												disabled: state.loading,
											}),
										],
									}
								),
								filters: () => h(
									EdgeFilterBar,
									{ title: t("Review Scope") },
									{
										default: () => [
											h(EdgeDropdown, {
												label: t("Company"),
												modelValue: state.company,
												options: dropdownOptions(state.options.companies, "Choose Company"),
												"onUpdate:modelValue": (value) => {
													state.company = value || "";
													state.branch = "";
													refresh(true);
												},
											}),
											h(EdgeDropdown, {
												label: t("Branch"),
												modelValue: state.branch,
												options: dropdownOptions(state.options.branches, "All permitted Branches"),
												"onUpdate:modelValue": (value) => {
													state.branch = value || "";
													refresh(true);
												},
											}),
											h(EdgeDropdown, {
												label: t("Status"),
												modelValue: state.status,
												options: dropdownOptions(state.options.statuses),
												"onUpdate:modelValue": (value) => {
													state.status = value || "Needs Review";
													refresh(true);
												},
											}),
											h(EdgeDropdown, {
												label: t("Source"),
												modelValue: state.sourceDoctype,
												options: dropdownOptions(state.options.source_doctypes, "All Sales"),
												"onUpdate:modelValue": (value) => {
													state.sourceDoctype = value || "";
													refresh(true);
												},
											}),
											h("label", { class: "retailedge-usage-search" }, [
												h("span", t("Search")),
												h("input", {
													type: "search",
													class: "form-control",
													value: state.search,
													placeholder: t("Invoice, reservation or reason"),
													onInput: (event) => { state.search = event.target.value || ""; },
													onKeyup: (event) => {
														if (event.key === "Enter") refresh(true);
													},
												}),
											]),
										],
										actions: () => [
											actionButton(t("Apply"), "secondary", () => refresh(true)),
										],
									}
								),
								default: () => [
									h("div", { class: "retailedge-usage-summary" }, [
										metric(t("Needs Review"), state.summary.needs_review, t("Human review required"), "danger"),
										metric(t("Pending Finalize"), state.summary.pending_finalize, t("Automatic retry pending"), "warning"),
										metric(t("Open"), state.summary.open, t("Not yet confirmed"), "neutral"),
										metric(t("Finalized"), state.summary.finalized, t("Platform usage confirmed"), "success"),
									]),
									state.requiresCompany
										? h(EdgeEmptyState, {
											title: t("Choose a Company"),
											description: t("Select a permitted Company before loading usage reconciliation records."),
										})
										: null,
									state.noBranchAccess
										? h(EdgeEmptyState, {
											title: t("No active Branch access"),
											description: t("Your current Company scope has no active permitted Branch for this review."),
										})
										: null,
									state.loading
										? h(EdgeLoadingState, { message: t("Loading usage reconciliation...") })
										: null,
									state.error
										? h(EdgeErrorState, {
											message: state.error,
											actionLabel: t("Try again"),
											onRetry: () => refresh(true),
										})
										: null,
									!state.loading && !state.error && !state.requiresCompany
									&& !state.noBranchAccess && !state.rows.length
										? h(EdgeEmptyState, {
											title: t("No usage exceptions in this scope"),
											description: t("Change the filters or refresh to check for new reconciliation work."),
										})
										: null,
									!state.loading && !state.error
										? h("div", { class: "retailedge-usage-list" }, state.rows.map(rowCard))
										: null,
									!state.loading && !state.error && state.hasMore
										? h("div", { class: "retailedge-usage-load-more" }, [
											actionButton(t("Load More"), "secondary", loadMore),
										])
										: null,
								],
							}
						)
					},
				);
			},
		});

		const app = edge.createEdgeApp(component);
		app.mount(page.main[0]);
		wrapper.retailedgeUsageReconciliationApp = app;
	};
})(window);
