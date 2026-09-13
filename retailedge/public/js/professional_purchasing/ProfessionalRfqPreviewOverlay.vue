<template>
	<EdgeModal
		:open="open"
		title="Review Request for Quotation"
		subtitle="Preview ERPNext's sourcing mapping before any RFQ is created or supplier email is sent."
		size="xl"
		@close="close"
	>
		<div class="rfq-preview">
			<div class="rfq-preview__source">
				<span>Purchase Material Request</span>
				<strong>{{ materialRequest }}</strong>
			</div>

			<div v-if="submitted" class="rfq-preview__submitted" role="status">
				<strong>Request for Quotation {{ submitted.name }} submitted in ERPNext.</strong>
				<span>No supplier email was sent. Use RFQ History to review the submitted document.</span>
			</div>

			<template v-else>
				<EdgeLinkField
					v-model="supplierInput"
					label="Add Supplier"
					placeholder="Search permitted supplier"
					:searcher="supplierSearch"
					@select="addSupplier"
					@clear="clearSupplierInput"
				/>
				<div class="supplier-selection">
					<span v-if="!suppliers.length" class="selection-empty">Select at least one supplier.</span>
					<span v-for="supplier in suppliers" :key="supplier.value" class="supplier-chip">
						{{ supplier.label || supplier.value }}
						<button type="button" aria-label="Remove supplier" @click="removeSupplier(supplier.value)">×</button>
					</span>
				</div>

				<div class="rfq-preview__actions">
					<button type="button" class="edge-button edge-button--primary" :disabled="loading || submitting || !suppliers.length" @click="loadPreview">
						{{ loading ? 'Preparing preview…' : 'Preview RFQ' }}
					</button>
				</div>

				<EdgeLoadingState v-if="loading" message="Preparing RFQ preview..." :skeleton="true" />
				<EdgeErrorState v-else-if="error" title="RFQ action unavailable" :message="error" @retry="loadPreview" />
				<div v-else-if="preview" class="rfq-preview__result">
					<div class="rfq-preview__context">
						<div><span>Company</span><strong>{{ preview.company }}</strong></div>
						<div><span>Branch</span><strong>{{ preview.branch || 'Company-wide' }}</strong></div>
						<div><span>Suppliers</span><strong>{{ preview.supplier_count || 0 }}</strong></div>
						<div><span>Items</span><strong>{{ preview.item_count || 0 }}</strong></div>
					</div>
					<div class="rfq-preview__ready">
						<strong>RFQ preflight passed.</strong>
						<span>No RFQ has been saved yet. Standard submission creates and submits the ERPNext RFQ with supplier email explicitly disabled.</span>
					</div>
					<div class="table-responsive">
						<table class="table rfq-preview__table">
							<thead><tr><th>Item</th><th class="text-right">Qty</th><th>UOM</th><th>Required</th><th>Stock Location</th></tr></thead>
							<tbody>
								<tr v-for="row in preview.items || []" :key="row.material_request_item || row.item_code">
									<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
									<td class="text-right">{{ row.qty }}</td>
									<td>{{ row.uom || '—' }}</td>
									<td>{{ formatDate(row.schedule_date) }}</td>
									<td>{{ row.warehouse || '—' }}</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-if="preview.can_submit" class="rfq-preview__submit-note">
						<strong>Ready to submit.</strong>
						<span>This creates a submitted ERPNext Request for Quotation. Supplier email remains off for every selected supplier.</span>
					</div>
					<div v-else class="rfq-preview__submit-note" role="alert">
						<strong>Submission permission required.</strong>
						<span>You can review this preflight, but your ERPNext role cannot submit a Request for Quotation.</span>
					</div>
				</div>
			</template>
		</div>

		<template #footer>
			<div class="rfq-preview__footer">
				<button v-if="nativeFallbackEnabled && preview && !submitted" type="button" class="edge-button" :disabled="submitting" @click="openAdvanced">Advanced: Prepare Draft in ERPNext</button>
				<div class="rfq-preview__footer-actions">
					<button v-if="preview?.can_submit && !submitted" type="button" class="edge-button edge-button--primary" :disabled="loading || submitting" @click="submitStandard">
						{{ submitting ? 'Submitting RFQ…' : 'Create & Submit RFQ' }}
					</button>
					<button type="button" class="edge-button" :class="{ 'edge-button--primary': submitted || !preview?.can_submit }" :disabled="loading || submitting" @click="close">Close</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.professional_sourcing.get_request_for_quotation_preview";
