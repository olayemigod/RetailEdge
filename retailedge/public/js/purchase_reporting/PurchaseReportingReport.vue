<template>
	<div v-if="!edgeUIValid" class="purchase-report-fallback">
		<strong>Purchase reporting could not start.</strong>
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
		:activeRoute="activeRoute"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			:title="config.title"
			eyebrow="Purchasing & Payables"
			:subtitle="config.subtitle"
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No matching purchases"
			emptyDescription="Adjust the scope or filters and try again."
			loadingMessage="Loading purchase report…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="openReportCell"
		>
			<template #filters>
				<div class="purchase-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<template v-if="reportType === 'purchase_register'">
						<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
						<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					</template>
					<div v-else class="edge-field">
						<span class="edge-field-label">Balance Basis</span>
						<div class="edge-input edge-input--readonly">Current outstanding · {{ filters.as_of_date || "Today" }}</div>
					</div>
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.supplier" :selectedLabel="supplierLabel" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
					<label v-if="reportType === 'supplier_payables'" class="edge-field">
						<span class="edge-field-label">Age</span>
						<select v-model="filters.ageing_bucket" class="edge-input">
							<option v-for="bucket in ageingBuckets" :key="bucket" :value="bucket">{{ bucket }}</option>
						</select>
					</label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !requiredReady" @click="applyFilters">{{ loading ? "Loading…" : "Apply Filters" }}</button></div>
				</div>
				<details class="advanced-filters">
					<summary>More filters</summary>
					<div class="purchase-filter-grid advanced-grid">
						<EdgeLinkField v-model="filters.supplier_group" label="Supplier Group" placeholder="All supplier groups" :searcher="supplierGroupSearch" />
						<EdgeLinkField v-if="reportType === 'purchase_register'" v-model="filters.item_group" label="Item Group" placeholder="All item groups" :searcher="itemGroupSearch" @select="onItemGroupSelected" @clear="clearItemGroup" />
						<EdgeLinkField v-if="reportType === 'purchase_register'" v-model="filters.item_code" :selectedLabel="itemLabel" label="Item" placeholder="All items" :searcher="itemSearch" @select="onItemSelected" @clear="clearItem" />
						<EdgeLinkField v-if="reportType === 'purchase_register'" v-model="filters.warehouse" label="Warehouse" placeholder="All warehouses in scope" :searcher="warehouseSearch" @select="onWarehouseSelected" @clear="filters.warehouse = ''" />
						<label v-if="reportType === 'purchase_register'" class="edge-field"><span class="edge-field-label">Invoice Type</span><select v-model="filters.invoice_kind" class="edge-input"><option value="All">All</option><option value="Purchases">Purchases</option><option value="Returns">Returns</option></select></label>
						<label class="edge-field"><span class="edge-field-label">Invoice Status</span><select v-model="filters.status" class="edge-input"><option value="">All statuses</option><option v-for="status in invoiceStatuses" :key="status" :value="status">{{ status }}</option></select></label>
					</div>
				</details>
			</template>
			<template #resultMeta>
				<span v-if="scan.invoices !== undefined">{{ scan.invoices }} submitted invoice{{ scan.invoices === 1 ? "" : "s" }} scanned</span>
				<span v-if="reportType === 'supplier_payables'">Current ERPNext outstanding balances aged at {{ payablesAgeingDate || filters.as_of_date || "today" }}</span>
				<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				<span>Bounded server dataset · {{ providerDatasetLimit.toLocaleString() }} row cap</span>
			</template>
		</EdgeReportShell>

		<SimplePaymentDialog
			v-if="reportType === 'supplier_payables'"
			:open="supplierPaymentOpen"
			intent="pay-supplier"
			:initialContext="supplierPaymentContext"
			@close="closeSupplierPayment"
			@saved="handleSupplierPaymentSaved"
			@open-native="openNativePayment"
		/>
	</EdgeAppShell>
</template>

