<template>
	<div class="professional-purchasing-extensions">
		<section v-if="capability.can_prepare_incoming_quality" class="edge-panel incoming-quality-panel">
			<div class="quality-heading">
				<div>
					<span class="quality-kicker">Receiving quality control</span>
					<h3>Incoming Quality Inspection</h3>
					<p>Select a saved draft Purchase Receipt, inspect only the rows ERPNext identifies as requiring incoming quality control, then continue readings and submission on the native Quality Inspection forms.</p>
				</div>
				<button v-if="context.purchase_receipt" type="button" class="edge-button edge-button--secondary" @click="openReceipt">Open Purchase Receipt</button>
			</div>

			<div class="quality-source">
				<EdgeLinkField
					v-model="source"
					label="Draft Purchase Receipt"
					placeholder="Search permitted saved draft receipt"
					:searcher="receiptSearch"
					@select="onReceiptSelected"
					@clear="clearReceipt"
				/>
				<p class="quality-help">Submitted and return Purchase Receipts are intentionally excluded from this guided flow. ERPNext remains authoritative for inspection requirements, templates, readings, acceptance and receipt submission gates.</p>
			</div>

			<div v-if="error || notice" class="quality-feedback" :class="{ 'quality-feedback--error': error }">
				<strong>{{ error ? "Quality inspection needs attention" : "Quality inspection prepared" }}</strong>
				<span>{{ error || notice }}</span>
			</div>

			<p v-if="loadingContext" class="quality-loading">Loading ERPNext inspection requirements…</p>

			<div v-else-if="context.purchase_receipt" class="quality-context">
				<div class="quality-context-summary">
					<div><span>Purchase Receipt</span><strong>{{ context.purchase_receipt }}</strong></div>
					<div><span>Supplier</span><strong>{{ context.supplier_name || context.supplier || "—" }}</strong></div>
					<div><span>Eligible rows</span><strong>{{ context.eligible_count || 0 }}</strong></div>
				</div>

				<EdgeEmptyState
					v-if="!context.items || !context.items.length"
					title="No rows need a new incoming inspection"
					description="ERPNext found no uninspected Purchase Receipt rows currently requiring Incoming Quality Inspection."
				/>

				<div v-else class="quality-table-wrap">
					<table class="quality-table">
						<thead>
							<tr><th>Select</th><th>Item</th><th>Accepted Qty</th><th>Warehouse</th><th>Batch / Serial</th><th>Sample Size</th></tr>
						</thead>
						<tbody>
							<tr v-for="row in context.items" :key="row.child_row_reference">
								<td><input type="checkbox" :checked="isSelected(row.child_row_reference)" @change="toggleRow(row.child_row_reference, $event)" /></td>
								<td><strong>{{ row.item_code }}</strong><small>{{ row.item_name || "" }}</small></td>
								<td>{{ formatQty(row.qty) }} {{ row.uom || "" }}</td>
								<td>{{ row.warehouse || "—" }}</td>
								<td>{{ row.batch_no || (row.has_serial_no ? "Serialised" : "—") }}</td>
								<td>
									<input
										type="number"
										class="quality-sample-input"
										:min="0"
										:max="row.qty"
										step="any"
										:value="sampleSizes[row.child_row_reference]"
										@input="setSampleSize(row.child_row_reference, $event)"
									/>
								</td>
							</tr>
						</tbody>
					</table>
				</div>

				<div v-if="context.items && context.items.length" class="quality-actions">
					<span>{{ selectedCount }} selected</span>
					<button type="button" class="edge-button edge-button--primary" :disabled="creating || !selectedCount" @click="createInspections">{{ creating ? "Creating Draft Inspections…" : "Create Draft Quality Inspections" }}</button>
				</div>
			</div>

			<div v-if="created.length" class="quality-created">
				<strong>Created draft Quality Inspections</strong>
				<div class="quality-created-links">
					<button v-for="inspection in created" :key="inspection.name" type="button" class="edge-small-button edge-small-button--primary" @click="openInspection(inspection.name)">{{ inspection.name }}</button>
				</div>
				<p>Enter readings, review acceptance status and submit each Quality Inspection in ERPNext. This guided action never submits the inspection or the Purchase Receipt.</p>
			</div>
		</section>

		<SupplierScorecardGovernance :company="company" :branch="branch" :supplier="supplier" />
	</div>
</template>

<script>
import SupplierScorecardGovernance from "./SupplierScorecardGovernance.vue";

const CAPABILITY_METHOD = "retailedge.incoming_quality_inspection.get_incoming_quality_capability";
const SEARCH_METHOD = "retailedge.incoming_quality_inspection.search_incoming_quality_receipts";
const CONTEXT_METHOD = "retailedge.incoming_quality_inspection.get_incoming_quality_receipt_context";
const CREATE_METHOD = "retailedge.incoming_quality_inspection.create_incoming_quality_inspections";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response?.message ?? response),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc_type || fallback;
}

function linkValue(value) {
	if (typeof value === "string") return value;
	return value?.value || value?.name || "";
}

