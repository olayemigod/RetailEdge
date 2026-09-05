<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Deposit Cash'"
		:subtitle="formContext.subtitle || 'Deposit accountable shift cash to an approved company bank account.'"
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="cash-deposit-state">
			<EdgeLoadingState message="Preparing cashier cash..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="cash-deposit-state">
			<EdgeErrorState title="Deposit Cash unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="cash-deposit-form" @submit.prevent="saveDraft">
			<div class="cash-deposit-context">
				<div><span>Company</span><strong>{{ values.company || 'Not set' }}</strong></div>
				<div v-if="values.branch"><span>Branch</span><strong>{{ values.branch }}</strong></div>
				<div><span>Cashier</span><strong>{{ values.cashier || 'Not set' }}</strong></div>
				<div><span>Opening Shift</span><strong>{{ values.pos_opening_shift || 'Not set' }}</strong></div>
			</div>

			<div class="cash-deposit-summary" aria-label="Cash custody summary">
				<div><span>Opening Cash</span><strong>{{ money(custody.opening_cash) }}</strong></div>
				<div><span>Cash Sales</span><strong>{{ money(custody.cash_sales) }}</strong></div>
				<div><span>Cashier Expenses</span><strong>{{ money(custody.cashier_expenses) }}</strong></div>
				<div><span>Deposited Already</span><strong>{{ money(custody.submitted_deposits) }}</strong></div>
				<div class="cash-deposit-summary-total"><span>Available Cash</span><strong>{{ money(custody.available_cash) }}</strong></div>
			</div>

			<div v-if="saveError" class="cash-deposit-error" role="alert">{{ saveError }}</div>

			<div class="cash-deposit-grid">
				<label class="cash-deposit-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>
				<EdgeLinkField
					:modelValue="values.to_bank_account"
					label="Deposit To Bank Account"
					placeholder="Search bank, account or branch"
					description="Shared bank accounts and accounts for your current branch are shown."
					:required="true"
					:searcher="searchBankAccount"
					:context="searchContext"
					@update:modelValue="setBankAccount"
				/>
				<label class="cash-deposit-field">
					<span>Amount <b>*</b></span>
					<input
						v-model.number="values.amount"
						class="form-control"
						type="number"
						min="0.01"
						:max="Number(custody.available_cash || 0) || undefined"
						step="0.01"
						required
					/>
				</label>
				<label class="cash-deposit-field">
					<span>Deposit / Teller Reference <b>*</b></span>
					<input v-model="values.reference_no" class="form-control" type="text" required />
				</label>
				<label class="cash-deposit-field">
					<span>Reference Date <b>*</b></span>
					<input v-model="values.reference_date" class="form-control" type="date" required />
				</label>
			</div>

			<p class="cash-deposit-hint">
				The source Cash account is controlled by your active shift and cannot be changed here. Only submitted deposits reduce available shift cash.
			</p>
			<label class="cash-deposit-field cash-deposit-field--wide">
				<span>Remarks</span>
				<textarea v-model="values.remarks" class="form-control" rows="3" placeholder="Optional deposit note"></textarea>
			</label>
		</form>

		<template #footer>
			<div class="cash-deposit-footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="cash-deposit-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveDraft">
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const CONTEXT_METHOD = "retailedge.cash_custody.get_cash_deposit_context";
const SEARCH_METHOD = "retailedge.cash_custody.search_cash_deposit_options";
const CREATE_METHOD = "retailedge.cash_custody.create_cash_deposit_draft";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		company: "",
		branch: "",
		cashier: "",
		pos_opening_shift: "",
		posting_date: "",
		from_account: "",
		to_bank_account: "",
		amount: "",
		reference_no: "",
		reference_date: "",
		remarks: "",
	};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) =>
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		})
	);
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc_type || fallback;
}

function optionValue(option) {
	return typeof option === "string" ? option : option?.value || "";
}

export default {
	name: "SimpleCashDepositDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
		nativeFallbackEnabled: { type: Boolean, default: true },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			custody: {},
			values: emptyValues(),
		};
	},
	computed: {
		searchContext() {
			return { ...this.values };
		},
	},
	watch: {
		open(value) {
			if (value) this.loadContext();
			else this.reset();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		reset() {
			this.loading = false;
			this.saving = false;
			this.loadError = "";
			this.saveError = "";
			this.formContext = {};
			this.custody = {};
			this.values = emptyValues();
		},
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			try {
				const result = await callMethod(CONTEXT_METHOD);
				this.formContext = result || {};
				this.custody = result?.custody || {};
				this.values = { ...emptyValues(), ...(result?.defaults || {}) };
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Deposit Cash.");
			} finally {
				this.loading = false;
			}
		},
		async searchBankAccount(txt) {
			const result = await callMethod(SEARCH_METHOD, {
				fieldname: "to_bank_account",
				txt: txt || "",
				values: { ...this.values },
				limit: 20,
			});
			return Array.isArray(result) ? result : [];
		},
		setBankAccount(option) {
			this.values.to_bank_account = optionValue(option);
		},
		money(value) {
			const amount = Number(value || 0);
			return new Intl.NumberFormat(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(amount);
		},
		requestClose() {
			if (!this.saving) this.$emit("close");
		},
		openFullForm() {
			if (!this.saving) this.$emit("open-native", this.formContext.full_form_doctype || "Payment Entry");
		},
		async saveDraft() {
			if (this.saving || this.loading) return;
			const amount = Number(this.values.amount || 0);
			if (!this.values.to_bank_account || amount <= 0 || !this.values.reference_no) {
				this.saveError = "Bank Account, a positive Amount and Deposit Reference are required.";
				return;
			}
			if (amount > Number(this.custody.available_cash || 0)) {
				this.saveError = "Amount cannot exceed the available cash for this shift.";
				return;
			}
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: { ...this.values } });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Cash deposit could not be saved.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.cash-deposit-state { min-height: 180px; display: grid; place-items: center; }
.cash-deposit-form { display: grid; gap: 18px; }
.cash-deposit-context,
.cash-deposit-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 12px; padding: 14px; border: 1px solid var(--edge-border, #dfe3e8); border-radius: 10px; }
.cash-deposit-summary { grid-template-columns: repeat(5, minmax(0, 1fr)); }
.cash-deposit-context div,
.cash-deposit-summary div,
.cash-deposit-field { display: grid; gap: 5px; }
.cash-deposit-context span,
.cash-deposit-summary span,
.cash-deposit-field span { font-size: .78rem; color: var(--edge-text-muted, #667085); }
.cash-deposit-summary-total strong { font-size: 1.08rem; }
.cash-deposit-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.cash-deposit-field--wide { grid-column: 1 / -1; }
.cash-deposit-error { padding: 10px 12px; border-radius: 8px; background: #fef3f2; color: #b42318; }
.cash-deposit-hint { margin: 0; color: var(--edge-text-muted, #667085); font-size: .83rem; }
.cash-deposit-footer,
.cash-deposit-footer-actions { display: flex; align-items: center; gap: 10px; }
.cash-deposit-footer { justify-content: space-between; width: 100%; }
@media (max-width: 900px) { .cash-deposit-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 720px) { .cash-deposit-context, .cash-deposit-grid, .cash-deposit-summary { grid-template-columns: 1fr; } .cash-deposit-footer { align-items: stretch; flex-direction: column; } .cash-deposit-footer-actions { justify-content: flex-end; } }
</style>
