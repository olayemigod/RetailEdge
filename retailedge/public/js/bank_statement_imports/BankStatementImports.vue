<template>
	<div v-if="!edgeUIValid" class="statement-fallback">
		<strong>Bank Statement Imports could not start.</strong>
		<span>Required EdgeSuite components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Bank Statement Imports"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/bank-statement-imports"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<div class="statement-page">
			<header class="statement-header">
				<div>
					<p class="eyebrow">Money & Banking</p>
					<h2>Bank Statement Imports</h2>
					<p>Upload, review and convert statement rows into governed ERPNext Bank Transactions without leaving EdgeSuite.</p>
				</div>
				<div class="statement-header-actions">
					<button v-if="canUseNativeDesk" type="button" class="edge-button" @click="openNativeList">Advanced: ERPNext List</button>
					<button v-if="canCreate" type="button" class="edge-button edge-button--primary" @click="openNew">New Statement Import</button>
				</div>
			</header>

			<EdgeLoadingState v-if="loadingContext" message="Preparing statement imports..." :skeleton="true" />
			<EdgeErrorState v-else-if="contextError" title="Bank Statement Imports unavailable" :message="contextError" @retry="loadContext" />

			<template v-else>
				<section class="edge-card">
					<div class="statement-filter-grid">
						<EdgeLinkField v-model="filters.company" label="Company" placeholder="All permitted companies" :searcher="companySearch" @select="selectFilterCompany" @clear="clearFilterCompany" />
						<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="filterBranchSearch" @select="selectFilterBranch" @clear="clearFilterBranch" />
						<EdgeDropdown v-model="filters.status" label="Status" :options="['All', ...statuses]" />
						<label class="statement-field">
							<span>Search</span>
							<input v-model="filters.search_text" class="edge-input" placeholder="Import, bank account or category" @keyup.enter="applyFilters" />
						</label>
						<div class="statement-filter-action">
							<button type="button" class="edge-button edge-button--primary" :disabled="listLoading" @click="applyFilters">{{ listLoading ? "Loading…" : "Apply" }}</button>
						</div>
					</div>
				</section>

				<section class="edge-card">
					<div class="section-heading">
						<div>
							<h3>Statement import queue</h3>
							<p>The import document remains the audit record; accounting is created only through ERPNext Bank Transactions.</p>
						</div>
						<span>{{ rows.length }} shown</span>
					</div>
					<div v-if="listError" class="statement-error">{{ listError }}</div>
					<div class="statement-table-wrap">
						<table class="statement-table">
							<thead>
								<tr><th>Statement</th><th>Date</th><th>Bank Account</th><th>Branch</th><th>Status</th><th>Rows</th><th>Duplicates</th><th>Bank Transactions</th></tr>
							</thead>
							<tbody>
								<tr v-for="row in rows" :key="row.name" class="statement-row" @click="openDetail(row.name)">
									<td><strong>{{ row.name }}</strong><small>{{ row.payment_category || row.statement_type || "Statement" }}</small></td>
									<td>{{ row.statement_date || "—" }}</td>
									<td>{{ row.bank_account || "—" }}</td>
									<td>{{ row.branch || "All Branches" }}</td>
									<td><span class="statement-badge">{{ row.import_status || "Draft" }}</span></td>
									<td>{{ Number(row.total_rows || row.imported_row_count || 0).toLocaleString() }}</td>
									<td>{{ Number(row.duplicate_suspected_count || 0).toLocaleString() }}</td>
									<td>{{ Number(row.linked_bank_transactions || 0).toLocaleString() }}</td>
								</tr>
								<tr v-if="!listLoading && !rows.length"><td colspan="8" class="statement-empty">No statement imports match the current filters.</td></tr>
							</tbody>
						</table>
					</div>
					<div class="statement-pagination">
						<span>Page {{ page }}</span>
						<div>
							<button type="button" class="edge-button" :disabled="page <= 1 || listLoading" @click="goPage(page - 1)">Previous</button>
							<button type="button" class="edge-button" :disabled="!hasMore || listLoading" @click="goPage(page + 1)">Next</button>
						</div>
					</div>
				</section>
			</template>
		</div>

		<EdgeModal :open="createOpen" title="New Bank Statement Import" subtitle="Create the governed import record first, then attach a CSV or XLSX statement." size="lg" @close="closeCreate">
			<div class="statement-form-grid">
				<EdgeLinkField v-model="form.company" label="Company" placeholder="Select Company" :searcher="companySearch" required @select="selectFormCompany" @clear="clearFormCompany" />
				<EdgeLinkField v-model="form.branch" label="Branch" placeholder="Select Branch when required" :searcher="formBranchSearch" @select="selectFormBranch" @clear="clearFormBranch" />
				<label class="statement-field"><span>Statement Date</span><input v-model="form.statement_date" class="edge-input" type="date" required /></label>
				<EdgeLinkField v-model="form.bank_account" label="Bank Account" placeholder="Select permitted Bank Account" :searcher="bankAccountSearch" required @select="selectBankAccount" @clear="clearBankAccount" />
				<EdgeDropdown v-model="form.statement_type" label="Statement Type" :options="statementTypes" />
				<EdgeDropdown v-model="form.payment_category" label="Payment Category" :options="paymentCategories" />
				<EdgeLinkField v-model="form.mapping_template" label="Mapping Template" placeholder="Optional mapping template" :searcher="mappingTemplateSearch" @select="selectMappingTemplate" @clear="clearMappingTemplate" />
			</div>
			<div v-if="formError" class="statement-error">{{ formError }}</div>
			<template #footer>
				<button type="button" class="edge-button" :disabled="saving" @click="closeCreate">Cancel</button>
				<button type="button" class="edge-button edge-button--primary" :disabled="saving" @click="createImport">{{ saving ? "Creating…" : "Create & Upload Statement" }}</button>
			</template>
		</EdgeModal>

		<EdgeModal :open="detailOpen" :title="detail?.document?.name || 'Bank Statement Import'" :subtitle="detailSubtitle" size="xl" @close="closeDetail">
			<EdgeLoadingState v-if="detailLoading" message="Loading statement import..." />
			<EdgeErrorState v-else-if="detailError" title="Statement Import unavailable" :message="detailError" @retry="reloadDetail" />
			<template v-else-if="detail?.document">
				<div class="statement-detail-summary">
					<div><span>Company</span><strong>{{ detail.document.company }}</strong></div>
					<div><span>Branch</span><strong>{{ detail.document.branch || "All Branches" }}</strong></div>
					<div><span>Bank Account</span><strong>{{ detail.document.bank_account }}</strong></div>
					<div><span>Status</span><strong>{{ detail.document.import_status || "Draft" }}</strong></div>
					<div><span>Total Rows</span><strong>{{ Number(detail.document.total_rows || 0).toLocaleString() }}</strong></div>
					<div><span>Ready</span><strong>{{ Number(detail.document.ready_rows || 0).toLocaleString() }}</strong></div>
					<div><span>Possible Duplicates</span><strong>{{ Number(detail.document.duplicate_suspected_count || 0).toLocaleString() }}</strong></div>
					<div><span>Bank Transactions</span><strong>{{ Number(detail.document.linked_bank_transactions || 0).toLocaleString() }}</strong></div>
				</div>

				<section class="statement-attachment">
					<div>
						<strong>Statement file</strong>
						<span>{{ detail.document.attachment || "No CSV/XLSX attached yet." }}</span>
					</div>
					<button v-if="detail.can_write" type="button" class="edge-button" :disabled="actionBusy" @click="uploadStatement">{{ detail.document.attachment ? "Replace File" : "Upload File" }}</button>
				</section>

				<div v-if="actionError" class="statement-error">{{ actionError }}</div>
				<div class="statement-actions">
					<button type="button" class="edge-button" :disabled="actionBusy || !detail.document.attachment" @click="runAction('preview-rows')">Preview Statement Rows</button>
					<button v-if="detail.can_write" type="button" class="edge-button" :disabled="actionBusy || !detail.document.attachment" @click="confirmImportRows">Import Statement Rows</button>
					<button type="button" class="edge-button" :disabled="actionBusy || !detail.document.imported_row_count" @click="runAction('preview-bank')">Preview Bank Transactions</button>
					<button v-if="detail.can_write" type="button" class="edge-button edge-button--primary" :disabled="actionBusy || !detail.document.imported_row_count" @click="confirmCreateBankTransactions">Create Bank Transactions</button>
					<button type="button" class="edge-button" :disabled="actionBusy || !detail.document.duplicate_suspected_count" @click="loadDuplicates">Review Possible Duplicates</button>
				</div>

				<div class="statement-detail-table-wrap">
					<table class="statement-table statement-detail-table">
						<thead><tr><th>#</th><th>Date</th><th>Reference</th><th>Amount</th><th>Direction</th><th>Duplicate</th><th>Import</th><th>Bank Transaction</th></tr></thead>
						<tbody>
							<tr v-for="row in detail.rows || []" :key="row.name">
								<td>{{ row.idx }}</td><td>{{ row.transaction_date || "—" }}</td><td>{{ row.reference || "—" }}</td>
								<td>{{ formatAmount(row.amount) }}</td><td>{{ row.transaction_direction || "—" }}</td>
								<td>{{ row.duplicate_status || "—" }}</td><td>{{ row.import_status || "—" }}</td>
								<td>{{ row.bank_transaction || row.existing_bank_transaction || "—" }}</td>
							</tr>
							<tr v-if="!(detail.rows || []).length"><td colspan="8" class="statement-empty">No imported statement rows yet. Preview and import the attached file first.</td></tr>
						</tbody>
					</table>
					<p v-if="detail.rows_truncated" class="statement-hint">Showing the first 100 statement rows.</p>
				</div>
			</template>
			<template #footer>
				<button v-if="canUseNativeDesk && detail?.document?.name" type="button" class="edge-button" @click="openNativeRecord">Advanced: Open Full Record</button>
				<button type="button" class="edge-button edge-button--primary" @click="closeDetail">Close</button>
			</template>
		</EdgeModal>

		<EdgeModal :open="resultOpen" :title="resultTitle || 'Statement Action Result'" size="lg" @close="closeResult">
			<div class="statement-result-grid">
				<div v-for="metric in resultMetrics" :key="metric.label"><span>{{ metric.label }}</span><strong>{{ metric.value }}</strong></div>
			</div>
			<div v-if="actionResult?.errors?.length" class="statement-error-list">
				<strong>Rows needing attention</strong>
				<ul><li v-for="error in actionResult.errors.slice(0, 20)" :key="error">{{ error }}</li></ul>
			</div>
			<div v-if="actionResult?.rows?.length" class="statement-preview">
				<table class="statement-table"><thead><tr><th>Row</th><th>Status</th><th>Reference</th><th>Amount</th></tr></thead>
					<tbody><tr v-for="(row, index) in actionResult.rows.slice(0, 10)" :key="row.name || row.row_index || index"><td>{{ row.row_index || index + 1 }}</td><td>{{ row.status || row.import_status || row.duplicate_status || "Ready" }}</td><td>{{ row.reference || "—" }}</td><td>{{ formatAmount(row.amount || row.normalized_amount) }}</td></tr></tbody>
				</table>
			</div>
			<template #footer><button type="button" class="edge-button edge-button--primary" @click="closeResult">Close</button></template>
		</EdgeModal>

		<EdgeModal :open="duplicatesOpen" title="Review Possible Duplicates" subtitle="A possible duplicate is informational until a reviewer explicitly accepts it." size="xl" @close="closeDuplicates">
			<div v-if="duplicatesError" class="statement-error">{{ duplicatesError }}</div>
			<div v-if="duplicatesLoading" class="statement-state">Loading possible duplicates…</div>
			<div v-else class="duplicate-list">
				<article v-for="row in duplicates" :key="row.name" class="duplicate-card">
					<div class="duplicate-card-head"><strong>{{ row.name }}</strong><span>{{ row.duplicate_status || "Possible Duplicate" }}</span></div>
					<p>{{ row.transaction_date || "—" }} · {{ formatAmount(row.amount || row.normalized_amount) }} · {{ row.reference || "No reference" }}</p>
					<p>{{ row.duplicate_reason || "Review the candidate before accepting." }}</p>
					<label class="statement-field"><span>Acceptance Note</span><input v-model="duplicateNotes[row.name]" class="edge-input" placeholder="Why is this row valid?" /></label>
					<button v-if="detail?.can_write" type="button" class="edge-button edge-button--primary" :disabled="actionBusy || !String(duplicateNotes[row.name] || '').trim()" @click="acceptDuplicate(row)">Accept Selected Row</button>
				</article>
				<div v-if="!duplicates.length" class="statement-empty">No possible duplicate rows require review.</div>
			</div>
			<template #footer><button type="button" class="edge-button edge-button--primary" @click="closeDuplicates">Close</button></template>
		</EdgeModal>
	</EdgeAppShell>
