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
						<span class="assignment-kicker">Current records</span>
						<h3>{{ assignments.length }} assignment{{ assignments.length === 1 ? "" : "s" }}</h3>
						<p>Ended assignments stay visible so staff movement between Branches remains auditable.</p>
					</div>
					<button v-if="canCreate" type="button" class="edge-button edge-button--primary" @click="openAssignDialog">
						Assign User
					</button>
				</section>

				<section class="edge-panel assignment-filters">
					<div class="filter-grid">
						<label class="edge-field">
							<span class="edge-field-label">User</span>
							<input v-model.trim="filters.user" class="edge-input" placeholder="user@example.com" @keyup.enter="loadAssignments" />
						</label>
						<label class="edge-field">
							<span class="edge-field-label">Company</span>
							<input v-model.trim="filters.company" class="edge-input" placeholder="Company" @keyup.enter="loadAssignments" />
						</label>
						<label class="edge-field">
							<span class="edge-field-label">Branch</span>
							<input v-model.trim="filters.branch" class="edge-input" placeholder="Branch" @keyup.enter="loadAssignments" />
						</label>
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
									<td><button type="button" class="link-button" @click="openRecord(row)">{{ row.user }}</button></td>
									<td>{{ row.company }}</td>
									<td>{{ row.branch }}</td>
									<td>{{ row.branch_role }}</td>
									<td>{{ formatDate(row.effective_from) }}</td>
									<td>{{ row.effective_to ? formatDate(row.effective_to) : "Current" }}</td>
									<td><EdgeStatusBadge :status="statusBadge(row.status)" /> <span class="status-text">{{ row.status }}</span></td>
									<td>
										<button v-if="canWrite && row.status === 'Active'" type="button" class="edge-button edge-button--secondary edge-button--small" @click="openTransferDialog(row)">Transfer</button>
									</td>
								</tr>
								<tr v-if="!sortedAssignments.length">
									<td colspan="8" class="empty-cell">No Branch Assignments match the current filters.</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeStatusBadge"];
const CONTEXT_METHOD = "retailedge.branch_assignment.get_branch_assignment_context";
const CREATE_METHOD = "retailedge.branch_assignment.create_branch_assignment";
const TRANSFER_METHOD = "retailedge.branch_assignment.transfer_branch_assignment";
const BRANCH_QUERY = "retailedge.branch_profile_queries.search_configured_company_branches";
const ROLE_OPTIONS = "Cashier\nManager\nAuditor\nSales\nStock\nAccounts\nPurchasing\nOther";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}, options = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			freeze: Boolean(options.freeze),
			freeze_message: options.freezeMessage || undefined,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

