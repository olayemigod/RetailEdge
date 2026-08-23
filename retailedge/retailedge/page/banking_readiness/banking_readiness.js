(function installRetailEdgeBankingReadinessPage(global) {
	"use strict";

	const PAGE_NAME = "banking-readiness";

	function runtime() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}

	function issueText(row) {
		const blocked = Array.isArray(row.issues) ? row.issues.map((item) => item.message).filter(Boolean) : [];
		const warnings = Array.isArray(row.warnings) ? row.warnings.map((item) => item.message).filter(Boolean) : [];
		return [...blocked, ...warnings].join(" · ");
	}

	function openNativeBankAccount(name) {
		if (!name) return;
		global.open(`/app/bank-account/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer");
	}

	frappe.pages[PAGE_NAME].on_page_load = function onPageLoad(wrapper) {
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Banking Setup & Readiness"),
			single_column: true,
		});
		const company = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
		});
		page.set_primary_action(__("Refresh"), () => refresh());
		page.add_inner_button(__("Bank Matching & Reconciliation"), () => frappe.set_route("bank-matching-reconciliation"));

		const edge = runtime();
		if (!edge?.Vue) {
			frappe.throw(__("EdgeSuite UI runtime is unavailable. Rebuild assets and clear cache."));
		}
		const { createApp, defineComponent, h, onMounted, reactive } = edge.Vue;
		const EdgePageLayout = edge.getComponent("EdgePageLayout");
		const EdgePageHeader = edge.getComponent("EdgePageHeader");
		const EdgeStatusBadge = edge.getComponent("EdgeStatusBadge");
		const EdgeLoadingState = edge.getComponent("EdgeLoadingState");
		const EdgeEmptyState = edge.getComponent("EdgeEmptyState");
		const EdgeErrorState = edge.getComponent("EdgeErrorState");

		const state = reactive({ loading: false, error: "", rows: [], summary: { ready: 0, warning: 0, blocked: 0 } });

		async function refresh() {
			state.loading = true;
			state.error = "";
			try {
				const response = await frappe.call({
					method: "retailedge.banking_readiness.get_banking_readiness",
					args: { company: company?.get_value?.() || "" },
				});
				const payload = response?.message || {};
				state.rows = payload.rows || [];
				state.summary = payload.summary || { ready: 0, warning: 0, blocked: 0 };
			} catch (error) {
				state.error = error?.message || __("Unable to evaluate banking readiness.");
			} finally {
				state.loading = false;
			}
		}

		if (company) company.df.change = refresh;

		const component = defineComponent({
			name: "RetailEdgeBankingReadiness",
			setup() {
				onMounted(refresh);
				function summaryCard(label, value, status) {
					return h("section", { class: "retailedge-readiness-summary-card" }, [
						h("span", { class: "retailedge-readiness-summary-label" }, label),
						h("strong", { class: "retailedge-readiness-summary-value" }, String(value || 0)),
						h(EdgeStatusBadge, { status }),
					]);
				}
				function rowCard(row) {
					return h("section", { class: "retailedge-readiness-card" }, [
						h("header", { class: "retailedge-readiness-card-header" }, [
							h("div", null, [
								h("strong", { class: "retailedge-readiness-bank-name" }, row.bank_account || __("Bank Account")),
								h("div", { class: "retailedge-readiness-bank-subtitle" }, [row.bank, row.company].filter(Boolean).join(" · ")),
							]),
							h(EdgeStatusBadge, { status: row.readiness || "Warning" }),
						]),
						h("div", { class: "retailedge-readiness-grid" }, [
							h("div", null, [h("span", null, __("GL Account")), h("strong", null, row.resolved_gl_account || __("Not configured"))]),
							h("div", null, [h("span", null, __("Branch Scope")), h("strong", null, row.branch_scope || __("Company Wide / Central"))]),
							h("div", null, [h("span", null, __("Mode of Payment")), h("strong", null, (row.mode_of_payments || []).join(", ") || __("No default"))]),
							h("div", null, [h("span", null, __("Reconciliation")), h("strong", null, row.can_reconcile ? __("Allowed") : __("Blocked"))]),
						]),
						issueText(row) ? h("p", { class: "retailedge-readiness-issues" }, issueText(row)) : null,
						h("div", { class: "retailedge-readiness-actions" }, [
							h("button", {
								type: "button",
								class: "edge-button edge-button--secondary",
								onClick: () => openNativeBankAccount(row.bank_account),
							}, __("Open ERPNext Bank Account")),
						]),
					]);
				}
				return () => h(EdgePageLayout, { class: "retailedge-banking-readiness" }, {
					default: () => [
						h(EdgePageHeader, {
							title: __("Banking Setup & Readiness"),
							description: __("Check whether ERPNext bank accounts are safely mapped for RetailEdge matching and reconciliation."),
						}),
						h("div", { class: "retailedge-readiness-summary" }, [
							summaryCard(__("Ready"), state.summary.ready, "Ready"),
							summaryCard(__("Warning"), state.summary.warning, "Warning"),
							summaryCard(__("Blocked"), state.summary.blocked, "Blocked"),
						]),
						state.loading ? h(EdgeLoadingState) : null,
						state.error ? h(EdgeErrorState, { message: state.error }) : null,
						!state.loading && !state.error && !state.rows.length ? h(EdgeEmptyState, { title: __("No Bank Accounts found") }) : null,
						...state.rows.map(rowCard),
					],
				});
			},
		});

		createApp(component).mount(page.main[0]);
	};
})(window);
