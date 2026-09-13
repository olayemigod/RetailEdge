<template>
	<section class="expense-category-manager">
		<header class="manager-header">
			<div>
				<span class="manager-kicker">RetailEdge Setup</span>
				<h2>Expense Categories</h2>
				<p>Maintain the controlled categories used by Business Expenses, Cashier Expenses and expense reporting.</p>
			</div>
			<div class="manager-actions">
				<button type="button" class="edge-button edge-button--secondary" @click="$emit('back')">Back to Setup</button>
				<button v-if="screen === 'list' && canCreate" type="button" class="edge-button edge-button--primary" @click="openNew">Add Category</button>
			</div>
		</header>

		<div v-if="loadingContext" class="manager-state">Preparing Expense Categories…</div>
		<div v-else-if="contextError" class="manager-error">
			<span>{{ contextError }}</span>
			<button type="button" class="edge-button edge-button--secondary" @click="loadContext">Retry</button>
		</div>

		<template v-else-if="screen === 'list'">
			<section class="edge-panel">
				<div class="manager-filter-grid">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						placeholder="All permitted companies"
						:searcher="companySearch"
						@select="selectFilterCompany"
						@clear="clearFilterCompany"
					/>
					<label class="manager-field">
						<span>Status</span>
						<select v-model="filters.active_status" class="edge-input">
							<option value="All">All</option>
							<option value="Active">Active</option>
							<option value="Inactive">Inactive</option>
						</select>
					</label>
					<label class="manager-field manager-search">
						<span>Search</span>
						<input v-model="filters.search_text" class="edge-input" placeholder="Name, code or description" @keyup.enter="applyFilters" />
					</label>
					<div class="manager-filter-action">
						<button type="button" class="edge-button edge-button--primary" :disabled="listLoading" @click="applyFilters">{{ listLoading ? "Loading…" : "Apply" }}</button>
					</div>
				</div>
			</section>

			<section class="edge-panel">
				<div class="manager-summary">
					<div><span>Visible categories</span><strong>{{ Number(summary.count || 0).toLocaleString() }}</strong></div>
					<div><span>Status filter</span><strong>{{ summary.active_filter || "All" }}</strong></div>
				</div>
				<div v-if="listError" class="manager-error">{{ listError }}</div>
				<div class="manager-table-wrap">
					<table class="manager-table">
						<thead>
							<tr><th>Category</th><th>Code</th><th>Company</th><th>Expense Account</th><th>Default Cost Centre</th><th>Status</th></tr>
						</thead>
						<tbody>
							<tr v-for="row in rows" :key="row.name" class="manager-row" @click="openEdit(row.name)">
								<td><strong>{{ row.category_name || row.name }}</strong></td>
								<td>{{ row.category_code || "—" }}</td>
								<td>{{ row.company || "—" }}</td>
								<td>{{ row.expense_account || "—" }}</td>
								<td>{{ row.default_cost_center || "—" }}</td>
								<td>{{ row.is_active ? "Active" : "Inactive" }}</td>
							</tr>
							<tr v-if="!listLoading && !rows.length"><td colspan="6" class="manager-empty">No Expense Categories match the selected filters.</td></tr>
						</tbody>
					</table>
				</div>
				<div class="manager-pagination">
					<span>Page {{ pagination.page || 1 }} of {{ pagination.total_pages || 1 }}</span>
					<div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="!pagination.has_previous || listLoading" @click="goToPage((pagination.page || 1) - 1)">Previous</button>
						<button type="button" class="edge-button edge-button--secondary" :disabled="!pagination.has_next || listLoading" @click="goToPage((pagination.page || 1) + 1)">Next</button>
					</div>
				</div>
			</section>
		</template>

		<section v-else class="edge-panel">
			<div class="form-heading">
				<div>
					<h3>{{ editingName ? "Edit Expense Category" : "New Expense Category" }}</h3>
					<p v-if="editingName">Category identity remains stable; update accounting defaults, code, notes or active state here.</p>
					<p v-else>Select Company first so accounting choices show only valid records.</p>
				</div>
				<button type="button" class="edge-button edge-button--secondary" @click="returnToList">Back to Categories</button>
			</div>

			<div class="manager-form-grid">
				<label class="manager-field">
					<span>Category Name</span>
					<input v-model="form.category_name" class="edge-input" :disabled="Boolean(editingName)" required />
				</label>
				<label class="manager-field">
					<span>Category Code</span>
					<input v-model="form.category_code" class="edge-input" />
				</label>
				<EdgeLinkField
					v-model="form.company"
					label="Company"
					placeholder="Select Company"
					:searcher="companySearch"
					required
					@select="selectFormCompany"
					@clear="clearFormCompany"
				/>
				<EdgeLinkField
					v-model="form.expense_account"
					label="Expense Account"
					placeholder="Select an Expense ledger account"
					:searcher="expenseAccountSearch"
					@select="selectExpenseAccount"
					@clear="clearExpenseAccount"
				/>
				<EdgeLinkField
					v-model="form.default_cost_center"
					label="Default Cost Centre"
					placeholder="Optional"
					:searcher="costCenterSearch"
					@select="selectCostCenter"
					@clear="clearCostCenter"
				/>
				<label class="manager-check">
					<input v-model="form.is_active" type="checkbox" />
					<span>Active category</span>
				</label>
			</div>

			<label class="manager-field manager-full">
				<span>Description</span>
				<textarea v-model="form.description" class="edge-input" rows="3"></textarea>
			</label>
			<label class="manager-field manager-full">
				<span>Notes</span>
				<textarea v-model="form.notes" class="edge-input" rows="3"></textarea>
			</label>

			<div v-if="formError" class="manager-error">{{ formError }}</div>
			<div class="form-actions">
				<button type="button" class="edge-button edge-button--secondary" @click="returnToList">Cancel</button>
				<button type="button" class="edge-button edge-button--primary" :disabled="saving || (editingName && !canWrite)" @click="saveCategory">{{ saving ? "Saving…" : editingName ? "Save Changes" : "Create Category" }}</button>
			</div>
		</section>
	</section>