const SUBMIT_METHOD = "retailedge.professional_sourcing.submit_standard_request_for_quotation";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const OPEN_EVENT = "retailedge-open-professional-rfq-preview";
const ADVANCED_EVENT = "retailedge-advanced-prepare-rfq";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function postMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, type: "POST", args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "ProfessionalRfqPreviewOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	data() {
		return {
			open: false,
			materialRequest: "",
			supplierInput: "",
			suppliers: [],
			loading: false,
			submitting: false,
			error: "",
			preview: null,
			submitted: null,
		};
	},
	computed: {
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE; },
	},
	created() {
		this._open = (event) => {
			const materialRequest = String(event?.detail?.material_request || "").trim();
			if (!materialRequest) return;
			this.materialRequest = materialRequest;
			this.supplierInput = "";
			this.suppliers = [];
			this.preview = null;
			this.submitted = null;
			this.error = "";
			this.open = true;
		};
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		formatDate(value, fallback = "—") { if (!value) return fallback; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
		async supplierSearch(txt) {
			const result = await callMethod(SEARCH_METHOD, { kind: "rfq_supplier", txt });
			return Array.isArray(result) ? result : [];
		},
		addSupplier(option) {
			const value = option?.value || "";
			if (!value || this.suppliers.some((supplier) => supplier.value === value)) { this.supplierInput = ""; return; }
			this.suppliers.push({ value, label: option.label || value });
			this.supplierInput = "";
			this.preview = null;
			this.submitted = null;
			this.error = "";
		},
		removeSupplier(value) {
			this.suppliers = this.suppliers.filter((supplier) => supplier.value !== value);
			this.preview = null;
			this.submitted = null;
			this.error = "";
		},
		clearSupplierInput() { this.supplierInput = ""; },
		async loadPreview() {
			if (!this.materialRequest || !this.suppliers.length || this.loading || this.submitting) return;
			this.loading = true;
			this.error = "";
			this.preview = null;
			this.submitted = null;
			try {
				this.preview = await callMethod(PREVIEW_METHOD, {
					material_request: this.materialRequest,
					suppliers: this.suppliers.map((supplier) => supplier.value),
				});
			} catch (error) {
				this.error = errorMessage(error, "Unable to preview this Request for Quotation.");
			} finally {
				this.loading = false;
			}
		},
		async submitStandard() {
			if (!this.preview?.can_submit || this.submitting || this.loading || !this.materialRequest || !this.suppliers.length) return;
			this.submitting = true;
			this.error = "";
			try {
				this.submitted = await postMethod(SUBMIT_METHOD, {
					material_request: this.materialRequest,
					suppliers: this.suppliers.map((supplier) => supplier.value),
					expected_material_request_modified: this.preview.material_request_modified,
				});
				this.preview = null;
			} catch (error) {
				this.error = errorMessage(error, "ERPNext could not submit this Request for Quotation. Refresh the preview and try again.");
			} finally {
				this.submitting = false;
			}
		},
		openAdvanced() {
			if (!this.nativeFallbackEnabled || !this.preview || this.submitting) return;
			window.dispatchEvent(new CustomEvent(ADVANCED_EVENT, {
				detail: {
					material_request: this.materialRequest,
					suppliers: this.suppliers.map((supplier) => supplier.value),
				},
			}));
			this.close();
		},
		close() {
			if (this.loading || this.submitting) return;
			this.open = false;
			this.materialRequest = "";
			this.supplierInput = "";
			this.suppliers = [];
			this.preview = null;
			this.submitted = null;
			this.error = "";
		},
	},
};
</script>

<style scoped>
.rfq-preview { display:grid; gap:1rem; }
.rfq-preview__source { display:grid; gap:.2rem; padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.rfq-preview__source span,.rfq-preview__context span,.rfq-preview__table small,.rfq-preview__submitted span,.rfq-preview__submit-note span { display:block; opacity:.72; }
.supplier-selection { min-height:40px; display:flex; gap:.5rem; flex-wrap:wrap; align-items:center; }
.selection-empty { opacity:.72; }
.supplier-chip { display:inline-flex; gap:.4rem; align-items:center; padding:.35rem .55rem; border:1px solid var(--border-color,#d1d8dd); border-radius:999px; }
.supplier-chip button { border:0; background:transparent; cursor:pointer; }
.rfq-preview__actions { display:flex; justify-content:flex-end; }
.rfq-preview__context { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.75rem; }
.rfq-preview__context div,.rfq-preview__ready,.rfq-preview__submitted,.rfq-preview__submit-note { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.rfq-preview__table td { vertical-align:top; }
.rfq-preview__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
.rfq-preview__footer-actions { display:flex; gap:.75rem; margin-left:auto; }
@media (max-width:560px) { .rfq-preview__footer,.rfq-preview__footer-actions { flex-direction:column; } }
</style>
