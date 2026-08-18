(function installRetailEdgeBankingWorkspace(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const QUEUES = ["To Match", "To Reconcile", "Exceptions", "Reconciled"];
	const DIRECTIONS = [
		{ label: "All", value: "All" },
		{ label: "Inflows", value: "Inflow" },
		{ label: "Outflows", value: "Outflow" },
	];

	function edgeRuntime() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}

	function formatMoney(value, currency) {
		try {
			return format_currency(value || 0, currency || undefined);
		} catch (_error) {
			return String(value || 0);
		}
	}

	function getFilters(page) {
		return {
			company: page.fields_dict?.company?.get_value?.() || "",
			bank_account: page.fields_dict?.bank_account?.get_value?.() || "",
			from_date: page.fields_dict?.from_date?.get_value?.() || "",
			to_date: page.fields_dict?.to_date?.get_value?.() || "",
			search: page.fields_dict?.search?.get_value?.() || "",
		};
	}

	function installPageFilters(page, refresh) {
		[
			{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
			{ fieldname: "bank_account", label: __("Bank Account"), fieldtype: "Link", options: "Bank Account" },
			{ fieldname: "from_date", label: __("From Date"), fieldtype: "Date" },
			{ fieldname: "to_date", label: __("To Date"), fieldtype: "Date" },
			{ fieldname: "search", label: __("Search"), fieldtype: "Data", placeholder: __("Narration, reference, party, document or amount") },
		].forEach((definition) => {
			page.add_field({ ...definition, change: refresh });
		});
	}

	function createWorkspaceComponent(runtime, page) {
		const { defineComponent, h, onMounted, reactive } = runtime.Vue;
		const EdgePageLayout = runtime.getComponent("EdgePageLayout");
		const EdgePageHeader = runtime.getComponent("EdgePageHeader");
		const EdgeActionBar = runtime.getComponent("EdgeActionBar");
		const EdgeStatusBadge = runtime.getComponent("EdgeStatusBadge");
		const EdgeLoadingState = runtime.getComponent("EdgeLoadingState");
		const EdgeEmptyState = runtime.getComponent("EdgeEmptyState");
		const EdgeErrorState = runtime.getComponent("EdgeErrorState");

		return defineComponent({
			name: "RetailEdgeBankMatchingReconciliation",
			setup() {
				const state = reactive({
					direction: "All",
					queue: "To Match",
					loading: false,
					error: "",
					rows: [],
					skippedCount: 0,
				});

				async function refresh() {
					state.loading = true;
					state.error = "";
					try {
						const response = await frappe.call({
							method: "retailedge.banking_workspace.get_banking_workspace_rows",
							args: {
								direction: state.direction,
								queue: state.queue,
								limit: 100,
								...getFilters(page),
							},
						});
						const payload = response?.message || {};
						state.rows = payload.rows || [];
						state.skippedCount = Number(payload.skipped_count || 0);
					} catch (error) {
						state.error = error?.message || __("Unable to load the banking queue.");
					} finally {
						state.loading = false;
					}
				}

				function routeToDocument(doctype, name) {
					if (doctype && name) frappe.set_route("Form", doctype, name);
				}

				function rowAction(row) {
					if (row.operational_status === "Ready to Reconcile") {
						return h(
							"button",
							{
								type: "button",
								class: "edge-button edge-button--primary",
								onClick: () => reconcile(row.match_name),
							},
							__("Reconcile"),
						);
					}
					if (row.operational_status === "Suggested Match" && row.match_name) {
						return h(
							"button",
							{
								type: "button",
								class: "edge-button edge-button--secondary",
								onClick: () => routeToDocument("RetailEdge Bank Transaction Match", row.match_name),
							},
							__("Review Suggestion"),
						);
					}
					if (!row.match_name && state.queue === "To Match") {
						return h(
							"button",
							{
								type: "button",
								class: "edge-button edge-button--primary",
								onClick: () => findCandidates(row.bank_transaction),
							},
							__("Find Match"),
						);
					}
					if (row.match_name) {
						return h(
							"button",
							{
								type: "button",
								class: "edge-button edge-button--secondary",
								onClick: () => routeToDocument("RetailEdge Bank Transaction Match", row.match_name),
							},
							__("Review"),
						);
					}
					return null;
				}

				async function findCandidates(bankTransaction) {
					const response = await frappe.call({
						method: "retailedge.bank_candidate_engine.get_direction_aware_bank_candidates",
						args: { bank_transaction_name: bankTransaction, limit: 20 },
						freeze: true,
						freeze_message: __("Finding accounting matches..."),
					});
					showCandidateDialog(bankTransaction, response?.message || {});
				}

				function candidateReason(row) {
					const reasons = Array.isArray(row.reasons) ? row.reasons.filter(Boolean) : [];
					const fuzzy = row.fuzzy_note || row.fuzzy_evidence?.reason;
					return [...reasons, fuzzy].filter(Boolean).join(" · ");
				}

				function showCandidateDialog(bankTransaction, payload) {
					const candidates = payload.candidates || [];
					if (!candidates.length) {
						frappe.msgprint(__("No safe accounting candidate was found for this bank transaction."));
						return;
					}
					const dialog = new frappe.ui.Dialog({
						title: __("Matching Candidates for {0}", [bankTransaction]),
						fields: [
							{
								fieldname: "candidate",
								label: __("Candidate"),
								fieldtype: "Select",
								options: candidates.map((row, index) => ({
									label: `${row.document_type} ${row.document_name} · ${row.transaction_category || row.candidate_category || ""} · ${formatMoney(row.candidate_amount, row.currency)} · ${__("Hard")}: ${row.hard_match_score ?? row.match_score ?? 0} · ${__("Fuzzy")}: ${row.fuzzy_score ?? 0}`,
									value: String(index),
								})),
								reqd: 1,
							},
							{ fieldname: "evidence", label: __("Why this matches"), fieldtype: "Small Text", read_only: 1 },
						],
						primary_action_label: __("Review Match"),
						primary_action: async (values) => {
							const row = candidates[Number(values.candidate || 0)];
							if (!row || Number(row.review_supported) === 0) {
								frappe.msgprint(row?.review_block_reason || __("This candidate cannot enter review yet."));
								return;
							}
							const response = await frappe.call({
								method: "retailedge.bank_candidate_engine.prepare_direction_aware_bank_candidate",
								args: {
									bank_transaction_name: bankTransaction,
									document_type: row.document_type,
									document_name: row.document_name,
								},
								freeze: true,
								freeze_message: __("Revalidating candidate..."),
							});
							const result = response?.message || {};
							if (!result.match_name) {
								frappe.msgprint(result.message || __("This candidate cannot enter review yet."));
								return;
							}
							dialog.hide();
							routeToDocument("RetailEdge Bank Transaction Match", result.match_name);
						},
					});

					function syncEvidence() {
						const row = candidates[Number(dialog.get_value("candidate") || 0)];
						dialog.set_value("evidence", row ? candidateReason(row) : "");
					}
					dialog.fields_dict.candidate.df.change = syncEvidence;
					dialog.set_value("candidate", "0");
					syncEvidence();
					dialog.show();
				}

				function reconcile(matchName) {
					frappe.confirm(
						__("This match is already confirmed. Reconcile it through ERPNext after a fresh safety check?"),
						async () => {
							const response = await frappe.call({
								method: "retailedge.banking_operations.match_and_reconcile",
								args: { match_name: matchName, confirm_match: 0, confirm_reconciliation: 1 },
								freeze: true,
								freeze_message: __("Reconciling through ERPNext..."),
							});
							const result = response?.message || {};
							frappe.show_alert({
								message: result.message || result.status || __("Reconciliation processed."),
								indicator: result.status === "Executed" ? "green" : "orange",
							});
							refresh();
						},
					);
				}

				function headerCell(label) {
					return h("th", { scope: "col" }, __(label));
				}

				function renderTable() {
					return h("div", { class: "edge-table-wrap retailedge-bank-table-wrap" }, [
						h("table", { class: "edge-table retailedge-bank-table" }, [
							h("thead", [
								h("tr", [
									headerCell("Date"),
									headerCell("Bank Account"),
									headerCell("Narration / Reference"),
									headerCell("Direction"),
									headerCell("Category"),
									headerCell("Bank Amount"),
									headerCell("Candidate"),
									headerCell("Candidate Amount"),
									headerCell("Difference"),
									headerCell("Status"),
									headerCell("Action"),
								]),
							]),
							h("tbody", state.rows.map((row) =>
								h("tr", { key: row.match_name || row.bank_transaction }, [
									h("td", row.transaction_date || ""),
									h("td", row.bank_account || ""),
									h("td", [
										h("button", {
											type: "button",
											class: "edge-link-button",
											onClick: () => routeToDocument("Bank Transaction", row.bank_transaction),
										}, row.description || row.reference || row.bank_transaction || ""),
										row.reference && row.description ? h("small", { class: "text-muted d-block" }, row.reference) : null,
									]),
									h("td", row.direction || ""),
									h("td", row.transaction_category || ""),
									h("td", { class: "text-right" }, formatMoney(row.bank_amount, row.currency)),
									h("td", row.suggested_document
										? h("button", {
											type: "button",
											class: "edge-link-button",
											onClick: () => routeToDocument(row.suggested_document_type, row.suggested_document),
										}, `${row.suggested_document_type || ""} ${row.suggested_document}`)
										: "—"),
									h("td", { class: "text-right" }, row.candidate_amount == null ? "—" : formatMoney(row.candidate_amount, row.currency)),
									h("td", { class: "text-right" }, row.amount_difference == null ? "—" : formatMoney(row.amount_difference, row.currency)),
									h("td", [h(EdgeStatusBadge, { label: row.operational_status || "", status: row.operational_status || "" })]),
									h("td", [rowAction(row)]),
								]),
							)),
						]),
					]);
				}

				onMounted(refresh);
				page.set_primary_action(__("Refresh"), refresh);
				installPageFilters(page, refresh);
				global.retailedgeBankingWorkspaceRefresh = refresh;

				return () => h(EdgePageLayout, null, {
					header: () => h(EdgePageHeader, {
						eyebrow: __("RetailEdge Banking"),
						title: __("Bank Matching & Reconciliation"),
						subtitle: __("Match bank inflows and outflows to valid ERPNext accounting events, then reconcile through ERPNext Banking."),
					}),
					default: () => [
						h(EdgeActionBar, { label: __("Direction and workflow queue") }, {
							actions: () => [
								...DIRECTIONS.map((item) => h("button", {
									type: "button",
									class: ["edge-button", state.direction === item.value ? "edge-button--primary" : "edge-button--secondary"],
									onClick: () => { state.direction = item.value; refresh(); },
								}, __(item.label))),
								...QUEUES.map((queue) => h("button", {
									type: "button",
									class: ["edge-button", state.queue === queue ? "edge-button--primary" : "edge-button--secondary"],
									onClick: () => { state.queue = queue; refresh(); },
								}, __(queue))),
							],
						}),
						state.loading ? h(EdgeLoadingState, { message: __("Loading banking queue...") }) : null,
						state.error ? h(EdgeErrorState, { message: state.error, actionLabel: __("Try again"), onRetry: refresh }) : null,
						!state.loading && !state.error && !state.rows.length ? h(EdgeEmptyState, {
							title: __("No transactions in this queue"),
							description: __("Adjust the direction or filters, or refresh after new bank transactions are imported."),
						}) : null,
						!state.loading && !state.error && state.rows.length ? renderTable() : null,
						state.skippedCount ? h("p", { class: "text-muted small" }, __("{0} row(s) were skipped because their banking context could not be resolved safely.", [state.skippedCount])) : null,
					],
				});
			},
		});
	}

	function boot(wrapper) {
		const runtime = edgeRuntime();
		if (!runtime?.createEdgeApp || !runtime?.Vue) {
			frappe.throw(__("EdgeSuite UI runtime is required for Bank Matching & Reconciliation."));
		}
		const page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("Bank Matching & Reconciliation"),
			single_column: true,
		});
		page.add_menu_item(__("Open Matching Report"), () => frappe.set_route("query-report", "RetailEdge Bank Transaction Matching"));
		page.add_menu_item(__("Open Reconciliation Readiness"), () => frappe.set_route("query-report", "RetailEdge Bank Match Reconciliation Readiness"));
		const component = createWorkspaceComponent(runtime, page);
		const app = runtime.createEdgeApp(component);
		app.mount(page.main[0]);
		wrapper.retailedgeBankingApp = app;
	}

	global.retailedgeBootBankingWorkspace = boot;
	global.retailedgeBankingWorkspacePageName = PAGE_NAME;
})(window);
