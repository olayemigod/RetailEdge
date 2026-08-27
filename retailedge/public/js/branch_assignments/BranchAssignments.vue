<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Branch Assignments could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Branch Assignments"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/branch-assignments"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-branch-assignments-page">
			<EdgePageHeader
				title="Branch Assignments"
				description="Assign users to operational Branches with effective dates and preserve a clear transfer history."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadAssignments()" />

			<div v-else class="assignment-layout">
				<section class="edge-panel assignment-summary">
					<div>
						<span class="assignment-kicker">User posting history</span>
						<h3>{{ assignments.length }} assignment{{ assignments.length === 1 ? "" : "s" }}</h3>
						<p>Ended assignments stay visible. Transfers create a new effective-dated record instead of rewriting where the user worked before.</p>
					</div>
					<div class="summary-actions">
						<button type="button" class="edge-button edge-button--secondary" @click="openBranchSetup">Branch Setup</button>
						<button v-if="canCreate" type="button" class="edge-button edge-button--primary" @click="openAssign">Assign User</button>
					</div>
				</section>

				<section class="edge-panel assignment-filters">
					<div class="filter-grid">
						<EdgeLinkField :modelValue="filters.user" label="User" placeholder="All users" :searcher="searchFilterUser" @update:modelValue="filters.user = $event || ''" />
						<EdgeLinkField :modelValue="filters.company" label="Company" placeholder="All Companies" :searcher="searchFilterCompany" @update:modelValue="setFilterCompany" />
						<EdgeLinkField :modelValue="filters.branch" label="Branch" placeholder="All Branches" :searcher="searchFilterBranch" @update:modelValue="filters.branch = $event || ''" />
						<label class="edge-field">
							<span class="edge-field-label">Status</span>
							<select v-model="filters.status" class="edge-input">
								<option value="">All statuses</option>
								<option value="Active">Active</option>
								<option value="Planned">Planned</option>
								<option value="Ended">Ended</option>
							</select>
						</label>
					</div>
					<div class="filter-actions">
						<button type="button" class="edge-button edge-button--primary" :disabled="loading" @click="loadAssignments">Apply Filters</button>
						<button type="button" class="edge-button edge-button--secondary" :disabled="loading" @click="clearFilters">Clear</button>
					</div>
				</section>

				<section class="edge-panel assignment-table-panel">
					<div class="assignment-table-wrap">
						<table class="assignment-table">
							<thead>
								<tr>
									<th v-for="column in columns" :key="column.key">
										<button type="button" class="sort-button" @click="setSort(column.key)">
											{{ column.label }} <span v-if="sortKey === column.key">{{ sortDirection === "asc" ? "↑" : "↓" }}</span>
										</button>
									</th>
									<th>Actions</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in sortedAssignments" :key="row.name">
									<td><strong>{{ row.user }}</strong></td>
									<td>{{ row.company }}</td>
									<td>{{ row.branch }}</td>
									<td>{{ row.branch_role }}</td>
									<td>{{ formatDate(row.effective_from) }}</td>
									<td>{{ row.effective_to ? formatDate(row.effective_to) : "Current" }}</td>
									<td><EdgeStatusBadge :status="statusBadge(row.status)" /> <span class="status-text">{{ row.status }}</span></td>
									<td class="row-actions">
										<button v-if="canWrite && row.status === 'Active'" type="button" class="edge-button edge-button--secondary edge-button--small" @click="openTransfer(row)">Transfer</button>
										<button type="button" class="edge-button edge-button--secondary edge-button--small" @click="openNative(row)">Full Form</button>
									</td>
								</tr>
								<tr v-if="!sortedAssignments.length"><td colspan="8" class="empty-cell">No Branch Assignments match the current filters.</td></tr>
							</tbody>
						</table>
					</div>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>

	<EdgeModal :open="assignOpen" title="Assign User to Branch" subtitle="Create an effective-dated posting record. Company → Branch choices come from enabled Branch Setup mappings." size="lg" @close="closeAssign">
		<div v-if="assignError" class="form-error">{{ assignError }}</div>
		<div class="form-grid">
			<EdgeLinkField :modelValue="assign.user" label="User" placeholder="Choose system user" :required="true" :searcher="searchAssignUser" @update:modelValue="assign.user = $event || ''" />
			<EdgeLinkField :modelValue="assign.company" label="Company" placeholder="Choose Company" :required="true" :searcher="searchAssignCompany" @update:modelValue="setAssignCompany" />
			<EdgeLinkField :modelValue="assign.branch" label="Branch" placeholder="Choose configured Branch" :required="true" :searcher="searchAssignBranch" @update:modelValue="assign.branch = $event || ''" />
			<label class="edge-field"><span class="edge-field-label">Branch Role *</span><select v-model="assign.branch_role" class="edge-input"><option v-for="role in roles" :key="role" :value="role">{{ role }}</option></select></label>
			<label class="edge-field"><span class="edge-field-label">Effective From *</span><input v-model="assign.effective_from" class="edge-input" type="date" /></label>
			<label class="edge-field"><span class="edge-field-label">Effective To</span><input v-model="assign.effective_to" class="edge-input" type="date" /></label>
			<label class="check-field"><input v-model="assign.is_primary" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Primary Branch</strong><small>A user can have only one overlapping primary Branch per Company.</small></span></label>
			<label class="edge-field edge-field--wide"><span class="edge-field-label">Assignment Reason</span><textarea v-model="assign.transfer_reason" class="edge-input" rows="2"></textarea></label>
			<label class="edge-field edge-field--wide"><span class="edge-field-label">Notes</span><textarea v-model="assign.notes" class="edge-input" rows="3"></textarea></label>
		</div>
		<template #footer>
			<div class="modal-footer-actions"><span></span><div class="footer-right"><button type="button" class="edge-button" :disabled="saving" @click="closeAssign">Cancel</button><button type="button" class="edge-button edge-button--primary" :disabled="saving" @click="saveAssignment">{{ saving ? "Assigning…" : "Assign User" }}</button></div></div>
		</template>
	</EdgeModal>

	<EdgeModal :open="transferOpen" title="Transfer User to Branch" subtitle="The current assignment will end the day before the new assignment starts. The old record remains in history." size="lg" @close="closeTransfer">
		<div v-if="transferError" class="form-error">{{ transferError }}</div>
		<div class="transfer-current"><div><span>User</span><strong>{{ transferRow.user }}</strong></div><div><span>Current Branch</span><strong>{{ transferRow.company }} · {{ transferRow.branch }}</strong></div></div>
		<div class="form-grid">
			<EdgeLinkField :modelValue="transfer.company" label="New Company" placeholder="Choose Company" :required="true" :searcher="searchTransferCompany" @update:modelValue="setTransferCompany" />
			<EdgeLinkField :modelValue="transfer.branch" label="New Branch" placeholder="Choose configured Branch" :required="true" :searcher="searchTransferBranch" @update:modelValue="transfer.branch = $event || ''" />
			<label class="edge-field"><span class="edge-field-label">Transfer Date *</span><input v-model="transfer.effective_date" class="edge-input" type="date" /></label>
			<label class="edge-field"><span class="edge-field-label">Branch Role</span><select v-model="transfer.branch_role" class="edge-input"><option v-for="role in roles" :key="role" :value="role">{{ role }}</option></select></label>
			<label class="edge-field edge-field--wide"><span class="edge-field-label">Transfer Reason *</span><textarea v-model="transfer.reason" class="edge-input" rows="2"></textarea></label>
			<label class="edge-field edge-field--wide"><span class="edge-field-label">Notes</span><textarea v-model="transfer.notes" class="edge-input" rows="3"></textarea></label>
		</div>
		<template #footer>
			<div class="modal-footer-actions"><span></span><div class="footer-right"><button type="button" class="edge-button" :disabled="saving" @click="closeTransfer">Cancel</button><button type="button" class="edge-button edge-button--primary" :disabled="saving" @click="saveTransfer">{{ saving ? "Transferring…" : "Transfer" }}</button></div></div>
		</template>
	</EdgeModal>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeStatusBadge", "EdgeModal", "EdgeLinkField"];
