<template>
	<div v-if="!edgeUIValid" class="inventory-intelligence-fallback">
		<strong>Inventory Intelligence could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Inventory Intelligence"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/inventory-intelligence"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Inventory Intelligence"
			eyebrow="Inventory Control"
			subtitle="Use current ERPNext stock, bounded historical demand evidence and native reorder configuration to identify inventory actions."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:sort="sort"
			rowKey="item_code"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No inventory intelligence found"
			emptyDescription="Adjust the stock, movement, replenishment, scope or evidence-window filters and try again."
			loadingMessage="Loading inventory intelligence…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@sort-change="changeSort"
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
				<div class="inventory-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.warehouse" label="Warehouse" placeholder="All warehouses in scope" :searcher="warehouseSearch" @select="onWarehouseSelected" @clear="clearWarehouse" />
					<EdgeLinkField v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<EdgeLinkField v-model="filters.item_code" :selectedLabel="itemLabel" label="Item" placeholder="All stock items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<label class="edge-field">
						<span class="edge-field-label">Stock Status</span>
						<select v-model="filters.stock_status" class="edge-input">
							<option v-for="status in stockStatuses" :key="status" :value="status">{{ status }}</option>
						</select>
					</label>
					<label class="edge-field">
						<span class="edge-field-label">Movement Class</span>
						<select v-model="filters.movement_class" class="edge-input">
							<option v-for="movement in movementClasses" :key="movement" :value="movement">{{ movement }}</option>
						</select>
					</label>
					<label class="edge-field">
						<span class="edge-field-label">Replenishment Status</span>
						<select v-model="filters.replenishment_status" class="edge-input">
							<option v-for="status in replenishmentStatuses" :key="status" :value="status">{{ status }}</option>
						</select>
					</label>
					<label class="edge-field">
						<span class="edge-field-label">Evidence Window</span>
						<select v-model.number="filters.lookback_days" class="edge-input">
							<option v-for="days in lookbackOptions" :key="days" :value="days">Last {{ days }} days</option>
						</select>
					</label>
					<label class="include-zero-field">
						<input v-model="includeZero" type="checkbox" />
						<span><strong>Include zero-stock items</strong><small>Recommended so sold-out demand and reorder items remain visible.</small></span>
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
				<span v-if="scope.from_date && scope.to_date">Demand evidence: {{ scope.from_date }} to {{ scope.to_date }}</span>
				<span v-if="Number(scan.synthetic_zero_items || 0) > 0">{{ Number(scan.synthetic_zero_items) }} zero-balance item(s) retained from demand/reorder evidence</span>
				<span>Replenishment uses ERPNext Item Reorder configuration</span>
				<span>Stock cover is historical estimation, not a forecast</span>
				<span v-if="!showCosts">Cost values hidden by RetailEdge settings</span>
				<span v-else-if="companyCurrency">Valuation in {{ companyCurrency }}</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];

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
	name: "InventoryIntelligenceCentre",
	props: {
		pageMethod: { type: String, required: true },
		exportMethod: { type: String, required: true },
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
			scope: {},
			scan: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			showCosts: false,
			itemLabel: "",
			sort: null,
			filters: {
				company: "",
				branch: "",
				warehouse: "",
				item_group: "",
				item_code: "",
				stock_status: "All",
				movement_class: "All",
				replenishment_status: "All",
				lookback_days: 90,
				slow_days: 30,
				non_moving_days: 90,
				include_zero: 1,
				page_size: 50,
			},
			currentPage: 1,
			stockStatuses: ["All", "In Stock", "Available", "Out of Stock", "Negative", "Fully Reserved"],
			movementClasses: ["All", "Normal", "Slow", "Non-moving", "No demand in window"],
			replenishmentStatuses: ["All", "Reorder Now", "Review warehouse group", "Healthy", "No reorder rule"],
			lookbackOptions: [30, 60, 90, 180, 365],
		};
	},
	computed: {
		includeZero: {
			get() { return Boolean(Number(this.filters.include_zero)); },
			set(value) { this.filters.include_zero = value ? 1 : 0; },
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: column.fieldname === "item_code",
				sortable: true,
			}));
		},
		scopeLabel() {
			if (this.scope.warehouse) return `Warehouse: ${this.scope.warehouse}`;
			if (this.scope.branch) return `Branch: ${this.scope.branch} · ${Number(this.scope.warehouse_count || 0)} warehouse(s)`;
			return `${Number(this.scope.warehouse_count || 0)} permitted warehouse(s)`;
		},
		exportDataset() {
			return {
				title: "Inventory Intelligence",
				filename: `RetailEdge Inventory Intelligence ${this.filters.company || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company", branch: "Branch", warehouse: "Warehouse", item_group: "Item Group", item_code: "Item",
				stock_status: "Stock Status", movement_class: "Movement Class", replenishment_status: "Replenishment Status",
				lookback_days: "Evidence Window (Days)",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined && entry.value !== "All");
		},
		exportMetadata() {
			return [
				{ label: "Current Stock Source", value: "ERPNext Bin" },
				{ label: "Demand Source", value: "Bounded outward ERPNext Stock Ledger Entry evidence" },
				{ label: "Replenishment Source", value: "ERPNext Item Reorder configuration" },
				{ label: "Zero-stock Visibility", value: this.includeZero ? "Included" : "Excluded by filter" },
				{ label: "Stock Cover", value: "Historical estimate, not forecast" },
				{ label: "Cost Visibility", value: this.showCosts ? "Included" : "Hidden by RetailEdge settings" },
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
					callMethod("retailedge.stock_position.get_stock_position_context"),
					navigationPromise,
				]);
				this.filters = {
					...this.filters,
					...(context.default_filters || {}),
					movement_class: "All",
					replenishment_status: "All",
					lookback_days: 90,
					slow_days: 30,
					non_moving_days: 90,
					include_zero: 1,
				};
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.showCosts = Boolean(Number(context.show_costs));
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Inventory Intelligence controls.");
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
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer");
			else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer");
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
			this.filters.item_group = "";
			this.filters.item_code = "";
			this.itemLabel = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.filters.warehouse = "";
			this.branchName = option.label || option.value;
			this.currentPage = 1;
		},
		clearBranch() { this.filters.branch = ""; this.filters.warehouse = ""; this.branchName = ""; this.currentPage = 1; },
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
				this.error = errorMessage(error, "The selected Warehouse is not valid for Inventory Intelligence.");
			}
		},
		onItemGroupSelected(option) { this.filters.item_group = option.value; this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		onItemSelected(option) {
			this.filters.item_code = option.value;
			this.itemLabel = option.label || option.value;
			if (!this.filters.item_group && option.raw?.item_group) this.filters.item_group = option.raw.item_group;
			this.currentPage = 1;
		},
		clearItem() { this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		requestFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(this.pageMethod, {
					filters: this.requestFilters(),
					page: this.currentPage,
					page_size: Number(this.filters.page_size || 50),
					sort_field: this.sort?.field || "",
					sort_direction: this.sort?.direction || "",
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scope = result.scope || {};
				this.scan = result.scan || {};
				this.companyCurrency = result.company_currency || "";
				this.showCosts = Boolean(Number(result.show_costs));
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = errorMessage(error, "Inventory Intelligence failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			const result = await callMethod(this.exportMethod, {
				filters: this.requestFilters(),
				sort_field: this.sort?.field || "",
				sort_direction: this.sort?.direction || "",
			});
			return {
				columns: result.columns || this.columns,
				rows: result.rows || [],
				summary: result.summary || this.summary,
				metadata: this.exportMetadata,
			};
		},
		changeSort(next) { this.sort = next; this.currentPage = 1; this.fetchData(); },
		goToPage(page) { this.currentPage = Math.max(1, Number(page || 1)); this.fetchData(); },
		setPageSize(pageSize) { this.filters.page_size = Number(pageSize || 50); this.currentPage = 1; this.fetchData(); },
		openReportCell(payload) {
			if (payload?.column?.fieldname === "item_code" && payload.value) {
				window.open(`/app/item/${encodeURIComponent(payload.value)}`, "_blank", "noopener,noreferrer");
			}
		},
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
.inventory-intelligence-fallback {
	margin: 20px;
	padding: 24px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.inventory-filter-grid {
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
@media (max-width: 72rem) { .inventory-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .inventory-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 36rem) { .inventory-filter-grid { grid-template-columns: 1fr; } }
</style>