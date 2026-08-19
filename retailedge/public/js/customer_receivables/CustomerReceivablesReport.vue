<template>
	<div v-if="!edgeUIValid" class="receivables-fallback">
		<strong>Customer Receivables could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Customer Receivables"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/customer-receivables"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Customer Receivables"
			eyebrow="Customers & Receivables"
			subtitle="Current unpaid customer invoices, overdue exposure, and ageing from ERPNext Sales Invoice accounting truth."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No current receivables"
			emptyDescription="No unpaid customer invoices match the current scope."
			loadingMessage="Loading customer receivables…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="openReportCell"
		>
			<template #filters>
				<div class="receivables-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.customer" :selectedLabel="customerLabel" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<label class="edge-field">
						<span class="edge-field-label">Age</span>
						<select v-model="filters.ageing_bucket" class="edge-input">
							<option v-for="bucket in ageingBuckets" :key="bucket" :value="bucket">{{ bucket }}</option>
						</select>
					</label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Loading…" : "Apply Filters" }}</button></div>
				</div>
				<details class="advanced-filters">
					<summary>More filters</summary>
					<div class="receivables-filter-grid advanced-grid">
						<EdgeLinkField v-model="filters.customer_group" label="Customer Group" placeholder="All customer groups" :searcher="customerGroupSearch" />
						<label class="edge-field">
							<span class="edge-field-label">Balance Basis</span>
							<input value="Current outstanding" class="edge-input" type="text" readonly />
						</label>
					</div>
				</details>
			</template>
			<template #resultMeta>
				<span>Current ERPNext outstanding balances aged at {{ currentBalanceDate || "today" }}</span>
				<span v-if="scan.invoices !== undefined">{{ scan.invoices }} submitted invoice{{ scan.invoices === 1 ? "" : "s" }} scanned</span>
				<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				<span>Bounded server dataset · {{ providerDatasetLimit.toLocaleString() }} row cap</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "customer-receivables";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "CustomerReceivablesReport",
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
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			currentBalanceDate: "",
			customerLabel: "",
			filters: { company: "", branch: "", customer: "", customer_group: "", ageing_bucket: "All", page_size: 50 },
			currentPage: 1,
			ageingBuckets: ["All", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "91+ Days"],
		};
	},
	computed: {
		reportProvider() { return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) || null; },
		providerDatasetLimit() { return Number(this.reportProvider?.max_dataset_rows || 0); },
		reportColumns() { return (this.columns || []).filter((column) => !column.hidden).map((column) => ({ ...column, fieldtype: column.fieldtype || column.type || "Data", clickable: ["invoice", "customer"].includes(column.fieldname) })); },
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
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.customer_receivables.get_customer_receivables_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.currentBalanceDate = context.current_balance_date || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Customer Receivables controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.customer_receivables.search_customer_receivables_options", { kind, txt, company: this.filters.company }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		customerSearch(txt) { return this.searchOptions("customer", txt); },
		customerGroupSearch(txt) { return this.searchOptions("customer_group", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.branchName = ""; this.currentPage = 1; },
		onBranchSelected(option) { this.filters.branch = option.value; this.branchName = option.label || option.value; this.currentPage = 1; },
		clearBranch() { this.filters.branch = ""; this.branchName = ""; this.currentPage = 1; },
		onCustomerSelected(option) { this.filters.customer = option.value; this.customerLabel = option.label || option.value; this.currentPage = 1; },
		clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; this.currentPage = 1; },
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		providerFilters() { const { page_size: _pageSize, ...filters } = this.filters; return filters; },
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) { this.error = "The shared EdgeSuite Customer Receivables provider is unavailable."; return; }
			this.loading = true;
			this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50);
				const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({ filters: this.providerFilters(), start, page_length: pageSize });
				this.rows = result.rows || [];
				this.columns = (result.columns || []).filter((column) => !column.hidden);
				this.summary = result.summary || [];
				this.scan = result.metadata?.scan || {};
				this.companyCurrency = result.metadata?.company_currency || this.companyCurrency;
				this.currentBalanceDate = result.metadata?.current_balance_date || this.currentBalanceDate;
				const totalRows = Number(result.total || this.rows.length);
				const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
				if (this.currentPage > totalPages) this.currentPage = totalPages;
				this.pagination = { page: this.currentPage, page_size: pageSize, total_rows: totalRows, total_pages: totalPages, has_previous: this.currentPage > 1, has_next: this.currentPage < totalPages };
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = errorMessage(error, "Customer Receivables failed to load.");
			} finally { this.loading = false; }
		},
		goToPage(page) { const next = Math.max(1, Number(page || 1)); if (next === this.currentPage) return; this.currentPage = next; this.fetchData(); },
		setPageSize(pageSize) { this.filters.page_size = Number(pageSize || 50); this.currentPage = 1; this.fetchData(); },
		rowKey(row, index) { return row.invoice || `customer-receivables:${index}`; },
		openReportCell(payload) { const column = payload?.column; const row = payload?.row; if (!column || !row) return; const value = row[column.fieldname]; if (!value) return; if (column.fieldname === "invoice") frappe.set_route("Form", "Sales Invoice", value); else if (column.fieldname === "customer") frappe.set_route("Form", "Customer", value); },
		formatCell(value, column) { return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency); },
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") { const number = Number(value); if (!Number.isFinite(number)) return String(value); try { return frappe.format(number, { fieldtype: "Currency", options: currency || this.companyCurrency }); } catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } }
			if (fieldtype === "Int") return Number(value).toLocaleString();
			if (fieldtype === "Date") { try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } }
			return String(value);
		},
	},
};
</script>

<style scoped>
.receivables-fallback { margin:20px; padding:24px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); display:flex; flex-direction:column; gap:8px; }
.receivables-filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:var(--edge-space-md,16px); align-items:end; width:100%; }
.advanced-filters { margin-top:var(--edge-space-md,16px); }
.advanced-filters summary { cursor:pointer; font-weight:600; color:var(--edge-text,#101828); }
.advanced-grid { margin-top:var(--edge-space-sm,10px); }
.edge-field { display:flex; flex-direction:column; gap:6px; min-width:0; }
.edge-field-label { font-size:.78rem; font-weight:600; color:var(--edge-text-muted,#667085); }
.edge-input,.edge-primary-button { min-height:38px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); padding:0 10px; }
.edge-primary-button { background:var(--edge-primary,#0f766e); color:#fff; border-color:var(--edge-primary,#0f766e); font-weight:600; cursor:pointer; }
.edge-primary-button:disabled { opacity:.55; cursor:not-allowed; }
@media (max-width:1180px) { .receivables-filter-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media (max-width:860px) { .receivables-filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:560px) { .receivables-filter-grid { grid-template-columns:1fr; } }
</style>