const CONTEXT_METHOD = "retailedge.branch_assignment.get_branch_assignment_context";
const CREATE_METHOD = "retailedge.branch_assignment.create_branch_assignment";
const TRANSFER_METHOD = "retailedge.branch_assignment.transfer_branch_assignment";
const SEARCH_METHOD = "retailedge.branch_assignment_ui.search_branch_assignment_options";
const ROLES = ["Cashier", "Manager", "Auditor", "Sales", "Stock", "Accounts", "Purchasing", "Other"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}, options = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, freeze: Boolean(options.freeze), freeze_message: options.freezeMessage || undefined, callback: (response) => resolve(response.message || {}), error: reject }));
}
function extractServerMessage(error, fallback) {
	const response = error?.responseJSON || {};
	const rawMessages = response._server_messages;
	if (rawMessages) {
		try {
			const messages = JSON.parse(rawMessages);
			for (const item of messages) {
				let payload = item;
				if (typeof payload === "string") {
					try { payload = JSON.parse(payload); } catch (_) { payload = { message: payload }; }
				}
				const message = payload?.message || payload?.title || "";
				if (message) return String(message).replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim();
			}
		} catch (_) {
			// Frappe still renders its normal Message dialog; do not expose malformed server diagnostics.
		}
	}
	for (const candidate of [response.message, error?.message]) {
		const message = String(candidate || "").trim();
		if (message && !message.includes("Traceback") && !message.includes('File "apps/')) return message;
	}
	return fallback;
}
function blankAssign() { return { user: "", company: "", branch: "", branch_role: "Other", effective_from: frappe.datetime.get_today(), effective_to: "", is_primary: 0, transfer_reason: "", notes: "" }; }
function blankTransfer(row = {}) { return { company: row.company || "", branch: "", effective_date: frappe.datetime.get_today(), branch_role: row.branch_role || "Other", reason: "", notes: "" }; }

