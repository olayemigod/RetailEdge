<template>
	<EdgeModal
		:open="open"
		title="Review Purchase Receipt"
		subtitle="Review ERPNext's receipt mapping before stock is received."
		size="xl"
		@close="close"
	>
		<EdgeLoadingState v-if="loading" message="Preparing receipt preview..." :skeleton="true" />
		<EdgeErrorState v-else-if="error" title="Receipt action unavailable" :message="error" @retry="loadPreview" />
		<div v-else-if="preview" class="receipt-preview">
			<div class="receipt-preview__context">
				<div><span>Purchase Order</span><strong>{{ preview.purchase_order }}</strong></div>
				<div><span>Supplier</span><strong>{{ preview.supplier_name || preview.supplier }}</strong></div>
				<div><span>Company</span><strong>{{ preview.company }}</strong></div>
				<div><span>Branch</span><strong>{{ preview.branch || 'Company-wide' }}</strong></div>
				<div v-if="preview.purchase_receipt"><span>Purchase Receipt</span><strong>{{ preview.purchase_receipt }}</strong></div>
				<div v-if="preview.workflow_started"><span>Workflow State</span><strong>{{ preview.workflow_readiness?.current_state || '—' }}</strong></div>
			</div>

			<div v-if="preview.blockers?.length" class="receipt-preview__warning" role="alert">
				<strong>Advanced handling required</strong>
				<p>This receipt contains stock controls that RetailEdge will not simplify or bypass.</p>
				<ul><li v-for="(blocker, index) in preview.blockers" :key="`${blocker.key}-${blocker.item_code || index}`">{{ blocker.item_code ? `${blocker.item_code}: ` : '' }}{{ blocker.label }}</li></ul>
			</div>
			<div v-else class="receipt-preview__ready">
				<strong v-if="preview.workflow_controlled && preview.workflow_started">Receipt approval is in progress.</strong>
				<strong v-else>Standard receipt preflight passed.</strong>
				<span v-if="preview.workflow_controlled && !preview.workflow_started">Start Receipt Approval saves one standard Purchase Receipt draft. No stock is posted until Frappe Workflow reaches a submitting state.</span>
				<span v-else-if="preview.workflow_controlled">{{ preview.workflow_readiness?.message || 'Choose an available workflow action.' }}</span>
				<span v-else-if="preview.can_submit">Receive Stock will create and submit the ERPNext Purchase Receipt. ERPNext remains responsible for validation and stock posting.</span>
				<span v-else>You can review this receipt, but your role cannot submit Purchase Receipts.</span>
			</div>

			<div v-if="preview.workflow_started && !preview.blockers?.length" class="receipt-preview__workflow">
				<strong>{{ preview.workflow_readiness?.workflow || 'Purchase Receipt Workflow' }}</strong>
				<span>{{ preview.workflow_readiness?.message || 'Choose an available workflow action.' }}</span>
				<div class="receipt-preview__workflow-actions">
					<button
						v-for="action in preview.workflow_readiness?.available_actions || []"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="posting"
						@click="applyWorkflow(action.action)"
					>
						{{ posting ? 'Applying…' : action.action }}<span v-if="action.next_state"> → {{ action.next_state }}</span>
					</button>
					<span v-if="!(preview.workflow_readiness?.available_actions || []).length">No workflow action is currently available to this user.</span>
				</div>
			</div>

			<div class="table-responsive">
				<table class="table receipt-preview__table">
					<thead><tr><th>Item</th><th class="text-right">Qty to Receive</th><th>UOM</th><th>Receiving Stock Location</th><th>Controls</th></tr></thead>
					<tbody>
						<tr v-for="row in preview.items || []" :key="row.purchase_order_item || row.item_code">
							<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
							<td class="text-right">{{ row.qty }}</td>
							<td>{{ row.uom || row.stock_uom }}</td>
							<td>{{ row.warehouse || 'Not resolved' }}</td>
							<td>{{ controlLabel(row) }}</td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<template #footer>
			<div class="receipt-preview__footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="posting" @click="openAdvanced">Advanced: Prepare in ERPNext</button>
				<div class="receipt-preview__footer-actions">
					<button type="button" class="edge-button" :disabled="posting" @click="close">Close</button>
					<button v-if="canStartWorkflow" type="button" class="edge-button edge-button--primary" :disabled="posting" @click="startWorkflow">{{ posting ? 'Starting…' : 'Start Receipt Approval' }}</button>
					<button v-if="canSubmitStandard" type="button" class="edge-button edge-button--primary" :disabled="posting" @click="confirmSubmit">{{ posting ? 'Receiving Stock...' : 'Receive Stock' }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.professional_purchase_receipt.get_professional_purchase_receipt_preview";
const SUBMIT_METHOD = "retailedge.professional_purchase_receipt.submit_standard_purchase_receipt";
const START_WORKFLOW_METHOD = "retailedge.professional_purchase_receipt.start_standard_purchase_receipt_workflow";
const WORKFLOW_ACTION_METHOD = "retailedge.professional_purchase_receipt.apply_standard_purchase_receipt_workflow_action";
const OPEN_EVENT = "retailedge-open-professional-purchase-receipt-preview";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, ...(type ? { type } : {}), callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalPurchaseReceiptPreviewOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() { return { open: false, purchaseOrder: "", loading: false, posting: false, error: "", preview: null }; },
	computed: {
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE; },
		canSubmitStandard() { return Boolean(this.preview?.standard_receipt_eligible && this.preview?.can_submit && !this.preview?.workflow_controlled); },
		canStartWorkflow() { return Boolean(this.preview?.workflow_controlled && !this.preview?.workflow_started && this.preview?.standard_receipt_eligible && this.preview?.can_start_workflow); },
	},
	created() {
		this._open = (event) => {
			this.purchaseOrder = String(event?.detail?.purchase_order || "").trim();
			if (!this.purchaseOrder) return;
			this.open = true;
			this.loadPreview();
		};
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadPreview() {
			if (!this.purchaseOrder || this.loading || this.posting) return;
			this.loading = true; this.error = ""; this.preview = null;
			try { this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder }); }
			catch (error) { this.error = errorMessage(error, "Unable to preview this Purchase Receipt."); }
			finally { this.loading = false; }
		},
		close() { if (!this.loading && !this.posting) { this.open = false; this.preview = null; this.error = ""; } },
		openAdvanced() {
			if (!this.nativeFallbackEnabled || !this.purchaseOrder || this.posting) return;
			this.close();
			window.dispatchEvent(new CustomEvent("retailedge-advanced-prepare-purchase-receipt", { detail: { purchase_order: this.purchaseOrder } }));
		},
		async startWorkflow() {
			if (!this.canStartWorkflow || this.posting) return;
			this.posting = true; this.error = "";
			try {
				this.preview = await callMethod(START_WORKFLOW_METHOD, {
					purchase_order: this.purchaseOrder,
					expected_purchase_order_modified: this.preview?.purchase_order_modified || "",
				}, "POST");
				frappe.show_alert({ message: __("Purchase Receipt draft created. Continue with the available approval action."), indicator: "green" }, 5);
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) {
				this.error = errorMessage(error, "Unable to start Purchase Receipt approval.");
			} finally {
				this.posting = false;
			}
		},
		async applyWorkflow(action) {
			if (!this.preview?.workflow_started || !action || this.posting) return;
			this.posting = true; this.error = "";
			try {
				const result = await callMethod(WORKFLOW_ACTION_METHOD, {
					purchase_receipt: this.preview.purchase_receipt,
					action,
					expected_purchase_receipt_modified: this.preview.purchase_receipt_modified || "",
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
				}, "POST");
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
				if (Number(result.docstatus || 0) === 1) {
					const receiptName = result.name || this.preview.purchase_receipt || "";
					this.posting = false;
					this.close();
					frappe.show_alert({ message: __(`Purchase Receipt ${receiptName} submitted. Stock has been received.`), indicator: "green" }, 7);
					return;
				}
				this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder });
			} catch (error) {
				this.error = errorMessage(error, "Unable to apply this Purchase Receipt workflow action.");
			} finally {
				this.posting = false;
			}
		},
		confirmSubmit() {
			if (!this.canSubmitStandard || this.posting) return;
			frappe.confirm(
				__("Receive the listed quantities now? This submits an ERPNext Purchase Receipt and posts stock to the shown receiving locations."),
				() => this.submitStandardReceipt(),
			);
		},
		async submitStandardReceipt() {
			if (!this.canSubmitStandard || this.posting) return;
			this.posting = true; this.error = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					purchase_order: this.purchaseOrder,
					expected_purchase_order_modified: this.preview?.purchase_order_modified || "",
				}, "POST");
				this.posting = false;
				this.close();
				frappe.show_alert({ message: __(`Purchase Receipt ${result.name || ''} submitted. Stock has been received.`), indicator: "green" }, 7);
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) {
				this.posting = false;
				this.error = errorMessage(error, "Unable to submit this Purchase Receipt.");
			}
		},
		controlLabel(row) {
			const flags = [];
			if (row.requires_serial_no) flags.push("Serial");
			if (row.requires_batch) flags.push("Batch");
			if (row.requires_quality_inspection) flags.push("Quality Inspection");
			return flags.length ? flags.join(", ") : "Standard";
		},
	},
};
</script>

<style scoped>
.receipt-preview { display: grid; gap: 1rem; }
.receipt-preview__context { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: .75rem; }
.receipt-preview__context div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--border-color, #d1d8dd); border-radius: .5rem; }
.receipt-preview__context span, .receipt-preview__table small { display: block; opacity: .72; }
.receipt-preview__warning, .receipt-preview__ready, .receipt-preview__workflow { padding: .9rem; border: 1px solid var(--border-color, #d1d8dd); border-radius: .5rem; }
.receipt-preview__workflow { display: grid; gap: .5rem; }
.receipt-preview__workflow-actions { display: flex; flex-wrap: wrap; gap: .5rem; align-items: center; }
.receipt-preview__table td { vertical-align: top; }
.receipt-preview__footer { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: .75rem; }
.receipt-preview__footer-actions { display: flex; justify-content: flex-end; gap: .75rem; margin-left: auto; }
</style>
