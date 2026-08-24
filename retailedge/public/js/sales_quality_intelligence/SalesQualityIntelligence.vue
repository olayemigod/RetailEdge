<template>
	<div v-if="!edgeUIValid" class="sales-quality-fallback">
		<strong>Discount & Sales Quality could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Discount & Sales Quality"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/sales-quality-intelligence"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Discount & Sales Quality"
			eyebrow="Sales Quality"
			subtitle="Review recorded price reductions, additional invoice discounts, returns and transactional margin quality without replacing ERPNext accounting truth."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="invoice"
			:formatter="formatCell"
			emptyTitle="No submitted sales matched this scope"
			emptyDescription="Adjust the date, branch, customer, salesperson or product filters and try again."
			loadingMessage="Reviewing submitted sales quality…"
			@retry="fetchData"
			@cell-click="openReportCell"
		>
			<template #actions>
				<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
			</template>

			<template #filters>
				<div class="sales-quality-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" class="edge-input" type="date" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" class="edge-input" type="date" /></label>
					<EdgeLinkField v-model="filters.customer" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<EdgeLinkField v-model="filters.salesperson" label="Salesperson" placeholder="All salespeople" :searcher="salespersonSearch" @select="onSalespersonSelected" @clear="clearSalesperson" />
					<EdgeLinkField v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<EdgeLinkField v-model="filters.item_code" label="Item" placeholder="All items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<EdgeLinkField v-model="filters.warehouse" label="Warehouse" placeholder="All permitted warehouses" :searcher="warehouseSearch" @select="onWarehouseSelected" @clear="clearWarehouse" />
					<label class="edge-field"><span class="edge-field-label">High Reduction Threshold (%)</span><input v-model.number="filters.high_reduction_percent" class="edge-input" type="number" min="0" max="100" step="1" /></label>
					<label v-if="showCosts" class="edge-field"><span class="edge-field-label">Low Margin Threshold (%)</span><input v-model.number="filters.low_margin_percent" class="edge-input" type="number" min="-100" max="100" step="1" /></label>
					<label class="edge-field"><span class="edge-field-label">Rows per page</span><select v-model.number="pageSize" class="edge-input" @change="resetAndFetch"><option :value="25">25</option><option :value="50">50</option><option :value="100">100</option></select></label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="resetAndFetch">{{ loading ? "Reviewing…" : "Apply / Refresh" }}</button></div>
				</div>
			</template>

			<template #resultMeta>
				<span>Reference value uses recorded rate-with-margin, falling back to recorded price-list rate</span>
				<span>Price Reduction is reference value minus submitted net sales; Additional Discount is shown separately from ERPNext</span>
				<span>Returns are reported separately and are not labelled discount leakage</span>
				<span v-if="showCosts">Margin uses the R8 transactional incoming-rate × stock-quantity contract</span>
				<span v-else>Cost and margin data are not fetched under the current cost-visibility policy</span>
				<span>ERPNext Profit & Loss remains financial profit truth</span>
			</template>
		</EdgeReportShell>
		<div v-if="pagination.total_rows" class="sales-quality-pagination">
			<span>Page {{ pagination.page }} · {{ pagination.total_rows }} invoice(s)</span>
			<div><button class="edge-button edge-button--secondary" :disabled="loading || !pagination.has_previous" @click="changePage(-1)">Previous</button><button class="edge-button edge-button--secondary" :disabled="loading || !pagination.has_next" @click="changePage(1)">Next</button></div>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "SalesQualityIntelligence",
	props: { pageMethod: { type: String, required: true }, exportMethod: { type: String, required: true } },
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], pagination: {}, metadata: {}, menuItems: [], tenantName: "", branchName: "", userName: "", showCosts: false,
			page: 1, pageSize: 50,
			filters: { company: "", branch: "", from_date: "", to_date: "", customer: "", salesperson: "", item_group: "", item_code: "", warehouse: "", high_reduction_percent: 10, low_margin_percent: 10 },
		};
	},
	computed: {
		reportColumns() { return (this.columns || []).map((column) => ({ ...column, clickable: ["invoice", "customer"].includes(column.fieldname), sortable: false })); },
		exportDataset() { return { title: "Discount & Sales Quality", filename: `RetailEdge Discount Sales Quality ${this.filters.company || ""}`.trim(), columns: this.columns, rows: this.rows, filters: this.exportFilters, summary: this.summary, metadata: this.exportMetadata }; },
		exportFilters() { const labels = { company: "Company", branch: "Branch", from_date: "From Date", to_date: "To Date", customer: "Customer", salesperson: "Salesperson", item_group: "Item Group", item_code: "Item", warehouse: "Warehouse", high_reduction_percent: "High Reduction Threshold (%)", low_margin_percent: "Low Margin Threshold (%)" }; return Object.entries(labels).map(([key, label]) => ({ label, value: this.filters[key] })).filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined && (key => key !== "low_margin_percent" || this.showCosts)(key)); },
		exportMetadata() { return [ { label: "Sales Source", value: this.metadata.sales_truth || "Submitted ERPNext Sales Invoice / Sales Invoice Item" }, { label: "Reduction", value: this.metadata.reduction_definition || "Recorded reference value less submitted net sales" }, { label: "Additional Discount", value: this.metadata.additional_discount_truth || "ERPNext invoice-level additional discount" }, { label: "Returns", value: this.metadata.returns || "Reported separately" }, { label: "Financial Profit", value: this.metadata.financial_truth || "ERPNext Profit and Loss" } ]; },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.sales_reporting.get_sales_reporting_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}), item_code: "", item_group: "", salesperson: "", warehouse: "", high_reduction_percent: 10, low_margin_percent: 10 };
				this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Discount & Sales Quality controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer"); else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer"); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, customerSearch(txt) { return this.searchOptions("customer", txt); }, salespersonSearch(txt) { return this.searchOptions("salesperson", txt); }, itemGroupSearch(txt) { return this.searchOptions("item_group", txt); }, itemSearch(txt) { return this.searchOptions("item", txt); }, warehouseSearch(txt) { return this.searchOptions("warehouse", txt); },
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.filters.customer = ""; this.filters.salesperson = ""; this.filters.item_group = ""; this.filters.item_code = ""; this.filters.warehouse = ""; this.page = 1; },
		onBranchSelected(option) { this.filters.branch = option?.value || ""; this.filters.customer = ""; this.filters.salesperson = ""; this.filters.warehouse = ""; this.page = 1; }, clearBranch() { this.filters.branch = ""; this.filters.warehouse = ""; this.page = 1; },
		onCustomerSelected(option) { this.filters.customer = option?.value || ""; this.page = 1; }, clearCustomer() { this.filters.customer = ""; this.page = 1; },
		onSalespersonSelected(option) { this.filters.salesperson = option?.value || ""; this.page = 1; }, clearSalesperson() { this.filters.salesperson = ""; this.page = 1; },
		onItemGroupSelected(option) { this.filters.item_group = option?.value || ""; this.filters.item_code = ""; this.page = 1; }, clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; this.page = 1; },
		onItemSelected(option) { this.filters.item_code = option?.value || ""; this.page = 1; }, clearItem() { this.filters.item_code = ""; this.page = 1; },
		onWarehouseSelected(option) { this.filters.warehouse = option?.value || ""; this.page = 1; }, clearWarehouse() { this.filters.warehouse = ""; this.page = 1; },
		resetAndFetch() { this.page = 1; this.fetchData(); }, changePage(direction) { this.page = Math.max(1, this.page + direction); this.fetchData(); },
		async fetchData() { if (!this.filters.company) return; this.loading = true; this.error = ""; try { const result = await callMethod(this.pageMethod, { filters: { ...this.filters }, page: this.page, page_size: this.pageSize }); this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.pagination = result.pagination || {}; this.metadata = result.metadata || {}; this.showCosts = Boolean(result.show_costs); } catch (error) { this.rows = []; this.summary = []; this.error = errorMessage(error, "Discount & Sales Quality failed to load."); } finally { this.loading = false; } },
		async loadExportDataset() { return callMethod(this.exportMethod, { filters: { ...this.filters } }); },
		openReportCell(payload) { const row = payload?.row || {}; const field = payload?.column?.fieldname; if (field === "invoice" && row.invoice) window.open(`/app/sales-invoice/${encodeURIComponent(row.invoice)}`, "_blank", "noopener,noreferrer"); if (field === "customer" && row.customer) window.open(`/app/customer/${encodeURIComponent(row.customer)}`, "_blank", "noopener,noreferrer"); },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatCell(value, column) { if (column?.fieldtype === "Currency") return this.formatCurrency(value); if (column?.fieldtype === "Percent") return `${Number(value || 0).toFixed(1)}%`; if (column?.fieldtype === "Date" && value) { try { return frappe.datetime.str_to_user(value); } catch (_error) { return String(value); } } if (value === null || value === undefined || value === "") return "—"; return String(value); },
	},
};
</script>

<style scoped>
.sales-quality-fallback { display: grid; gap: 6px; padding: 24px; }
.sales-quality-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.filter-action { display: flex; align-items: end; }
.sales-quality-pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 4px; color: var(--edge-text-muted); font-size: 13px; }
.sales-quality-pagination > div { display: flex; gap: 8px; }
@media (max-width: 1100px) { .sales-quality-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .sales-quality-filter-grid { grid-template-columns: 1fr; } .sales-quality-pagination { flex-direction: column; align-items: flex-start; } }
</style>
