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
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					eyebrow="Stock Intelligence"
					title="Stock Position"
					subtitle="See current on-hand, reserved, available, ordered and projected stock across your permitted Branch or Warehouse scope."
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
							@clear="filters.warehouse = ''"
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
							@clear="itemLabel = ''"
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
								<small>Show items whose current and projected quantities are all zero.</small>
							</span>
						</label>
						<div class="filter-action">
							<button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">
								{{ loading ? "Loading…" : "Apply Filters" }}
							</button>
						</div>
					</div>
				</EdgeFilterBar>
			</template>

			<EdgeLoadingState v-if="metadataLoading" message="Loading Stock Position controls…" />
			<EdgeErrorState v-else-if="error" title="Stock Position failed to load" :message="error" actionLabel="Try again" @retry="fetchData" />
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
					<span>{{ pagination.total_rows || rows.length }} item{{ (pagination.total_rows || rows.length) === 1 ? "" : "s" }}</span>
					<span>{{ scopeLabel }}</span>
					<span v-if="scan.bin_rows !== undefined">{{ scan.bin_rows }} Bin row{{ scan.bin_rows === 1 ? "" : "s" }} scanned</span>
					<span v-if="!showCosts">Cost values hidden by RetailEdge settings</span>
					<span v-else-if="companyCurrency">Valuation in {{ companyCurrency }}</span>
				</div>

				<div v-if="rows.length" class="stock-position-card">
					<div class="stock-position-table-wrap">
						<table class="stock-position-table">
							<thead>
								<tr>
									<th v-for="column in columns" :key="column.fieldname" :class="{ number: isNumericColumn(column) }">{{ column.label }}</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in rows" :key="row.item_code">
									<td v-for="column in columns" :key="column.fieldname" :class="{ number: isNumericColumn(column) }">
										<button v-if="column.fieldname === 'item_code'" type="button" class="doc-link" @click="openItem(row.item_code)">
											{{ row.item_code }}
										</button>
										<span v-else-if="column.fieldname === 'stock_status'" :class="statusClass(row.stock_status)">{{ row.stock_status }}</span>
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
					title="No stock position found"
					description="Adjust the Branch, Warehouse, Item, or stock-status filters and try again."
				/>
				<EdgeLoadingState v-if="loading" message="Loading current stock position…" />
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
	name: "StockPosition",
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
			stockStatuses: ["All", "In Stock", "Available", "Out of Stock", "Negative", "Fully Reserved"],
		};
	},
	computed: {
		includeZero: {
			get() { return Boolean(Number(this.filters.include_zero)); },
			set(value) { this.filters.include_zero = value ? 1 : 0; },
		},
		scopeLabel() {
			if (this.scope.warehouse) return `Warehouse: ${this.scope.warehouse}`;
			if (this.scope.branch) return `Branch: ${this.scope.branch} · ${this.scope.warehouse_count || 0} warehouse${this.scope.warehouse_count === 1 ? "" : "s"}`;
			return `${this.scope.warehouse_count || 0} permitted warehouse${this.scope.warehouse_count === 1 ? "" : "s"}`;
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
				company: "Company",
				branch: "Branch",
				warehouse: "Warehouse",
				item_group: "Item Group",
				item_code: "Item",
				stock_status: "Stock Status",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined && entry.value !== "All");
		},
		exportMetadata() {
			return [
				{ label: "Source", value: "ERPNext Bin current stock" },
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
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.stock_position.get_stock_position", {
					filters: { ...this.filters },
					page: this.currentPage,
					page_size: this.filters.page_size,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scan = result.scan || {};
				this.scope = result.scope || {};
				this.companyCurrency = result.company_currency || "";
				this.showCosts = Boolean(Number(result.show_costs));
				this.currentPage = this.pagination.page || this.currentPage;
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
			const result = await callMethod("retailedge.stock_position.get_stock_position_export", { filters: { ...this.filters } });
			return {
				columns: result.columns || this.columns,
				rows: result.rows || [],
				summary: result.summary || this.summary,
				metadata: [
					{ label: "Source", value: "ERPNext Bin current stock" },
					{ label: "Warehouse Scope", value: this.scopeLabel },
					{ label: "Cost Visibility", value: Number(result.show_costs) ? "Included" : "Hidden by RetailEdge settings" },
				].concat(result.company_currency ? [{ label: "Company Currency", value: result.company_currency }] : []),
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
		openItem(itemCode) {
			if (itemCode) frappe.set_route("Form", "Item", itemCode);
		},
		isNumericColumn(column) {
			return ["Currency", "Float", "Int"].includes(column.fieldtype);
		},
		statusClass(status) {
			return ["stock-status", `stock-status--${String(status || "").toLowerCase().replace(/\s+/g, "-")}`];
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

:deep(.edge-filter-bar) {
	align-items: stretch;
	flex-direction: column;
}

:deep(.edge-filter-bar__fields) {
	display: block;
	width: 100%;
}

.stock-position-filter-grid {
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

.include-zero-field {
	display: flex;
	align-items: center;
	gap: 10px;
	min-height: 38px;
	padding: 6px 0;
}

.include-zero-field input { width: 18px; height: 18px; }
.include-zero-field span { display: flex; flex-direction: column; gap: 2px; }
.include-zero-field small { color: var(--edge-text-muted, #667085); font-size: 0.72rem; }

.filter-action { display: flex; align-items: end; }

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
.page-button:disabled { opacity: 0.55; cursor: not-allowed; }

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

.stock-position-card {
	border: 1px solid var(--edge-border, #e4e7ec);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	overflow: hidden;
}

.stock-position-table-wrap { overflow-x: auto; }
.stock-position-table { width: 100%; border-collapse: collapse; font-size: 0.82rem; }
.stock-position-table th,
.stock-position-table td {
	padding: 10px 12px;
	border-bottom: 1px solid var(--edge-border, #eaecf0);
	text-align: left;
	vertical-align: top;
	white-space: nowrap;
}
.stock-position-table th {
	background: var(--edge-bg, #f8fafc);
	color: var(--edge-text-muted, #667085);
	font-weight: 600;
}

.number { text-align: right !important; font-variant-numeric: tabular-nums; }
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

.stock-status {
	display: inline-flex;
	align-items: center;
	border-radius: 999px;
	padding: 3px 8px;
	font-size: 0.72rem;
	font-weight: 700;
	background: var(--edge-bg, #f8fafc);
}
.stock-status--available { color: var(--edge-success, #15803d); }
.stock-status--fully-reserved { color: var(--edge-warning, #b45309); }
.stock-status--out-of-stock,
.stock-status--negative { color: var(--edge-danger, #b42318); }

.pagination-footer {
	display: flex;
	justify-content: space-between;
	align-items: center;
	gap: 12px;
	padding: 12px 14px;
	border-top: 1px solid var(--edge-border, #e4e7ec);
}
.pagination-actions { display: flex; gap: 8px; align-items: center; }
.page-size,
.page-button { width: auto; min-height: 34px; padding: 6px 10px; }
.page-button { cursor: pointer; }

@media (max-width: 1180px) {
	.stock-position-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); }
}
@media (max-width: 900px) {
	.stock-position-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
	.stock-position-filter-grid { grid-template-columns: 1fr; }
	.pagination-footer { align-items: stretch; flex-direction: column; }
	.pagination-actions { justify-content: space-between; }
}
</style>
