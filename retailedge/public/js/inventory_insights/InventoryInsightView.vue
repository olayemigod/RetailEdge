<template>
	<div v-if="!edgeUIValid" class="inventory-insight-fallback">
		<strong>{{ config.title }} could not start.</strong>
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
		:activeRoute="`/app/${config.route}`"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			:title="config.title"
			eyebrow="Inventory Intelligence"
			:subtitle="config.subtitle"
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:sort="sort"
			rowKey="_row_key"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			:emptyTitle="config.emptyTitle"
			:emptyDescription="availabilityMessage || config.emptyDescription"
			:loadingMessage="`Loading ${config.title}…`"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@sort-change="changeSort"
			@cell-click="openReportCell"
			@row-click="selectRow"
		>
			<template #actions>
				<button type="button" class="edge-button" @click="goBackToInventory">Inventory Intelligence</button>
				<button
					v-if="isTransferView && selectedRow"
					type="button"
					class="edge-button edge-button--primary"
					@click="openSelectedTransferWorkflow"
				>
					{{ selectedRow.requires_full_stock_entry ? "Open Stock Entry" : "Open Guided Transfer" }}
				</button>
			</template>

			<template #filters>
				<div class="inventory-insight-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.warehouse" label="Warehouse" placeholder="All warehouses in scope" :searcher="warehouseSearch" @select="onWarehouseSelected" @clear="clearWarehouse" />
					<EdgeLinkField v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<EdgeLinkField v-model="filters.item_code" :selectedLabel="itemLabel" label="Item" placeholder="All stock items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<label v-if="isAgeingView" class="edge-field">
						<span class="edge-field-label">Age Bands (Days)</span>
						<input v-model.trim="filters.age_ranges" class="edge-input" type="text" placeholder="30,60,90,180" />
						<small>Comma-separated increasing limits; ERPNext FIFO slots remain the ageing truth.</small>
					</label>
					<label v-if="isAgeingView" class="edge-field">
						<span class="edge-field-label">Aged Stock Threshold (Days)</span>
						<input v-model.number="filters.aged_threshold_days" class="edge-input" type="number" min="1" max="3650" step="1" />
					</label>
					<label v-if="isProfitabilityView" class="edge-field">
						<span class="edge-field-label">From Date</span>
						<input v-model="filters.from_date" class="edge-input" type="date" />
					</label>
					<label v-if="isProfitabilityView" class="edge-field">
						<span class="edge-field-label">To Date</span>
						<input v-model="filters.to_date" class="edge-input" type="date" />
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
				<span v-if="isAgeingView">Ageing uses ERPNext v16 FIFO stock-ageing semantics</span>
				<span v-if="isAgeingView && scope.age_ranges">Bands: {{ scope.age_ranges.join ? scope.age_ranges.join(", ") : scope.age_ranges }} days · aged threshold {{ scope.aged_threshold_days }} days</span>
				<span v-if="isTransferView">Suggestions are advisory and never create or submit Stock Entries automatically</span>
				<span v-if="isProfitabilityView">Profitability classifications come from R8; R10 does not recalculate margin</span>
				<span v-if="isProfitabilityView && scope.from_date && scope.to_date">Profitability period: {{ scope.from_date }} to {{ scope.to_date }}</span>
				<span v-if="isTransferView && selectedRow">Selected: {{ selectedRow.item_code }} · {{ selectedRow.source_warehouse }} → {{ selectedRow.target_warehouse }} · suggested {{ selectedRow.suggested_transfer_qty }}</span>
			</template>
		</EdgeReportShell>

		<SimpleStockTransferDialog
			v-if="isTransferView"
			:open="guidedTransferOpen"
			:prefill="guidedTransferPrefill"
			@close="guidedTransferOpen = false"
			@saved="handleGuidedTransferSaved"
			@open-native="openNativeStockEntry"
		/>
	</EdgeAppShell>
</template>

