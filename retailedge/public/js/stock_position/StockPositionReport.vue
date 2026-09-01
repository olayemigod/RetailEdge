<template>
	<div v-if="!edgeUIValid" class="stock-position-fallback">
		<strong>Stock Position could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Stock Position"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/stock-position"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Stock Position"
			eyebrow="Stock Intelligence"
			subtitle="See current and projected stock together with ERPNext direct-warehouse replenishment signals across your permitted Branch or Warehouse scope."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="item_code"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No stock position found"
			emptyDescription="Adjust the Branch, Warehouse, Item, or stock-status filters and try again."
			loadingMessage="Loading current stock position…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
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
				<div class="stock-position-filter-grid">
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
						v-model="filters.warehouse"
						label="Warehouse"
						placeholder="All warehouses in scope"
						:searcher="warehouseSearch"
						@select="onWarehouseSelected"
						@clear="clearWarehouse"
					/>
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
						placeholder="All stock items"
						:searcher="itemSearch"
						@select="onItemSelected"
						@clear="clearItem"
					/>
					<label class="edge-field">
						<span class="edge-field-label">Stock Status</span>
						<select v-model="filters.stock_status" class="edge-input">
							<option v-for="status in stockStatuses" :key="status" :value="status">{{ status }}</option>
						</select>
					</label>
					<label class="include-zero-field">
						<input v-model="includeZero" type="checkbox" />
						<span>
							<strong>Include zero rows</strong>
							<small>Show zero-stock rows. Reorder-due items remain visible even when this is off.</small>
						</span>
					</label>
					<div class="filter-action">
						<button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span>{{ scopeLabel }}</span>
				<span v-if="scan.bin_rows !== undefined">{{ scan.bin_rows }} Bin row{{ scan.bin_rows === 1 ? "" : "s" }} scanned</span>
				<span v-if="scan.reorder_rows !== undefined">{{ scan.reorder_rows }} direct reorder rule{{ scan.reorder_rows === 1 ? "" : "s" }} scanned</span>
				<span v-if="!showCosts">Cost values hidden by RetailEdge settings</span>
				<span v-else-if="companyCurrency">Valuation in {{ companyCurrency }}</span>
				<span>Bounded server dataset · {{ providerDatasetLimit.toLocaleString() }} export-row cap</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "stock-position";

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
	name: "StockPositionReport",
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
			scope: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			showCosts: false,
			itemLabel: "",
			filters: {
				company: "",
				branch: "",
				warehouse: "",
				item_group: "",
				item_code: "",
				stock_status: "All",
				include_zero: 0,
				page_size: 50,
			},
			currentPage: 1,
			stockStatuses: ["All", "In Stock", "Available", "Out of Stock", "Negative", "Fully Reserved", "Reorder Due"],
		};
	},
	computed: {
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| null;
		},
		providerDatasetLimit() { return Number(this.reportProvider?.max_dataset_rows || 0); },
		includeZero: {
			get() { return Boolean(Number(this.filters.include_zero)); },
			set(value) { this.filters.include_zero = value ? 1 : 0; },
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: column.fieldname === "item_code",
			}));
		},
		scopeLabel() {
			if (this.scope.warehouse) return `Warehouse: ${this.scope.warehouse}`;
			if (this.scope.branch) {
				const count = Number(this.scope.warehouse_count || 0);
				return `Branch: ${this.scope.branch} · ${count} warehouse${count === 1 ? "" : "s"}`;
			}
			const count = Number(this.scope.warehouse_count || 0);
			return `${count} permitted warehouse${count === 1 ? "" : "s"}`;
		},
		exportDataset() {
			return {
				title: "Stock Position",
				filename: `RetailEdge Stock Position ${this.filters.company || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company", branch: "Branch", warehouse: "Warehouse", item_group: "Item Group",
				item_code: "Item", stock_status: "Stock Status",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined && entry.value !== "All");
		},
		exportMetadata() {
			return [
				{ label: "Source", value: "ERPNext Bin + direct Item Reorder rules" },
				{ label: "Warehouse Scope", value: this.scopeLabel },
				{ label: "Cost Visibility", value: this.showCosts ? "Included" : "Hidden by RetailEdge settings" },
			].concat(this.showCosts && this.companyCurrency ? [{ label: "Company Currency", value: this.companyCurrency }] : []);
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
					callMethod("retailedge.stock_position.get_stock_position_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.showCosts = Boolean(Number(context.show_costs));
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Stock Position controls.");
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
			const result = await callMethod("retailedge.stock_position.search_stock_position_options", {
				kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		warehouseSearch(txt) { return this.searchOptions("warehouse", txt); },
		itemGroupSearch(txt) { return this.searchOptions("item_group", txt); },
		itemSearch(txt) { return this.searchOptions("item", txt); },
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
		clearWarehouse() { this.filters.warehouse = ""; this.currentPage = 1; },
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
				this.error = errorMessage(error, "The selected Warehouse is not valid for Stock Position.");
			}
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
		clearItem() { this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		providerFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error = "The shared EdgeSuite Stock Position provider is unavailable.";
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50);
				const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({ filters: this.providerFilters(), start, page_length: pageSize });
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.scan = result.metadata?.scan || {};
				this.scope = result.metadata?.scope || {};
				this.companyCurrency = result.metadata?.company_currency || "";
				this.showCosts = Boolean(Number(result.metadata?.show_costs));
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
				this.error = errorMessage(error, "Stock Position failed to load.");
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
					{ label: "Source", value: "ERPNext Bin + direct Item Reorder rules" },
					{ label: "Warehouse Scope", value: this.scopeLabel },
					{ label: "Cost Visibility", value: Number(result.show_costs) ? "Included" : "Hidden by RetailEdge settings" },
				].concat(result.company_currency ? [{ label: "Company Currency", value: result.company_currency }] : []),
			};
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
		openReportCell(payload) {
			if (payload?.column?.fieldname === "item_code" && payload.value) this.openItem(payload.value);
		},
		openItem(itemCode) { if (itemCode) frappe.set_route("Form", "Item", itemCode); },
		formatCell(value, column) { return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency); },
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try { return frappe.format(number, { fieldtype: "Currency", options: currency || this.companyCurrency }); }
				catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
			}
			if (fieldtype === "Float") {
				const number = Number(value);
				return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(value);
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			return String(value);
		},
	},
};
</script>

<style scoped>
.stock-position-fallback {
	margin: 20px;
	padding: 24px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.stock-position-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}
.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
.edge-input,
.edge-primary-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d0d5dd);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 8px 10px;
	width: 100%;
}
.include-zero-field { display: flex; align-items: center; gap: 10px; min-height: 38px; padding: 6px 0; }
.include-zero-field input { width: 18px; height: 18px; }
.include-zero-field span { display: flex; flex-direction: column; gap: 2px; }
.include-zero-field small { color: var(--edge-text-muted, #667085); font-size: 0.72rem; }
.edge-primary-button { border: 0; background: var(--edge-primary, #2563eb); color: #fff; font-weight: 600; padding: 8px 14px; }
@media (max-width: 72rem) { .stock-position-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .stock-position-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 36rem) { .stock-position-filter-grid { grid-template-columns: 1fr; } }
</style>
