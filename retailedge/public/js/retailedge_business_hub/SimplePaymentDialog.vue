<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Payment'"
		:subtitle="formContext.subtitle || 'Create a Payment Entry draft using ERPNext payment and allocation controls.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-payment-state">
			<EdgeLoadingState message="Preparing Payment Entry..." :skeleton="true" />
		</div>

		<div v-else-if="loadError" class="guided-payment-state">
			<EdgeErrorState
				title="Payment entry unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<form v-else class="guided-payment-form" @submit.prevent="saveDraft">
			<div class="guided-payment-context" aria-label="Payment context">
				<div>
					<span>Company</span>
					<strong>{{ values.company || 'Not set' }}</strong>
				</div>
				<div>
					<span>Payment Type</span>
					<strong>{{ formContext.payment_type || 'Payment' }}</strong>
				</div>
				<div v-if="values.branch">
					<span>Branch</span>
					<strong>{{ values.branch }}</strong>
				</div>
			</div>

			<div v-if="saveError" class="guided-payment-error" role="alert">
				{{ saveError }}
			</div>

			<div class="guided-payment-grid">
				<EdgeLinkField
					:modelValue="values.party"
					:label="formContext.party_label || 'Party'"
					:placeholder="`Search ${(formContext.party_label || 'party').toLowerCase()}`"
					:required="true"
					:searcher="searchParty"
					:context="searchContext"
					@update:modelValue="setParty"
				/>

				<label class="guided-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					description="Changing branch clears selected invoice allocations."
					:searcher="searchBranch"
					:context="searchContext"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.mode_of_payment"
					label="Mode of Payment"
					placeholder="Cash, bank transfer, POS..."
					:required="true"
					:searcher="searchModeOfPayment"
					:context="searchContext"
					@update:modelValue="setModeOfPayment"
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

				<div v-if="modeDetails.account" class="guided-account-summary">
					<span>Payment Account</span>
					<strong>{{ modeDetails.account }}</strong>
					<small>{{ modeDetails.account_type }} · {{ modeDetails.account_currency }}</small>
				</div>

				<label v-if="modeDetails.reference_required" class="guided-field">
					<span>Reference No <b>*</b></span>
					<input
						v-model="values.reference_no"
						class="form-control"
						type="text"
						placeholder="Transfer / cheque reference"
						required
					/>
				</label>

				<label v-if="modeDetails.reference_required" class="guided-field">
					<span>Reference Date <b>*</b></span>
					<input v-model="values.reference_date" class="form-control" type="date" required />
				</label>
			</div>

			<EdgeChildTable
				:field="referenceTableField"
				:rows="values.references"
				:columns="referenceColumns"
				:addLabel="`Add ${formContext.reference_label || 'Invoice'}`"
				:linkSearcher="searchReferenceLink"
				@update:rows="updateReferences"
			/>

			<div class="guided-payment-summary">
				<div>
					<span>Payment Amount</span>
					<strong>{{ formatAmount(values.amount) }}</strong>
				</div>
				<div>
					<span>Allocated</span>
					<strong>{{ formatAmount(allocatedTotal) }}</strong>
				</div>
				<div :class="{ 'has-warning': unallocatedAmount < 0 }">
					<span>Unallocated</span>
					<strong>{{ formatAmount(unallocatedAmount) }}</strong>
				</div>
			</div>

			<p class="guided-payment-hint">
				Only submitted invoices with a positive outstanding balance are offered. Multi-currency and
				payment-term allocation cases remain on the full ERPNext Payment Entry form.
			</p>

			<label class="guided-field guided-field--wide">
				<span>Remarks</span>
				<textarea
					v-model="values.remarks"
					class="form-control"
					rows="3"
					placeholder="Optional payment note"
				></textarea>
			</label>
		</form>

		<template #footer>
			<div class="guided-payment-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">
					Open Full Form
				</button>
				<div class="guided-payment-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">
						Cancel
					</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading || referenceLoading"
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
const CONTEXT_METHOD = "retailedge.guided_payment.get_simple_payment_context";
const SEARCH_METHOD = "retailedge.guided_payment.search_simple_payment_options";
const MODE_METHOD = "retailedge.guided_payment.get_simple_payment_mode_details";
const REFERENCE_METHOD = "retailedge.guided_payment.get_simple_payment_reference_details";
const CREATE_METHOD = "retailedge.guided_payment.create_simple_payment_draft";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyReference() {
	return { reference_name: "", outstanding_amount: "", allocated_amount: "" };
}

