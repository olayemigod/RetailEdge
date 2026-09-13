<template>
	<EdgeModal
		:open="open"
		:title="capture.active ? 'Record Supplier Quotation' : 'Request for Quotation History'"
		:subtitle="capture.active ? 'Record a supplier response against the submitted RFQ using ERPNext quotation truth.' : 'Review RFQs within your permitted Company and Branch scope without leaving RetailEdge.'"
		size="xl"
		@close="close"
	>
		<template v-if="capture.active">
			<EdgeLoadingState v-if="capture.loading && !capture.loaded" message="Preparing Supplier Quotation review..." :skeleton="true" />
			<EdgeErrorState v-else-if="capture.error && !capture.loaded" title="Supplier Quotation capture unavailable" :message="capture.error" @retry="loadCapturePreview" />
			<div v-else class="quote-capture">
				<div v-if="capture.created" class="quote-capture__success">
					<strong>Supplier Quotation {{ capture.created.name }} submitted.</strong>
					<span>ERPNext recorded the quotation and updated the RFQ supplier response status through its standard submit logic.</span>
					<span v-if="capture.created.grand_total !== undefined">Total: {{ formatMoney(capture.created.grand_total, capture.created.currency) }}</span>
				</div>
				<template v-else>
					<div class="quote-capture__scope">
						<span><strong>RFQ:</strong> {{ capture.preview.request_for_quotation || capture.rfq }}</span>
						<span><strong>Company:</strong> {{ capture.preview.company || '—' }}</span>
						<span><strong>Branch:</strong> {{ capture.preview.branch || 'Unassigned' }}</span>
						<span><strong>Currency:</strong> {{ capture.preview.currency || 'Select supplier' }}</span>
					</div>

					<div class="quote-capture__form">
						<label class="quote-field">
							<span>Supplier</span>
							<select v-model="capture.supplier" class="edge-input" :disabled="capture.saving" @change="onCaptureSupplierChanged">
								<option value="">Choose supplier</option>
								<option v-for="option in capture.preview.suppliers || []" :key="option.value" :value="option.value">{{ option.label || option.value }}</option>
							</select>
						</label>
						<label class="quote-field"><span>Quotation Date</span><input v-model="capture.transaction_date" class="edge-input" type="date" :disabled="capture.saving" /></label>
						<label class="quote-field"><span>Valid Till</span><input v-model="capture.valid_till" class="edge-input" type="date" :disabled="capture.saving" /></label>
						<label class="quote-field"><span>Supplier Reference</span><input v-model.trim="capture.quotation_number" class="edge-input" type="text" :disabled="capture.saving" placeholder="Optional quote/reference number" /></label>
					</div>

					<div v-if="capture.loading" class="quote-capture__notice">Refreshing mapped RFQ details...</div>
					<div v-if="capture.error" class="quote-capture__error" role="alert">{{ capture.error }}</div>
					<div v-if="(capture.preview.blockers || []).length" class="quote-capture__blockers" role="alert">
						<strong>This quotation cannot use the standard RetailEdge path:</strong>
						<ul><li v-for="message in capture.preview.blockers" :key="message">{{ message }}</li></ul>
					</div>

					<div v-if="(capture.preview.items || []).length" class="table-responsive">
						<table class="table quote-capture__table">
							<thead><tr><th>Item</th><th class="num">Qty</th><th>UOM</th><th class="num">Quoted Rate</th><th class="num">Line Total</th></tr></thead>
							<tbody>
								<tr v-for="item in capture.preview.items" :key="item.request_for_quotation_item">
									<td><strong>{{ item.item_code }}</strong><small>{{ item.item_name || item.description || item.request_for_quotation_item }}</small></td>
									<td class="num">{{ formatQty(item.qty) }}</td>
									<td>{{ item.uom || '—' }}</td>
									<td class="num"><input v-model.number="capture.rates[item.request_for_quotation_item]" class="edge-input quote-rate-input" type="number" min="0" step="0.01" :disabled="capture.saving" /></td>
									<td class="num">{{ formatMoney(Number(item.qty || 0) * Number(capture.rates[item.request_for_quotation_item] || 0), capture.preview.currency) }}</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div class="quote-capture__safety">
						<strong>Standard RFQ response only.</strong>
						<span>RetailEdge uses ERPNext's RFQ → Supplier Quotation mapper, preserves RFQ item lineage, inserts the native quotation and calls normal ERPNext submit. It does not post GL or Stock Ledger. Ad-hoc quotations, subcontracting, active approval Workflows, extra items, or special tax/currency edits remain Advanced ERPNext.</span>
					</div>
				</template>
			</div>
		</template>

		<template v-else>
			<div class="rfq-history__filters">
				<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
				<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
				<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
				<button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="loadHistory">{{ loading ? 'Refreshing...' : 'Apply Filters' }}</button>
			</div>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading RFQ history..." :skeleton="true" />
			<EdgeErrorState v-else-if="error && !loaded" title="RFQ history unavailable" :message="error" @retry="loadHistory" />
			<div v-else class="rfq-history">
				<div v-if="error" class="rfq-history__inline-error" role="alert">{{ error }}</div>
				<div class="rfq-history__scope">
					<span><strong>Company:</strong> {{ history.company || filters.company || '—' }}</span>
					<span><strong>Branch:</strong> {{ history.branch || 'All permitted' }}</span>
					<span><strong>Supplier:</strong> {{ history.supplier || 'All suppliers' }}</span>
					<span><strong>Showing:</strong> {{ sortedRows.length }} / {{ history.limit || 50 }} max</span>
				</div>

				<EdgeEmptyState v-if="!sortedRows.length" title="No Requests for Quotation" description="No permitted RFQs match the selected scope." />
				<div v-else class="table-responsive">
					<table class="table rfq-history__table">
						<thead>
							<tr>
								<th><button type="button" class="sort-button" @click="sortBy('name')">RFQ {{ sortMark('name') }}</button></th>
								<th><button type="button" class="sort-button" @click="sortBy('transaction_date')">Date {{ sortMark('transaction_date') }}</button></th>
								<th>Suppliers</th>
								<th><button type="button" class="sort-button" @click="sortBy('item_count')">Items {{ sortMark('item_count') }}</button></th>
								<th>Branch</th>
								<th><button type="button" class="sort-button" @click="sortBy('status')">Status {{ sortMark('status') }}</button></th>
								<th>Actions</th>
								<th v-if="nativeFallbackEnabled">Advanced</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in sortedRows" :key="row.name">
								<td><strong>{{ row.name }}</strong></td>
								<td>{{ formatDate(row.transaction_date || row.modified) }}</td>
								<td>{{ (row.suppliers || []).join(', ') || '—' }}</td>
								<td>{{ row.item_count || 0 }}</td>
								<td>{{ row.branch || '—' }}</td>
								<td>{{ row.status || statusLabel(row.docstatus) }}</td>
								<td><button v-if="canRecordQuote(row)" type="button" class="edge-small-button edge-small-button--primary" @click="startQuoteCapture(row)">Record Supplier Quote</button><span v-else>—</span></td>
								<td v-if="nativeFallbackEnabled"><button type="button" class="edge-small-button" @click="openAdvanced(row.name)">Advanced: Open in ERPNext</button></td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>
		</template>

		<template #footer>
			<div v-if="capture.active" class="rfq-history__footer">
				<button type="button" class="edge-button" :disabled="capture.saving" @click="leaveCapture">{{ capture.created ? 'Back to RFQ History' : 'Cancel' }}</button>
				<button v-if="!capture.created" type="button" class="edge-button edge-button--primary" :disabled="!capture.preview.can_record || capture.loading || capture.saving" @click="recordAndSubmitQuote">{{ capture.saving ? 'Recording...' : 'Record & Submit Supplier Quotation' }}</button>
			</div>
			<div v-else class="rfq-history__footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" @click="openAdvancedList">Advanced: RFQs in ERPNext</button>
				<button type="button" class="edge-button edge-button--primary" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const HISTORY_METHOD = "retailedge.professional_sourcing.get_request_for_quotation_history";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const CAPTURE_PREVIEW_METHOD = "retailedge.professional_supplier_quotation_capture.get_supplier_quotation_capture_preview";
