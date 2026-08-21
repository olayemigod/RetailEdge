<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Profitability Intelligence could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Profitability Intelligence"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/profitability-intelligence"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Profitability Intelligence"
			eyebrow="Owner Intelligence"
			subtitle="Gross profit, contribution, period movement and margin leakage from submitted ERPNext sales and recorded item cost."
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			loadingMessage="Calculating profitability…"
			@retry="fetchData"
		>
			<template #filters>
				<div class="profitability-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="24rem">
				<EdgeDashboardSection title="Previous Period" :description="comparisonDescription">
					<div class="comparison-grid">
						<div v-for="metric in comparison.metrics || []" :key="metric.key" class="comparison-card">
							<span>{{ metric.label }}</span>
							<strong>{{ formatMetric(metric.current, metric.datatype) }}</strong>
							<small>{{ formatChange(metric) }} vs previous period</small>
						</div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Top Profit Contributors" description="Items ranked by gross-profit contribution in the selected period.">
					<div class="profit-table-wrap">
						<table class="profit-table">
							<thead><tr><th>Item</th><th>Net Sales</th><th>Gross Profit</th><th>Margin</th></tr></thead>
							<tbody>
								<tr v-for="row in topContributors" :key="row.item_code">
									<td><strong>{{ row.item_name || row.item_code }}</strong><small>{{ row.item_code }}</small></td>
									<td>{{ money(row.net_sales) }}</td><td>{{ money(row.gross_profit) }}</td><td>{{ percent(row.gross_margin_percent) }}</td>
								</tr>
								<tr v-if="!topContributors.length"><td colspan="4" class="empty-cell">No profitability rows for this period.</td></tr>
							</tbody>
						</table>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Margin Leakage" description="Negative and low-margin items requiring owner review.">
					<div class="profit-table-wrap">
						<table class="profit-table">
							<thead><tr><th>Item</th><th>Net Sales</th><th>Cost</th><th>Profit</th><th>Margin</th></tr></thead>
							<tbody>
								<tr v-for="row in marginLeakage" :key="row.item_code">
									<td><strong>{{ row.item_name || row.item_code }}</strong><small>{{ row.item_code }}</small></td>
									<td>{{ money(row.net_sales) }}</td><td>{{ money(row.cost_of_sales) }}</td><td>{{ money(row.gross_profit) }}</td><td>{{ percent(row.gross_margin_percent) }}</td>
								</tr>
								<tr v-if="!marginLeakage.length"><td colspan="5" class="empty-cell">No low-margin leakage detected in this period.</td></tr>
							</tbody>
						</table>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-for="dimension in dimensionSections" :key="dimension.key" :title="dimension.label" :description="dimension.description">
					<div class="profit-table-wrap">
						<table class="profit-table">
							<thead><tr><th>{{ dimension.entityLabel }}</th><th>Net Sales</th><th>Gross Profit</th><th>Margin</th></tr></thead>
							<tbody>
								<tr v-for="row in dimension.rows" :key="row.key">
									<td><strong>{{ row.key }}</strong></td><td>{{ money(row.net_sales) }}</td><td>{{ money(row.gross_profit) }}</td><td>{{ percent(row.gross_margin_percent) }}</td>
								</tr>
								<tr v-if="!dimension.rows.length"><td colspan="4" class="empty-cell">No data for this dimension.</td></tr>
							</tbody>
						</table>
					</div>
				</EdgeDashboardSection>
			</EdgeDashboardGrid>
		</EdgeDashboardShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ProfitabilityIntelligence",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			summary: [], topContributors: [], marginLeakage: [], dimensions: {}, comparison: {}, menuItems: [], tenantName: "", userName: "", companyCurrency: "",
			filters: { company: "", branch: "", from_date: "", to_date: "" },
		};
	},
	computed: {
		comparisonDescription() {
			if (!this.comparison.previous_from_date) return "Selected period compared with the immediately preceding equal-length period.";
			return `${this.comparison.previous_from_date} to ${this.comparison.previous_to_date}`;
		},
		dimensionSections() {
			return [
				{ key: "branch", label: "Profitability by Branch", entityLabel: "Branch", description: "Gross-profit contribution by permitted branch.", rows: this.dimensions.branch || [] },
				{ key: "item_group", label: "Profitability by Item Group", entityLabel: "Item Group", description: "Product-category contribution and margin.", rows: this.dimensions.item_group || [] },
				{ key: "customer", label: "Profitability by Customer", entityLabel: "Customer", description: "Customer contribution ranked by gross profit.", rows: this.dimensions.customer || [] },
				{ key: "salesperson", label: "Profitability by Salesperson", entityLabel: "Salesperson", description: "Gross profit allocated using ERPNext Sales Team percentages without double-counting invoice contribution.", rows: this.dimensions.salesperson || [] },
			];
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
				const [context, navigation] = await Promise.all([callMethod("retailedge.owner_dashboard.get_owner_dashboard_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load profitability controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod("retailedge.profitability_intelligence.get_profitability_intelligence", { filters: this.filters });
				this.summary = result.summary || [];
				this.topContributors = result.top_contributors || [];
				this.marginLeakage = result.margin_leakage || [];
				this.dimensions = result.dimensions || {};
				this.comparison = result.comparison || {};
				this.companyCurrency = result.company_currency || "";
			} catch (error) {
				this.summary = []; this.topContributors = []; this.marginLeakage = []; this.dimensions = {}; this.comparison = {};
				this.error = errorMessage(error, "Profitability Intelligence failed to load.");
			} finally { this.loading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		money(value) { try { return frappe.format(value, { fieldtype: "Currency", options: this.companyCurrency }); } catch (_error) { return value ?? "—"; } },
		percent(value) { return `${Number(value || 0).toFixed(1)}%`; },
		formatMetric(value, datatype) { return datatype === "Percent" ? this.percent(value) : this.money(value); },
		formatChange(metric) {
			if (metric.change_percent === null || metric.change_percent === undefined) return "No comparable base";
			const sign = Number(metric.change_percent) > 0 ? "+" : "";
			return `${sign}${Number(metric.change_percent).toFixed(1)}%`;
		},
	},
};
</script>

<style scoped>
.profitability-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.comparison-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.comparison-card { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
.comparison-card span, .comparison-card small { color: var(--edge-text-muted); }
.profit-table-wrap { overflow-x: auto; }
.profit-table { width: 100%; border-collapse: collapse; min-width: 620px; }
.profit-table th, .profit-table td { padding: 10px 12px; border-bottom: 1px solid var(--edge-border); text-align: right; vertical-align: top; }
.profit-table th:first-child, .profit-table td:first-child { text-align: left; }
.profit-table td small { display: block; color: var(--edge-text-muted); margin-top: 2px; }
.empty-cell { color: var(--edge-text-muted); text-align: center !important; padding: 18px !important; }
@media (max-width: 720px) { .profitability-filters, .comparison-grid { grid-template-columns: 1fr; } }
</style>