export default {
	name: "RetailEdgeBranchAssignments",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			assignments: [],
			canCreate: false,
			canWrite: false,
			filters: { user: "", company: "", branch: "", status: "" },
			sortKey: "effective_from",
			sortDirection: "desc",
			userName: "",
			menuItems: [],
			columns: [
				{ key: "user", label: "User" },
				{ key: "company", label: "Company" },
				{ key: "branch", label: "Branch" },
				{ key: "branch_role", label: "Role" },
				{ key: "effective_from", label: "From" },
				{ key: "effective_to", label: "To" },
				{ key: "status", label: "Status" },
			],
		};
	},
	computed: {
		sortedAssignments() {
			const rows = [...this.assignments];
			const direction = this.sortDirection === "asc" ? 1 : -1;
			return rows.sort((a, b) => {
				const left = String(a?.[this.sortKey] || "").toLowerCase();
				const right = String(b?.[this.sortKey] || "").toLowerCase();
				return left.localeCompare(right) * direction;
			});
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadAssignments();
	},
	mounted() {
		window.addEventListener("retailedge-branch-assignments-page-show", this._onPageShow);
		if (this.edgeUIValid) {
			this.loadNavigation();
			this.loadAssignments();
		}
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-branch-assignments-page-show", this._onPageShow);
	},
	methods: {
		async loadNavigation() {
			try {
				const navigation = typeof window.retailedgeGetBusinessHubContext === "function"
					? await window.retailedgeGetBusinessHubContext()
					: await callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				this.menuItems = (navigation.navigation_groups || []).map((group) => ({
					...group,
					items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
				}));
				this.userName = navigation.context?.user_name || "";
			} catch (error) {
				this.menuItems = [];
			}
		},
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
		},
		async loadAssignments() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const data = await callMethod(CONTEXT_METHOD, { filters: this.filters });
				this.assignments = Array.isArray(data.assignments) ? data.assignments : [];
				this.canCreate = Boolean(data.can_create);
				this.canWrite = Boolean(data.can_write);
				this.userName = this.userName || data.user_name || "";
				this.loaded = true;
			} catch (error) {
				this.error = error?.message || error?.exc || __("Branch Assignment history could not be loaded.");
			} finally {
				this.loading = false;
			}
		},
		clearFilters() {
			this.filters = { user: "", company: "", branch: "", status: "" };
			this.loadAssignments();
		},
		setSort(key) {
			if (this.sortKey === key) this.sortDirection = this.sortDirection === "asc" ? "desc" : "asc";
			else {
				this.sortKey = key;
				this.sortDirection = "asc";
			}
		},
		statusBadge(status) {
			if (status === "Active") return "Active";
			if (status === "Planned") return "Warning";
			return "Inactive";
		},
		formatDate(value) {
			return value ? frappe.datetime.str_to_user(value) : "";
		},
		openRecord(row) {
			frappe.set_route("Form", "RetailEdge Branch Assignment", row.name);
		},
		openAssignDialog() {
			let dialog;
			dialog = new frappe.ui.Dialog({
				title: __("Assign User to Branch"),
				fields: [
					{ fieldname: "user", fieldtype: "Link", label: __("User"), options: "User", reqd: 1 },
					{ fieldname: "company", fieldtype: "Link", label: __("Company"), options: "Company", reqd: 1 },
					{ fieldname: "branch", fieldtype: "Link", label: __("Branch"), options: "Branch", reqd: 1, get_query: () => ({ query: BRANCH_QUERY, filters: { company: dialog.get_value("company") || "" } }) },
					{ fieldname: "branch_role", fieldtype: "Select", label: __("Branch Role"), options: ROLE_OPTIONS, default: "Other", reqd: 1 },
					{ fieldname: "effective_from", fieldtype: "Date", label: __("Effective From"), default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldname: "effective_to", fieldtype: "Date", label: __("Effective To") },
					{ fieldname: "is_primary", fieldtype: "Check", label: __("Primary Branch"), default: 0 },
					{ fieldname: "transfer_reason", fieldtype: "Small Text", label: __("Assignment Reason") },
					{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
				],
				primary_action_label: __("Assign User"),
				primary_action: async (values) => {
					await callMethod(CREATE_METHOD, values, { freeze: true, freezeMessage: __("Creating Branch Assignment...") });
					dialog.hide();
					frappe.show_alert({ message: __("Branch Assignment created."), indicator: "green" });
					await this.loadAssignments();
				},
			});
			dialog.fields_dict.company.df.onchange = () => dialog.set_value("branch", null);
			dialog.show();
		},
		openTransferDialog(row) {
			let dialog;
			dialog = new frappe.ui.Dialog({
				title: __("Transfer User to Branch"),
				fields: [
					{ fieldname: "new_company", fieldtype: "Link", label: __("New Company"), options: "Company", reqd: 1, default: row.company },
					{ fieldname: "new_branch", fieldtype: "Link", label: __("New Branch"), options: "Branch", reqd: 1, get_query: () => ({ query: BRANCH_QUERY, filters: { company: dialog.get_value("new_company") || "" } }) },
					{ fieldname: "effective_date", fieldtype: "Date", label: __("Transfer Date"), default: frappe.datetime.get_today(), reqd: 1 },
					{ fieldname: "branch_role", fieldtype: "Select", label: __("Branch Role"), options: ROLE_OPTIONS, default: row.branch_role || "Other" },
					{ fieldname: "reason", fieldtype: "Small Text", label: __("Transfer Reason"), reqd: 1 },
					{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
				],
				primary_action_label: __("Transfer"),
				primary_action: async (values) => {
					await callMethod(TRANSFER_METHOD, { name: row.name, ...values }, { freeze: true, freezeMessage: __("Recording Branch transfer...") });
					dialog.hide();
					frappe.show_alert({ message: __("Branch transfer recorded."), indicator: "green" });
					await this.loadAssignments();
				},
			});
			dialog.fields_dict.new_company.df.onchange = () => dialog.set_value("new_branch", null);
			dialog.show();
		},
	},
};
</script>

<style scoped>
.assignment-layout { display: grid; gap: 1rem; }
.assignment-summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.assignment-summary h3 { margin: .25rem 0; }
.assignment-summary p { margin: 0; }
.assignment-kicker { font-size: .75rem; text-transform: uppercase; letter-spacing: .08em; opacity: .7; }
.filter-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; }
.filter-actions { display: flex; gap: .5rem; margin-top: .75rem; }
.assignment-table-wrap { overflow-x: auto; }
.assignment-table { width: 100%; border-collapse: collapse; }
.assignment-table th, .assignment-table td { padding: .75rem; border-bottom: 1px solid var(--border-color, #dfe3e8); text-align: left; vertical-align: middle; white-space: nowrap; }
.sort-button, .link-button { background: none; border: 0; padding: 0; font: inherit; color: inherit; cursor: pointer; }
.sort-button { font-weight: 600; }
.link-button { text-decoration: underline; text-underline-offset: 2px; }
.status-text { margin-left: .35rem; }
.empty-cell { text-align: center !important; padding: 2rem !important; opacity: .7; }
.edge-button--small { padding: .3rem .6rem; min-height: auto; }
@media (max-width: 900px) { .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .assignment-summary { align-items: flex-start; flex-direction: column; } .filter-grid { grid-template-columns: 1fr; } }
</style>
