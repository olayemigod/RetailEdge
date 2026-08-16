<template>
	<div v-if="!edgeUIValid" class="stock-movement-fallback">
		<strong>EdgeSuite UI failed to load</strong>
		<span>Missing components: {{ missingComponents.join(", ") }}</span>
	</div>

	<EdgeAppShell
		v-else
		product="retailedge"
		:menuItems="menuItems"
		activeRoute="/app/stock-movement-history"
		title="RetailEdge"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:hideNativeSidebar="true"
		sectionStateKey="retailedge:stock-movement:navigation"
		@navigate="handleNavigation"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="Stock Movement History"
					subtitle="Trace item movement, stock balance and source documents without loading the full ledger into the browser."
				/>
			</template>

			<EdgeFilterBar title="Movement Filters">
				<div class="stock-filter-grid">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						placeholder="Search company"
						:searcher="companySearch"
						:required="true"
						@select="onCompanySelected"
					/>

					<div class="edge-field">
						<label class="edge-field-label">Date Range</label>
						<select v-model="filters.date_range_preset" class="edge-input" @change="onPresetChange">
							<option v-for="preset in datePresets" :key="preset" :value="preset">{{ preset }}</option>
						</select>
					</div>

					<div class="edge-field">
						<label class="edge-field-label">From Date</label>
						<input v-model="filters.from_date" class="edge-input" type="date" @change="onDateChange" />
					</div>

					<div class="edge-field">
						<label class="edge-field-label">To Date</label>
						<input v-model="filters.to_date" class="edge-input" type="date" @change="onDateChange" />
					</div>

					<EdgeLinkField
						v-model="filters.item_code"
						:selectedLabel="itemLabel"
						label="Item"
						placeholder="Search stock item"
						:searcher="itemSearch"
						:required="true"
						@select="onItemSelected"
						@clear="clearItem"
					/>

					<EdgeLinkField
						v-model="filters.branch"
						label="Branch"
						placeholder="Search branch"
						:searcher="branchSearch"
						:context="{ company: filters.company }"
						@select="onBranchSelected"
						@clear="clearBranch"
					/>

					<EdgeLinkField
						v-model="filters.warehouse"
						label="Warehouse"
						placeholder="Search warehouse"
						:searcher="warehouseSearch"
						:context="{ company: filters.company, branch: filters.branch }"
						:required="true"
						@select="onWarehouseSelected"
					/>

					<EdgeLinkField
						v-model="filters.compare_uom"
						label="Compare UOM"
						placeholder="Optional comparison UOM"
						:searcher="uomSearch"
					/>

					<div class="edge-field">
						<label class="edge-field-label">Movement Type</label>
						<select v-model="filters.movement_type" class="edge-input">
							<option value="">All Movement Types</option>
							<option v-for="movement in movementTypes" :key="movement" :value="movement">{{ movement }}</option>
						</select>
					</div>

					<div class="filter-action">
						<button class="edge-primary-button" type="button" :disabled="loading || !requiredReady" @click="applyFilters">
							{{ loading ? "Loading…" : "Apply / Refresh" }}
						</button>
					</div>
				</div>

				<details class="advanced-filters">
					<summary>Advanced filters</summary>
					<div class="stock-filter-grid advanced-grid">
						<div class="edge-field">
							<label class="edge-field-label">Voucher Type</label>
							<input v-model.trim="filters.voucher_type" class="edge-input" type="text" placeholder="e.g. Sales Invoice" />
						</div>
						<div class="edge-field">
							<label class="edge-field-label">Voucher Number</label>
							<input v-model.trim="filters.voucher_no" class="edge-input" type="text" placeholder="Exact voucher number" />
						</div>
						<EdgeLinkField
							v-model="filters.batch_no"
							label="Batch Number"
							placeholder="Search batch"
							:searcher="batchSearch"
							:context="{ item_code: filters.item_code }"
						/>
					</div>
				</details>
			</EdgeFilterBar>

			<div v-if="metadataLoading" class="state-wrap">
				<EdgeLoadingState message="Loading Stock Movement controls…" :skeleton="true" />
			</div>
			<div v-else-if="error" class="state-wrap">
				<EdgeErrorState title="Stock Movement History could not load" :message="error" @retry="applyFilters" />
			</div>
			<div v-else-if="loading" class="state-wrap">
				<EdgeLoadingState message="Calculating stock movement and running balances…" :skeleton="true" />
			</div>
			<div v-else-if="!requiredReady" class="state-wrap">
				<EdgeEmptyState
					title="Select an item and warehouse"
					description="Choose Company, Item and Warehouse. Branch will guide the warehouse list when configured."
					icon="search"
				/>
			</div>
			<div v-else>
				<div v-if="summary.length" class="summary-grid">
					<EdgeStatCard
						v-for="card in summary"
						:key="card.label"
						:label="card.label"
						:value="formatQuantity(card.value)"
						:tooltip="card.label"
					/>
				</div>

				<div class="result-meta" v-if="scan.limit">
					<span>{{ pagination.total_rows || 0 }} displayed rows</span>
					<span>{{ scan.ledger_rows || 0 }} ledger rows processed</span>
					<span>Safe scan limit: {{ scan.limit }}</span>
				</div>

				<div v-if="rows.length" class="movement-card">
					<div class="movement-table-wrap">
						<table class="movement-table">
							<thead>
								<tr>
									<th>Date / Time</th>
									<th>Movement</th>
									<th>Item</th>
									<th class="number">In</th>
									<th class="number">Out</th>
									<th class="number">Balance</th>
									<th v-if="filters.compare_uom" class="number">Compare Balance</th>
									<th>Source</th>
									<th>Destination</th>
									<th>Voucher</th>
									<th>Batch</th>
									<th>Purpose / Reference</th>
									<th>Remarks</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="(row, index) in rows" :key="rowKey(row, index)" :class="{ opening: row.is_opening_row }">
									<td>{{ formatDateTime(row.posting_datetime) }}</td>
									<td class="movement-type">{{ row.movement_type || "—" }}</td>
									<td>
										<a href="#" class="doc-link" @click.prevent="openDoc('Item', row.item_code)">{{ row.item_code }}</a>
										<div class="subtle">{{ row.item_name || row.stock_uom || "" }}</div>
									</td>
									<td class="number">{{ formatQuantity(row.in_quantity) }}</td>
									<td class="number">{{ formatQuantity(row.out_quantity) }}</td>
									<td class="number balance">{{ formatQuantity(row.balance) }}</td>
									<td v-if="filters.compare_uom" class="number">{{ formatQuantity(row.compare_balance) }}</td>
									<td>{{ row.source_warehouse || "—" }}</td>
									<td>{{ row.destination_warehouse || "—" }}</td>
									<td>
										<a v-if="row.voucher_type && row.voucher_no" href="#" class="doc-link" @click.prevent="openDoc(row.voucher_type, row.voucher_no)">{{ row.voucher_no }}</a>
										<span v-else>—</span>
										<div v-if="row.voucher_type" class="subtle">{{ row.voucher_type }}</div>
									</td>
									<td>{{ row.batch_no || "—" }}</td>
									<td>{{ row.purpose || "—" }}</td>
									<td class="remarks">{{ row.remarks || "—" }}</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div class="pagination-footer">
						<div>
							Page {{ pagination.page || 1 }} of {{ pagination.total_pages || 1 }}
							<span class="subtle">· {{ pagination.total_rows || 0 }} rows</span>
						</div>
						<div class="pagination-actions">
							<select v-model.number="filters.page_size" class="page-size" @change="changePageSize">
								<option :value="25">25 / page</option>
								<option :value="50">50 / page</option>
								<option :value="100">100 / page</option>
							</select>
							<button type="button" class="page-button" :disabled="!pagination.has_previous" @click="changePage(-1)">Previous</button>
							<button type="button" class="page-button" :disabled="!pagination.has_next" @click="changePage(1)">Next</button>
						</div>
					</div>
				</div>

				<div v-else class="state-wrap">
					<EdgeEmptyState
						title="No stock movements found"
						description="No ledger movement matches the selected item, warehouse, date range and optional filters."
						icon="search"
					/>
				</div>
			</div>
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
	name: "StockMovementHistory",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			rows: [],
			summary: [],
			pagination: {},
			scan: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			itemLabel: "",
			filters: {
				company: "",
				date_range_preset: "This Month",
				from_date: "",
				to_date: "",
				item_code: "",
				branch: "",
				warehouse: "",
				compare_uom: "",
				movement_type: "",
				voucher_type: "",
				voucher_no: "",
				batch_no: "",
				page_size: 50,
			},
			currentPage: 1,
			datePresets: [
				"This Month",
				"Today",
				"Yesterday",
				"This Week",
				"This Quarter",
				"This Year",
				"Last Week",
				"Last Month",
				"Last Quarter",
				"Last Year",
				"Custom Period",
			],
			movementTypes: [
				"Purchase Receipt",
				"Sale",
				"Sales Return",
				"Purchase Return",
				"Internal Transfer",
				"Material Issue",
				"Material Receipt",
				"Manufacture",
				"Repack",
				"Adjustment In",
				"Adjustment Out",
				"Stock Reconciliation",
				"Incoming",
				"Outgoing",
			],
		};
	},
	computed: {
		requiredReady() {
			return Boolean(
				this.filters.company &&
					this.filters.from_date &&
					this.filters.to_date &&
					this.filters.item_code &&
					this.filters.warehouse
			);
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
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.stock_movement_page.get_stock_movement_page_context"),
					callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context"),
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || context.default_filters?.company || "";
				this.branchName = context.branch_name || context.default_filters?.branch || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Stock Movement controls.");
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
			const result = await callMethod("retailedge.stock_movement_page.search_stock_movement_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
				item_code: this.filters.item_code,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) {
			return this.searchOptions("company", txt);
		},
		itemSearch(txt) {
			return this.searchOptions("item", txt);
		},
		branchSearch(txt) {
			return this.searchOptions("branch", txt);
		},
		warehouseSearch(txt) {
			return this.searchOptions("warehouse", txt);
		},
		uomSearch(txt) {
			return this.searchOptions("uom", txt);
		},
		batchSearch(txt) {
			return this.searchOptions("batch", txt);
		},
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.warehouse = "";
			this.currentPage = 1;
		},
		onItemSelected(option) {
			this.filters.item_code = option.value;
			this.itemLabel = option.label || option.value;
			this.filters.batch_no = "";
			this.currentPage = 1;
		},
		clearItem() {
			this.itemLabel = "";
			this.filters.batch_no = "";
		},
		async onBranchSelected(option) {
			this.filters.branch = option.value;
			this.filters.warehouse = "";
			this.currentPage = 1;
			if (!this.filters.company || !this.filters.branch) return;
			try {
				const resolved = await callMethod("retailedge.guided_entry_context.resolve_branch_warehouse_selection", {
					company: this.filters.company,
					branch: this.filters.branch,
					warehouse: "",
					preference: "default",
				});
				if (resolved.warehouse) this.filters.warehouse = resolved.warehouse;
			} catch (error) {
				this.error = errorMessage(error, "Unable to resolve the Branch warehouse.");
			}
		},
		clearBranch() {
			this.filters.branch = "";
			this.filters.warehouse = "";
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
				if (resolved.branch) this.filters.branch = resolved.branch;
			} catch (error) {
				this.filters.warehouse = "";
				this.error = errorMessage(error, "The selected Warehouse is not valid for this context.");
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
			if (!this.requiredReady) {
				this.rows = [];
				this.summary = [];
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.stock_movement_page.get_stock_movement_page", {
					filters: { ...this.filters },
					page: this.currentPage,
					page_size: this.filters.page_size,
				});
				this.rows = result.rows || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scan = result.scan || {};
				this.currentPage = this.pagination.page || this.currentPage;
			} catch (error) {
				this.rows = [];
				this.summary = [];
				this.error = errorMessage(error, "Stock Movement History failed to load.");
			} finally {
				this.loading = false;
			}
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
		openDoc(doctype, name) {
			if (doctype && name) frappe.set_route("Form", doctype, name);
		},
		rowKey(row, index) {
			return `${row.voucher_type || "opening"}:${row.voucher_no || ""}:${row.voucher_detail_no || ""}:${row.posting_datetime || ""}:${index}`;
		},
		formatDateTime(value) {
			if (!value) return "—";
			try {
				return frappe.datetime.str_to_user(String(value));
			} catch (_error) {
				return String(value);
			}
		},
		formatQuantity(value) {
			if (value === null || value === undefined || value === "") return "—";
			const number = Number(value);
			if (!Number.isFinite(number)) return String(value);
			return number.toLocaleString(undefined, { maximumFractionDigits: 4 });
		},
	},
};
</script>

