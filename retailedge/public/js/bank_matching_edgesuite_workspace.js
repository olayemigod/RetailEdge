(function installRetailEdgeBankingEdgeSuiteWorkspace(global) {
	"use strict";

	const PAGE_NAME = "bank-matching-reconciliation";
	const QUEUES = ["To Match", "To Reconcile", "Exceptions", "Reconciled"];
	const DIRECTIONS = [
		{ label: "All", value: "All" },
		{ label: "Inflows", value: "Inflow" },
		{ label: "Outflows", value: "Outflow" },
	];
	const TECHNICAL_CATEGORY_LABELS = {
		payment_entry_match: "Payment Entry",
		invoice_payment_row_match: "Invoice Payment Row",
		journal_entry_match: "Journal Entry",
	};

	function edgeRuntime() {
		return global.EdgeSuiteUI || global.EdgeUI || null;
	}

	function t(text, args) {
		return typeof global.__ === "function" ? global.__(text, args) : text;
	}

	function formatMoney(value, currency) {
		try {
			return global.format_currency(value || 0, currency || undefined);
		} catch (_error) {
			return String(value || 0);
		}
	}

	function clean(value) {
		return String(value ?? "").trim();
	}

	function humanize(value) {
		const raw = clean(value);
		if (!raw) return "";
		if (TECHNICAL_CATEGORY_LABELS[raw]) return t(TECHNICAL_CATEGORY_LABELS[raw]);
		return raw
			.replace(/[_-]+/g, " ")
			.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
			.replace(/\b\w/g, (letter) => letter.toUpperCase());
	}

	function businessCategory(...values) {
		for (const value of values) {
			const raw = clean(value);
			if (!raw || raw.toLowerCase() === "unclassified") continue;
			return humanize(raw);
		}
		return "";
	}

	function rowCategory(row) {
		const category = businessCategory(row?.transaction_category);
		if (category) return category;
		if (row?.suggested_document_type === "Sales Invoice") return t("Invoice Payment");
		if (row?.suggested_document_type === "Journal Entry") return t("Journal Entry");
		if (row?.suggested_document_type === "Payment Entry") return t("Payment Entry");
		return "";
	}

	async function permissionAwareLinkSearch(doctype, query, filters = {}) {
		const response = await global.frappe.call({
			method: "frappe.desk.search.search_link",
			args: {
				doctype,
				txt: clean(query),
				filters,
				page_length: 20,
			},
		});
		return (response?.message || []).map((row) => ({
			value: row.value || row.name,
			label: row.label || row.value || row.name,
			description: row.description || "",
		}));
	}

	function createWorkspaceComponent(runtime, page) {
		const { defineComponent, h, onMounted, reactive, computed } = runtime.Vue;
		const EdgePageLayout = runtime.getComponent("EdgePageLayout");
		const EdgePageHeader = runtime.getComponent("EdgePageHeader");
		const EdgeActionBar = runtime.getComponent("EdgeActionBar");
		const EdgeFilterBar = runtime.getComponent("EdgeFilterBar");
		const EdgeLinkField = runtime.getComponent("EdgeLinkField");
		const EdgeInput = runtime.getComponent("EdgeInput");
		const EdgeDropdown = runtime.getComponent("EdgeDropdown");
		const EdgeStatCard = runtime.getComponent("EdgeStatCard");
		const EdgeStatusBadge = runtime.getComponent("EdgeStatusBadge");
		const EdgeLoadingState = runtime.getComponent("EdgeLoadingState");
		const EdgeEmptyState = runtime.getComponent("EdgeEmptyState");
		const EdgeErrorState = runtime.getComponent("EdgeErrorState");
		const EdgeModal = runtime.getComponent("EdgeModal");
		const EdgeTextarea = runtime.getComponent("EdgeTextarea");

		return defineComponent({
			name: "RetailEdgeBankMatchingReconciliationEdgeSuite",
			setup() {
				const state = reactive({
					direction: "All",
					queue: "To Match",
					loading: false,
					error: "",
					rows: [],
					skippedCount: 0,
					sortKey: "transaction_date",
					sortDirection: "desc",
					filters: {
						company: "",
						branch: "",
						bank_account: "",
						from_date: "",
						to_date: "",
						search: "",
					},
					notice: { message: "", tone: "neutral" },
					candidate: {
						open: false,
						busy: false,
						bankTransaction: "",
						candidates: [],
						selected: "",
						error: "",
					},
					review: {
						open: false,
						loading: false,
						busy: false,
						error: "",
						matchName: "",
						doc: {},
						approval: {},
						evidence: {},
						candidateSnapshot: null,
						decisionNote: "",
						approvalNote: "",
					},
					reconcile: {
						open: false,
						busy: false,
						matchName: "",
						confirmed: false,
						error: "",
					},
				});
				let searchTimer = null;

				const sortedRows = computed(() => {
					const rows = [...state.rows];
					const key = state.sortKey;
					const direction = state.sortDirection === "asc" ? 1 : -1;
					return rows.sort((left, right) => {
						let a = left?.[key];
						let b = right?.[key];
						if (key === "bank_amount" || key === "candidate_amount") {
							a = Number(a || 0);
							b = Number(b || 0);
							return (a - b) * direction;
						}
						return clean(a).localeCompare(clean(b), undefined, { numeric: true, sensitivity: "base" }) * direction;
					});
				});

				function setNotice(message, tone = "neutral") {
					state.notice.message = message || "";
					state.notice.tone = tone;
				}

				async function refresh() {
					state.loading = true;
					state.error = "";
					try {
						const response = await global.frappe.call({
							method: "retailedge.banking_workspace.get_banking_workspace_rows",
							args: {
								direction: state.direction,
								queue: state.queue,
								limit: 100,
								...state.filters,
							},
						});
						const payload = response?.message || {};
						state.rows = payload.rows || [];
						state.skippedCount = Number(payload.skipped_count || 0);
					} catch (error) {
						state.error = error?.message || t("Unable to load the banking queue.");
					} finally {
						state.loading = false;
					}
				}

				function scheduleRefresh() {
					if (searchTimer) clearTimeout(searchTimer);
					searchTimer = setTimeout(refresh, 300);
				}

				function updateFilter(field, value, { immediate = true } = {}) {
					state.filters[field] = value || "";
					if (field === "company") {
						state.filters.branch = "";
						state.filters.bank_account = "";
					}
					if (immediate) refresh();
					else scheduleRefresh();
				}

				function clearFilters() {
					Object.assign(state.filters, {
						company: "",
						branch: "",
						bank_account: "",
						from_date: "",
						to_date: "",
						search: "",
					});
					refresh();
				}

				function routeToDocument(doctype, name) {
					if (doctype && name) global.frappe.set_route("Form", doctype, name);
				}

				function toggleSort(key) {
					if (state.sortKey === key) state.sortDirection = state.sortDirection === "asc" ? "desc" : "asc";
					else {
						state.sortKey = key;
						state.sortDirection = key === "transaction_date" ? "desc" : "asc";
					}
				}

				function candidateReason(row) {
					return (Array.isArray(row?.reasons) ? row.reasons.filter(Boolean) : []).join(" · ");
				}

				function fuzzyReason(row) {
					return row?.fuzzy_note || row?.fuzzy_evidence?.reason || t("No supplemental fuzzy evidence recorded.");
				}

				function candidateKey(row, index) {
					return `${row.document_type || ""}::${row.document_name || ""}::${row.payment_row_index ?? ""}::${index}`;
				}

				function selectedCandidate() {
					return state.candidate.candidates.find((item) => item.__key === state.candidate.selected) || null;
				}

				async function findCandidates(bankTransaction) {
					state.candidate.error = "";
					try {
						const response = await global.frappe.call({
							method: "retailedge.bank_candidate_engine.get_direction_aware_bank_candidates",
							args: { bank_transaction_name: bankTransaction, limit: 20 },
						});
						const payload = response?.message || {};
						const candidates = (payload.candidates || []).map((row, index) => ({ ...row, __key: candidateKey(row, index) }));
						if (!candidates.length) {
							setNotice(t("No safe accounting candidate was found for this bank transaction."), "warning");
							return;
						}
						Object.assign(state.candidate, {
							open: true,
							busy: false,
							bankTransaction,
							candidates,
							selected: candidates[0].__key,
							error: "",
						});
					} catch (error) {
						setNotice(error?.message || t("Unable to search for accounting matches."), "danger");
					}
				}

				async function prepareSelectedCandidate() {
					const row = selectedCandidate();
					if (!row) return;
					if (Number(row.review_supported) === 0) {
						state.candidate.error = row.review_block_reason || t("This candidate cannot enter review yet.");
						return;
					}
					state.candidate.busy = true;
					state.candidate.error = "";
					try {
						const response = await global.frappe.call({
							method: "retailedge.bank_candidate_engine.prepare_direction_aware_bank_candidate",
							args: {
								bank_transaction_name: state.candidate.bankTransaction,
								document_type: row.document_type,
								document_name: row.document_name,
							},
						});
						const result = response?.message || {};
						if (!result.match_name) {
							state.candidate.error = result.message || t("This candidate cannot enter review yet.");
							return;
						}
						state.candidate.open = false;
						await showReviewMatchDialog(result.match_name, row);
					} catch (error) {
						state.candidate.error = error?.message || t("Unable to prepare this candidate for review.");
					} finally {
						state.candidate.busy = false;
					}
				}

				async function getMatchDocument(matchName) {
					const response = await global.frappe.call({
						method: "frappe.client.get",
						args: { doctype: "RetailEdge Bank Transaction Match", name: matchName },
					});
					return response?.message || {};
				}

				async function getApprovalState(matchName) {
					const response = await global.frappe.call({
						method: "retailedge.reconciliation_approval.get_reconciliation_approval_state",
						args: { match_name: matchName },
					});
					return response?.message || {};
				}

				async function getMatchEvidence(matchName) {
					const response = await global.frappe.call({
						method: "retailedge.banking_readiness.get_match_account_evidence",
						args: { match_name: matchName },
					});
					return response?.message || {};
				}

				async function showReviewMatchDialog(matchName, candidateSnapshot = null) {
					Object.assign(state.review, {
						open: true,
						loading: true,
						busy: false,
						error: "",
						matchName,
						doc: {},
						approval: {},
						evidence: {},
						candidateSnapshot,
						decisionNote: "",
						approvalNote: "",
					});
					try {
						const [doc, approval, evidence] = await Promise.all([
							getMatchDocument(matchName),
							getApprovalState(matchName),
							getMatchEvidence(matchName),
						]);
						state.review.doc = doc;
						state.review.approval = approval;
						state.review.evidence = evidence;
						state.review.decisionNote = doc.decision_note || "";
						state.review.approvalNote = approval.approval_note || "";
					} catch (error) {
						state.review.error = error?.message || t("Unable to load this bank match review.");
					} finally {
						state.review.loading = false;
					}
				}

				function closeReview() {
					if (!state.review.busy) state.review.open = false;
				}

				async function applyReviewDecision(method, successMessage) {
					state.review.busy = true;
					state.review.error = "";
					try {
						const response = await global.frappe.call({
							method,
							args: {
								match_name: state.review.matchName,
								decision_note: state.review.decisionNote || "",
							},
						});
						const result = response?.message || {};
						state.review.open = false;
						setNotice(result.message || successMessage, "success");
						await refresh();
					} catch (error) {
						state.review.error = error?.message || t("Unable to apply the review decision.");
					} finally {
						state.review.busy = false;
					}
				}

				async function applyApprovalAction(method, successMessage, tone = "success") {
					state.review.busy = true;
					state.review.error = "";
					try {
						const response = await global.frappe.call({
							method,
							args: {
								match_name: state.review.matchName,
								approval_note: state.review.approvalNote || "",
							},
						});
						const result = response?.message || {};
						state.review.open = false;
						setNotice(result.message || successMessage, tone);
						await refresh();
					} catch (error) {
						state.review.error = error?.message || t("Unable to update reconciliation approval.");
					} finally {
						state.review.busy = false;
					}
				}

				function openReconciliation(matchName) {
					Object.assign(state.reconcile, {
						open: true,
						busy: false,
						matchName,
						confirmed: false,
						error: "",
					});
				}

				async function executeReconciliation() {
					if (!state.reconcile.confirmed || !state.reconcile.matchName) return;
					state.reconcile.busy = true;
					state.reconcile.error = "";
					try {
						const response = await global.frappe.call({
							method: "retailedge.banking_operations.match_and_reconcile",
							args: {
								match_name: state.reconcile.matchName,
								confirm_match: 0,
								confirm_reconciliation: 1,
							},
						});
						const result = response?.message || {};
						state.reconcile.open = false;
						setNotice(result.message || result.status || t("Reconciliation processed."), result.status === "Executed" ? "success" : "warning");
						await refresh();
					} catch (error) {
						state.reconcile.error = error?.message || t("ERPNext reconciliation could not be completed.");
					} finally {
						state.reconcile.busy = false;
					}
				}

				function rowAction(row) {
					if (row.operational_status === "Ready to Reconcile") {
						return actionButton(t("Reconcile"), "primary", () => openReconciliation(row.match_name));
					}
					if (row.operational_status === "Awaiting Approval" && row.match_name) {
						return actionButton(row.approval_can_approve ? t("Approve") : t("Review Approval"), "secondary", () => showReviewMatchDialog(row.match_name));
					}
					if (row.operational_status === "Suggested Match" && row.match_name) {
						return actionButton(t("Review Suggestion"), "secondary", () => showReviewMatchDialog(row.match_name));
					}
					if (!row.match_name && state.queue === "To Match") {
						return actionButton(t("Find Match"), "primary", () => findCandidates(row.bank_transaction));
					}
					if (row.match_name) return actionButton(t("Review"), "secondary", () => showReviewMatchDialog(row.match_name));
					return null;
				}

				function actionButton(label, variant, onClick, extra = {}) {
					return h("button", {
						type: "button",
						class: ["edge-button", `edge-button--${variant}`],
						onClick,
						...extra,
					}, label);
				}

				function sortHeader(label, key, className = "") {
					const active = state.sortKey === key;
					return h("th", { scope: "col", class: className }, [
						h("button", {
							type: "button",
							class: ["retailedge-bank-sort", { "is-active": active }],
							onClick: () => toggleSort(key),
							"aria-label": t("Sort by {0}", [label]),
						}, [t(label), active ? h("span", { "aria-hidden": "true" }, state.sortDirection === "asc" ? " ↑" : " ↓") : null]),
					]);
				}

				function renderNarration(row) {
					const narration = row.description || row.reference || row.bank_transaction || "";
					const meta = [row.bank_account, row.reference, rowCategory(row)].filter(Boolean).join(" · ");
					return h("div", { class: "retailedge-bank-transaction-cell" }, [
						h("button", {
							type: "button",
							class: "edge-link-button retailedge-bank-narration",
							title: narration,
							onClick: () => routeToDocument("Bank Transaction", row.bank_transaction),
						}, narration),
						meta ? h("small", { class: "retailedge-bank-meta" }, meta) : null,
					]);
				}

				function renderCandidate(row) {
					if (!row.suggested_document) return "—";
					const detail = [
						row.candidate_amount == null ? null : formatMoney(row.candidate_amount, row.currency),
						row.amount_difference == null ? null : `${t("Difference")}: ${formatMoney(row.amount_difference, row.currency)}`,
					].filter(Boolean).join(" · ");
					return h("div", { class: "retailedge-bank-candidate-cell" }, [
						h("button", {
							type: "button",
							class: "edge-link-button",
							onClick: () => routeToDocument(row.suggested_document_type, row.suggested_document),
						}, `${row.suggested_document_type || ""} ${row.suggested_document}`),
						detail ? h("small", { class: "retailedge-bank-meta" }, detail) : null,
					]);
				}

				function renderTable() {
					return h("div", { class: "edge-table-wrap retailedge-bank-table-wrap" }, [
						h("table", { class: "edge-table retailedge-bank-table" }, [
							h("thead", [h("tr", [
								sortHeader("Date", "transaction_date", "retailedge-col-date"),
								sortHeader("Bank Transaction", "bank_transaction", "retailedge-col-transaction"),
								sortHeader("Direction", "direction", "retailedge-col-direction"),
								sortHeader("Bank Amount", "bank_amount", "retailedge-col-amount text-right"),
								h("th", { scope: "col", class: "retailedge-col-candidate" }, t("Candidate")),
								sortHeader("Status", "operational_status", "retailedge-col-status"),
								h("th", { scope: "col", class: "retailedge-col-action" }, t("Action")),
						])]),
							h("tbody", sortedRows.value.map((row) => h("tr", { key: row.match_name || row.bank_transaction }, [
								h("td", { class: "retailedge-col-date", "data-label": t("Date") }, row.transaction_date || ""),
								h("td", { class: "retailedge-col-transaction", "data-label": t("Bank Transaction") }, [renderNarration(row)]),
								h("td", { class: "retailedge-col-direction", "data-label": t("Direction") }, row.direction || ""),
								h("td", { class: "retailedge-col-amount text-right", "data-label": t("Bank Amount") }, formatMoney(row.bank_amount, row.currency)),
								h("td", { class: "retailedge-col-candidate", "data-label": t("Candidate") }, [renderCandidate(row)]),
								h("td", { class: "retailedge-col-status", "data-label": t("Status") }, [h(EdgeStatusBadge, { label: row.operational_status || "", status: row.operational_status || "" })]),
								h("td", { class: "retailedge-col-action", "data-label": t("Action") }, [rowAction(row)]),
							]))),
						]),
					]);
				}

				function selectorBar(label, values, currentValue, onSelect) {
					return h(EdgeActionBar, { label: t(label) }, {
						actions: () => values.map((item) => {
							const value = typeof item === "string" ? item : item.value;
							const text = typeof item === "string" ? item : item.label;
							return actionButton(t(text), currentValue === value ? "primary" : "secondary", () => onSelect(value), {
								"aria-pressed": currentValue === value ? "true" : "false",
							});
						}),
					});
				}

				function renderFilters() {
					const companyFilters = state.filters.company ? { company: state.filters.company } : {};
					return h(EdgeFilterBar, { title: t("Filters") }, {
						default: () => [
							h(EdgeLinkField, {
								label: t("Company"),
								modelValue: state.filters.company,
								searcher: (query) => permissionAwareLinkSearch("Company", query),
								"onUpdate:modelValue": (value) => updateFilter("company", value),
							}),
							h(EdgeLinkField, {
								label: t("Branch"),
								modelValue: state.filters.branch,
								disabled: !state.filters.company,
								description: !state.filters.company ? t("Select a company first.") : "",
								context: { company: state.filters.company },
								searcher: (query) => permissionAwareLinkSearch("Branch", query, companyFilters),
								"onUpdate:modelValue": (value) => updateFilter("branch", value),
							}),
							h(EdgeLinkField, {
								label: t("Bank Account"),
								modelValue: state.filters.bank_account,
								disabled: !state.filters.company,
								description: !state.filters.company ? t("Select a company first.") : "",
								context: { company: state.filters.company },
								searcher: (query) => permissionAwareLinkSearch("Bank Account", query, companyFilters),
								"onUpdate:modelValue": (value) => updateFilter("bank_account", value),
							}),
							h(EdgeInput, {
								label: t("From Date"), type: "date", modelValue: state.filters.from_date,
								"onUpdate:modelValue": (value) => updateFilter("from_date", value),
							}),
							h(EdgeInput, {
								label: t("To Date"), type: "date", modelValue: state.filters.to_date,
								"onUpdate:modelValue": (value) => updateFilter("to_date", value),
							}),
							h(EdgeInput, {
								label: t("Search"),
								type: "search",
								placeholder: t("Narration, reference, party, document or amount"),
								modelValue: state.filters.search,
								"onUpdate:modelValue": (value) => updateFilter("search", value, { immediate: false }),
							}),
						],
						actions: () => [actionButton(t("Clear Filters"), "secondary", clearFilters)],
					});
				}

				function renderStats() {
					const inflows = state.rows.filter((row) => row.direction === "Inflow").length;
					const outflows = state.rows.filter((row) => row.direction === "Outflow").length;
					return h("div", { class: "retailedge-bank-stats" }, [
						h(EdgeStatCard, { label: t("Current Queue"), value: state.rows.length, helper: state.queue, tone: "neutral" }),
						h(EdgeStatCard, { label: t("Inflows"), value: inflows, helper: t("Visible records"), tone: "success" }),
						h(EdgeStatCard, { label: t("Outflows"), value: outflows, helper: t("Visible records"), tone: "warning" }),
						h(EdgeStatCard, { label: t("Skipped Safely"), value: state.skippedCount, helper: t("Unresolved banking context"), tone: state.skippedCount ? "warning" : "neutral" }),
					]);
				}

				function renderNotice() {
					if (!state.notice.message) return null;
					return h("div", { class: ["retailedge-bank-notice", `is-${state.notice.tone}`], role: "status" }, [
						h("span", state.notice.message),
						h("button", { type: "button", class: "edge-button edge-button--ghost", onClick: () => setNotice("") }, "×"),
					]);
				}

				function renderCandidateModal() {
					const row = selectedCandidate();
					const options = state.candidate.candidates.map((candidate) => ({
						value: candidate.__key,
						label: `${candidate.document_type || ""} ${candidate.document_name || ""}`.trim(),
						description: [businessCategory(candidate.transaction_category, candidate.candidate_category), formatMoney(candidate.candidate_amount, candidate.currency)].filter(Boolean).join(" · "),
					}));
					return h(EdgeModal, {
						open: state.candidate.open,
						title: t("Matching Candidates"),
						subtitle: state.candidate.bankTransaction,
						size: "lg",
						busy: state.candidate.busy,
						onClose: () => { if (!state.candidate.busy) state.candidate.open = false; },
					}, {
						default: () => [
							h(EdgeDropdown, {
								label: t("Candidate"),
								modelValue: state.candidate.selected,
								options,
								"onUpdate:modelValue": (value) => { state.candidate.selected = value; state.candidate.error = ""; },
							}),
							row ? h("section", { class: "retailedge-bank-candidate-review" }, [
								h("div", { class: "retailedge-bank-candidate-review__header" }, [
									h("strong", businessCategory(row.transaction_category, row.candidate_category) || t("Accounting Candidate")),
									h(EdgeStatusBadge, { status: Number(row.review_supported) === 0 ? "Blocked" : "Ready" }),
								]),
								h("dl", { class: "retailedge-bank-detail-grid" }, [
									detailPair("Document", `${row.document_type || ""} ${row.document_name || ""}`),
									detailPair("Amount", formatMoney(row.candidate_amount, row.currency)),
									detailPair("Accounting / Hard Score", row.hard_match_score ?? row.match_score ?? "—"),
									detailPair("Supplemental Fuzzy Score", row.fuzzy_score ?? "—"),
								]),
								candidateReason(row) ? h("p", { class: "retailedge-bank-evidence-text" }, candidateReason(row)) : null,
								h("p", { class: "retailedge-bank-fuzzy-note" }, `${t("Fuzzy evidence is supplemental only")}: ${fuzzyReason(row)}`),
							]) : null,
							state.candidate.error ? h("div", { class: "retailedge-bank-inline-error", role: "alert" }, state.candidate.error) : null,
						],
						footer: () => [
							actionButton(t("Cancel"), "secondary", () => { state.candidate.open = false; }, { disabled: state.candidate.busy }),
							actionButton(t("Review Match"), "primary", prepareSelectedCandidate, { disabled: state.candidate.busy || !row }),
						],
					});
				}

				function detailPair(label, value) {
					return h("div", { class: "retailedge-bank-detail-pair" }, [
						h("dt", t(label)),
						h("dd", clean(value) || t("Not Available")),
					]);
				}

				function evidencePair(item) {
					return h("div", { class: "retailedge-bank-safety-row" }, [
						h("strong", item.label || humanize(item.key)),
						h(EdgeStatusBadge, { status: item.status || "Not Available" }),
						h("span", [clean(item.statement) || "—", " ↔ ", clean(item.accounting) || "—"]),
					]);
				}

				function renderReviewModal() {
					const doc = state.review.doc || {};
					const approval = state.review.approval || {};
					const evidence = state.review.evidence || {};
					const statement = evidence.statement || {};
					const accounting = evidence.accounting || {};
					const canDecide = ["Suggested", "Reopened", "Needs Review"].includes(doc.decision_status || "Suggested");
					const confirmed = doc.decision_status === "Confirmed";
					const approvalRequired = Boolean(approval.required);
					const approvalSatisfied = Boolean(approval.is_satisfied);
					const canApprove = Boolean(approval.can_approve);
					const canRequestApproval = confirmed && approvalRequired && !approvalSatisfied && !canApprove;
					const category = businessCategory(evidence.transaction_category, evidence.candidate_category, state.review.candidateSnapshot?.transaction_category, state.review.candidateSnapshot?.candidate_category);
					const recordBadge = confirmed ? (doc.execution_status === "Executed" || doc.execution_status === "Already Handled" ? t("Reconciled Record") : t("Confirmed Candidate")) : t("Suggested Candidate");

					return h(EdgeModal, {
						open: state.review.open,
						title: t("Review Match: {0}", [doc.bank_transaction || state.review.matchName]),
						subtitle: confirmed ? t("Confirmed match — reconciliation remains governed by approval and fresh ERPNext safety checks.") : t("Review accounting identity before confirming this match."),
						size: "xl",
						busy: state.review.busy,
						closeOnBackdrop: false,
						onClose: closeReview,
					}, {
						default: () => state.review.loading
							? [h(EdgeLoadingState, { message: t("Loading match review...") })]
							: [
								state.review.error ? h("div", { class: "retailedge-bank-inline-error", role: "alert" }, state.review.error) : null,
								h("div", { class: "retailedge-bank-compare-grid" }, [
									h("section", { class: "retailedge-bank-compare-card" }, [
										h("header", [h("h3", t("Bank Statement")), h(EdgeStatusBadge, { status: evidence.direction || doc.bank_direction || "" })]),
										h("dl", { class: "retailedge-bank-detail-grid" }, [
											detailPair("Bank Transaction", statement.bank_transaction || doc.bank_transaction),
											detailPair("Bank", statement.bank),
											detailPair("Bank Account", statement.bank_account || doc.bank_account),
											detailPair("GL Account", statement.gl_account || doc.resolved_bank_account),
											detailPair("Company", statement.company || doc.company),
											detailPair("Direction", evidence.direction || doc.bank_direction),
											detailPair("Amount", formatMoney(statement.amount || doc.bank_amount, doc.currency)),
											detailPair("Date", statement.date || doc.transaction_date),
											detailPair("Reference", statement.reference || doc.bank_reference),
										]),
									]),
									h("section", { class: "retailedge-bank-compare-card" }, [
										h("header", [h("h3", t("Accounting Record")), h(EdgeStatusBadge, { status: recordBadge })]),
										h("dl", { class: "retailedge-bank-detail-grid" }, [
											detailPair("Accounting Document", `${accounting.doctype || doc.suggested_document_type || ""} ${accounting.name || doc.suggested_document || ""}`),
											detailPair("Business Category", category || t("Accounting Match")),
											detailPair("Bank", accounting.bank),
											detailPair("Bank Account", accounting.bank_account),
											detailPair(accounting.gl_account_label || "Bank-side Account", accounting.gl_account || doc.resolved_payment_account || doc.payment_account),
											detailPair("Company", accounting.company || doc.company),
											detailPair("Direction", evidence.direction || doc.bank_direction),
											detailPair("Amount", formatMoney(accounting.amount || doc.candidate_amount, doc.currency)),
											detailPair("Date", accounting.date || doc.candidate_posting_date),
											detailPair("Reference", accounting.reference),
										]),
									]),
								]),
								h("section", { class: "retailedge-bank-review-section" }, [
									h("h3", t("Bank Identity & Accounting Safety")),
									h("div", { class: "retailedge-bank-safety-grid" }, (evidence.evidence || []).map(evidencePair)),
								]),
								h("section", { class: "retailedge-bank-review-section" }, [
									h("h3", t("Why this matches")),
									category ? h("p", [h("strong", `${t("Business Category")}: `), category]) : null,
									doc.match_reason_summary || doc.match_reason ? h("p", doc.match_reason_summary || doc.match_reason) : null,
									h("p", { class: "retailedge-bank-fuzzy-note" }, t("Fuzzy evidence is supplemental only and cannot change accounting eligibility or confirmation rules.")),
								]),
								confirmed ? h("section", { class: "retailedge-bank-review-section" }, [
									h("div", { class: "retailedge-bank-section-heading" }, [h("h3", t("Reconciliation Approval")), h(EdgeStatusBadge, { status: approval.status || (approvalRequired ? "Pending" : "Not Required") })]),
									approval.reason ? h("p", approval.reason) : null,
									approval.approved_by ? h("p", [h("strong", `${t("Approved by")}: `), approval.approved_by]) : null,
									!approvalSatisfied ? h(EdgeTextarea, {
										label: t("Approval Note"),
										modelValue: state.review.approvalNote,
										"onUpdate:modelValue": (value) => { state.review.approvalNote = value; },
									}) : null,
								]) : null,
								canDecide ? h("section", { class: "retailedge-bank-review-section" }, [
									h("h3", t("Review Decision")),
									h(EdgeTextarea, {
										label: t("Decision Note"),
										modelValue: state.review.decisionNote,
										"onUpdate:modelValue": (value) => { state.review.decisionNote = value; },
									}),
								]) : null,
								h("div", { class: "retailedge-bank-record-links" }, [
									actionButton(t("Open Audit Record"), "secondary", () => routeToDocument("RetailEdge Bank Transaction Match", state.review.matchName)),
									actionButton(t("Open Bank Transaction"), "secondary", () => routeToDocument("Bank Transaction", doc.bank_transaction)),
									doc.suggested_document ? actionButton(t("Open Accounting Document"), "secondary", () => routeToDocument(doc.suggested_document_type, doc.suggested_document)) : null,
								]),
							],
						footer: () => {
							const buttons = [actionButton(t("Close"), "secondary", closeReview, { disabled: state.review.busy })];
							if (canDecide) {
								buttons.push(actionButton(t("Keep for Review"), "secondary", () => applyReviewDecision("retailedge.api.mark_bank_transaction_match_needs_review", t("Match kept for review.")), { disabled: state.review.busy }));
								buttons.push(actionButton(t("Reject Match"), "danger", () => applyReviewDecision("retailedge.api.reject_bank_transaction_match", t("Match rejected.")), { disabled: state.review.busy }));
								buttons.push(actionButton(t("Confirm Match"), "primary", () => applyReviewDecision("retailedge.api.confirm_bank_transaction_match", t("Match confirmed. Reconciliation is still required.")), { disabled: state.review.busy }));
							} else if (canApprove) {
								buttons.push(actionButton(t("Decline Approval"), "danger", () => applyApprovalAction("retailedge.reconciliation_approval.decline_reconciliation_for_match", t("Reconciliation approval declined."), "warning"), { disabled: state.review.busy }));
								buttons.push(actionButton(t("Approve Reconciliation"), "primary", () => applyApprovalAction("retailedge.reconciliation_approval.approve_reconciliation_for_match", t("Reconciliation approved.")), { disabled: state.review.busy }));
							} else if (canRequestApproval) {
								buttons.push(actionButton(t("Request Approval"), "primary", () => applyApprovalAction("retailedge.reconciliation_approval.request_reconciliation_approval", t("Reconciliation approval requested.")), { disabled: state.review.busy }));
							}
							return buttons;
						},
					});
				}

				function renderReconciliationModal() {
					return h(EdgeModal, {
						open: state.reconcile.open,
						title: t("Final Reconciliation"),
						subtitle: state.reconcile.matchName,
						size: "md",
						busy: state.reconcile.busy,
						closeOnBackdrop: false,
						onClose: () => { if (!state.reconcile.busy) state.reconcile.open = false; },
					}, {
						default: () => [
							h("div", { class: "retailedge-bank-final-warning" }, [
								h("strong", t("ERPNext remains the reconciliation authority.")),
								h("p", t("RetailEdge will run a fresh safety check against current accounting data before ERPNext Banking reconciliation. Submitted accounting documents will not be mutated.")),
							]),
							h("label", { class: "edge-checkbox retailedge-bank-confirm-check" }, [
								h("input", {
									type: "checkbox",
									checked: state.reconcile.confirmed,
									disabled: state.reconcile.busy,
									onChange: (event) => { state.reconcile.confirmed = event.target.checked; },
								}),
								h("span", t("I confirm that the Bank Transaction, accounting document, bank account, direction and amount are correct.")),
							]),
							state.reconcile.error ? h("div", { class: "retailedge-bank-inline-error", role: "alert" }, state.reconcile.error) : null,
						],
						footer: () => [
							actionButton(t("Cancel"), "secondary", () => { state.reconcile.open = false; }, { disabled: state.reconcile.busy }),
							actionButton(t("Reconcile Through ERPNext"), "primary", executeReconciliation, { disabled: state.reconcile.busy || !state.reconcile.confirmed }),
						],
					});
				}

				onMounted(refresh);
				global.retailedgeBankingWorkspaceRefresh = refresh;

				return () => h(EdgePageLayout, { class: "retailedge-bank-layout" }, {
					header: () => h(EdgePageHeader, {
						eyebrow: t("RetailEdge Banking"),
						title: t("Bank Matching & Reconciliation"),
						subtitle: t("Match bank inflows and outflows to valid ERPNext accounting events, then reconcile through ERPNext Banking."),
					}, {
						actions: () => [
							actionButton(t("Banking Setup & Readiness"), "secondary", () => global.frappe.set_route("banking-readiness")),
							actionButton(t("Refresh"), "primary", refresh, { disabled: state.loading }),
						],
					}),
					filters: renderFilters,
					default: () => [
						renderNotice(),
						renderStats(),
						selectorBar("Direction", DIRECTIONS, state.direction, (value) => { state.direction = value; refresh(); }),
						selectorBar("Workflow Status", QUEUES, state.queue, (value) => { state.queue = value; refresh(); }),
						state.loading ? h(EdgeLoadingState, { message: t("Loading banking queue...") }) : null,
						state.error ? h(EdgeErrorState, { message: state.error, actionLabel: t("Try again"), onRetry: refresh }) : null,
						!state.loading && !state.error && !state.rows.length ? h(EdgeEmptyState, {
							title: t("No transactions in this queue"),
							description: t("Adjust the direction or filters, or refresh after new bank transactions are imported."),
						}) : null,
						!state.loading && !state.error && state.rows.length ? renderTable() : null,
						state.skippedCount ? h("p", { class: "retailedge-bank-skipped-note" }, t("{0} row(s) were skipped because their banking context could not be resolved safely.", [state.skippedCount])) : null,
						renderCandidateModal(),
						renderReviewModal(),
						renderReconciliationModal(),
					],
				});
			},
		});
	}

	function boot(wrapper) {
		const runtime = edgeRuntime();
		if (!runtime?.createEdgeApp || !runtime?.Vue) {
			global.frappe.throw(t("EdgeSuite UI runtime is required for Bank Matching & Reconciliation."));
		}
		const required = ["EdgePageLayout", "EdgePageHeader", "EdgeFilterBar", "EdgeLinkField", "EdgeInput", "EdgeDropdown", "EdgeStatCard", "EdgeStatusBadge", "EdgeModal", "EdgeTextarea"];
		const missing = required.filter((name) => !runtime.getComponent(name));
		if (missing.length) global.frappe.throw(t("EdgeSuite UI is missing required banking components: {0}", [missing.join(", ")]));

		const page = global.frappe.ui.make_app_page({
			parent: wrapper,
			title: t("Bank Matching & Reconciliation"),
			single_column: true,
		});
		page.add_menu_item(t("Open Matching Report"), () => global.frappe.set_route("query-report", "RetailEdge Bank Transaction Matching"));
		page.add_menu_item(t("Open Reconciliation Readiness Report"), () => global.frappe.set_route("query-report", "RetailEdge Bank Match Reconciliation Readiness"));
		const app = runtime.createEdgeApp(createWorkspaceComponent(runtime, page));
		app.mount(page.main[0]);
		wrapper.retailedgeBankingApp = app;
	}

	global.retailedgeBootBankingWorkspace = boot;
	global.retailedgeBankingWorkspacePageName = PAGE_NAME;
	global.retailedgeBankingEdgeSuiteWorkspace = true;
})(window);
