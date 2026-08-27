<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Branch Setup could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Branch Setup"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/branch-setup"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-branch-setup-page">
			<EdgePageHeader
				title="Branch Setup"
				description="Map Branches to Companies and configure the stock, POS, accounting and control defaults used by RetailEdge."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadProfiles()" />

			<div v-else class="branch-setup-layout">
				<section class="edge-panel branch-setup-summary">
					<div>
						<span class="setup-kicker">Operating foundation</span>
						<h3>{{ profiles.length }} Branch Setup{{ profiles.length === 1 ? "" : "s" }}</h3>
						<p>Company → Branch ownership is explicit here. User movement and history are managed separately in Branch Assignments.</p>
					</div>
					<div class="summary-actions">
						<button type="button" class="edge-button edge-button--secondary" @click="openAssignments">Branch Assignments</button>
						<button v-if="canCreate" type="button" class="edge-button edge-button--primary" @click="openNew">Add Branch Setup</button>
					</div>
				</section>

				<section class="edge-panel branch-setup-filters">
					<div class="filter-grid">
						<EdgeLinkField
							:modelValue="filters.company"
							label="Company"
							placeholder="All Companies"
							:searcher="searchFilterCompany"
							@update:modelValue="setFilterCompany"
						/>
						<EdgeLinkField
							:modelValue="filters.branch"
							label="Branch"
							placeholder="All Branches"
							:searcher="searchFilterBranch"
							@update:modelValue="filters.branch = $event || ''"
						/>
						<label class="edge-field">
							<span class="edge-field-label">Status</span>
							<select v-model="filters.enabled" class="edge-input">
								<option value="">All</option>
								<option value="1">Enabled</option>
								<option value="0">Disabled / History</option>
							</select>
						</label>
					</div>
					<div class="filter-actions">
						<button type="button" class="edge-button edge-button--primary" :disabled="loading" @click="loadProfiles">Apply Filters</button>
						<button type="button" class="edge-button edge-button--secondary" :disabled="loading" @click="clearFilters">Clear</button>
					</div>
				</section>

				<section class="edge-panel branch-setup-table-panel">
					<div class="table-wrap">
						<table class="branch-setup-table">
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
								<tr v-for="row in sortedProfiles" :key="row.name">
									<td><button type="button" class="link-button" @click="openEdit(row)">{{ row.profile_name || row.name }}</button></td>
									<td>{{ row.company }}</td>
									<td>{{ row.branch }}</td>
									<td><EdgeStatusBadge :status="row.enabled ? 'Active' : 'Inactive'" /> <span class="status-text">{{ row.enabled ? "Enabled" : "Disabled" }}</span></td>
									<td>{{ row.is_default_for_company ? "Yes" : "" }}</td>
									<td>{{ row.default_pos_profile || "—" }}</td>
									<td>{{ row.default_warehouse || "—" }}</td>
									<td class="row-actions">
										<button type="button" class="edge-button edge-button--secondary edge-button--small" @click="openEdit(row)">{{ canWrite ? "Edit" : "View" }}</button>
										<button type="button" class="edge-button edge-button--secondary edge-button--small" @click="openNative(row.name)">Full Form</button>
									</td>
								</tr>
								<tr v-if="!sortedProfiles.length"><td colspan="8" class="empty-cell">No Branch Setup records match the current filters.</td></tr>
							</tbody>
						</table>
					</div>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>

	<EdgeModal :open="editorOpen" :title="editorTitle" subtitle="RetailEdge validates all Company, Branch, stock and accounting relationships on the server." size="xl" @close="closeEditor">
		<div v-if="editorError" class="form-error">{{ editorError }}</div>
		<div v-if="editorLoading" class="p-6 text-center text-muted">Loading Branch Setup…</div>
		<div v-else class="editor-body">
			<div class="editor-tabs" role="tablist" aria-label="Branch Setup sections">
				<button v-for="tab in tabs" :key="tab.key" type="button" class="edge-button" :class="{ 'edge-button--primary': activeTab === tab.key }" @click="activeTab = tab.key">{{ tab.label }}</button>
			</div>

			<section v-if="activeTab === 'identity'" class="form-section">
				<h4>Branch identity</h4>
				<div class="form-grid">
					<label class="edge-field"><span class="edge-field-label">Setup Name *</span><input v-model.trim="editor.profile_name" class="edge-input" :disabled="saving || Boolean(editor.name)" /></label>
					<label class="check-field"><input v-model="editor.enabled" type="checkbox" :true-value="1" :false-value="0" :disabled="saving" /><span><strong>Enabled</strong><small>Disabled mappings stay available as history but are not operational Branch options.</small></span></label>
					<template v-if="identityEditable">
						<EdgeLinkField :modelValue="editor.company" label="Company" placeholder="Choose Company" :required="true" :searcher="searchEditorCompany" @update:modelValue="setEditorCompany" />
						<EdgeLinkField :modelValue="editor.branch" label="Branch" placeholder="Choose unassigned Branch" :required="true" :searcher="searchEditorBranch" @update:modelValue="setEditorBranch" />
					</template>
					<div v-else class="identity-readonly"><span>Company</span><strong>{{ editor.company }}</strong></div>
					<div v-if="!identityEditable" class="identity-readonly"><span>Branch</span><strong>{{ editor.branch }}</strong></div>
					<label class="check-field"><input v-model="editor.is_default_for_company" type="checkbox" :true-value="1" :false-value="0" :disabled="saving" /><span><strong>Default Branch for Company</strong><small>Only one enabled default is allowed per Company.</small></span></label>
				</div>
				<div v-if="state.has_operational_history" class="history-warning">
					<strong>Operational history exists.</strong>
					<span>Company / Branch identity cannot be rewritten directly. Use the controlled change action so historical meaning is preserved.</span>
					<button v-if="state.can_reassign" type="button" class="edge-button edge-button--secondary" @click="openReassign">Change Company / Branch</button>
				</div>
			</section>

			<section v-if="activeTab === 'operations'" class="form-section">
				<h4>POS & stock defaults</h4>
				<p class="section-hint">POS Profile is optional for non-POS users. Stock Location choices are restricted to the selected Company.</p>
				<div class="form-grid">
					<EdgeLinkField :modelValue="editor.default_pos_profile" label="Default POS Profile" placeholder="Optional" :searcher="searchDefaultPosProfile" @update:modelValue="editor.default_pos_profile = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_pos_opening_cash_account" label="POS Opening Cash Account" placeholder="Optional" :searcher="searchPosOpeningAccount" @update:modelValue="editor.default_pos_opening_cash_account = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_cash_mode_of_payment" label="Cash Mode of Payment" placeholder="Optional" :searcher="searchCashMode" @update:modelValue="editor.default_cash_mode_of_payment = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_warehouse" label="Default Stock Location" placeholder="Optional" :searcher="searchDefaultWarehouse" @update:modelValue="editor.default_warehouse = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_source_warehouse" label="Default Source Stock Location" placeholder="Optional" :searcher="searchSourceWarehouse" @update:modelValue="editor.default_source_warehouse = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_target_warehouse" label="Default Destination Stock Location" placeholder="Optional" :searcher="searchTargetWarehouse" @update:modelValue="editor.default_target_warehouse = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_returns_warehouse" label="Default Returns Stock Location" placeholder="Optional" :searcher="searchReturnsWarehouse" @update:modelValue="editor.default_returns_warehouse = $event || ''" />
				</div>
			</section>

			<section v-if="activeTab === 'accounting'" class="form-section">
				<h4>Accounting defaults</h4>
				<p class="section-hint">These are defaults only. ERPNext accounting documents and ledgers remain authoritative.</p>
				<div class="form-grid">
					<EdgeLinkField :modelValue="editor.default_cost_center" label="Default Cost Center" placeholder="Optional" :searcher="searchDefaultCostCenter" @update:modelValue="editor.default_cost_center = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_sales_cost_center" label="Sales Cost Center" placeholder="Optional" :searcher="searchSalesCostCenter" @update:modelValue="editor.default_sales_cost_center = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_expense_cost_center" label="Expense Cost Center" placeholder="Optional" :searcher="searchExpenseCostCenter" @update:modelValue="editor.default_expense_cost_center = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_cash_account" label="Cash Account" placeholder="Optional" :searcher="searchCashAccount" @update:modelValue="editor.default_cash_account = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_bank_account" label="Bank Account" placeholder="Optional" :searcher="searchBankAccount" @update:modelValue="editor.default_bank_account = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_card_pos_account" label="Card/POS Settlement Account" placeholder="Optional" :searcher="searchCardAccount" @update:modelValue="editor.default_card_pos_account = $event || ''" />
					<EdgeLinkField :modelValue="editor.default_mobile_money_account" label="Mobile Money Account" placeholder="Optional" :searcher="searchMobileMoneyAccount" @update:modelValue="editor.default_mobile_money_account = $event || ''" />
				</div>
			</section>

			<section v-if="activeTab === 'controls'" class="form-section">
				<h4>Controls & audit</h4>
				<div class="control-grid">
					<label class="check-field"><input v-model="editor.enable_cashier_expense_control" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Cashier Expense Control</strong><small>Use RetailEdge branch controls for cashier expenses.</small></span></label>
					<label class="check-field"><input v-model="editor.enable_daily_sales_audit" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Daily Sales Audit</strong><small>Enable Branch daily audit workflows.</small></span></label>
					<label class="check-field"><input v-model="editor.enable_transaction_branch_attribution" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Transaction Branch Attribution</strong><small>Apply the Branch context to supported new RetailEdge work.</small></span></label>
					<label class="check-field"><input v-model="editor.require_pos_closing_shift_for_audit" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Require POS Closing Shift</strong><small>Require closing evidence for the audit flow where applicable.</small></span></label>
					<label class="edge-field"><span class="edge-field-label">Variance Tolerance</span><input v-model.number="editor.variance_tolerance" class="edge-input" type="number" step="0.01" min="0" /></label>
					<label class="edge-field edge-field--wide"><span class="edge-field-label">Notes</span><textarea v-model="editor.notes" class="edge-input" rows="4"></textarea></label>
				</div>
			</section>
		</div>
		<template #footer>
			<div class="modal-footer-actions">
				<button v-if="editor.name" type="button" class="edge-button" :disabled="saving" @click="openNative(editor.name)">Open Full Form</button>
				<div class="footer-right">
					<button type="button" class="edge-button" :disabled="saving" @click="closeEditor">Cancel</button>
					<button v-if="canWrite || !editor.name" type="button" class="edge-button edge-button--primary" :disabled="saving" @click="saveEditor">{{ saving ? "Saving…" : "Save Branch Setup" }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>

	<EdgeModal :open="reassignOpen" title="Change Company / Branch" subtitle="RetailEdge preserves historical meaning and clears Branch-specific defaults before applying the new mapping." size="lg" @close="closeReassign">
		<div v-if="reassignError" class="form-error">{{ reassignError }}</div>
		<div class="form-grid">
			<EdgeLinkField :modelValue="reassign.company" label="New Company" placeholder="Choose Company" :required="true" :searcher="searchReassignCompany" @update:modelValue="setReassignCompany" />
			<EdgeLinkField :modelValue="reassign.branch" label="New Branch" placeholder="Choose Branch" :required="true" :searcher="searchReassignBranch" @update:modelValue="reassign.branch = $event || ''" />
		</div>
		<div class="history-warning"><strong>History-safe change</strong><span>Submitted ERPNext transactions are not changed. Active POS work can block the reassignment.</span></div>
		<template #footer>
			<div class="modal-footer-actions">
				<span></span>
				<div class="footer-right">
					<button type="button" class="edge-button" :disabled="reassigning" @click="closeReassign">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="reassigning || !reassign.company || !reassign.branch" @click="submitReassign">{{ reassigning ? "Changing…" : "Validate & Change" }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeStatusBadge", "EdgeModal", "EdgeLinkField"];
const CONTEXT_METHOD = "retailedge.branch_setup.get_branch_setup_context";
const GET_METHOD = "retailedge.branch_setup.get_branch_setup";
const SAVE_METHOD = "retailedge.branch_setup.save_branch_setup";
const SEARCH_METHOD = "retailedge.branch_setup.search_branch_setup_options";
const REASSIGN_METHOD = "retailedge.retailedge.doctype.retailedge_branch_profile.retailedge_branch_profile.reassign_branch_profile";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
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
function blankEditor() {
	return {
		name: "", profile_name: "", enabled: 1, company: "", branch: "", is_default_for_company: 0,
		default_pos_profile: "", default_pos_opening_cash_account: "", default_cash_mode_of_payment: "",
		default_warehouse: "", default_source_warehouse: "", default_target_warehouse: "", default_returns_warehouse: "",
		default_cost_center: "", default_sales_cost_center: "", default_expense_cost_center: "",
		default_cash_account: "", default_bank_account: "", default_card_pos_account: "", default_mobile_money_account: "",
		enable_cashier_expense_control: 1, enable_daily_sales_audit: 1, enable_transaction_branch_attribution: 1,
		require_pos_closing_shift_for_audit: 0, variance_tolerance: 0, notes: "",
	};
}
const DEPENDENT_FIELDS = [
	"default_pos_profile", "default_pos_opening_cash_account", "default_cash_mode_of_payment",
	"default_warehouse", "default_source_warehouse", "default_target_warehouse", "default_returns_warehouse",
	"default_cost_center", "default_sales_cost_center", "default_expense_cost_center",
	"default_cash_account", "default_bank_account", "default_card_pos_account", "default_mobile_money_account",
];

export default {
	name: "RetailEdgeBranchSetup",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], loading: false, loaded: false, error: "", profiles: [], canCreate: false, canWrite: false,
		filters: { company: "", branch: "", enabled: "" }, sortKey: "company", sortDirection: "asc", userName: "", menuItems: [],
		editorOpen: false, editorLoading: false, saving: false, editorError: "", editor: blankEditor(), state: {}, activeTab: "identity",
		reassignOpen: false, reassigning: false, reassignError: "", reassign: { company: "", branch: "" },
		tabs: [{ key: "identity", label: "Identity" }, { key: "operations", label: "POS & Stock" }, { key: "accounting", label: "Accounting" }, { key: "controls", label: "Controls" }],
		columns: [
			{ key: "profile_name", label: "Setup" }, { key: "company", label: "Company" }, { key: "branch", label: "Branch" },
			{ key: "enabled", label: "Status" }, { key: "is_default_for_company", label: "Default" },
			{ key: "default_pos_profile", label: "POS Profile" }, { key: "default_warehouse", label: "Stock Location" },
		],
		};
	},
	computed: {
		sortedProfiles() {
			const direction = this.sortDirection === "asc" ? 1 : -1;
			return [...this.profiles].sort((a, b) => String(a?.[this.sortKey] ?? "").localeCompare(String(b?.[this.sortKey] ?? "")) * direction);
		},
		editorTitle() { return this.editor.name ? (this.editor.profile_name || "Branch Setup") : "Add Branch Setup"; },
		identityEditable() { return !this.editor.name || Boolean(this.state.identity_editable); },
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadProfiles();
	},
	mounted() {
		window.addEventListener("retailedge-branch-setup-page-show", this._onPageShow);
		if (this.edgeUIValid) { this.loadNavigation(); this.loadProfiles(); }
	},
	beforeUnmount() { window.removeEventListener("retailedge-branch-setup-page-show", this._onPageShow); },
	methods: {
		async loadNavigation() {
			try {
				const navigation = typeof window.retailedgeGetBusinessHubContext === "function" ? await window.retailedgeGetBusinessHubContext() : await callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				this.menuItems = (navigation.navigation_groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) }));
				this.userName = navigation.context?.user_name || "";
			} catch (error) { this.menuItems = []; }
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
		async loadProfiles() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const data = await callMethod(CONTEXT_METHOD, { filters: this.filters });
				this.profiles = Array.isArray(data.profiles) ? data.profiles : [];
				this.canCreate = Boolean(data.can_create); this.canWrite = Boolean(data.can_write); this.userName = this.userName || data.user_name || ""; this.loaded = true;
			} catch (error) { this.error = error?.message || error?.exc || __("Branch Setup could not be loaded."); }
			finally { this.loading = false; }
		},
		clearFilters() { this.filters = { company: "", branch: "", enabled: "" }; this.loadProfiles(); },
		setFilterCompany(value) { this.filters.company = value || ""; this.filters.branch = ""; },
		setSort(key) { if (this.sortKey === key) this.sortDirection = this.sortDirection === "asc" ? "desc" : "asc"; else { this.sortKey = key; this.sortDirection = "asc"; } },
		search(fieldname, query, values = this.editor) { return callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values }).then((rows) => Array.isArray(rows) ? rows : []); },
		searchFilterCompany(query) { return this.search("company", query, {}); },
		searchFilterBranch(query) { return this.search("filter_branch", query, { company: this.filters.company }); },
		searchEditorCompany(query) { return this.search("company", query, this.editor); },
		searchEditorBranch(query) { return this.search("branch", query, this.editor); },
		searchDefaultPosProfile(query) { return this.search("default_pos_profile", query); },
		searchPosOpeningAccount(query) { return this.search("default_pos_opening_cash_account", query); },
		searchCashMode(query) { return this.search("default_cash_mode_of_payment", query); },
		searchDefaultWarehouse(query) { return this.search("default_warehouse", query); },
		searchSourceWarehouse(query) { return this.search("default_source_warehouse", query); },
		searchTargetWarehouse(query) { return this.search("default_target_warehouse", query); },
		searchReturnsWarehouse(query) { return this.search("default_returns_warehouse", query); },
		searchDefaultCostCenter(query) { return this.search("default_cost_center", query); },
		searchSalesCostCenter(query) { return this.search("default_sales_cost_center", query); },
		searchExpenseCostCenter(query) { return this.search("default_expense_cost_center", query); },
		searchCashAccount(query) { return this.search("default_cash_account", query); },
		searchBankAccount(query) { return this.search("default_bank_account", query); },
		searchCardAccount(query) { return this.search("default_card_pos_account", query); },
		searchMobileMoneyAccount(query) { return this.search("default_mobile_money_account", query); },
		openNew() { this.editor = blankEditor(); this.state = { identity_editable: true }; this.activeTab = "identity"; this.editorError = ""; this.editorOpen = true; },
		async openEdit(row) {
			this.editorOpen = true; this.editorLoading = true; this.editorError = ""; this.activeTab = "identity";
			try { const data = await callMethod(GET_METHOD, { name: row.name }); this.editor = { ...blankEditor(), ...(data.doc || {}) }; this.state = data.state || {}; this.canWrite = Boolean(data.can_write); }
			catch (error) { this.editorError = error?.message || error?.exc || __("Branch Setup could not be opened."); }
			finally { this.editorLoading = false; }
		},
		closeEditor() { if (!this.saving) { this.editorOpen = false; this.editorError = ""; } },
		setEditorCompany(value) {
			const next = value || ""; if (next === this.editor.company) return; this.editor.company = next; this.editor.branch = "";
			DEPENDENT_FIELDS.forEach((field) => { this.editor[field] = ""; }); this.editor.is_default_for_company = 0;
		},
		setEditorBranch(value) {
			const next = value || ""; if (next === this.editor.branch) return; this.editor.branch = next;
			DEPENDENT_FIELDS.forEach((field) => { this.editor[field] = ""; });
		},
		async saveEditor() {
			if (!this.editor.profile_name || !this.editor.company || !this.editor.branch) { this.editorError = __("Setup Name, Company and Branch are required."); return; }
			this.saving = true; this.editorError = "";
			try {
				const result = await callMethod(SAVE_METHOD, { values: this.editor }, { freeze: true, freezeMessage: __("Saving Branch Setup...") });
				this.editor = { ...blankEditor(), ...(result.doc || {}) }; this.state = result.state || {}; frappe.show_alert({ message: __("Branch Setup saved."), indicator: "green" });
				this.editorOpen = false; await this.loadProfiles();
			} catch (error) { this.editorError = error?.message || error?.exc || __("Branch Setup could not be saved."); }
			finally { this.saving = false; }
		},
		openReassign() { this.reassign = { company: this.editor.company || "", branch: "" }; this.reassignError = ""; this.reassignOpen = true; },
		closeReassign() { if (!this.reassigning) this.reassignOpen = false; },
		searchReassignCompany(query) { return this.search("company", query, {}); },
		searchReassignBranch(query) { return this.search("reassignment_branch", query, { name: this.editor.name, company: this.reassign.company }); },
		setReassignCompany(value) { this.reassign.company = value || ""; this.reassign.branch = ""; },
		async submitReassign() {
			this.reassigning = true; this.reassignError = "";
			try {
				const result = await callMethod(REASSIGN_METHOD, { name: this.editor.name, new_company: this.reassign.company, new_branch: this.reassign.branch }, { freeze: true, freezeMessage: __("Changing Branch mapping...") });
				this.reassignOpen = false; frappe.show_alert({ message: result.historical_setup ? __("Branch mapping changed and history preserved.") : __("Branch mapping changed."), indicator: "green" });
				await this.openEdit({ name: this.editor.name }); await this.loadProfiles();
			} catch (error) { this.reassignError = error?.message || error?.exc || __("Branch mapping could not be changed."); }
			finally { this.reassigning = false; }
		},
		openAssignments() { frappe.set_route("branch-assignments"); },
		openNative(name) { if (name) window.open(`/app/retailedge-branch-profile/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer"); },
	},
};
</script>

<style scoped>
.branch-setup-layout, .editor-body { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.branch-setup-summary { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.branch-setup-summary h3, .form-section h4 { margin: 0.2rem 0 0.35rem; }
.branch-setup-summary p, .section-hint { margin: 0; color: var(--text-muted); }
.setup-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.summary-actions, .filter-actions, .row-actions, .modal-footer-actions, .footer-right, .editor-tabs { display: flex; gap: 0.65rem; flex-wrap: wrap; }
.modal-footer-actions { width: 100%; justify-content: space-between; }
.filter-grid, .form-grid, .control-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.filter-actions { margin-top: 1rem; }
.table-wrap { overflow-x: auto; }
.branch-setup-table { width: 100%; border-collapse: collapse; min-width: 980px; }
.branch-setup-table th, .branch-setup-table td { padding: 0.75rem; border-bottom: 1px solid var(--edge-border-color, var(--border-color)); text-align: left; vertical-align: middle; }
.sort-button, .link-button { border: 0; background: transparent; color: inherit; font: inherit; padding: 0; cursor: pointer; }
.sort-button { font-weight: 600; }
.link-button { color: var(--primary); font-weight: 600; }
.status-text { margin-left: 0.35rem; }
.empty-cell { text-align: center !important; color: var(--text-muted); padding: 2rem !important; }
.form-section { display: grid; gap: 1rem; }
.edge-field { display: grid; gap: 0.35rem; }
.edge-field--wide { grid-column: 1 / -1; }
.edge-input { width: 100%; padding: 0.65rem 0.75rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.45rem; background: var(--edge-surface, var(--control-bg)); color: var(--text-color); }
.check-field { display: flex; gap: 0.65rem; align-items: flex-start; padding: 0.7rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.55rem; }
.check-field span { display: grid; gap: 0.2rem; }
.check-field small { color: var(--text-muted); }
.identity-readonly { display: grid; gap: 0.2rem; padding: 0.7rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.55rem; }
.identity-readonly span { color: var(--text-muted); font-size: 0.8rem; }
.history-warning, .form-error { padding: 0.85rem; border-radius: 0.55rem; display: grid; gap: 0.35rem; }
.history-warning { border: 1px solid var(--orange-300, var(--edge-border-color, var(--border-color))); background: var(--edge-surface-subtle, var(--subtle-accent)); }
.form-error { border: 1px solid var(--red-300, var(--edge-border-color, var(--border-color))); }
@media (max-width: 760px) { .branch-setup-summary { flex-direction: column; } .filter-grid, .form-grid, .control-grid { grid-template-columns: 1fr; } .edge-field--wide { grid-column: auto; } }
</style>
