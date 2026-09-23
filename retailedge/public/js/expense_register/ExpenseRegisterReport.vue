<template>
	<div v-if="!edgeUIValid" class="expense-register-fallback">
		<strong>{{ config.title }} could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		:title="config.title"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		:activeRoute="config.route"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			:title="config.title"
			eyebrow="Expense Control"
			:subtitle="config.subtitle"
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:sort="reportSort"
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
			@sort-change="handleSortChange"
			@cell-click="openReportCell"
		>
			<template #actions>
				<button v-if="config.analysis" type="button" class="secondary-action" @click="openExpenseRegister">Expense Register</button>
				<template v-else>
					<button type="button" class="secondary-action" @click="openExpenseCategories">Expense Categories</button>
					<button type="button" class="primary-action" @click="recordExpense">{{ consolidatedViewAvailable && hasPageTarget("business-expenses") ? "Record Business Expense" : "Record Cashier Expense" }}</button>
				</template>
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
					<EdgeDropdown v-if="config.analysis" v-model="analysisPreset" :options="analysisPresets" label="Analysis View" @change="onAnalysisPresetChange" />
					<EdgeDropdown v-if="config.analysis" v-model="filters.group_by" :options="groupByOptions" label="Group By" @change="onAnalysisGroupChange" />
					<EdgeDropdown v-if="consolidatedViewAvailable && !config.analysis" v-model="filters.view_mode" :options="[{ value: 'consolidated', label: 'Consolidated business expenses' }, { value: 'cashier', label: 'Cashier / POS expenses only' }]" label="View" @change="onViewModeChanged" />
					<EdgeDropdown v-if="consolidatedViewAvailable && (config.analysis || filters.view_mode === 'consolidated')" v-model="filters.source_type" :options="sourceTypes" label="Source" placeholder="All expense sources" />
					<label
						v-if="consolidatedViewAvailable && (config.analysis || filters.view_mode === 'consolidated')"
						class="edge-check-field"
					>
						<input
							v-model="filters.include_unposted_cashier_expenses"
							type="checkbox"
							:true-value="1"
							:false-value="0"
						/>
						<span>
							<strong>Include unposted Cashier Expenses</strong>
							<small>Show operational exposure separately from posted expense totals.</small>
						</span>
					</label>
					<EdgeDropdown v-model="filters.expense_status" :options="statuses" label="Status" placeholder="All active statuses" />
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
						<span v-if="config.analysis">Posted accounting expense is kept separate from optional unposted cashier exposure</span>
						<span v-else-if="!showCashier">Cashier view is limited to your own expenses</span>
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
				<span v-if="config.analysis">Grouped by {{ filters.group_by }}</span>
				<span v-else>{{ showCashier ? "Permitted cashier visibility" : "Your expenses only" }}</span>
				<span v-if="config.analysis">Source: governed consolidated Expense Register</span>
				<span v-else>{{ filters.view_mode === "consolidated" ? "Sources: Cashier/POS + posted business expenses" : "Source: Cashier Expense" }}</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
	<SimpleCashierExpenseDialog
		:open="cashierExpenseOpen"
		:nativeFallbackEnabled="false"
		@close="cashierExpenseOpen = false"
		@saved="handleCashierExpenseSaved"
	/>
</template>

<script>
import SimpleCashierExpenseDialog from "../retailedge_business_hub/SimpleCashierExpenseDialog.vue";
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgeReportShell",
	"EdgeLinkField",
	"EdgeExportMenu",
	"EdgeDropdown",
];

