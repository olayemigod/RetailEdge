<template>
	<EdgeModal
		:open="open"
		:title="title"
		:subtitle="subtitle"
		size="xl"
		@close="close"
	>
		<EdgeLoadingState v-if="loading" message="Preparing return review..." :skeleton="true" />
		<EdgeErrorState v-else-if="error" title="Return action unavailable" :message="error" @retry="loadReview" />
		<div v-else-if="review" class="return-review">
			<div class="return-review__context">
				<div><span>Source</span><strong>{{ review.source_name }}</strong></div>
				<div><span>Supplier</span><strong>{{ review.supplier_name || review.supplier }}</strong></div>
				<div><span>Company</span><strong>{{ review.company }}</strong></div>
				<div><span>Branch</span><strong>{{ review.branch || 'Company-wide' }}</strong></div>
				<div v-if="sourceType === 'purchase_invoice'"><span>Update Stock</span><strong>{{ review.update_stock ? 'Yes' : 'No' }}</strong></div>
			</div>

			<div v-if="review.blockers?.length" class="return-review__warning" role="alert">
				<strong>Advanced handling required</strong>
				<p>RetailEdge will not simplify or bypass ERPNext stock controls for this return.</p>
				<ul>
					<li v-for="(blocker, index) in review.blockers" :key="`${blocker.key}-${blocker.item_code || index}`">
						{{ blocker.item_code ? `${blocker.item_code}: ` : '' }}{{ blocker.label }}
					</li>
				</ul>
			</div>
			<div v-else class="return-review__ready">
				<strong>Standard return preflight passed.</strong>
				<span v-if="review.can_submit">Submission will use ERPNext's canonical return document and standard posting lifecycle.</span>
				<span v-else>You can review this return, but your role cannot submit the target document.</span>
			</div>

			<div class="table-responsive">
				<table class="table return-review__table">
					<thead><tr><th>Item</th><th class="text-right">Return Qty</th><th>UOM</th><th>Stock Location</th><th>Controls</th></tr></thead>
					<tbody>
						<tr v-for="(row, index) in review.items || []" :key="row.name || `${row.item_code}-${index}`">
							<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
							<td class="text-right">{{ row.qty }}</td>
							<td>{{ row.uom || '—' }}</td>
							<td>{{ row.warehouse || '—' }}</td>
							<td>{{ controlLabel(row) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<template #footer>
			<div class="return-review__footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="submitting || loading" @click="openAdvanced">
					Advanced: Prepare in ERPNext
				</button>
				<div class="return-review__footer-actions">
					<button type="button" class="edge-button" :disabled="submitting" @click="close">Close</button>
					<button v-if="canSubmitStandard" type="button" class="edge-button edge-button--primary" :disabled="submitting" @click="confirmSubmit">
						{{ submitting ? 'Submitting...' : submitLabel }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const REVIEW_METHOD = "retailedge.professional_purchase_returns.get_purchase_return_review";
const SUBMIT_METHOD = "retailedge.professional_purchase_returns.submit_purchase_return_review";
const PREPARE_PURCHASE_RETURN_METHOD = "retailedge.professional_purchasing.prepare_purchase_return_draft";
const PREPARE_DEBIT_NOTE_METHOD = "retailedge.professional_purchasing.prepare_supplier_debit_note_draft";
const OPEN_EVENT = "retailedge-open-professional-purchase-return-review";
const REFRESH_EVENT = "retailedge-professional-purchasing-page-show";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, ...(type ? { type } : {}), callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalPurchaseReturnReviewOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() {
		return {
			open: false,
			sourceType: "",
			sourceName: "",
			loading: false,
			submitting: false,
			error: "",
			review: null,
		};
	},
	computed: {
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE; },
		isDebitNote() { return this.sourceType === "purchase_invoice"; },
		title() { return this.isDebitNote ? "Review Supplier Debit Note" : "Review Purchase Return"; },
		subtitle() { return this.isDebitNote ? "Review ERPNext's supplier Debit Note mapping before accounting or stock effects are posted." : "Review ERPNext's Purchase Receipt return mapping before stock is posted out."; },
		submitLabel() { return this.isDebitNote ? "Submit Supplier Debit Note" : "Submit Purchase Return"; },
		canSubmitStandard() { return Boolean(this.review?.standard_return_eligible && this.review?.can_submit); },
	},
	created() {
		this._open = (event) => {
			const sourceType = String(event?.detail?.source_type || "").trim();
			const sourceName = String(event?.detail?.source_name || "").trim();
			if (!["purchase_receipt", "purchase_invoice"].includes(sourceType) || !sourceName) return;
			this.sourceType = sourceType;
			this.sourceName = sourceName;
			this.open = true;
			this.loadReview();
		};
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadReview() {
			if (!this.sourceType || !this.sourceName || this.loading || this.submitting) return;
			this.loading = true;
			this.error = "";
			this.review = null;
			try {
				this.review = await callMethod(REVIEW_METHOD, { source_type: this.sourceType, source_name: this.sourceName });
			} catch (error) {
				this.error = errorMessage(error, "Unable to preview this return.");
			} finally {
				this.loading = false;
			}
		},
		close() {
			if (this.loading || this.submitting) return;
			this.open = false;
			this.review = null;
			this.error = "";
		},
		confirmSubmit() {
			if (!this.canSubmitStandard || this.submitting) return;
			const message = this.isDebitNote
				? __("Submit this ERPNext supplier Debit Note now? Standard ERPNext accounting and any enabled stock effects will be posted.")
				: __("Submit this ERPNext Purchase Return now? Standard ERPNext stock posting will return the listed quantities to the supplier.");
			frappe.confirm(message, () => this.submitStandard());
		},
		async submitStandard() {
			if (!this.canSubmitStandard || this.submitting) return;
			this.submitting = true;
			this.error = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					source_type: this.sourceType,
					source_name: this.sourceName,
					expected_source_modified: this.review?.source_modified || "",
				}, "POST");
				this.submitting = false;
				this.close();
				const label = this.isDebitNote ? __("Supplier Debit Note") : __("Purchase Return");
				frappe.show_alert({ message: __(`${label} ${result.name || ''} submitted.`), indicator: "green" }, 7);
				window.dispatchEvent(new CustomEvent(REFRESH_EVENT));
			} catch (error) {
				this.submitting = false;
				this.error = errorMessage(error, "Unable to submit this return.");
			}
		},
		async openAdvanced() {
			if (!this.nativeFallbackEnabled || !this.sourceName || this.submitting || this.loading) return;
			this.submitting = true;
			this.error = "";
			try {
				const method = this.isDebitNote ? PREPARE_DEBIT_NOTE_METHOD : PREPARE_PURCHASE_RETURN_METHOD;
				const args = this.isDebitNote ? { purchase_invoice: this.sourceName } : { purchase_receipt: this.sourceName };
				const result = await callMethod(method, args, "POST");
				this.submitting = false;
				this.close();
				if (result.name) frappe.set_route("Form", result.doctype || (this.isDebitNote ? "Purchase Invoice" : "Purchase Receipt"), result.name);
			} catch (error) {
				this.submitting = false;
				this.error = errorMessage(error, "Unable to prepare the advanced ERPNext return draft.");
			}
		},
		controlLabel(row) {
			const flags = [];
			if (row.requires_serial_no) flags.push("Serial");
			if (row.requires_batch) flags.push("Batch");
			return flags.length ? flags.join(", ") : "Standard";
		},
	},
};
</script>

<style scoped>
.return-review { display: grid; gap: 1rem; }
.return-review__context { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; }
.return-review__context div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--border-color, #d1d8dd); border-radius: .5rem; }
.return-review__context span, .return-review__table small { display: block; opacity: .72; }
.return-review__warning, .return-review__ready { padding: .9rem; border: 1px solid var(--border-color, #d1d8dd); border-radius: .5rem; }
.return-review__table td { vertical-align: top; }
.return-review__footer { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: .75rem; }
.return-review__footer-actions { display: flex; justify-content: flex-end; gap: .75rem; margin-left: auto; }
</style>
