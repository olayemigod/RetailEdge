<template>
	<div v-if="!edgeUIValid" class="expense-register-fallback">
		<strong>Expense Register could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Expense Register"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/expense-register"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Expense Register"
			eyebrow="Expense Control"
			subtitle="Review cashier expenses by period, Branch, Category and status without loading the full expense history."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No expenses found"
			emptyDescription="Adjust the date, Branch, Expense Category or status filters and try again."
			loadingMessage="Loading expenses…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="openReportCell"
		>
			<template #actions>
				<button type="button" class="secondary-action" @click="openExpenseCategories">Expense Categories</button>
				<button type="button" class="primary-action" @click="recordExpense">Record Expense</button>
				<EdgeExportMenu
					v-if="rows.length"
					:dataset="exportDataset"
					:loadDataset="loadExportDataset"
				/>
			</template>

			<template #filters>
				<div class="expense-filter-grid">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						required
						placeholder="Search company"
						:searcher="companySearch"
						@select="onCompanySelected"
					/>
					<EdgeLinkField
						v-model="filters.branch"
						label="Branch"
						placeholder="All permitted branches"
						:searcher="branchSearch"
						@select="onBranchSelected"
						@clear="clearBranch"
					/>
					<EdgeLinkField
						v-model="filters.expense_category"
						:selectedLabel="categoryLabel"
						label="Expense Category"
						placeholder="All categories"
						:searcher="categorySearch"
						@select="onCategorySelected"
						@clear="clearCategory"
					/>
					<label class="edge-field">
						<span class="edge-field-label">Status</span>
						<select v-model="filters.expense_status" class="edge-input">
							<option value="">All active statuses</option>
							<option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
						</select>
					</label>
					<label class="edge-field">
						<span class="edge-field-label">From Date</span>
						<input v-model="filters.from_date" type="date" class="edge-input" />
					</label>
					<label class="edge-field">
						<span class="edge-field-label">To Date</span>
						<input v-model="filters.to_date" type="date" class="edge-input" />
					</label>
					<div class="filter-note">
						<span>{{ dateRangeLimit }}-day maximum per request</span>
						<span v-if="!showCashier">Cashier view is limited to your own expenses</span>
					</div>
					<div class="filter-action">
						<button class="primary-action full" type="button" :disabled="loading || !filters.company" @click="applyFilters">
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span>{{ scopeLabel }}</span>
				<span>{{ showCashier ? "Permitted cashier visibility" : "Your expenses only" }}</span>
				<span>Source: RetailEdge Cashier Expense</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgeReportShell",
	"EdgeLinkField",
	"EdgeExportMenu",
];

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "expense-register";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

