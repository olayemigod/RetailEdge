<template>
	<EdgeModal
		:open="open"
		title="Prepare Purchase Order"
		subtitle="Review ERPNext's Supplier Quotation mapping before creating a draft Purchase Order."
		size="xl"
		@close="close"
	>
		<EdgeLoadingState v-if="loading && !preview" message="Preparing Purchase Order preview..." :skeleton="true" />
		<EdgeErrorState v-else-if="error && !preview" title="Purchase Order preview unavailable" :message="error" @retry="loadPreview" />
		<div v-else-if="preview" class="quotation-po-preview">
			<div v-if="error" class="quotation-po-preview__error" role="alert">{{ error }}</div>
			<div class="quotation-po-preview__context">
				<div><span>Supplier Quotation</span><strong>{{ preview.supplier_quotation }}</strong></div>
				<div><span>Supplier</span><strong>{{ preview.supplier_name || preview.supplier }}</strong></div>
				<div><span>Company</span><strong>{{ preview.company }}</strong></div>
				<div><span>Branch</span><strong>{{ preview.branch || 'Company-wide' }}</strong></div>
				<div><span>Mapped Total</span><strong>{{ formatMoney(preview.grand_total, preview.currency) }}</strong></div>
				<div><span>Mapped Items</span><strong>{{ preview.item_count || 0 }}</strong></div>
			</div>

			<div v-if="preview.existing_purchase_order" class="quotation-po-preview__blocked">
				<strong>Purchase Order already exists.</strong>
				<span>An active Purchase Order already references this Supplier Quotation. Review the existing order instead of creating a duplicate.</span>
			</div>
			<div v-else-if="created" class="quotation-po-preview__success">
				<strong>Draft Purchase Order {{ created.name }} created.</strong>
				<span>The order remains a draft. Review and submit it through the normal approved purchasing workflow.</span>
			</div>
			<div v-else class="quotation-po-preview__ready">
				<strong>ERPNext mapping preview passed.</strong>
				<span>No Purchase Order has been saved yet. Quotation rates, taxes and item references come from ERPNext's standard mapper.</span>
			</div>

			<div class="table-responsive">
				<table class="table quotation-po-preview__table">
					<thead><tr><th>Item</th><th class="text-right">Qty</th><th>UOM</th><th class="text-right">Rate</th><th class="text-right">Amount</th><th>Required</th><th>Stock Location</th></tr></thead>
					<tbody>
						<tr v-for="row in preview.items || []" :key="row.supplier_quotation_item || row.item_code">
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
			<p class="quotation-po-preview__note">Taxes mapped: {{ preview.tax_row_count || 0 }}. Purchase Order submission is not performed by this action.</p>
		</div>

		<template #footer>
			<div class="quotation-po-preview__footer">
				<button
					v-if="preview && preview.can_create_draft && !created"
					type="button"
					class="edge-button edge-button--primary"
					:disabled="saving"
					@click="createDraft"
				>
					{{ saving ? 'Creating draft...' : 'Create Draft Purchase Order' }}
				</button>
				<span v-else></span>
				<button type="button" class="edge-button" :disabled="saving" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.professional_supplier_quotation_purchase_order.get_supplier_quotation_purchase_order_preview";
const CREATE_METHOD = "retailedge.professional_supplier_quotation_purchase_order.create_purchase_order_draft_from_supplier_quotation";
const OPEN_EVENT = "retailedge-open-supplier-quotation-purchase-order";
const REFRESH_HISTORY_EVENT = "retailedge-refresh-professional-supplier-quotation-history";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalSupplierQuotationPurchaseOrderOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() {
		return {
			open: false,
			supplierQuotation: "",
			loading: false,
			saving: false,
			error: "",
			preview: null,
			created: null,
		};
	},
	created() {
		this._open = (event) => {
			const supplierQuotation = String(event?.detail?.supplier_quotation || "").trim();
			if (!supplierQuotation) return;
			this.supplierQuotation = supplierQuotation;
			this.preview = null;
			this.created = null;
			this.error = "";
			this.open = true;
			this.loadPreview();
		};
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadPreview() {
			if (!this.supplierQuotation || this.loading) return;
			this.loading = true; this.error = ""; this.created = null;
			try {
				this.preview = await callMethod(PREVIEW_METHOD, { supplier_quotation: this.supplierQuotation });
			} catch (error) { this.error = errorMessage(error, "Unable to preview this Supplier Quotation as a Purchase Order."); }
			finally { this.loading = false; }
		},
		async createDraft() {
			if (!this.preview?.can_create_draft || this.saving) return;
			this.saving = true; this.error = "";
			try {
				this.created = await callMethod(CREATE_METHOD, {
					supplier_quotation: this.preview.supplier_quotation,
					expected_supplier_quotation_modified: this.preview.supplier_quotation_modified,
				}, "POST");
				this.preview.can_create_draft = false;
				this.preview.existing_purchase_order = true;
				window.dispatchEvent(new CustomEvent(REFRESH_HISTORY_EVENT));
				window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-page-show"));
			} catch (error) { this.error = errorMessage(error, "Unable to create the draft Purchase Order."); }
			finally { this.saving = false; }
		},
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		formatMoney(value, currency) { try { return format_currency(Number(value || 0), currency || frappe.boot?.sysdefaults?.currency || ""); } catch (_error) { return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim(); } },
		close() {
			if (this.loading || this.saving) return;
			this.open = false;
			this.supplierQuotation = "";
			this.preview = null;
			this.created = null;
			this.error = "";
		},
	},
};
</script>

<style scoped>
.quotation-po-preview { display:grid; gap:1rem; }
.quotation-po-preview__context { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:.75rem; }
.quotation-po-preview__context div,.quotation-po-preview__ready,.quotation-po-preview__blocked,.quotation-po-preview__success,.quotation-po-preview__error { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.quotation-po-preview__context span,.quotation-po-preview__table small { display:block; opacity:.72; }
.quotation-po-preview__blocked,.quotation-po-preview__success,.quotation-po-preview__ready { display:grid; gap:.25rem; }
.quotation-po-preview__table td { vertical-align:top; }
.quotation-po-preview__note { margin:0; font-size:.82rem; opacity:.72; }
.quotation-po-preview__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:560px) { .quotation-po-preview__footer { flex-direction:column; } }
</style>
