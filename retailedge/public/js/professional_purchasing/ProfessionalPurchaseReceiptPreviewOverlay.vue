<template>
	<EdgeModal
		:open="open"
		title="Review Purchase Receipt"
		subtitle="Preview ERPNext's standard receipt mapping before any draft or stock movement is created."
		size="xl"
		@close="close"
	>
		<EdgeLoadingState v-if="loading" message="Preparing receipt preview..." :skeleton="true" />
		<EdgeErrorState v-else-if="error" title="Receipt preview unavailable" :message="error" @retry="loadPreview" />
		<div v-else-if="preview" class="receipt-preview">
			<div class="receipt-preview__context">
				<div><span>Purchase Order</span><strong>{{ preview.purchase_order }}</strong></div>
				<div><span>Supplier</span><strong>{{ preview.supplier_name || preview.supplier }}</strong></div>
				<div><span>Company</span><strong>{{ preview.company }}</strong></div>
				<div><span>Branch</span><strong>{{ preview.branch || 'Company-wide' }}</strong></div>
			</div>

			<div v-if="preview.blockers?.length" class="receipt-preview__warning" role="alert">
				<strong>Advanced handling required</strong>
				<p>This receipt contains stock controls that RetailEdge will not simplify or bypass.</p>
				<ul><li v-for="(blocker, index) in preview.blockers" :key="`${blocker.key}-${blocker.item_code || index}`">{{ blocker.item_code ? `${blocker.item_code}: ` : '' }}{{ blocker.label }}</li></ul>
			</div>
			<div v-else class="receipt-preview__ready">
				<strong>Standard receipt preflight passed.</strong>
				<span>No document has been created and no stock has moved. Posting remains disabled until RIR2F2D2.</span>
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
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" @click="openAdvanced">Advanced: Prepare in ERPNext</button>
				<button type="button" class="edge-button edge-button--primary" @click="close">Close Preview</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.professional_purchase_receipt.get_professional_purchase_receipt_preview";
const OPEN_EVENT = "retailedge-open-professional-purchase-receipt-preview";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalPurchaseReceiptPreviewOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() { return { open: false, purchaseOrder: "", loading: false, error: "", preview: null }; },
	computed: {
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE; },
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
			if (!this.purchaseOrder || this.loading) return;
			this.loading = true; this.error = ""; this.preview = null;
			try { this.preview = await callMethod(PREVIEW_METHOD, { purchase_order: this.purchaseOrder }); }
			catch (error) { this.error = errorMessage(error, "Unable to preview this Purchase Receipt."); }
			finally { this.loading = false; }
		},
		close() { if (!this.loading) { this.open = false; this.preview = null; this.error = ""; } },
		openAdvanced() {
			if (!this.nativeFallbackEnabled || !this.purchaseOrder) return;
			this.close();
			window.dispatchEvent(new CustomEvent("retailedge-advanced-prepare-purchase-receipt", { detail: { purchase_order: this.purchaseOrder } }));
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
.receipt-preview__warning, .receipt-preview__ready { padding: .9rem; border: 1px solid var(--border-color, #d1d8dd); border-radius: .5rem; }
.receipt-preview__table td { vertical-align: top; }
.receipt-preview__footer { width: 100%; display: flex; justify-content: space-between; gap: .75rem; }
</style>
