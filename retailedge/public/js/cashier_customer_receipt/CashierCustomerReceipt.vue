<template>
	<div v-if="!edgeUIValid" class="receipt-state">
		<strong>Receive Payment could not start.</strong>
		<span>Refresh the page. If the problem continues, contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		title="ProcessEdge Retail"
		subtitle="Structured for Scale."
		:tenantName="context.company || ''"
		:branchName="context.branch || ''"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/professional-selling"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="cashier-receipt-page">
			<EdgePageHeader
				title="Receive Payment"
				description="Record a customer payment against this Sales Invoice using the current Company and Working Branch."
			/>

			<EdgeLoadingState v-if="loading" message="Preparing customer payment..." />
			<EdgeErrorState v-else-if="error" :message="error" @retry="load" />

			<div v-else-if="posted" class="receipt-content">
				<section class="edge-panel receipt-success" role="status">
					<div>
						<span class="receipt-kicker">Payment posted</span>
						<h3>{{ posted.payment_reference }}</h3>
						<p>This payment has been posted to your accounts.</p>
					</div>
					<EdgeStatusBadge status="Posted" />
				</section>
				<section class="edge-panel receipt-summary-grid">
					<div><span>Sales Invoice</span><strong>{{ posted.sales_invoice }}</strong></div>
					<div><span>Payment received</span><strong>{{ money(posted.payment_amount) }}</strong></div>
					<div><span>Remaining outstanding</span><strong>{{ money(posted.invoice_outstanding) }}</strong></div>
					<div><span>Posting status</span><strong>{{ posted.posting_status || "Posted" }}</strong></div>
				</section>
				<div class="receipt-actions">
					<button type="button" class="edge-button edge-button--primary" @click="backToSelling">Back to Professional Selling</button>
				</div>
			</div>

			<div v-else class="receipt-content">
				<section class="edge-panel receipt-context">
					<div>
						<span class="receipt-kicker">Invoice</span>
						<h3>{{ context.sales_invoice }}</h3>
						<p>{{ context.customer_name || context.customer }}</p>
					</div>
					<div class="receipt-context-amount">
						<span>Invoice outstanding</span>
						<strong>{{ money(context.invoice_outstanding) }}</strong>
						<small>{{ context.invoice_status || "Submitted" }} · {{ context.branch || "Current branch" }}</small>
					</div>
				</section>

				<section v-if="!review" class="edge-panel receipt-form-panel">
					<div class="receipt-section-heading">
						<div>
							<span class="receipt-kicker">Payment details</span>
							<h3>Enter the amount received</h3>
							<p>Partial payments are allowed up to the current invoice outstanding amount.</p>
						</div>
					</div>
					<div v-if="formError" class="receipt-error" role="alert">{{ formError }}</div>
					<div class="receipt-form-grid">
						<EdgeInput
							v-model="values.posting_date"
							type="date"
							label="Posting Date"
							:disabled="reviewing"
						/>
						<EdgeLinkField
							:modelValue="values.mode_of_payment"
							label="Mode of Payment"
							placeholder="Cash, bank transfer, card..."
							:required="true"
							:disabled="reviewing || posting || confirming"
							:searcher="searchModes"
							@update:modelValue="setMode"
						/>
						<EdgeInput
							v-model="values.amount"
							type="number"
							label="Payment Amount"
							:disabled="reviewing"
						/>
						<div class="receipt-readonly-field">
							<span>Remaining after payment</span>
							<strong>{{ money(remainingDraft) }}</strong>
						</div>
						<EdgeInput
							v-if="modeDetails.reference_required"
							v-model="values.reference_no"
							type="text"
							label="Reference No"
							:disabled="reviewing"
						/>
						<EdgeInput
							v-if="modeDetails.reference_required"
							v-model="values.reference_date"
							type="date"
							label="Reference Date"
							:disabled="reviewing"
						/>
					</div>
					<div class="receipt-actions receipt-actions--split">
						<button type="button" class="edge-button" :disabled="reviewing" @click="backToSelling">Cancel</button>
						<button type="button" class="edge-button edge-button--primary" :disabled="reviewing" @click="reviewPayment">
							{{ reviewing ? "Reviewing..." : "Review Payment" }}
						</button>
					</div>
				</section>

				<section v-else class="edge-panel receipt-review-panel">
					<div class="receipt-section-heading">
						<div>
							<span class="receipt-kicker">Payment review</span>
							<h3>Confirm before posting</h3>
							<p>These values were revalidated against the current Sales Invoice before this review.</p>
						</div>
						<EdgeStatusBadge :status="review.invoice_status || 'Submitted'" />
					</div>
					<div v-if="formError" class="receipt-error" role="alert">{{ formError }}</div>
					<div class="receipt-summary-grid">
						<div><span>Sales Invoice</span><strong>{{ review.sales_invoice }}</strong></div>
						<div><span>Customer</span><strong>{{ review.customer_name || review.customer }}</strong></div>
						<div><span>Company</span><strong>{{ review.company }}</strong></div>
						<div><span>Branch</span><strong>{{ review.branch || "Company-wide" }}</strong></div>
						<div><span>Invoice outstanding</span><strong>{{ money(review.invoice_outstanding) }}</strong></div>
						<div><span>Payment received</span><strong>{{ money(review.payment_amount) }}</strong></div>
						<div><span>Remaining after payment</span><strong>{{ money(review.remaining_after_payment) }}</strong></div>
						<div><span>Mode of Payment</span><strong>{{ review.mode_of_payment }}</strong></div>
						<div><span>Posting Date</span><strong>{{ userDate(review.posting_date) }}</strong></div>
						<div v-if="review.reference_required"><span>Reference No</span><strong>{{ review.reference_no }}</strong></div>
					</div>
					<p class="receipt-note">Posting records this payment against the invoice through the normal accounting process.</p>
					<div class="receipt-actions receipt-actions--split">
						<button type="button" class="edge-button" :disabled="posting || confirming" @click="editPayment">Edit Payment</button>
						<button type="button" class="edge-button edge-button--primary" :disabled="posting || confirming" @click="postPayment">
							{{ posting ? "Posting..." : "Post Payment" }}
						</button>
					</div>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import { confirmAboveEdgeModal } from "../retailedge_business_hub/guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.cashier_customer_receipt.get_cashier_customer_receipt_context";