<style scoped>
.stock-movement-fallback,
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

.stock-filter-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
}

.edge-field {
	display: flex;
	flex-direction: column;
	gap: 6px;
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

.advanced-grid {
	margin-top: 12px;
}

.summary-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
	gap: var(--edge-space-md, 16px);
	margin: var(--edge-space-lg, 20px) 0;
}

.result-meta {
	display: flex;
	flex-wrap: wrap;
	gap: 12px;
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
	margin-bottom: 10px;
}

.movement-card {
	border: 1px solid var(--edge-border, #e4e7ec);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	overflow: hidden;
}

.movement-table-wrap {
	overflow-x: auto;
}

.movement-table {
	width: 100%;
	border-collapse: collapse;
	font-size: 0.82rem;
}

.movement-table th,
.movement-table td {
	padding: 10px 12px;
	border-bottom: 1px solid var(--edge-border, #eaecf0);
	text-align: left;
	vertical-align: top;
	white-space: nowrap;
}

.movement-table th {
	background: var(--edge-bg, #f8fafc);
	color: var(--edge-text-muted, #667085);
	font-weight: 600;
}

.movement-table tr.opening td {
	background: color-mix(in srgb, var(--edge-primary, #2563eb) 7%, var(--edge-surface, #fff));
	font-weight: 600;
}

.number {
	text-align: right !important;
	font-variant-numeric: tabular-nums;
}

.balance {
	font-weight: 700;
}

.movement-type {
	font-weight: 600;
}

.doc-link {
	color: var(--edge-primary, #2563eb);
	text-decoration: none;
	font-weight: 600;
}

.doc-link:hover {
	text-decoration: underline;
}

.subtle {
	color: var(--edge-text-muted, #667085);
	font-size: 0.74rem;
	margin-top: 2px;
}

.remarks {
	max-width: 260px;
	white-space: normal !important;
}

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
	min-height: 34px;
	padding: 6px 10px;
}

.page-button {
	cursor: pointer;
}

@media (max-width: 768px) {
	.stock-filter-grid {
		grid-template-columns: 1fr;
	}
	.pagination-footer {
		align-items: stretch;
		flex-direction: column;
	}
	.pagination-actions {
		justify-content: space-between;
	}
}
</style>
