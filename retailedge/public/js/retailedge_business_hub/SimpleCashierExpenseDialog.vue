<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Record Cashier Expense'"
		:subtitle="formContext.subtitle || 'Record a controlled cashier expense for the current operating context.'"
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-expense-state">
			<EdgeLoadingState message="Preparing cashier expense..." :skeleton="true" />
		</div>

		<div v-else-if="loadError" class="guided-expense-state">
			<EdgeErrorState
				title="Cashier Expense unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<form v-else class="guided-expense-form" @submit.prevent="saveDraft">
			<div class="guided-expense-context">
				<div>
					<span>Cashier</span>
					<strong>{{ businessContext.cashier || 'Not resolved' }}</strong>
				</div>
				<div>
					<span>Company</span>
					<strong>{{ businessContext.company || 'Not resolved' }}</strong>
				</div>
				<div v-if="businessContext.branch">
					<span>Branch</span>
					<strong>{{ businessContext.branch }}</strong>
				</div>
				<div v-if="businessContext.opening_shift">
					<span>Open Shift</span>
					<strong>{{ businessContext.opening_shift }}</strong>
				</div>
			</div>

			<div v-if="blockingReasons.length" class="guided-expense-block" role="alert">
				<strong>Expense cannot be saved yet.</strong>
				<ul>
					<li v-for="reason in blockingReasons" :key="reason">{{ reason }}</li>
				</ul>
			</div>

			<div v-else-if="businessContext.cash_control_message" class="guided-expense-note">
				{{ businessContext.cash_control_message }}
			</div>

			<div v-if="saveError" class="guided-expense-error" role="alert">
				{{ saveError }}
			</div>

			<div class="guided-expense-grid">
				<EdgeLinkField
					:modelValue="values.expense_category"
					label="Expense Category"
					placeholder="Search expense category"
					:required="true"
					:searcher="searchCategory"
					:context="categoryContext"
					@update:modelValue="setExpenseCategory"
				/>

				<label class="guided-field">
					<span>Amount <b>*</b></span>
					<input
						v-model.number="values.amount"
						class="form-control"
						type="number"
						min="0.01"
						step="0.01"
						required
					/>
				</label>

				<label v-if="allowExpenseDateEdit" class="guided-field">
					<span>Expense Date <b>*</b></span>
					<input v-model="values.expense_date" class="form-control" type="date" required />
				</label>
			</div>

			<div v-if="businessContext.opening_shift" class="guided-cash-summary">
				<div>
					<span>Opening Cash</span>
					<strong>{{ formatAmount(businessContext.opening_cash) }}</strong>
				</div>
				<div>
					<span>Cash Sales</span>
					<strong>{{ formatAmount(businessContext.cash_sales) }}</strong>
				</div>
				<div>
					<span>Prior Expenses</span>
					<strong>{{ formatAmount(businessContext.prior_expenses) }}</strong>
				</div>
				<div>
					<span>Available Before</span>
					<strong>{{ formatAmount(businessContext.available_cash) }}</strong>
				</div>
				<div :class="{ 'has-warning': projectedCash < 0 }">
					<span>Expected After</span>
					<strong>{{ formatAmount(projectedCash) }}</strong>
				</div>
			</div>

			<label class="guided-field guided-field--wide">
				<span>Description</span>
				<textarea
					v-model="values.description"
					class="form-control"
					rows="3"
					placeholder="What was this expense for?"
				></textarea>
			</label>

			<p class="guided-expense-hint">
				The expense account, cost centre and cash account are resolved from the selected category
				and current cashier context. Receipt upload and review details remain available in the full form.
			</p>
		</form>

		<template #footer>
			<div class="guided-expense-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">
					Open Full Form
				</button>
				<div class="guided-expense-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">
						Cancel
					</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading || !ready || projectedCash < 0"
						@click="saveDraft"
					>
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const CONTEXT_METHOD = "retailedge.guided_cashier_expense.get_guided_cashier_expense_context";
const SEARCH_METHOD = "retailedge.guided_cashier_expense.search_guided_expense_categories";
const CREATE_METHOD = "retailedge.guided_cashier_expense.create_guided_cashier_expense_draft";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		expense_category: "",
		amount: "",
		description: "",
		expense_date: "",
	};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	if (error?.message) return error.message;
	if (error?.exc_type) return error.exc_type;
	return fallback;
}

