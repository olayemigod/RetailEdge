<template>
	<EdgeModal
		:open="open"
		title="Review & Submit Purchase Order"
		subtitle="Review the current ERPNext draft before submission. Standard submission is blocked when advanced approval or purchasing rules apply."
		size="xl"
		@close="close"
	>
		<EdgeLoadingState v-if="loading && !preview" message="Loading Purchase Order review..." :skeleton="true" />
		<EdgeErrorState v-else-if="error && !preview" title="Purchase Order review unavailable" :message="error" @retry="loadPreview" />
		<div v-else-if="preview" class="po-submit-review">
			<div v-if="error" class="po-submit-review__error" role="alert">{{ error }}</div>
			<div class="po-submit-review__context">
				<div><span>Purchase Order</span><strong>{{ preview.purchase_order }}</strong></div>
				<div><span>Supplier</span><strong>{{ preview.supplier_name || preview.supplier }}</strong></div>
				<div><span>Company</span><strong>{{ preview.company }}</strong></div>
				<div><span>Branch</span><strong>{{ preview.branch || 'Company-wide' }}</strong></div>
				<div><span>Total</span><strong>{{ formatMoney(preview.grand_total, preview.currency) }}</strong></div>
				<div><span>Items</span><strong>{{ preview.item_count || 0 }}</strong></div>
			</div>

			<div v-if="submitted" class="po-submit-review__success">
				<strong>Purchase Order {{ submitted.name }} submitted.</strong>
				<span>ERPNext has applied its normal Purchase Order submission rules and procurement status updates.</span>
			</div>
			<div v-else-if="preview.blockers?.length" class="po-submit-review__blocked">
				<strong>Standard EdgeSuite submission is not available.</strong>
				<ul><li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li></ul>
			</div>
			<div v-else class="po-submit-review__ready">
				<strong>Ready for standard ERPNext submission.</strong>
				<span>This action submits the existing draft only. It does not create a receipt, invoice, GL Entry or Stock Ledger Entry.</span>
			</div>

			<div class="table-responsive">
				<table class="table po-submit-review__table">
					<thead><tr><th>Item</th><th class="text-right">Qty</th><th>UOM</th><th class="text-right">Rate</th><th class="text-right">Amount</th><th>Required</th><th>Stock Location</th></tr></thead>
					<tbody>
						<tr v-for="row in preview.items || []" :key="`${row.item_code}-${row.schedule_date}-${row.warehouse}`">
							<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
							<td class="text-right">{{ row.qty }}</td>
							<td>{{ row.uom || '—' }}</td>
							<td class="text-right">{{ formatMoney(row.rate, preview.currency) }}</td>
							<td class="text-right">{{ formatMoney(row.amount, preview.currency) }}</td>
							<td>{{ formatDate(row.schedule_date) }}</td>
							<td>{{ row.warehouse || '—' }}</td>
						</tr>
					</tbody>
				</table>
			</div>
			<p class="po-submit-review__note">Taxes on draft: {{ preview.tax_row_count || 0 }}. Any configured Purchase Order approval Workflow keeps submission in the workflow-aware ERPNext path.</p>
		</div>

		<template #footer>
			<div class="po-submit-review__footer">
				<button
					v-if="preview?.can_submit && !submitted"
					type="button"
					class="edge-button edge-button--primary"
					:disabled="submitting"
					@click="submitOrder"
				>
					{{ submitting ? 'Submitting...' : 'Submit Purchase Order' }}
				</button>
				<span v-else></span>
				<button type="button" class="edge-button" :disabled="submitting" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.professional_purchase_order_submit.get_purchase_order_submit_preview";
const SUBMIT_METHOD = "retailedge.professional_purchase_order_submit.submit_standard_purchase_order";
const OPEN_EVENT = "retailedge-open-purchase-order-submit";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalPurchaseOrderSubmitOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() {
		return {
			open: false,
			purchaseOrder: "",
			loading: false,
			submitting: false,
			error: "",
			preview: null,
			submitted: null,
		};
	},
	created() {
		this._open = (event) => {
			const purchaseOrder = String(event?.detail?.purchase_order || "").trim();
			if (!purchaseOrder) return;
			this.purchaseOrder = purchaseOrder;
			this.preview = null;
			this.submitted = null;
			this.error = "";
			this.open = true;
			this.loadPreview();
		};
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadPreview() {
			if (!this.purchaseOrder || this.loading) return;
			this.loading = true; this.error = ""; this.submitted = null;
			try {
				this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder });
			} catch (error) { this.error = errorMessage(error, "Unable to review this Purchase Order."); }
			finally { this.loading = false; }
		},
		async submitOrder() {
			if (!this.preview?.can_submit || this.submitting) return;
			this.submitting = true; this.error = "";
			try {
				this.submitted = await callMethod(SUBMIT_METHOD, {
					purchase_order: this.preview.purchase_order,
					expected_purchase_order_modified: this.preview.purchase_order_modified,
				}, "POST");
				this.preview.can_submit = false;
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) { this.error = errorMessage(error, "Unable to submit this Purchase Order."); }
			finally { this.submitting = false; }
		},
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		formatMoney(value, currency) { try { return format_currency(Number(value || 0), currency || frappe.boot?.sysdefaults?.currency || ""); } catch (_error) { return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim(); } },
		close() {
			if (this.loading || this.submitting) return;
			this.open = false;
			this.purchaseOrder = "";
			this.preview = null;
			this.submitted = null;
			this.error = "";
		},
	},
};
</script>

<style scoped>
.po-submit-review { display:grid; gap:1rem; }
.po-submit-review__context { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:.75rem; }
.po-submit-review__context div,.po-submit-review__ready,.po-submit-review__blocked,.po-submit-review__success,.po-submit-review__error { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.po-submit-review__context span,.po-submit-review__table small { display:block; opacity:.72; }
.po-submit-review__ready,.po-submit-review__blocked,.po-submit-review__success { display:grid; gap:.25rem; }
.po-submit-review__blocked ul { margin:.35rem 0 0 1.1rem; padding:0; }
.po-submit-review__table td { vertical-align:top; }
.po-submit-review__note { margin:0; font-size:.82rem; opacity:.72; }
.po-submit-review__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:560px) { .po-submit-review__footer { flex-direction:column; } }
</style>
