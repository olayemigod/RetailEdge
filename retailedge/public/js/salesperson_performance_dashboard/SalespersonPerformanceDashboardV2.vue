<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Salesperson Performance could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Salesperson Performance"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/salesperson-performance-dashboard"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Salesperson Performance"
			eyebrow="Sales Intelligence"
			subtitle="Review submitted invoice performance using ERPNext Sales Team allocation percentages."
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="rows.length > 0 && capabilities.can_export"
			:printEnabled="rows.length > 0 && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Aggregating salesperson performance…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #actions>
				<button type="button" class="edge-button edge-button--secondary" @click="openSalesInvoices">Sales Invoices</button>
			</template>

			<template #filters>
				<div class="salesperson-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.salesperson" label="Salesperson" placeholder="All salespeople" :searcher="salespersonSearch" @select="onSalespersonSelected" @clear="clearSalesperson" />
					<EdgeLinkField v-model="filters.customer" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<EdgeLinkField v-model="filters.item" label="Item" placeholder="All items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
					<EdgeLinkField v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
					<label class="edge-field">
						<span class="edge-field-label">Date Range Preset</span>
						<select v-model="filters.date_range_preset" class="edge-input" @change="onPresetChange">
							<option v-for="preset in datePresets" :key="preset" :value="preset">{{ preset }}</option>
						</select>
					</label>
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" @change="filters.date_range_preset = 'Custom Period'" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" @change="filters.date_range_preset = 'Custom Period'" /></label>
					<label class="edge-field">
						<span class="edge-field-label">Rows per page</span>
						<select v-model.number="filters.limit" class="edge-input" @change="resetAndFetch"><option :value="25">25</option><option :value="50">50</option><option :value="100">100</option></select>
					</label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="resetAndFetch">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="25rem">
				<EdgeDashboardSection title="Invoice Allocation Detail" description="Each row reflects the salesperson share recorded on the submitted Sales Invoice." span="2">
					<EdgeReportTable :columns="tableColumns" :rows="rows" :rowKey="rowKey" :formatter="formatCell" @cell-click="openCell" />
					<div class="salesperson-pagination">
						<span>Page {{ currentPage }} · {{ rows.length }} row(s)</span>
						<div class="salesperson-pagination-actions">
							<button class="edge-button edge-button--secondary" type="button" :disabled="loading || !pagination.has_previous" @click="changePage(-1)">Previous</button>
							<button class="edge-button edge-button--secondary" type="button" :disabled="loading || !pagination.has_next" @click="changePage(1)">Next</button>
						</div>
					</div>
				</EdgeDashboardSection>
				<EdgeDashboardSection title="Allocation Policy" description="How RetailEdge interprets the ERPNext source records.">
					<div class="salesperson-policy">
						<strong>Submitted invoices only</strong>
						<span>Gross, net, discount and outstanding values are proportionally split using Sales Team allocated percentage.</span>
						<span>Company and Branch scope are enforced on the server.</span>
						<span>Download is capped at {{ exportRowCap }} rows per request.</span>
					</div>
				</EdgeDashboardSection>
			</EdgeDashboardGrid>
		</EdgeDashboardShell>
	</EdgeAppShell>
</template>

