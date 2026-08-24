<template>
	<div v-if="!edgeUIValid" class="forecast-fallback">
		<strong>Sales Forecast could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Sales Forecast"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/sales-forecast"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Sales Forecast"
			eyebrow="Forecasting & Planning"
			subtitle="Project submitted net sales from completed historical months while keeping Actual, Forecast and owner Plan as separate concepts."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="period_start"
			:formatter="formatCell"
			emptyTitle="No completed sales history matched this scope"
			emptyDescription="Adjust Company, Branch, customer, salesperson, item or warehouse scope and try again."
			loadingMessage="Building explainable sales forecast…"
			@retry="fetchData"
		>
			<template #actions>
				<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
				<button class="edge-button edge-button--secondary" type="button" @click="openPlanningWorkspace">Planning Workspace</button>
			</template>

			<template #filters>
				<div class="forecast-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<label class="edge-field"><span class="edge-field-label">As of Date</span><input v-model="filters.as_of_date" class="edge-input" type="date" /></label>
					<label class="edge-field"><span class="edge-field-label">History Months</span><select v-model.number="filters.history_months" class="edge-input"><option v-for="n in historyOptions" :key="n" :value="n">{{ n }}</option></select></label>
					<label class="edge-field"><span class="edge-field-label">Forecast Months</span><select v-model.number="filters.forecast_months" class="edge-input"><option v-for="n in 12" :key="n" :value="n">{{ n }}</option></select></label>
					<EdgeLinkField v-model="filters.customer" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<EdgeLinkField v-model="filters.salesperson" label="Salesperson" placeholder="All salespeople" :searcher="salespersonSearch" @select="onSalespersonSelected" @clear="clearSalesperson" />
					<EdgeLinkField v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<EdgeLinkField v-model="filters.item_code" label="Item" placeholder="All items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<EdgeLinkField v-model="filters.warehouse" label="Warehouse" placeholder="All permitted warehouses" :searcher="warehouseSearch" @select="onWarehouseSelected" @clear="clearWarehouse" />
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Forecasting…" : "Apply / Refresh" }}</button></div>
				</div>
			</template>

			<template #resultMeta>
				<span>History: {{ scope.history_from_date || "—" }} to {{ scope.history_to_date || "—" }}</span>
				<span>Forecast starts: {{ scope.forecast_start || "—" }}</span>
				<span>{{ metadata.history_policy || "Completed calendar months only." }}</span>
				<span>{{ forecastMethod }}</span>
				<span>{{ metadata.profit_truth || "ERPNext Profit & Loss remains financial profit truth." }}</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "SalesForecast",
	props: { pageMethod: { type: String, required: true }, exportMethod: { type: String, required: true } },
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], metadata: {}, scope: {}, menuItems: [], tenantName: "", branchName: "", userName: "",
			filters: { company: "", branch: "", as_of_date: "", history_months: 6, forecast_months: 3, customer: "", salesperson: "", item_group: "", item_code: "", warehouse: "" },
			historyOptions: [3, 6, 9, 12, 18, 24],
		};
	},
	computed: {
		reportColumns() { return (this.columns || []).map((column) => ({ ...column, sortable: false })); },
		forecastMethod() { const engine = this.metadata.forecast_engine || {}; return engine.method ? `Method: ${engine.method}${engine.fallback_reason ? ` · ${engine.fallback_reason}` : ""}` : "Explainable deterministic baseline"; },
		exportDataset() { return { title: "Sales Forecast", filename: `RetailEdge Sales Forecast ${this.filters.company || ""}`.trim(), columns: this.columns, rows: this.rows, filters: this.exportFilters, summary: this.summary, metadata: this.exportMetadata }; },
		exportFilters() {
			const labels = { company: "Company", branch: "Branch", as_of_date: "As of Date", history_months: "History Months", forecast_months: "Forecast Months", customer: "Customer", salesperson: "Salesperson", item_group: "Item Group", item_code: "Item", warehouse: "Warehouse" };
			return Object.entries(labels).map(([key, label]) => ({ label, value: this.filters[key] })).filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() { return [ { label: "Sales Truth", value: this.metadata.sales_truth || "Submitted ERPNext Sales Invoice" }, { label: "History Policy", value: this.metadata.history_policy || "Completed months" }, { label: "Forecast Method", value: this.metadata.forecast_engine?.method || "Deterministic baseline" }, { label: "Accounting Mutation", value: "None" } ]; },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.sales_reporting.get_sales_reporting_context"), navigationPromise]);
				const defaults = context.default_filters || {};
				this.filters.company = defaults.company || ""; this.filters.branch = defaults.branch || ""; this.filters.as_of_date = defaults.to_date || frappe.datetime.get_today();
				this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Sales Forecast controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer"); else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer"); },
		openPlanningWorkspace() { frappe.set_route("forecasting-planning"); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, customerSearch(txt) { return this.searchOptions("customer", txt); }, salespersonSearch(txt) { return this.searchOptions("salesperson", txt); }, itemGroupSearch(txt) { return this.searchOptions("item_group", txt); }, itemSearch(txt) { return this.searchOptions("item", txt); }, warehouseSearch(txt) { return this.searchOptions("warehouse", txt); },
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.filters.customer = ""; this.filters.salesperson = ""; this.filters.item_group = ""; this.filters.item_code = ""; this.filters.warehouse = ""; },
		onBranchSelected(option) { this.filters.branch = option?.value || ""; this.filters.customer = ""; this.filters.salesperson = ""; this.filters.warehouse = ""; }, clearBranch() { this.filters.branch = ""; this.filters.warehouse = ""; },
		onCustomerSelected(option) { this.filters.customer = option?.value || ""; }, clearCustomer() { this.filters.customer = ""; },
		onSalespersonSelected(option) { this.filters.salesperson = option?.value || ""; }, clearSalesperson() { this.filters.salesperson = ""; },
		onItemGroupSelected(option) { this.filters.item_group = option?.value || ""; this.filters.item_code = ""; }, clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; },
		onItemSelected(option) { this.filters.item_code = option?.value || ""; }, clearItem() { this.filters.item_code = ""; },
		onWarehouseSelected(option) { this.filters.warehouse = option?.value || ""; }, clearWarehouse() { this.filters.warehouse = ""; },
		async fetchData() { if (!this.filters.company) return; this.loading = true; this.error = ""; try { const result = await callMethod(this.pageMethod, { filters: { ...this.filters } }); this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.metadata = result.metadata || {}; this.scope = result.scope || {}; } catch (error) { this.rows = []; this.summary = []; this.error = errorMessage(error, "Sales Forecast failed to load."); } finally { this.loading = false; } },
		async loadExportDataset() { return callMethod(this.exportMethod, { filters: { ...this.filters } }); },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatCell(value, column) { if (column?.fieldtype === "Currency") return value === null || value === undefined ? "—" : this.formatCurrency(value); if (column?.fieldtype === "Date" && value) { try { return frappe.datetime.str_to_user(value); } catch (_error) { return String(value); } } if (value === null || value === undefined || value === "") return "—"; return String(value); },
	},
};
</script>

<style scoped>
.forecast-fallback { display: grid; gap: 6px; padding: 24px; }
.forecast-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.filter-action { display: flex; align-items: end; min-height: 42px; }
@media (max-width: 1100px) { .forecast-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .forecast-filter-grid { grid-template-columns: 1fr; } }
</style>