<script>
import SimpleStockTransferDialog from "../retailedge_business_hub/SimpleStockTransferDialog.vue";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const VIEW_CONFIG = {
	ageing: {
		title: "Inventory Ageing",
		route: "inventory-ageing",
		subtitle: "See how long current stock has remained in inventory using ERPNext's FIFO stock-ageing engine, with value hidden when cost visibility is restricted.",
		emptyTitle: "No aged inventory found",
		emptyDescription: "Adjust the inventory scope or ageing thresholds and try again.",
	},
	"transfer-opportunities": {
		title: "Transfer Opportunities",
		route: "inventory-transfer-opportunities",
		subtitle: "Identify safe same-company stock rebalancing opportunities anchored to ERPNext reorder rules and protected source stock.",
		emptyTitle: "No safe transfer opportunities",
		emptyDescription: "No permitted warehouse pair currently satisfies the R10 transfer safeguards.",
	},
	profitability: {
		title: "Inventory + Profitability",
		route: "inventory-profitability",
		subtitle: "Combine R8 profitability classifications with current R10 stock, movement and replenishment evidence.",
		emptyTitle: "No inventory-profitability signals",
		emptyDescription: "No current item meets the configured R8/R10 intersection for this scope.",
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

function todayValue() {
	return frappe.datetime?.get_today?.() || new Date().toISOString().slice(0, 10);
}

function monthStartValue() {
	return frappe.datetime?.month_start?.() || `${todayValue().slice(0, 7)}-01`;
}

export default {
	name: "InventoryInsightView",
	props: {
		view: { type: String, required: true },
		pageMethod: { type: String, default: "retailedge.inventory_insight_views.get_inventory_insight_view" },
	},
	components: {
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
		SimpleStockTransferDialog,
	},
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			availabilityMessage: "",
			rows: [],
			columns: [],
			summary: [],
			pagination: {},
			scope: {},
			metadata: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			itemLabel: "",
			selectedRow: null,
			guidedTransferOpen: false,
			sort: null,
			filters: {
				company: "",
				branch: "",
				warehouse: "",
				item_group: "",
				item_code: "",
				age_ranges: "30,60,90,180",
				aged_threshold_days: 90,
				from_date: monthStartValue(),
				to_date: todayValue(),
				page_size: 50,
			},
			currentPage: 1,
		};
	},
	computed: {
		config() { return VIEW_CONFIG[this.view] || VIEW_CONFIG.ageing; },
		isAgeingView() { return this.view === "ageing"; },
		isTransferView() { return this.view === "transfer-opportunities"; },
		isProfitabilityView() { return this.view === "profitability"; },
		guidedTransferPrefill() {
			const row = this.selectedRow;
			if (!this.isTransferView || !row) return {};
			return {
				company: this.filters.company,
				source_warehouse: row.source_warehouse || "",
				target_warehouse: row.target_warehouse || "",
				item_code: row.item_code || "",
				qty: Number(row.suggested_transfer_qty || 0),
			};
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: ["item_code", "source_warehouse", "target_warehouse"].includes(column.fieldname),
				sortable: true,
			}));
		},
		scopeLabel() {
			if (this.scope.warehouse) return `Warehouse: ${this.scope.warehouse}`;
			if (this.scope.branch) return `Branch: ${this.scope.branch}`;
			return this.filters.company ? `Company: ${this.filters.company}` : "Current permitted inventory scope";
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
					age_ranges: this.filters.age_ranges,
					aged_threshold_days: this.filters.aged_threshold_days,
					from_date: this.filters.from_date,
					to_date: this.filters.to_date,
				};
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
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
			this.filters.branch = ""; this.filters.warehouse = ""; this.filters.item_group = ""; this.filters.item_code = "";
			this.itemLabel = ""; this.branchName = ""; this.resetResultState();
		},
		onBranchSelected(option) { this.filters.branch = option.value; this.filters.warehouse = ""; this.branchName = option.label || option.value; this.resetResultState(); },
		clearBranch() { this.filters.branch = ""; this.filters.warehouse = ""; this.branchName = ""; this.resetResultState(); },
		clearWarehouse() { this.filters.warehouse = ""; this.resetResultState(); },
		async onWarehouseSelected(option) {
			this.filters.warehouse = option.value; this.resetResultState();
			if (!this.filters.company) return;
			try {
				const resolved = await callMethod("retailedge.guided_entry_context.resolve_branch_warehouse_selection", {
					company: this.filters.company, branch: this.filters.branch, warehouse: this.filters.warehouse, preference: "default",
				});
				if (resolved.branch) { this.filters.branch = resolved.branch; this.branchName = resolved.branch; }
			} catch (error) {
				this.filters.warehouse = "";
				this.error = errorMessage(error, "The selected Warehouse is not valid for this inventory scope.");
			}
		},
		onItemGroupSelected(option) { this.filters.item_group = option.value; this.filters.item_code = ""; this.itemLabel = ""; this.resetResultState(); },
		clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; this.itemLabel = ""; this.resetResultState(); },
		onItemSelected(option) { this.filters.item_code = option.value; this.itemLabel = option.label || option.value; if (!this.filters.item_group && option.raw?.item_group) this.filters.item_group = option.raw.item_group; this.resetResultState(); },
		clearItem() { this.filters.item_code = ""; this.itemLabel = ""; this.resetResultState(); },
		resetResultState() { this.currentPage = 1; this.selectedRow = null; },
		applyFilters() { this.resetResultState(); return this.fetchData(); },
		requestFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			if (!this.isProfitabilityView) { delete filters.from_date; delete filters.to_date; }
			if (!this.isAgeingView) { delete filters.age_ranges; delete filters.aged_threshold_days; }
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = ""; this.availabilityMessage = "";
			try {
				const result = await callMethod(this.pageMethod, {
					view: this.view,
					filters: this.requestFilters(),
					page: this.currentPage,
					page_size: Number(this.filters.page_size || 50),
					sort_field: this.sort?.field || "",
					sort_direction: this.sort?.direction || "",
				});
				this.rows = (result.rows || []).map((row, index) => ({ ...row, _row_key: this.rowKey(row, index) }));
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.scope = result.scope || {};
				this.metadata = result.metadata || {};
				if (result.available === false) this.availabilityMessage = this.metadata.reason || "This insight is unavailable for the current permission or data scope.";
			} catch (error) {
				this.rows = []; this.columns = []; this.summary = [];
				this.error = errorMessage(error, `${this.config.title} failed to load.`);
			} finally { this.loading = false; }
		},
		rowKey(row, index) { return [row.item_code, row.source_warehouse, row.target_warehouse, row.label, index].filter(Boolean).join("::") || String(index); },
		changeSort(next) { this.sort = next; this.currentPage = 1; this.selectedRow = null; this.fetchData(); },
		goToPage(page) { this.currentPage = Math.max(1, Number(page || 1)); this.selectedRow = null; this.fetchData(); },
		setPageSize(pageSize) { this.filters.page_size = Number(pageSize || 50); this.currentPage = 1; this.selectedRow = null; this.fetchData(); },
		selectRow(row) { if (this.isTransferView) this.selectedRow = row || null; },
		openReportCell(payload) {
			if (!payload?.value) return;
			if (payload.column?.fieldname === "item_code") window.open(`/app/item/${encodeURIComponent(payload.value)}`, "_blank", "noopener,noreferrer");
			if (["source_warehouse", "target_warehouse"].includes(payload.column?.fieldname)) window.open(`/app/warehouse/${encodeURIComponent(payload.value)}`, "_blank", "noopener,noreferrer");
		},
		goBackToInventory() { frappe.set_route("inventory-intelligence"); },
		openSelectedTransferWorkflow() {
			const row = this.selectedRow;
			if (!row) return;
			if (row.requires_full_stock_entry) {
				this.openNativeStockEntry();
				return;
			}
			this.guidedTransferOpen = true;
		},
		handleGuidedTransferSaved(result) {
			this.guidedTransferOpen = false;
			if (!result?.name) return;
			frappe.set_route("Form", result.doctype || "Stock Entry", result.name);
			frappe.show_alert?.({ message: `Stock Transfer ${result.name} saved as Draft`, indicator: "green" });
		},
		openNativeStockEntry() {
			this.guidedTransferOpen = false;
			window.open("/app/stock-entry", "_blank", "noopener,noreferrer");
		},
		formatCell(value, column) {
			if (column.fieldtype === "Check") return Number(value) ? "Yes" : "No";
			if (value === null || value === undefined || value === "") return "—";
			if (["Currency", "Float", "Percent"].includes(column.fieldtype)) {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				if (column.fieldtype === "Percent") return `${number.toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
				return number.toLocaleString(undefined, { maximumFractionDigits: 2 });
			}
			if (column.fieldtype === "Int") return Number(value).toLocaleString();
			return String(value);
		},
	},
};
</script>

<style scoped>
.inventory-insight-fallback { margin: 20px; padding: 24px; border: 1px solid var(--edge-border, #d9d9d9); border-radius: 10px; display: grid; gap: 8px; }
.inventory-insight-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: var(--edge-space-md, 16px); align-items: end; width: 100%; }
.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
.edge-field small { color: var(--edge-text-muted, #667085); font-size: 0.7rem; line-height: 1.3; }
.edge-input, .edge-primary-button { min-height: 38px; border: 1px solid var(--edge-border, #d0d5dd); border-radius: 8px; background: var(--edge-surface, #fff); color: var(--edge-text, #101828); padding: 8px 10px; width: 100%; }
.edge-primary-button { border: 0; background: var(--edge-primary, #2563eb); color: #fff; font-weight: 600; }
@media (max-width: 72rem) { .inventory-insight-filter-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 54rem) { .inventory-insight-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 36rem) { .inventory-insight-filter-grid { grid-template-columns: 1fr; } }
</style>