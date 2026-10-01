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
				<div v-if="submitted.next_actions?.length" class="po-submit-review__next-actions">
					<button
						v-for="action in submitted.next_actions"
						:key="action.value"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting"
						@click="runNextAction(action.value)"
					>
						{{ action.label }}
					</button>
				</div>
			</div>
			<div v-else-if="preview.blockers?.length" class="po-submit-review__blocked">
				<strong v-if="preview.workflow_eligible">This Purchase Order is controlled by {{ preview.workflow_readiness?.workflow || 'Frappe Workflow' }}.</strong>
				<strong v-else>Standard submission is not available.</strong>
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
						:disabled="submitting || saving || draftDirty"
						@click="applyWorkflow(action.action)"
					>
						{{ submitting ? 'Applying…' : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
					</button>
					<span v-if="!(preview.workflow_readiness?.available_actions || []).length">No workflow action is currently available to this user.</span>
				</div>
			</div>

			<section v-if="preview.can_edit && !submitted" class="po-draft-editor">
				<div class="po-draft-editor__heading">
					<div>
						<strong>Edit draft before completion</strong>
						<p>Company, Supplier, Branch, Buying Price List, Stock Location and item identity stay protected. ERPNext recalculates and validates the draft when you save.</p>
					</div>
				</div>
				<div class="po-draft-editor__grid">
					<label><span>Order Date</span><input v-model="draftTransactionDate" class="form-control" type="date" :disabled="saving || submitting" /></label>
					<label><span>Required By</span><input v-model="draftScheduleDate" class="form-control" type="date" :min="draftTransactionDate || undefined" :disabled="saving || submitting" /></label>
					<label class="po-draft-editor__terms"><span>Terms / Notes</span><textarea v-model="draftTerms" class="form-control" rows="2" :disabled="saving || submitting"></textarea></label>
				</div>
				<div class="table-responsive">
					<table class="table po-submit-review__table po-draft-editor__table">
						<thead><tr><th>Item</th><th class="text-right">Qty</th><th>UOM</th><th class="text-right">Rate</th><th>Required</th><th>Stock Location</th></tr></thead>
						<tbody>
							<tr v-for="(row, index) in draftItems" :key="row.name || index">
								<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
								<td><input v-model.number="row.qty" class="form-control text-right" type="number" min="0.000001" step="any" :disabled="saving || submitting" /></td>
								<td>{{ row.uom || '—' }}</td>
								<td><input v-model.number="row.rate" class="form-control text-right" type="number" min="0" step="any" :disabled="saving || submitting" /></td>
								<td><input v-model="row.schedule_date" class="form-control" type="date" :min="draftTransactionDate || undefined" :disabled="saving || submitting" /></td>
								<td>{{ row.warehouse || '—' }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>
			<div v-else class="table-responsive">
				<table class="table po-submit-review__table">
					<thead><tr><th>Item</th><th class="text-right">Qty</th><th>UOM</th><th class="text-right">Rate</th><th class="text-right">Amount</th><th>Required</th><th>Stock Location</th></tr></thead>
					<tbody>
						<tr v-for="row in preview.items || []" :key="[row.name || row.item_code, row.schedule_date, row.warehouse].join('-')">
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
				<div class="po-submit-review__footer-actions">
					<button
						v-if="preview?.can_edit && !submitted"
						type="button"
						class="edge-button"
						:disabled="saving || submitting || !draftDirty || !draftValid"
						@click="saveDraft"
					>
						{{ saving ? 'Saving...' : 'Save Draft Changes' }}
					</button>
					<button
						v-if="preview?.can_submit && !preview?.workflow_eligible && !submitted"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="submitting || saving || draftDirty"
						@click="submitOrder"
					>
						{{ submitting ? 'Submitting...' : 'Submit Purchase Order' }}
					</button>
				</div>
				<button type="button" class="edge-button" :disabled="submitting || saving" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { confirmAboveEdgeModal } from "../retailedge_business_hub/guidedEntryUtils";

const PREVIEW_METHOD = "retailedge.professional_purchase_order_submit.get_purchase_order_submit_preview";
const SUBMIT_METHOD = "retailedge.professional_purchase_order_submit.submit_standard_purchase_order";
const UPDATE_METHOD = "retailedge.professional_purchase_order_submit.update_standard_purchase_order_draft";
const WORKFLOW_METHOD = "retailedge.professional_purchase_order_submit.apply_standard_purchase_order_workflow_action";
const OPEN_EVENT = "retailedge-open-purchase-order-submit";
const OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT = "retailedge-open-professional-purchase-receipt-preview";
const PREPARE_PO_INVOICE_METHOD = "retailedge.professional_purchasing.prepare_purchase_invoice_from_purchase_order";
const PURCHASE_INVOICE_READY_EVENT = "retailedge-professional-purchasing-purchase-invoice-ready";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return window.retailedge?.userErrorMessage?.(error, fallback) || fallback; }

function draftSnapshot(transactionDate, scheduleDate, terms, items) {
	return JSON.stringify({
		transaction_date: transactionDate || "",
		schedule_date: scheduleDate || "",
		terms: terms || "",
		items: (items || []).map((row) => ({
			name: row.name || "",
			qty: Number(row.qty || 0),
			rate: Number(row.rate || 0),
			schedule_date: row.schedule_date || "",
		})),
	});
}

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
			saving: false,
			error: "",
			preview: null,
			submitted: null,
			draftTransactionDate: "",
			draftScheduleDate: "",
			draftTerms: "",
			draftItems: [],
			draftBaseline: "",
		};
	},
	computed: {
		draftDirty() {
			if (!this.preview?.can_edit || this.submitted) return false;
			return draftSnapshot(this.draftTransactionDate, this.draftScheduleDate, this.draftTerms, this.draftItems) !== this.draftBaseline;
		},
		draftValid() {
			if (!this.draftTransactionDate || !this.draftScheduleDate || this.draftScheduleDate < this.draftTransactionDate) return false;
			return this.draftItems.length > 0 && this.draftItems.every((row) =>
				Boolean(row.name) &&
				Number(row.qty || 0) > 0 &&
				Number(row.rate || 0) >= 0 &&
				Boolean(row.schedule_date) &&
				row.schedule_date >= this.draftTransactionDate
			);
		},
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
		resetDraft() {
			this.draftTransactionDate = "";
			this.draftScheduleDate = "";
			this.draftTerms = "";
			this.draftItems = [];
			this.draftBaseline = "";
		},
		hydrateDraft(preview) {
			this.draftTransactionDate = preview?.transaction_date || "";
			this.draftScheduleDate = preview?.schedule_date || preview?.transaction_date || "";
			this.draftTerms = preview?.terms || "";
			this.draftItems = (preview?.items || []).map((row) => ({ ...row }));
			this.draftBaseline = draftSnapshot(this.draftTransactionDate, this.draftScheduleDate, this.draftTerms, this.draftItems);
		},
		async saveDraft() {
			if (!this.preview?.can_edit || !this.draftDirty || !this.draftValid || this.saving || this.submitting) return;
			this.saving = true;
			this.error = "";
			try {
				this.preview = await callMethod(UPDATE_METHOD, {
					purchase_order: this.preview.purchase_order,
					expected_purchase_order_modified: this.preview.purchase_order_modified,
					values: {
						transaction_date: this.draftTransactionDate,
						schedule_date: this.draftScheduleDate,
						terms: this.draftTerms,
						items: this.draftItems.map((row) => ({
							name: row.name,
							qty: Number(row.qty || 0),
							rate: Number(row.rate || 0),
							schedule_date: row.schedule_date,
						})),
					},
				}, "POST");
				this.hydrateDraft(this.preview);
				frappe.show_alert({ message: __("Purchase Order draft changes saved."), indicator: "green" });
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) {
				this.error = errorMessage(error, "Unable to save Purchase Order draft changes.");
			} finally {
				this.saving = false;
			}
		},
		async loadPreview() {
			if (!this.purchaseOrder || this.loading) return;
			this.loading = true; this.error = ""; this.submitted = null;
			try {
				this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder });
				this.hydrateDraft(this.preview);
			} catch (error) { this.error = errorMessage(error, "Unable to review this Purchase Order."); }
			finally { this.loading = false; }
		},
		async applyWorkflow(action) {
			if (!this.preview?.workflow_eligible || !action || this.submitting || this.saving || this.draftDirty) return;
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
				this.hydrateDraft(this.preview);
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) { this.error = errorMessage(error, "Unable to apply this Purchase Order workflow action."); }
			finally { this.submitting = false; }
		},
		async runNextAction(action) {
			if (!this.submitted?.name || !action || this.submitting) return;
			if (action === "receive-stock") {
				const purchaseOrder = this.submitted.name;
				this.close();
				window.dispatchEvent(new CustomEvent(OPEN_PURCHASE_RECEIPT_PREVIEW_EVENT, {
					detail: { purchase_order: purchaseOrder },
				}));
				return;
			}
			if (action === "create-purchase-invoice") {
				this.submitting = true;
				this.error = "";
				try {
					const result = await callMethod(PREPARE_PO_INVOICE_METHOD, { purchase_order: this.submitted.name }, "POST");
					if (!result?.name) throw new Error("Purchase Invoice draft was not returned.");
					this.submitting = false;
					this.close();
					window.dispatchEvent(new CustomEvent(PURCHASE_INVOICE_READY_EVENT, { detail: result }));
				} catch (error) {
					this.error = errorMessage(error, "Unable to prepare a Purchase Invoice from this Purchase Order.");
					this.submitting = false;
				}
			}
		},
		async submitOrder() {
			if (!this.preview?.can_submit || this.preview?.workflow_eligible || this.submitting || this.saving || this.draftDirty) return;
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
		forceClose() {
			this.open = false;
			this.purchaseOrder = "";
			this.preview = null;
			this.submitted = null;
			this.error = "";
			this.resetDraft();
		},
		close() {
			if (this.loading || this.submitting || this.saving) return;
			if (this.draftDirty) {
				confirmAboveEdgeModal(
					__("Discard unsaved Purchase Order changes?"),
					() => this.forceClose(),
				);
				return;
			}
			this.forceClose();
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
.po-submit-review__next-actions { display:flex; gap:.5rem; flex-wrap:wrap; margin-top:.25rem; }
.po-submit-review__workflow-actions { display:flex; flex-wrap:wrap; gap:.5rem; align-items:center; }
.po-submit-review__blocked ul { margin:.35rem 0 0 1.1rem; padding:0; }
.po-submit-review__table td { vertical-align:top; }
.po-draft-editor { display:grid; gap:.8rem; padding:.8rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.po-draft-editor__heading p { margin:.2rem 0 0; opacity:.72; font-size:.82rem; }
.po-draft-editor__grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }
.po-draft-editor__grid label { display:grid; gap:.3rem; font-size:.82rem; font-weight:600; }
.po-draft-editor__terms { grid-column:1 / -1; }
.po-draft-editor__table input { min-width:7rem; }
.po-submit-review__note { margin:0; font-size:.82rem; opacity:.72; }
.po-submit-review__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
.po-submit-review__footer-actions { display:flex; gap:.5rem; flex-wrap:wrap; }
@media (max-width:560px) { .po-submit-review__footer { flex-direction:column; } .po-draft-editor__grid { grid-template-columns:1fr; } .po-draft-editor__terms { grid-column:auto; } }
</style>
