<template>
	<section class="payment-history-panel">
		<div class="payment-history-head">
			<div>
				<div class="payment-history-eyebrow">Money & Payments</div>
				<h3>Payment History</h3>
				<p>Find and revisit permission-visible ERPNext Payment Entries without leaving Payment Management.</p>
			</div>
			<button class="edge-secondary-button" type="button" :disabled="loading || !filters.company" @click="loadPaymentHistory(1)">
				{{ loading ? "Refreshing…" : "Refresh" }}
			</button>
		</div>

		<div class="history-filter-grid">
			<EdgeLinkField
				v-model="filters.company"
				:selectedLabel="companyLabel"
				label="Company"
				required
				placeholder="Search company"
				:searcher="companySearch"
				@select="onCompanySelected"
			/>
			<EdgeLinkField
				v-model="filters.branch"
				:selectedLabel="branchLabel"
				label="Branch"
				placeholder="All permitted branches"
				:searcher="branchSearch"
				@select="onBranchSelected"
				@clear="clearBranch"
			/>
			<label class="edge-field">
				<span>Party Type</span>
				<select v-model="filters.party_type" class="edge-input" @change="onPartyTypeChanged">
					<option value="">All parties</option>
					<option value="Customer">Customer</option>
					<option value="Supplier">Supplier</option>
				</select>
			</label>
			<EdgeLinkField
				v-if="filters.party_type"
				v-model="filters.party"
				:selectedLabel="partyLabel"
				:label="filters.party_type"
				:placeholder="`Search ${filters.party_type.toLowerCase()}`"
				:searcher="partySearch"
				@select="onPartySelected"
				@clear="clearParty"
			/>
			<div v-else class="edge-field">
				<span>Party</span>
				<div class="edge-input edge-input--readonly">Choose Party Type first</div>
			</div>
			<label class="edge-field">
				<span>Payment Type</span>
				<select v-model="filters.payment_type" class="edge-input">
					<option value="">All payment types</option>
					<option value="Receive">Receive</option>
					<option value="Pay">Pay</option>
					<option value="Internal Transfer">Internal Transfer</option>
				</select>
			</label>
			<label class="edge-field">
				<span>Document State</span>
				<select v-model="filters.docstatus" class="edge-input">
					<option value="all">All states</option>
					<option value="draft">Draft</option>
					<option value="submitted">Submitted</option>
					<option value="cancelled">Cancelled</option>
				</select>
			</label>
			<label class="edge-field"><span>From Date</span><input v-model="filters.from_date" class="edge-input" type="date" /></label>
			<label class="edge-field"><span>To Date</span><input v-model="filters.to_date" class="edge-input" type="date" /></label>
			<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="loadPaymentHistory(1)">Apply Filters</button></div>
		</div>

		<div v-if="error" class="payment-history-error">{{ error }}</div>
		<div v-else-if="loading" class="payment-history-state">Loading payment history…</div>
		<div v-else-if="!paymentHistory.length" class="payment-history-state">No Payment Entries match the current permitted scope.</div>
		<div v-else class="table-wrap">
			<table class="payment-history-table">
				<thead>
					<tr><th>Payment</th><th>Date</th><th>Type</th><th>Party</th><th>Branch</th><th>Mode</th><th class="num">Amount</th><th>Status</th><th>Action</th></tr>
				</thead>
				<tbody>
					<tr v-for="row in paymentHistory" :key="row.payment_entry">
						<td>{{ row.payment_entry }}</td>
						<td>{{ formatDate(row.posting_date) }}</td>
						<td>{{ row.payment_type || "—" }}</td>
						<td><span v-if="row.party">{{ row.party_type }} · {{ row.party }}</span><span v-else>—</span></td>
						<td>{{ row.branch || "—" }}</td>
						<td>{{ row.mode_of_payment || "—" }}</td>
						<td class="num">{{ formatCurrency(paymentAmount(row)) }}</td>
						<td>{{ row.status || documentState(row.docstatus) }}</td>
						<td><button class="edge-small-button" type="button" @click="reviewHistoryPayment(row.payment_entry)">Review</button></td>
					</tr>
				</tbody>
			</table>
		</div>

		<div class="history-pagination">
			<button class="edge-secondary-button" type="button" :disabled="loading || !pagination.has_previous" @click="loadPaymentHistory(Number(pagination.page || 1) - 1)">Previous</button>
			<span>Page {{ pagination.page || 1 }}</span>
			<button class="edge-secondary-button" type="button" :disabled="loading || !pagination.has_next" @click="loadPaymentHistory(Number(pagination.page || 1) + 1)">Next</button>
		</div>

		<section v-if="paymentDetail.payment_entry" class="payment-detail-panel">
			<div class="payment-history-head">
				<div>
					<div class="payment-history-eyebrow">Payment Review</div>
					<h3>{{ paymentDetail.payment_entry }}</h3>
					<p>ERPNext Payment Entry remains the accounting source of truth.</p>
				</div>
				<div class="detail-actions">
					<button v-if="canUseNativeDesk" class="edge-secondary-button" type="button" @click="openPaymentInERPNext(paymentDetail.payment_entry)">Open in ERPNext</button>
					<button class="edge-secondary-button" type="button" @click="clearPaymentDetail">Close</button>
				</div>
			</div>

			<div v-if="detailError" class="payment-history-error">{{ detailError }}</div>
			<div v-else-if="detailLoading" class="payment-history-state compact">Loading payment details…</div>
			<template v-else>
				<div class="detail-grid">
					<article><span>Status</span><strong>{{ paymentDetail.status || documentState(paymentDetail.docstatus) }}</strong></article>
					<article><span>Company</span><strong>{{ paymentDetail.company }}</strong></article>
					<article><span>Branch</span><strong>{{ paymentDetail.branch || "—" }}</strong></article>
					<article><span>Posting Date</span><strong>{{ formatDate(paymentDetail.posting_date) }}</strong></article>
					<article><span>Payment Type</span><strong>{{ paymentDetail.payment_type || "—" }}</strong></article>
					<article><span>Party</span><strong>{{ paymentDetail.party ? `${paymentDetail.party_type} · ${paymentDetail.party}` : "—" }}</strong></article>
					<article><span>Mode</span><strong>{{ paymentDetail.mode_of_payment || "—" }}</strong></article>
					<article><span>Paid</span><strong>{{ formatCurrency(paymentDetail.paid_amount) }}</strong></article>
					<article><span>Received</span><strong>{{ formatCurrency(paymentDetail.received_amount) }}</strong></article>
					<article><span>Unallocated</span><strong>{{ formatCurrency(paymentDetail.unallocated_amount) }}</strong></article>
					<article><span>Reference No</span><strong>{{ paymentDetail.reference_no || "—" }}</strong></article>
					<article><span>Reference Date</span><strong>{{ formatDate(paymentDetail.reference_date) }}</strong></article>
				</div>

				<div v-if="paymentDetail.references?.length" class="reference-block">
					<h4>Allocations</h4>
					<div class="table-wrap">
						<table class="payment-history-table compact-table">
							<thead><tr><th>Document</th><th>Reference</th><th class="num">Allocated</th><th class="num">Outstanding at Draft</th></tr></thead>
							<tbody>
								<tr v-for="row in paymentDetail.references" :key="`${row.reference_doctype}:${row.reference_name}`">
									<td>{{ row.reference_doctype }}</td><td>{{ row.reference_name }}</td><td class="num">{{ formatCurrency(row.allocated_amount) }}</td><td class="num">{{ formatCurrency(row.outstanding_amount) }}</td>
								</tr>
							</tbody>
						</table>
					</div>
				</div>

				<div v-if="standardReview.blockers?.length" class="review-warning">
					<strong>{{ standardReview.advanced_only ? "Advanced review required" : "Submission checks" }}</strong>
					<ul><li v-for="blocker in standardReview.blockers" :key="blocker">{{ blocker }}</li></ul>
					<p v-if="standardReview.advanced_only && !canUseNativeDesk">An accounting manager with Advanced ERPNext access must handle this payment shape.</p>
				</div>
				<div v-if="canSubmitStandard" class="standard-submit-bar">
					<span>This draft passes the existing standard RetailEdge review contract.</span>
					<button class="edge-primary-button" type="button" :disabled="submitting" @click="submitStandardDraft">{{ submitting ? "Submitting…" : "Submit Standard Payment" }}</button>
				</div>
				<div v-else-if="Number(paymentDetail.docstatus) !== 0" class="read-only-note">Submitted and cancelled payments are inspect-only here. RetailEdge does not mutate posted accounting documents.</div>
			</template>
		</section>
	</section>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeLinkField"];
