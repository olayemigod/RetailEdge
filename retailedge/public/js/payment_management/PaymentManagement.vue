<template>
	<div v-if="!edgeUIValid" class="payment-fallback">
		<strong>Payment Management could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Payment Management"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/payment-management"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<section class="payment-page">
			<header class="payment-hero">
				<div>
					<div class="payment-eyebrow">Customers & Receivables</div>
					<h2>Advanced Payment Management</h2>
					<p>Record customer advances, settle submitted Sales Invoices, and keep ERPNext Payment Entry and Payment Reconciliation as the accounting source of truth.</p>
				</div>
				<div class="hero-actions">
					<button v-if="canUseNativeDesk" class="edge-secondary-button" type="button" @click="openPaymentEntries">Advanced ERPNext</button>
					<button class="edge-primary-button" type="button" :disabled="!filters.company" @click="openAdvanceDialog">Record Advance</button>
				</div>
			</header>

			<EdgeLoadingState v-if="metadataLoading" message="Loading Payment Management…" />
			<EdgeErrorState v-else-if="metadataError" title="Payment Management failed to load" :message="metadataError" actionLabel="Retry" @retry="loadMetadata" />
			<template v-else>
			<div class="payment-cards">
				<article class="metric-card"><span>Available Advances</span><strong>{{ formatCurrency(context.available_advance || 0) }}</strong></article>
				<article class="metric-card"><span>Unapplied Receipts</span><strong>{{ context.advance_count || 0 }}</strong></article>
				<article class="metric-card"><span>Accounting Source</span><strong>ERPNext</strong></article>
			</div>

			<section ref="draftPanel" class="payment-panel">
				<div class="panel-head">
					<div>
						<h3>Draft Payments Awaiting Submission</h3>
						<p>Review standard customer receipts and advances here before ERPNext posts them. Complex payments remain available through Advanced ERPNext.</p>
					</div>
					<button class="edge-secondary-button" type="button" :disabled="draftLoading || !filters.company || !filters.customer" @click="loadDraftPayments">{{ draftLoading ? "Refreshing…" : "Refresh Drafts" }}</button>
				</div>
				<div v-if="!filters.company || !filters.customer" class="payment-state compact">Choose Company and Customer to review draft customer payments.</div>
				<EdgeErrorState v-else-if="draftLoadError" title="Draft payments failed to load" :message="draftLoadError" actionLabel="Refresh" @retry="loadDraftPayments" />
				<EdgeLoadingState v-else-if="draftLoading" message="Loading eligible draft payments…" />
				<EdgeEmptyState v-else-if="!draftPayments.length" title="No draft payments awaiting submission" description="No standard draft customer payments are awaiting submission in this scope." />
				<div v-else class="table-wrap">
					<table class="payment-table draft-table">
						<thead><tr>
							<th><button type="button" class="table-sort-button" @click='sortDraftPaymentsBy("payment_entry")'>Payment {{ localSortMark(draftPaymentSort, "payment_entry") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortDraftPaymentsBy("payment_kind")'>Type {{ localSortMark(draftPaymentSort, "payment_kind") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortDraftPaymentsBy("posting_date")'>Date {{ localSortMark(draftPaymentSort, "posting_date") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortDraftPaymentsBy("branch")'>Branch {{ localSortMark(draftPaymentSort, "branch") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortDraftPaymentsBy("sales_invoice")'>Invoice {{ localSortMark(draftPaymentSort, "sales_invoice") }}</button></th>
							<th class="num"><button type="button" class="table-sort-button table-sort-button--num" @click='sortDraftPaymentsBy("received_amount")'>Received {{ localSortMark(draftPaymentSort, "received_amount") }}</button></th>
							<th>Status</th><th>Action</th>
						</tr></thead>
						<tbody>
							<tr v-for="row in sortedDraftPayments" :key="row.payment_entry">
								<td>{{ row.payment_entry }}</td>
								<td>{{ row.payment_kind }}</td>
								<td>{{ formatDate(row.posting_date) }}</td>
								<td>{{ row.branch || "—" }}</td>
								<td>{{ row.sales_invoice || "—" }}</td>
								<td class="num">{{ formatCurrency(row.received_amount, row.currency) }}</td>
								<td>{{ row.workflow_eligible ? "Workflow" : (row.can_submit ? "Ready" : "Advanced Review") }}</td>
								<td><button class="edge-small-button" type="button" @click="reviewPaymentDraft(row.payment_entry)">Review</button></td>
							</tr>
						</tbody>
					</table>
				</div>
				<div v-if="draftError" class="payment-error compact" role="alert">{{ draftError }}</div>

				<div v-if="draftReview.payment_entry" class="draft-review">
					<div class="block-head">
						<div>
							<h4>Review {{ draftReview.payment_entry }}</h4>
							<p>{{ draftReview.payment_kind }} · ERPNext Payment Entry remains authoritative.</p>
						</div>
						<strong>{{ draftReview.workflow_eligible ? "Workflow Action Required" : (draftReview.can_submit ? "Ready to Submit" : "Advanced Review Required") }}</strong>
					</div>
					<div class="draft-review-grid">
						<article><span>Customer</span><strong>{{ draftReview.customer }}</strong></article>
						<article><span>Posting Date</span><strong>{{ formatDate(draftReview.posting_date) }}</strong></article>
						<article><span>Received</span><strong>{{ formatCurrency(draftReview.received_amount, draftReview.currency) }}</strong></article>
						<article><span>Receiving Account</span><strong>{{ draftReview.paid_to || "—" }}</strong></article>
						<article><span>Sales Invoice</span><strong>{{ draftReview.sales_invoice || "Unallocated advance" }}</strong></article>
						<article><span>Allocated</span><strong>{{ formatCurrency(draftReview.allocated_amount, draftReview.currency) }}</strong></article>
						<article><span>Unallocated</span><strong>{{ formatCurrency(draftReview.unallocated_amount, draftReview.currency) }}</strong></article>
						<article><span>Branch</span><strong>{{ draftReview.branch || "—" }}</strong></article>
					</div>
					<div v-if="draftReview.blockers?.length" class="draft-blockers">
						<strong v-if="draftReview.workflow_eligible">This Payment Entry is controlled by {{ draftReview.workflow_readiness?.workflow || "Frappe Workflow" }}:</strong>
						<strong v-else>{{ canUseNativeDesk ? "Use Advanced ERPNext for this draft:" : "This draft requires an accounting manager with Advanced ERPNext access:" }}</strong>
						<ul><li v-for="blocker in draftReview.blockers" :key="blocker">{{ blocker }}</li></ul>
					</div>
					<div v-if="draftReview.workflow_eligible" class="draft-blockers">
						<strong>{{ draftReview.workflow_readiness?.message || "Choose an available workflow action." }}</strong>
						<div class="draft-actions">
							<button v-for="action in draftReview.workflow_readiness?.available_actions || []" :key="action.action" class="edge-primary-button" type="button" :disabled="draftSubmitting" @click="applyPaymentWorkflow(action.action)">
								{{ draftSubmitting ? "Applying…" : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
							</button>
							<span v-if="!(draftReview.workflow_readiness?.available_actions || []).length">No workflow action is currently available to this user.</span>
						</div>
					</div>
					<div class="draft-actions">
						<button v-if="canUseNativeDesk" class="edge-secondary-button" type="button" @click="openPayment(draftReview.payment_entry)">Open in ERPNext</button>
						<button v-if="!draftReview.workflow_eligible" class="edge-primary-button" type="button" :disabled="draftSubmitting || !draftReview.can_submit" @click="submitPaymentDraft">{{ draftSubmitting ? "Submitting…" : "Submit Payment" }}</button>
					</div>
				</div>
			</section>

			<section ref="settlementPanel" class="payment-panel settlement-panel">
				<div class="panel-head">
					<div>
						<h3>Mixed Customer Settlement</h3>
						<p>Use existing submitted advances first, then optionally create a draft receipt for the remaining invoice balance.</p>
					</div>
					<button v-if="settlement.invoice" class="edge-secondary-button" type="button" :disabled="settlement.loading" @click="loadSettlementInvoice(settlement.invoice)">{{ settlement.loading ? "Refreshing…" : "Refresh Invoice" }}</button>
				</div>

				<div class="settlement-selector">
					<EdgeLinkField
						v-model="settlement.invoice"
						:selectedLabel="settlement.invoiceLabel"
						label="Sales Invoice"
						placeholder="Choose a submitted outstanding invoice"
						:searcher="salesInvoiceSearch"
						@select="onSettlementInvoiceSelected"
						@clear="clearSettlementInvoice"
					/>
					<div class="selector-help">Choose Company and Customer above first when starting from Payment Management. Opening from a Sales Invoice preloads this context.</div>
				</div>

				<EdgeErrorState v-if="settlement.loadError" title="Settlement context failed to load" :message="settlement.loadError" actionLabel="Retry" @retry="loadSettlementInvoice(settlement.invoice)" />
				<EdgeLoadingState v-else-if="settlement.loading" message="Loading authoritative Sales Invoice payment context…" />
				<template v-else-if="settlement.context.sales_invoice">
					<div v-if="settlement.actionError" class="payment-error" role="alert">{{ settlement.actionError }}</div>
					<div class="settlement-summary">
						<article><span>Invoice</span><strong><button v-if="canUseNativeDesk" class="link-button" type="button" @click="openInvoice(settlement.context.sales_invoice)">{{ settlement.context.sales_invoice }}</button><span v-else>{{ settlement.context.sales_invoice }}</span></strong></article>
						<article><span>Customer</span><strong>{{ settlement.context.customer }}</strong></article>
						<article><span>Authoritative Outstanding</span><strong>{{ formatCurrency(settlement.context.outstanding_amount, settlement.context.currency) }}</strong></article>
						<article><span>Eligible Advances</span><strong>{{ formatCurrency(settlement.context.available_advance, settlement.context.currency) }}</strong></article>
					</div>

					<div v-if="!settlement.context.currency_supported" class="accounting-warning">
						This invoice uses a non-company currency. Use the full ERPNext Payment Reconciliation and Payment Entry forms for settlement.
					</div>
					<template v-else>
						<div class="settlement-block">
							<div class="block-head">
								<div><h4>1. Apply Existing Advances</h4><p>Enter only the amounts to apply. Blank or zero rows are ignored.</p></div>
								<div class="allocation-total">Selected: <strong>{{ formatCurrency(selectedAdvanceTotal, settlement.context.currency) }}</strong></div>
							</div>
							<EdgeEmptyState v-if="!settlement.context.eligible_advances?.length" title="No eligible customer advances" description="No eligible submitted customer advances are available for this invoice." />
							<div v-else class="table-wrap">
								<table class="payment-table settlement-table">
									<thead><tr>
										<th><button type="button" class="table-sort-button" @click='sortSettlementAdvancesBy("name")'>Payment {{ localSortMark(settlementAdvanceSort, "name") }}</button></th>
										<th><button type="button" class="table-sort-button" @click='sortSettlementAdvancesBy("posting_date")'>Date {{ localSortMark(settlementAdvanceSort, "posting_date") }}</button></th>
										<th><button type="button" class="table-sort-button" @click='sortSettlementAdvancesBy("mode_of_payment")'>Mode {{ localSortMark(settlementAdvanceSort, "mode_of_payment") }}</button></th>
										<th class="num"><button type="button" class="table-sort-button table-sort-button--num" @click='sortSettlementAdvancesBy("unallocated_amount")'>Available {{ localSortMark(settlementAdvanceSort, "unallocated_amount") }}</button></th>
										<th class="num">Apply</th>
									</tr></thead>
									<tbody>
										<tr v-for="row in sortedSettlementAdvances" :key="row.name">
											<td><button v-if="canUseNativeDesk" class="link-button" type="button" @click="openPayment(row.name)">{{ row.name }}</button><span v-else>{{ row.name }}</span></td>
											<td>{{ formatDate(row.posting_date) }}</td>
											<td>{{ row.mode_of_payment || "—" }}</td>
											<td class="num">{{ formatCurrency(row.unallocated_amount, settlement.context.currency) }}</td>
											<td class="num"><input v-model.number="settlement.allocations[row.name]" class="edge-input amount-input" type="number" min="0" step="0.01" :max="Math.min(Number(row.unallocated_amount || 0), Number(settlement.context.outstanding_amount || 0))" placeholder="0.00" /></td>
										</tr>
									</tbody>
								</table>
							</div>
							<div class="settlement-actions">
								<span>Estimated balance after selected advances: <strong>{{ formatCurrency(estimatedRemainingAfterAdvances, settlement.context.currency) }}</strong></span>
								<button class="edge-primary-button" type="button" :disabled="settlement.applying || !selectedSettlementAllocations.length" @click="applySelectedAdvances">{{ settlement.applying ? "Applying…" : "Apply Selected Advances" }}</button>
							</div>
						</div>

						<div class="settlement-block receipt-block">
							<div class="block-head">
								<div><h4>2. Record Additional Receipt</h4><p>Create a standard ERPNext Payment Entry draft allocated to this invoice. Drafts do not reduce outstanding until submitted.</p></div>
							</div>
							<div class="receipt-grid">
								<EdgeLinkField v-model="settlement.receipt.mode_of_payment" :selectedLabel="settlement.receipt.modeLabel" label="Mode of Payment" required placeholder="Choose payment mode" :searcher="paymentModeSearch" @select="onPaymentModeSelected" @clear="clearPaymentMode" />
								<label class="edge-field"><span>Posting Date</span><input v-model="settlement.receipt.posting_date" class="edge-input" type="date" /></label>
								<label class="edge-field"><span>Receipt Amount</span><input v-model.number="settlement.receipt.amount" class="edge-input" type="number" min="0" step="0.01" :max="Number(settlement.context.outstanding_amount || 0)" placeholder="0.00" /></label>
								<label v-if="settlement.receipt.referenceRequired" class="edge-field"><span>Reference No</span><input v-model="settlement.receipt.reference_no" class="edge-input" type="text" /></label>
								<label v-if="settlement.receipt.referenceRequired" class="edge-field"><span>Reference Date</span><input v-model="settlement.receipt.reference_date" class="edge-input" type="date" /></label>
								<label class="edge-field receipt-remarks"><span>Remarks</span><input v-model="settlement.receipt.remarks" class="edge-input" type="text" placeholder="Optional receipt note" /></label>
							</div>
							<div class="settlement-actions">
								<span>Current ERPNext outstanding: <strong>{{ formatCurrency(settlement.context.outstanding_amount, settlement.context.currency) }}</strong></span>
								<button class="edge-primary-button" type="button" :disabled="settlement.creatingReceipt || !canCreateReceipt" @click="createReceiptDraft">{{ settlement.creatingReceipt ? "Creating…" : "Create Draft Receipt" }}</button>
							</div>
							<div v-if="settlement.lastDraft.name" class="draft-notice">
								<div><strong>Draft {{ settlement.lastDraft.name }} created.</strong><br />It is not posted yet. Review and submit it in EdgeSuite to update the Sales Invoice outstanding.</div>
								<button class="edge-secondary-button" type="button" @click="reviewPaymentDraft(settlement.lastDraft.name)">Review Draft</button>
							</div>
						</div>
					</template>
				</template>
			</section>

			<section class="payment-panel">
				<div class="panel-head">
					<div><h3>Customer Advances</h3><p>Submitted customer receipts with a positive ERPNext unallocated amount.</p></div>
					<button class="edge-secondary-button" type="button" :disabled="loading" @click="loadAdvances">{{ loading ? "Refreshing…" : "Refresh" }}</button>
				</div>
				<div class="filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.customer" :selectedLabel="customerLabel" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="refreshPaymentContext">Apply Filters</button></div>
				</div>

				<EdgeErrorState v-if="advanceLoadError" title="Customer advances failed to load" :message="advanceLoadError" actionLabel="Retry" @retry="loadAdvances" />
				<EdgeLoadingState v-else-if="loading" message="Loading customer advances…" />
				<EdgeEmptyState v-else-if="!advances.length" title="No unapplied customer advances" description="No unapplied customer advances match the current scope." />
				<div v-else class="table-wrap">
					<table class="payment-table">
						<thead><tr>
							<th><button type="button" class="table-sort-button" @click='sortCustomerAdvancesBy("name")'>Payment {{ localSortMark(customerAdvanceSort, "name") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortCustomerAdvancesBy("posting_date")'>Date {{ localSortMark(customerAdvanceSort, "posting_date") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortCustomerAdvancesBy("customer")'>Customer {{ localSortMark(customerAdvanceSort, "customer") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortCustomerAdvancesBy("branch")'>Branch {{ localSortMark(customerAdvanceSort, "branch") }}</button></th>
							<th><button type="button" class="table-sort-button" @click='sortCustomerAdvancesBy("mode_of_payment")'>Mode {{ localSortMark(customerAdvanceSort, "mode_of_payment") }}</button></th>
							<th class="num"><button type="button" class="table-sort-button table-sort-button--num" @click='sortCustomerAdvancesBy("received_amount")'>Received {{ localSortMark(customerAdvanceSort, "received_amount") }}</button></th>
							<th class="num"><button type="button" class="table-sort-button table-sort-button--num" @click='sortCustomerAdvancesBy("unallocated_amount")'>Available {{ localSortMark(customerAdvanceSort, "unallocated_amount") }}</button></th>
							<th>Actions</th>
						</tr></thead>
						<tbody>
							<tr v-for="row in sortedCustomerAdvances" :key="row.name">
								<td><button v-if="canUseNativeDesk" class="link-button" type="button" @click="openPayment(row.name)">{{ row.name }}</button><span v-else>{{ row.name }}</span></td>
								<td>{{ formatDate(row.posting_date) }}</td>
								<td>{{ row.customer }}</td>
								<td>{{ row.branch || "—" }}</td>
								<td>{{ row.mode_of_payment || "—" }}</td>
								<td class="num">{{ formatCurrency(row.received_amount) }}</td>
								<td class="num strong">{{ formatCurrency(row.unallocated_amount) }}</td>
								<td><button class="edge-small-button" type="button" @click="prepareSettlement(row)">Use in Settlement</button></td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<div class="accounting-note">
				<strong>Accounting safety:</strong> RetailEdge does not maintain a separate customer wallet or advance ledger. Submitted Payment Entry <code>unallocated_amount</code>, Sales Invoice <code>outstanding_amount</code>, ERPNext Payment Reconciliation, and standard Payment Entry submission remain authoritative.
			</div>
			</template>
		</section>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState"];
const RECEIVE_INTENT = "receive-customer-payment";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }
function optionRows(result) {
	return Array.isArray(result)
		? result.map((row) => ({
			value: row?.value || row?.name || String(row || ""),
			label: row?.label || row?.value || row?.name || String(row || ""),
			description: row?.description || "",
		})).filter((row) => row.value)
		: [];
}

function comparableValue(value) {
	if (value === null || value === undefined || value === "") return { kind: "empty", value: null };
	if (typeof value === "number" && Number.isFinite(value)) return { kind: "number", value };
	const text = String(value).trim();
	if (/^\d{4}-\d{2}-\d{2}(?:[ T].*)?$/.test(text)) {
		const timestamp = Date.parse(text);
		if (Number.isFinite(timestamp)) return { kind: "date", value: timestamp };
	}
	if (/^[-+]?\d+(?:\.\d+)?$/.test(text)) {
		const number = Number(text);
		if (Number.isFinite(number)) return { kind: "number", value: number };
	}
	return { kind: "text", value: text.toLocaleLowerCase() };
}

function nextLocalSort(current, field) {
	if (!current || current.field !== field) return { field, direction: "asc" };
	if (current.direction === "asc") return { field, direction: "desc" };
	return null;
}

function sortedCopy(rows, sort) {
	const result = [...(rows || [])];
	if (!sort?.field) return result;
	const factor = sort.direction === "desc" ? -1 : 1;
	return result
		.map((row, index) => ({ row, index }))
		.sort((left, right) => {
			const a = comparableValue(left.row?.[sort.field]);
			const b = comparableValue(right.row?.[sort.field]);
			if (a.kind === "empty" && b.kind === "empty") return left.index - right.index;
			if (a.kind === "empty") return 1;
			if (b.kind === "empty") return -1;
			let comparison = 0;
			if (a.kind === b.kind && ["number", "date"].includes(a.kind)) comparison = a.value - b.value;
			else comparison = String(a.value).localeCompare(String(b.value), undefined, { numeric: true, sensitivity: "base" });
			return comparison ? comparison * factor : left.index - right.index;
		})
		.map(({ row }) => row);
}

export default {
	name: "PaymentManagement",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		const today = frappe.datetime.get_today();
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			metadataError: "",
			loading: false,
			advanceLoadError: "",
			context: {},
			advances: [],
			draftPayments: [],
			draftLoading: false,
			draftLoadError: "",
			draftError: "",
			draftReview: {},
			draftSubmitting: false,
			draftPaymentSort: null,
			settlementAdvanceSort: null,
			customerAdvanceSort: null,
			menuItems: [],
			canUseNativeDesk: false,
			tenantName: "",
			branchName: "",
			userName: "",
			customerLabel: "",
			filters: { company: "", branch: "", customer: "" },
			settlement: {
				invoice: "",
				invoiceLabel: "",
				context: {},
				allocations: {},
				pendingAdvance: "",
				loading: false,
				applying: false,
				creatingReceipt: false,
				loadError: "",
				actionError: "",
				lastDraft: {},
				receipt: {
					mode_of_payment: "",
					modeLabel: "",
					posting_date: today,
					amount: "",
					reference_no: "",
					reference_date: today,
					remarks: "",
					referenceRequired: false,
				},
			},
		};
	},
	computed: {
		sortedDraftPayments() { return sortedCopy(this.draftPayments, this.draftPaymentSort); },
		sortedSettlementAdvances() { return sortedCopy(this.settlement.context.eligible_advances || [], this.settlementAdvanceSort); },
		sortedCustomerAdvances() { return sortedCopy(this.advances, this.customerAdvanceSort); },
		selectedSettlementAllocations() {
			const eligible = new Map((this.settlement.context.eligible_advances || []).map((row) => [row.name, row]));
			return Object.entries(this.settlement.allocations || {})
				.map(([payment_entry, value]) => ({ payment_entry, allocated_amount: Number(value || 0) }))
				.filter((row) => row.allocated_amount > 0 && eligible.has(row.payment_entry));
		},
		selectedAdvanceTotal() {
			return this.selectedSettlementAllocations.reduce((total, row) => total + Number(row.allocated_amount || 0), 0);
		},
		estimatedRemainingAfterAdvances() {
			return Math.max(Number(this.settlement.context.outstanding_amount || 0) - this.selectedAdvanceTotal, 0);
		},
		canCreateReceipt() {
			const amount = Number(this.settlement.receipt.amount || 0);
			const outstanding = Number(this.settlement.context.outstanding_amount || 0);
			return Boolean(this.settlement.receipt.mode_of_payment) && amount > 0 && amount <= outstanding;
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() { this.loadMetadata(); },
	methods: {
		sortDraftPaymentsBy(field) { this.draftPaymentSort = nextLocalSort(this.draftPaymentSort, field); },
		sortSettlementAdvancesBy(field) { this.settlementAdvanceSort = nextLocalSort(this.settlementAdvanceSort, field); },
		sortCustomerAdvancesBy(field) { this.customerAdvanceSort = nextLocalSort(this.customerAdvanceSort, field); },
		localSortMark(sort, field) {
			if (!sort || sort.field !== field) return "↕";
			return sort.direction === "desc" ? "↓" : "↑";
		},
		async loadMetadata() {
			this.metadataLoading = true;
			this.metadataError = "";
			try {
				const routeInvoice = String(frappe.route_options?.sales_invoice || frappe.route_options?.retailedge_sales_invoice || "").trim();
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_master_retailedge_business_hub_context");
				const [receivablesContext, navigation] = await Promise.all([
					callMethod("retailedge.customer_receivables.get_customer_receivables_context"),
					navigationPromise,
				]);
				this.filters.company = receivablesContext.default_filters?.company || "";
				this.filters.branch = receivablesContext.default_filters?.branch || "";
				this.tenantName = receivablesContext.tenant_name || this.filters.company;
				this.branchName = receivablesContext.branch_name || this.filters.branch;
				this.userName = receivablesContext.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);
				if (routeInvoice) {
					await this.loadSettlementInvoice(routeInvoice);
				} else if (this.filters.company) {
					await this.refreshPaymentContext();
				}
			} catch (error) {
				this.metadataError = errorMessage(error, "Failed to load Payment Management controls.");
			} finally {
				this.metadataLoading = false;
			}
		},
		async refreshPaymentContext() {
			await this.loadAdvances();
			await this.loadDraftPayments();
		},
		async loadAdvances() {
			if (!this.filters.company) return;
			this.loading = true;
			this.advanceLoadError = "";
			try {
				const result = await callMethod("retailedge.advanced_payments.get_customer_advance_context", {
					customer: this.filters.customer || null,
					company: this.filters.company,
					branch: this.filters.branch || null,
					limit: 100,
				});
				this.context = result || {};
				this.advances = result.advances || [];
			} catch (error) {
				this.advances = [];
				this.context = {};
				this.advanceLoadError = errorMessage(error, "Customer advances failed to load.");
			} finally { this.loading = false; }
		},
		async loadDraftPayments() {
			if (!this.filters.company || !this.filters.customer) {
				this.draftPayments = [];
				this.draftLoadError = "";
				this.draftError = "";
				return;
			}
			this.draftLoading = true;
			this.draftLoadError = "";
			this.draftError = "";
			try {
				const result = await callMethod("retailedge.standard_customer_payment_submit.list_standard_customer_payment_drafts", {
					company: this.filters.company,
					customer: this.filters.customer,
					branch: this.filters.branch || null,
					limit: 50,
				});
				this.draftPayments = Array.isArray(result) ? result : [];
				if (this.draftReview.payment_entry && !this.draftPayments.some((row) => row.payment_entry === this.draftReview.payment_entry)) this.draftReview = {};
			} catch (error) {
				this.draftPayments = [];
				this.draftLoadError = errorMessage(error, "Draft customer payments failed to load.");
			} finally { this.draftLoading = false; }
		},
		async reviewPaymentDraft(paymentEntry) {
			if (!paymentEntry) return;
			this.draftError = "";
			try {
				this.draftReview = await callMethod("retailedge.standard_customer_payment_submit.get_customer_payment_submit_preview", {
					payment_entry: paymentEntry,
					company: this.filters.company || null,
					customer: this.filters.customer || null,
					branch: this.filters.branch || null,
				});
				this.$nextTick(() => this.$refs.draftPanel?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
			} catch (error) {
				this.draftReview = {};
				this.draftError = errorMessage(error, "Payment draft review failed to load.");
			}
		},
		async applyPaymentWorkflow(action) {
			const preview = this.draftReview;
			if (!preview?.payment_entry || !preview.workflow_eligible || !action || this.draftSubmitting) return;
			this.draftSubmitting = true;
			this.draftError = "";
			try {
				const result = await callMethod("retailedge.standard_customer_payment_submit.apply_standard_customer_payment_workflow_action", {
					payment_entry: preview.payment_entry,
					action,
					expected_payment_entry_modified: preview.payment_entry_modified,
					expected_workflow_state: preview.workflow_readiness?.current_state || "",
					company: this.filters.company || null,
					customer: this.filters.customer || null,
					branch: this.filters.branch || null,
				});
				frappe.show_alert({ message: __("Payment workflow action applied: " + action), indicator: "green" });
				if (preview.sales_invoice && Number(result.docstatus || 0) === 1) await this.loadSettlementInvoice(preview.sales_invoice);
				else await this.loadAdvances();
				await this.loadDraftPayments();
				if (this.draftPayments.some((row) => row.payment_entry === preview.payment_entry)) await this.reviewPaymentDraft(preview.payment_entry);
				else this.draftReview = {};
			} catch (error) {
				this.draftError = errorMessage(error, "Payment workflow action failed.");
				if (preview.payment_entry) await this.reviewPaymentDraft(preview.payment_entry);
			} finally { this.draftSubmitting = false; }
		},
		submitPaymentDraft() {
			const preview = this.draftReview;
			if (!preview?.payment_entry || !preview.can_submit || this.draftSubmitting) return;
			frappe.confirm(
				__(`Submit Payment Entry ${preview.payment_entry}? ERPNext will post the payment and update the authoritative customer balance.`),
				async () => {
					this.draftSubmitting = true;
					this.draftError = "";
					try {
						const result = await callMethod("retailedge.standard_customer_payment_submit.submit_standard_customer_payment", {
							payment_entry: preview.payment_entry,
							expected_payment_entry_modified: preview.payment_entry_modified,
							company: this.filters.company || null,
							customer: this.filters.customer || null,
							branch: this.filters.branch || null,
						});
						this.draftReview = {};
						frappe.show_alert({ message: __("Customer payment submitted through ERPNext."), indicator: "green" });
						if (result.sales_invoice) await this.loadSettlementInvoice(result.sales_invoice);
						else await this.loadAdvances();
						await this.loadDraftPayments();
					} catch (error) {
						this.draftError = errorMessage(error, "Customer payment submission failed.");
						if (preview.payment_entry) await this.reviewPaymentDraft(preview.payment_entry);
					} finally { this.draftSubmitting = false; }
				},
			);
		},
		clearDraftState() {
			this.draftPayments = [];
			this.draftReview = {};
			this.draftLoadError = "";
			this.draftError = "";
		},
		async loadSettlementInvoice(invoiceName) {
			if (!invoiceName) return;
			this.settlement.loading = true;
			this.settlement.loadError = "";
			this.settlement.actionError = "";
			this.settlement.lastDraft = {};
			this.clearDraftState();
			try {
				const result = await callMethod("retailedge.advanced_payments.get_sales_invoice_advance_context", { sales_invoice: invoiceName, limit: 100 });
				this.settlement.context = result || {};
				this.settlement.invoice = result.sales_invoice || invoiceName;
				this.settlement.invoiceLabel = result.sales_invoice || invoiceName;
				this.filters.company = result.company || this.filters.company;
				this.filters.branch = result.branch || "";
				this.filters.customer = result.customer || "";
				this.customerLabel = result.customer || "";
				this.branchName = result.branch || "";
				const allocations = {};
				for (const row of result.eligible_advances || []) allocations[row.name] = 0;
				if (this.settlement.pendingAdvance && Object.prototype.hasOwnProperty.call(allocations, this.settlement.pendingAdvance)) {
					const row = (result.eligible_advances || []).find((advance) => advance.name === this.settlement.pendingAdvance);
					allocations[this.settlement.pendingAdvance] = Math.min(Number(row?.unallocated_amount || 0), Number(result.outstanding_amount || 0));
				}
				this.settlement.pendingAdvance = "";
				this.settlement.allocations = allocations;
				this.settlement.receipt.amount = "";
				await this.loadAdvances();
				await this.loadDraftPayments();
			} catch (error) {
				this.settlement.context = {};
				this.settlement.allocations = {};
				this.settlement.loadError = errorMessage(error, "Sales Invoice settlement context failed to load.");
			} finally { this.settlement.loading = false; }
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.customer_receivables.search_customer_receivables_options", { kind, txt, company: this.filters.company });
			return optionRows(result);
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		customerSearch(txt) { return this.searchOptions("customer", txt); },
		async salesInvoiceSearch(txt) {
			if (!this.filters.company || !this.filters.customer) return [];
			const result = await callMethod("retailedge.guided_payment.search_simple_payment_options", {
				intent: RECEIVE_INTENT,
				fieldname: "reference_name",
				txt: txt || "",
				values: { company: this.filters.company, branch: this.filters.branch || "", party: this.filters.customer },
			});
			return optionRows(result);
		},
		async paymentModeSearch(txt) {
			const result = await callMethod("retailedge.guided_payment.search_simple_payment_options", {
				intent: RECEIVE_INTENT,
				fieldname: "mode_of_payment",
				txt: txt || "",
				values: { company: this.settlement.context.company || this.filters.company, branch: this.settlement.context.branch || "", party: this.settlement.context.customer || this.filters.customer },
			});
			return optionRows(result);
		},
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.customer = ""; this.branchName = ""; this.customerLabel = ""; this.clearDraftState(); this.clearSettlementInvoice(); this.refreshPaymentContext(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.branchName = option.label || option.value; this.clearDraftState(); this.clearSettlementInvoice(); this.refreshPaymentContext(); },
		clearBranch() { this.filters.branch = ""; this.branchName = ""; this.clearDraftState(); this.clearSettlementInvoice(); this.refreshPaymentContext(); },
		onCustomerSelected(option) { this.filters.customer = option.value; this.customerLabel = option.label || option.value; this.clearDraftState(); this.clearSettlementInvoice(); this.refreshPaymentContext(); },
		clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; this.clearDraftState(); this.clearSettlementInvoice(); this.refreshPaymentContext(); },
		onSettlementInvoiceSelected(option) { this.loadSettlementInvoice(option.value); },
		clearSettlementInvoice() {
			this.settlement.invoice = "";
			this.settlement.invoiceLabel = "";
			this.settlement.context = {};
			this.settlement.allocations = {};
			this.settlement.loadError = "";
			this.settlement.actionError = "";
			this.settlement.lastDraft = {};
		},
		async prepareSettlement(row) {
			this.filters.company = row.company;
			this.filters.branch = row.branch || "";
			this.filters.customer = row.customer;
			this.customerLabel = row.customer;
			this.branchName = row.branch || "";
			this.settlement.pendingAdvance = row.name;
			this.clearDraftState();
			this.clearSettlementInvoice();
			this.settlement.pendingAdvance = row.name;
			await this.refreshPaymentContext();
			this.$nextTick(() => this.$refs.settlementPanel?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
			frappe.show_alert({ message: __("Choose the Sales Invoice to settle. The selected advance will be prefilled if eligible."), indicator: "blue" });
		},
		async applySelectedAdvances() {
			const outstanding = Number(this.settlement.context.outstanding_amount || 0);
			if (!this.selectedSettlementAllocations.length) return;
			if (this.selectedAdvanceTotal > outstanding + 0.005) {
				this.settlement.actionError = __("Selected advance allocations cannot exceed the current invoice outstanding amount.");
				return;
			}
			const byName = new Map((this.settlement.context.eligible_advances || []).map((row) => [row.name, row]));
			for (const allocation of this.selectedSettlementAllocations) {
				if (allocation.allocated_amount > Number(byName.get(allocation.payment_entry)?.unallocated_amount || 0) + 0.005) {
					this.settlement.actionError = __(`Allocation for ${allocation.payment_entry} exceeds its available advance.`);
					return;
				}
			}
			this.settlement.applying = true;
			this.settlement.actionError = "";
			try {
				await callMethod("retailedge.payment_application.apply_customer_advances", {
					sales_invoice: this.settlement.invoice,
					allocations: this.selectedSettlementAllocations,
				});
				frappe.show_alert({ message: __("Selected advances applied through ERPNext Payment Reconciliation."), indicator: "green" });
				await this.loadSettlementInvoice(this.settlement.invoice);
			} catch (error) { this.settlement.actionError = errorMessage(error, "Customer advance reconciliation failed."); }
			finally { this.settlement.applying = false; }
		},
		async onPaymentModeSelected(option) {
			this.settlement.receipt.mode_of_payment = option.value;
			this.settlement.receipt.modeLabel = option.label || option.value;
			this.settlement.receipt.referenceRequired = false;
			this.settlement.receipt.reference_no = "";
			this.settlement.actionError = "";
			try {
				const details = await callMethod("retailedge.guided_payment.get_simple_payment_mode_details", {
					intent: RECEIVE_INTENT,
					company: this.settlement.context.company,
					mode_of_payment: option.value,
				});
				this.settlement.receipt.referenceRequired = Boolean(details.reference_required);
			} catch (error) { this.settlement.actionError = errorMessage(error, "Payment mode details could not be loaded."); }
		},
		clearPaymentMode() {
			this.settlement.receipt.mode_of_payment = "";
			this.settlement.receipt.modeLabel = "";
			this.settlement.receipt.referenceRequired = false;
			this.settlement.receipt.reference_no = "";
		},
		async createReceiptDraft() {
			if (!this.canCreateReceipt) return;
			if (this.selectedSettlementAllocations.length) {
				this.settlement.actionError = __("Apply or clear the selected advances before creating the draft receipt so the receipt uses the latest authoritative outstanding balance.");
				return;
			}
			this.settlement.creatingReceipt = true;
			this.settlement.actionError = "";
			try {
				const result = await callMethod("retailedge.payment_application.create_sales_invoice_payment_draft", {
					sales_invoice: this.settlement.invoice,
					values: {
						posting_date: this.settlement.receipt.posting_date,
						mode_of_payment: this.settlement.receipt.mode_of_payment,
						amount: Number(this.settlement.receipt.amount || 0),
						reference_no: this.settlement.receipt.reference_no || "",
						reference_date: this.settlement.receipt.reference_date || this.settlement.receipt.posting_date,
						remarks: this.settlement.receipt.remarks || "",
					},
				});
				this.settlement.lastDraft = result || {};
				this.settlement.receipt.amount = "";
				frappe.show_alert({ message: __("Draft customer Payment Entry created. Review it below before submission."), indicator: "green" });
				await this.loadDraftPayments();
				if (result.name) await this.reviewPaymentDraft(result.name);
			} catch (error) { this.settlement.actionError = errorMessage(error, "Draft customer receipt could not be created."); }
			finally { this.settlement.creatingReceipt = false; }
		},
		async openAdvanceDialog() {
			const dialog = new frappe.ui.Dialog({
				title: __("Record Customer Advance"),
				fields: [
					{ fieldname: "company", fieldtype: "Link", options: "Company", label: __("Company"), reqd: 1, default: this.filters.company, read_only: 1 },
					{ fieldname: "branch", fieldtype: "Link", options: "Branch", label: __("Branch"), default: this.filters.branch || "" },
					{ fieldname: "customer", fieldtype: "Link", options: "Customer", label: __("Customer"), reqd: 1, default: this.filters.customer || "" },
					{ fieldname: "posting_date", fieldtype: "Date", label: __("Posting Date"), reqd: 1, default: frappe.datetime.get_today() },
					{ fieldname: "mode_of_payment", fieldtype: "Link", options: "Mode of Payment", label: __("Mode of Payment"), reqd: 1 },
					{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1 },
					{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No") },
					{ fieldname: "reference_date", fieldtype: "Date", label: __("Reference Date") },
					{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
				],
				primary_action_label: __("Create Draft Payment"),
				primary_action: async (values) => {
					try {
						const result = await callMethod("retailedge.advanced_payments.create_customer_advance_draft", { values });
						dialog.hide();
						this.filters.company = result.company || this.filters.company;
						this.filters.branch = result.branch || "";
						this.filters.customer = result.customer || "";
						this.branchName = result.branch || "";
						this.customerLabel = result.customer || "";
						this.clearSettlementInvoice();
						frappe.show_alert({ message: __("Customer advance draft created. Review it below before submission."), indicator: "green" });
						await this.loadAdvances();
						await this.loadDraftPayments();
						if (result.name) await this.reviewPaymentDraft(result.name);
					} catch (error) { frappe.msgprint({ title: __("Could not create advance"), message: errorMessage(error, "Payment Entry draft could not be created."), indicator: "red" }); }
				},
			});
			dialog.show();
		},
		openPaymentEntries() { if (!this.canUseNativeDesk) return; frappe.set_route("List", "Payment Entry"); },
		openPayment(name) { if (!this.canUseNativeDesk) return; frappe.set_route("Form", "Payment Entry", name); },
		openInvoice(name) { if (!this.canUseNativeDesk) return; frappe.set_route("Form", "Sales Invoice", name); },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		formatCurrency(value, currency = "") { try { return frappe.format(Number(value || 0), { fieldtype: "Currency", options: currency || this.context.currency || this.settlement.context.currency || "" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.payment-fallback,.payment-panel,.accounting-note,.metric-card { border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
.payment-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; }
.payment-page { display:flex; flex-direction:column; gap:var(--edge-space-lg,20px); padding-bottom:24px; }
.payment-hero { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; padding:8px 2px; }
.payment-hero h2 { margin:4px 0 6px; color:var(--edge-text,#101828); }
.payment-hero p { margin:0; max-width:850px; color:var(--edge-text-muted,#667085); }
.payment-eyebrow { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--edge-primary,#0f766e); }
.hero-actions { display:flex; gap:8px; flex-wrap:wrap; }
.payment-cards { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.metric-card { padding:16px; display:flex; flex-direction:column; gap:6px; }
.metric-card span,.settlement-summary span,.draft-review-grid span { color:var(--edge-text-muted,#667085); font-size:.8rem; }
.metric-card strong { color:var(--edge-text,#101828); font-size:1.25rem; }
.payment-panel { padding:18px; }
.panel-head,.block-head,.settlement-actions,.draft-notice,.draft-actions { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.panel-head { margin-bottom:16px; }
.panel-head h3,.block-head h4 { margin:0 0 4px; color:var(--edge-text,#101828); }
.panel-head p,.block-head p,.selector-help { margin:0; color:var(--edge-text-muted,#667085); }
.filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; margin-bottom:18px; }
.filter-action { display:flex; }
.edge-primary-button,.edge-secondary-button,.edge-small-button { min-height:38px; border-radius:var(--edge-radius-md,8px); padding:0 12px; font-weight:600; cursor:pointer; }
.edge-primary-button { border:1px solid var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; }
.edge-secondary-button,.edge-small-button { border:1px solid var(--edge-border,#d9d9d9); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); }
.edge-small-button { min-height:30px; padding:0 9px; font-size:.78rem; }
button:disabled { opacity:.55; cursor:not-allowed; }
.table-wrap { width:100%; overflow:auto; }
.payment-table { width:100%; border-collapse:collapse; min-width:900px; }
.settlement-table { min-width:720px; }
.draft-table { min-width:880px; }
.payment-table th,.payment-table td { padding:10px 9px; border-bottom:1px solid var(--edge-border,#e5e7eb); text-align:left; color:var(--edge-text,#101828); }
.payment-table th { font-size:.76rem; color:var(--edge-text-muted,#667085); text-transform:uppercase; letter-spacing:.03em; }
.table-sort-button { width:100%; border:0; padding:0; background:transparent; color:inherit; font:inherit; font-weight:700; text-align:left; cursor:pointer; text-transform:inherit; letter-spacing:inherit; }
.table-sort-button--num { text-align:right; }
.table-sort-button:hover,.table-sort-button:focus-visible { color:var(--edge-primary,#0f766e); text-decoration:underline; text-underline-offset:3px; }
.payment-table .num { text-align:right; }
.payment-table .strong { font-weight:700; }
.link-button { border:0; background:transparent; color:var(--edge-primary,#0f766e); padding:0; cursor:pointer; font-weight:600; }
.payment-state,.payment-error { padding:28px; text-align:center; color:var(--edge-text-muted,#667085); }
.payment-state.compact,.payment-error.compact { padding:16px; }
.payment-error { color:var(--edge-danger,#b42318); }
.accounting-note { padding:14px 16px; color:var(--edge-text-muted,#667085); }
.accounting-note strong { color:var(--edge-text,#101828); }
.settlement-panel,.payment-panel { scroll-margin-top:16px; }
.settlement-selector { display:grid; grid-template-columns:minmax(260px,420px) 1fr; align-items:end; gap:16px; margin-bottom:16px; }
.selector-help { font-size:.82rem; padding-bottom:8px; }
.settlement-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin:12px 0 18px; }
.settlement-summary article { border:1px solid var(--edge-border,#e5e7eb); border-radius:var(--edge-radius-md,8px); padding:12px; display:flex; flex-direction:column; gap:5px; background:var(--edge-surface-subtle,var(--edge-surface,#fff)); }
.settlement-summary strong { color:var(--edge-text,#101828); }
.accounting-warning { border:1px solid var(--edge-warning,#d97706); border-radius:var(--edge-radius-md,8px); padding:12px 14px; color:var(--edge-text,#101828); background:var(--edge-surface,#fff); }
.settlement-block { border-top:1px solid var(--edge-border,#e5e7eb); padding-top:18px; margin-top:18px; }
.receipt-block { margin-top:22px; }
.allocation-total { color:var(--edge-text-muted,#667085); white-space:nowrap; }
.allocation-total strong,.settlement-actions strong { color:var(--edge-text,#101828); }
.edge-input { width:100%; min-height:38px; box-sizing:border-box; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); padding:8px 10px; background:var(--edge-surface,#fff); color:var(--edge-text,#101828); }
.amount-input { max-width:150px; text-align:right; margin-left:auto; }
.receipt-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; margin-top:14px; }
.edge-field { display:flex; flex-direction:column; gap:6px; color:var(--edge-text,#101828); font-size:.82rem; font-weight:600; }
.receipt-remarks { grid-column:span 2; }
.settlement-actions { align-items:center; margin-top:14px; color:var(--edge-text-muted,#667085); }
.draft-notice { align-items:center; margin-top:14px; padding:12px 14px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); color:var(--edge-text-muted,#667085); }
.draft-notice strong { color:var(--edge-text,#101828); }
.draft-review { margin-top:18px; padding-top:18px; border-top:1px solid var(--edge-border,#e5e7eb); }
.draft-review-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:10px; margin-top:12px; }
.draft-review-grid article { border:1px solid var(--edge-border,#e5e7eb); border-radius:var(--edge-radius-md,8px); padding:11px; display:flex; flex-direction:column; gap:5px; min-width:0; }
.draft-review-grid strong { color:var(--edge-text,#101828); overflow-wrap:anywhere; }
.draft-blockers { margin-top:12px; padding:12px 14px; border:1px solid var(--edge-warning,#d97706); border-radius:var(--edge-radius-md,8px); color:var(--edge-text,#101828); }
.draft-blockers ul { margin:6px 0 0 18px; padding:0; }
.draft-actions { align-items:center; justify-content:flex-end; margin-top:14px; }
@media (max-width:900px) { .payment-hero { flex-direction:column; } .payment-cards,.settlement-summary,.draft-review-grid { grid-template-columns:1fr 1fr; } .filter-grid,.receipt-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } .settlement-selector { grid-template-columns:1fr; } }
@media (max-width:560px) { .filter-grid,.receipt-grid,.payment-cards,.settlement-summary,.draft-review-grid { grid-template-columns:1fr; } .receipt-remarks { grid-column:span 1; } .panel-head,.block-head,.settlement-actions,.draft-notice,.draft-actions { flex-direction:column; } }
</style>