export default {
	name: "IncomingQualityInspection",
	components: {
		SupplierScorecardGovernance,
		EdgeLinkField: runtimeComponents().EdgeLinkField,
		EdgeEmptyState: runtimeComponents().EdgeEmptyState,
	},
	props: {
		company: { type: String, default: "" },
		branch: { type: String, default: "" },
		supplier: { type: String, default: "" },
	},
	data() {
		return {
			capability: { can_prepare_incoming_quality: false, max_rows: 50 },
			source: "",
			context: {},
			selected: {},
			sampleSizes: {},
			loadingContext: false,
			creating: false,
			error: "",
			notice: "",
			created: [],
		};
	},
	computed: {
		selectedCount() {
			return Object.values(this.selected).filter(Boolean).length;
		},
	},
	watch: {
		company() { this.resetForScopeChange(); },
		branch() { this.resetForScopeChange(); },
		supplier() { this.resetForScopeChange(); },
	},
	async mounted() {
		try {
			this.capability = { ...this.capability, ...(await callMethod(CAPABILITY_METHOD) || {}) };
		} catch (error) {
			this.error = errorMessage(error, "Incoming Quality Inspection capability could not be loaded.");
		}
	},
	methods: {
		async receiptSearch(txt) {
			const result = await callMethod(SEARCH_METHOD, {
				txt,
				company: this.company || null,
				branch: this.branch || null,
				supplier: this.supplier || null,
			});
			return Array.isArray(result) ? result : [];
		},
		async onReceiptSelected(value) {
			this.source = linkValue(value) || this.source;
			await this.loadReceiptContext();
		},
		clearReceipt() {
			this.source = "";
			this.context = {};
			this.selected = {};
			this.sampleSizes = {};
			this.error = "";
			this.notice = "";
			this.created = [];
		},
		resetForScopeChange() {
			if (this.source || this.context.purchase_receipt) this.clearReceipt();
		},
		async loadReceiptContext() {
			if (!this.source || this.loadingContext) return;
			this.loadingContext = true;
			this.error = "";
			this.notice = "";
			try {
				const context = await callMethod(CONTEXT_METHOD, { purchase_receipt: this.source });
				this.context = context || {};
				this.selected = {};
				this.sampleSizes = Object.fromEntries(
					(this.context.items || []).map((row) => [row.child_row_reference, row.suggested_sample_size || ""])
				);
			} catch (error) {
				this.context = {};
				this.error = errorMessage(error, "ERPNext could not load the Purchase Receipt inspection context.");
			} finally {
				this.loadingContext = false;
			}
		},
		isSelected(rowName) {
			return Boolean(this.selected[rowName]);
		},
		toggleRow(rowName, event) {
			this.selected = { ...this.selected, [rowName]: Boolean(event?.target?.checked) };
		},
		setSampleSize(rowName, event) {
			this.sampleSizes = { ...this.sampleSizes, [rowName]: event?.target?.value ?? "" };
		},
		async createInspections() {
			if (!this.source || !this.selectedCount || this.creating) return;
			const selections = (this.context.items || [])
				.filter((row) => this.selected[row.child_row_reference])
				.map((row) => ({
					child_row_reference: row.child_row_reference,
					sample_size: Number(this.sampleSizes[row.child_row_reference]),
				}));
			this.creating = true;
			this.error = "";
			this.notice = "";
			try {
				const result = await callMethod(CREATE_METHOD, {
					purchase_receipt: this.source,
					selections,
				});
				this.created = Array.isArray(result?.created) ? result.created : [];
				this.notice = `${result?.created_count || this.created.length} draft Quality Inspection${(result?.created_count || this.created.length) === 1 ? "" : "s"} created in ERPNext.`;
				await this.loadReceiptContext();
			} catch (error) {
				this.error = errorMessage(error, "ERPNext could not create the draft Quality Inspections.");
			} finally {
				this.creating = false;
			}
		},
		openInspection(name) {
			if (name) frappe.set_route("Form", "Quality Inspection", name);
		},
		openReceipt() {
			const name = this.context.purchase_receipt || this.source;
			if (name) frappe.set_route("Form", "Purchase Receipt", name);
		},
		formatQty(value) {
			const number = Number(value || 0);
			return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : "0";
		},
	},
};
</script>

<style scoped>
.professional-purchasing-extensions { display: grid; gap: 20px; }
.incoming-quality-panel { display: grid; gap: 16px; }
.quality-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.quality-heading h3 { margin: 4px 0 6px; }
.quality-heading p, .quality-help, .quality-created p { margin: 0; opacity: 0.78; line-height: 1.5; }
.quality-kicker { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.72; }
.quality-source { display: grid; gap: 8px; max-width: 720px; }
.quality-feedback { display: grid; gap: 3px; padding: 12px 14px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 10px; }
.quality-feedback--error { border-color: var(--edge-color-danger, var(--red-400)); }
.quality-loading { margin: 0; opacity: 0.72; }
.quality-context { display: grid; gap: 14px; }
.quality-context-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.quality-context-summary > div { display: grid; gap: 3px; padding: 10px 12px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 10px; }
.quality-context-summary span { font-size: 0.78rem; opacity: 0.68; }
.quality-table-wrap { overflow-x: auto; }
.quality-table { width: 100%; border-collapse: collapse; }
.quality-table th, .quality-table td { padding: 10px; border-bottom: 1px solid var(--edge-border-subtle, var(--border-color)); text-align: left; vertical-align: middle; }
.quality-table td small { display: block; margin-top: 2px; opacity: 0.68; }
.quality-sample-input { width: 110px; min-height: 34px; padding: 6px 8px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 8px; background: var(--edge-surface, var(--control-bg)); color: inherit; }
.quality-actions { display: flex; justify-content: flex-end; align-items: center; gap: 12px; }
.quality-created { display: grid; gap: 10px; padding-top: 4px; }
.quality-created-links { display: flex; flex-wrap: wrap; gap: 8px; }
@media (max-width: 800px) {
	.quality-heading { display: grid; }
	.quality-context-summary { grid-template-columns: 1fr; }
	.quality-actions { justify-content: space-between; }
}
</style>
