<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Business Control Centre could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Business Control Centre"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/business-control-center"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Business Control Centre"
			eyebrow="Business Control & Financial Intelligence"
			subtitle="One prioritised view of operational exceptions and management financial signals. ERPNext remains authoritative for accounting balances and submitted transactions."
			:summary="summaryCards"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="false"
			:printEnabled="false"
			loadingMessage="Checking business controls…"
			@retry="fetchData"
		>
			<template #filters>
				<div class="business-control-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">Follow-up Status</span><select v-model="filters.follow_up_status" class="edge-input"><option>All</option><option>Open</option><option>Acknowledged</option><option>Snoozed</option></select></label>
					<label class="edge-field"><span class="edge-field-label">Assignment</span><select v-model="filters.assignment_scope" class="edge-input"><option value="all">All Actions</option><option value="mine">My Actions</option></select></label>
					<label class="edge-field"><span class="edge-field-label">Follow-up Timing</span><select v-model="filters.due_scope" class="edge-input"><option value="all">All Timing</option><option value="due">Due / Overdue</option></select></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<div v-if="earlyWarning.available === false" class="business-control-notice">
				<strong>Financial intelligence is unavailable for this scope.</strong>
				<span>{{ earlyWarning.metadata?.reason || "Your operational Action Centre controls remain available." }}</span>
			</div>

			<EdgeDashboardGrid minColumnWidth="23rem">
				<EdgeDashboardSection title="Critical Controls" description="Highest-priority operational or financial conditions requiring management attention.">
					<div v-if="critical.length" class="control-list">
						<BusinessControlRow v-for="item in critical" :key="itemKey(item)" :item="item" :busy="isMutating(item)" @open="openWorkflow" @follow-up="handleFollowUp" />
					</div>
					<div v-else class="control-empty">No critical controls match the current scope and follow-up filters.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Needs Attention" description="Warnings, early signals and operational exceptions that should be reviewed before they become critical.">
					<div v-if="warnings.length" class="control-list">
						<BusinessControlRow v-for="item in warnings" :key="itemKey(item)" :item="item" :busy="isMutating(item)" @open="openWorkflow" @follow-up="handleFollowUp" />
					</div>
					<div v-else class="control-empty">No warning controls match the current scope and follow-up filters.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Financial Signals" description="Net-new R9 liquidity, profitability, budget and spend-governance signals. Receivables and payables remain owned by their existing Action Centre controls.">
					<div v-if="financialSignals.length" class="control-list">
						<div v-for="item in financialSignals" :key="itemKey(item)" class="signal-row">
							<span><strong>{{ item.label }}</strong><small>{{ item.family || sourceLabel(item.source) }}</small></span>
							<strong>{{ formatValue(item.value, item.datatype) }}</strong>
						</div>
					</div>
					<div v-else class="control-empty">No separate R9 financial signals are visible for the current scope.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-if="unavailableSources.length" title="Unavailable Operational Sources" description="These existing Action Centre sources were excluded by permission or scope rules.">
					<div class="source-list">
						<div v-for="source in unavailableSources" :key="source.key" class="source-row"><strong>{{ sourceLabel(source.key) }}</strong><small>{{ source.reason }}</small></div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Control rules" description="Management follow-up never changes the accounting or operational truth." span="2">
					<div class="control-note">
						<strong>Follow-up is tracking, not resolution.</strong>
						<span>Acknowledge, assignment, follow-up date and snooze update only the separate RetailEdge Action Follow Up record. Resolve the underlying condition in its owning RetailEdge workflow or authoritative ERPNext record/report. Native ERPNext/Frappe drill-through opens in a new tab.</span>
					</div>
				</EdgeDashboardSection>
			</EdgeDashboardGrid>
		</EdgeDashboardShell>
	</EdgeAppShell>
</template>

