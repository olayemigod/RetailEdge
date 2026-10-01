(function (global) {
	"use strict";

	const PAGE = "usage-reconciliation";
	const STATUSES = ["", "Needs Review", "Pending Finalize", "Finalized"];

	function edge() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}
	function t(value) {
		return typeof global.__ === "function" ? global.__(value) : value;
	}
	function clean(value) {
		return String(value ?? "").trim();
	}
	async function linkSearch(doctype, query, filters = {}) {
		const response = await frappe.call({
			method: "frappe.desk.search.search_link",
			args: { doctype, txt: clean(query), filters, page_length: 20 },
		});
		return (response.message || []).map((row) => ({
			value: row.value || row.name,
			label: row.label || row.value || row.name,
			description: row.description || "",
		}));
	}
	function button(h, label, variant, onClick, disabled = false) {
		return h("button", {
			type: "button",
			class: ["edge-button", "edge-button--" + variant],
			disabled,
			onClick,
		}, label);
	}
	function sourceRoute(row) {
		if (row.source_doctype && row.source_name) {
			frappe.set_route("Form", row.source_doctype, row.source_name);
		}
	}

	frappe.pages[PAGE].on_page_load = function (wrapper) {
		const ui = edge();
		if (!ui?.createEdgeApp || !ui?.Vue) {
			frappe.throw(t("Required interface components are unavailable."));
		}

		const names = [
			"EdgePageLayout", "EdgePageHeader", "EdgeFilterBar", "EdgeLinkField",
			"EdgeDropdown", "EdgeStatCard", "EdgeStatusBadge", "EdgeLoadingState",
			"EdgeEmptyState", "EdgeErrorState",
		];
		const components = Object.fromEntries(names.map((name) => [name, ui.getComponent(name)]));
		if (names.some((name) => !components[name])) {
			frappe.throw(t("Required Usage Reconciliation components are unavailable."));
		}

		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: t("Usage Reconciliation"),
			single_column: true,
		});
		const { defineComponent, h, onMounted, reactive } = ui.Vue;

		const component = defineComponent({
			name: "RetailEdgeUsageReconciliation",
			setup() {
				const state = reactive({
					loading: false,
					error: "",
					rows: [],
					summary: {},
					truncated: false,
					status: "",
					source: "",
					company: "",
					branch: "",
					retrying: "",
				});

				async function refresh() {
					state.loading = true;
					state.error = "";
					try {
						const response = await frappe.call({
							method: "retailedge.coreedge_sales_quota.get_sales_quota_review",
							args: {
								filters: {
									status: state.status,
									source_doctype: state.source,
									company: state.company,
									branch: state.branch,
								},
								limit: 200,
							},
						});
						const data = response.message || {};
						state.rows = data.rows || [];
						state.summary = data.summary || {};
						state.truncated = Boolean(data.truncated);
					} catch (error) {
						state.error = error?.message || t("Unable to load Usage Reconciliation.");
					} finally {
						state.loading = false;
					}
				}

				async function retry(row) {
					if (!row.can_retry || state.retrying) return;
					state.retrying = row.name;
					try {
						const response = await frappe.call({
							method: "retailedge.coreedge_sales_quota.retry_sales_quota_review",
							args: { operation_name: row.name },
						});
						const status = response.message?.status || row.status;
						frappe.show_alert({
							message: status === "Finalized"
								? t("Usage reconciliation finalized.")
								: t("Retry completed; review the current status."),
							indicator: status === "Finalized" ? "green" : "orange",
						});
						await refresh();
					} catch (error) {
						frappe.msgprint({
							title: t("Usage Reconciliation"),
							indicator: "red",
							message: error?.message || t("Unable to retry finalization."),
						});
					} finally {
						state.retrying = "";
					}
				}

				function clearFilters() {
					state.status = "";
					state.source = "";
					state.company = "";
					state.branch = "";
					refresh();
				}

				function metric(label, key, helper, tone) {
					return h(components.EdgeStatCard, {
						label: t(label),
						value: Number(state.summary[key] || 0),
						helper: t(helper),
						tone,
					});
				}

				function field(label, value) {
					return h("div", { class: "p-2" }, [
						h("small", { class: "text-muted d-block" }, t(label)),
						h("strong", value || "—"),
					]);
				}

				function card(row) {
					const source = [row.source_doctype, row.source_name].filter(Boolean).join(" ");
					const guidance = row.requires_manual_reconciliation
						? t("No CoreEdge reservation exists. Manual commercial reconciliation is required.")
						: row.can_retry
							? t("A reservation exists. Retry safely asks CoreEdge for its authoritative state.")
							: t("No reconciliation action is currently required.");

					return h("section", { class: "card mb-3" }, [
						h("div", { class: "card-body" }, [
							h("div", { class: "d-flex justify-content-between align-items-start gap-3" }, [
								h("div", null, [
									h("h4", { class: "mb-1" }, source || t("Sales transaction")),
									h("div", { class: "text-muted" },
										[row.company, row.branch].filter(Boolean).join(" · ") || t("No additional context")),
								]),
								h(components.EdgeStatusBadge, { status: row.status || "Needs Review" }),
							]),
							h("div", { class: "row mt-3" }, [
								h("div", { class: "col-md-3" }, [field("Entitlement", row.entitlement_key)]),
								h("div", { class: "col-md-3" }, [field("Reservation", row.reservation_reference || t("Not reserved"))]),
								h("div", { class: "col-md-3" }, [field("Attempts", String(row.attempt_count || 0))]),
								h("div", { class: "col-md-3" }, [field("Reason", row.reason_code)]),
							]),
							(row.last_error || row.remote_message)
								? h("div", { class: "alert alert-warning mt-3 mb-2" }, row.last_error || row.remote_message)
								: null,
							h("p", { class: "text-muted mb-3" }, guidance),
							h("div", { class: "d-flex gap-2 flex-wrap" }, [
								button(h, t("Open Source"), "secondary", () => sourceRoute(row),
									!row.source_doctype || !row.source_name),
								row.can_retry
									? button(h,
										state.retrying === row.name ? t("Retrying…") : t("Retry Finalization"),
										"primary",
										() => retry(row),
										Boolean(state.retrying))
									: null,
							]),
						]),
					]);
				}

				onMounted(refresh);

				return () => h(components.EdgePageLayout, null, {
					header: () => h(components.EdgePageHeader, {
						eyebrow: t("Management / Review"),
						title: t("Usage Reconciliation"),
						subtitle: t("Review sales-usage finalization without changing submitted ERPNext transactions."),
					}, {
						actions: () => [button(h, t("Refresh"), "primary", refresh, state.loading)],
					}),
					filters: () => h(components.EdgeFilterBar, { title: t("Filters") }, {
						default: () => [
							h(components.EdgeDropdown, {
								label: t("Status"),
								modelValue: state.status,
								options: STATUSES.map((value) => ({
									value,
									label: value ? t(value) : t("All States"),
								})),
								"onUpdate:modelValue": (value) => { state.status = value || ""; refresh(); },
							}),
							h(components.EdgeDropdown, {
								label: t("Source"),
								modelValue: state.source,
								options: [
									{ value: "", label: t("All Sales Documents") },
									{ value: "Sales Invoice", label: t("Sales Invoice") },
									{ value: "POS Invoice", label: t("POS Invoice") },
								],
								"onUpdate:modelValue": (value) => { state.source = value || ""; refresh(); },
							}),
							h(components.EdgeLinkField, {
								label: t("Company"),
								modelValue: state.company,
								searcher: (query) => linkSearch("Company", query),
								"onUpdate:modelValue": (value) => {
									state.company = value || "";
									state.branch = "";
									refresh();
								},
							}),
							h(components.EdgeLinkField, {
								label: t("Branch"),
								modelValue: state.branch,
								searcher: (query) => linkSearch("Branch", query,
									state.company ? { company: state.company } : {}),
								"onUpdate:modelValue": (value) => { state.branch = value || ""; refresh(); },
							}),
						],
						actions: () => (state.status || state.source || state.company || state.branch)
							? [button(h, t("Clear Filters"), "secondary", clearFilters)]
							: [],
					}),
					default: () => [
						h("div", { class: "row g-3 mb-4" }, [
							h("div", { class: "col-md-3" }, [metric("Needs Review", "needs_review", "Operator attention required", "danger")]),
							h("div", { class: "col-md-3" }, [metric("Pending Finalize", "pending_finalize", "Retry may be available", "warning")]),
							h("div", { class: "col-md-3" }, [metric("Finalized", "finalized", "CoreEdge usage confirmed", "success")]),
							h("div", { class: "col-md-3" }, [metric("Rows", "total", "Current filter result", "neutral")]),
						]),
						state.truncated
							? h("div", { class: "alert alert-warning" },
								t("Results are truncated. Narrow the filters before taking review action."))
							: null,
						state.loading ? h(components.EdgeLoadingState, { message: t("Loading usage reconciliation…") }) : null,
						state.error ? h(components.EdgeErrorState, {
							message: state.error,
							actionLabel: t("Try again"),
							onRetry: refresh,
						}) : null,
						!state.loading && !state.error && !state.rows.length
							? h(components.EdgeEmptyState, {
								title: t("No usage reconciliation rows"),
								description: t("No quota operations match the current filters."),
							})
							: null,
						!state.loading && !state.error
							? h("div", null, state.rows.map(card))
							: null,
					],
				});
			},
		});

		ui.createEdgeApp(component).mount(page.main[0]);
	};
})(window);
