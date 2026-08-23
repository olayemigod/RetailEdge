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
			subtitle="Prioritised issues from existing RetailEdge and ERPNext controls, with separate follow-up tracking. Resolve each underlying issue in its owning workflow or report."
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
					<label class="edge-field"><span class="edge-field-label">Follow-up Status</span><select v-model="filters.follow_up_status" class="edge-input"><option>All</option><option>Open</option><option>Acknowledged</option><option>Snoozed</option></select></label>
					<label class="edge-field"><span class="edge-field-label">Assignment</span><select v-model="filters.assignment_scope" class="edge-input"><option value="all">All Actions</option><option value="mine">My Actions</option></select></label>
					<label class="edge-field"><span class="edge-field-label">Follow-up Timing</span><select v-model="filters.due_scope" class="edge-input"><option value="all">All Timing</option><option value="due">Due / Overdue</option></select></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="23rem">
				<EdgeDashboardSection title="Critical" description="Issues that can affect cash control, stock integrity, posting, or materially overdue balances.">
					<div v-if="critical.length" class="action-list">
						<div v-for="item in critical" :key="itemKey(item)" class="action-row action-row--danger">
							<div class="action-row-main">
								<span class="action-copy"><strong>{{ item.label }}</strong><small>{{ sourceLabel(item.source) }} · {{ basisLabel(item.time_basis) }}</small></span>
								<strong>{{ formatValue(item.value, item.datatype) }}</strong>
							</div>
							<div v-if="item.priority_reason" class="priority-reason">Why this is prioritised: {{ item.priority_reason }}</div>
							<div class="follow-up-summary">
								<span class="follow-up-status">{{ followUpStatus(item) }}</span>
								<span v-if="followUp(item).is_due" class="follow-up-due">Due / overdue</span>
								<span v-if="followUp(item).snooze_expired">Snooze expired</span>
								<span v-if="followUp(item).assigned_to">Assigned: {{ followUp(item).assigned_to }}</span>
								<span v-if="followUp(item).follow_up_on">Follow up: {{ formatDateTime(followUp(item).follow_up_on) }}</span>
								<span v-if="followUpStatus(item) === 'Snoozed' && followUp(item).snoozed_until">Snoozed until: {{ formatDateTime(followUp(item).snoozed_until) }}</span>
							</div>
							<div class="action-controls">
								<button class="edge-button edge-button--primary" type="button" :title="workflowTitle(item)" @click="openWorkflow(item)">Open workflow</button>
								<button v-if="followUpStatus(item) !== 'Acknowledged'" class="edge-button" type="button" :disabled="isMutating(item)" @click="acknowledge(item)">Acknowledge</button>
								<button class="edge-button" type="button" :disabled="isMutating(item)" @click="promptAssignment(item)">Assign</button>
								<button class="edge-button" type="button" :disabled="isMutating(item)" @click="promptSchedule(item)">Follow-up</button>
								<button v-if="followUpStatus(item) !== 'Snoozed'" class="edge-button" type="button" :disabled="isMutating(item)" @click="promptSnooze(item)">Snooze</button>
								<button v-if="followUpStatus(item) !== 'Open'" class="edge-button" type="button" :disabled="isMutating(item)" @click="reopen(item)">Reopen</button>
							</div>
						</div>
					</div>
					<div v-else class="action-empty">No critical exceptions match the current Action Centre filters.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Needs Attention" description="Items requiring review, follow-up, or management attention.">
					<div v-if="warnings.length" class="action-list">
						<div v-for="item in warnings" :key="itemKey(item)" class="action-row action-row--warning">
							<div class="action-row-main">
								<span class="action-copy"><strong>{{ item.label }}</strong><small>{{ sourceLabel(item.source) }} · {{ basisLabel(item.time_basis) }}</small></span>
								<strong>{{ formatValue(item.value, item.datatype) }}</strong>
							</div>
							<div v-if="item.priority_reason" class="priority-reason">Why this is prioritised: {{ item.priority_reason }}</div>
							<div class="follow-up-summary">
								<span class="follow-up-status">{{ followUpStatus(item) }}</span>
								<span v-if="followUp(item).is_due" class="follow-up-due">Due / overdue</span>
								<span v-if="followUp(item).snooze_expired">Snooze expired</span>
								<span v-if="followUp(item).assigned_to">Assigned: {{ followUp(item).assigned_to }}</span>
								<span v-if="followUp(item).follow_up_on">Follow up: {{ formatDateTime(followUp(item).follow_up_on) }}</span>
								<span v-if="followUpStatus(item) === 'Snoozed' && followUp(item).snoozed_until">Snoozed until: {{ formatDateTime(followUp(item).snoozed_until) }}</span>
							</div>
							<div class="action-controls">
								<button class="edge-button edge-button--primary" type="button" :title="workflowTitle(item)" @click="openWorkflow(item)">Open workflow</button>
								<button v-if="followUpStatus(item) !== 'Acknowledged'" class="edge-button" type="button" :disabled="isMutating(item)" @click="acknowledge(item)">Acknowledge</button>
								<button class="edge-button" type="button" :disabled="isMutating(item)" @click="promptAssignment(item)">Assign</button>
								<button class="edge-button" type="button" :disabled="isMutating(item)" @click="promptSchedule(item)">Follow-up</button>
								<button v-if="followUpStatus(item) !== 'Snoozed'" class="edge-button" type="button" :disabled="isMutating(item)" @click="promptSnooze(item)">Snooze</button>
								<button v-if="followUpStatus(item) !== 'Open'" class="edge-button" type="button" :disabled="isMutating(item)" @click="reopen(item)">Reopen</button>
							</div>
						</div>
					</div>
					<div v-else class="action-empty">No attention items match the current Action Centre filters.</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-if="unavailableSources.length" title="Unavailable Sources" description="These sources were excluded because your current permissions do not allow them.">
					<div class="source-list">
						<div v-for="source in unavailableSources" :key="source.key" class="source-row"><strong>{{ sourceLabel(source.key) }}</strong><small>{{ source.reason }}</small></div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="How resolution works" description="Follow-up tracking is separate from business resolution." span="2">
					<div class="action-note">
						<strong>RetailEdge does not resolve accounting, stock or workflow exceptions from Action Centre.</strong>
						<span>Acknowledge, assignment, follow-up date and snooze only update the separate Action Follow Up record. Open workflow keeps RetailEdge pages in this tab and opens retained native ERPNext/Frappe records or reports in a new tab, where existing permissions, approvals, submissions and accounting controls remain authoritative.</span>
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
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "", mutatingFingerprint: "",
			summary: [], items: [], sources: {}, metadata: {}, menuItems: [], tenantName: "", userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "", follow_up_status: "All", assignment_scope: "all", due_scope: "all" },
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
		async updateFollowUp(item, action, values = {}) {
			if (!item?.fingerprint || this.mutatingFingerprint) return;
			this.mutatingFingerprint = item.fingerprint;
			try {
				await callMethod("retailedge.action_follow_up.update_action_follow_up", { fingerprint: item.fingerprint, action, filters: this.filters, ...values });
				await this.fetchData();
			} catch (error) {
				frappe.msgprint({ title: "Follow-up was not updated", message: errorMessage(error, "RetailEdge could not update this follow-up record."), indicator: "red" });
			} finally { this.mutatingFingerprint = ""; }
		},
		acknowledge(item) { return this.updateFollowUp(item, "acknowledge"); },
		reopen(item) { return this.updateFollowUp(item, "reopen"); },
		promptAssignment(item) {
			const current = this.followUp(item);
			frappe.prompt([
				{ fieldname: "assigned_to", fieldtype: "Link", options: "User", label: "Assigned To", reqd: 1, default: current.assigned_to || frappe.session.user, get_query: () => ({ filters: { enabled: 1 } }) },
				{ fieldname: "follow_up_on", fieldtype: "Datetime", label: "Follow Up On", default: current.follow_up_on || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: current.notes || "" },
			], (values) => this.updateFollowUp(item, "assign", values), "Assign follow-up", "Assign");
		},
		promptSchedule(item) {
			const current = this.followUp(item);
			frappe.prompt([
				{ fieldname: "follow_up_on", fieldtype: "Datetime", label: "Follow Up On", reqd: 1, default: current.follow_up_on || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: current.notes || "" },
			], (values) => this.updateFollowUp(item, "schedule", values), "Schedule follow-up", "Save");
		},
		promptSnooze(item) {
			const current = this.followUp(item);
			frappe.prompt([
				{ fieldname: "snoozed_until", fieldtype: "Datetime", label: "Snoozed Until", reqd: 1, default: current.snoozed_until || "" },
				{ fieldname: "notes", fieldtype: "Small Text", label: "Follow-up Notes", default: current.notes || "" },
			], (values) => this.updateFollowUp(item, "snooze", values), "Snooze action", "Snooze");
		},
		followUp(item) { return item.follow_up || { status: "Open", effective_status: "Open" }; },
		followUpStatus(item) { const state = this.followUp(item); return state.effective_status || state.status || "Open"; },
		isMutating(item) { return this.mutatingFingerprint === item.fingerprint; },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openWorkflow(item) {
			const route = item?.route;
			if (!route) return;
			if (item.open_mode === "new_tab") {
				window.open(route, "_blank", "noopener,noreferrer");
				return;
			}
			window.location.assign(route);
		},
		workflowTitle(item) { return item?.open_mode === "new_tab" ? "Open authoritative workflow in a new tab" : "Open RetailEdge workflow"; },
		itemKey(item) { return item.fingerprint || `${item.source}:${item.semantic_key || item.kind}:${item.route}`; },
		sourceLabel(source) { return String(source || "management").replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase()); },
		basisLabel(value) { return value === "current" ? "Current position" : "Selected period"; },
		formatDateTime(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(value); } catch (_error) { return value; } },
		formatValue(value, datatype) {
			if (value === null || value === undefined || value === "") return "—";
			const fieldtype = String(datatype || "Data");
			try {
				if (fieldtype === "Int") return String(Math.trunc(Number(value)));
				if (fieldtype === "Float") return String(Number(value));
				if (fieldtype === "Currency") return format_currency(Number(value));
				if (fieldtype === "Percent") return `${Number(value)}%`;
				return String(value);
			} catch (_error) {
				return String(value);
			}
		},
	},
};
</script>

