<template>
	<div v-if="!edgeUIValid" class="business-expense-fallback">
		<strong>Business Expenses could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Business Expenses"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch || values.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/business-expenses"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<div class="business-expense-page">
			<header class="business-expense-header">
				<div>
					<p class="eyebrow">Expense Control</p>
					<h2>Business Expenses</h2>
					<p>Capture direct non-POS spending, evidence and approvals without leaving EdgeSuite.</p>
				</div>
				<div class="header-actions">
					<button type="button" class="edge-button" @click="openExpenseRegister">Expense Register</button>
					<button type="button" class="edge-button" @click="openExpenseCategories">Expense Categories</button>
					<button v-if="canCreate" type="button" class="edge-button edge-button--primary" @click="openNewExpense">New Expense</button>
				</div>
			</header>

			<EdgeLoadingState v-if="metadataLoading" message="Preparing Business Expenses..." :skeleton="true" />
			<EdgeErrorState v-else-if="metadataError" title="Business Expenses unavailable" :message="metadataError" @retry="loadMetadata" />

			<template v-else>
				<section v-if="screen === 'list'" class="edge-card">
					<div class="section-heading">
						<div>
							<h3>Expense queue</h3>
							<p>Draft, approval and posting-readiness states are operational; posted accounting remains in Expense Register.</p>
						</div>
					</div>

					<div class="filter-grid">
						<EdgeLinkField v-model="filters.company" label="Company" :searcher="companySearch" required @select="selectFilterCompany" />
						<EdgeLinkField v-model="filters.branch" label="Branch" :searcher="branchSearch" placeholder="All permitted branches" @select="selectFilterBranch" @clear="clearFilterBranch" />
						<EdgeLinkField v-model="filters.expense_category" label="Expense Category" :searcher="categorySearchForFilter" placeholder="All categories" @select="selectFilterCategory" @clear="clearFilterCategory" />
						<label class="field-wrap">
							<span>Status</span>
							<select v-model="filters.expense_status" class="edge-input">
								<option value="">All statuses</option>
								<option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
							</select>
						</label>
						<label class="field-wrap"><span>From Date</span><input v-model="filters.from_date" class="edge-input" type="date" /></label>
						<label class="field-wrap"><span>To Date</span><input v-model="filters.to_date" class="edge-input" type="date" /></label>
						<label class="field-wrap filter-search"><span>Search</span><input v-model="filters.search_text" class="edge-input" placeholder="Reference, payee, supplier..." @keyup.enter="applyFilters" /></label>
						<div class="filter-action"><button type="button" class="edge-button edge-button--primary" :disabled="listLoading" @click="applyFilters">{{ listLoading ? "Loading..." : "Apply" }}</button></div>
					</div>

					<div class="queue-summary">
						<div><span>Expenses</span><strong>{{ Number(summary.count || 0).toLocaleString() }}</strong></div>
						<div><span>Operational value</span><strong>{{ formatAmount(summary.total_amount) }}</strong></div>
						<div><span>Scope</span><strong>{{ scopeLabel }}</strong></div>
					</div>

					<div v-if="listError" class="error-banner">{{ listError }}</div>
					<div class="table-wrap">
						<table class="expense-table">
							<thead><tr><th>Date</th><th>Expense</th><th>Payee</th><th>Branch</th><th>Status</th><th>Ledger</th><th class="amount">Amount</th></tr></thead>
							<tbody>
								<tr v-for="row in rows" :key="row.name" class="expense-row" @click="openExpense(row.name)">
									<td>{{ formatDate(row.expense_date) }}</td>
									<td><strong>{{ row.expense_category }}</strong><small>{{ row.reference_no || row.name }}</small></td>
									<td>{{ row.supplier || row.payee_name || "—" }}</td>
									<td>{{ row.branch || "Company-wide" }}</td>
									<td><span class="status-pill">{{ row.expense_status || "Draft" }}</span></td>
									<td>{{ row.ledger_status || "Not Applicable" }}</td>
									<td class="amount">{{ formatAmount(row.amount) }}</td>
								</tr>
								<tr v-if="!listLoading && !rows.length"><td colspan="7" class="empty-cell">No Business Expenses match the selected filters.</td></tr>
							</tbody>
						</table>
					</div>
					<div class="pagination-bar">
						<span>Page {{ pagination.page || 1 }} of {{ pagination.total_pages || 1 }}</span>
						<div>
							<button type="button" class="edge-button" :disabled="!pagination.has_previous || listLoading" @click="goToPage((pagination.page || 1) - 1)">Previous</button>
							<button type="button" class="edge-button" :disabled="!pagination.has_next || listLoading" @click="goToPage((pagination.page || 1) + 1)">Next</button>
						</div>
					</div>
				</section>

				<section v-else-if="screen === 'form'" class="edge-card">
					<div class="section-heading">
						<div><h3>{{ editingName ? "Edit Draft" : "New Business Expense" }}</h3><p>For direct paid business spend. Supplier credit bills remain in the Purchase Invoice workflow.</p></div>
						<button type="button" class="edge-button" @click="returnToList">Back to Queue</button>
					</div>
					<div class="form-grid">
						<EdgeLinkField v-model="values.company" label="Company" :searcher="companySearch" required @select="selectCompany" />
						<EdgeLinkField v-model="values.branch" label="Branch" :searcher="branchSearchForForm" placeholder="Choose Branch when required" @select="selectBranch" @clear="clearBranch" />
						<label class="field-wrap"><span>Expense Date</span><input v-model="values.expense_date" class="edge-input" type="date" required /></label>
						<EdgeLinkField v-model="values.expense_category" label="Expense Category" :searcher="categorySearchForForm" required @select="selectCategory" />
						<label class="field-wrap"><span>Amount</span><input v-model.number="values.amount" class="edge-input" type="number" min="0.01" step="0.01" required /></label>
						<label class="field-wrap"><span>Payee Type</span><select v-model="values.payee_type" class="edge-input" @change="payeeTypeChanged"><option value="Other">Other / Merchant</option><option value="Supplier">Supplier</option></select></label>
						<EdgeLinkField v-if="values.payee_type === 'Supplier'" v-model="values.supplier" label="Supplier" :searcher="supplierSearch" required @select="selectSupplier" />
						<label v-else class="field-wrap"><span>Payee / Merchant</span><input v-model="values.payee_name" class="edge-input" placeholder="Who was paid?" /></label>
						<label class="field-wrap"><span>Receipt / Reference No.</span><input v-model="values.reference_no" class="edge-input" /></label>
						<EdgeLinkField v-model="values.payment_account" label="Paid From" :searcher="paymentAccountSearch" placeholder="Cash or Bank account" required @select="selectPaymentAccount" />
						<EdgeLinkField v-model="values.cost_center" label="Cost Centre" :searcher="costCenterSearch" placeholder="Optional" @select="selectCostCenter" @clear="clearCostCenter" />
						<EdgeLinkField v-model="values.project" label="Project" :searcher="projectSearch" placeholder="Optional" @select="selectProject" @clear="clearProject" />
					</div>
					<div v-if="categoryDefaults.expense_account" class="derived-context">
						<div><span>Expense Account</span><strong>{{ categoryDefaults.expense_account }}</strong></div>
						<div><span>Category Cost Centre</span><strong>{{ categoryDefaults.cost_center || "Not set" }}</strong></div>
					</div>
					<label class="field-wrap full-width"><span>Description</span><textarea v-model="values.description" class="edge-input" rows="3" placeholder="What was this expense for?"></textarea></label>
					<div v-if="formError" class="error-banner">{{ formError }}</div>
					<div class="form-actions"><button type="button" class="edge-button" @click="returnToList">Cancel</button><button type="button" class="edge-button edge-button--primary" :disabled="saving" @click="saveDraft">{{ saving ? "Saving..." : "Save Draft" }}</button></div>
				</section>

				<section v-else class="detail-stack">
					<div class="edge-card">
						<div class="section-heading">
							<div><p class="eyebrow">{{ current.name }}</p><h3>{{ current.expense_category }}</h3><p>{{ current.supplier || current.payee_name || "Business expense" }} · {{ formatAmount(current.amount) }}</p></div>
							<div class="header-actions"><button v-if="current.can_edit" type="button" class="edge-button" @click="editCurrent">Edit Draft</button><button type="button" class="edge-button" @click="returnToList">Back to Queue</button></div>
						</div>
						<div class="detail-grid">
							<div><span>Document</span><strong>{{ documentStatus }}</strong></div>
							<div><span>Workflow State</span><strong>{{ current.workflow_readiness?.current_state || current.expense_status || "—" }}</strong></div>
							<div><span>Ledger Status</span><strong>{{ current.ledger_status || "Not Applicable" }}</strong></div>
							<div><span>Branch</span><strong>{{ current.branch || "Company-wide" }}</strong></div>
							<div><span>Expense Account</span><strong>{{ current.expense_account || "—" }}</strong></div>
							<div><span>Paid From</span><strong>{{ current.payment_account || "—" }}</strong></div>
							<div><span>Cost Centre</span><strong>{{ current.cost_center || "—" }}</strong></div>
							<div><span>Project</span><strong>{{ current.project || "—" }}</strong></div>
							<div><span>Requested By</span><strong>{{ current.requested_by || "—" }}</strong></div>
						</div>
						<p v-if="current.description" class="detail-description">{{ current.description }}</p>
					</div>

					<div class="edge-card">
						<div class="section-heading">
							<div><h3>Receipt / evidence</h3><p>{{ settings.require_attachment ? "Evidence is required before submission." : "Attach a receipt or supporting document for audit evidence." }}</p></div>
							<button v-if="current.can_edit" type="button" class="edge-button" @click="uploadEvidence">Attach Evidence</button>
						</div>
						<a v-if="current.attachment" class="attachment-link" :href="current.attachment" target="_blank" rel="noopener">{{ current.attachment }}</a>
						<div v-else class="empty-note">No receipt or evidence attached yet.</div>
					</div>

					<div class="edge-card">
						<div class="section-heading"><div><h3>Approval & workflow</h3><p>{{ current.workflow_readiness?.message || "Normal document permissions apply." }}</p></div></div>
						<div class="workflow-meta"><span>Process</span><strong>{{ current.workflow_readiness?.workflow || settings.process || "Normal document lifecycle" }}</strong></div>
						<label v-if="(current.workflow_readiness?.available_actions || []).length" class="field-wrap full-width"><span>Action note / rejection reason</span><textarea v-model="actionRemarks" class="edge-input" rows="2" placeholder="Optional except where the selected action requires remarks"></textarea></label>
						<div v-if="actionError" class="error-banner">{{ actionError }}</div>
						<div class="workflow-actions">
							<button v-for="action in current.workflow_readiness?.available_actions || []" :key="action.action" type="button" class="edge-button edge-button--primary" :disabled="acting" @click="applyWorkflow(action.action)"><span>{{ action.action }}</span><small v-if="action.next_state">→ {{ action.next_state }}</small></button>
							<span v-if="!(current.workflow_readiness?.available_actions || []).length" class="empty-note">No workflow action is currently available to this user.</span>
						</div>
					</div>

					<div v-if="Number(current.docstatus || 0) === 1 || current.posting_reference" class="edge-card">
						<div class="section-heading">
							<div><h3>Accounting posting</h3><p>Accounting entries remain the financial truth. This action never writes the ledger directly.</p></div>
							<button v-if="postingReadiness.can_post && !current.posting_reference" type="button" class="edge-button edge-button--primary" :disabled="postingAction" @click="postToAccounts">{{ postingAction ? "Posting..." : "Post to Accounts" }}</button>
						</div>
						<div v-if="postingLoading" class="empty-note">Checking accounting readiness...</div>
						<div v-else-if="current.posting_reference" class="posting-reference"><span>{{ current.posting_reference_type }}</span><strong>{{ current.posting_reference }}</strong></div>
						<div v-else class="posting-readiness">
							<div><span>Readiness</span><strong>{{ postingReadiness.posting_ready ? "Ready" : "Blocked" }}</strong></div>
							<p v-if="postingReadiness.posting_block_reason">{{ postingReadiness.posting_block_reason }}</p>
							<p v-else-if="postingReadiness.posting_ready && !postingReadiness.can_post">You do not have accounting-posting permission for this expense.</p>
						</div>
						<div v-if="postingError" class="error-banner">{{ postingError }}</div>
					</div>
				</section>
			</template>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState"];
