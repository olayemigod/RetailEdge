<template>
	<div v-if="!edgeUIValid" class="sales-report-fallback">
		<strong>Sales reporting could not start.</strong>
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
		:activeRoute="activeRoute"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			:title="config.title"
			eyebrow="Sales Intelligence"
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
			emptyTitle="No matching sales"
			emptyDescription="Adjust the date range or filters and try again."
			loadingMessage="Loading Sales report…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@sort-change="handleSortChange"
			@cell-click="openReportCell"
		>
			<template #actions>
				<EdgeExportMenu
					v-if="rows.length"
					:dataset="exportDataset"
					:loadDataset="loadExportDataset"
				/>
			</template>

			<template #filters>
				<div class="sales-filter-grid">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						required
						placeholder="Search company"
						:searcher="companySearch"
						@select="onCompanySelected"
					/>
					<EdgeSmartDateRange
						v-model="smartDate"
						label="Smart Date Range"
						:referenceDate="smartDateReference || null"
						dateOrder="DMY"
						@resolved="onSmartDateResolved"
					/>
					<EdgeDropdown v-model="filters.date_range_preset" :options="datePresets" label="Date Range" @change="onPresetChange" />
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
						@clear="clearCustomer"
					/>
					<EdgeDropdown v-model="filters.invoice_kind" :options="['All', 'Sales', 'Returns']" label="Invoice Type" />
					<EdgeDropdown
						v-if="config.analysis"
						v-model="analysisPreset"
						:options="analysisPresets"
						label="Analysis View"
						@change="onAnalysisPresetChange"
					/>
					<EdgeDropdown
						v-if="config.analysis"
						v-model="filters.group_by"
						:options="groupByOptions"
						label="Group By"
						@change="onAnalysisGroupChange"
					/>
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
							@clear="clearItem"
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
							@clear="filters.warehouse = ''"
						/>
						<EdgeDropdown v-model="filters.status" :options="invoiceStatuses" label="Invoice Status" placeholder="All statuses" />
					</div>
				</details>
			</template>

			<template #resultMeta>
				<span v-if="scan.invoices !== undefined">{{ scan.invoices }} submitted invoice{{ scan.invoices === 1 ? "" : "s" }} scanned</span>
				<span v-if="scan.item_rows !== undefined">{{ scan.item_rows }} item row{{ scan.item_rows === 1 ? "" : "s" }} scanned</span>
				<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				<span>Bounded server dataset · {{ providerDatasetLimit.toLocaleString() }} row cap</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu", "EdgeSmartDateRange", "EdgeDropdown"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_CONFIG = {
	sales_analysis: {
		title: "Sales Analysis",
		subtitle: "Group submitted sales by the business dimension that matters without creating separate reporting truth.",
		providerKey: "sales-analysis",
		route: "/app/sales-analysis",
		filename: "ProcessEdge Retail Sales Analysis",
		analysis: true,
	},
	sales_by_item: {
		title: "Sales by Item",
		subtitle: "Understand what is selling, what is being returned, and the net sales contribution of each item.",
		providerKey: "sales-by-item",
		route: "/app/sales-by-item",
		filename: "ProcessEdge Retail Sales by Item",
	},
	sales_invoice_register: {
		title: "Sales Invoice Register",
		subtitle: "A clear invoice-level view of submitted sales, returns, taxes, and outstanding balances.",
		providerKey: "sales-invoice-register",
		route: "/app/sales-invoice-register",
		filename: "ProcessEdge Retail Sales Invoice Register",
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
	name: "SalesReportingReport",
	props: { reportType: { type: String, default: "sales_by_item" } },
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
			summary: [], reportSort: null,
			pagination: {},
			scan: {},
			menuItems: [],
			canUseNativeDesk: false,
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			analysisPreset: "Sales Trend",
			customerLabel: "",
			itemLabel: "",
			smartDate: {},
			smartDateReference: "",
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
				group_by: "Month",
				page_size: 50,
			},
			currentPage: 1,
			datePresets: [
				"This Month", "Today", "Yesterday", "This Week", "This Quarter", "This Year",
				"Last Week", "Last Month", "Last Quarter", "Last Year", "Custom Period",
			],
			analysisPresets: [
				"Sales Trend",
				"Sales by Item",
				"Sales by Category",
				"Sales by Customer",
				"Sales by Customer Group",
				"Sales by Branch",
				"Sales by Salesperson",
				"Sales by Warehouse",
				"Daily Sales",
				"Weekly Sales",
				"Quarterly Sales",
				"Yearly Sales",
				"Custom",
			],
			groupByOptions: [
				"Day", "Week", "Month", "Quarter", "Year", "Item", "Item Group",
				"Customer", "Customer Group", "Branch", "Salesperson", "Warehouse",
			],
			invoiceStatuses: ["Paid", "Unpaid", "Overdue", "Partly Paid", "Return", "Credit Note"],
		};
	},
	computed: {
		config() { return REPORT_CONFIG[this.reportType] || REPORT_CONFIG.sales_by_item; },
		activeRoute() { return this.config.route; },
		requiredReady() { return Boolean(this.filters.company && this.filters.from_date && this.filters.to_date); },
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey)
				|| null;
		},
		providerDatasetLimit() { return Number(this.reportProvider?.max_dataset_rows || 0); },
		reportColumns() {
			return (this.columns || []).filter((column) => !column.hidden).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: this.canUseNativeDesk && ["invoice", "item_code", "customer", "return_against"].includes(column.fieldname),
			}));
		},
		exportDataset() {
			return {
				title: this.config.title,
				filename: `${this.config.filename} ${this.filters.from_date || ""} to ${this.filters.to_date || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company", from_date: "From Date", to_date: "To Date", branch: "Branch",
				customer: "Customer", item_group: "Item Group", item_code: "Item", salesperson: "Salesperson",
				warehouse: "Warehouse", invoice_kind: "Invoice Type", status: "Invoice Status", group_by: "Group By",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() {
			return [
				{ label: "Company Currency", value: this.companyCurrency },
				{ label: "Source", value: "Submitted ERPNext Sales Invoices" },
				{ label: "Pagination", value: "Bounded materialized server dataset" },
			];
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() { this.fetchMetadata(); },
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
				const hubHandoff = window.retailedgeConsumeBusinessHubRouteOptions?.(this.config.providerKey) || {};
				this.filters = { ...this.filters, ...hubHandoff };
				if (hubHandoff.from_date && hubHandoff.to_date) this.filters.date_range_preset = "Custom Period";
				this.smartDateReference = hubHandoff.to_date || context.default_filters?.to_date || this.filters.to_date || "";
				this.tenantName = hubHandoff.company || context.tenant_name || this.filters.company || "";
				this.branchName = hubHandoff.branch || context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);
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
			if ((item.target_type === "DocType" || item.target_type === "Report") && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", {
				kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group, from_date: this.filters.from_date, to_date: this.filters.to_date,
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
			this.filters.customer = "";
			this.customerLabel = "";
			this.filters.salesperson = "";
			this.filters.warehouse = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.filters.customer = "";
			this.customerLabel = "";
			this.filters.salesperson = "";
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
		clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; this.currentPage = 1; },
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
		clearItem() { this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
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
		onSmartDateResolved(value) {
			if (!value?.from_date || !value?.to_date) return;
			this.filters.from_date = value.from_date;
			this.filters.to_date = value.to_date;
			this.filters.date_range_preset = "Custom Period";
			this.currentPage = 1;
		},
		async onPresetChange() {
			if (this.filters.date_range_preset === "Custom Period") return;
			const dates = window.retailedge?.getPresetDates?.(this.filters.date_range_preset);
			if (!dates) return;
			this.filters.from_date = dates.from_date;
			this.filters.to_date = dates.to_date;
			this.currentPage = 1;
		},
		onDateChange() { this.filters.date_range_preset = "Custom Period"; this.currentPage = 1; },
		onAnalysisPresetChange() {
			const groups = {
				"Sales Trend": "Month",
				"Sales by Item": "Item",
				"Sales by Category": "Item Group",
				"Sales by Customer": "Customer",
				"Sales by Customer Group": "Customer Group",
				"Sales by Branch": "Branch",
				"Sales by Salesperson": "Salesperson",
				"Sales by Warehouse": "Warehouse",
				"Daily Sales": "Day",
				"Weekly Sales": "Week",
				"Quarterly Sales": "Quarter",
				"Yearly Sales": "Year",
			};
			if (groups[this.analysisPreset]) this.filters.group_by = groups[this.analysisPreset];
			this.currentPage = 1;
		},
		onAnalysisGroupChange() {
			const presets = {
				Month: "Sales Trend",
				Item: "Sales by Item",
				"Item Group": "Sales by Category",
				Customer: "Sales by Customer",
				"Customer Group": "Sales by Customer Group",
				Branch: "Sales by Branch",
				Salesperson: "Sales by Salesperson",
				Warehouse: "Sales by Warehouse",
				Day: "Daily Sales",
				Week: "Weekly Sales",
				Quarter: "Quarterly Sales",
				Year: "Yearly Sales",
			};
			this.analysisPreset = presets[this.filters.group_by] || "Custom";
			this.currentPage = 1;
		},
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		providerFilters() {
			const { page_size: _pageSize, date_range_preset: _preset, ...filters } = this.filters;
			return filters;
		},
		async fetchData() {
			if (!this.requiredReady) return;
			if (!this.reportProvider?.load) {
				this.error = `The ${this.config.title} reporting service is unavailable.`;
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50);
				const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({ filters: this.providerFilters(), start, page_length: pageSize, sort: this.reportSort });
				this.rows = result.rows || [];
				this.columns = (result.columns || []).filter((column) => !column.hidden);
				this.summary = result.summary || []; this.reportSort = result.sort || null;
				this.scan = result.metadata?.scan || {};
				this.companyCurrency = result.metadata?.company_currency || this.companyCurrency;
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
			const result = this.reportProvider?.export
				? await this.reportProvider.export({ filters: this.providerFilters() })
				: {};
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
		rowKey(row, index) { return row.group_key || row.invoice || row.item_code || `${this.reportType}:${index}`; },
		openReportCell(payload) {
			const column = payload?.column;
			const row = payload?.row;
			if (!column || !row) return;
			this.openDrilldown(column, row);
		},
		openDrilldown(column, row) {
			const value = row?.[column.fieldname];
			if (!value) return;
			if (!this.canUseNativeDesk) return;
			if (["invoice", "return_against"].includes(column.fieldname)) frappe.set_route("Form", "Sales Invoice", value);
			else if (column.fieldname === "item_code") frappe.set_route("Form", "Item", value);
			else if (column.fieldname === "customer") frappe.set_route("Form", "Customer", value);
		},
		formatCell(value, column) { return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency); },
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try { return window.retailedge.formatPlainValue(number, { fieldtype: "Currency", options: currency || this.companyCurrency }); }
				catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
			}
			if (fieldtype === "Float") {
				const number = Number(value);
				return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(value);
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; }
				catch (_error) { return String(value); }
			}
			return String(value);
		},
	},
};
</script>

<style scoped>
.sales-report-fallback {
	margin: 20px;
	padding: 24px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.sales-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}
.advanced-filters { margin-top: var(--edge-space-md, 16px); }
.advanced-filters summary { cursor: pointer; font-weight: 600; color: var(--edge-text, #101828); }
.advanced-grid { margin-top: var(--edge-space-sm, 10px); }
.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
.edge-input,
.edge-primary-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 0 10px;
}
.edge-primary-button { width: 100%; background: var(--edge-primary, #1d4ed8); color: #fff; border-color: transparent; font-weight: 600; }
@media (max-width: 72rem) { .sales-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .sales-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 36rem) { .sales-filter-grid { grid-template-columns: 1fr; } }
</style>
