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
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					eyebrow="Expense Control"
					title="Expense Register"
					subtitle="Review cashier expenses by period, Branch, Category and status without loading the full expense history."
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
				</EdgePageHeader>
			</template>

			<template #filters>
				<EdgeFilterBar title="Filters">
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
				</EdgeFilterBar>
			</template>

			<EdgeLoadingState v-if="metadataLoading" message="Loading Expense Register controls…" />
			<EdgeErrorState
				v-else-if="error"
				title="Expense Register failed to load"
				:message="error"
				actionLabel="Try again"
				@retry="fetchData"
			/>
			<template v-else>
				<div v-if="summary.length" class="summary-grid">
					<EdgeStatCard
						v-for="card in summary"
						:key="card.label"
						:label="card.label"
						:value="formatSummary(card)"
					/>
				</div>

				<div v-if="rows.length" class="result-meta">
					<span>{{ pagination.total_rows || rows.length }} expense{{ (pagination.total_rows || rows.length) === 1 ? "" : "s" }}</span>
					<span>{{ scopeLabel }}</span>
					<span>{{ showCashier ? "Permitted cashier visibility" : "Your expenses only" }}</span>
				</div>

				<div v-if="rows.length" class="expense-card">
					<div class="expense-table-wrap">
						<table class="expense-table">
							<thead>
								<tr>
									<th v-for="column in columns" :key="column.fieldname" :class="{ number: isNumericColumn(column) }">
										{{ column.label }}
									</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in rows" :key="row.name">
									<td
										v-for="column in columns"
										:key="column.fieldname"
										:class="[
											{ number: isNumericColumn(column) },
											{ description: column.fieldname === 'description' },
										]"
									>
										<button
											v-if="column.fieldname === 'name'"
											type="button"
											class="doc-link"
											@click="openExpense(row.name)"
										>
											{{ row.name }}
										</button>
										<span v-else-if="column.fieldname === 'expense_status'" :class="statusClass(row.expense_status)">
											{{ row.expense_status || "Draft" }}
										</span>
										<span v-else-if="column.fieldname === 'posting_ready'">{{ row.posting_ready ? "Yes" : "No" }}</span>
										<span v-else>{{ formatCell(row[column.fieldname], column) }}</span>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div class="pagination-footer">
						<div>Page {{ pagination.page || currentPage }} of {{ pagination.total_pages || 1 }}</div>
						<div class="pagination-actions">
							<select v-model.number="filters.page_size" class="page-size" @change="changePageSize">
								<option :value="25">25 / page</option>
								<option :value="50">50 / page</option>
								<option :value="100">100 / page</option>
							</select>
							<button type="button" class="page-button" :disabled="!pagination.has_previous || loading" @click="changePage(-1)">Previous</button>
							<button type="button" class="page-button" :disabled="!pagination.has_next || loading" @click="changePage(1)">Next</button>
						</div>
					</div>
				</div>

				<EdgeEmptyState
					v-else-if="!loading"
					title="No expenses found"
					description="Adjust the date, Branch, Expense Category or status filters and try again."
				/>
				<EdgeLoadingState v-if="loading" message="Loading expenses…" />
			</template>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgePageLayout",
	"EdgePageHeader",
	"EdgeFilterBar",
	"EdgeStatCard",
	"EdgeLoadingState",
	"EdgeEmptyState",
	"EdgeErrorState",
	"EdgeLinkField",
	"EdgeExportMenu",
];

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
	name: "ExpenseRegister",
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
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
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
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.expense_register.get_expense_register", {
					filters: { ...this.filters },
					page: this.currentPage,
					page_size: this.filters.page_size,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scope = result.scope || {};
				this.currentPage = this.pagination.page || this.currentPage;
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
			const result = await callMethod("retailedge.expense_register.get_expense_register_export", {
				filters: { ...this.filters },
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
		changePage(direction) {
			const next = this.currentPage + direction;
			if (next < 1) return;
			this.currentPage = next;
			this.fetchData();
		},
		changePageSize() {
			this.currentPage = 1;
			this.fetchData();
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
		isNumericColumn(column) {
			return ["Currency", "Float", "Int"].includes(column.type || column.fieldtype);
		},
		statusClass(status) {
			return ["expense-status", `expense-status--${String(status || "draft").toLowerCase().replace(/\s+/g, "-")}`];
		},
		formatSummary(card) {
			return this.formatValue(card.value, card.type || card.datatype);
		},
		formatCell(value, column) {
			return this.formatValue(value, column.type || column.fieldtype);
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
	padding: 24px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 8px;
}

:deep(.edge-filter-bar) {
	align-items: stretch;
	flex-direction: column;
}

:deep(.edge-filter-bar__fields) {
	display: block;
	width: 100%;
}

.expense-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}

.edge-field {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}

.edge-field-label {
	font-size: 0.78rem;
	font-weight: 600;
	color: var(--edge-text-muted, #667085);
}

.edge-input,
.page-size,
.page-button,
.primary-action,
.secondary-action {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d0d5dd);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 8px 10px;
}

.edge-input,
.page-size { width: 100%; }

.primary-action {
	border-color: transparent;
	background: var(--edge-primary, #2563eb);
	color: #fff;
	font-weight: 600;
	padding-inline: 14px;
}

.secondary-action {
	font-weight: 600;
	padding-inline: 14px;
}

.primary-action.full { width: 100%; }
.primary-action:disabled,
.page-button:disabled { opacity: 0.55; cursor: not-allowed; }

.filter-note {
	min-height: 38px;
	display: flex;
	flex-direction: column;
	justify-content: center;
	gap: 2px;
	font-size: 0.72rem;
	color: var(--edge-text-muted, #667085);
}

.filter-action { display: flex; align-items: end; }

.summary-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: var(--edge-space-md, 16px);
	margin: 0 0 var(--edge-space-lg, 20px);
}

.result-meta {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
	margin-bottom: 10px;
}

.expense-card {
	border: 1px solid var(--edge-border, #e4e7ec);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	overflow: hidden;
}

.expense-table-wrap { overflow-x: auto; }
.expense-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.expense-table th,
.expense-table td {
	padding: 10px 12px;
	border-bottom: 1px solid var(--edge-border, #eaecf0);
	text-align: left;
	vertical-align: top;
	white-space: nowrap;
}

.expense-table th {
	background: var(--edge-bg, #f8fafc);
	color: var(--edge-text-muted, #667085);
	font-weight: 600;
}

.expense-table td.description {
	white-space: normal;
	min-width: 220px;
	max-width: 360px;
}

.number { text-align: right !important; font-variant-numeric: tabular-nums; }
.doc-link {
	appearance: none;
	border: 0;
	background: none;
	padding: 0;
	color: var(--edge-primary, #2563eb);
	font-weight: 600;
	cursor: pointer;
}

.expense-status {
	display: inline-flex;
	align-items: center;
	min-height: 24px;
	padding: 2px 8px;
	border-radius: 999px;
	background: var(--edge-bg, #f2f4f7);
	font-weight: 600;
}

.expense-status--submitted,
.expense-status--pending-ledger { background: #fffaeb; color: #b54708; }
.expense-status--posted { background: #ecfdf3; color: #027a48; }
.expense-status--rejected,
.expense-status--cancelled { background: #fef3f2; color: #b42318; }

.pagination-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 12px;
	padding: 12px;
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}

.pagination-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}

.page-size { width: auto; min-width: 110px; }
.page-button { width: auto; min-width: 84px; }

@media (max-width: 1100px) {
	.expense-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
	.expense-filter-grid { grid-template-columns: 1fr; }
	.pagination-footer { align-items: stretch; flex-direction: column; }
	.pagination-actions { flex-wrap: wrap; }
}
</style>
