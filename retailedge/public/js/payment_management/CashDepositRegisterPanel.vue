<template>
	<section class="deposit-register">
		<div class="deposit-filters">
			<EdgeDropdown v-model="status" label="Status" :options="statusOptions" />
			<EdgeSmartDateRange v-model="period" label="Period" placeholder="All dates" dateOrder="DMY" @resolved="resolvePeriod" />
			<button class="edge-button edge-button--secondary" :disabled="loading" @click="resetPeriod">All dates</button>
			<button class="edge-button edge-button--primary" :disabled="loading" @click="load(1)">Apply / Refresh</button>
		</div>
		<p class="deposit-note">Only submitted deposits reduce available shift cash. Drafts can be reviewed and completed here.</p>
		<div v-if="loading" role="status">Loading deposits…</div>
		<div v-else-if="error" role="alert">{{ error }}</div>
		<div v-else-if="!rows.length" role="status">No cash deposits found for your current access and filters.</div>
		<div v-else class="deposit-table-wrap">
			<table class="deposit-table">
				<thead><tr><th>Deposit</th><th>Date</th><th>Bank</th><th>Reference</th><th>Branch</th><th>Cashier</th><th>Shift</th><th>Amount</th><th>Status</th><th>Actions</th></tr></thead>
				<tbody>
					<tr v-for="row in rows" :key="row.payment_entry">
						<td>{{ row.payment_entry }}</td><td>{{ row.posting_date }}</td>
						<td>{{ row.bank_account || row.to_account }}</td><td>{{ row.reference_no || "—" }}</td>
						<td>{{ row.branch }}</td><td>{{ row.cashier }}</td><td>{{ row.opening_shift }}</td>
						<td class="amount">{{ money(row) }}</td><td>{{ row.status }}</td>
						<td class="deposit-actions">
							<button class="edge-button edge-button--secondary" @click="selected = row">View</button>
							<button v-if="row.docstatus === 0" class="edge-button edge-button--secondary" @click="review = row">Review</button>
							<button v-if="canUseNativeDesk" class="edge-button edge-button--secondary" @click="advanced(row)">Advanced</button>
							<button v-if="row.can_print" class="edge-button edge-button--secondary" @click="print(row)">Print</button>
						</td>
					</tr>
				</tbody>
			</table>
		</div>
		<div class="deposit-pagination">
			<button class="edge-button edge-button--secondary" :disabled="loading || !pagination.has_previous" @click="load(pagination.page - 1)">Previous</button>
			<span>Page {{ pagination.page || 1 }}</span>
			<button class="edge-button edge-button--secondary" :disabled="loading || !pagination.has_next" @click="load(pagination.page + 1)">Next</button>
		</div>
		<EdgeModal :open="Boolean(selected)" title="Cash Deposit" size="lg" @close="selected = null">
			<dl v-if="selected" class="deposit-details">
				<template v-for="field in detailFields" :key="field.key"><dt>{{ field.label }}</dt><dd>{{ selected[field.key] || "—" }}</dd></template>
				<dt>Amount</dt><dd>{{ money(selected) }}</dd>
			</dl>
			<template #footer><button class="edge-button edge-button--secondary" @click="selected = null">Close</button></template>
		</EdgeModal>
		<StandardInternalTransferCompletionDialog
			v-if="review"
			:open="true"
			:document="{ name: review.payment_entry, doctype: 'Payment Entry' }"
			:can-use-native-desk="canUseNativeDesk"
			@close="review = null"
			@changed="load(pagination.page || 1)"
			@completed="review = null"
		/>
	</section>
</template>

<script>
import StandardInternalTransferCompletionDialog from "../retailedge_business_hub/StandardInternalTransferCompletionDialog.vue";

const REQUIRED_COMPONENTS = ["EdgeDropdown", "EdgeSmartDateRange", "EdgeModal"];
const components = window.EdgeSuiteUI?.components || {};

