<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Sales Overview could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Sales Overview"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/sales-overview"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Sales Overview"
			eyebrow="Sales Performance"
			subtitle="Invoice health and product performance from RetailEdge's existing Sales Invoice Register and Sales by Item engines."
			:summary="headlineSummary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="Boolean(headlineSummary.length) && capabilities.can_export"
			:printEnabled="Boolean(headlineSummary.length) && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Building sales overview…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #filters>
				<div class="sales-dashboard-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="22rem">
				<EdgeDashboardSection v-if="attention.length" title="Attention Required" description="Sales exceptions surfaced from the Sales Invoice Register." span="2">
					<div class="sales-attention-list">
						<button v-for="item in attention" :key="item.metric" type="button" class="sales-attention-item" @click="openRoute(item.route)">
							<span><strong>{{ item.label }}</strong><small>{{ item.metric }}</small></span>
							<strong>{{ formatValue(item) }}</strong>
						</button>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Recent Invoices" description="Latest submitted invoices in the selected period.">
					<div v-if="recentInvoices.length" class="sales-list">
						<button v-for="row in recentInvoices" :key="row.invoice" type="button" class="sales-list-row" @click="openInvoice(row.invoice)">
							<span><strong>{{ row.invoice }}</strong><small>{{ row.customer_name || row.customer }} · {{ row.posting_date }}</small></span>
							<strong>{{ formatCurrency(row.grand_total) }}</strong>
						</button>
					</div>
					<div v-else class="sales-empty">No submitted invoices matched this period.</div>
					<button type="button" class="edge-button edge-button--secondary sales-open" @click="openRoute(routes.invoice_register)">Open Sales Invoice Register</button>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Top Items" description="Highest net sales items from the existing Sales by Item report.">
					<div v-if="topItems.length" class="sales-list">
						<div v-for="row in topItems" :key="row.item_code" class="sales-list-row sales-list-row--static">
							<span><strong>{{ row.item_name || row.item_code }}</strong><small>{{ row.item_code }} · Net Qty {{ row.net_qty }}</small></span>
							<strong>{{ formatCurrency(row.net_sales) }}</strong>
						</div>
					</div>
					<div v-else class="sales-empty">No item sales matched this period.</div>
					<button type="button" class="edge-button edge-button--secondary sales-open" @click="openRoute(routes.sales_by_item)">Open Sales by Item</button>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Performance Drill-downs" description="Use the established RetailEdge dashboards for salesperson and branch comparison.">
					<div class="sales-drilldowns">
						<button type="button" class="edge-button edge-button--secondary" @click="openRoute(routes.salesperson_performance)">Salesperson Performance</button>
						<button type="button" class="edge-button edge-button--secondary" @click="openRoute(routes.branch_performance)">Branch Performance</button>
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

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
const DASHBOARD_KEY = "sales-overview";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "SalesDashboard",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			exportBusy: false,
			printBusy: false,
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(),
			headlineSummary: [],
			attention: [],
			recentInvoices: [],
			topItems: [],
			routes: {},
			menuItems: [],
			tenantName: "",
			userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "" },
		};
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
					callMethod("retailedge.sales_dashboard.get_sales_dashboard_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.capabilities = context.capabilities || this.capabilities;
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Sales Overview controls.");
			} finally {
				this.metadataLoading = false;
			}
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.sales_dashboard.get_sales_dashboard_data", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.headlineSummary = result.headline_summary || [];
				this.attention = result.attention || [];
				this.recentInvoices = result.recent_invoices || [];
				this.topItems = result.top_items || [];
				this.routes = result.routes || {};
				this.capabilities = capabilities || this.capabilities;
			} catch (error) {
				this.headlineSummary = [];
				this.attention = [];
				this.recentInvoices = [];
				this.topItems = [];
				this.error = errorMessage(error, "Sales Overview failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async handleExport(options) {
			if (!this.capabilities.can_export) return;
			this.exportBusy = true;
			try { await exportDashboard(DASHBOARD_KEY, this.filters, options); }
			catch (error) { frappe.msgprint({ title: __("Dashboard Export Failed"), message: errorMessage(error, "Sales Overview could not be exported."), indicator: "red" }); }
			finally { this.exportBusy = false; }
		},
		async handlePrint() {
			if (!this.capabilities.can_print) return;
			this.printBusy = true;
			try { await printDashboard(DASHBOARD_KEY, this.filters); }
			catch (error) { frappe.msgprint({ title: __("Dashboard Print Failed"), message: errorMessage(error, "Sales Overview print view could not be prepared."), indicator: "red" }); }
			finally { this.printBusy = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openRoute(route) { if (route) window.location.assign(route); },
		openInvoice(name) { if (name) frappe.set_route("Form", "Sales Invoice", name); },
		formatValue(card) { try { return frappe.format(card.value, { fieldtype: card.datatype || card.type || "Data" }); } catch (_error) { return card.value ?? "—"; } },
		formatCurrency(value) { try { return frappe.format(value, { fieldtype: "Currency" }); } catch (_error) { return value ?? "—"; } },
	},
};
</script>

<style scoped>
.sales-dashboard-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.sales-attention-list, .sales-list { display: grid; gap: 9px; }
.sales-attention-list { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.sales-attention-item, .sales-list-row { display: flex; align-items: center; justify-content: space-between; gap: 14px; width: 100%; padding: 11px 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); text-align: left; }
button.sales-attention-item, button.sales-list-row { cursor: pointer; }
.sales-attention-item span, .sales-list-row span { display: grid; gap: 3px; }
.sales-attention-item small, .sales-list-row small, .sales-empty { color: var(--edge-text-muted); }
.sales-list-row--static { cursor: default; }
.sales-open { margin-top: 12px; }
.sales-drilldowns { display: flex; flex-wrap: wrap; gap: 10px; }
@media (max-width: 720px) { .sales-dashboard-filters, .sales-attention-list { grid-template-columns: 1fr; } }
</style>