const REPORT_PRODUCT = "RetailEdge";
const REPORT_CONFIG = {
	expense_register: {
		title: "Expense Register",
		subtitle: "Review cashier and consolidated business expenses by period, Branch, Category and status.",
		providerKey: "expense-register",
		route: "/app/expense-register",
		analysis: false,
	},
	expense_analysis: {
		title: "Expense Analysis",
		subtitle: "Group governed business expense activity by time, category, account, Branch, source, cost center, payment account or cashier.",
		providerKey: "expense-analysis",
		route: "/app/expense-analysis",
		analysis: true,
	},
};

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
	props: { reportType: { type: String, default: "expense_register" } },
	components: {
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
		SimpleCashierExpenseDialog,
	},
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			rows: [],
			columns: [],
			summary: [], reportSort: null,
			pagination: {},
			scope: {},
			menuItems: [],
			canUseNativeDesk: false,
			cashierExpenseOpen: false,
			tenantName: "",
			branchName: "",
			userName: "",
			showCashier: false,
			consolidatedViewAvailable: false,
			sourceTypes: [],
			statuses: [],
			dateRangeLimit: 366,
			categoryLabel: "",
			analysisPreset: "Expense Trend",
			analysisPresets: [
				"Expense Trend",
				"Expenses by Category",
				"Expenses by Expense Account",
				"Expenses by Branch",
				"Expenses by Source",
				"Expenses by Cost Center",
				"Expenses by Payment Account",
				"Expenses by Cashier",
				"Expenses by Status",
				"Daily Expenses",
				"Weekly Expenses",
				"Quarterly Expenses",
				"Yearly Expenses",
				"Custom",
			],
			groupByOptions: [
				"Day", "Week", "Month", "Quarter", "Year", "Expense Category", "Expense Account",
				"Branch", "Source", "Cost Center", "Payment Account", "Cashier", "Expense Status",
			],
			filters: {
				company: "",
				branch: "",
				from_date: "",
				to_date: "",
				expense_category: "",
				expense_status: "",
				source_type: "",
				view_mode: "cashier",
				include_unposted_cashier_expenses: 0,
				group_by: "Month",
				page_size: 50,
			},
			currentPage: 1,
		};
	},
	computed: {
		config() { return REPORT_CONFIG[this.reportType] || REPORT_CONFIG.expense_register; },
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey)
				|| null;
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: !this.config.analysis && column.fieldname === "name",
			}));
		},
		scopeLabel() {
			if (this.scope.branch) return `Branch: ${this.scope.branch}`;
			if (this.scope.company) return `Company: ${this.scope.company}`;
			return this.filters.company ? `Company: ${this.filters.company}` : "Current permitted scope";
		},
		exportDataset() {
			return {
				title: this.config.title,
				filename: (`ProcessEdge Retail ${this.config.title} ${this.filters.company || ""}`).trim(),
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
				source_type: "Source",
				view_mode: "View",
				include_unposted_cashier_expenses: "Include Unposted Cashier Expenses",
				group_by: "Group By",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({
					label,
					value: key === "include_unposted_cashier_expenses"
						? (this.filters[key] ? "Yes" : "No")
						: this.filters[key],
				}))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() {
			return [
				{ label: "Source", value: this.config.analysis ? "Governed consolidated Expense Register" : (this.filters.view_mode === "consolidated" ? "Consolidated business expenses" : "Cashier Expense") },
				{ label: "Scope", value: this.scopeLabel },
				{ label: "Grouping", value: this.config.analysis ? this.filters.group_by : "Transaction detail" },
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
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.expense_register.get_expense_register_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				const hubHandoff = window.retailedgeConsumeBusinessHubRouteOptions?.(this.config.providerKey) || {};
				this.filters = { ...this.filters, ...hubHandoff };
				if (this.config.analysis) this.filters.view_mode = "consolidated";
				this.tenantName = hubHandoff.company || context.tenant_name || this.filters.company || "";
				this.branchName = hubHandoff.branch || context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.showCashier = Boolean(Number(context.show_cashier));
				this.consolidatedViewAvailable = Boolean(Number(context.consolidated_view_available));
				this.sourceTypes = context.source_types || [];
				this.statuses = context.statuses || [];
				this.dateRangeLimit = Number(context.limits?.date_range_days || 366);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, `Failed to load ${this.config.title} controls.`);
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
			if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		hasPageTarget(target) {
			return Boolean(
				target
				&& this.menuItems
					.flatMap((group) => group.items || [])
					.some((item) => item.target_type === "Page" && item.target === target)
			);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.expense_register.search_expense_register_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
				view_mode: this.filters.view_mode,
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
		onViewModeChanged() {
			if (this.filters.view_mode !== "consolidated") {
				this.filters.source_type = "";
				this.filters.include_unposted_cashier_expenses = 0;
			}
			this.currentPage = 1;
		},
		onAnalysisPresetChange() {
			const groups = {
				"Expense Trend": "Month",
				"Expenses by Category": "Expense Category",
				"Expenses by Expense Account": "Expense Account",
				"Expenses by Branch": "Branch",
				"Expenses by Source": "Source",
				"Expenses by Cost Center": "Cost Center",
				"Expenses by Payment Account": "Payment Account",
				"Expenses by Cashier": "Cashier",
				"Expenses by Status": "Expense Status",
				"Daily Expenses": "Day",
				"Weekly Expenses": "Week",
				"Quarterly Expenses": "Quarter",
				"Yearly Expenses": "Year",
			};
			if (groups[this.analysisPreset]) this.filters.group_by = groups[this.analysisPreset];
			this.currentPage = 1;
		},
		onAnalysisGroupChange() {
			const presets = {
				Month: "Expense Trend",
				"Expense Category": "Expenses by Category",
				"Expense Account": "Expenses by Expense Account",
				Branch: "Expenses by Branch",
				Source: "Expenses by Source",
				"Cost Center": "Expenses by Cost Center",
				"Payment Account": "Expenses by Payment Account",
				Cashier: "Expenses by Cashier",
				"Expense Status": "Expenses by Status",
				Day: "Daily Expenses",
				Week: "Weekly Expenses",
				Quarter: "Quarterly Expenses",
				Year: "Yearly Expenses",
			};
			this.analysisPreset = presets[this.filters.group_by] || "Custom";
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
			if (this.config.analysis) filters.view_mode = "consolidated";
			else delete filters.group_by;
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error = `The ${this.config.title} reporting service is unavailable.`;
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
					page_length: pageSize, sort: this.reportSort,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || []; this.reportSort = result.sort || null;
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
				this.error = errorMessage(error, `${this.config.title} failed to load.`);
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
			const fallbackMethod = this.config.analysis
				? "retailedge.expense_analysis.get_expense_analysis_export"
				: "retailedge.expense_register.get_expense_register_export";
			const result = await callMethod(fallbackMethod, {
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
		handleSortChange(sort) { this.reportSort = sort || null; this.currentPage = 1; return this.fetchData(); },
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
		rowKey(row, index) {
			return row?.group_key || row?.name || `${this.reportType}:${index}`;
		},
		openReportCell(payload) {
			if (this.config.analysis) return;
			if (["name", "source_reference"].includes(payload?.column?.fieldname) && payload?.row) this.openExpense(payload.row);
		},
		openExpense(row) {
			if (!row) return;
			if (row.source_doctype === "RetailEdge Business Expense" && this.hasPageTarget("business-expenses")) {
				frappe.route_options = { business_expense: row.source_reference || "" };
				frappe.set_route("business-expenses");
				return;
			}
			if (row.source_doctype === "Purchase Invoice" && this.hasPageTarget("purchase-register")) {
				frappe.route_options = { purchase_invoice: row.source_reference || "" };
				frappe.set_route("purchase-register");
				return;
			}
			if (this.canUseNativeDesk && row.source_doctype && row.source_reference) {
				frappe.set_route("Form", row.source_doctype, row.source_reference);
			}
		},
		recordExpense() {
			if (this.consolidatedViewAvailable && this.hasPageTarget("business-expenses")) {
				frappe.route_options = { action: "new" };
				frappe.set_route("business-expenses");
				return;
			}
			this.cashierExpenseOpen = true;
		},
		handleCashierExpenseSaved() {
			this.cashierExpenseOpen = false;
			this.fetchData();
		},
		openExpenseCategories() {
			if (!this.hasPageTarget("retailedge-setup")) return;
			frappe.route_options = { setup_resource: "expense-categories" };
			frappe.set_route("retailedge-setup");
		},
		openExpenseRegister() {
			frappe.set_route("expense-register");
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
				try { return window.retailedge.formatPlainValue(number, { fieldtype: "Currency" }); }
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
.edge-check-field { display: flex; align-items: flex-start; gap: 8px; min-width: 0; padding: 8px 0; }
.edge-check-field span { display: grid; gap: 2px; }
.edge-check-field small { color: var(--edge-text-muted, #667085); }
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