<script>
import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_CONFIG = {
	purchase_register: {
		title: "Purchase Register",
		subtitle: "A clear invoice-level view of submitted purchases, returns, taxes, due dates, and outstanding balances.",
		providerKey: "purchase-register",
		route: "/app/purchase-register",
	},
	supplier_payables: {
		title: "Supplier Payables",
		subtitle: "See current unpaid supplier bills, overdue exposure, due dates, and ageing from ERPNext's live outstanding balances.",
		providerKey: "supplier-payables",
		route: "/app/supplier-payables",
	},
};

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "PurchaseReportingReport",
	props: { reportType: { type: String, default: "purchase_register" } },
	components: {
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
		SimplePaymentDialog,
	},
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], pagination: {}, scan: {}, menuItems: [], tenantName: "", branchName: "", userName: "", companyCurrency: "",
			supplierLabel: "", itemLabel: "", payablesAgeingDate: "",
			filters: { company: "", from_date: "", to_date: "", as_of_date: "", branch: "", supplier: "", supplier_group: "", item_code: "", item_group: "", warehouse: "", status: "", invoice_kind: "All", ageing_bucket: "All", page_size: 50 },
			currentPage: 1,
			supplierPaymentOpen: false,
			supplierPaymentContext: {},
			ageingBuckets: ["All", "Current", "1-30 Days", "31-60 Days", "61-90 Days", "91+ Days"],
			invoiceStatuses: ["Paid", "Unpaid", "Overdue", "Partly Paid", "Return", "Credit Note"],
		};
	},
	computed: {
		config() { return REPORT_CONFIG[this.reportType] || REPORT_CONFIG.purchase_register; },
		activeRoute() { return this.config.route; },
		requiredReady() { return Boolean(this.filters.company && (this.reportType === "supplier_payables" || this.filters.from_date && this.filters.to_date)); },
		reportProvider() { return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey) || window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, this.config.providerKey) || null; },
		providerDatasetLimit() { return Number(this.reportProvider?.max_dataset_rows || 0); },
		reportColumns() {
			const columns = (this.columns || []).filter((column) => !column.hidden).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: ["invoice", "supplier", "return_against"].includes(column.fieldname),
			}));
			if (this.reportType === "supplier_payables") {
				columns.push({ label: "Payment", fieldname: "payment_action", fieldtype: "Data", width: 110, clickable: true });
			}
			return columns;
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
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.purchase_reporting.get_purchase_reporting_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || ""; this.companyCurrency = context.company_currency || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.requiredReady) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Purchase report controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.purchase_reporting.search_purchase_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch, item_group: this.filters.item_group }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, supplierSearch(txt) { return this.searchOptions("supplier", txt); }, supplierGroupSearch(txt) { return this.searchOptions("supplier_group", txt); }, itemGroupSearch(txt) { return this.searchOptions("item_group", txt); }, itemSearch(txt) { return this.searchOptions("item", txt); }, warehouseSearch(txt) { return this.searchOptions("warehouse", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.warehouse = ""; this.branchName = ""; this.currentPage = 1; },
		onBranchSelected(option) { this.filters.branch = option.value; this.filters.warehouse = ""; this.branchName = option.label || option.value; this.currentPage = 1; },
		clearBranch() { this.filters.branch = ""; this.filters.warehouse = ""; this.branchName = ""; this.currentPage = 1; },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.supplierLabel = option.label || option.value; this.currentPage = 1; }, clearSupplier() { this.filters.supplier = ""; this.supplierLabel = ""; this.currentPage = 1; },
		onItemGroupSelected(option) { this.filters.item_group = option.value; this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; }, clearItemGroup() { this.filters.item_group = ""; this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		onItemSelected(option) { this.filters.item_code = option.value; this.itemLabel = option.label || option.value; if (!this.filters.item_group && option.raw?.item_group) this.filters.item_group = option.raw.item_group; this.currentPage = 1; }, clearItem() { this.filters.item_code = ""; this.itemLabel = ""; this.currentPage = 1; },
		async onWarehouseSelected(option) { this.filters.warehouse = option.value; this.currentPage = 1; if (!this.filters.company) return; try { const resolved = await callMethod("retailedge.guided_entry_context.resolve_branch_warehouse_selection", { company: this.filters.company, branch: this.filters.branch, warehouse: this.filters.warehouse, preference: "default" }); if (resolved.branch) { this.filters.branch = resolved.branch; this.branchName = resolved.branch; } } catch (error) { this.filters.warehouse = ""; this.error = errorMessage(error, "The selected Warehouse is not valid for this purchase context."); } },
		applyFilters() { this.currentPage = 1; return this.fetchData(); },
		providerFilters() { const { page_size: _pageSize, ...filters } = this.filters; if (this.reportType === "supplier_payables") { delete filters.from_date; delete filters.to_date; delete filters.item_code; delete filters.item_group; delete filters.warehouse; delete filters.invoice_kind; } else { delete filters.as_of_date; delete filters.ageing_bucket; } return filters; },
		async fetchData() {
			if (!this.requiredReady) return; if (!this.reportProvider?.load) { this.error = `The shared EdgeSuite ${this.config.title} provider is unavailable.`; return; }
			this.loading = true; this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50); const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({ filters: this.providerFilters(), start, page_length: pageSize });
				const providerRows = result.rows || [];
				this.rows = this.reportType === "supplier_payables"
					? providerRows.map((row) => ({ ...row, payment_action: "Pay Supplier" }))
					: providerRows;
				this.columns = (result.columns || []).filter((column) => !column.hidden); this.summary = result.summary || []; this.scan = result.metadata?.scan || {}; this.companyCurrency = result.metadata?.company_currency || this.companyCurrency; this.payablesAgeingDate = result.metadata?.ageing_date || this.payablesAgeingDate;
				const totalRows = Number(result.total || this.rows.length); const totalPages = Math.max(1, Math.ceil(totalRows / pageSize)); if (this.currentPage > totalPages) this.currentPage = totalPages;
				this.pagination = { page: this.currentPage, page_size: pageSize, total_rows: totalRows, total_pages: totalPages, has_previous: this.currentPage > 1, has_next: this.currentPage < totalPages };
			} catch (error) { this.rows = []; this.columns = []; this.summary = []; this.error = errorMessage(error, `${this.config.title} failed to load.`); }
			finally { this.loading = false; }
		},
		goToPage(page) { const next = Math.max(1, Number(page || 1)); if (next === this.currentPage) return; this.currentPage = next; this.fetchData(); },
		setPageSize(pageSize) { this.filters.page_size = Number(pageSize || 50); this.currentPage = 1; this.fetchData(); },
		rowKey(row, index) { return row.invoice || `${this.reportType}:${index}`; },
		openSupplierPayment(row) {
			if (this.reportType !== "supplier_payables" || !row?.invoice || !row?.supplier) return;
			this.supplierPaymentContext = {
				company: this.filters.company || "",
				branch: row.branch || this.filters.branch || "",
				party: row.supplier,
				reference_name: row.invoice,
			};
			this.supplierPaymentOpen = true;
		},
		closeSupplierPayment() { this.supplierPaymentOpen = false; this.supplierPaymentContext = {}; },
		async handleSupplierPaymentSaved(result) {
			this.closeSupplierPayment();
			await this.fetchData();
			if (result?.name) frappe.set_route("Form", "Payment Entry", result.name);
		},
		openNativePayment() { this.closeSupplierPayment(); frappe.new_doc("Payment Entry"); },
		openReportCell(payload) {
			const column = payload?.column; const row = payload?.row;
			if (!column || !row) return;
			if (column.fieldname === "payment_action") { this.openSupplierPayment(row); return; }
			const value = row[column.fieldname]; if (!value) return;
			if (["invoice", "return_against"].includes(column.fieldname)) frappe.set_route("Form", "Purchase Invoice", value);
			else if (column.fieldname === "supplier") frappe.set_route("Form", "Supplier", value);
		},
		formatCell(value, column) { return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency); },
		formatValue(value, fieldtype, currency) { if (value === null || value === undefined || value === "") return "—"; if (fieldtype === "Currency") { const number = Number(value); if (!Number.isFinite(number)) return String(value); try { return frappe.format(number, { fieldtype: "Currency", options: currency || this.companyCurrency }); } catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } } if (fieldtype === "Float") { const number = Number(value); return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : String(value); } if (fieldtype === "Int") return Number(value).toLocaleString(); if (fieldtype === "Date") { try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } } return String(value); },
	},
};
</script>

