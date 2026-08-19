<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Action Centre could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Action Centre"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/action-center"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Action Centre"
			eyebrow="Exceptions & Follow-up"
			subtitle="Prioritised issues from existing RetailEdge and ERPNext controls. Resolve each item in its owning workflow or report."
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="false"
			:printEnabled="false"
			loadingMessage="Checking business exceptions…"
			@retry="fetchData"
		>
			<template #filters>
				<div class="action-center-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="23rem">
				<EdgeDashboardSection title="Critical" description="Issues that can affect cash control, stock integrity, posting, or materially overdue balances.">
					<div v-if="critical.length" class="action-list">
						<button v-for="item in critical" :key="itemKey(item)" class="action-row action-row--danger" type="button" @click="openRoute(item.route)">
							<span class="action-copy"><strong>{{ item.label }}</strong><small>{{ sourceLabel(item.source) }} · {{ basisLabel(item.time_basis) }}</small></span>
							<strong>{{ formatValue(item.value, item.datatype) }}</strong>
						</button>
					</div>
					<div v-else class="action-empty">No critical exceptions are visible in your current scope.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Needs Attention" description="Items requiring review, follow-up, or management attention.">
					<div v-if="warnings.length" class="action-list">
						<button v-for="item in warnings" :key="itemKey(item)" class="action-row action-row--warning" type="button" @click="openRoute(item.route)">
							<span class="action-copy"><strong>{{ item.label }}</strong><small>{{ sourceLabel(item.source) }} · {{ basisLabel(item.time_basis) }}</small></span>
							<strong>{{ formatValue(item.value, item.datatype) }}</strong>
						</button>
					</div>
					<div v-else class="action-empty">No attention items are visible in your current scope.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-if="unavailableSources.length" title="Unavailable Sources" description="These sources were excluded because your current permissions do not allow them.">
					<div class="source-list">
						<div v-for="source in unavailableSources" :key="source.key" class="source-row"><strong>{{ sourceLabel(source.key) }}</strong><small>{{ source.reason }}</small></div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="How resolution works" description="Action Centre is a read-only prioritisation layer." span="2">
					<div class="action-note">
						<strong>RetailEdge does not close these issues here.</strong>
						<span>Opening an item takes you to the existing Expense Review, Receivables, Payables, Stock Position, Cash Shift Verification, or other owning workflow. Existing ERPNext/RetailEdge permissions, approvals, submissions and accounting controls remain authoritative.</span>
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
	name: "RetailEdgeActionCenter",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			summary: [], items: [], sources: {}, metadata: {}, menuItems: [], tenantName: "", userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "" },
		};
	},
	computed: {
		critical() { return this.items.filter((item) => item.severity === "danger"); },
		warnings() { return this.items.filter((item) => item.severity === "warning"); },
		unavailableSources() { return Object.values(this.sources || {}).filter((source) => !source.available); },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.action_center.get_action_center_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) }; this.tenantName = context.tenant_name || this.filters.company || ""; this.userName = context.user_name || ""; this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Action Centre controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return; this.loading = true; this.error = "";
			try {
				const result = await callMethod("retailedge.action_center.get_action_center_data", { filters: this.filters });
				this.summary = result.summary || []; this.items = result.items || []; this.sources = result.sources || {}; this.metadata = result.metadata || {};
			} catch (error) { this.error = errorMessage(error, "Action Centre failed to load."); }
			finally { this.loading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openRoute(route) { if (route) window.location.assign(route); },
		itemKey(item) { return `${item.source}:${item.kind}:${item.label}:${item.route}`; },
		sourceLabel(source) { return String(source || "management").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); },
		basisLabel(value) { return value === "current" ? "Current position" : "Selected period"; },
		formatValue(value, datatype) { try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value ?? "—"; } },
	},
};
</script>

<style scoped>
.action-center-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.action-list, .source-list { display: grid; gap: 9px; }
.action-row { display: flex; justify-content: space-between; align-items: center; gap: 14px; width: 100%; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); text-align: left; cursor: pointer; }
.action-row--danger { border-color: var(--red-300, var(--edge-border)); }
.action-row--warning { border-color: var(--orange-300, var(--edge-border)); }
.action-copy, .source-row, .action-note { display: grid; gap: 4px; }
.action-copy small, .source-row small, .action-note span, .action-empty { color: var(--edge-text-muted); font-size: 12px; }
.source-row, .action-note { padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
@media (max-width: 720px) { .action-center-filters { grid-template-columns: 1fr; } .action-row { align-items: flex-start; } }
</style>