export default {
	name: "RetailEdgeBranchAssignments",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], loading: false, loaded: false, error: "", assignments: [], canCreate: false, canWrite: false,
		filters: { user: "", company: "", branch: "", status: "" }, sortKey: "effective_from", sortDirection: "desc", userName: "", menuItems: [],
		assignOpen: false, transferOpen: false, saving: false, assignError: "", transferError: "", assign: blankAssign(), transfer: blankTransfer(), transferRow: {}, roles: ROLES,
		columns: [{ key: "user", label: "User" }, { key: "company", label: "Company" }, { key: "branch", label: "Branch" }, { key: "branch_role", label: "Role" }, { key: "effective_from", label: "From" }, { key: "effective_to", label: "To" }, { key: "status", label: "Status" }],
		};
	},
	computed: {
		sortedAssignments() { const direction = this.sortDirection === "asc" ? 1 : -1; return [...this.assignments].sort((a, b) => String(a?.[this.sortKey] || "").localeCompare(String(b?.[this.sortKey] || "")) * direction); },
	},
	created() {
		const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; this._onPageShow = () => this.loadAssignments();
	},
	mounted() { window.addEventListener("retailedge-branch-assignments-page-show", this._onPageShow); if (this.edgeUIValid) { this.loadNavigation(); this.loadAssignments(); } },
	beforeUnmount() { window.removeEventListener("retailedge-branch-assignments-page-show", this._onPageShow); },
	methods: {
		async loadNavigation() {
			try {
				const navigation = typeof window.retailedgeGetBusinessHubContext === "function" ? await window.retailedgeGetBusinessHubContext() : await callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				this.menuItems = (navigation.navigation_groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); this.userName = navigation.context?.user_name || "";
			} catch (error) { this.menuItems = []; }
		},
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer"); },
		async loadAssignments() {
			if (this.loading) return; this.loading = true; this.error = "";
			try { const data = await callMethod(CONTEXT_METHOD, { filters: this.filters }); this.assignments = Array.isArray(data.assignments) ? data.assignments : []; this.canCreate = Boolean(data.can_create); this.canWrite = Boolean(data.can_write); this.userName = this.userName || data.user_name || ""; this.loaded = true; }
			catch (error) { this.error = extractServerMessage(error, __("Branch Assignment history could not be loaded.")); }
			finally { this.loading = false; }
		},
		clearFilters() { this.filters = { user: "", company: "", branch: "", status: "" }; this.loadAssignments(); },
		setFilterCompany(value) { this.filters.company = value || ""; this.filters.branch = ""; },
		setSort(key) { if (this.sortKey === key) this.sortDirection = this.sortDirection === "asc" ? "desc" : "asc"; else { this.sortKey = key; this.sortDirection = "asc"; } },
		statusBadge(status) { if (status === "Active") return "Active"; if (status === "Planned") return "Warning"; return "Inactive"; },
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : ""; },
		search(fieldname, query, values = {}) { return callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values }).then((rows) => Array.isArray(rows) ? rows : []); },
		searchFilterUser(query) { return this.search("user", query); }, searchFilterCompany(query) { return this.search("company", query); }, searchFilterBranch(query) { return this.search("filter_branch", query, { company: this.filters.company }); },
		searchAssignUser(query) { return this.search("user", query); }, searchAssignCompany(query) { return this.search("company", query); }, searchAssignBranch(query) { return this.search("branch", query, { company: this.assign.company }); },
		searchTransferCompany(query) { return this.search("company", query); }, searchTransferBranch(query) { return this.search("branch", query, { company: this.transfer.company }); },
		openAssign() { this.assign = blankAssign(); this.assignError = ""; this.assignOpen = true; }, closeAssign() { if (!this.saving) this.assignOpen = false; },
		setAssignCompany(value) { this.assign.company = value || ""; this.assign.branch = ""; },
		async saveAssignment() {
			if (!this.assign.user || !this.assign.company || !this.assign.branch || !this.assign.effective_from) { this.assignError = __("User, Company, Branch and Effective From are required."); return; }
			this.saving = true; this.assignError = "";
			try { await callMethod(CREATE_METHOD, this.assign, { freeze: true, freezeMessage: __("Creating Branch Assignment...") }); this.assignOpen = false; frappe.show_alert({ message: __("Branch Assignment created."), indicator: "green" }); await this.loadAssignments(); }
			catch (error) { this.assignError = extractServerMessage(error, __("Branch Assignment could not be created.")); }
			finally { this.saving = false; }
		},
		openTransfer(row) { this.transferRow = { ...row }; this.transfer = blankTransfer(row); this.transferError = ""; this.transferOpen = true; }, closeTransfer() { if (!this.saving) this.transferOpen = false; },
		setTransferCompany(value) { this.transfer.company = value || ""; this.transfer.branch = ""; },
		async saveTransfer() {
			if (!this.transfer.company || !this.transfer.branch || !this.transfer.effective_date || !this.transfer.reason) { this.transferError = __("New Company, Branch, Transfer Date and Transfer Reason are required."); return; }
			this.saving = true; this.transferError = "";
			try { await callMethod(TRANSFER_METHOD, { name: this.transferRow.name, new_company: this.transfer.company, new_branch: this.transfer.branch, effective_date: this.transfer.effective_date, branch_role: this.transfer.branch_role, reason: this.transfer.reason, notes: this.transfer.notes }, { freeze: true, freezeMessage: __("Recording Branch transfer...") }); this.transferOpen = false; frappe.show_alert({ message: __("Branch transfer recorded; previous assignment preserved."), indicator: "green" }); await this.loadAssignments(); }
			catch (error) { this.transferError = extractServerMessage(error, __("Branch transfer could not be recorded.")); }
			finally { this.saving = false; }
		},
		openNative(row) { if (row?.name) window.open(`/app/retailedge-branch-assignment/${encodeURIComponent(row.name)}`, "_blank", "noopener,noreferrer"); },
		openBranchSetup() { frappe.set_route("branch-setup"); },
	},
};
</script>