export default {
	name: "SimpleCashierExpenseDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			businessContext: {},
			values: emptyValues(),
		};
	},
	computed: {
		ready() {
			return Boolean(this.formContext.ready);
		},
		blockingReasons() {
			return this.formContext.blocking_reasons || [];
		},
		allowExpenseDateEdit() {
			return Boolean(this.formContext.capabilities?.allow_expense_date_edit);
		},
		categoryContext() {
			return { company: this.businessContext.company || "" };
		},
		projectedCash() {
			if (!this.businessContext.opening_shift) return 0;
			return (Number(this.businessContext.available_cash) || 0) - (Number(this.values.amount) || 0);
		},
	},
	watch: {
		open(next) {
			if (next) this.loadContext();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.businessContext = data.context || {};
				this.values = { ...emptyValues(), ...(data.defaults || {}) };
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Cashier Expense.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() {
			if (this.saving) return;
			this.$emit("close");
		},
		openFullForm() {
			if (this.saving) return;
			this.$emit("open-native", "RetailEdge Cashier Expense");
		},
		async searchCategory(query) {
			const results = await callMethod(SEARCH_METHOD, {
				txt: query || "",
				company: this.businessContext.company || "",
			});
			return Array.isArray(results) ? results : [];
		},
		setExpenseCategory(next) {
			this.values.expense_category = next || "";
		},
		async saveDraft() {
			if (this.saving || this.loading || !this.ready || this.projectedCash < 0) return;
			this.saveError = "";
			this.saving = true;
			try {
				const result = await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Cashier Expense draft.");
			} finally {
				this.saving = false;
			}
		},
		formatAmount(value) {
			const amount = Number(value) || 0;
			return amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
		},
	},
};
</script>

<style scoped>
.guided-expense-state {
	min-height: 220px;
	padding: 18px 0;
}
.guided-expense-form {
	display: grid;
	gap: 18px;
}
.guided-expense-context,
.guided-cash-summary {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 10px;
}
.guided-expense-context > div,
.guided-cash-summary > div {
	display: grid;
	gap: 3px;
	padding: 9px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
	background: var(--edge-surface-muted, #f8fafc);
}
.guided-expense-context span,
.guided-cash-summary span,
.guided-field > span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.guided-expense-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
}
.guided-field {
	display: grid;
	gap: 6px;
}
.guided-field > span {
	font-weight: 600;
	color: var(--edge-text, #344054);
}
.guided-field--wide {
	grid-column: 1 / -1;
}
.guided-expense-block,
.guided-expense-note,
.guided-expense-error {
	padding: 10px 12px;
	border-radius: 8px;
}
.guided-expense-block,
.guided-expense-error {
	border: 1px solid var(--edge-danger, #d92d20);
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.guided-expense-block ul {
	margin: 6px 0 0 18px;
	padding: 0;
}
.guided-expense-note {
	border: 1px solid var(--edge-border, #e5e7eb);
	color: var(--edge-text-muted, #667085);
	background: var(--edge-surface-muted, #f8fafc);
}
.guided-cash-summary {
	grid-template-columns: repeat(5, minmax(0, 1fr));
}
.guided-cash-summary .has-warning strong {
	color: var(--edge-danger, #b42318);
}
.guided-expense-hint {
	margin: -8px 0 0;
	font-size: 0.8rem;
	color: var(--edge-text-muted, #667085);
}
.guided-expense-footer,
.guided-expense-footer-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}
.guided-expense-footer {
	width: 100%;
	justify-content: space-between;
}
@media (max-width: 900px) {
	.guided-expense-context,
	.guided-cash-summary {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 720px) {
	.guided-expense-grid,
	.guided-expense-context,
	.guided-cash-summary {
		grid-template-columns: 1fr;
	}
	.guided-expense-footer {
		align-items: stretch;
		flex-direction: column-reverse;
	}
	.guided-expense-footer-actions {
		justify-content: flex-end;
	}
}
</style>
