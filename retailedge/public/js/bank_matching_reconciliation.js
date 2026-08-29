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
			branch: page.fields_dict?.branch?.get_value?.() || "",
			bank_account: page.fields_dict?.bank_account?.get_value?.() || "",
			from_date: page.fields_dict?.from_date?.get_value?.() || "",
			to_date: page.fields_dict?.to_date?.get_value?.() || "",
			search: page.fields_dict?.search?.get_value?.() || "",
		};
	}

	function installPageFilters(page, refresh) {
		const company = page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			change: () => {
				page.fields_dict?.branch?.set_value?.("");
				page.fields_dict?.bank_account?.set_value?.("");
				refresh();
			},
		});
		const branch = page.add_field({
			fieldname: "branch",
			label: __("Branch"),
			fieldtype: "Link",
			options: "Branch",
			change: refresh,
		});
		const bankAccount = page.add_field({
			fieldname: "bank_account",
			label: __("Bank Account"),
			fieldtype: "Link",
			options: "Bank Account",
			change: refresh,
		});
		page.add_field({ fieldname: "from_date", label: __("From Date"), fieldtype: "Date", change: refresh });
		page.add_field({ fieldname: "to_date", label: __("To Date"), fieldtype: "Date", change: refresh });
		page.add_field({
			fieldname: "search",
			label: __("Search"),
			fieldtype: "Data",
			placeholder: __("Narration, reference, party, document or amount"),
			change: refresh,
		});

		const companyFilter = () => {
			const selectedCompany = company?.get_value?.() || "";
			return selectedCompany ? { filters: { company: selectedCompany } } : {};
		};
		if (branch) branch.get_query = companyFilter;
		if (bankAccount) bankAccount.get_query = companyFilter;
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
						return h("button", {
							type: "button",
							class: "edge-button edge-button--primary",
							onClick: () => reconcile(row.match_name),
						}, __("Reconcile"));
					}
					if (row.operational_status === "Awaiting Approval" && row.match_name) {
						return h("button", {
							type: "button",
							class: "edge-button edge-button--secondary",
							onClick: () => showReviewMatchDialog(row.match_name),
						}, row.approval_can_approve ? __("Approve") : __("Review Approval"));
					}
					if (row.operational_status === "Suggested Match" && row.match_name) {
						return h("button", {
							type: "button",
							class: "edge-button edge-button--secondary",
							onClick: () => showReviewMatchDialog(row.match_name),
						}, __("Review Suggestion"));
					}
					if (!row.match_name && state.queue === "To Match") {
						return h("button", {
							type: "button",
							class: "edge-button edge-button--primary",
							onClick: () => findCandidates(row.bank_transaction),
						}, __("Find Match"));
					}
					if (row.match_name) {
						return h("button", {
							type: "button",
							class: "edge-button edge-button--secondary",
							onClick: () => showReviewMatchDialog(row.match_name),
						}, __("Review"));
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
					return reasons.join(" · ");
				}

				function fuzzyReason(row) {
					return row?.fuzzy_note || row?.fuzzy_evidence?.reason || __("No supplemental fuzzy evidence recorded.");
				}

				function candidateOption(row) {
					return `${row.document_type} ${row.document_name} · ${row.transaction_category || row.candidate_category || ""} · ${formatMoney(row.candidate_amount, row.currency)} · ${__("Hard")}: ${row.hard_match_score ?? row.match_score ?? 0} · ${__("Fuzzy")}: ${row.fuzzy_score ?? 0}`;
				}

				function selectedCandidate(candidates, optionLabels, value) {
					const index = optionLabels.indexOf(String(value || ""));
					return index >= 0 ? candidates[index] : null;
				}

				function showCandidateDialog(bankTransaction, payload) {
					const candidates = payload.candidates || [];
					if (!candidates.length) {
						frappe.msgprint(__("No safe accounting candidate was found for this bank transaction."));
						return;
					}
					const optionLabels = candidates.map(candidateOption);
					const dialog = new frappe.ui.Dialog({
						title: __("Matching Candidates for {0}", [bankTransaction]),
						fields: [
							{
								fieldname: "candidate",
								label: __("Candidate"),
								fieldtype: "Select",
								options: optionLabels.join("\n"),
								reqd: 1,
							},
							{
								fieldname: "evidence",
								label: __("Accounting evidence"),
								fieldtype: "Small Text",
								read_only: 1,
							},
							{
								fieldname: "fuzzy_evidence",
								label: __("Supplemental fuzzy evidence"),
								fieldtype: "Small Text",
								read_only: 1,
							},
						],
						primary_action_label: __("Review Match"),
						primary_action: async (values) => {
							const row = selectedCandidate(candidates, optionLabels, values.candidate);
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
							showReviewMatchDialog(result.match_name, row);
						},
					});

					function syncEvidence() {
						const row = selectedCandidate(candidates, optionLabels, dialog.get_value("candidate"));
						dialog.set_value("evidence", row ? candidateReason(row) : "");
						dialog.set_value("fuzzy_evidence", row ? fuzzyReason(row) : "");
					}
					dialog.fields_dict.candidate.df.change = syncEvidence;
					dialog.set_value("candidate", optionLabels[0]);
					syncEvidence();
					dialog.show();
				}

				async function getMatchDocument(matchName) {
					const response = await frappe.call({
						method: "frappe.client.get",
						args: { doctype: "RetailEdge Bank Transaction Match", name: matchName },
					});
					return response?.message || {};
				}

				async function getApprovalState(matchName) {
					const response = await frappe.call({
						method: "retailedge.reconciliation_approval.get_reconciliation_approval_state",
						args: { match_name: matchName },
					});
					return response?.message || {};
				}

				async function applyReviewDecision(method, matchName, decisionNote, dialog, successMessage) {
					const response = await frappe.call({
						method,
						args: { match_name: matchName, decision_note: decisionNote || "" },
						freeze: true,
						freeze_message: __("Applying review decision..."),
					});
					const result = response?.message || {};
					dialog.hide();
					frappe.show_alert({ message: result.message || successMessage, indicator: "green" });
					refresh();
				}

				async function applyApprovalAction(method, matchName, approvalNote, dialog, indicator = "green") {
					const response = await frappe.call({
						method,
						args: { match_name: matchName, approval_note: approvalNote || "" },
						freeze: true,
						freeze_message: __("Updating reconciliation approval..."),
					});
					const result = response?.message || {};
					dialog.hide();
					frappe.show_alert({
						message: result.message || __("Reconciliation approval updated."),
						indicator,
					});
					refresh();
				}

				async function showReviewMatchDialog(matchName, candidateSnapshot = null) {
					const [doc, approval] = await Promise.all([
						getMatchDocument(matchName),
						getApprovalState(matchName),
					]);
					const canDecide = ["Suggested", "Reopened", "Needs Review"].includes(doc.decision_status || "Suggested");
					const confirmed = doc.decision_status === "Confirmed";
					const approvalRequired = Boolean(approval.required);
					const approvalSatisfied = Boolean(approval.is_satisfied);
					const canApprove = Boolean(approval.can_approve);
					const canRequestApproval = confirmed && approvalRequired && !approvalSatisfied && !canApprove;
					const dialog = new frappe.ui.Dialog({
						title: __("Review Match · {0}", [matchName]),
						size: "extra-large",
						fields: [
							{ fieldname: "bank_section", fieldtype: "Section Break", label: __("Bank Transaction") },
							{ fieldname: "bank_direction", label: __("Direction"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "bank_amount", label: __("Bank Amount"), fieldtype: "Currency", read_only: 1 },
							{ fieldname: "transaction_date", label: __("Transaction Date"), fieldtype: "Date", read_only: 1 },
							{ fieldname: "bank_account", label: __("Bank Account"), fieldtype: "Link", options: "Bank Account", read_only: 1 },
							{ fieldname: "bank_reference", label: __("Reference"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "bank_narration", label: __("Narration"), fieldtype: "Small Text", read_only: 1 },
							{ fieldname: "candidate_column", fieldtype: "Column Break" },
							{ fieldname: "transaction_category", label: __("Category"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "suggested_document_type", label: __("Document Type"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "suggested_document", label: __("Candidate Document"), fieldtype: "Dynamic Link", options: "suggested_document_type", read_only: 1 },
							{ fieldname: "candidate_amount", label: __("Candidate Amount"), fieldtype: "Currency", read_only: 1 },
							{ fieldname: "amount_difference", label: __("Difference"), fieldtype: "Currency", read_only: 1 },
							{ fieldname: "party", label: __("Party"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "payment_event_source", label: __("Payment Evidence"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "payment_mode", label: __("Mode of Payment"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "evidence_section", fieldtype: "Section Break", label: __("Why this matches") },
							{ fieldname: "match_confidence", label: __("Match Confidence"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "match_score", label: __("Accounting / Hard Score"), fieldtype: "Int", read_only: 1 },
							{ fieldname: "risk_level", label: __("Risk"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "accounting_evidence", label: __("Accounting Evidence"), fieldtype: "Small Text", read_only: 1 },
							{ fieldname: "fuzzy_review_evidence", label: __("Supplemental Fuzzy Evidence"), fieldtype: "Small Text", read_only: 1 },
							{ fieldname: "approval_section", fieldtype: "Section Break", label: __("Reconciliation Approval"), hidden: !confirmed },
							{ fieldname: "approval_status", label: __("Approval Status"), fieldtype: "Data", read_only: 1, hidden: !confirmed },
							{ fieldname: "approval_reason", label: __("Approval Guidance"), fieldtype: "Small Text", read_only: 1, hidden: !confirmed },
							{ fieldname: "approval_actor", label: __("Approved By"), fieldtype: "Data", read_only: 1, hidden: !confirmed },
							{ fieldname: "approval_note", label: __("Approval Note"), fieldtype: "Small Text", read_only: !confirmed || approvalSatisfied },
							{ fieldname: "request_approval", label: __("Request Approval"), fieldtype: "Button", hidden: !canRequestApproval },
							{ fieldname: "approve_reconciliation", label: __("Approve Reconciliation"), fieldtype: "Button", hidden: !canApprove },
							{ fieldname: "decline_reconciliation", label: __("Decline Approval"), fieldtype: "Button", hidden: !canApprove },
							{ fieldname: "decision_section", fieldtype: "Section Break", label: __("Review Decision") },
							{ fieldname: "decision_status", label: __("Current Status"), fieldtype: "Data", read_only: 1 },
							{ fieldname: "decision_note", label: __("Decision Note"), fieldtype: "Small Text", read_only: !canDecide },
							{ fieldname: "mark_needs_review", label: __("Keep for Review"), fieldtype: "Button", hidden: !canDecide },
							{ fieldname: "open_audit_record", label: __("Open Audit Record"), fieldtype: "Button" },
							{ fieldname: "open_bank_transaction", label: __("Open Bank Transaction"), fieldtype: "Button" },
							{ fieldname: "open_candidate_document", label: __("Open Candidate Document"), fieldtype: "Button" },
						],
						primary_action_label: canDecide ? __("Confirm Match") : __("Close"),
						primary_action: async (values) => {
							if (!canDecide) {
								dialog.hide();
								return;
							}
							await applyReviewDecision(
								"retailedge.api.confirm_bank_transaction_match",
								matchName,
								values.decision_note,
								dialog,
								__("Match confirmed. Reconciliation is still required."),
							);
						},
						secondary_action_label: canDecide ? __("Reject Match") : null,
						secondary_action: canDecide
							? async () => {
									await applyReviewDecision(
										"retailedge.api.reject_bank_transaction_match",
										matchName,
										dialog.get_value("decision_note"),
										dialog,
										__("Match rejected."),
									);
								}
							: null,
					});

					const category = candidateSnapshot?.transaction_category || candidateSnapshot?.candidate_category || "";
					dialog.set_values({
						bank_direction: doc.bank_direction || candidateSnapshot?.direction || "",
						bank_amount: doc.bank_amount,
						transaction_date: doc.transaction_date,
						bank_account: doc.bank_account,
						bank_reference: doc.bank_reference,
						bank_narration: doc.bank_narration,
						transaction_category: category,
						suggested_document_type: doc.suggested_document_type,
						suggested_document: doc.suggested_document,
						candidate_amount: doc.candidate_amount,
						amount_difference: doc.amount_difference,
						party: doc.customer || doc.party || candidateSnapshot?.party || "",
						payment_event_source: doc.payment_event_source || candidateSnapshot?.payment_event_source || "",
						payment_mode: doc.payment_mode || candidateSnapshot?.payment_mode || "",
						match_confidence: doc.match_confidence,
						match_score: doc.match_score,
						risk_level: doc.risk_level,
						accounting_evidence: doc.match_reason_summary || doc.match_reason || candidateReason(candidateSnapshot || {}),
						fuzzy_review_evidence: candidateSnapshot ? fuzzyReason(candidateSnapshot) : __("Fuzzy evidence is supplemental only. Open the audit record for persisted detail."),
						approval_status: approval.status || "",
						approval_reason: approval.reason || "",
						approval_actor: approval.approved_by || "",
						approval_note: approval.approval_note || "",
						decision_status: doc.decision_status || "Suggested",
						decision_note: doc.decision_note || "",
					});

					dialog.fields_dict.mark_needs_review.df.click = async () => {
						await applyReviewDecision(
							"retailedge.api.mark_bank_transaction_match_needs_review",
							matchName,
							dialog.get_value("decision_note"),
							dialog,
							__("Match kept for review."),
						);
					};
					if (dialog.fields_dict.request_approval) {
						dialog.fields_dict.request_approval.df.click = async () => {
							await applyApprovalAction(
								"retailedge.reconciliation_approval.request_reconciliation_approval",
								matchName,
								dialog.get_value("approval_note"),
								dialog,
							);
						};
					}
					if (dialog.fields_dict.approve_reconciliation) {
						dialog.fields_dict.approve_reconciliation.df.click = async () => {
							await applyApprovalAction(
								"retailedge.reconciliation_approval.approve_reconciliation_for_match",
								matchName,
								dialog.get_value("approval_note"),
								dialog,
							);
						};
					}
					if (dialog.fields_dict.decline_reconciliation) {
						dialog.fields_dict.decline_reconciliation.df.click = async () => {
							await applyApprovalAction(
								"retailedge.reconciliation_approval.decline_reconciliation_for_match",
								matchName,
								dialog.get_value("approval_note"),
								dialog,
								"orange",
							);
						};
					}
					dialog.fields_dict.open_audit_record.df.click = () => {
						dialog.hide();
						routeToDocument("RetailEdge Bank Transaction Match", matchName);
					};
					dialog.fields_dict.open_bank_transaction.df.click = () => routeToDocument("Bank Transaction", doc.bank_transaction);
					dialog.fields_dict.open_candidate_document.df.click = () => routeToDocument(doc.suggested_document_type, doc.suggested_document);
					dialog.show();
				}

				function reconcile(matchName) {
					frappe.confirm(
						__("This match is confirmed and approved. Reconcile it through ERPNext after a fresh safety check?"),
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

				function headerCell(label, className) {
					return h("th", { scope: "col", class: className || "" }, __(label));
				}

				function renderNarration(row) {
					const narration = row.description || row.reference || row.bank_transaction || "";
					return h("div", { class: "retailedge-bank-transaction-cell" }, [
						h("button", {
							type: "button",
							class: "edge-link-button retailedge-bank-narration",
							title: narration,
							onClick: () => routeToDocument("Bank Transaction", row.bank_transaction),
						}, narration),
						h("small", { class: "text-muted retailedge-bank-meta" },
							[row.bank_account, row.reference, row.transaction_category].filter(Boolean).join(" · "),
						),
					]);
				}

				function renderCandidate(row) {
					if (!row.suggested_document) return "—";
					const detail = [
						row.candidate_amount == null ? null : formatMoney(row.candidate_amount, row.currency),
						row.amount_difference == null ? null : `${__("Difference")}: ${formatMoney(row.amount_difference, row.currency)}`,
					].filter(Boolean).join(" · ");
					return h("div", { class: "retailedge-bank-candidate-cell" }, [
						h("button", {
							type: "button",
							class: "edge-link-button",
							onClick: () => routeToDocument(row.suggested_document_type, row.suggested_document),
						}, `${row.suggested_document_type || ""} ${row.suggested_document}`),
						detail ? h("small", { class: "text-muted retailedge-bank-meta" }, detail) : null,
					]);
				}

				function renderTable() {
					return h("div", { class: "edge-table-wrap retailedge-bank-table-wrap" }, [
						h("table", { class: "edge-table retailedge-bank-table" }, [
							h("thead", [
								h("tr", [
									headerCell("Date", "retailedge-col-date"),
									headerCell("Bank Transaction", "retailedge-col-transaction"),
									headerCell("Direction", "retailedge-col-direction"),
									headerCell("Bank Amount", "retailedge-col-amount text-right"),
									headerCell("Candidate", "retailedge-col-candidate"),
									headerCell("Status", "retailedge-col-status"),
									headerCell("Action", "retailedge-col-action"),
								]),
							]),
							h(
								"tbody",
								state.rows.map((row) =>
									h("tr", { key: row.match_name || row.bank_transaction }, [
										h("td", { class: "retailedge-col-date" }, row.transaction_date || ""),
										h("td", { class: "retailedge-col-transaction" }, [renderNarration(row)]),
										h("td", { class: "retailedge-col-direction" }, row.direction || ""),
										h("td", { class: "retailedge-col-amount text-right" }, formatMoney(row.bank_amount, row.currency)),
										h("td", { class: "retailedge-col-candidate" }, [renderCandidate(row)]),
										h("td", { class: "retailedge-col-status" }, [
											h(EdgeStatusBadge, {
												label: row.operational_status || "",
												status: row.operational_status || "",
											}),
										]),
										h("td", { class: "retailedge-col-action" }, [rowAction(row)]),
									]),
								),
							),
						]),
					]);
				}

				onMounted(refresh);
				page.set_primary_action(__("Refresh"), refresh);
				installPageFilters(page, refresh);
				global.retailedgeBankingWorkspaceRefresh = refresh;

				function selectorBar(label, values, currentValue, onSelect) {
					return h(
						EdgeActionBar,
						{ label: __(label) },
						{
							actions: () => values.map((item) => {
								const value = typeof item === "string" ? item : item.value;
								const text = typeof item === "string" ? item : item.label;
								return h("button", {
									type: "button",
									class: [
										"edge-button",
										currentValue === value ? "edge-button--primary" : "edge-button--secondary",
									],
									onClick: () => onSelect(value),
								}, __(text));
							}),
						},
					);
				}

				return () =>
					h(EdgePageLayout, null, {
						header: () =>
							h(EdgePageHeader, {
								eyebrow: __("RetailEdge Banking"),
								title: __("Bank Matching & Reconciliation"),
								subtitle: __(
									"Match bank inflows and outflows to valid ERPNext accounting events, then reconcile through ERPNext Banking.",
								),
							}),
						default: () => [
							selectorBar("Direction", DIRECTIONS, state.direction, (value) => {
								state.direction = value;
								refresh();
							}),
							selectorBar("Workflow Status", QUEUES, state.queue, (value) => {
								state.queue = value;
								refresh();
							}),
							state.loading
								? h(EdgeLoadingState, { message: __("Loading banking queue...") })
								: null,
							state.error
								? h(EdgeErrorState, {
										message: state.error,
										actionLabel: __("Try again"),
										onRetry: refresh,
									})
								: null,
							!state.loading && !state.error && !state.rows.length
								? h(EdgeEmptyState, {
										title: __("No transactions in this queue"),
										description: __(
											"Adjust the direction or filters, or refresh after new bank transactions are imported.",
										),
									})
								: null,
							!state.loading && !state.error && state.rows.length ? renderTable() : null,
							state.skippedCount
								? h(
										"p",
										{ class: "text-muted small" },
										__(
											"{0} row(s) were skipped because their banking context could not be resolved safely.",
											[state.skippedCount],
										),
									)
								: null,
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
		page.add_menu_item(__("Open Matching Report"), () =>
			frappe.set_route("query-report", "RetailEdge Bank Transaction Matching"),
		);
		page.add_menu_item(__("Open Reconciliation Readiness"), () =>
			frappe.set_route("query-report", "RetailEdge Bank Match Reconciliation Readiness"),
		);
		const component = createWorkspaceComponent(runtime, page);
		const app = runtime.createEdgeApp(component);
		app.mount(page.main[0]);
		wrapper.retailedgeBankingApp = app;
	}

	global.retailedgeBootBankingWorkspace = boot;
	global.retailedgeBankingWorkspacePageName = PAGE_NAME;
})(window);