const SEARCH_METHOD = "retailedge.cashier_customer_receipt.search_cashier_customer_receipt_modes";
const MODE_METHOD = "retailedge.cashier_customer_receipt.get_cashier_customer_receipt_mode_details";
const PREVIEW_METHOD = "retailedge.cashier_customer_receipt.preview_cashier_customer_receipt";
const POST_METHOD = "retailedge.cashier_customer_receipt.post_cashier_customer_receipt";
const NAVIGATION_METHOD = "retailedge.navigation_consolidation.get_retailedge_business_hub_context";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeInput", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState", "EdgeStatusBadge"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

function routeInvoice() {
	const route = frappe.get_route?.() || [];
	const raw = String(route[1] || "").trim();
	if (!raw) return "";
	try { return decodeURIComponent(raw); } catch (_error) { return raw; }
}

export default {
	name: "CashierCustomerReceipt",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			loading: true,
			reviewing: false,
			confirming: false,
			posting: false,
			error: "",
			formError: "",
			context: {},
			values: { posting_date: "", mode_of_payment: "", amount: "", reference_no: "", reference_date: "" },
			modeDetails: {},
			modeLookupPromise: null,
			review: null,
			reviewedValues: null,
			posted: null,
			menuItems: [],
			userName: "",
		};
	},
	computed: {
		remainingDraft() {
			return Math.max(Number(this.context.invoice_outstanding || 0) - Number(this.values.amount || 0), 0);
		},
	},
	created() {
		const components = runtimeComponents();
		this.edgeUIValid = REQUIRED_COMPONENTS.every((name) => Boolean(components[name]));
	},
	mounted() {
		if (this.edgeUIValid) this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = "";
			this.formError = "";
			this.review = null;
			this.reviewedValues = null;
			this.modeLookupPromise = null;
			this.modeDetails = {};
			this.posted = null;
			try {
				const salesInvoice = routeInvoice();
				if (!salesInvoice) throw new Error("Choose an unpaid Sales Invoice from Professional Selling before receiving payment.");
				window.__retailedgeBusinessHubContextCache = null;
				window.__retailedgeBusinessHubContextRequest = null;
				const [receiptContext, navigation] = await Promise.all([
					callMethod(CONTEXT_METHOD, { sales_invoice: salesInvoice }),
					callMethod(NAVIGATION_METHOD),
				]);
				this.context = receiptContext || {};
				this.values = { ...this.values, ...(receiptContext.defaults || {}) };
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.userName = navigation.context?.user_name || "";
			} catch (error) {
				this.error = errorMessage(error, "Receive Payment could not be prepared.");
			} finally {
				this.loading = false;
			}
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			})).filter((group) => group.items.length);
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "URL") return item.target || "";
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "URL") {
				if (item.target === "/pos/") window.open(item.target, "_blank", "noopener,noreferrer");
				else window.location.assign(item.target);
				return;
			}
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
		},
		searchModes(query) {
			return callMethod(SEARCH_METHOD, { sales_invoice: this.context.sales_invoice, txt: query || "" });
		},
		async setMode(next) {
			if (this.reviewing || this.confirming || this.posting || this.review) return;
			const selectedMode = next || "";
			this.values.mode_of_payment = selectedMode;
			this.modeDetails = {};
			this.formError = "";
			if (!selectedMode) {
				this.modeLookupPromise = null;
				return;
			}
			const lookup = callMethod(MODE_METHOD, {
				sales_invoice: this.context.sales_invoice,
				mode_of_payment: selectedMode,
			});
			this.modeLookupPromise = lookup;
			try {
				const details = await lookup;
				// An older lookup cannot overwrite a newer selection or a review.
				if (this.values.mode_of_payment !== selectedMode || this.review || this.confirming || this.posting) return;
				// Set the reference requirements even if Review was clicked while
				// the lookup was running. Review waits for this same request.
				this.modeDetails = details;
				if (!details.reference_required && !this.reviewing) this.values.reference_no = "";
			} catch (error) {
				if (this.values.mode_of_payment === selectedMode && !this.review && !this.posting && !this.confirming) {
					this.formError = errorMessage(error, "This Mode of Payment is not available for the invoice.");
				}
			} finally {
				if (this.modeLookupPromise === lookup) this.modeLookupPromise = null;
			}
		},
		async reviewPayment() {
			if (this.reviewing || this.confirming || this.posting || this.review) return;
			this.reviewing = true;
			this.reviewedValues = null;
			this.formError = "";
			try {
				// Wait for the selected Bank/Cash mode's field requirements
				// before building the exact review snapshot.
				const pendingModeLookup = this.modeLookupPromise;
				if (pendingModeLookup) await pendingModeLookup;
				if (this.formError) return;
				if (!this.values.mode_of_payment || !this.modeDetails?.account_type) {
					this.formError = "Choose an available Mode of Payment before reviewing.";
					return;
				}
				const paymentValues = { ...this.values };
				const preview = await callMethod(PREVIEW_METHOD, {
					sales_invoice: this.context.sales_invoice,
					values: paymentValues,
				});
				this.reviewedValues = { ...paymentValues };
				this.review = preview;
			} catch (error) {
				this.review = null;
				this.reviewedValues = null;
				this.formError = errorMessage(error, "The payment could not be reviewed.");
			} finally {
				this.reviewing = false;
			}
		},
		editPayment() {
			if (this.posting || this.confirming) return;
			this.review = null;
			this.reviewedValues = null;
			this.formError = "";
		},
		async postPayment() {
			if (this.posting || this.confirming || !this.review?.can_post || !this.reviewedValues) return;
			const reviewed = { ...this.review };
			const values = { ...this.reviewedValues };
			this.confirming = true;
			let confirmed = false;
			try {
				confirmed = await new Promise((resolve) => {
					confirmAboveEdgeModal(
						`Post ${this.money(reviewed.payment_amount)} against Sales Invoice ${reviewed.sales_invoice}?`,
						() => resolve(true),
						() => resolve(false),
					);
				});
			} finally {
				if (!confirmed) this.confirming = false;
			}
			if (!confirmed) return;
			this.posting = true;
			this.formError = "";
			try {
				this.posted = await callMethod(POST_METHOD, {
					sales_invoice: reviewed.sales_invoice,
					values,
					expected_invoice_modified: reviewed.expected_invoice_modified,
					expected_outstanding_amount: reviewed.expected_outstanding_amount,
				}, "POST");
			} catch (error) {
				this.formError = errorMessage(error, "The customer payment could not be posted. Refresh the invoice and review it again.");
				this.review = null;
				this.reviewedValues = null;
			} finally {
				this.posting = false;
				this.confirming = false;
			}
		},
		backToSelling() {
			frappe.set_route("professional-selling");
		},
		money(value) {
			const amount = Number(value || 0);
			const currency = this.context.currency || this.review?.currency || this.posted?.currency || "";
			try {
				if (currency) return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 2 }).format(amount);
			} catch (_error) {
				// Fall through to currency text when the browser lacks metadata.
			}
			return `${currency} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`.trim();
		},
		userDate(value) {
			if (!value) return "—";
			try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); }
		},
	},
};
</script>