<style scoped>
.assignment-layout { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.assignment-summary { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.assignment-summary h3 { margin: 0.2rem 0 0.35rem; }
.assignment-summary p { margin: 0; color: var(--text-muted); }
.assignment-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.summary-actions, .filter-actions, .row-actions, .modal-footer-actions, .footer-right { display: flex; gap: 0.65rem; flex-wrap: wrap; }
.modal-footer-actions { width: 100%; justify-content: space-between; }
.filter-grid, .form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.filter-actions { margin-top: 1rem; }
.assignment-table-wrap { overflow-x: auto; }
.assignment-table { width: 100%; border-collapse: collapse; min-width: 980px; }
.assignment-table th, .assignment-table td { padding: 0.75rem; border-bottom: 1px solid var(--edge-border-color, var(--border-color)); text-align: left; vertical-align: middle; }
.sort-button { border: 0; background: transparent; color: inherit; font: inherit; font-weight: 600; padding: 0; cursor: pointer; }
.status-text { margin-left: 0.35rem; }
.empty-cell { text-align: center !important; color: var(--text-muted); padding: 2rem !important; }
.edge-field { display: grid; gap: 0.35rem; }
.edge-field--wide { grid-column: 1 / -1; }
.edge-input { width: 100%; padding: 0.65rem 0.75rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.45rem; background: var(--edge-surface, var(--control-bg)); color: var(--text-color); }
.check-field { display: flex; gap: 0.65rem; align-items: flex-start; padding: 0.7rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.55rem; }
.check-field span { display: grid; gap: 0.2rem; }.check-field small { color: var(--text-muted); }
.form-error { padding: 0.85rem; margin-bottom: 1rem; border: 1px solid var(--red-300, var(--edge-border-color, var(--border-color))); border-radius: 0.55rem; }
.transfer-current { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.75rem; margin-bottom: 1rem; }
.transfer-current div { display: grid; gap: 0.2rem; padding: 0.7rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.55rem; }.transfer-current span { color: var(--text-muted); font-size: 0.8rem; }
@media (max-width: 760px) { .assignment-summary { flex-direction: column; } .filter-grid, .form-grid, .transfer-current { grid-template-columns: 1fr; } .edge-field--wide { grid-column: auto; } }
</style>