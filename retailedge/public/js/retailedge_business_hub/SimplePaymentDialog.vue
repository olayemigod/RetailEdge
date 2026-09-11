<template>
	<EdgeModal
		:open="open"
		:title="customerReview ? 'Customer Payment Review' : (supplierReview ? 'Supplier Payment Review' : (formContext.title || 'Payment'))"
		:subtitle="customerReview
			? 'Review the draft Payment Entry before ERPNext posts the customer payment.'
			: (supplierReview
				? 'Review the draft Payment Entry before ERPNext posts the supplier payment.'
				: (formContext.subtitle || 'Create a Payment Entry draft using ERPNext payment and allocation controls.'))"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading || reviewLoading" class="guided-payment-state">
			<EdgeLoadingState
				:message="reviewLoading ? (isCustomerPayment ? 'Preparing customer payment review...' : 'Preparing supplier payment review...') : 'Preparing Payment Entry...'"
				:skeleton="true"
			/>
		</div>

		<div v-else-if="loadError" class="guided-payment-state">
			<EdgeErrorState
				title="Payment entry unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<div v-else-if="customerReview" class="supplier-payment-review">
			<div class="guided-payment-context" aria-label="Customer payment review context">
				<div>
					<span>Payment Entry</span>
					<strong>{{ customerReview.payment_entry }}</strong>
				</div>
				<div>
					<span>Status</span>
					<strong>{{ customerReview.status || 'Draft' }}</strong>
				</div>
				<div>
					<span>Company</span>
					<strong>{{ customerReview.company || 'Not set' }}</strong>
				</div>
				<div v-if="customerReview.branch">
					<span>Branch</span>
					<strong>{{ customerReview.branch }}</strong>
				</div>
			</div>

			<div v-if="submitError" class="guided-payment-error" role="alert">
				{{ submitError }}
			</div>

			<div v-if="customerReview.blockers && customerReview.blockers.length" class="supplier-review-blockers" role="alert">
				<strong v-if="customerReview.workflow_eligible">This Payment Entry is controlled by {{ customerReview.workflow_readiness?.workflow || 'Frappe Workflow' }}.</strong>
				<strong v-else>This draft needs Advanced ERPNext review before it can be submitted.</strong>
				<ul>
					<li v-for="blocker in customerReview.blockers" :key="blocker">{{ blocker }}</li>
				</ul>
			</div>

			<div v-if="customerReview.workflow_eligible" class="supplier-review-blockers">
				<strong>{{ customerReview.workflow_readiness?.message || 'Choose an available workflow action.' }}</strong>
				<div>Current state: {{ customerReview.workflow_readiness?.current_state || '—' }}</div>
			</div>

			<div class="supplier-review-grid">
				<div>
					<span>Customer</span>
					<strong>{{ customerReview.customer }}</strong>
				</div>
				<div>
					<span>Posting Date</span>
					<strong>{{ customerReview.posting_date }}</strong>
				</div>
				<div>
					<span>Received Amount</span>
					<strong>{{ formatMoney(customerReview.received_amount, customerReview.currency) }}</strong>
				</div>
				<div>
					<span>Mode of Payment</span>
					<strong>{{ customerReview.mode_of_payment || 'Not set' }}</strong>
				</div>
				<div>
					<span>Customer Receivable</span>
					<strong>{{ customerReview.paid_from }}</strong>
				</div>
				<div>
					<span>Receiving Account</span>
					<strong>{{ customerReview.paid_to }}</strong>
				</div>
				<div>
					<span>Payment Kind</span>
					<strong>{{ customerReview.payment_kind || 'Customer Receipt' }}</strong>
				</div>
				<div>
					<span>Sales Invoice</span>
					<strong>{{ customerReview.sales_invoice || 'Customer Advance' }}</strong>
				</div>
				<div>
					<span>Allocated</span>
					<strong>{{ formatMoney(customerReview.allocated_amount, customerReview.currency) }}</strong>
				</div>
				<div>
					<span>Unallocated</span>
					<strong>{{ formatMoney(customerReview.unallocated_amount, customerReview.currency) }}</strong>
				</div>
				<div v-if="customerReview.sales_invoice">
					<span>Invoice Outstanding</span>
					<strong>{{ formatMoney(customerReview.invoice_outstanding_amount, customerReview.currency) }}</strong>
				</div>
			</div>

			<p class="guided-payment-hint">
				Submitting uses the native ERPNext Payment Entry submit flow. RetailEdge does not directly change
				the Sales Invoice outstanding amount, GL Entry, Payment Ledger Entry, or customer balance.
			</p>
		</div>

		<div v-else-if="supplierReview" class="supplier-payment-review">
			<div class="guided-payment-context" aria-label="Supplier payment review context">
				<div>
					<span>Payment Entry</span>
					<strong>{{ supplierReview.payment_entry }}</strong>
				</div>
				<div>
					<span>Status</span>
					<strong>{{ supplierReview.status || 'Draft' }}</strong>
				</div>
				<div>
					<span>Company</span>
					<strong>{{ supplierReview.company || 'Not set' }}</strong>
				</div>
				<div v-if="supplierReview.branch">
					<span>Branch</span>
					<strong>{{ supplierReview.branch }}</strong>
				</div>
			</div>

			<div v-if="submitError" class="guided-payment-error" role="alert">
				{{ submitError }}
			</div>

			<div v-if="supplierReview.blockers && supplierReview.blockers.length" class="supplier-review-blockers" role="alert">
				<strong v-if="supplierReview.workflow_eligible">This Payment Entry is controlled by {{ supplierReview.workflow_readiness?.workflow || 'Frappe Workflow' }}.</strong>
				<strong v-else>This draft needs Advanced ERPNext review before it can be submitted.</strong>
				<ul>
					<li v-for="blocker in supplierReview.blockers" :key="blocker">{{ blocker }}</li>
				</ul>
			</div>

			<div v-if="supplierReview.workflow_eligible" class="supplier-review-blockers">
				<strong>{{ supplierReview.workflow_readiness?.message || 'Choose an available workflow action.' }}</strong>
				<div>Current state: {{ supplierReview.workflow_readiness?.current_state || '—' }}</div>
			</div>

			<div class="supplier-review-grid">
				<div>
					<span>Supplier</span>
					<strong>{{ supplierReview.supplier }}</strong>
				</div>
				<div>
					<span>Posting Date</span>
					<strong>{{ supplierReview.posting_date }}</strong>
				</div>
				<div>
					<span>Payment Amount</span>
					<strong>{{ formatMoney(supplierReview.paid_amount, supplierReview.currency) }}</strong>
				</div>
				<div>
					<span>Mode of Payment</span>
					<strong>{{ supplierReview.mode_of_payment || 'Not set' }}</strong>
				</div>
				<div>
					<span>Payment Account</span>
					<strong>{{ supplierReview.paid_from }}</strong>
				</div>
				<div>
					<span>Supplier Payable</span>
					<strong>{{ supplierReview.paid_to }}</strong>
				</div>
				<div>
					<span>Purchase Invoice</span>
					<strong>{{ supplierReview.purchase_invoice || 'Not set' }}</strong>
				</div>
				<div>
					<span>Allocated</span>
					<strong>{{ formatMoney(supplierReview.allocated_amount, supplierReview.currency) }}</strong>
				</div>
				<div>
					<span>Invoice Outstanding</span>
					<strong>{{ formatMoney(supplierReview.invoice_outstanding_amount, supplierReview.currency) }}</strong>
				</div>
			</div>

			<p class="guided-payment-hint">
				Submitting uses the native ERPNext Payment Entry submit flow. RetailEdge does not directly change
				the Purchase Invoice outstanding amount, GL Entry, Payment Ledger Entry, or supplier balance.
			</p>
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
				<template v-if="isCustomerPayment">
					Standard Receive Customer supports one Sales Invoice receipt or an unallocated customer advance; complex allocations stay in Advanced ERPNext.
				</template>
				<template v-if="isSupplierPayment">
					Standard Pay Supplier supports one Purchase Invoice per payment; complex allocations stay in Advanced ERPNext.
				</template>
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
			<div v-if="customerReview" class="guided-payment-footer">
				<button
					v-if="nativeFallbackEnabled"
					type="button"
					class="edge-button"
					:disabled="submitting"
					@click="openReviewedCustomerPaymentInERPNext"
				>
					Open in ERPNext
				</button>
				<div class="guided-payment-footer-actions">
					<button type="button" class="edge-button" :disabled="submitting" @click="requestClose">
						Close
					</button>
					<button
						v-for="action in customerReview.workflow_eligible ? (customerReview.workflow_readiness?.available_actions || []) : []"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting"
						@click="applyPaymentWorkflow(customerReview, action.action, 'customer')"
					>
						{{ submitting ? 'Applying...' : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
					</button>
					<button
						v-if="!customerReview.workflow_eligible"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting || !customerReview.can_submit"
						@click="submitCustomerPayment"
					>
						{{ submitting ? 'Submitting...' : 'Submit Payment' }}
					</button>
				</div>
			</div>
			<div v-else-if="supplierReview" class="guided-payment-footer">
				<button
					v-if="nativeFallbackEnabled"
					type="button"
					class="edge-button"
					:disabled="submitting"
					@click="openReviewedPaymentInERPNext"
				>
					Open in ERPNext
				</button>
				<div class="guided-payment-footer-actions">
					<button type="button" class="edge-button" :disabled="submitting" @click="requestClose">
						Close
					</button>
					<button
						v-for="action in supplierReview.workflow_eligible ? (supplierReview.workflow_readiness?.available_actions || []) : []"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting"
						@click="applyPaymentWorkflow(supplierReview, action.action, 'supplier')"
					>
						{{ submitting ? 'Applying...' : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
					</button>
					<button
						v-if="!supplierReview.workflow_eligible"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting || !supplierReview.can_submit"
						@click="submitSupplierPayment"
					>
						{{ submitting ? 'Submitting...' : 'Submit Payment' }}
					</button>
				</div>
			</div>
			<div v-else class="guided-payment-footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">
					Advanced ERPNext
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
const CUSTOMER_PREVIEW_METHOD = "retailedge.standard_customer_payment_submit.get_customer_payment_submit_preview";
const CUSTOMER_SUBMIT_METHOD = "retailedge.standard_customer_payment_submit.submit_standard_customer_payment";
const SUPPLIER_PREVIEW_METHOD = "retailedge.standard_supplier_payment_submit.get_supplier_payment_submit_preview";
const SUPPLIER_SUBMIT_METHOD = "retailedge.standard_supplier_payment_submit.submit_standard_supplier_payment";
const WORKFLOW_METHOD = "retailedge.workflow_actions.apply_document_workflow_action";
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

function cleanPrefill(value) {
	return typeof value === "string" ? value.trim() : "";
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

function confirmAction(message) {
	return new Promise((resolve) => {
		if (typeof frappe.confirm !== "function") {
			resolve(false);
			return;
		}
		frappe.confirm(message, () => resolve(true), () => resolve(false));
	});
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
		nativeFallbackEnabled: { type: Boolean, default: true },
		open: { type: Boolean, default: false },
		intent: { type: String, default: "" },
		initialContext: { type: Object, default: () => ({}) },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			referenceLoading: false,
			reviewLoading: false,
			submitting: false,
			loadError: "",
			saveError: "",
			submitError: "",
			customerReview: null,
			supplierReview: null,
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
		isCustomerPayment() {
			return this.intent === "receive-customer-payment";
		},
		isSupplierPayment() {
			return this.intent === "pay-supplier";
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
		initialContext: {
			deep: true,
			handler(next, previous) {
				if (this.open && next !== previous) this.loadContext();
			},
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
			this.submitError = "";
			this.customerReview = null;
			this.supplierReview = null;
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
				await this.applyInitialContext();
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Payment Entry.");
			} finally {
				this.loading = false;
			}
		},
		async applyInitialContext() {
			const initial = this.initialContext || {};
			const company = cleanPrefill(initial.company);
			const branch = cleanPrefill(initial.branch);
			const party = cleanPrefill(initial.party);
			const referenceName = cleanPrefill(initial.reference_name);

			if (company) this.values.company = company;
			if (branch) this.values.branch = branch;
			if (party) this.values.party = party;
			if (!referenceName || !party) return;

			this.referenceLoading = true;
			try {
				const details = await callMethod(REFERENCE_METHOD, {
					intent: this.intent,
					company: this.values.company,
					party: this.values.party,
					reference_name: referenceName,
					branch: this.values.branch,
				});
				const outstandingAmount = Number(details.outstanding_amount || 0);
				if (!(outstandingAmount > 0)) {
					throw new Error("The selected invoice no longer has an outstanding amount available for payment.");
				}
				this.values.references = [{
					reference_name: referenceName,
					outstanding_amount: outstandingAmount,
					allocated_amount: outstandingAmount,
				}];
				this.values.amount = outstandingAmount;
			} finally {
				this.referenceLoading = false;
			}
		},
		requestClose() {
			if (this.saving || this.submitting) return;
			this.$emit("close");
		},
		openFullForm() {
			if (this.saving || this.submitting) return;
			this.$emit("open-native", "Payment Entry");
		},
		openReviewedCustomerPaymentInERPNext() {
			if (this.submitting || !this.nativeFallbackEnabled || !this.customerReview?.payment_entry) return;
			const paymentEntry = this.customerReview.payment_entry;
			this.$emit("close");
			frappe.set_route("Form", "Payment Entry", paymentEntry);
		},
		openReviewedPaymentInERPNext() {
			if (this.submitting || !this.nativeFallbackEnabled || !this.supplierReview?.payment_entry) return;
			const paymentEntry = this.supplierReview.payment_entry;
			this.$emit("close");
			frappe.set_route("Form", "Payment Entry", paymentEntry);
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
				this.customerReview = null;
				this.supplierReview = null;
			}
		},
		setBranch(next) {
			if (this.values.branch !== (next || "")) {
				this.values.branch = next || "";
				this.values.references = [emptyReference()];
				this.customerReview = null;
				this.supplierReview = null;
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
		validateStandardSupplierDraft() {
			const references = (this.values.references || []).filter((row) => row?.reference_name);
			if (references.length !== 1) {
				throw new Error("Standard Pay Supplier supports one Purchase Invoice per payment. Use Advanced ERPNext for multi-invoice payments.");
			}
			const amount = Number(this.values.amount) || 0;
			const allocated = Number(references[0].allocated_amount) || 0;
			if (!(amount > 0) || Math.abs(amount - allocated) > 0.005) {
				throw new Error("Standard Pay Supplier must allocate the full payment amount to the selected Purchase Invoice.");
			}
		},
		async loadCustomerReview(paymentEntry) {
			this.reviewLoading = true;
			this.submitError = "";
			try {
				this.customerReview = await callMethod(CUSTOMER_PREVIEW_METHOD, {
					payment_entry: paymentEntry,
					company: this.values.company,
					customer: this.values.party,
					branch: this.values.branch,
				});
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to prepare the customer payment review.");
				throw error;
			} finally {
				this.reviewLoading = false;
			}
		},
		async loadSupplierReview(paymentEntry) {
			this.reviewLoading = true;
			this.submitError = "";
			try {
				this.supplierReview = await callMethod(SUPPLIER_PREVIEW_METHOD, {
					payment_entry: paymentEntry,
					company: this.values.company,
					supplier: this.values.party,
					branch: this.values.branch,
				});
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to prepare the supplier payment review.");
				throw error;
			} finally {
				this.reviewLoading = false;
			}
		},
		async applyPaymentWorkflow(review, action, kind) {
			if (this.submitting || !review?.workflow_eligible || !review.payment_entry || !action) return;
			this.submitError = "";
			this.submitting = true;
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					doctype: "Payment Entry",
					name: review.payment_entry,
					action,
					expected_modified: review.payment_entry_modified,
					expected_state: review.workflow_readiness?.current_state || "",
				});
				frappe.show_alert?.({ message: `Payment workflow action applied: ${action}`, indicator: "green" });
				if (Number(result.docstatus || 0) !== 0) {
					this.$emit("close");
					return;
				}
				if (kind === "customer") await this.loadCustomerReview(review.payment_entry);
				else await this.loadSupplierReview(review.payment_entry);
			} catch (error) {
				this.submitError = errorMessage(error, "Unable to apply the Payment Entry workflow action.");
				try {
					if (kind === "customer") await this.loadCustomerReview(review.payment_entry);
					else await this.loadSupplierReview(review.payment_entry);
				} catch (_refreshError) {
					// Preserve the workflow error if the document changed or left the draft queue.
				}
			} finally {
				this.submitting = false;
			}
		},
		async submitCustomerPayment() {
			if (this.submitting || !this.customerReview?.can_submit) return;
			this.submitError = "";
			const confirmed = await confirmAction(
				`Submit Payment Entry ${this.customerReview.payment_entry}? ERPNext will post this customer payment.`
			);
			if (!confirmed) return;

			this.submitting = true;
			try {
				await callMethod(CUSTOMER_SUBMIT_METHOD, {
					payment_entry: this.customerReview.payment_entry,
					expected_payment_entry_modified: this.customerReview.payment_entry_modified,
					company: this.customerReview.company,
					customer: this.customerReview.customer,
					branch: this.customerReview.branch,
				});
				this.$emit("close");
			} catch (error) {
				this.submitError = errorMessage(error, "Unable to submit the customer payment.");
				try {
					await this.loadCustomerReview(this.customerReview.payment_entry);
				} catch (_refreshError) {
					// Preserve the submit error. The operator can close and reopen if the draft changed.
				}
			} finally {
				this.submitting = false;
			}
		},
		async submitSupplierPayment() {
			if (this.submitting || !this.supplierReview?.can_submit) return;
			this.submitError = "";
			const confirmed = await confirmAction(
				`Submit Payment Entry ${this.supplierReview.payment_entry}? ERPNext will post this supplier payment.`
			);
			if (!confirmed) return;

			this.submitting = true;
			try {
				await callMethod(SUPPLIER_SUBMIT_METHOD, {
					payment_entry: this.supplierReview.payment_entry,
					expected_payment_entry_modified: this.supplierReview.payment_entry_modified,
					company: this.supplierReview.company,
					supplier: this.supplierReview.supplier,
					branch: this.supplierReview.branch,
				});
				this.$emit("close");
			} catch (error) {
				this.submitError = errorMessage(error, "Unable to submit the supplier payment.");
				try {
					await this.loadSupplierReview(this.supplierReview.payment_entry);
				} catch (_refreshError) {
					// Preserve the submit error. The operator can close and reopen if the draft changed.
				}
			} finally {
				this.submitting = false;
			}
		},
		async saveDraft() {
			if (this.saving || this.loading || this.referenceLoading) return;
			this.saveError = "";
			this.saving = true;
			try {
				if (this.isSupplierPayment) this.validateStandardSupplierDraft();
				const result = await callMethod(CREATE_METHOD, {
					intent: this.intent,
					values: this.values,
				});
				if (this.isCustomerPayment) {
					await this.loadCustomerReview(result.name);
					return;
				}
				if (this.isSupplierPayment) {
					await this.loadSupplierReview(result.name);
					return;
				}
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
		formatMoney(value, currency) {
			const amount = Number(value) || 0;
			return `${currency || ""} ${amount.toLocaleString(undefined, {
				minimumFractionDigits: 2,
				maximumFractionDigits: 2,
			})}`.trim();
		},
	},
};
</script>

<style scoped>
.guided-payment-state {
	min-height: 220px;
	padding: 18px 0;
}
.guided-payment-form,
.supplier-payment-review {
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
.guided-payment-summary span,
.supplier-review-grid span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.guided-payment-grid,
.supplier-review-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
}
.supplier-review-grid > div {
	display: grid;
	gap: 4px;
	padding: 10px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
	background: var(--edge-surface, #ffffff);
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
.guided-payment-error,
.supplier-review-blockers {
	padding: 10px 12px;
	border: 1px solid var(--edge-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.supplier-review-blockers ul {
	margin: 8px 0 0;
	padding-left: 20px;
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
	.guided-payment-summary,
	.supplier-review-grid {
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