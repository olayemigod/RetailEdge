<template>
	<div v-if="!edgeUIValid" class="customer-360-fallback">
		<strong>Customer 360 could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Customer 360"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/customer-360"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<section class="customer-360-page">
			<header class="customer-360-header">
				<div>
					<p class="customer-360-eyebrow">Customer Intelligence</p>
					<h2>Customer 360</h2>
					<p>Understand one customer from submitted ERPNext sales, current receivables and RetailEdge profitability evidence.</p>
				</div>
			</header>

			<div class="customer-360-filter-grid">
				<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
				<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
				<EdgeLinkField v-model="filters.customer" :selectedLabel="customerLabel" label="Customer" required placeholder="Search customer" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
				<label class="edge-field">
					<span class="edge-field-label">From Date</span>
					<input v-model="filters.from_date" class="edge-input" type="date" />
				</label>
				<label class="edge-field">
					<span class="edge-field-label">To Date</span>
					<input v-model="filters.to_date" class="edge-input" type="date" />
				</label>
				<div class="customer-360-filter-action">
					<button class="edge-primary-button" type="button" :disabled="loading || !filters.company || !filters.customer" @click="fetchData">
						{{ loading ? "Loading…" : "Load Customer" }}
					</button>
				</div>
			</div>

			<div v-if="error" class="alert alert-danger customer-360-error">{{ error }}</div>
			<div v-else-if="loading" class="customer-360-loading">Loading customer intelligence…</div>
			<div v-else-if="data.customer" class="customer-360-content">
				<section class="customer-profile-card">
					<div>
						<p class="customer-360-eyebrow">Customer</p>
						<h3>{{ data.customer.customer_name || data.customer.name }}</h3>
						<p>{{ [data.customer.name, data.customer.customer_group, data.customer.territory].filter(Boolean).join(" · ") }}</p>
					</div>
					<button type="button" class="edge-secondary-button" @click="openCustomer">Open Customer</button>
				</section>

				<section class="customer-360-metrics">
					<article v-for="metric in metrics" :key="metric.label" class="customer-360-metric">
						<span>{{ metric.label }}</span>
						<strong>{{ metric.value }}</strong>
					</article>
				</section>

				<section class="customer-360-grid">
					<article class="customer-360-panel">
						<h3>Relationship</h3>
						<dl>
							<div><dt>First purchase</dt><dd>{{ formatDate(data.relationship.first_purchase_date) }}</dd></div>
							<div><dt>Last purchase</dt><dd>{{ formatDate(data.relationship.last_purchase_date) }}</dd></div>
							<div><dt>Days since purchase</dt><dd>{{ valueOrDash(data.relationship.days_since_last_purchase) }}</dd></div>
							<div><dt>Purchases in period</dt><dd>{{ valueOrDash(data.relationship.period_purchase_count) }}</dd></div>
							<div><dt>Average days between purchases</dt><dd>{{ formatNumber(data.relationship.average_days_between_purchases) }}</dd></div>
						</dl>
					</article>
					<article class="customer-360-panel">
						<h3>Current Receivables</h3>
						<dl>
							<div><dt>Total outstanding</dt><dd>{{ formatCurrency(data.receivables.total_outstanding) }}</dd></div>
							<div><dt>Overdue</dt><dd>{{ formatCurrency(data.receivables.overdue_outstanding) }}</dd></div>
							<div><dt>Open invoices</dt><dd>{{ valueOrDash(data.receivables.open_invoice_count) }}</dd></div>
							<div><dt>Balance date</dt><dd>{{ formatDate(data.receivables.balance_date) }}</dd></div>
						</dl>
						<small>Receivables are current ERPNext outstanding balances, not reconstructed historical balances at the report end date.</small>
					</article>
				</section>

				<section class="customer-360-panel">
					<h3>Top Items</h3>
					<div class="customer-360-table-wrap">
						<table class="customer-360-table">
							<thead><tr><th>Item</th><th>Group</th><th>Net Qty</th><th>Invoices</th><th>Net Sales</th></tr></thead>
							<tbody>
								<tr v-for="row in data.top_items || []" :key="row.item_code">
									<td><button class="customer-360-link" type="button" @click="openDoc('Item', row.item_code)">{{ row.item_name || row.item_code }}</button></td>
									<td>{{ row.item_group || "—" }}</td><td>{{ formatNumber(row.net_qty) }}</td><td>{{ row.invoice_count }}</td><td>{{ formatCurrency(row.net_sales) }}</td>
								</tr>
								<tr v-if="!(data.top_items || []).length"><td colspan="5">No item activity in this period.</td></tr>
							</tbody>
						</table>
					</div>
				</section>

				<section class="customer-360-panel">
					<h3>Recent Invoices</h3>
					<div class="customer-360-table-wrap">
						<table class="customer-360-table">
							<thead><tr><th>Invoice</th><th>Date</th><th>Type</th><th>Net Amount</th><th>Outstanding</th><th>Status</th></tr></thead>
							<tbody>
								<tr v-for="row in data.recent_invoices || []" :key="row.invoice">
									<td><button class="customer-360-link" type="button" @click="openDoc('Sales Invoice', row.invoice)">{{ row.invoice }}</button></td>
									<td>{{ formatDate(row.posting_date) }}</td><td>{{ row.type }}</td><td>{{ formatCurrency(row.net_amount) }}</td><td>{{ formatCurrency(row.outstanding) }}</td><td>{{ row.status || "—" }}</td>
								</tr>
								<tr v-if="!(data.recent_invoices || []).length"><td colspan="6">No submitted invoices in this period.</td></tr>
							</tbody>
						</table>
					</div>
				</section>
			</div>
		</section>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "Customer360",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		const today = window.frappe?.datetime?.get_today?.() || new Date().toISOString().slice(0, 10);
		return {
			edgeUIValid: true, missingComponents: [], loading: false, error: "", data: {}, menuItems: [], tenantName: "", branchName: "", userName: "", customerLabel: "",
			filters: { company: "", branch: "", customer: "", from_date: `${today.slice(0, 7)}-01`, to_date: today },
		};
	},
	computed: {
		currency() { return this.data.company_currency || ""; },
		metrics() {
			const period = this.data.period || {};
			const metrics = [
				{ label: "Segment", value: period.segment || "—" },
				{ label: "Net Sales", value: this.formatCurrency(period.net_sales) },
				{ label: "Average Purchase", value: this.formatCurrency(period.average_purchase_value) },
				{ label: "Sales", value: this.valueOrDash(period.sales_invoice_count) },
				{ label: "Returns", value: this.valueOrDash(period.return_invoice_count) },
				{ label: "Current Outstanding", value: this.formatCurrency(period.current_outstanding) },
			];
			if (Number(this.data.show_profitability)) {
				metrics.push({ label: "Transactional Gross Profit", value: this.formatCurrency(period.gross_profit) });
				metrics.push({ label: "Gross Margin", value: period.gross_margin_percent == null ? "—" : `${Number(period.gross_margin_percent).toFixed(1)}%` });
			}
			return metrics;
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
			try {
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.sales_reporting.get_sales_reporting_context"),
					typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context"),
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}), customer: this.filters.customer || "" };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				const routeOptions = frappe.route_options || {};
				if (routeOptions.customer) {
					this.filters.customer = routeOptions.customer;
					this.customerLabel = routeOptions.customer_name || routeOptions.customer;
					if (routeOptions.from_date) this.filters.from_date = routeOptions.from_date;
					if (routeOptions.to_date) this.filters.to_date = routeOptions.to_date;
					if (routeOptions.branch) this.filters.branch = routeOptions.branch;
					frappe.route_options = null;
					await this.fetchData();
				}
			} catch (error) { this.error = errorMessage(error, "Failed to load Customer 360 controls."); }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
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
			const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch });
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, customerSearch(txt) { return this.searchOptions("customer", txt); },
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.clearCustomer(); },
		onBranchSelected(option) { this.filters.branch = option?.value || ""; this.clearCustomer(); }, clearBranch() { this.filters.branch = ""; this.clearCustomer(); },
		onCustomerSelected(option) { this.filters.customer = option?.value || ""; this.customerLabel = option?.label || this.filters.customer; }, clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; this.data = {}; },
		async fetchData() {
			if (!this.filters.company || !this.filters.customer) return;
			this.loading = true; this.error = "";
			try { this.data = await callMethod("retailedge.customer_360.get_customer_360", { filters: this.filters }); }
			catch (error) { this.data = {}; this.error = errorMessage(error, "Failed to load Customer 360."); }
			finally { this.loading = false; }
		},
		openCustomer() { if (this.data.customer?.name) this.openDoc("Customer", this.data.customer.name); },
		openDoc(doctype, name) {
			if (!name) return;
			const slug = String(doctype).toLowerCase().replace(/\s+/g, "-");
			window.open(`/app/${slug}/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer");
		},
		formatCurrency(value) { const number = Number(value || 0); return this.currency ? `${this.currency} ${number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); },
		formatNumber(value) { return value == null ? "—" : Number(value).toLocaleString(undefined, { maximumFractionDigits: 2 }); },
		formatDate(value) { return value || "—"; }, valueOrDash(value) { return value == null ? "—" : value; },
	},
};
</script>

