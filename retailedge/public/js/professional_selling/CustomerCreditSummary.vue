<template>
	<section v-if="customer && company" class="credit-summary" aria-label="Customer credit visibility">
		<div class="credit-summary__heading">
			<div>
				<span class="credit-summary__kicker">ERPNext credit control</span>
				<strong>{{ customerLabel }}</strong>
			</div>
			<EdgeStatusBadge v-if="credit" :status="statusBadge" />
		</div>

		<EdgeLoadingState v-if="loading" message="Checking customer credit..." />
		<div v-else-if="error" class="credit-summary__message credit-summary__message--muted">
			Credit visibility is unavailable for this customer. Final ERPNext submission controls still apply.
		</div>
		<template v-else-if="credit">
			<div class="credit-summary__metrics">
				<div><span>Credit Limit</span><strong>{{ credit.has_credit_limit ? money(credit.credit_limit) : "No configured limit" }}</strong></div>
				<div><span>Current Exposure</span><strong>{{ money(credit.outstanding_exposure) }}</strong></div>
				<div><span>Remaining Credit</span><strong>{{ credit.has_credit_limit ? money(credit.remaining_credit) : "Not limited" }}</strong></div>
				<div><span>Overdue</span><strong>{{ money(credit.overdue_amount) }}</strong></div>
			</div>
			<div v-if="warnings.length" class="credit-summary__warnings">
				<strong>Review before proceeding</strong>
				<ul><li v-for="warning in warnings" :key="warning">{{ warning }}</li></ul>
			</div>
			<p class="credit-summary__note">
				Company-level ERPNext credit exposure is shown for guidance only. Final Sales Order / Sales Invoice submission remains governed by ERPNext credit and overdue controls.
			</p>
		</template>
	</section>
</template>

<script>
import { callMethod } from "../retailedge_business_hub/guidedEntryUtils";

const CREDIT_METHOD = "retailedge.customer_credit_visibility.get_customer_credit_visibility";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

export default {
	name: "CustomerCreditSummary",
	components: {
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeStatusBadge: runtime.EdgeStatusBadge,
	},
	props: {
		customer: { type: String, default: "" },
		company: { type: String, default: "" },
	},
	data() {
		return {
			loading: false,
			error: "",
			credit: null,
			requestToken: 0,
		};
	},
	computed: {
		customerLabel() { return this.credit?.customer_name || this.customer; },
		statusBadge() { return this.warnings.length ? "Warning" : "Active"; },
		warnings() {
			if (!this.credit) return [];
			const warnings = [];
			if (this.credit.disabled) warnings.push("Customer is disabled in ERPNext.");
			if (this.credit.is_frozen) warnings.push("Customer is frozen in ERPNext.");
			if (this.credit.credit_limit_crossed) warnings.push("Configured ERPNext credit limit is currently crossed.");
			if (this.credit.overdue_threshold_crossed) warnings.push("Configured ERPNext overdue-billing threshold is currently crossed.");
			if (this.credit.sales_order_credit_check_bypassed) warnings.push("ERPNext is configured to bypass the Sales Order credit-limit check for this Customer and Company.");
			return warnings;
		},
	},
	watch: {
		customer() { this.loadCredit(); },
		company() { this.loadCredit(); },
	},
	mounted() { this.loadCredit(); },
	methods: {
		reset() {
			this.credit = null;
			this.error = "";
			this.loading = false;
		},
		async loadCredit() {
			const token = ++this.requestToken;
			const customer = String(this.customer || "").trim();
			const company = String(this.company || "").trim();
			if (!customer || !company) { this.reset(); return; }
			this.loading = true;
			this.error = "";
			this.credit = null;
			try {
				const result = await callMethod(CREDIT_METHOD, { customer, company });
				if (token !== this.requestToken || customer !== this.customer || company !== this.company) return;
				this.credit = result || null;
			} catch (_error) {
				if (token === this.requestToken) this.error = "unavailable";
			} finally {
				if (token === this.requestToken) this.loading = false;
			}
		},
		money(value) {
			const amount = Number(value || 0);
			const currency = this.credit?.company_currency || frappe.boot?.sysdefaults?.currency || "NGN";
			try { return format_currency(amount, currency); }
			catch (_error) { return `${currency} ${amount.toLocaleString()}`; }
		},
	},
};
</script>

<style scoped>
.credit-summary {
	margin: 14px 0;
	padding: 14px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface-subtle, #f8fafc);
}
.credit-summary__heading {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 12px;
	margin-bottom: 10px;
}
.credit-summary__heading > div { display: flex; flex-direction: column; gap: 3px; }
.credit-summary__kicker { color: var(--edge-text-muted, #667085); font-size: .74rem; text-transform: uppercase; letter-spacing: .04em; }
.credit-summary__metrics { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }
.credit-summary__metrics > div { display: flex; flex-direction: column; gap: 3px; }
.credit-summary__metrics span { color: var(--edge-text-muted, #667085); font-size: .76rem; }
.credit-summary__metrics strong { color: var(--edge-text, #101828); }
.credit-summary__warnings { margin-top: 12px; color: var(--edge-warning, #b54708); }
.credit-summary__warnings ul { margin: 5px 0 0 18px; padding: 0; }
.credit-summary__note,.credit-summary__message { margin: 10px 0 0; color: var(--edge-text-muted, #667085); font-size: .78rem; }
.credit-summary__message--muted { padding: 8px 0; }
@media (max-width: 760px) { .credit-summary__metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 480px) { .credit-summary__metrics { grid-template-columns: 1fr; } }
</style>
