<template>
	<div class="professional-purchasing-extensions">
		<section v-if="capability.can_prepare_incoming_quality" class="edge-panel incoming-quality-panel">
			<div class="quality-heading">
				<div>
					<span class="quality-kicker">Receiving quality control</span>
					<h3>Incoming Quality Inspection</h3>
					<p>Review the inspection readings required by ERPNext and submit standard incoming Quality Inspections without leaving RetailEdge.</p>
				</div>
				<button v-if="nativeFallbackEnabled && context.purchase_receipt" type="button" class="edge-button edge-button--secondary" @click="openReceipt">Open Purchase Receipt</button>
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
				<p class="quality-help">ERPNext remains authoritative for inspection requirements, templates, acceptance criteria and final Accepted/Rejected status. Complex or manual inspections stay in Advanced ERPNext.</p>
			</div>

			<div v-if="error || notice" class="quality-feedback" :class="{ 'quality-feedback--error': error }">
				<strong>{{ error ? "Quality inspection needs attention" : "Quality inspection complete" }}</strong>
				<span>{{ error || notice }}</span>
			</div>

			<p v-if="loadingContext" class="quality-loading">Loading ERPNext inspection requirements…</p>

			<div v-else-if="context.purchase_receipt && !review" class="quality-context">
				<div class="quality-context-summary">
					<div><span>Purchase Receipt</span><strong>{{ context.purchase_receipt }}</strong></div>
					<div><span>Supplier</span><strong>{{ context.supplier_name || context.supplier || "—" }}</strong></div>
					<div><span>Eligible rows</span><strong>{{ context.eligible_count || 0 }}</strong></div>
				</div>

				<EdgeEmptyState
					v-if="!context.items || !context.items.length"
					title="No rows need incoming inspection"
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
					<button type="button" class="edge-button edge-button--primary" :disabled="reviewLoading || !selectedCount" @click="reviewInspections">{{ reviewLoading ? "Preparing Review…" : "Review Quality Inspections" }}</button>
				</div>
			</div>

			<div v-if="review" class="quality-review">
				<div class="quality-context-summary">
					<div><span>Purchase Receipt</span><strong>{{ review.purchase_receipt }}</strong></div>
					<div><span>Supplier</span><strong>{{ review.supplier_name || review.supplier || "—" }}</strong></div>
					<div><span>Inspections</span><strong>{{ (review.items || []).length }}</strong></div>
				</div>

				<div v-if="review.blockers && review.blockers.length" class="quality-blockers" role="alert">
					<strong>Advanced handling required</strong>
					<p>RetailEdge will not approximate this inspection.</p>
					<ul><li v-for="(blocker, index) in review.blockers" :key="`${blocker.key}-${index}`">{{ blocker.item_code ? `${blocker.item_code}: ` : "" }}{{ blocker.label }}</li></ul>
				</div>

				<article v-for="item in review.items || []" :key="item.child_row_reference" class="quality-review-card">
					<div class="quality-review-card__heading">
						<div><strong>{{ item.item_code }}</strong><span>{{ item.item_name || "" }}</span></div>
						<div><span>Sample</span><strong>{{ formatQty(item.sample_size) }} / {{ formatQty(item.qty) }} {{ item.uom || "" }}</strong></div>
					</div>
					<p v-if="item.quality_inspection_template" class="quality-template">Template: <strong>{{ item.quality_inspection_template }}</strong></p>
					<div v-for="reading in item.readings || []" :key="`${item.child_row_reference}-${reading.idx}`" class="quality-reading">
						<div class="quality-reading__criteria">
							<strong>{{ reading.specification }}</strong>
							<span v-if="reading.numeric && !reading.formula_based_criteria">Target {{ reading.min_value }} – {{ reading.max_value }}</span>
							<span v-else-if="!reading.numeric && !reading.formula_based_criteria">Expected {{ reading.value || "value" }}</span>
							<span v-else>Formula-based acceptance</span>
						</div>
						<div v-if="reading.numeric" class="quality-reading__inputs">
							<label v-for="number in 10" :key="number">
								<span>Reading {{ number }}</span>
								<input type="text" :value="readingValue(item.child_row_reference, reading.idx, `reading_${number}`)" @input="setReadingValue(item.child_row_reference, reading.idx, `reading_${number}`, $event)" />
							</label>
						</div>
						<label v-else class="quality-reading__value">
							<span>Reading Value</span>
							<input type="text" :value="readingValue(item.child_row_reference, reading.idx, 'reading_value')" @input="setReadingValue(item.child_row_reference, reading.idx, 'reading_value', $event)" />
						</label>
					</div>
				</article>

				<div class="quality-actions quality-actions--review">
					<button type="button" class="edge-button edge-button--secondary" :disabled="submitting || advancedPreparing" @click="cancelReview">Back</button>
					<button v-if="nativeFallbackEnabled" type="button" class="edge-button edge-button--secondary" :disabled="submitting || advancedPreparing" @click="prepareAdvanced">{{ advancedPreparing ? "Preparing…" : "Advanced: Prepare in ERPNext" }}</button>
					<button v-if="canSubmitReview" type="button" class="edge-button edge-button--primary" :disabled="submitting || advancedPreparing" @click="confirmSubmit">{{ submitting ? "Submitting…" : "Submit Quality Inspections" }}</button>
				</div>
			</div>

			<div v-if="submitted.length" class="quality-results">
				<strong>Submitted Quality Inspections</strong>
				<div v-for="inspection in submitted" :key="inspection.name" class="quality-result-row">
					<span>{{ inspection.name }}</span><strong>{{ inspection.status || "Submitted" }}</strong>
					<button v-if="nativeFallbackEnabled" type="button" class="edge-small-button" @click="openInspection(inspection.name)">Open</button>
				</div>
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
const REVIEW_METHOD = "retailedge.incoming_quality_inspection.get_incoming_quality_inspection_review";
const SUBMIT_METHOD = "retailedge.incoming_quality_inspection.submit_incoming_quality_inspection_review";
const CREATE_METHOD = "retailedge.incoming_quality_inspection.create_incoming_quality_inspections";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}, type = undefined) {
	return new Promise((resolve, reject) => frappe.call({ method, args, ...(type ? { type } : {}), callback: (response) => resolve(response?.message ?? response), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc_type || error?.exc || error?._server_messages || fallback; }
function linkValue(value) { if (typeof value === "string") return value; return value?.value || value?.name || ""; }

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
			capability: { can_prepare_incoming_quality: false, can_submit_quality_inspection: false, max_rows: 50 },
			source: "",
			context: {},
			selected: {},
			sampleSizes: {},
			loadingContext: false,
			reviewLoading: false,
			review: null,
			readingValues: {},
			submitting: false,
			advancedPreparing: false,
			error: "",
			notice: "",
			submitted: [],
		};
	},
	computed: {
		selectedCount() { return Object.values(this.selected).filter(Boolean).length; },
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== "edgesuite_only"; },
		canSubmitReview() { return Boolean(this.review?.standard_submit_eligible && this.review?.can_submit && (this.review?.items || []).length); },
	},
	watch: {
		company() { this.resetForScopeChange(); },
		branch() { this.resetForScopeChange(); },
		supplier() { this.resetForScopeChange(); },
	},
	async mounted() {
		try { this.capability = { ...this.capability, ...(await callMethod(CAPABILITY_METHOD) || {}) }; }
		catch (error) { this.error = errorMessage(error, "Incoming Quality Inspection capability could not be loaded."); }
	},
	methods: {
		async receiptSearch(txt) {
			const result = await callMethod(SEARCH_METHOD, { txt, company: this.company || null, branch: this.branch || null, supplier: this.supplier || null });
			return Array.isArray(result) ? result : [];
		},
		async onReceiptSelected(value) { this.source = linkValue(value) || this.source; await this.loadReceiptContext(); },
		clearReceipt() {
			this.source = ""; this.context = {}; this.selected = {}; this.sampleSizes = {}; this.review = null; this.readingValues = {}; this.error = ""; this.notice = ""; this.submitted = [];
		},
		resetForScopeChange() { if (this.source || this.context.purchase_receipt) this.clearReceipt(); },
		async loadReceiptContext() {
			if (!this.source || this.loadingContext) return;
			this.loadingContext = true; this.error = ""; this.notice = "";
			try {
				const context = await callMethod(CONTEXT_METHOD, { purchase_receipt: this.source });
				this.context = context || {}; this.review = null; this.readingValues = {}; this.selected = {};
				this.sampleSizes = Object.fromEntries((this.context.items || []).map((row) => [row.child_row_reference, row.suggested_sample_size || ""]));
			} catch (error) { this.context = {}; this.error = errorMessage(error, "ERPNext could not load the Purchase Receipt inspection context."); }
			finally { this.loadingContext = false; }
		},
		isSelected(rowName) { return Boolean(this.selected[rowName]); },
		toggleRow(rowName, event) { this.selected = { ...this.selected, [rowName]: Boolean(event?.target?.checked) }; },
		setSampleSize(rowName, event) { this.sampleSizes = { ...this.sampleSizes, [rowName]: event?.target?.value ?? "" }; },
		selectedRows() {
			return (this.context.items || []).filter((row) => this.selected[row.child_row_reference]).map((row) => ({ child_row_reference: row.child_row_reference, sample_size: Number(this.sampleSizes[row.child_row_reference]) }));
		},
		async reviewInspections() {
			if (!this.source || !this.selectedCount || this.reviewLoading) return;
			this.reviewLoading = true; this.error = ""; this.notice = ""; this.submitted = [];
			try {
				this.review = await callMethod(REVIEW_METHOD, { purchase_receipt: this.source, selections: this.selectedRows() });
				this.initialiseReadingValues();
			} catch (error) { this.review = null; this.error = errorMessage(error, "ERPNext could not prepare the Quality Inspection review."); }
			finally { this.reviewLoading = false; }
		},
		initialiseReadingValues() {
			const values = {};
			for (const item of this.review?.items || []) {
				values[item.child_row_reference] = {};
				for (const reading of item.readings || []) values[item.child_row_reference][reading.idx] = {};
			}
			this.readingValues = values;
		},
		readingValue(rowName, idx, fieldname) { return this.readingValues?.[rowName]?.[idx]?.[fieldname] ?? ""; },
		setReadingValue(rowName, idx, fieldname, event) {
			const rowValues = { ...(this.readingValues[rowName] || {}) };
			rowValues[idx] = { ...(rowValues[idx] || {}), [fieldname]: event?.target?.value ?? "" };
			this.readingValues = { ...this.readingValues, [rowName]: rowValues };
		},
		submissionRows() {
			return (this.review?.items || []).map((item) => ({
				child_row_reference: item.child_row_reference,
				sample_size: Number(item.sample_size),
				readings: (item.readings || []).map((reading) => ({
					idx: reading.idx,
					specification: reading.specification,
					reading_value: this.readingValue(item.child_row_reference, reading.idx, "reading_value"),
					...Object.fromEntries(Array.from({ length: 10 }, (_, index) => [`reading_${index + 1}`, this.readingValue(item.child_row_reference, reading.idx, `reading_${index + 1}`)])),
				})),
			}));
		},
		cancelReview() { if (this.submitting || this.advancedPreparing) return; this.review = null; this.readingValues = {}; this.error = ""; },
		confirmSubmit() {
			if (!this.canSubmitReview || this.submitting) return;
			frappe.confirm(__("Submit these Quality Inspections now? ERPNext will calculate Accepted/Rejected status from the configured inspection criteria."), () => this.submitInspections());
		},
		async submitInspections() {
			if (!this.canSubmitReview || this.submitting) return;
			this.submitting = true; this.error = ""; this.notice = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, { purchase_receipt: this.source, expected_source_modified: this.review?.source_modified || "", selections: this.submissionRows() }, "POST");
				this.submitted = Array.isArray(result?.created) ? result.created : [];
				this.notice = `${result?.created_count || this.submitted.length} Quality Inspection${(result?.created_count || this.submitted.length) === 1 ? "" : "s"} submitted through ERPNext.`;
				this.review = null; this.readingValues = {}; this.selected = {}; await this.loadReceiptContext();
			} catch (error) { this.error = errorMessage(error, "ERPNext could not submit the Quality Inspections."); }
			finally { this.submitting = false; }
		},
		async prepareAdvanced() {
			if (!this.nativeFallbackEnabled || !this.source || !this.review || this.advancedPreparing) return;
			this.advancedPreparing = true; this.error = "";
			try {
				const result = await callMethod(CREATE_METHOD, { purchase_receipt: this.source, selections: (this.review.items || []).map((item) => ({ child_row_reference: item.child_row_reference, sample_size: Number(item.sample_size) })) }, "POST");
				const first = Array.isArray(result?.created) ? result.created[0] : null;
				this.review = null; this.readingValues = {};
				if (first?.name) this.openInspection(first.name);
			} catch (error) { this.error = errorMessage(error, "ERPNext could not prepare the advanced Quality Inspection drafts."); }
			finally { this.advancedPreparing = false; }
		},
		openInspection(name) { if (!this.nativeFallbackEnabled || !name) return; frappe.set_route("Form", "Quality Inspection", name); },
		openReceipt() { if (!this.nativeFallbackEnabled) return; const name = this.context.purchase_receipt || this.source; if (name) frappe.set_route("Form", "Purchase Receipt", name); },
		formatQty(value) { const number = Number(value || 0); return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 4 }) : "0"; },
	},
};
</script>