<script>
import {
	defaultDashboardExportOptions,
	exportDashboard,
	getDashboardCapabilities,
	printDashboard,
} from "../retailedge_dashboard_actions";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection", "EdgeReportTable", "EdgeLinkField"];
const DASHBOARD_KEY = "salesperson-performance";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "SalespersonPerformanceDashboardV2",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			exportBusy: false, printBusy: false,
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(),
			rows: [], columns: [], summary: [], pagination: {}, menuItems: [], tenantName: "", userName: "", exportRowCap: 500,
			datePresets: ["This Month", "Today", "Yesterday", "This Week", "This Quarter", "This Year", "Last Week", "Last Month", "Last Quarter", "Last Year", "Custom Period"],
			filters: { company: "", date_range_preset: "This Month", from_date: "", to_date: "", branch: "", salesperson: "", customer: "", item: "", item_group: "", limit: 50, offset: 0 },
		};
	},
	computed: {
		currentPage() { return Math.floor(Number(this.filters.offset || 0) / Number(this.filters.limit || 50)) + 1; },
		tableColumns() { return (this.columns || []).map((column) => ({ ...column, clickable: ["salesperson", "sales_invoice", "customer"].includes(column.fieldname) })); },
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.salesperson_performance_dashboard.get_salesperson_dashboard_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.capabilities = context.capabilities || this.capabilities;
				this.tenantName = context.tenant_name || this.filters.company || ""; this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Salesperson Performance controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.salesperson_performance_dashboard.search_salesperson_dashboard_options", { kind, txt, company: this.filters.company }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, salespersonSearch(txt) { return this.searchOptions("salesperson", txt); }, customerSearch(txt) { return this.searchOptions("customer", txt); }, itemSearch(txt) { return this.searchOptions("item", txt); }, itemGroupSearch(txt) { return this.searchOptions("item_group", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.offset = 0; }, onBranchSelected(option) { this.filters.branch = option.value; this.filters.offset = 0; }, clearBranch() { this.filters.branch = ""; this.filters.offset = 0; }, onSalespersonSelected(option) { this.filters.salesperson = option.value; this.filters.offset = 0; }, clearSalesperson() { this.filters.salesperson = ""; this.filters.offset = 0; }, onCustomerSelected(option) { this.filters.customer = option.value; this.filters.offset = 0; }, clearCustomer() { this.filters.customer = ""; this.filters.offset = 0; }, onItemSelected(option) { this.filters.item = option.value; this.filters.offset = 0; }, clearItem() { this.filters.item = ""; this.filters.offset = 0; }, onItemGroupSelected(option) { this.filters.item_group = option.value; this.filters.offset = 0; }, clearItemGroup() { this.filters.item_group = ""; this.filters.offset = 0; },
		onPresetChange() { if (this.filters.date_range_preset === "Custom Period") return; const dates = window.retailedge?.getPresetDates?.(this.filters.date_range_preset); if (dates) { this.filters.from_date = dates.from_date || ""; this.filters.to_date = dates.to_date || ""; } this.filters.offset = 0; },
		resetAndFetch() { this.filters.offset = 0; this.fetchData(); },
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.salesperson_performance_dashboard.get_salesperson_dashboard_data", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.pagination = result.pagination || {}; this.capabilities = capabilities || this.capabilities; this.exportRowCap = result.metadata?.export_row_cap || 500;
			} catch (error) { this.rows = []; this.summary = []; this.error = errorMessage(error, "Salesperson Performance failed to load."); }
			finally { this.loading = false; }
		},
		changePage(direction) { const limit = Number(this.filters.limit || 50); this.filters.offset = Math.max(0, Number(this.filters.offset || 0) + direction * limit); this.fetchData(); },
		async handleExport(options) { if (!this.capabilities.can_export) return; this.exportBusy = true; try { await exportDashboard(DASHBOARD_KEY, this.filters, options); } catch (error) { frappe.msgprint({ title: __("Dashboard Export Failed"), message: errorMessage(error, "The dashboard could not be exported."), indicator: "red" }); } finally { this.exportBusy = false; } },
		async handlePrint() { if (!this.capabilities.can_print) return; this.printBusy = true; try { await printDashboard(DASHBOARD_KEY, this.filters); } catch (error) { frappe.msgprint({ title: __("Dashboard Print Failed"), message: errorMessage(error, "The dashboard print view could not be prepared."), indicator: "red" }); } finally { this.printBusy = false; } },
		openCell(payload) { const row = payload?.row || {}; const field = payload?.column?.fieldname; if (field === "salesperson" && row.salesperson) frappe.set_route("Form", "Sales Person", row.salesperson); if (field === "sales_invoice" && row.sales_invoice) frappe.set_route("Form", "Sales Invoice", row.sales_invoice); if (field === "customer" && row.customer) frappe.set_route("Form", "Customer", row.customer); },
		openSalesInvoices() { frappe.set_route("List", "Sales Invoice"); },
		rowKey(row, index) { return `${row.salesperson || "salesperson"}-${row.sales_invoice || index}`; },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatCell(value, column) { if (column?.fieldtype === "Currency") return this.formatCurrency(value); if (column?.fieldtype === "Date" && value) { try { return frappe.datetime.str_to_user(value); } catch (_error) { return String(value); } } if (value === null || value === undefined || value === "") return "—"; return String(value); },
	},
};
</script>

<style scoped>
.salesperson-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.salesperson-pagination { display: flex; justify-content: space-between; gap: 12px; align-items: center; margin-top: 12px; color: var(--edge-text-muted); font-size: 13px; }
.salesperson-pagination-actions { display: flex; gap: 8px; }
.salesperson-policy { display: grid; gap: 8px; color: var(--edge-text-muted); font-size: 13px; }
.salesperson-policy strong { color: var(--edge-text); }
@media (max-width: 1100px) { .salesperson-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .salesperson-filter-grid { grid-template-columns: 1fr; } .salesperson-pagination { align-items: flex-start; flex-direction: column; } }
</style>