const HISTORY_METHOD = "retailedge.payment_history.list_payment_history";
const DETAIL_METHOD = "retailedge.payment_history.get_payment_history_detail";
const CUSTOMER_SUBMIT_METHOD = "retailedge.standard_customer_payment_submit.submit_standard_customer_payment";
const SUPPLIER_SUBMIT_METHOD = "retailedge.standard_supplier_payment_submit.submit_standard_supplier_payment";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function optionRows(result) {
	return Array.isArray(result)
		? result.map((row) => ({ value: row?.value || row?.name || String(row || ""), label: row?.label || row?.value || row?.name || String(row || ""), description: row?.description || "" })).filter((row) => row.value)
		: [];
}

export default {
	name: "PaymentHistoryPanel",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			loading: false, error: "", detailLoading: false, detailError: "", submitting: false,
			paymentHistory: [], paymentDetail: {}, pagination: { page: 1, page_size: 25, has_previous: false, has_next: false },
			canUseNativeDesk: false, companyLabel: "", branchLabel: "", partyLabel: "",
			filters: { company: "", branch: "", party_type: "", party: "", payment_type: "", docstatus: "all", from_date: "", to_date: "", page_size: 25 },
		};
	},
	computed: {
		standardReview() { return this.paymentDetail.standard_review || {}; },
		canSubmitStandard() {
			const review = this.standardReview.review || {};
			return Number(this.paymentDetail.docstatus) === 0 && ["standard_customer", "standard_supplier"].includes(this.standardReview.kind) && Boolean(review.can_submit);
		},
	},
	mounted() { this.loadMetadata(); },
	methods: {
		async loadMetadata() {
			this.error = "";
			try {
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.customer_receivables.get_customer_receivables_context"),
					callMethod("retailedge.master_experience.get_master_retailedge_business_hub_context"),
				]);
				this.filters.company = context.default_filters?.company || "";
				this.filters.branch = context.default_filters?.branch || "";
				this.companyLabel = this.filters.company;
				this.branchLabel = this.filters.branch;
				this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);
				if (this.filters.company) await this.loadPaymentHistory(1);
			} catch (error) { this.error = errorMessage(error, "Payment History controls failed to load."); }
		},
		async searchReceivables(kind, txt) {
			const result = await callMethod("retailedge.customer_receivables.search_customer_receivables_options", { kind, txt: txt || "", company: this.filters.company });
			return optionRows(result);
		},
		companySearch(txt) { return this.searchReceivables("company", txt); },
		branchSearch(txt) { return this.filters.company ? this.searchReceivables("branch", txt) : []; },
		async partySearch(txt) {
			if (!this.filters.party_type) return [];
			if (this.filters.party_type === "Customer") return this.searchReceivables("customer", txt);
			const result = await callMethod("retailedge.purchase_reporting.search_purchase_reporting_options", { kind: "supplier", txt: txt || "", company: this.filters.company, branch: this.filters.branch || "" });
			return optionRows(result);
		},
		onCompanySelected(option) {
			this.filters.company = option.value; this.companyLabel = option.label || option.value;
			this.filters.branch = ""; this.branchLabel = ""; this.clearParty(); this.clearPaymentDetail();
		},
		onBranchSelected(option) { this.filters.branch = option.value; this.branchLabel = option.label || option.value; if (this.filters.party_type === "Supplier") this.clearParty(); this.clearPaymentDetail(); },
		clearBranch() { this.filters.branch = ""; this.branchLabel = ""; if (this.filters.party_type === "Supplier") this.clearParty(); this.clearPaymentDetail(); },
		onPartyTypeChanged() { this.clearParty(); this.clearPaymentDetail(); },
		onPartySelected(option) { this.filters.party = option.value; this.partyLabel = option.label || option.value; this.clearPaymentDetail(); },
		clearParty() { this.filters.party = ""; this.partyLabel = ""; },
		async loadPaymentHistory(page = 1) {
			if (!this.filters.company) return;
			if (this.filters.from_date && this.filters.to_date && this.filters.from_date > this.filters.to_date) { this.error = "From Date cannot be after To Date."; return; }
			this.loading = true; this.error = "";
			try {
				const result = await callMethod(HISTORY_METHOD, { ...this.filters, page, page_size: this.filters.page_size });
				this.paymentHistory = Array.isArray(result.rows) ? result.rows : [];
				this.pagination = result.pagination || { page, page_size: this.filters.page_size, has_previous: false, has_next: false };
				if (this.paymentDetail.payment_entry && !this.paymentHistory.some((row) => row.payment_entry === this.paymentDetail.payment_entry)) this.clearPaymentDetail();
			} catch (error) { this.paymentHistory = []; this.pagination = { page: 1, page_size: this.filters.page_size, has_previous: false, has_next: false }; this.error = errorMessage(error, "Payment History failed to load."); }
			finally { this.loading = false; }
		},
		async reviewHistoryPayment(paymentEntry) {
			if (!paymentEntry) return;
			this.detailLoading = true; this.detailError = ""; this.paymentDetail = { payment_entry: paymentEntry };
			try {
				this.paymentDetail = await callMethod(DETAIL_METHOD, { payment_entry: paymentEntry, company: this.filters.company || "", branch: this.filters.branch || "" });
			} catch (error) { this.paymentDetail = {}; this.detailError = errorMessage(error, "Payment detail failed to load."); }
			finally { this.detailLoading = false; }
		},
		clearPaymentDetail() { this.paymentDetail = {}; this.detailError = ""; },
		openPaymentInERPNext(name) { if (!this.canUseNativeDesk || !name) return; frappe.set_route("Form", "Payment Entry", name); },
		submitStandardDraft() {
			const review = this.standardReview.review || {};
			if (!this.canSubmitStandard || this.submitting) return;
			frappe.confirm(__(`Submit Payment Entry ${this.paymentDetail.payment_entry}? ERPNext will post the authoritative accounting entry.`), async () => {
				this.submitting = true; this.detailError = "";
				try {
					const isCustomer = this.standardReview.kind === "standard_customer";
					const method = isCustomer ? CUSTOMER_SUBMIT_METHOD : SUPPLIER_SUBMIT_METHOD;
					const args = {
						payment_entry: this.paymentDetail.payment_entry,
						expected_payment_entry_modified: review.payment_entry_modified,
						company: this.paymentDetail.company,
						branch: this.paymentDetail.branch || null,
						...(isCustomer ? { customer: this.paymentDetail.party } : { supplier: this.paymentDetail.party }),
					};
					await callMethod(method, args);
					frappe.show_alert({ message: __("Payment submitted through ERPNext."), indicator: "green" });
					await this.loadPaymentHistory(Number(this.pagination.page || 1));
					await this.reviewHistoryPayment(this.paymentDetail.payment_entry);
				} catch (error) {
					this.detailError = errorMessage(error, "Payment submission failed.");
					if (this.paymentDetail.payment_entry) await this.reviewHistoryPayment(this.paymentDetail.payment_entry);
				} finally { this.submitting = false; }
			});
		},
		paymentAmount(row) { return row.payment_type === "Receive" ? Number(row.received_amount || 0) : Number(row.paid_amount || 0); },
		documentState(docstatus) { const state = Number(docstatus); return state === 0 ? "Draft" : state === 1 ? "Submitted" : state === 2 ? "Cancelled" : "Unknown"; },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.payment-history-panel,.payment-detail-panel { margin-top:20px; padding:18px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
.payment-history-head,.history-pagination,.detail-actions,.standard-submit-bar { display:flex; align-items:center; justify-content:space-between; gap:16px; }
.payment-history-head { align-items:flex-start; margin-bottom:16px; }
.payment-history-head h3 { margin:4px 0; color:var(--edge-text,#101828); }
.payment-history-head p { margin:0; color:var(--edge-text-muted,#667085); }
.payment-history-eyebrow { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--edge-primary,#0f766e); }
.history-filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; }
.edge-field { display:flex; flex-direction:column; gap:6px; color:var(--edge-text,#101828); font-size:.82rem; font-weight:600; }
.edge-input,.edge-primary-button,.edge-secondary-button,.edge-small-button { min-height:38px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); padding:0 10px; }
.edge-input--readonly { display:flex; align-items:center; color:var(--edge-text-muted,#667085); background:var(--edge-surface-subtle,#f8fafc); }
.edge-primary-button { border-color:var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; font-weight:600; cursor:pointer; }
.edge-secondary-button,.edge-small-button { font-weight:600; cursor:pointer; }
.edge-small-button { min-height:30px; padding:0 9px; font-size:.78rem; }
button:disabled { opacity:.55; cursor:not-allowed; }
.filter-action { display:flex; }
.table-wrap { width:100%; overflow:auto; margin-top:16px; }
.payment-history-table { width:100%; border-collapse:collapse; min-width:980px; }
.compact-table { min-width:680px; }
.payment-history-table th,.payment-history-table td { padding:10px 9px; border-bottom:1px solid var(--edge-border,#e5e7eb); text-align:left; color:var(--edge-text,#101828); }
.payment-history-table th { font-size:.76rem; color:var(--edge-text-muted,#667085); text-transform:uppercase; letter-spacing:.03em; }
.payment-history-table .num { text-align:right; }
.payment-history-state,.payment-history-error { padding:24px; text-align:center; color:var(--edge-text-muted,#667085); }
.payment-history-state.compact { padding:14px; }
.payment-history-error { color:var(--edge-danger,#b42318); }
.history-pagination { justify-content:flex-end; margin-top:14px; color:var(--edge-text-muted,#667085); }
.detail-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; }
.detail-grid article { border:1px solid var(--edge-border,#e5e7eb); border-radius:var(--edge-radius-md,8px); padding:11px; display:flex; flex-direction:column; gap:5px; min-width:0; }
.detail-grid span { color:var(--edge-text-muted,#667085); font-size:.8rem; }
.detail-grid strong { color:var(--edge-text,#101828); overflow-wrap:anywhere; }
.reference-block { margin-top:18px; }
.reference-block h4 { margin:0; color:var(--edge-text,#101828); }
.review-warning,.read-only-note { margin-top:16px; padding:12px 14px; border:1px solid var(--edge-warning,#d97706); border-radius:var(--edge-radius-md,8px); color:var(--edge-text,#101828); }
.review-warning ul { margin:6px 0 0 18px; padding:0; }
.review-warning p { margin:8px 0 0; }
.read-only-note { border-color:var(--edge-border,#d9d9d9); color:var(--edge-text-muted,#667085); }
.standard-submit-bar { margin-top:16px; padding:12px 14px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); color:var(--edge-text-muted,#667085); }
@media (max-width:980px) { .history-filter-grid,.detail-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:560px) { .history-filter-grid,.detail-grid { grid-template-columns:1fr; } .payment-history-head,.history-pagination,.detail-actions,.standard-submit-bar { flex-direction:column; align-items:stretch; } }
</style>