export default {
	name: "CashDepositRegisterPanel",
	components: { StandardInternalTransferCompletionDialog, ...Object.fromEntries(REQUIRED_COMPONENTS.map(name => [name, components[name]])) },
	props: { canUseNativeDesk: { type: Boolean, default: false } },
	data() {
		return {
			rows: [], loading: false, error: "", status: "all", period: {}, fromDate: "", toDate: "",
			pagination: { page: 1 }, selected: null, review: null, requestId: 0,
			statusOptions: [{ value: "all", label: "All states" }, { value: "draft", label: "Draft" }, { value: "submitted", label: "Submitted" }, { value: "cancelled", label: "Cancelled" }],
			detailFields: [
				{ key: "payment_entry", label: "Deposit" }, { key: "posting_date", label: "Date" },
				{ key: "status", label: "Status" }, { key: "from_account", label: "From" },
				{ key: "to_account", label: "To" }, { key: "bank_account", label: "Bank" },
				{ key: "reference_no", label: "Reference" }, { key: "branch", label: "Branch" },
				{ key: "cashier", label: "Cashier" }, { key: "opening_shift", label: "Shift" },
			],
		};
	},
	created() { this._pageShow = () => { this.selected = null; this.review = null; this.load(1); }; },
	mounted() {
		window.addEventListener("retailedge-cash-deposits-page-show", this._pageShow);
		this.load(1);
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-cash-deposits-page-show", this._pageShow);
		this.requestId++;
	},
	methods: {
		resolvePeriod(value) {
			this.fromDate = value?.from_date || "";
			this.toDate = value?.to_date || "";
		},
		resetPeriod() { this.period = {}; this.fromDate = ""; this.toDate = ""; this.load(1); },
		async load(page = 1) {
			const requestId = ++this.requestId;
			this.loading = true; this.error = ""; this.rows = [];
			try {
				const result = await new Promise((resolve, reject) => frappe.call({
					method: "retailedge.cash_deposit_register.list_cash_deposits",
					args: { docstatus: this.status, from_date: this.fromDate, to_date: this.toDate, page },
					callback: response => resolve(response.message || {}), error: reject,
				}));
				if (requestId !== this.requestId) return;
				this.rows = result.rows || [];
				this.pagination = result.pagination || { page };
			} catch (error) {
				if (requestId === this.requestId) this.error = window.retailedge?.userErrorMessage?.(error, "Cash Deposits could not be loaded.") || "Cash Deposits could not be loaded.";
			} finally { if (requestId === this.requestId) this.loading = false; }
		},
		money(row) {
			try { return new Intl.NumberFormat(undefined, { style: "currency", currency: row.currency }).format(row.amount); }
			catch (_error) { return Number(row.amount || 0).toFixed(2); }
		},
		advanced(row) { if (this.canUseNativeDesk) frappe.set_route("Form", "Payment Entry", row.payment_entry); },
		print(row) {
			if (!row.can_print) return;
			const query = new URLSearchParams({ doctype: "Payment Entry", name: row.payment_entry });
			window.open("/printview?" + query, "_blank", "noopener,noreferrer");
		},
	},
};
</script>

<style scoped>
.deposit-register { padding: 1rem; border: 1px solid var(--border-color); background: var(--card-bg,var(--fg-color)); border-radius: var(--border-radius-lg,12px); color: var(--text-color); }
.deposit-filters { display: flex; flex-wrap: wrap; gap: .75rem; align-items: end; }
.deposit-note { color: var(--text-muted); margin: 1rem 0; }
.deposit-table-wrap { overflow: auto; }
.deposit-table { width: 100%; border-collapse: collapse; }
.deposit-table th, .deposit-table td { padding: .7rem; white-space: nowrap; text-align: left; border-bottom: 1px solid var(--border-color); }
.deposit-table th { color: var(--text-muted); font-size: .8rem; }
.deposit-table .amount { text-align: right; }
.deposit-actions, .deposit-pagination { display: flex; flex-wrap: wrap; align-items: center; gap: .5rem; }
.deposit-pagination { justify-content: flex-end; margin-top: 1rem; }
.deposit-details { display: grid; grid-template-columns: 1fr 2fr; gap: .75rem; }
.deposit-details dt { color: var(--text-muted); }
.deposit-details dd { margin: 0; overflow-wrap: anywhere; }
</style>