const CAPTURE_RECORD_METHOD = "retailedge.professional_supplier_quotation_capture.record_submitted_supplier_quotation_from_rfq";
const OPEN_EVENT = "retailedge-open-professional-rfq-history";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }
function comparable(value) { if (value === null || value === undefined) return ""; if (typeof value === "number") return value; return String(value).toLowerCase(); }
function emptyCapture() {
	return {
		active: false, rfq: "", supplier: "", loading: false, loaded: false, saving: false, error: "", preview: {}, rates: {},
		transaction_date: "", valid_till: "", quotation_number: "", created: null,
	};
}

export default {
	name: "ProfessionalRfqHistoryOverlay",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
		EdgeEmptyState: runtime.EdgeEmptyState,
	},
	data() {
		return {
			open: false, loading: false, loaded: false, error: "",
			history: { company: "", branch: "", supplier: "", limit: 50, rows: [] },
			filters: { company: "", branch: "", supplier: "" },
			sort: { key: "transaction_date", direction: "desc" },
			capture: emptyCapture(),
		};
	},
	computed: {
		nativeFallbackEnabled() { return frappe.boot?.edgesuite_ui_access?.mode !== ACCESS_MODE; },
		sortedRows() {
			const rows = [...(this.history.rows || [])];
			const { key, direction } = this.sort;
			return rows.sort((left, right) => {
				const a = comparable(left?.[key]); const b = comparable(right?.[key]);
				if (a === b) return 0;
				const result = a > b ? 1 : -1;
				return direction === "asc" ? result : -result;
			});
		},
	},
	created() { this._open = () => { this.capture = emptyCapture(); this.open = true; this.loadHistory(); }; },
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadHistory() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod(HISTORY_METHOD, {
					company: this.filters.company || null, branch: this.filters.branch || null, supplier: this.filters.supplier || null, limit: 50,
				});
				this.history = { ...this.history, ...(result || {}) };
				if (!this.filters.company) this.filters.company = result.company || "";
				if (!this.filters.branch && result.branch) this.filters.branch = result.branch;
				this.loaded = true;
			} catch (error) { this.error = errorMessage(error, "Unable to load RFQ history."); }
			finally { this.loading = false; }
		},
		async searchOptions(kind, txt) {
			const result = await callMethod(SEARCH_METHOD, { kind, txt, company: this.filters.company || null });
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		supplierSearch(txt) { return this.searchOptions("supplier", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.supplier = ""; this.loaded = false; this.loadHistory(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.loaded = false; this.loadHistory(); },
		clearBranch() { this.filters.branch = ""; this.loaded = false; this.loadHistory(); },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.loaded = false; this.loadHistory(); },
		clearSupplier() { this.filters.supplier = ""; this.loaded = false; this.loadHistory(); },
		canRecordQuote(row) { return Number(row?.docstatus || 0) === 1 && Array.isArray(row?.suppliers) && row.suppliers.length > 0; },
		async startQuoteCapture(row) {
			if (!this.canRecordQuote(row)) return;
			this.capture = { ...emptyCapture(), active: true, rfq: row.name, transaction_date: frappe.datetime.get_today() };
			await this.loadCapturePreview();
		},
		async loadCapturePreview() {
			if (!this.capture.rfq || this.capture.loading) return;
			this.capture.loading = true; this.capture.error = "";
			try {
				const result = await callMethod(CAPTURE_PREVIEW_METHOD, { request_for_quotation: this.capture.rfq, supplier: this.capture.supplier || null });
				this.capture.preview = result || {};
				this.capture.loaded = true;
				if (!this.capture.supplier && (result.suppliers || []).length === 1) {
					this.capture.supplier = result.suppliers[0].value;
					this.capture.loading = false;
					await this.loadCapturePreview();
					return;
				}
				if (!this.capture.transaction_date) this.capture.transaction_date = result.transaction_date || frappe.datetime.get_today();
				this.capture.rates = Object.fromEntries((result.items || []).map((item) => [item.request_for_quotation_item, Number(item.rate || 0)]));
			} catch (error) { this.capture.error = errorMessage(error, "Unable to prepare the Supplier Quotation review."); this.capture.loaded = true; }
			finally { this.capture.loading = false; }
		},
		onCaptureSupplierChanged() { this.capture.preview = {}; this.capture.rates = {}; this.capture.loaded = false; this.loadCapturePreview(); },
		async recordAndSubmitQuote() {
			if (!this.capture.preview.can_record || this.capture.saving) return;
			this.capture.saving = true; this.capture.error = "";
			try {
				const itemRates = (this.capture.preview.items || []).map((item) => ({ request_for_quotation_item: item.request_for_quotation_item, rate: Number(this.capture.rates[item.request_for_quotation_item] || 0) }));
				const result = await callMethod(CAPTURE_RECORD_METHOD, {
					request_for_quotation: this.capture.rfq,
					supplier: this.capture.supplier,
					expected_rfq_modified: this.capture.preview.expected_rfq_modified,
					item_rates: itemRates,
					transaction_date: this.capture.transaction_date || null,
					valid_till: this.capture.valid_till || null,
					quotation_number: this.capture.quotation_number || null,
				}, "POST");
				this.capture.created = result || {};
				window.dispatchEvent(new CustomEvent("retailedge-refresh-professional-supplier-quotation-history"));
			} catch (error) { this.capture.error = errorMessage(error, "ERPNext could not record and submit the Supplier Quotation."); }
			finally { this.capture.saving = false; }
		},
		leaveCapture() { if (this.capture.saving) return; this.capture = emptyCapture(); this.loadHistory(); },
		sortBy(key) { if (this.sort.key === key) this.sort.direction = this.sort.direction === "asc" ? "desc" : "asc"; else this.sort = { key, direction: "asc" }; },
		sortMark(key) { return this.sort.key === key ? (this.sort.direction === "asc" ? "↑" : "↓") : ""; },
		statusLabel(docstatus) { return Number(docstatus) === 1 ? "Submitted" : Number(docstatus) === 2 ? "Cancelled" : "Draft"; },
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		formatQty(value) { return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 4 }); },
		formatMoney(value, currency) { try { return format_currency(Number(value || 0), currency || frappe.boot?.sysdefaults?.currency || ""); } catch (_error) { return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim(); } },
		openAdvanced(name) { if (this.nativeFallbackEnabled && name) frappe.set_route("Form", "Request for Quotation", name); },
		openAdvancedList() { if (this.nativeFallbackEnabled) frappe.set_route("List", "Request for Quotation"); },
		close() { if (this.loading || this.capture.saving) return; if (this.capture.active) { this.leaveCapture(); return; } this.open = false; this.error = ""; },
	},
};
</script>