</template>

<script>
const EdgeLinkField = window.EdgeSuiteUI?.components?.EdgeLinkField;

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

function blankForm() {
	return {
		category_name: "",
		category_code: "",
		company: "",
		expense_account: "",
		default_cost_center: "",
		is_active: true,
		description: "",
		notes: "",
	};
}

export default {
	name: "ExpenseCategoryManager",
	components: { EdgeLinkField },
	props: {
		initialAction: { type: String, default: "list" },
		initialName: { type: String, default: "" },
	},
	emits: ["back"],
	data() {
		return {
			loadingContext: true,
			contextError: "",
			listLoading: false,
			listError: "",
			saving: false,
			formError: "",
			canCreate: false,
			canWrite: false,
			filters: { company: "", active_status: "Active", search_text: "", page_size: 25 },
			rows: [],
			summary: {},
			pagination: {},
			screen: "list",
			form: blankForm(),
			editingName: "",
			expectedModified: "",
		};
	},
	mounted() {
		this.loadContext();
	},
	methods: {
		async loadContext() {
			this.loadingContext = true;
			this.contextError = "";
			try {
				const context = await callMethod("retailedge.expense_category_setup.get_expense_category_manager_context");
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.canCreate = Boolean(context.can_create);
				this.canWrite = Boolean(context.can_write);
				if (this.initialName) await this.openEdit(this.initialName);
				else if (this.initialAction === "new" && this.canCreate) this.openNew();
				else await this.fetchList(1);
			} catch (error) {
				this.contextError = errorMessage(error, "Unable to prepare Expense Categories.");
			} finally {
				this.loadingContext = false;
			}
		},
		async fetchList(page = this.pagination.page || 1) {
			this.listLoading = true;
			this.listError = "";
			try {
				const result = await callMethod("retailedge.expense_category_setup.get_expense_categories", {
					filters: this.filters,
					page,
					page_size: this.filters.page_size || 25,
				});
				this.rows = result.rows || [];
				this.summary = result.summary || {};
				this.pagination = result.pagination || {};
			} catch (error) {
				this.rows = [];
				this.listError = errorMessage(error, "Unable to load Expense Categories.");
			} finally {
				this.listLoading = false;
			}
		},
		applyFilters() {
			this.fetchList(1);
		},
		goToPage(page) {
			if (page > 0) this.fetchList(page);
		},
		openNew() {
			if (!this.canCreate) return;
			this.form = { ...blankForm(), company: this.filters.company || "" };
			this.editingName = "";
			this.expectedModified = "";
			this.formError = "";
			this.screen = "form";
		},
		async openEdit(name) {
			if (!name) return;
			this.formError = "";
			try {
				const row = await callMethod("retailedge.expense_category_setup.get_expense_category", { name });
				this.form = {
					...blankForm(),
					category_name: row.category_name || row.name || "",
					category_code: row.category_code || "",
					company: row.company || "",
					expense_account: row.expense_account || "",
					default_cost_center: row.default_cost_center || "",
					is_active: Boolean(row.is_active),
					description: row.description || "",
					notes: row.notes || "",
				};
				this.editingName = row.name || name;
				this.expectedModified = row.modified || "";
				this.canWrite = Boolean(row.can_edit);
				this.screen = "form";
			} catch (error) {
				this.listError = errorMessage(error, "Unable to open this Expense Category.");
			}
		},
		returnToList() {
			this.screen = "list";
			this.form = blankForm();
			this.editingName = "";
			this.expectedModified = "";
			this.formError = "";
			this.fetchList();
		},
		async saveCategory() {
			if (this.saving || (this.editingName && !this.canWrite)) return;
			if (!this.form.category_name || (!this.form.company && !this.editingName)) {
				this.formError = "Category Name and Company are required.";
				return;
			}
			this.saving = true;
			this.formError = "";
			try {
				const result = await callMethod("retailedge.expense_category_setup.save_expense_category", {
					values: { ...this.form, is_active: this.form.is_active ? 1 : 0 },
					name: this.editingName || "",
					expected_modified: this.expectedModified || "",
				});
				this.editingName = result.name || this.editingName;
				this.expectedModified = result.modified || "";
				frappe.show_alert?.({ message: this.editingName ? "Expense Category saved" : "Expense Category created", indicator: "green" });
				this.returnToList();
			} catch (error) {
				this.formError = errorMessage(error, "Unable to save Expense Category.");
			} finally {
				this.saving = false;
			}
		},
		async search(kind, txt, company = this.form.company || this.filters.company) {
			const result = await callMethod("retailedge.expense_category_setup.search_expense_category_manager_options", {
				kind,
				txt: txt || "",
				company: company || "",
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) {
			return this.search("company", txt, "");
		},
		expenseAccountSearch(txt) {
			if (!this.form.company) return [];
			return this.search("expense_account", txt, this.form.company);
		},
		costCenterSearch(txt) {
			if (!this.form.company) return [];
			return this.search("cost_center", txt, this.form.company);
		},
		selectFilterCompany(option) {
			this.filters.company = option.value || "";
		},
		clearFilterCompany() {
			this.filters.company = "";
		},
		selectFormCompany(option) {
			const next = option.value || "";
			if (this.form.company !== next) {
				this.form.expense_account = "";
				this.form.default_cost_center = "";
			}
			this.form.company = next;
		},
		clearFormCompany() {
			this.form.company = "";
			this.form.expense_account = "";
			this.form.default_cost_center = "";
		},
		selectExpenseAccount(option) {
			this.form.expense_account = option.value || "";
		},
		clearExpenseAccount() {
			this.form.expense_account = "";
		},
		selectCostCenter(option) {
			this.form.default_cost_center = option.value || "";
		},
		clearCostCenter() {
			this.form.default_cost_center = "";
		},
	},
};
</script>

<style scoped>
.expense-category-manager { display: grid; gap: 1rem; }
.manager-header, .form-heading, .manager-pagination, .manager-actions, .form-actions { display: flex; justify-content: space-between; gap: .75rem; align-items: center; flex-wrap: wrap; }
.manager-header h2, .form-heading h3 { margin: .15rem 0 .35rem; }
.manager-header p, .form-heading p { margin: 0; color: var(--text-muted); }
.manager-kicker { color: var(--text-muted); font-size: .78rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
.manager-filter-grid { display: grid; grid-template-columns: 1.1fr .7fr 1.2fr auto; gap: .75rem; align-items: end; }
.manager-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .9rem; margin-top: 1rem; }
.manager-field { display: flex; flex-direction: column; gap: .35rem; min-width: 0; }
.manager-field > span { font-size: .8rem; font-weight: 600; color: var(--text-muted); }
.manager-full { margin-top: .9rem; }
.manager-check { display: flex; gap: .55rem; align-items: center; align-self: end; min-height: 38px; }
.manager-table-wrap { overflow-x: auto; margin-top: .75rem; }
.manager-table { width: 100%; border-collapse: collapse; }
.manager-table th, .manager-table td { padding: .75rem; text-align: left; border-bottom: 1px solid var(--edge-border-color, var(--border-color)); vertical-align: top; }
.manager-table th { font-size: .78rem; color: var(--text-muted); }
.manager-row { cursor: pointer; }
.manager-row:hover { background: var(--control-bg); }
.manager-summary { display: flex; gap: 1.5rem; flex-wrap: wrap; }
.manager-summary > div { display: grid; gap: .15rem; }
.manager-summary span { color: var(--text-muted); font-size: .78rem; }
.manager-summary strong { font-size: 1.1rem; }
.manager-pagination { margin-top: .9rem; }
.manager-pagination > div { display: flex; gap: .5rem; }
.manager-error { padding: .75rem; border: 1px solid var(--red-300, var(--edge-border-color)); border-radius: .5rem; color: var(--red-700, var(--text-color)); }
.manager-state, .manager-empty { padding: 1rem; color: var(--text-muted); text-align: center; }
.edge-input { min-height: 38px; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: .5rem; background: var(--edge-surface, var(--card-bg)); color: var(--text-color); padding: .5rem .65rem; }
textarea.edge-input { min-height: 76px; resize: vertical; }
.form-actions { margin-top: 1rem; justify-content: flex-end; }
@media (max-width: 900px) { .manager-filter-grid, .manager-form-grid { grid-template-columns: 1fr 1fr; } }
@media (max-width: 620px) { .manager-filter-grid, .manager-form-grid { grid-template-columns: 1fr; } }
</style>
