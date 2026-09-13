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
				<div v-if="preview.workflow_eligible"><span>Workflow State</span><strong>{{ preview.workflow_readiness?.current_state || '—' }}</strong></div>
			</div>

			<div v-if="submitted" class="po-submit-review__success">
				<strong>Purchase Order {{ submitted.name }} submitted.</strong>
				<span>ERPNext has applied its normal Purchase Order submission rules and procurement status updates.</span>
			</div>
			<div v-else-if="preview.blockers?.length" class="po-submit-review__blocked">
				<strong v-if="preview.workflow_eligible">This Purchase Order is controlled by {{ preview.workflow_readiness?.workflow || 'Frappe Workflow' }}.</strong>
				<strong v-else>Standard EdgeSuite submission is not available.</strong>
				<ul><li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li></ul>
			</div>
			<div v-else class="po-submit-review__ready">
				<strong>Ready for standard ERPNext submission.</strong>
				<span>This action submits the existing draft only. It does not create a receipt, invoice, GL Entry or Stock Ledger Entry.</span>
			</div>

			<div v-if="!submitted && preview.workflow_eligible" class="po-submit-review__workflow">
				<strong>{{ preview.workflow_readiness?.message || 'Choose an available workflow action.' }}</strong>
				<div class="po-submit-review__workflow-actions">
					<button
						v-for="action in preview.workflow_readiness?.available_actions || []"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting"
						@click="applyWorkflow(action.action)"
					>
						{{ submitting ? 'Applying…' : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
					</button>
					<span v-if="!(preview.workflow_readiness?.available_actions || []).length">No workflow action is currently available to this user.</span>
				</div>
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
			<p class="po-submit-review__note">Taxes on draft: {{ preview.tax_row_count || 0 }}. Active Purchase Order Workflow is executed through Frappe's permitted transitions; otherwise standard submission uses ERPNext's normal submit path.</p>
		</div>

		<template #footer>
			<div class="po-submit-review__footer">
				<button
					v-if="preview?.can_submit && !preview?.workflow_eligible && !submitted"
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
const WORKFLOW_METHOD = "retailedge.professional_purchase_order_submit.apply_standard_purchase_order_workflow_action";
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
		async applyWorkflow(action) {
			if (!this.preview?.workflow_eligible || !action || this.submitting) return;
			this.submitting = true; this.error = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					purchase_order: this.preview.purchase_order,
					action,
					expected_purchase_order_modified: this.preview.purchase_order_modified,
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
				}, "POST");
				this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder });
				this.submitted = Number(result.docstatus || 0) === 1 ? result : null;
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) { this.error = errorMessage(error, "Unable to apply this Purchase Order workflow action."); }
			finally { this.submitting = false; }
		},
		async submitOrder() {
			if (!this.preview?.can_submit || this.preview?.workflow_eligible || this.submitting) return;
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
.po-submit-review__context div,.po-submit-review__ready,.po-submit-review__blocked,.po-submit-review__success,.po-submit-review__error,.po-submit-review__workflow { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.po-submit-review__context span,.po-submit-review__table small { display:block; opacity:.72; }
.po-submit-review__ready,.po-submit-review__blocked,.po-submit-review__success,.po-submit-review__workflow { display:grid; gap:.5rem; }
.po-submit-review__workflow-actions { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }
.po-submit-review__blocked ul { margin:.35rem 0 0 1.1rem; padding:0; }
.po-submit-review__table td { vertical-align:top; }
.po-submit-review__note { margin:0; font-size:.82rem; opacity:.72; }
.po-submit-review__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:560px) { .po-submit-review__footer { flex-direction:column; } }
</style>
