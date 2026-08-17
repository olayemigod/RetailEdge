<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Branch Performance could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Branch Performance"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/branch-performance-dashboard"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Branch Performance"
			eyebrow="Management Overview"
			subtitle="Compare sales, cash control, expenses, audit variance and payment issues across permitted branches."
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="rows.length > 0 && capabilities.can_export"
			:printEnabled="rows.length > 0 && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Building branch performance view…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #actions>
				<button type="button" class="edge-button edge-button--secondary" @click="openDetailReport">
					Detailed Report
				</button>
			</template>

			<template #filters>
				<div class="branch-performance-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.pos_profile" label="POS Profile" placeholder="All POS Profiles" :searcher="posProfileSearch" @select="onPosProfileSelected" @clear="clearPosProfile" />
					<EdgeLinkField v-model="filters.cashier" label="Cashier" placeholder="All permitted cashiers" :searcher="cashierSearch" @select="onCashierSelected" @clear="clearCashier" />
					<label class="edge-field">
						<span class="edge-field-label">Date Range Preset</span>
						<select v-model="filters.date_range_preset" class="edge-input" @change="onPresetChange">
							<option v-for="preset in datePresets" :key="preset" :value="preset">{{ preset }}</option>
						</select>
					</label>
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" @change="filters.date_range_preset = 'Custom Period'" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" @change="filters.date_range_preset = 'Custom Period'" /></label>
					<label class="edge-field">
						<span class="edge-field-label">Payment Method</span>
						<select v-model="filters.payment_method" class="edge-input"><option value="">All payment methods</option><option v-for="method in paymentMethods" :key="method" :value="method">{{ method }}</option></select>
					</label>
					<label class="branch-performance-check"><input v-model="filters.only_pos_invoices" type="checkbox" :true-value="1" :false-value="0" /> Only POS invoices</label>
					<label class="branch-performance-check"><input v-model="filters.include_unattributed" type="checkbox" :true-value="1" :false-value="0" /> Include unattributed</label>
					<label class="branch-performance-check"><input v-model="filters.include_fallback_branch_resolution" type="checkbox" :true-value="1" :false-value="0" /> Use fallback branch resolution</label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="24rem">
				<EdgeDashboardSection title="Branch Scorecard" description="Operational comparison using the existing RetailEdge Branch Performance engine." span="2">
					<EdgeReportTable :columns="dashboardColumns" :rows="rows" rowKey="branch" :formatter="formatCell" @cell-click="openCell" />
				</EdgeDashboardSection>
				<EdgeDashboardSection title="Attention Required" description="Branches with payment issues, pending audits or material cash variance.">
					<div v-if="attentionRows.length" class="branch-attention-list">
						<button v-for="row in attentionRows" :key="row.branch" type="button" class="branch-attention-item" @click="focusBranch(row.branch)">
							<strong>{{ row.branch || "Unattributed" }}</strong>
							<span>{{ row.payment_issues || 0 }} payment issue(s)</span>
							<span>Variance: {{ formatCurrency(row.audit_variance) }}</span>
							<span>{{ row.review_status || "Review" }}</span>
						</button>
					</div>
					<div v-else class="text-muted">No branch currently requires attention for the selected period.</div>
				</EdgeDashboardSection>
				<EdgeDashboardSection v-if="messages.length" title="Data Notes" description="Scope or source notes returned by the branch engine.">
					<ul class="branch-performance-notes"><li v-for="message in messages" :key="message">{{ message }}</li></ul>
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
const DASHBOARD_KEY = "branch-performance";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "BranchPerformanceDashboard",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			exportBusy: false, printBusy: false,
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(),
			rows: [], columns: [], summary: [], messages: [], menuItems: [], tenantName: "", userName: "", paymentMethods: [],
			datePresets: ["This Month", "Today", "Yesterday", "This Week", "This Quarter", "This Year", "Last Week", "Last Month", "Last Quarter", "Last Year", "Custom Period", "Full Branch History"],
			filters: { company: "", branch: "", pos_profile: "", cashier: "", date_range_preset: "This Month", from_date: "", to_date: "", payment_method: "", only_pos_invoices: 0, include_unattributed: 1, include_fallback_branch_resolution: 0 },
		};
	},
	computed: {
		dashboardColumns() {
			const wanted = new Set(["branch", "invoice_count", "gross_sales", "cash_sales", "bank_sales", "outstanding_amount", "cashier_expenses", "net_cash_expected", "audit_variance", "payment_issues", "review_status"]);
			return (this.columns || []).filter((column) => wanted.has(column.fieldname)).map((column) => ({ ...column, clickable: column.fieldname === "branch" }));
		},
		attentionRows() {
			return (this.rows || []).filter((row) => Number(row.payment_issues || 0) > 0 || Math.abs(Number(row.audit_variance || 0)) > 0 || Number(row.pending_audit_count || 0) > 0).slice(0, 8);
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
				const [context, navigation] = await Promise.all([callMethod("retailedge.branch_performance_dashboard.get_branch_performance_dashboard_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.capabilities = context.capabilities || this.capabilities;
				this.tenantName = context.tenant_name || this.filters.company || ""; this.userName = context.user_name || ""; this.paymentMethods = context.payment_methods || [];
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Branch Performance controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.branch_performance_dashboard.search_branch_performance_options", { kind, txt, company: this.filters.company }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, posProfileSearch(txt) { return this.searchOptions("pos_profile", txt); }, cashierSearch(txt) { return this.searchOptions("cashier", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.pos_profile = ""; }, onBranchSelected(option) { this.filters.branch = option.value; }, clearBranch() { this.filters.branch = ""; }, onPosProfileSelected(option) { this.filters.pos_profile = option.value; }, clearPosProfile() { this.filters.pos_profile = ""; }, onCashierSelected(option) { this.filters.cashier = option.value; }, clearCashier() { this.filters.cashier = ""; },
		onPresetChange() { if (this.filters.date_range_preset === "Custom Period") return; const dates = window.retailedge?.getPresetDates?.(this.filters.date_range_preset); if (dates) { this.filters.from_date = dates.from_date || ""; this.filters.to_date = dates.to_date || ""; } },
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.branch_performance_dashboard.get_branch_performance_dashboard_data", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.messages = result.messages || []; this.capabilities = capabilities || this.capabilities;
			} catch (error) { this.rows = []; this.summary = []; this.error = errorMessage(error, "Branch Performance failed to load."); }
			finally { this.loading = false; }
		},
		async handleExport(options) { if (!this.capabilities.can_export) return; this.exportBusy = true; try { await exportDashboard(DASHBOARD_KEY, this.filters, options); } catch (error) { frappe.msgprint({ title: __("Dashboard Export Failed"), message: errorMessage(error, "The dashboard could not be exported."), indicator: "red" }); } finally { this.exportBusy = false; } },
		async handlePrint() { if (!this.capabilities.can_print) return; this.printBusy = true; try { await printDashboard(DASHBOARD_KEY, this.filters); } catch (error) { frappe.msgprint({ title: __("Dashboard Print Failed"), message: errorMessage(error, "The dashboard print view could not be prepared."), indicator: "red" }); } finally { this.printBusy = false; } },
		focusBranch(branch) { this.filters.branch = branch === "Unattributed" ? "" : branch; this.fetchData(); },
		openCell(payload) { if (payload?.column?.fieldname === "branch") this.focusBranch(payload.value); },
		openDetailReport() { frappe.set_route("query-report", "RetailEdge Branch Performance Summary"); },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatCell(value, column) { if (column?.fieldtype === "Currency") return this.formatCurrency(value); if (value === null || value === undefined || value === "") return "—"; return String(value); },
	},
};
</script>

<style scoped>
.branch-performance-filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.branch-performance-check { display: flex; gap: 8px; align-items: center; min-height: 38px; font-size: 13px; color: var(--edge-text-muted); }
.branch-attention-list { display: grid; gap: 8px; }
.branch-attention-item { display: grid; grid-template-columns: minmax(8rem, 1fr) auto auto auto; gap: 10px; width: 100%; padding: 10px 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); text-align: left; cursor: pointer; }
.branch-performance-notes { margin: 0; padding-left: 18px; color: var(--edge-text-muted); }
@media (max-width: 1100px) { .branch-performance-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } .branch-attention-item { grid-template-columns: 1fr 1fr; } }
@media (max-width: 640px) { .branch-performance-filter-grid { grid-template-columns: 1fr; } .branch-attention-item { grid-template-columns: 1fr; } }
</style>