<style scoped>
.customer-360-page { display: grid; gap: 1rem; padding: 0.5rem 0 2rem; }
.customer-360-header, .customer-profile-card, .customer-360-panel, .customer-360-metric { border: 1px solid var(--border-color, #dfe3e8); border-radius: 12px; background: var(--card-bg, #fff); }
.customer-360-header, .customer-profile-card, .customer-360-panel { padding: 1rem; }
.customer-profile-card { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.customer-360-eyebrow { margin: 0 0 0.25rem; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
.customer-360-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.75rem; align-items: end; }
.customer-360-filter-action { display: flex; align-items: end; min-height: 56px; }
.customer-360-metrics { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 0.75rem; }
.customer-360-metric { padding: 0.9rem; display: grid; gap: 0.3rem; }
.customer-360-metric span { font-size: 0.78rem; opacity: 0.75; }
.customer-360-metric strong { font-size: 1.05rem; }
.customer-360-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 0.75rem; }
.customer-360-panel h3, .customer-profile-card h3 { margin-top: 0; }
dl { display: grid; gap: 0.55rem; margin: 0; } dl div { display: flex; justify-content: space-between; gap: 1rem; } dt { opacity: 0.75; } dd { margin: 0; font-weight: 600; text-align: right; }
.customer-360-table-wrap { overflow-x: auto; }.customer-360-table { width: 100%; border-collapse: collapse; }.customer-360-table th, .customer-360-table td { padding: 0.65rem; border-bottom: 1px solid var(--border-color, #e5e7eb); text-align: left; white-space: nowrap; }.customer-360-link { border: 0; background: transparent; padding: 0; font: inherit; font-weight: 600; text-decoration: underline; cursor: pointer; color: inherit; }
.customer-360-error, .customer-360-loading { padding: 1rem; }
@media (max-width: 640px) { .customer-profile-card { align-items: flex-start; flex-direction: column; } }
</style>