<style scoped>
.rfq-history, .quote-capture { display:grid; gap:1rem; }
.rfq-history__filters { display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)) auto; gap:.75rem; align-items:end; margin-bottom:1rem; }
.rfq-history__scope, .quote-capture__scope { display:flex; flex-wrap:wrap; gap:.6rem 1.25rem; font-size:.85rem; opacity:.82; }
.rfq-history__inline-error, .quote-capture__error, .quote-capture__blockers, .quote-capture__notice, .quote-capture__success, .quote-capture__safety { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.quote-capture__success, .quote-capture__safety { display:grid; gap:.35rem; }
.quote-capture__form { display:grid; grid-template-columns:repeat(4,minmax(150px,1fr)); gap:.75rem; }
.quote-field { display:grid; gap:.35rem; font-size:.85rem; }
.quote-capture__table td, .rfq-history__table td { vertical-align:top; }
.quote-capture__table small { display:block; opacity:.72; }
.quote-rate-input { min-width:110px; text-align:right; }
.num { text-align:right; }
.sort-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; text-transform:inherit; letter-spacing:inherit; }
.edge-small-button { min-height:30px; padding:0 9px; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; background:var(--card-bg,#fff); color:inherit; cursor:pointer; white-space:nowrap; }
.edge-small-button--primary { font-weight:600; }
.rfq-history__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:900px) { .rfq-history__filters, .quote-capture__form { grid-template-columns:1fr 1fr; } }
@media (max-width:560px) { .rfq-history__filters, .quote-capture__form { grid-template-columns:1fr; } .rfq-history__footer { flex-direction:column; } }
</style>
