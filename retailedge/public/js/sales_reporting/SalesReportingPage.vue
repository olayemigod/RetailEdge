<template>
	<div v-if="!edgeUIValid" class="sales-report-fallback">
		<strong>Sales reporting could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		:title="config.title"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		:activeRoute="activeRoute"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					eyebrow="Sales Intelligence"
					:title="config.title"
					:subtitle="config.subtitle"
				>
					<template #actions>
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
					<div class="sales-filter-grid">
						<EdgeLinkField
							v-model="filters.company"
							label="Company"
							required
							placeholder="Search company"
							:searcher="companySearch"
							@select="onCompanySelected"
						/>
						<label class="edge-field">
							<span class="edge-field-label">Date Range</span>
							<select v-model="filters.date_range_preset" class="edge-input" @change="onPresetChange">
								<option v-for="preset in datePresets" :key="preset" :value="preset">{{ preset }}</option>
							</select>
						</label>
						<label class="edge-field">
							<span class="edge-field-label">From Date</span>
							<input v-model="filters.from_date" type="date" class="edge-input" @change="onDateChange" />
						</label>
						<label class="edge-field">
							<span class="edge-field-label">To Date</span>
							<input v-model="filters.to_date" type="date" class="edge-input" @change="onDateChange" />
						</label>
						<EdgeLinkField
							v-model="filters.branch"
							label="Branch"
							placeholder="All permitted branches"
							:searcher="branchSearch"
							@select="onBranchSelected"
							@clear="clearBranch"
						/>
						<EdgeLinkField
							v-model="filters.customer"
							:selectedLabel="customerLabel"
							label="Customer"
							placeholder="All customers"
							:searcher="customerSearch"
							@select="onCustomerSelected"
							@clear="customerLabel = ''"
						/>
						<label class="edge-field">
							<span class="edge-field-label">Invoice Type</span>
							<select v-model="filters.invoice_kind" class="edge-input">
								<option value="All">All</option>
								<option value="Sales">Sales</option>
								<option value="Returns">Returns</option>
							</select>
						</label>
						<div class="filter-action">
							<button class="edge-primary-button" type="button" :disabled="loading || !requiredReady" @click="applyFilters">
								{{ loading ? "Loading…" : "Apply Filters" }}
							</button>
						</div>
					</div>

					<details class="advanced-filters">
						<summary>More filters</summary>
						<div class="sales-filter-grid advanced-grid">
							<EdgeLinkField
								v-model="filters.item_group"
								label="Item Group"
								placeholder="All item groups"
								:searcher="itemGroupSearch"
								@select="onItemGroupSelected"
								@clear="clearItemGroup"
							/>
							<EdgeLinkField
								v-model="filters.item_code"
								:selectedLabel="itemLabel"
								label="Item"
								placeholder="All items"
								:searcher="itemSearch"
								@select="onItemSelected"
								@clear="itemLabel = ''"
							/>
							<EdgeLinkField
								v-model="filters.salesperson"
								label="Salesperson"
								placeholder="All salespeople"
								:searcher="salespersonSearch"
							/>
							<EdgeLinkField
								v-model="filters.warehouse"
								label="Warehouse"
								placeholder="All warehouses in scope"
								:searcher="warehouseSearch"
								@select="onWarehouseSelected"
							/>
							<label class="edge-field">
								<span class="edge-field-label">Invoice Status</span>
								<select v-model="filters.status" class="edge-input">
									<option value="">All statuses</option>
									<option v-for="status in invoiceStatuses" :key="status" :value="status">{{ status }}</option>
								</select>
							</label>
						</div>
					</details>
				</EdgeFilterBar>
			</template>

			<EdgeLoadingState v-if="metadataLoading" message="Loading Sales report controls…" />
			<EdgeErrorState v-else-if="error" title="Sales report failed to load" :message="error" actionLabel="Try again" @retry="fetchData" />
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
					<span>{{ pagination.total_rows || rows.length }} result{{ (pagination.total_rows || rows.length) === 1 ? "" : "s" }}</span>
					<span v-if="scan.invoices !== undefined">{{ scan.invoices }} submitted invoice{{ scan.invoices === 1 ? "" : "s" }} scanned</span>
					<span v-if="scan.item_rows !== undefined">{{ scan.item_rows }} item row{{ scan.item_rows === 1 ? "" : "s" }} scanned</span>
					<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				</div>

				<div v-if="rows.length" class="sales-table-card">
					<div class="sales-table-wrap">
						<table class="sales-table">
							<thead>
								<tr>
									<th v-for="column in columns" :key="column.fieldname" :class="{ number: isNumericColumn(column) }">{{ column.label }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(row, index) in rows" :key="rowKey(row, index)">
									<td v-for="column in columns" :key="column.fieldname" :class="{ number: isNumericColumn(column) }">
										<button v-if="isDrilldown(column, row)" type="button" class="doc-link" @click="openDrilldown(column, row)">
											{{ formatCell(row[column.fieldname], column) }}
										</button>
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
					title="No matching sales"
					description="Adjust the date range or filters and try again."
				/>
				<EdgeLoadingState v-if="loading" message="Loading Sales report…" />
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

const REPORT_CONFIG = {
	sales_by_item: {
		title: "Sales by Item",
		subtitle: "Understand what is selling, what is being returned, and the net sales contribution of each item.",
		endpoint: "retailedge.sales_reporting.get_sales_by_item",
		exportEndpoint: "retailedge.sales_reporting.get_sales_by_item_export",
		route: "/app/sales-by-item",
		filename: "RetailEdge Sales by Item",
	},
	sales_invoice_register: {
		title: "Sales Invoice Register",
		subtitle: "A clear invoice-level view of submitted sales, returns, taxes, and outstanding balances.",
		endpoint: "retailedge.sales_reporting.get_sales_invoice_register",
		exportEndpoint: "retailedge.sales_reporting.get_sales_invoice_register_export",
		route: "/app/sales-invoice-register",
		filename: "RetailEdge Sales Invoice Register",
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
	name: "SalesReportingPage",
	props: {
		reportType: { type: String, default: "sales_by_item" },
	},
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
			scan: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			customerLabel: "",
			itemLabel: "",
			filters: {
				company: "",
				date_range_preset: "This Month",
				from_date: "",
				to_date: "",
				branch: "",
				customer: "",
				item_code: "",
				item_group: "",
				salesperson: "",
				warehouse: "",
				status: "",
				invoice_kind: "All",
				page_size: 50,
			},
			currentPage: 1,
			datePresets: [
				"This Month", "Today", "Yesterday", "This Week", "This Quarter", "This Year",
				"Last Week", "Last Month", "Last Quarter", "Last Year", "Custom Period",
			],
			invoiceStatuses: ["Paid", "Unpaid", "Overdue", "Partly Paid", "Return", "Credit Note"],
		};
	},
	computed: {
		config() {
			return REPORT_CONFIG[this.reportType] || REPORT_CONFIG.sales_by_item;
		},
		activeRoute() {
			return this.config.route;
		},
		requiredReady() {
			return Boolean(this.filters.company && this.filters.from_date && this.filters.to_date);
		},
		exportDataset() {
			return {
				title: this.config.title,
				filename: `${this.config.filename} ${this.filters.from_date || ""} to ${this.filters.to_date || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: [
					{ label: "Company Currency", value: this.companyCurrency },
					{ label: "Source", value: "Submitted ERPNext Sales Invoices" },
				],
			};
		},
		exportFilters() {
			const labels = {
				company: "Company", from_date: "From Date", to_date: "To Date", branch: "Branch",
				customer: "Customer", item_group: "Item Group", item_code: "Item", salesperson: "Salesperson",
				warehouse: "Warehouse", invoice_kind: "Invoice Type", status: "Invoice Status",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
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
					callMethod("retailedge.sales_reporting.get_sales_reporting_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.requiredReady) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Sales report controls.");
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
			const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
				item_group: this.filters.item_group,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		customerSearch(txt) { return this.searchOptions("customer", txt); },
		itemGroupSearch(txt) { return this.searchOptions("item_group", txt); },
		itemSearch(txt) { return this.searchOptions("item", txt); },
		salespersonSearch(txt) { return this.searchOptions("salesperson", txt); },
		warehouseSearch(txt) { return this.searchOptions("warehouse", txt); },
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.warehouse = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.filters.warehouse = "";
			this.branchName = option.label || option.value;
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.filters.warehouse = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onCustomerSelected(option) {
			this.filters.customer = option.value;
			this.customerLabel = option.label || option.value;
			this.currentPage = 1;
		},
		onItemGroupSelected(option) {
			this.filters.item_group = option.value;
			this.filters.item_code = "";
			this.itemLabel = "";
			this.currentPage = 1;
		},
		clearItemGroup() {
			this.filters.item_group = "";
			this.filters.item_code = "";
			this.itemLabel = "";
			this.currentPage = 1;
		},
		onItemSelected(option) {
			this.filters.item_code = option.value;
			this.itemLabel = option.label || option.value;
			if (!this.filters.item_group && option.raw?.item_group) this.filters.item_group = option.raw.item_group;
			this.currentPage = 1;
		},
		async onWarehouseSelected(option) {
			this.filters.warehouse = option.value;
			this.currentPage = 1;
			if (!this.filters.company) return;
			try {
				const resolved = await callMethod("retailedge.guided_entry_context.resolve_branch_warehouse_selection", {
					company: this.filters.company,
					branch: this.filters.branch,
					warehouse: this.filters.warehouse,
					preference: "default",
				});
				if (resolved.branch) {
					this.filters.branch = resolved.branch;
					this.branchName = resolved.branch;
				}
			} catch (error) {
				this.filters.warehouse = "";
				this.error = errorMessage(error, "The selected Warehouse is not valid for this sales context.");
			}
		},
		async onPresetChange() {
			if (this.filters.date_range_preset === "Custom Period") return;
			const dates = window.retailedge?.getPresetDates?.(this.filters.date_range_preset);
			if (!dates) return;
			this.filters.from_date = dates.from_date;
			this.filters.to_date = dates.to_date;
			this.currentPage = 1;
		},
		onDateChange() {
			this.filters.date_range_preset = "Custom Period";
			this.currentPage = 1;
		},
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		async fetchData() {
			if (!this.requiredReady) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(this.config.endpoint, {
					filters: { ...this.filters },
					page: this.currentPage,
					page_size: this.filters.page_size,
				});
				this.rows = result.rows || [];
				this.columns = (result.columns || []).filter((column) => !column.hidden);
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scan = result.scan || {};
				this.companyCurrency = result.company_currency || this.companyCurrency;
				this.currentPage = this.pagination.page || this.currentPage;
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
			const result = await callMethod(this.config.exportEndpoint, { filters: { ...this.filters } });
			return {
				columns: result.columns || this.columns,
				rows: result.rows || [],
				summary: result.summary || this.summary,
				metadata: [
					{ label: "Company Currency", value: result.company_currency || this.companyCurrency },
					{ label: "Source", value: "Submitted ERPNext Sales Invoices" },
				],
			};
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
		rowKey(row, index) {
			return row.invoice || row.item_code || `${this.reportType}:${index}`;
		},
		isNumericColumn(column) {
			return ["Currency", "Float", "Int"].includes(column.fieldtype);
		},
		isDrilldown(column, row) {
			if (!row?.[column.fieldname]) return false;
			return ["invoice", "item_code", "customer", "return_against"].includes(column.fieldname);
		},
		openDrilldown(column, row) {
			const value = row?.[column.fieldname];
			if (!value) return;
			if (["invoice", "return_against"].includes(column.fieldname)) frappe.set_route("Form", "Sales Invoice", value);
			else if (column.fieldname === "item_code") frappe.set_route("Form", "Item", value);
			else if (column.fieldname === "customer") frappe.set_route("Form", "Customer", value);
		},
		formatSummary(card) {
			return this.formatValue(card.value, card.datatype, this.companyCurrency);
		},
		formatCell(value, column) {
			return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency);
		},
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try {
					return frappe.format(number, { fieldtype: "Currency", options: currency || this.companyCurrency });
				} catch (_error) {
					return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
				}
			}
			if (fieldtype === "Float") {
				const number = Number(value);
				return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(value);
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); }
			}
			return String(value);
		},
	},
};
</script>

<style scoped>
.sales-report-fallback,
.state-wrap {
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

.sales-filter-grid {
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
.page-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d0d5dd);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 8px 10px;
	width: 100%;
}

.filter-action {
	display: flex;
	align-items: end;
}

.edge-primary-button {
	width: 100%;
	min-height: 38px;
	border: 0;
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-primary, #2563eb);
	color: #fff;
	font-weight: 600;
	padding: 8px 14px;
}

.edge-primary-button:disabled,
.page-button:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}

.advanced-filters {
	margin-top: var(--edge-space-md, 16px);
	border-top: 1px solid var(--edge-border, #e4e7ec);
	padding-top: 12px;
}

.advanced-filters summary {
	cursor: pointer;
	font-weight: 600;
	color: var(--edge-text-muted, #667085);
}

.advanced-grid { margin-top: 12px; }

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

.sales-table-card {
	border: 1px solid var(--edge-border, #e4e7ec);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	overflow: hidden;
}

.sales-table-wrap { overflow-x: auto; }

.sales-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.82rem;
}

.sales-table th,
.sales-table td {
	padding: 10px 12px;
	border-bottom: 1px solid var(--edge-border, #eaecf0);
	text-align: left;
	vertical-align: top;
	white-space: nowrap;
}

.sales-table th {
	background: var(--edge-bg, #f8fafc);
	color: var(--edge-text-muted, #667085);
	font-weight: 600;
}

.number {
	text-align: right !important;
	font-variant-numeric: tabular-nums;
}

.doc-link {
	appearance: none;
	border: 0;
	background: transparent;
	padding: 0;
	color: var(--edge-primary, #2563eb);
	font: inherit;
	font-weight: 600;
	cursor: pointer;
}

.doc-link:hover { text-decoration: underline; }

.pagination-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 12px;
	padding: 12px 14px;
	border-top: 1px solid var(--edge-border, #e4e7ec);
}

.pagination-actions {
	display: flex;
	gap: 8px;
	align-items: center;
}

.page-size,
.page-button {
	width: auto;
	min-height: 34px;
	padding: 6px 10px;
}

.page-button { cursor: pointer; }

@media (max-width: 1180px) {
	.sales-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}

@media (max-width: 900px) {
	.sales-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 640px) {
	.sales-filter-grid { grid-template-columns: 1fr; }
	.pagination-footer { align-items: stretch; flex-direction: column; }
	.pagination-actions { justify-content: space-between; }
}
</style>