<style scoped>
.professional-purchasing-extensions { display: grid; gap: 20px; }
.incoming-quality-panel { display: grid; gap: 16px; }
.quality-heading { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; }
.quality-heading h3 { margin: 4px 0 6px; }
.quality-heading p, .quality-help, .quality-blockers p, .quality-template { margin: 0; opacity: 0.78; line-height: 1.5; }
.quality-kicker { font-size: 0.78rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; opacity: 0.72; }
.quality-source { display: grid; gap: 8px; max-width: 720px; }
.quality-feedback, .quality-blockers { display: grid; gap: 3px; padding: 12px 14px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 10px; }
.quality-feedback--error { border-color: var(--edge-color-danger, var(--red-400)); }
.quality-loading { margin: 0; opacity: 0.72; }
.quality-context, .quality-review, .quality-results { display: grid; gap: 14px; }
.quality-context-summary { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
.quality-context-summary > div { display: grid; gap: 3px; padding: 10px 12px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 10px; }
.quality-context-summary span { font-size: 0.78rem; opacity: 0.68; }
.quality-table-wrap { overflow-x: auto; }
.quality-table { width: 100%; border-collapse: collapse; }
.quality-table th, .quality-table td { padding: 10px; border-bottom: 1px solid var(--edge-border-subtle, var(--border-color)); text-align: left; vertical-align: middle; }
.quality-table td small { display: block; margin-top: 2px; opacity: 0.68; }
.quality-sample-input, .quality-reading input { min-height: 34px; padding: 6px 8px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 8px; background: var(--edge-surface, var(--control-bg)); color: inherit; }
.quality-sample-input { width: 110px; }
.quality-actions { display: flex; justify-content: flex-end; align-items: center; gap: 12px; flex-wrap: wrap; }
.quality-review-card { display: grid; gap: 12px; padding: 14px; border: 1px solid var(--edge-border-subtle, var(--border-color)); border-radius: 10px; }
.quality-review-card__heading { display: flex; justify-content: space-between; gap: 12px; }
.quality-review-card__heading > div { display: grid; gap: 2px; }
.quality-review-card__heading span { opacity: 0.7; font-size: 0.82rem; }
.quality-reading { display: grid; gap: 8px; padding-top: 10px; border-top: 1px solid var(--edge-border-subtle, var(--border-color)); }
.quality-reading__criteria { display: flex; justify-content: space-between; gap: 10px; }
.quality-reading__criteria span { opacity: 0.7; font-size: 0.82rem; }
.quality-reading__inputs { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 8px; }
.quality-reading__inputs label, .quality-reading__value { display: grid; gap: 4px; }
.quality-reading__inputs span, .quality-reading__value span { font-size: 0.78rem; opacity: 0.7; }
.quality-results { padding-top: 4px; }
.quality-result-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center; padding: 8px 0; border-bottom: 1px solid var(--edge-border-subtle, var(--border-color)); }
@media (max-width: 800px) {
	.quality-heading, .quality-review-card__heading, .quality-reading__criteria { display: grid; }
	.quality-context-summary { grid-template-columns: 1fr; }
	.quality-actions { justify-content: space-between; }
}
</style>
