<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Owner Dashboard could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Owner Dashboard"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/owner-dashboard"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Owner Dashboard"
			eyebrow="Business Overview"
			subtitle="Period performance plus current balances and stock, composed from RetailEdge's existing reporting engines."
			:summary="headlineSummary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="availableSections.length > 0 && capabilities.can_export"
			:printEnabled="availableSections.length > 0 && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Building owner overview…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #filters>
				<div class="owner-dashboard-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="20rem">
				<EdgeDashboardSection
					v-if="attention.length"
					title="Attention Required"
					description="Operational exceptions surfaced from the same RetailEdge reports behind this dashboard."
					span="2"
				>
					<div class="owner-attention-list">
						<button
							v-for="item in attention"
							:key="`${item.section}-${item.metric}`"
							type="button"
							class="owner-attention-item"
							:class="`owner-attention-item--${item.tone || 'warning'}`"
							@click="openRoute(item.route)"
						>
							<span class="owner-attention-copy">
								<strong>{{ item.label }}</strong>
								<small>{{ item.metric }} · {{ timeBasisLabel(item.time_basis) }}</small>
							</span>
							<strong class="owner-attention-value">{{ formatCard(item) }}</strong>
						</button>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection
					v-for="section in availableSections"
					:key="section.key"
					:title="section.label"
					:description="sectionDescription(section)"
				>
					<div class="owner-section-cards">
						<div v-for="card in section.summary" :key="card.label" class="owner-metric">
							<span>{{ card.label }}</span>
							<strong>{{ formatCard(card) }}</strong>
						</div>
					</div>
					<button type="button" class="edge-button edge-button--secondary owner-open" @click="openSection(section)">Open {{ section.label }}</button>
				</EdgeDashboardSection>
				<EdgeDashboardSection v-if="unavailableSections.length" title="Restricted Sections" description="These views remain hidden because your current permissions do not allow their source reports.">
					<ul class="owner-restricted"><li v-for="section in unavailableSections" :key="section.key"><strong>{{ section.label }}</strong> — {{ section.reason }}</li></ul>
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
const DASHBOARD_KEY = "owner-dashboard";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "OwnerDashboard",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			exportBusy: false, printBusy: false,
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(),
			sections: {}, headlineSummary: [], attention: [], menuItems: [], tenantName: "", userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "" },
		};
	},
	computed: {
		sectionList() { return Object.entries(this.sections || {}).map(([key, value]) => ({ key, ...(value || {}) })); },
		availableSections() { return this.sectionList.filter((section) => section.available); },
		unavailableSections() { return this.sectionList.filter((section) => !section.available); },
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
				this.capabilities = context.capabilities || this.capabilities;
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Owner Dashboard controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.owner_dashboard.get_owner_dashboard_data", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.sections = result.sections || {};
				this.headlineSummary = result.headline_summary || [];
				this.attention = result.attention || [];
				this.capabilities = capabilities || this.capabilities;
			} catch (error) {
				this.sections = {};
				this.headlineSummary = [];
				this.attention = [];
				this.error = errorMessage(error, "Owner Dashboard failed to load.");
			}
			finally { this.loading = false; }
		},
		async handleExport(options) {
			if (!this.capabilities.can_export) return;
			this.exportBusy = true;
			try { await exportDashboard(DASHBOARD_KEY, this.filters, options); }
			catch (error) { frappe.msgprint({ title: __("Dashboard Export Failed"), message: errorMessage(error, "The Owner Dashboard could not be exported."), indicator: "red" }); }
			finally { this.exportBusy = false; }
		},
		async handlePrint() {
			if (!this.capabilities.can_print) return;
			this.printBusy = true;
			try { await printDashboard(DASHBOARD_KEY, this.filters); }
			catch (error) { frappe.msgprint({ title: __("Dashboard Print Failed"), message: errorMessage(error, "The Owner Dashboard print view could not be prepared."), indicator: "red" }); }
			finally { this.printBusy = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openRoute(route) { if (route) window.location.assign(route); },
		openSection(section) { this.openRoute(section?.route); },
		timeBasisLabel(value) { return value === "current" ? "Current position" : "Selected period"; },
		sectionDescription(section) {
			if (section.key === "stock" && section.show_costs === false) return "Current stock quantities; valuation remains hidden by your cost-visibility policy.";
			if (section.time_basis === "current") return "Current position as of today; the selected date range does not reconstruct a historical balance.";
			return "Performance for the selected date range from the existing RetailEdge source report.";
		},
		formatCard(card) { try { return frappe.format(card.value, { fieldtype: card.datatype || card.type || "Data" }); } catch (_error) { return card.value ?? "—"; } },
	},
};
</script>

<style scoped>
.owner-dashboard-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.owner-section-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.owner-metric { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
.owner-metric span { color: var(--edge-text-muted); font-size: 12px; }
.owner-metric strong { font-size: 1.05rem; }
.owner-attention-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.owner-attention-item { display: flex; align-items: center; justify-content: space-between; gap: 14px; width: 100%; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); text-align: left; cursor: pointer; }
.owner-attention-item--danger { border-color: var(--edge-danger, var(--edge-border)); }
.owner-attention-item--warning { border-color: var(--edge-warning, var(--edge-border)); }
.owner-attention-copy { display: grid; gap: 3px; }
.owner-attention-copy small { color: var(--edge-text-muted); }
.owner-attention-value { white-space: nowrap; }
.owner-open { margin-top: 14px; }
.owner-restricted { margin: 0; padding-left: 18px; display: grid; gap: 8px; }
@media (max-width: 720px) { .owner-dashboard-filters, .owner-section-cards, .owner-attention-list { grid-template-columns: 1fr; } }
</style>