<style scoped>
.cashier-receipt-page { min-width:0; }
.receipt-content { display:grid; gap:1rem; }
.edge-panel { padding:1.2rem; border:1px solid var(--edge-color-border,var(--border-color)); border-radius:.75rem; background:var(--edge-color-surface,var(--card-bg)); }
.receipt-context,.receipt-success,.receipt-section-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
.receipt-context h3,.receipt-success h3,.receipt-section-heading h3 { margin:.2rem 0 .35rem; }
.receipt-context p,.receipt-success p,.receipt-section-heading p { margin:0; color:var(--text-muted); }
.receipt-kicker { color:var(--text-muted); font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.04em; }
.receipt-context-amount { display:grid; gap:.2rem; text-align:right; }
.receipt-context-amount span,.receipt-context-amount small,.receipt-summary-grid span,.receipt-readonly-field span { color:var(--text-muted); font-size:.8rem; }
.receipt-context-amount strong { font-size:1.3rem; }
.receipt-form-panel,.receipt-review-panel { display:grid; gap:1rem; }
.receipt-form-grid,.receipt-summary-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.8rem; }
.receipt-readonly-field,.receipt-summary-grid>div { display:grid; gap:.25rem; align-content:center; min-height:4rem; padding:.75rem; border:1px solid var(--edge-color-border,var(--border-color)); border-radius:.6rem; background:var(--edge-color-surface-muted,var(--control-bg)); }
.receipt-actions { display:flex; justify-content:flex-end; gap:.65rem; }
.receipt-actions--split { justify-content:space-between; }
.receipt-error { padding:.75rem; border:1px solid var(--edge-color-danger,var(--red-500)); border-radius:.6rem; color:var(--edge-color-danger,var(--red-700)); background:color-mix(in srgb,var(--edge-color-danger,var(--red-500)) 7%,transparent); }
.receipt-note { margin:0; color:var(--text-muted); font-size:.85rem; }
.receipt-state { display:grid; gap:.5rem; padding:1.5rem; }
@media (max-width:680px) {
	.receipt-context,.receipt-success,.receipt-section-heading { flex-direction:column; }
	.receipt-context-amount { text-align:left; }
	.receipt-form-grid,.receipt-summary-grid { grid-template-columns:1fr; }
	.receipt-actions--split { flex-direction:column-reverse; }
	.receipt-actions--split .edge-button { width:100%; }
}
</style>