<style scoped>
.action-center-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.action-list, .source-list { display: grid; gap: 9px; }
.action-row { display: grid; gap: 10px; width: 100%; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); }
.action-row--danger { border-color: var(--red-300, var(--edge-border)); }
.action-row--warning { border-color: var(--orange-300, var(--edge-border)); }
.action-row-main { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
.action-copy, .source-row, .action-note { display: grid; gap: 4px; }
.action-copy small, .source-row small, .action-note span, .action-empty, .follow-up-summary, .priority-reason { color: var(--edge-text-muted); font-size: 12px; }
.priority-reason { line-height: 1.45; }
.follow-up-summary { display: flex; flex-wrap: wrap; gap: 6px 12px; align-items: center; }
.follow-up-status, .follow-up-due { padding: 2px 7px; border: 1px solid var(--edge-border); border-radius: 999px; background: var(--edge-surface-soft, var(--edge-surface)); color: var(--edge-text); font-weight: 600; }
.follow-up-due { border-color: var(--orange-300, var(--edge-border)); }
.action-controls { display: flex; flex-wrap: wrap; gap: 7px; }
.source-row, .action-note { padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
@media (max-width: 900px) { .action-center-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .action-center-filters { grid-template-columns: 1fr; } .action-row-main { align-items: flex-start; } .action-controls .edge-button { flex: 1 1 auto; } }
</style>