</template>

<script>
import { confirmAboveEdgeModal } from "../retailedge_business_hub/guidedEntryUtils";

const WORKSPACE = "retailedge.payment_statement_import_workspace";
const runtime = typeof window !== "undefined" ? (window.EdgeSuiteUI?.components || {}) : {};

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		type,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}
function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || error?.message || fallback;
}
function optionValue(option) {
	return typeof option === "string" ? option : (option?.value || option?.name || "");
}
function blankForm(defaults = {}) {
	return {
		company: defaults.company || "",
		branch: defaults.branch || "",
		statement_date: defaults.statement_date || "",
		bank_account: "",
		statement_type: defaults.statement_type || "Bank Transfer",
		payment_category: defaults.payment_category || "Bank Transfer",
		mapping_template: "",
	};
}

export default {
	name: "RetailEdgeBankStatementImports",
	components: {
		EdgeAppShell: runtime.EdgeAppShell,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeDropdown: runtime.EdgeDropdown,
		EdgeModal: runtime.EdgeModal,
	},
	data() {
		return {
			edgeUIValid: Boolean(runtime.EdgeAppShell && runtime.EdgeModal && runtime.EdgeLinkField && runtime.EdgeDropdown),
			tenantName: "", branchName: "", userName: "", menuItems: [], canUseNativeDesk: false,
			loadingContext: true, contextError: "", context: {}, canCreate: false,
			statuses: [], statementTypes: [], paymentCategories: [],
			filters: { company: "", branch: "", status: "All", search_text: "" },
			rows: [], listLoading: false, listError: "", page: 1, pageSize: 25, hasMore: false,
			createOpen: false, form: blankForm(), formError: "", saving: false,
			detailOpen: false, detailLoading: false, detailError: "", detail: null,
			actionBusy: false, actionError: "", actionResult: null, resultOpen: false, resultTitle: "",
			duplicatesOpen: false, duplicatesLoading: false, duplicatesError: "", duplicates: [], duplicateNotes: {},
		};
	},
	computed: {
		detailSubtitle() {
			const doc = this.detail?.document;
			if (!doc) return "Review statement import";
			return [doc.company, doc.branch || "All Branches", doc.statement_date].filter(Boolean).join(" · ");
		},
		resultMetrics() {
			const result = this.actionResult || {};
			const candidates = [
				["Total Rows", result.total_rows ?? result.row_count],
				["Ready", result.ready_rows],
				["Imported", result.imported_rows ?? result.imported_row_count],
				["Duplicates", result.duplicate_rows ?? result.duplicate_suspected_count],
				["Skipped", result.skipped_rows],
				["Failed", result.failed_rows],
				["Bank Transactions", result.linked_bank_transactions ?? result.linked_bank_transaction_count],
			];
			return candidates.filter(([, value]) => value !== undefined && value !== null).map(([label, value]) => ({ label, value: Number.isFinite(Number(value)) ? Number(value).toLocaleString() : String(value) }));
		},
	},
	mounted() {
		this._pageShow = () => this.fetchList();
		window.addEventListener("retailedge-bank-statement-imports-page-show", this._pageShow);
		this.loadContext();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-bank-statement-imports-page-show", this._pageShow);
	},
	methods: {
		async loadContext() {
			this.loadingContext = true; this.contextError = "";
			try {
				const [context, navigation] = await Promise.all([
					callMethod(`${WORKSPACE}.get_bank_statement_import_workspace_context`),
					typeof window.retailedgeGetBusinessHubContext === "function"
						? window.retailedgeGetBusinessHubContext()
						: callMethod("retailedge.master_experience.get_retailedge_business_hub_context"),
				]);
				this.context = context || {};
				this.canCreate = Boolean(context?.can_create);
				this.statuses = context?.statuses || [];
				this.statementTypes = context?.statement_types || [];
				this.paymentCategories = context?.payment_categories || [];
				this.filters.company = context?.defaults?.company || "";
				this.filters.branch = context?.defaults?.branch || "";
				this.form = blankForm(context?.defaults || {});
				this.tenantName = navigation?.default_values?.company || this.filters.company || "";
				this.branchName = navigation?.default_values?.branch || this.filters.branch || "";
				this.userName = navigation?.context?.user_name || frappe.session?.user || "";
				this.menuItems = this.mapNavigationGroups(navigation?.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);
				await this.fetchList();
			} catch (error) {
				this.contextError = errorMessage(error, "Unable to prepare Bank Statement Imports.");
			} finally { this.loadingContext = false; }
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				label: group.label,
				items: (group.items || []).map((item) => ({
					label: item.label, icon: item.icon, target: item.target, target_type: item.target_type,
					route: item.target_type === "Page" ? `/app/${item.target}` : `/${String(item.target_type || "").toLowerCase()}/${item.target}`,
				})),
			}));
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async fetchList() {
			if (this.loadingContext) return;
			this.listLoading = true; this.listError = "";
			try {
				const result = await callMethod(`${WORKSPACE}.get_bank_statement_imports`, {
					company: this.filters.company || "", branch: this.filters.branch || "", status: this.filters.status || "All",
					search_text: this.filters.search_text || "", page: this.page, page_size: this.pageSize,
				});
				this.rows = result?.rows || []; this.hasMore = Boolean(result?.has_more);
			} catch (error) { this.listError = errorMessage(error, "Unable to load Bank Statement Imports."); }
			finally { this.listLoading = false; }
		},
		applyFilters() { this.page = 1; this.fetchList(); },
		goPage(page) { this.page = Math.max(1, Number(page || 1)); this.fetchList(); },
		async search(fieldname, txt, company = this.form.company || this.filters.company, branch = this.form.branch || this.filters.branch) {
			return await callMethod(`${WORKSPACE}.search_bank_statement_import_options`, { fieldname, txt: txt || "", company: company || "", branch: branch || "", limit: 20 });
		},
		companySearch(txt) { return this.search("company", txt, "", ""); },
		filterBranchSearch(txt) { if (!this.filters.company) return []; return this.search("branch", txt, this.filters.company, this.filters.branch); },
		formBranchSearch(txt) { if (!this.form.company) return []; return this.search("branch", txt, this.form.company, this.form.branch); },
		bankAccountSearch(txt) { if (!this.form.company) return []; return this.search("bank_account", txt, this.form.company, this.form.branch); },
		mappingTemplateSearch(txt) { if (!this.form.company) return []; return this.search("mapping_template", txt, this.form.company, this.form.branch); },
		selectFilterCompany(option) { this.filters.company = optionValue(option); this.filters.branch = ""; this.applyFilters(); },
		clearFilterCompany() { this.filters.company = ""; this.filters.branch = ""; this.applyFilters(); },
		selectFilterBranch(option) { this.filters.branch = optionValue(option); this.applyFilters(); },
		clearFilterBranch() { this.filters.branch = ""; this.applyFilters(); },
		selectFormCompany(option) { this.form.company = optionValue(option); this.form.branch = ""; this.form.bank_account = ""; this.form.mapping_template = ""; },
		clearFormCompany() { this.form.company = ""; this.form.branch = ""; this.form.bank_account = ""; this.form.mapping_template = ""; },
		selectFormBranch(option) { this.form.branch = optionValue(option); this.form.bank_account = ""; },
		clearFormBranch() { this.form.branch = ""; this.form.bank_account = ""; },
		selectBankAccount(option) { this.form.bank_account = optionValue(option); },
		clearBankAccount() { this.form.bank_account = ""; },
		selectMappingTemplate(option) { this.form.mapping_template = optionValue(option); },
		clearMappingTemplate() { this.form.mapping_template = ""; },
		openNew() { this.form = blankForm(this.context?.defaults || {}); this.formError = ""; this.createOpen = true; },
		closeCreate() { if (!this.saving) this.createOpen = false; },
		async createImport() {
			if (this.saving) return;
			if (!this.form.company || !this.form.statement_date || !this.form.bank_account || !this.form.payment_category) {
				this.formError = "Company, Statement Date, Bank Account and Payment Category are required."; return;
			}
			this.saving = true; this.formError = "";
			try {
				const result = await callMethod(`${WORKSPACE}.create_bank_statement_import`, { values: { ...this.form } }, "POST");
				this.createOpen = false;
				this.detail = result; this.detailOpen = true;
				await this.fetchList();
				this.uploadStatement();
			} catch (error) { this.formError = errorMessage(error, "Unable to create Bank Statement Import."); }
			finally { this.saving = false; }
		},
		async openDetail(name) {
			this.detailOpen = true; this.detailLoading = true; this.detailError = ""; this.detail = null;
			try { this.detail = await callMethod(`${WORKSPACE}.get_bank_statement_import_detail`, { name }); }
			catch (error) { this.detailError = errorMessage(error, "Unable to load Bank Statement Import."); }
			finally { this.detailLoading = false; }
		},
		async reloadDetail() {
			const name = this.detail?.document?.name;
			if (name) await this.openDetail(name);
		},
		closeDetail() { if (!this.actionBusy) { this.detailOpen = false; this.detail = null; this.actionError = ""; } },
		uploadStatement() {
			const name = this.detail?.document?.name;
			if (!name || !this.detail?.can_write || this.actionBusy) return;
			if (!frappe.ui?.FileUploader) {
				this.actionError = "Frappe File Uploader is unavailable."; return;
			}
			new frappe.ui.FileUploader({
				doctype: "RetailEdge Payment Statement Import",
				docname: name,
				allow_multiple: false,
				restrictions: { allowed_file_types: [".csv", ".xlsx"] },
				on_success: async (file) => {
					const fileUrl = file?.file_url || file?.fileUrl || "";
					if (!fileUrl) { this.actionError = "Uploaded file URL was not returned."; return; }
					this.actionBusy = true; this.actionError = "";
					try {
						this.detail = await callMethod(`${WORKSPACE}.set_bank_statement_import_attachment`, { name, file_url: fileUrl }, "POST");
						await this.fetchList();
					} catch (error) { this.actionError = errorMessage(error, "Unable to attach the uploaded statement."); }
					finally { this.actionBusy = false; }
				},
			});
		},
		async runAction(action) {
			if (!this.detail?.document?.name || this.actionBusy) return;
			this.actionBusy = true; this.actionError = "";
			try {
				let result;
				const name = this.detail.document.name;
				if (action === "preview-rows") result = await callMethod(`${WORKSPACE}.preview_statement_rows`, { name });
				else if (action === "import-rows") result = await callMethod(`${WORKSPACE}.import_statement_rows`, { name, replace_rows: 1 }, "POST");
				else if (action === "preview-bank") result = await callMethod(`${WORKSPACE}.preview_statement_bank_transactions`, { name });
				else if (action === "create-bank") result = await callMethod(`${WORKSPACE}.create_statement_bank_transactions`, { name }, "POST");
				else return;
				this.actionResult = result || {}; this.resultTitle = ({
					"preview-rows": "Statement Row Preview", "import-rows": "Statement Rows Imported",
					"preview-bank": "Bank Transaction Preview", "create-bank": "Bank Transaction Import Summary",
				})[action] || "Statement Action Result";
				this.resultOpen = true;
				this.detail = await callMethod(`${WORKSPACE}.get_bank_statement_import_detail`, { name });
				await this.fetchList();
			} catch (error) { this.actionError = errorMessage(error, "Statement action failed."); }
			finally { this.actionBusy = false; }
		},
		confirmImportRows() { confirmAboveEdgeModal("Import statement rows from the attached file?", () => this.runAction("import-rows")); },
		confirmCreateBankTransactions() { confirmAboveEdgeModal("Create or link ERPNext Bank Transactions for valid statement rows?", () => this.runAction("create-bank")); },
		closeResult() { this.resultOpen = false; this.actionResult = null; },
		async loadDuplicates() {
			const name = this.detail?.document?.name; if (!name) return;
			this.duplicatesOpen = true; this.duplicatesLoading = true; this.duplicatesError = "";
			try {
				const result = await callMethod(`${WORKSPACE}.get_statement_possible_duplicates`, { name });
				this.duplicates = Array.isArray(result) ? result : (result?.rows || []);
				this.duplicateNotes = Object.fromEntries(this.duplicates.map((row) => [row.name, ""]));
			} catch (error) { this.duplicatesError = errorMessage(error, "Unable to load possible duplicates."); }
			finally { this.duplicatesLoading = false; }
		},
		closeDuplicates() { if (!this.actionBusy) this.duplicatesOpen = false; },
		async acceptDuplicate(row) {
			const note = String(this.duplicateNotes[row.name] || "").trim();
			if (!row?.name || !note || this.actionBusy) return;
			this.actionBusy = true; this.duplicatesError = "";
			try {
				const result = await callMethod(`${WORKSPACE}.accept_statement_possible_duplicate`, { row_name: row.name, acceptance_note: note }, "POST");
				this.actionResult = result || {}; this.resultTitle = "Possible Duplicate Accepted"; this.resultOpen = true;
				await this.loadDuplicates();
				this.detail = await callMethod(`${WORKSPACE}.get_bank_statement_import_detail`, { name: this.detail.document.name });
				await this.fetchList();
			} catch (error) { this.duplicatesError = errorMessage(error, "Unable to accept this possible duplicate."); }
			finally { this.actionBusy = false; }
		},
		formatAmount(value) { const number = Number(value || 0); return Number.isFinite(number) ? number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—"; },
		openNativeList() { if (this.canUseNativeDesk) frappe.set_route("List", "RetailEdge Payment Statement Import"); },
		openNativeRecord() { if (this.canUseNativeDesk && this.detail?.document?.name) frappe.set_route("Form", "RetailEdge Payment Statement Import", this.detail.document.name); },
	},
};
</script>

