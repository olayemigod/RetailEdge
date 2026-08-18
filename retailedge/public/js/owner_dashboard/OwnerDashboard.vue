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
			subtitle="A concise management view composed from RetailEdge's existing sales, stock, cash, expense, receivable, payable and branch engines."
		:summary="headlineSummary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="false"
			:printEnabled="false"
			loadingMessage="Building owner overview…"
			@retry="fetchData"
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
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "OwnerDashboard",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			sections: {}, menuItems: [], tenantName: "", userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "" },
		};
	},
	computed: {
		sectionList() { return Object.entries(this.sections || {}).map(([key, value]) => ({ key, ...(value || {}) })); },
		availableSections() { return this.sectionList.filter((section) => section.available); },
		unavailableSections() { return this.sectionList.filter((section) => !section.available); },
		headlineSummary() {
			const preferred = [
				["sales", ["Net Sales", "Gross Sales", "Total Sales"]],
				["expenses", ["Total Expenses", "Expenses"]],
				["receivables", ["Total Receivables"]],
				["payables", ["Total Payables"]],
			];
			return preferred.flatMap(([key, labels]) => {
				const section = this.sections?.[key];
				if (!section?.available) return [];
				const card = (section.summary || []).find((item) => labels.includes(item.label));
				return card ? [{ ...card, label: card.label }] : [];
			});
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
			} catch (error) { this.error = errorMessage(error, "Failed to load Owner Dashboard controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try { const result = await callMethod("retailedge.owner_dashboard.get_owner_dashboard_data", { filters: this.filters }); this.sections = result.sections || {}; }
			catch (error) { this.sections = {}; this.error = errorMessage(error, "Owner Dashboard failed to load."); }
			finally { this.loading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openSection(section) { if (section?.route) window.location.assign(section.route); },
		sectionDescription(section) { return section.key === "stock" && section.show_costs === false ? "Stock quantities are shown using your permitted cost-visibility policy; valuation remains hidden." : "Summary from the existing RetailEdge source report."; },
		formatCard(card) { try { return frappe.format(card.value, { fieldtype: card.datatype || "Data" }); } catch (_error) { return card.value ?? "—"; } },
	},
};
</script>

<style scoped>
.owner-dashboard-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.owner-section-cards { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.owner-metric { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
.owner-metric span { color: var(--edge-text-muted); font-size: 12px; }
.owner-metric strong { font-size: 1.05rem; }
.owner-open { margin-top: 14px; }
.owner-restricted { margin: 0; padding-left: 18px; display: grid; gap: 8px; }
@media (max-width: 720px) { .owner-dashboard-filters, .owner-section-cards { grid-template-columns: 1fr; } }
</style>