const CONTEXT_METHOD = "retailedge.business_expense.get_business_expense_context";
const LIST_METHOD = "retailedge.business_expense.get_business_expenses";
const SEARCH_METHOD = "retailedge.business_expense.search_business_expense_options";
const CATEGORY_DEFAULTS_METHOD = "retailedge.business_expense.get_business_expense_category_defaults";
const CREATE_METHOD = "retailedge.business_expense.create_business_expense_draft";
const UPDATE_METHOD = "retailedge.business_expense.update_business_expense_draft";
const ATTACH_METHOD = "retailedge.business_expense.set_business_expense_attachment";
const GET_METHOD = "retailedge.business_expense.get_business_expense";
const WORKFLOW_METHOD = "retailedge.workflow_actions.apply_document_workflow_action";
const POSTING_READINESS_METHOD = "retailedge.business_expense_posting.get_business_expense_posting_readiness";
const POST_METHOD = "retailedge.business_expense_posting.post_business_expense_to_accounts";
const DOCTYPE = "RetailEdge Business Expense";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }
function blankValues() {
	return { company: "", branch: "", expense_date: "", expense_category: "", amount: "", description: "", payee_type: "Other", supplier: "", payee_name: "", reference_no: "", payment_account: "", cost_center: "", project: "" };
}

