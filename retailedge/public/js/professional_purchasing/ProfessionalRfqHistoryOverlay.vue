<template>
	<EdgeModal
		:open="open"
		title="Request for Quotation History"
		subtitle="Review RFQs within your permitted Company and Branch scope without leaving RetailEdge."
		size="xl"
		@close="close"
	>
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
							<td v-if="nativeFallbackEnabled"><button type="button" class="edge-small-button" @click="openAdvanced(row.name)">Advanced: Open in ERPNext</button></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<template #footer>
			<div class="rfq-history__footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" @click="openAdvancedList">Advanced: RFQs in ERPNext</button>
				<button type="button" class="edge-button edge-button--primary" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const HISTORY_METHOD = "retailedge.professional_sourcing.get_request_for_quotation_history";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const OPEN_EVENT = "retailedge-open-professional-rfq-history";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }
function comparable(value) { if (value === null || value === undefined) return ""; if (typeof value === "number") return value; return String(value).toLowerCase(); }

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
			open: false,
			loading: false,
			loaded: false,
			error: "",
			history: { company: "", branch: "", supplier: "", limit: 50, rows: [] },
			filters: { company: "", branch: "", supplier: "" },
			sort: { key: "transaction_date", direction: "desc" },
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
	created() { this._open = () => { this.open = true; this.loadHistory(); }; },
	mounted() { window.addEventListener(OPEN_EVENT, this._open); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); },
	methods: {
		async loadHistory() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod(HISTORY_METHOD, {
					company: this.filters.company || null,
					branch: this.filters.branch || null,
					supplier: this.filters.supplier || null,
					limit: 50,
				});
				this.history = { ...this.history, ...(result || {}) };
				if (!this.filters.company) this.filters.company = result.company || "";
				if (!this.filters.branch && result.branch) this.filters.branch = result.branch;
				this.loaded = true;
			} catch (error) {
				this.error = errorMessage(error, "Unable to load RFQ history.");
			} finally { this.loading = false; }
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
		sortBy(key) { if (this.sort.key === key) this.sort.direction = this.sort.direction === "asc" ? "desc" : "asc"; else this.sort = { key, direction: "asc" }; },
		sortMark(key) { return this.sort.key === key ? (this.sort.direction === "asc" ? "↑" : "↓") : ""; },
		statusLabel(docstatus) { return Number(docstatus) === 1 ? "Submitted" : Number(docstatus) === 2 ? "Cancelled" : "Draft"; },
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		openAdvanced(name) { if (this.nativeFallbackEnabled && name) frappe.set_route("Form", "Request for Quotation", name); },
		openAdvancedList() { if (this.nativeFallbackEnabled) frappe.set_route("List", "Request for Quotation"); },
		close() { if (!this.loading) { this.open = false; this.error = ""; } },
	},
};
</script>

<style scoped>
.rfq-history { display:grid; gap:1rem; }
.rfq-history__filters { display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)) auto; gap:.75rem; align-items:end; margin-bottom:1rem; }
.rfq-history__scope { display:flex; flex-wrap:wrap; gap:.6rem 1.25rem; font-size:.85rem; opacity:.82; }
.rfq-history__inline-error { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.rfq-history__table td { vertical-align:top; }
.sort-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; text-transform:inherit; letter-spacing:inherit; }
.edge-small-button { min-height:30px; padding:0 9px; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; background:var(--card-bg,#fff); color:inherit; cursor:pointer; white-space:nowrap; }
.rfq-history__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:900px) { .rfq-history__filters { grid-template-columns:1fr 1fr; } }
@media (max-width:560px) { .rfq-history__filters { grid-template-columns:1fr; } .rfq-history__footer { flex-direction:column; } }
</style>