function emptyValues() {
	return {
		company: "",
		branch: "",
		posting_date: "",
		party: "",
		mode_of_payment: "",
		amount: "",
		reference_no: "",
		reference_date: "",
		remarks: "",
		references: [emptyReference()],
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
	name: "SimplePaymentDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeChildTable: runtimeComponents.EdgeChildTable,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
		intent: { type: String, default: "" },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			referenceLoading: false,
			loadError: "",
			saveError: "",
			formContext: {},
			modeDetails: {},
			values: emptyValues(),
			referenceTableField: {
				label: "Invoice Allocations",
				description: "Allocate this payment to one or more outstanding invoices.",
			},
			referenceColumns: [
				{
					fieldname: "reference_name",
					label: "Invoice",
					fieldtype: "Link",
					placeholder: "Search outstanding invoice",
				},
				{
					fieldname: "outstanding_amount",
					label: "Outstanding",
					fieldtype: "Currency",
					readonly: true,
				},
				{
					fieldname: "allocated_amount",
					label: "Allocate",
					fieldtype: "Currency",
				},
			],
		};
	},
	computed: {
		branchEnabled() {
			return Boolean(this.formContext.capabilities?.branch_enabled);
		},
		searchContext() {
			return {
				company: this.values.company,
				branch: this.values.branch,
				party: this.values.party,
			};
		},
		allocatedTotal() {
			return (this.values.references || []).reduce(
				(total, row) => total + (Number(row.allocated_amount) || 0),
				0
			);
		},
		unallocatedAmount() {
			return (Number(this.values.amount) || 0) - this.allocatedTotal;
		},
	},
	watch: {
		open(next) {
			if (next) this.loadContext();
		},
		intent(next, previous) {
			if (this.open && next && next !== previous) this.loadContext();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		async loadContext() {
			if (!this.intent) return;
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			this.modeDetails = {};
			try {
				const data = await callMethod(CONTEXT_METHOD, { intent: this.intent });
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					references: (data.defaults?.references || [emptyReference()]).map((row) => ({
						...row,
					})),
				};
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Payment Entry.");
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
			this.$emit("open-native", "Payment Entry");
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				intent: this.intent,
				fieldname,
				txt: query || "",
				values: this.searchContext,
			});
			return Array.isArray(results) ? results : [];
		},
		searchParty(query) {
			return this.searchOptions("party", query);
		},
		searchBranch(query) {
			return this.searchOptions("branch", query);
		},
		searchModeOfPayment(query) {
			return this.searchOptions("mode_of_payment", query);
		},
		searchReferenceLink(column, query) {
			if (column?.fieldname !== "reference_name") return Promise.resolve([]);
			return this.searchOptions("reference_name", query);
		},
		setParty(next) {
			if (this.values.party !== (next || "")) {
				this.values.party = next || "";
				this.values.references = [emptyReference()];
			}
		},
		setBranch(next) {
			if (this.values.branch !== (next || "")) {
				this.values.branch = next || "";
				this.values.references = [emptyReference()];
			}
		},
		async setModeOfPayment(next) {
			this.values.mode_of_payment = next || "";
			this.modeDetails = {};
			this.saveError = "";
			if (!next) return;
			try {
				this.modeDetails = await callMethod(MODE_METHOD, {
					intent: this.intent,
					company: this.values.company,
					mode_of_payment: next,
				});
				if (!this.modeDetails.reference_required) {
					this.values.reference_no = "";
				}
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to resolve the payment account.");
			}
		},
		async updateReferences(nextRows) {
			const previousRows = this.values.references || [];
			const rows = (nextRows || []).map((row) => ({ ...row }));
			this.referenceLoading = true;
			this.saveError = "";
			try {
				for (let index = 0; index < rows.length; index += 1) {
					const row = rows[index];
					const previous = previousRows[index] || {};
					if (!row.reference_name) {
						row.outstanding_amount = "";
						row.allocated_amount = "";
						continue;
					}
					if (
						row.reference_name === previous.reference_name &&
						row.outstanding_amount
					) {
						continue;
					}
					const details = await callMethod(REFERENCE_METHOD, {
						intent: this.intent,
						company: this.values.company,
						party: this.values.party,
						reference_name: row.reference_name,
						branch: this.values.branch,
					});
					row.outstanding_amount = details.outstanding_amount;
					row.allocated_amount = details.outstanding_amount;
				}
				this.values.references = rows;
				if (!Number(this.values.amount) && this.allocatedTotal > 0) {
					this.values.amount = this.allocatedTotal;
				}
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to load the invoice outstanding amount.");
				this.values.references = rows;
			} finally {
				this.referenceLoading = false;
			}
		},
		async saveDraft() {
			if (this.saving || this.loading || this.referenceLoading) return;
			this.saveError = "";
			this.saving = true;
			try {
				const result = await callMethod(CREATE_METHOD, {
					intent: this.intent,
					values: this.values,
				});
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Payment Entry draft.");
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
.guided-payment-state {
	min-height: 220px;
	padding: 18px 0;
}
.guided-payment-form {
	display: grid;
	gap: 18px;
}
.guided-payment-context {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
}
.guided-payment-context > div,
.guided-account-summary {
	display: grid;
	gap: 2px;
	min-width: 180px;
	padding: 9px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
	background: var(--edge-surface-muted, #f8fafc);
}
.guided-payment-context span,
.guided-field > span,
.guided-account-summary span,
.guided-payment-summary span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.guided-payment-grid {
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
.guided-account-summary small,
.guided-payment-hint {
	color: var(--edge-text-muted, #667085);
}
.guided-payment-summary {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}
.guided-payment-summary > div {
	display: grid;
	gap: 3px;
	padding: 10px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
}
.guided-payment-summary .has-warning strong {
	color: var(--edge-danger, #b42318);
}
.guided-payment-hint {
	margin: -8px 0 0;
	font-size: 0.8rem;
}
.guided-payment-error {
	padding: 10px 12px;
	border: 1px solid var(--edge-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.guided-payment-footer,
.guided-payment-footer-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}
.guided-payment-footer {
	width: 100%;
	justify-content: space-between;
}
@media (max-width: 720px) {
	.guided-payment-grid,
	.guided-payment-summary {
		grid-template-columns: 1fr;
	}
	.guided-payment-footer {
		align-items: stretch;
		flex-direction: column-reverse;
	}
	.guided-payment-footer-actions {
		justify-content: flex-end;
	}
}
</style>