<script>
import BusinessControlRow from "./BusinessControlRow.vue";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "RetailEdgeBusinessControlCenter",
	components: { ...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])), BusinessControlRow },
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			mutatingFingerprint: "",
			summaryRaw: {},
			items: [],
			actionCenter: { sources: {}, metadata: {} },
			earlyWarning: { available: true, metadata: {} },
			menuItems: [],
			tenantName: "",
			userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "", follow_up_status: "All", assignment_scope: "all", due_scope: "all" },
		};
	},
	computed: {
		summaryCards() {
			return [
				{ label: "Critical", value: this.summaryRaw.critical || 0, datatype: "Int" },
				{ label: "Needs Attention", value: this.summaryRaw.warning || 0, datatype: "Int" },
				{ label: "Open Controls", value: this.summaryRaw.total || 0, datatype: "Int" },
			];
		},
		critical() { return this.items.filter((item) => item.severity === "danger"); },
		warnings() { return this.items.filter((item) => item.severity === "warning"); },
		financialSignals() { return this.items.filter((item) => item.source === "r9_early_warning"); },
		unavailableSources() { return Object.values(this.actionCenter.sources || {}).filter((source) => !source.available); },
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
				const [context, navigation] = await Promise.all([callMethod("retailedge.action_center.get_action_center_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Business Control Centre controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.business_control_center.get_business_control_center", { filters: this.filters });
				this.filters = { ...this.filters, ...(result.filters || {}) };
				this.summaryRaw = result.summary || {};
				this.items = result.items || [];
				this.actionCenter = result.action_center || { sources: {}, metadata: {} };
				this.earlyWarning = result.early_warning || { available: true, metadata: {} };
			} catch (error) { this.error = errorMessage(error, "Business Control Centre failed to load."); }
			finally { this.loading = false; }
		},
		async updateFollowUp(item, action, values = {}) {
			if (!item?.fingerprint || item.follow_up_supported === false || this.mutatingFingerprint) return;
			this.mutatingFingerprint = item.fingerprint;
			try {
				await callMethod("retailedge.action_follow_up.update_action_follow_up", { fingerprint: item.fingerprint, action, filters: this.filters, ...values });
				await this.fetchData();
			} catch (error) {
				frappe.msgprint({ title: "Follow-up was not updated", message: errorMessage(error, "RetailEdge could not update this follow-up record."), indicator: "red" });
			} finally { this.mutatingFingerprint = ""; }
		},
		handleFollowUp(item, action) {
			if (action === "acknowledge" || action === "reopen") return this.updateFollowUp(item, action);
			const state = item.follow_up || {};
			if (action === "assign") return frappe.prompt([
				{
					fieldname: "assigned_to",
					fieldtype: "Link",
					options: "User",
					label: "Assigned To",
					reqd: 1,
					default: state.assigned_to || frappe.session.user,
					get_query: () => ({
						query: "retailedge.action_follow_up_query.get_assignable_users",
						filters: {
							company: this.filters.company || "",
							branch: this.filters.branch || "",
							require_global_scope: item.source === "r9_early_warning" && !this.filters.branch ? 1 : 0,
						},
					}),
				},
				{ fieldname: "follow_up_on", fieldtype: "Datetime", label: "Follow Up On", default: state.follow_up_on || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: state.notes || "" },
			], (values) => this.updateFollowUp(item, "assign", values), "Assign follow-up", "Assign");
			if (action === "schedule") return frappe.prompt([
				{ fieldname: "follow_up_on", fieldtype: "Datetime", label: "Follow Up On", reqd: 1, default: state.follow_up_on || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: state.notes || "" },
			], (values) => this.updateFollowUp(item, "schedule", values), "Schedule follow-up", "Save");
			if (action === "snooze") return frappe.prompt([
				{ fieldname: "snoozed_until", fieldtype: "Datetime", label: "Snoozed Until", reqd: 1, default: state.snoozed_until || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: state.notes || "" },
			], (values) => this.updateFollowUp(item, "snooze", values), "Snooze action", "Snooze");
		},
		isMutating(item) { return this.mutatingFingerprint === item.fingerprint; },
		openWorkflow(item) {
			const route = item?.route;
			if (!route) return;
			if (item.open_mode === "new_tab") {
				window.open(route, "_blank", "noopener,noreferrer");
				return;
			}
			window.location.assign(route);
		},
		itemKey(item) { return item.fingerprint || `${item.source}:${item.semantic_key || item.kind}:${item.route}`; },
		sourceLabel(source) { return String(source || "management").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); },
		formatValue(value, datatype) { try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value ?? "—"; } },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
	},
};
</script>

<style scoped>
.business-control-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.business-control-notice { display: grid; gap: 4px; margin-bottom: 14px; padding: 12px 14px; border: 1px solid var(--orange-300, var(--edge-border)); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); }
.business-control-notice span, .control-empty, .source-row small, .control-note span, .signal-row small { color: var(--edge-text-muted); font-size: 12px; }
.control-list, .source-list { display: grid; gap: 9px; }
.source-row, .control-note, .signal-row { display: grid; gap: 10px; width: 100%; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); }
.signal-row { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.signal-row span, .source-row, .control-note { display: grid; gap: 4px; }
@media (max-width: 900px) { .business-control-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .business-control-filters { grid-template-columns: 1fr; } .signal-row { align-items: flex-start; } }
</style>