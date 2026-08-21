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
			:exportEnabled="summary.length > 0 && capabilities.can_export"
			:printEnabled="summary.length > 0 && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Calculating profitability…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
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

				<EdgeDashboardSection title="Margin Leakage" description="Negative and low-margin items requiring owner review. Evidence opens only for the selected item.">
					<div class="profit-table-wrap">
						<table class="profit-table">
							<thead><tr><th>Item</th><th>Net Sales</th><th>Cost</th><th>Profit</th><th>Margin</th><th></th></tr></thead>
							<tbody>
								<tr v-for="row in marginLeakage" :key="row.item_code">
									<td><strong>{{ row.item_name || row.item_code }}</strong><small>{{ row.item_code }}</small></td>
									<td>{{ money(row.net_sales) }}</td><td>{{ money(row.cost_of_sales) }}</td><td>{{ money(row.gross_profit) }}</td><td>{{ percent(row.gross_margin_percent) }}</td>
									<td><button type="button" class="edge-button edge-button--secondary" :disabled="evidenceBusy === row.item_code" @click="reviewLeakage(row)">{{ evidenceBusy === row.item_code ? "Loading…" : "Review Evidence" }}</button></td>
								</tr>
								<tr v-if="!marginLeakage.length"><td colspan="6" class="empty-cell">No low-margin leakage detected in this period.</td></tr>
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
import {
	defaultDashboardExportOptions,
	exportDashboard,
	getDashboardCapabilities,
	printDashboard,
} from "../retailedge_dashboard_actions";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
const DASHBOARD_KEY = "profitability-intelligence";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ProfitabilityIntelligence",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			exportBusy: false, printBusy: false, evidenceBusy: "",
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(),
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
				{ key: "salesperson", label: "Profitability by Salesperson", entityLabel: "Salesperson", description: "Profit contribution allocated using ERPNext Sales Team percentages.", rows: this.dimensions.salesperson || [] },
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
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.profitability_intelligence.get_profitability_intelligence", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.summary = result.summary || [];
				this.topContributors = result.top_contributors || [];
				this.marginLeakage = result.margin_leakage || [];
				this.dimensions = result.dimensions || {};
				this.comparison = result.comparison || {};
				this.companyCurrency = result.company_currency || "";
				this.capabilities = capabilities || this.capabilities;
			} catch (error) {
				this.summary = []; this.topContributors = []; this.marginLeakage = []; this.dimensions = {}; this.comparison = {};
				this.error = errorMessage(error, "Profitability Intelligence failed to load.");
			} finally { this.loading = false; }
		},
		async handleExport(options) {
			if (!this.capabilities.can_export) return;
			this.exportBusy = true;
			try { await exportDashboard(DASHBOARD_KEY, this.filters, options); }
			catch (error) { frappe.msgprint({ title: __("Profitability Export Failed"), message: errorMessage(error, "Profitability Intelligence could not be exported."), indicator: "red" }); }
			finally { this.exportBusy = false; }
		},
		async handlePrint() {
			if (!this.capabilities.can_print) return;
			this.printBusy = true;
			try { await printDashboard(DASHBOARD_KEY, this.filters); }
			catch (error) { frappe.msgprint({ title: __("Profitability Print Failed"), message: errorMessage(error, "The profitability print view could not be prepared."), indicator: "red" }); }
			finally { this.printBusy = false; }
		},
		async reviewLeakage(row) {
			if (!row?.item_code) return;
			this.evidenceBusy = row.item_code;
			try {
				const evidence = await callMethod("retailedge.profitability_leakage.get_margin_leakage_evidence", { item_code: row.item_code, filters: this.filters });
				this.showEvidenceDialog(evidence);
			} catch (error) { frappe.msgprint({ title: __("Margin Evidence Failed"), message: errorMessage(error, "Margin evidence could not be loaded."), indicator: "red" }); }
			finally { this.evidenceBusy = ""; }
		},
		showEvidenceDialog(evidence) {
			const rows = evidence?.rows || [];
			if (!rows.length) { frappe.msgprint(__("No submitted invoice evidence was found for this item in the selected scope.")); return; }
			const options = rows.map((row) => row.invoice).join("\n");
			const dialog = new frappe.ui.Dialog({
				title: __(`Margin Evidence — ${evidence.item_name || evidence.item_code}`),
				fields: [
					{ fieldtype: "Select", fieldname: "invoice", label: __("Sales Invoice"), options, default: rows[0].invoice, reqd: 1 },
					{ fieldtype: "Data", fieldname: "customer", label: __("Customer"), read_only: 1 },
					{ fieldtype: "Date", fieldname: "posting_date", label: __("Posting Date"), read_only: 1 },
					{ fieldtype: "Currency", fieldname: "net_sales", label: __("Net Sales"), read_only: 1 },
					{ fieldtype: "Currency", fieldname: "cost_of_sales", label: __("Cost of Sales"), read_only: 1 },
					{ fieldtype: "Currency", fieldname: "gross_profit", label: __("Gross Profit"), read_only: 1 },
					{ fieldtype: "Percent", fieldname: "gross_margin_percent", label: __("Gross Margin"), read_only: 1 },
					{ fieldtype: "Percent", fieldname: "discount_percentage", label: __("Discount"), read_only: 1 },
				],
				primary_action_label: __("Open Sales Invoice"),
				primary_action: (values) => {
					const selected = rows.find((candidate) => candidate.invoice === values.invoice);
					if (selected?.route) window.open(selected.route, "_blank", "noopener,noreferrer");
				},
			});
			const sync = () => {
				const invoice = dialog.get_value("invoice");
				const selected = rows.find((candidate) => candidate.invoice === invoice) || rows[0];
				for (const field of ["customer", "posting_date", "net_sales", "cost_of_sales", "gross_profit", "gross_margin_percent", "discount_percentage"]) dialog.set_value(field, selected[field] ?? "");
			};
			dialog.fields_dict.invoice.df.onchange = sync;
			dialog.show();
			sync();
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
.profit-table { width: 100%; border-collapse: collapse; min-width: 700px; }
.profit-table th, .profit-table td { padding: 10px 12px; border-bottom: 1px solid var(--edge-border); text-align: right; vertical-align: top; }
.profit-table th:first-child, .profit-table td:first-child { text-align: left; }
.profit-table td small { display: block; color: var(--edge-text-muted); margin-top: 2px; }
.empty-cell { color: var(--edge-text-muted); text-align: center !important; padding: 18px !important; }
@media (max-width: 720px) { .profitability-filters, .comparison-grid { grid-template-columns: 1fr; } }
</style>