<style scoped>
.purchase-report-fallback { margin:20px; padding:24px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); display:flex; flex-direction:column; gap:8px; }
.purchase-filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:var(--edge-space-md,16px); align-items:end; width:100%; }
.advanced-filters { margin-top:var(--edge-space-md,16px); }
.advanced-filters summary { cursor:pointer; font-weight:600; color:var(--edge-text,#101828); }
.advanced-grid { margin-top:var(--edge-space-sm,10px); }
.edge-field { display:flex; flex-direction:column; gap:6px; min-width:0; }
.edge-field-label { font-size:.78rem; font-weight:600; color:var(--edge-text-muted,#667085); }
.edge-input,.edge-primary-button { min-height:38px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); padding:0 10px; }
.edge-input--readonly { display:flex; align-items:center; color:var(--edge-text-muted,#667085); background:var(--edge-surface-subtle,#f8fafc); }
.edge-primary-button { background:var(--edge-primary,#0f766e); color:#fff; border-color:var(--edge-primary,#0f766e); font-weight:600; cursor:pointer; }
.edge-primary-button:disabled { opacity:.55; cursor:not-allowed; }
@media (max-width:1180px) { .purchase-filter-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } }
@media (max-width:860px) { .purchase-filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:560px) { .purchase-filter-grid { grid-template-columns:1fr; } }
</style>