export default {
	name: "BusinessExpenses",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, metadataError: "",
			listLoading: false, listError: "", saving: false, formError: "", acting: false, actionError: "",
			postingLoading: false, postingAction: false, postingError: "", postingReadiness: {},
			tenantName: "", branchName: "", userName: "", menuItems: [], canUseNativeDesk: false,
			canCreate: false, canReview: false, settings: {}, statuses: [], defaultValues: {},
			filters: { company: "", branch: "", from_date: "", to_date: "", expense_category: "", expense_status: "", search_text: "", page_size: 25 },
			rows: [], summary: {}, pagination: {}, scope: {}, screen: "list", values: blankValues(),
			categoryDefaults: {}, current: {}, editingName: "", actionRemarks: "",
		};
	},
	computed: {
		documentStatus() { const status = Number(this.current.docstatus || 0); return status === 1 ? "Submitted" : status === 2 ? "Cancelled" : "Draft"; },
		scopeLabel() { if (this.filters.branch) return this.filters.branch; return this.scope.restricted ? "Permitted branches" : "Company-wide"; },
	},
	created() {
		const runtime = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !runtime[name]);
		this.edgeUIValid = !this.missingComponents.length;
	},
	mounted() { this.loadMetadata(); },
	methods: {
		async loadMetadata() {
			this.metadataLoading = true; this.metadataError = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod(CONTEXT_METHOD), navigationPromise]);
				this.tenantName = context.default_values?.company || ""; this.branchName = context.default_values?.branch || ""; this.userName = navigation.context?.user_name || frappe.session?.user || "";
				this.defaultValues = { ...blankValues(), ...(context.default_values || {}) }; this.values = { ...this.defaultValues };
				this.filters = { ...this.filters, ...(context.default_filters || {}) }; this.settings = context.settings || {}; this.statuses = context.statuses || [];
				this.canCreate = Boolean(context.capabilities?.can_create); this.canReview = Boolean(context.capabilities?.can_review);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []); this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				const routeOptions = frappe.route_options || {}; frappe.route_options = null;
				if (routeOptions.business_expense) await this.openExpense(routeOptions.business_expense);
				else if (routeOptions.action === "new" && this.canCreate) this.openNewExpense();
				else await this.fetchList();
			} catch (error) { this.metadataError = errorMessage(error, "Unable to prepare Business Expenses."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return "/app/" + item.target; if (item.target_type === "Report") return "/app/query-report/" + encodeURIComponent(item.target); if (item.target_type === "DocType") return "/app/" + String(item.target || "").toLowerCase().replace(/\s+/g, "-"); return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		hasPageTarget(target) { return Boolean(target && this.menuItems.flatMap((group) => group.items || []).some((item) => item.target_type === "Page" && item.target === target)); },
		async search(kind, txt, formValues = this.values) { const result = await callMethod(SEARCH_METHOD, { kind, txt: txt || "", company: formValues.company || this.filters.company, branch: formValues.branch || "" }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.search("company", txt, this.values); }, branchSearch(txt) { return this.search("branch", txt, this.filters); }, branchSearchForForm(txt) { return this.search("branch", txt, this.values); },
		categorySearchForFilter(txt) { return this.search("expense_category", txt, this.filters); }, categorySearchForForm(txt) { return this.search("expense_category", txt, this.values); },
		paymentAccountSearch(txt) { return this.search("payment_account", txt, this.values); }, costCenterSearch(txt) { return this.search("cost_center", txt, this.values); }, projectSearch(txt) { return this.search("project", txt, this.values); }, supplierSearch(txt) { return this.search("supplier", txt, this.values); },
		selectFilterCompany(option) { this.filters.company = option.value || ""; this.filters.branch = ""; this.filters.expense_category = ""; },
		selectFilterBranch(option) { this.filters.branch = option.value || ""; }, clearFilterBranch() { this.filters.branch = ""; },
		selectFilterCategory(option) { this.filters.expense_category = option.value || ""; }, clearFilterCategory() { this.filters.expense_category = ""; },
		applyFilters() { this.pagination.page = 1; this.fetchList(1); },
		async fetchList(page = this.pagination.page || 1) { if (!this.filters.company) return; this.listLoading = true; this.listError = ""; try { const result = await callMethod(LIST_METHOD, { filters: this.filters, page, page_size: this.filters.page_size || 25 }); this.rows = result.rows || []; this.summary = result.summary || {}; this.pagination = result.pagination || {}; this.scope = result.scope || {}; } catch (error) { this.rows = []; this.listError = errorMessage(error, "Unable to load Business Expenses."); } finally { this.listLoading = false; } },
		goToPage(page) { if (page > 0) this.fetchList(page); },
		openNewExpense() { if (!this.canCreate) return; this.values = { ...this.defaultValues }; this.categoryDefaults = {}; this.editingName = ""; this.formError = ""; this.screen = "form"; },
		selectCompany(option) { this.values.company = option.value || ""; this.values.branch = ""; this.values.expense_category = ""; this.values.payment_account = ""; this.values.cost_center = ""; this.values.project = ""; this.categoryDefaults = {}; },
		selectBranch(option) { this.values.branch = option.value || ""; this.values.expense_category = ""; this.values.cost_center = ""; this.categoryDefaults = {}; }, clearBranch() { this.values.branch = ""; this.values.expense_category = ""; this.values.cost_center = ""; this.categoryDefaults = {}; },
		async selectCategory(option) { this.values.expense_category = option.value || ""; this.categoryDefaults = {}; if (!this.values.expense_category) return; try { this.categoryDefaults = await callMethod(CATEGORY_DEFAULTS_METHOD, { expense_category: this.values.expense_category, company: this.values.company }); if (this.categoryDefaults.cost_center) this.values.cost_center = this.categoryDefaults.cost_center; if (!this.values.description && this.categoryDefaults.description) this.values.description = this.categoryDefaults.description; } catch (error) { this.formError = errorMessage(error, "Unable to resolve Expense Category."); } },
		payeeTypeChanged() { if (this.values.payee_type === "Supplier") this.values.payee_name = ""; else this.values.supplier = ""; },
		selectSupplier(option) { this.values.supplier = option.value || ""; }, selectPaymentAccount(option) { this.values.payment_account = option.value || ""; },
		selectCostCenter(option) { this.values.cost_center = option.value || ""; }, clearCostCenter() { this.values.cost_center = ""; }, selectProject(option) { this.values.project = option.value || ""; }, clearProject() { this.values.project = ""; },
		async saveDraft() { if (this.saving) return; this.saving = true; this.formError = ""; try { let result; if (this.editingName) result = await callMethod(UPDATE_METHOD, { name: this.editingName, values: this.values, expected_modified: this.current.modified }); else result = await callMethod(CREATE_METHOD, { values: this.values }); this.current = result || {}; this.editingName = ""; this.actionRemarks = ""; this.screen = "detail"; frappe.show_alert?.({ message: "Business Expense saved as Draft", indicator: "green" }); } catch (error) { this.formError = errorMessage(error, "Unable to save the Business Expense draft."); } finally { this.saving = false; } },
		async openExpense(name) { this.actionError = ""; this.actionRemarks = ""; this.postingError = ""; this.current = await callMethod(GET_METHOD, { name }); this.settings = this.current.settings || this.settings; this.screen = "detail"; if (Number(this.current.docstatus || 0) === 1 || this.current.posting_reference) await this.loadPostingReadiness(); else this.postingReadiness = {}; },
		async loadPostingReadiness() { if (!this.current.name) return; this.postingLoading = true; try { this.postingReadiness = await callMethod(POSTING_READINESS_METHOD, { name: this.current.name }); } catch (error) { this.postingReadiness = {}; this.postingError = errorMessage(error, "Unable to check accounting-posting readiness."); } finally { this.postingLoading = false; } },
		editCurrent() { if (!this.current.can_edit) return; this.values = { ...blankValues(), company: this.current.company || "", branch: this.current.branch || "", expense_date: this.current.expense_date || "", expense_category: this.current.expense_category || "", amount: this.current.amount || "", description: this.current.description || "", payee_type: this.current.payee_type || "Other", supplier: this.current.supplier || "", payee_name: this.current.payee_name || "", reference_no: this.current.reference_no || "", payment_account: this.current.payment_account || "", cost_center: this.current.cost_center || "", project: this.current.project || "" }; this.categoryDefaults = { expense_account: this.current.expense_account || "", cost_center: this.current.cost_center || "" }; this.editingName = this.current.name; this.screen = "form"; },
		returnToList() { this.screen = "list"; this.editingName = ""; this.current = {}; this.postingReadiness = {}; this.postingError = ""; this.fetchList(); },
		async uploadEvidence() { if (!this.current.name || !this.current.can_edit) return; this.actionError = ""; try { if (!frappe.ui?.FileUploader) await new Promise((resolve, reject) => { try { const pending = frappe.require("file_uploader.bundle.js", resolve); if (pending && typeof pending.then === "function") pending.then(resolve).catch(reject); } catch (error) { reject(error); } }); new frappe.ui.FileUploader({ doctype: DOCTYPE, docname: this.current.name, fieldname: "attachment", allow_multiple: false, make_attachments_public: false, on_success: async (file) => { try { this.current = await callMethod(ATTACH_METHOD, { name: this.current.name, file_url: file.file_url, expected_modified: this.current.modified }); frappe.show_alert?.({ message: "Evidence attached", indicator: "green" }); } catch (error) { this.actionError = errorMessage(error, "Evidence uploaded but could not be linked to the expense."); } } }); } catch (error) { this.actionError = errorMessage(error, "Unable to open the evidence uploader."); } },
		async applyWorkflow(action) { if (this.acting || !action) return; this.acting = true; this.actionError = ""; try { await callMethod(WORKFLOW_METHOD, { doctype: DOCTYPE, name: this.current.name, action, expected_modified: this.current.modified, expected_state: this.current.workflow_readiness?.current_state || "", remarks: this.actionRemarks || "" }); await this.openExpense(this.current.name); frappe.show_alert?.({ message: "Workflow action applied: " + action, indicator: "green" }); } catch (error) { this.actionError = errorMessage(error, "Unable to apply the workflow action."); } finally { this.acting = false; } },
		postToAccounts() { if (this.postingAction || !this.postingReadiness.can_post || !this.current.name) return; frappe.confirm("Post this approved Business Expense to accounts? This will create and submit the accounting entry.", () => this.confirmPostToAccounts()); },
		async confirmPostToAccounts() { if (this.postingAction || !this.current.name) return; this.postingAction = true; this.postingError = ""; try { const result = await callMethod(POST_METHOD, { name: this.current.name, expected_modified: this.current.modified }); const expenseName = result.expense?.name || this.current.name; await this.openExpense(expenseName); frappe.show_alert?.({ message: result.idempotent ? "Business Expense was already posted" : "Business Expense posted to accounts", indicator: "green" }); } catch (error) { this.postingError = errorMessage(error, "Unable to post this Business Expense to accounts."); await this.loadPostingReadiness(); } finally { this.postingAction = false; } },
		openExpenseRegister() { frappe.set_route("expense-register"); },
		openExpenseCategories() { if (!this.hasPageTarget("retailedge-setup")) return; frappe.route_options = { setup_resource: "expense-categories" }; frappe.set_route("retailedge-setup"); },
		formatAmount(value) { const amount = Number(value) || 0; try { return frappe.format(amount, { fieldtype: "Currency" }); } catch (_error) { return amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(String(value)); } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.business-expense-page { display: grid; gap: 18px; padding: 18px 22px 32px; }
.business-expense-header, .section-heading, .header-actions, .form-actions, .pagination-bar, .workflow-actions { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.business-expense-header h2, .section-heading h3 { margin: 0; }
.business-expense-header p, .section-heading p { margin: 4px 0 0; color: var(--edge-text-muted, #667085); }
.eyebrow { margin: 0 0 4px !important; font-size: .74rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; color: var(--edge-text-muted, #667085); }
.edge-card { display: grid; gap: 16px; padding: 18px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 12px; background: var(--edge-surface, #fff); }
.filter-grid, .form-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; align-items: end; }
.form-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.field-wrap { display: grid; gap: 6px; }
.field-wrap > span, .derived-context span, .detail-grid span, .queue-summary span, .workflow-meta span { font-size: .78rem; color: var(--edge-text-muted, #667085); }
.edge-input, .edge-button { min-height: 38px; border: 1px solid var(--edge-border, #d0d5dd); border-radius: 8px; background: var(--edge-surface, #fff); color: var(--edge-text, #101828); }
.edge-input { width: 100%; padding: 8px 10px; }
textarea.edge-input { min-height: 78px; resize: vertical; }
.edge-button { padding: 8px 13px; cursor: pointer; }
.edge-button--primary { background: var(--edge-primary, #155eef); color: #fff; border-color: var(--edge-primary, #155eef); }
.edge-button:disabled { opacity: .55; cursor: not-allowed; }
.full-width { grid-column: 1 / -1; }
.filter-search { grid-column: span 2; }
.filter-action { display: flex; justify-content: flex-end; }
.queue-summary, .derived-context, .detail-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.queue-summary > div, .derived-context > div, .detail-grid > div { display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 8px; background: var(--edge-surface-muted, #f8fafc); }
.table-wrap { overflow-x: auto; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 9px; }
.expense-table { width: 100%; border-collapse: collapse; min-width: 840px; }
.expense-table th, .expense-table td { padding: 10px 12px; border-bottom: 1px solid var(--edge-border, #e5e7eb); text-align: left; vertical-align: top; }
.expense-table th { font-size: .75rem; color: var(--edge-text-muted, #667085); background: var(--edge-surface-muted, #f8fafc); }
.expense-table td small { display: block; margin-top: 2px; color: var(--edge-text-muted, #667085); }
.expense-table .amount { text-align: right; }
.expense-row { cursor: pointer; }
.expense-row:hover { background: var(--edge-surface-muted, #f8fafc); }
.status-pill { display: inline-flex; padding: 3px 8px; border-radius: 999px; background: var(--edge-surface-muted, #f2f4f7); font-size: .76rem; }
.empty-cell, .empty-note { color: var(--edge-text-muted, #667085); }
.empty-cell { padding: 24px !important; text-align: center !important; }
.detail-stack { display: grid; gap: 16px; }
.detail-description { margin: 0; padding-top: 4px; color: var(--edge-text-muted, #667085); }
.attachment-link { word-break: break-word; }
.workflow-meta, .posting-reference { display: flex; align-items: center; gap: 8px; }
.posting-readiness { display: grid; gap: 8px; }
.posting-readiness > div { display: flex; align-items: center; gap: 8px; }
.posting-readiness p { margin: 0; white-space: pre-line; color: var(--edge-text-muted, #667085); }
.workflow-actions { justify-content: flex-start; flex-wrap: wrap; }
.workflow-actions .edge-button { display: inline-flex; align-items: center; gap: 8px; }
.workflow-actions small { opacity: .85; }
.error-banner { padding: 10px 12px; border: 1px solid var(--edge-danger, #d92d20); border-radius: 8px; color: var(--edge-danger, #b42318); background: var(--edge-danger-subtle, #fef3f2); }
.business-expense-fallback { margin: 20px; padding: 16px; border: 1px solid var(--edge-border, #d9d9d9); border-radius: 10px; display: grid; gap: 6px; }
@media (max-width: 1000px) { .filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 760px) { .business-expense-header, .section-heading { align-items: flex-start; flex-direction: column; } .filter-grid, .form-grid, .queue-summary, .derived-context, .detail-grid { grid-template-columns: 1fr; } .filter-search { grid-column: auto; } .header-actions { flex-wrap: wrap; } }
</style>
