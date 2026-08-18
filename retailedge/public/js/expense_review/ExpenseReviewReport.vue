<template>
	<div v-if="!edgeUIValid" class="review-fallback">
		<strong>Expense Review could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Expense Review"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/expense-review"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Expense Review"
			eyebrow="Review & Approvals"
			subtitle="Review cashier expenses for Daily Sales Audit inclusion and posting readiness without creating a second expense workflow."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No expenses need review"
			emptyDescription="Adjust the filters or change the Review Status to inspect other expenses."
			loadingMessage="Loading expense review…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="handleCellClick"
		>
			<template #filters>
				<div class="review-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.cashier" :selectedLabel="cashierLabel" label="Cashier" placeholder="All cashiers" :searcher="cashierSearch" @select="onCashierSelected" @clear="clearCashier" />
					<EdgeLinkField v-model="filters.expense_category" label="Expense Category" placeholder="All categories" :searcher="categorySearch" />
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">Review Status</span><select v-model="filters.daily_audit_inclusion_status" class="edge-input"><option value="">All</option><option value="Pending Review">Pending Review</option><option value="Included">Included</option><option value="Excluded">Excluded</option><option value="Needs Clarification">Needs Clarification</option></select></label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Loading…" : "Apply Filters" }}</button></div>
				</div>
				<details class="advanced-filters">
					<summary>More filters</summary>
					<div class="review-filter-grid advanced-grid">
						<label class="edge-field"><span class="edge-field-label">Expense Status</span><select v-model="filters.expense_status" class="edge-input"><option value="">All</option><option v-for="status in expenseStatuses" :key="status" :value="status">{{ status }}</option></select></label>
						<label class="edge-field"><span class="edge-field-label">Posting Ready</span><select v-model="filters.posting_ready" class="edge-input"><option value="">All</option><option value="1">Ready</option><option value="0">Blocked</option></select></label>
					</div>
				</details>
			</template>
			<template #resultMeta>
				<span>{{ scan.rows || 0 }} matching expense{{ Number(scan.rows || 0) === 1 ? "" : "s" }}</span>
				<span>Bounded review dataset · {{ providerDatasetLimit.toLocaleString() }} row cap</span>
				<span v-if="canReview">Reviewer actions enabled</span>
				<span v-else>Read-only review access</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "expense-review";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ExpenseReviewReport",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], pagination: {}, scan: {}, menuItems: [], tenantName: "", branchName: "", userName: "", cashierLabel: "", canReview: false, currentPage: 1,
			filters: { company: "", branch: "", cashier: "", expense_category: "", expense_status: "", daily_audit_inclusion_status: "Pending Review", posting_ready: "", from_date: "", to_date: "", page_size: 50 },
			expenseStatuses: ["Draft", "Submitted", "Pending Ledger", "Rejected", "Posted", "Cancelled"],
		};
	},
	computed: {
		reportProvider() { return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null; },
		providerDatasetLimit() { return Number(this.reportProvider?.max_dataset_rows || 5000); },
		reportColumns() { return (this.columns || []).map((column) => ({ ...column, fieldtype: column.fieldtype || "Data", clickable: ["name", "cashier", "expense_category", "review_action"].includes(column.fieldname) })); },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.expense_review.get_expense_review_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) }; this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || ""; this.canReview = Boolean(context.can_review); this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Expense Review controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.expense_review.search_expense_review_options", { kind, txt, company: this.filters.company }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, cashierSearch(txt) { return this.searchOptions("cashier", txt); }, categorySearch(txt) { return this.searchOptions("expense_category", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.branchName = ""; this.currentPage = 1; },
		onBranchSelected(option) { this.filters.branch = option.value; this.branchName = option.label || option.value; this.currentPage = 1; }, clearBranch() { this.filters.branch = ""; this.branchName = ""; this.currentPage = 1; },
		onCashierSelected(option) { this.filters.cashier = option.value; this.cashierLabel = option.label || option.value; this.currentPage = 1; }, clearCashier() { this.filters.cashier = ""; this.cashierLabel = ""; this.currentPage = 1; },
		providerFilters() { const { page_size: _pageSize, ...filters } = this.filters; return filters; },
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		async fetchData() {
			if (!this.filters.company) return; if (!this.reportProvider?.load) { this.error = "The shared EdgeSuite Expense Review provider is unavailable."; return; }
			this.loading = true; this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50); const start = Math.max(0, (this.currentPage - 1) * pageSize); const result = await this.reportProvider.load({ filters: this.providerFilters(), start, page_length: pageSize });
				this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.scan = result.metadata?.scan || {}; this.canReview = Boolean(result.metadata?.can_review ?? this.canReview); const totalRows = Number(result.total || this.rows.length); const totalPages = Math.max(1, Math.ceil(totalRows / pageSize)); this.pagination = { page: this.currentPage, page_size: pageSize, total_rows: totalRows, total_pages: totalPages, has_previous: this.currentPage > 1, has_next: this.currentPage < totalPages };
			} catch (error) { this.rows = []; this.columns = []; this.summary = []; this.error = errorMessage(error, "Expense Review failed to load."); }
			finally { this.loading = false; }
		},
		goToPage(page) { const next = Math.max(1, Number(page || 1)); if (next === this.currentPage) return; this.currentPage = next; this.fetchData(); }, setPageSize(pageSize) { this.filters.page_size = Number(pageSize || 50); this.currentPage = 1; this.fetchData(); }, rowKey(row, index) { return row.name || `expense-review:${index}`; },
		handleCellClick(payload) { const column = payload?.column; const row = payload?.row; if (!column || !row) return; const value = row[column.fieldname]; if (!value) return; if (column.fieldname === "name") frappe.set_route("Form", "RetailEdge Cashier Expense", value); else if (column.fieldname === "cashier") frappe.set_route("Form", "User", value); else if (column.fieldname === "expense_category") frappe.set_route("Form", "RetailEdge Expense Category", value); else if (column.fieldname === "review_action") this.openReviewDialog(row); },
		openReviewDialog(row) {
			if (!this.canReview) { frappe.msgprint({ title: __("Read-only access"), message: __("You do not have reviewer permission for cashier expense actions."), indicator: "orange" }); return; }
			frappe.prompt([
				{ fieldname: "action", label: __("Review Action"), fieldtype: "Select", options: "Include in Daily Audit\nExclude from Daily Audit\nNeeds Clarification", reqd: 1 },
				{ fieldname: "note", label: __("Note / Reason"), fieldtype: "Small Text", description: __("A reason is required when excluding an expense.") },
			], async (values) => {
				const actionMap = { "Include in Daily Audit": "include", "Exclude from Daily Audit": "exclude", "Needs Clarification": "clarify" }; const action = actionMap[values.action]; if (action === "exclude" && !String(values.note || "").trim()) { frappe.msgprint(__("A reason is required to exclude an expense.")); return; }
				try { await callMethod("retailedge.expense_review.apply_expense_review_action", { expense_name: row.name, action, note: values.note || "" }); frappe.show_alert({ message: __("Expense review updated."), indicator: "green" }); await this.fetchData(); } catch (error) { frappe.msgprint({ title: __("Expense Review Failed"), message: errorMessage(error, "The expense review action failed."), indicator: "red" }); }
			}, __("Review Expense"), __("Apply"));
		},
		formatCell(value, column) { if (value === null || value === undefined || value === "") return "—"; if (column.fieldtype === "Currency") { try { return frappe.format(Number(value), { fieldtype: "Currency" }); } catch (_error) { return Number(value).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } } if (column.fieldtype === "Check") return Number(value) ? __("Yes") : __("No"); if (column.fieldtype === "Date") { try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } } return String(value); },
	},
};
</script>

<style scoped>
.review-fallback { margin:20px; padding:24px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); display:flex; flex-direction:column; gap:8px; }
.review-filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:var(--edge-space-md,16px); align-items:end; width:100%; }
.advanced-filters { margin-top:var(--edge-space-md,16px); }
.advanced-filters summary { cursor:pointer; font-weight:600; color:var(--edge-text,#101828); }
.advanced-grid { margin-top:var(--edge-space-sm,10px); }
.edge-field { display:flex; flex-direction:column; gap:6px; min-width:0; }
.edge-field-label { font-size:.78rem; font-weight:600; color:var(--edge-text-muted,#667085); }
.edge-input,.edge-primary-button { min-height:38px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); padding:0 10px; }
.edge-primary-button { background:var(--edge-primary,#0f766e); color:#fff; border-color:var(--edge-primary,#0f766e); font-weight:600; cursor:pointer; }
.edge-primary-button:disabled { opacity:.55; cursor:not-allowed; }
@media (max-width:1180px) { .review-filter-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media (max-width:860px) { .review-filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:560px) { .review-filter-grid { grid-template-columns:1fr; } }
</style>