<style scoped>
.statement-page{display:grid;gap:1rem;padding:1rem}.statement-header,.section-heading,.statement-attachment,.duplicate-card-head{display:flex;align-items:flex-start;justify-content:space-between;gap:1rem}.statement-header h2,.section-heading h3{margin:.1rem 0}.statement-header p,.section-heading p{margin:.2rem 0;color:var(--text-muted)}.eyebrow{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em}.statement-header-actions,.statement-actions,.statement-pagination>div{display:flex;gap:.55rem;flex-wrap:wrap}.edge-card{padding:1rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.75rem;background:var(--edge-surface,var(--card-bg,#fff))}.statement-filter-grid,.statement-form-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.75rem;align-items:end}.statement-filter-action{display:flex;align-items:end}.statement-field{display:grid;gap:.35rem}.statement-field>span{font-size:.78rem;color:var(--text-muted)}.edge-input{width:100%;min-height:2.35rem;padding:.45rem .65rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.45rem;background:var(--edge-surface,var(--control-bg,#fff));color:inherit}.statement-table-wrap,.statement-detail-table-wrap{overflow:auto}.statement-table{width:100%;border-collapse:collapse;font-size:.82rem}.statement-table th,.statement-table td{padding:.7rem;border-bottom:1px solid var(--edge-border-color,var(--border-color));text-align:left;vertical-align:top;white-space:nowrap}.statement-table th{font-size:.72rem;color:var(--text-muted);text-transform:uppercase}.statement-row{cursor:pointer}.statement-row:hover{background:var(--edge-surface-subtle,var(--subtle-fg,#f8fafc))}.statement-row td:first-child{display:grid;gap:.15rem}.statement-row small{color:var(--text-muted)}.statement-badge{padding:.2rem .45rem;border-radius:999px;background:var(--edge-surface-subtle,var(--subtle-fg,#eef2f6))}.statement-empty,.statement-state{padding:1.4rem;text-align:center;color:var(--text-muted)}.statement-pagination{display:flex;align-items:center;justify-content:space-between;gap:1rem;padding-top:.75rem}.statement-error{padding:.7rem;border:1px solid var(--red-400,#f04438);border-radius:.5rem;background:var(--red-50,#fef3f2);color:var(--red-700,#b42318)}.statement-detail-summary,.statement-result-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.7rem}.statement-detail-summary>div,.statement-result-grid>div{display:grid;gap:.2rem;padding:.7rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.55rem;background:var(--edge-surface-subtle,var(--subtle-fg,#f8fafc))}.statement-detail-summary span,.statement-result-grid span{font-size:.72rem;color:var(--text-muted)}.statement-attachment{margin:.8rem 0;padding:.75rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.55rem}.statement-attachment>div{display:grid;gap:.2rem}.statement-attachment span,.statement-hint{font-size:.76rem;color:var(--text-muted)}.statement-actions{margin:.8rem 0}.statement-error-list{margin-top:.8rem}.duplicate-list{display:grid;gap:.75rem}.duplicate-card{display:grid;gap:.55rem;padding:.8rem;border:1px solid var(--edge-border-color,var(--border-color));border-radius:.6rem}.duplicate-card p{margin:0;color:var(--text-muted)}.statement-fallback{display:grid;gap:.4rem;padding:1rem}.statement-preview{margin-top:.8rem;overflow:auto}@media(max-width:960px){.statement-filter-grid,.statement-form-grid,.statement-detail-summary,.statement-result-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:620px){.statement-header,.section-heading,.statement-attachment,.statement-pagination{flex-direction:column;align-items:stretch}.statement-filter-grid,.statement-form-grid,.statement-detail-summary,.statement-result-grid{grid-template-columns:1fr}}
</style>