export default {
	name: "ExpenseRegisterReport",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			rows: [],
			columns: [],
			summary: [],
			pagination: {},
			scope: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			showCashier: false,
			statuses: [],
			dateRangeLimit: 366,
			categoryLabel: "",
			filters: {
				company: "",
				branch: "",
				from_date: "",
				to_date: "",
				expense_category: "",
				expense_status: "",
				page_size: 50,
			},
			currentPage: 1,
		};
	},
	computed: {
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| null;
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: column.fieldname === "name",
			}));
		},
		scopeLabel() {
			if (this.scope.branch) return `Branch: ${this.scope.branch}`;
			if (this.scope.company) return `Company: ${this.scope.company}`;
			return this.filters.company ? `Company: ${this.filters.company}` : "Current permitted scope";
		},
		exportDataset() {
			return {
				title: "Expense Register",
				filename: `RetailEdge Expense Register ${this.filters.company || ""}`.trim(),
				columns: this.exportColumns(this.columns),
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.exportSummary(this.summary),
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company",
				branch: "Branch",
				from_date: "From Date",
				to_date: "To Date",
				expense_category: "Expense Category",
				expense_status: "Status",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() {
			return [
				{ label: "Source", value: "RetailEdge Cashier Expense" },
				{ label: "Scope", value: this.scopeLabel },
				{ label: "Cashier visibility", value: this.showCashier ? "Permitted scope" : "Current user only" },
			];
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() {
		this.fetchMetadata();
	},
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.expense_register.get_expense_register_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.showCashier = Boolean(Number(context.show_cashier));
				this.statuses = context.statuses || [];
				this.dateRangeLimit = Number(context.limits?.date_range_days || 366);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Expense Register controls.");
			} finally {
				this.metadataLoading = false;
			}
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const items = this.menuItems.flatMap((group) => group.items || []);
			const item = items.find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.expense_register.search_expense_register_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		categorySearch(txt) { return this.searchOptions("expense_category", txt); },
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.expense_category = "";
			this.branchName = "";
			this.categoryLabel = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.branchName = option.label || option.value;
			this.filters.expense_category = "";
			this.categoryLabel = "";
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
			this.filters.expense_category = "";
			this.categoryLabel = "";
			this.currentPage = 1;
		},
		onCategorySelected(option) {
			this.filters.expense_category = option.value;
			this.categoryLabel = option.label || option.value;
			this.currentPage = 1;
		},
		clearCategory() {
			this.filters.expense_category = "";
			this.categoryLabel = "";
			this.currentPage = 1;
		},
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		providerFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error = "The shared EdgeSuite Expense Register provider is unavailable.";
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50);
				const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({
					filters: this.providerFilters(),
					start,
					page_length: pageSize,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.scope = result.metadata?.scope || {};
				const totalRows = Number(result.total || this.rows.length);
				const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
				if (this.currentPage > totalPages) this.currentPage = totalPages;
				this.pagination = {
					page: this.currentPage,
					page_size: pageSize,
					total_rows: totalRows,
					total_pages: totalPages,
					has_previous: this.currentPage > 1,
					has_next: this.currentPage < totalPages,
				};
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = errorMessage(error, "Expense Register failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			if (this.reportProvider?.exportReport) {
				const result = await this.reportProvider.exportReport({ filters: this.providerFilters() });
				return {
					columns: this.exportColumns(result.columns || this.columns),
					rows: result.rows || [],
					summary: this.exportSummary(result.summary || this.summary),
					metadata: this.exportMetadata,
				};
			}
			const result = await callMethod("retailedge.expense_register.get_expense_register_export", {
				filters: this.providerFilters(),
			});
			return {
				columns: this.exportColumns(result.columns || this.columns),
				rows: result.rows || [],
				summary: this.exportSummary(result.summary || this.summary),
				metadata: this.exportMetadata,
			};
		},
		exportColumns(columns) {
			return (columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				options: column.options || column.doctype || undefined,
			}));
		},
		exportSummary(summary) {
			return (summary || []).map((card) => ({
				...card,
				datatype: card.datatype || card.type || "Data",
			}));
		},
		goToPage(page) {
			const next = Math.max(1, Number(page || 1));
			if (next === this.currentPage) return;
			this.currentPage = next;
			this.fetchData();
		},
		setPageSize(pageSize) {
			this.filters.page_size = Number(pageSize || 50);
			this.currentPage = 1;
			this.fetchData();
		},
		rowKey(row) {
			return row?.name || "";
		},
		openReportCell(payload) {
			if (payload?.column?.fieldname === "name" && payload.value) this.openExpense(payload.value);
		},
		openExpense(name) {
			if (name) frappe.set_route("Form", "RetailEdge Cashier Expense", name);
		},
		recordExpense() {
			frappe.new_doc("RetailEdge Cashier Expense");
		},
		openExpenseCategories() {
			frappe.set_route("List", "RetailEdge Expense Category");
		},
		formatCell(value, column) {
			if (column?.fieldname === "posting_ready") return value ? "Yes" : "No";
			if (column?.fieldname === "expense_status") return value || "Draft";
			return this.formatValue(value, column?.fieldtype || column?.type);
		},
		formatValue(value, fieldtype) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try { return frappe.format(number, { fieldtype: "Currency" }); }
				catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(String(value)); }
				catch (_error) { return String(value); }
			}
			return String(value);
		},
	},
};
</script>

<style scoped>
.expense-register-fallback {
	margin: 20px;
	padding: 16px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.expense-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}

.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
.edge-input,
.primary-action,
.secondary-action {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 0 10px;
}
.primary-action { background: var(--edge-primary, #1d4ed8); color: #fff; border-color: transparent; font-weight: 600; }
.secondary-action { font-weight: 600; cursor: pointer; }
.full { width: 100%; }
.filter-note { display: flex; flex-direction: column; gap: 3px; font-size: 0.76rem; color: var(--edge-text-muted, #667085); }

@media (max-width: 72rem) { .expense-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .expense-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 36rem) { .expense-filter-grid { grid-template-columns: 1fr; } }
</style>
