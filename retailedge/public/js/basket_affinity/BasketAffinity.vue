<template>
	<div v-if="!edgeUIValid" class="basket-affinity-fallback">
		<strong>Basket & Product Affinity could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Basket & Product Affinity"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/basket-affinity"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Basket & Product Affinity"
			eyebrow="Sales Intelligence"
			subtitle="See which products appear together on submitted sales invoices using bounded, explainable basket support and confidence metrics."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="pair_key"
			:formatter="formatCell"
			emptyTitle="No product pairs found"
			emptyDescription="Adjust the period, branch, customer, product anchor or minimum pair count and try again."
			loadingMessage="Analysing submitted sale baskets…"
			@retry="fetchData"
			@cell-click="openReportCell"
		>
			<template #actions>
				<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
			</template>

			<template #filters>
				<div class="basket-affinity-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" class="edge-input" type="date" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" class="edge-input" type="date" /></label>
					<EdgeLinkField v-model="filters.customer" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<EdgeLinkField v-model="filters.salesperson" label="Salesperson" placeholder="All salespeople" :searcher="salespersonSearch" @select="onSalespersonSelected" @clear="clearSalesperson" />
					<EdgeLinkField v-model="filters.item_group" label="Product Group Anchor" placeholder="Any group" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<EdgeLinkField v-model="filters.item_code" label="Product Anchor" placeholder="Any product" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<label class="edge-field"><span class="edge-field-label">Minimum Times Together</span><input v-model.number="filters.minimum_pair_count" class="edge-input" type="number" min="1" step="1" /></label>
					<label class="edge-field"><span class="edge-field-label">Rows per page</span><select v-model.number="pageSize" class="edge-input"><option :value="25">25</option><option :value="50">50</option><option :value="100">100</option></select></label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="resetAndFetch">{{ loading ? "Analysing…" : "Apply / Refresh" }}</button></div>
				</div>
			</template>

			<template #resultMeta>
				<span>Submitted non-return Sales Invoices only</span>
				<span>Duplicate product lines count once per basket</span>
				<span>Basket share = pair baskets ÷ multi-item baskets</span>
				<span>Confidence A→B = pair baskets ÷ invoices containing A</span>
				<span>Product filters are anchors; companion products remain visible</span>
			</template>
		</EdgeReportShell>
		<div v-if="pagination.total_rows" class="basket-pagination">
			<span>Page {{ pagination.page }} · {{ pagination.total_rows }} pair(s)</span>
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
	name: "BasketAffinity",
	props: { pageMethod: { type: String, required: true }, exportMethod: { type: String, required: true } },
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], pagination: {}, metadata: {}, menuItems: [], tenantName: "", branchName: "", userName: "",
			page: 1, pageSize: 50,
			filters: { company: "", branch: "", from_date: "", to_date: "", customer: "", salesperson: "", item_group: "", item_code: "", minimum_pair_count: 1 },
		};
	},
	computed: {
		reportColumns() { return (this.columns || []).map((column) => ({ ...column, clickable: ["item_a", "item_b"].includes(column.fieldname), sortable: false })); },
		exportDataset() { return { title: "Basket & Product Affinity", filename: `RetailEdge Basket Affinity ${this.filters.company || ""}`.trim(), columns: this.columns, rows: this.rows, filters: this.exportFilters, summary: this.summary, metadata: this.exportMetadata }; },
		exportFilters() { const labels = { company: "Company", branch: "Branch", from_date: "From Date", to_date: "To Date", customer: "Customer", salesperson: "Salesperson", item_group: "Product Group Anchor", item_code: "Product Anchor", minimum_pair_count: "Minimum Times Together" }; return Object.entries(labels).map(([key, label]) => ({ label, value: this.filters[key] })).filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined); },
		exportMetadata() { return [ { label: "Sales Source", value: this.metadata.sales_truth || "Submitted non-return ERPNext Sales Invoice" }, { label: "Pair Definition", value: this.metadata.pair_definition || "Distinct products on the same sale invoice" }, { label: "Returns", value: this.metadata.returns || "Return invoices do not create pairs" }, { label: "Interpretation", value: "Explainable association only; no recommendation claim" } ]; },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.sales_reporting.get_sales_reporting_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}), item_code: "", item_group: "", salesperson: "", minimum_pair_count: 1 };
				this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Basket & Product Affinity controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer"); else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer"); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, customerSearch(txt) { return this.searchOptions("customer", txt); }, salespersonSearch(txt) { return this.searchOptions("salesperson", txt); }, itemGroupSearch(txt) { return this.searchOptions("item_group", txt); }, itemSearch(txt) { return this.searchOptions("item", txt); },
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.filters.customer = ""; this.filters.salesperson = ""; this.filters.item_group = ""; this.filters.item_code = ""; this.page = 1; },
		onBranchSelected(option) { this.filters.branch = option?.value || ""; this.filters.customer = ""; this.filters.salesperson = ""; this.page = 1; }, clearBranch() { this.filters.branch = ""; this.page = 1; },
		onCustomerSelected(option) { this.filters.customer = option?.value || ""; this.page = 1; }, clearCustomer() { this.filters.customer = ""; this.page = 1; },
		onSalespersonSelected(option) { this.filters.salesperson = option?.value || ""; this.page = 1; }, clearSalesperson() { this.filters.salesperson = ""; this.page = 1; },
		onItemGroupSelected(option) { this.filters.item_group = option?.value || ""; this.filters.item_code = ""; this.page = 1; }, clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; this.page = 1; },
		onItemSelected(option) { this.filters.item_code = option?.value || ""; this.page = 1; }, clearItem() { this.filters.item_code = ""; this.page = 1; },
		resetAndFetch() { this.page = 1; this.fetchData(); }, changePage(direction) { this.page = Math.max(1, this.page + direction); this.fetchData(); },
		async fetchData() { if (!this.filters.company) return; this.loading = true; this.error = ""; try { const result = await callMethod(this.pageMethod, { filters: { ...this.filters }, page: this.page, page_size: this.pageSize }); this.rows = (result.rows || []).map((row) => ({ ...row, pair_key: `${row.item_a}::${row.item_b}` })); this.columns = result.columns || []; this.summary = result.summary || []; this.pagination = result.pagination || {}; this.metadata = result.metadata || {}; } catch (error) { this.rows = []; this.summary = []; this.error = errorMessage(error, "Basket & Product Affinity failed to load."); } finally { this.loading = false; } },
		async loadExportDataset() { return callMethod(this.exportMethod, { filters: { ...this.filters } }); },
		openReportCell(payload) { const row = payload?.row || {}; const field = payload?.column?.fieldname; const item = field === "item_a" ? row.item_a : field === "item_b" ? row.item_b : ""; if (item) window.open(`/app/item/${encodeURIComponent(item)}`, "_blank", "noopener,noreferrer"); },
		formatCell(value, column) { if (column?.fieldtype === "Percent") return `${Number(value || 0).toFixed(1)}%`; if (value === null || value === undefined || value === "") return "—"; return String(value); },
	},
};
</script>

<style scoped>
.basket-affinity-fallback { display: grid; gap: 6px; padding: 24px; }
.basket-affinity-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.filter-action { display: flex; align-items: end; }
.basket-pagination { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 12px 4px; color: var(--edge-text-muted); font-size: 13px; }
.basket-pagination > div { display: flex; gap: 8px; }
@media (max-width: 1100px) { .basket-affinity-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .basket-affinity-filter-grid { grid-template-columns: 1fr; } .basket-pagination { flex-direction: column; align-items: flex-start; } }
</style>
