<template>
	<EdgeModal
		:open="open"
		title="Supplier Quotation History"
		subtitle="Review supplier quotations inside your permitted Company and Branch sourcing scope."
		size="xl"
		@close="close"
	>
		<div class="supplier-quote-history__filters">
			<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
			<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
			<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
			<button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="loadHistory">{{ loading ? 'Refreshing...' : 'Apply Filters' }}</button>
		</div>

		<EdgeLoadingState v-if="loading && !loaded" message="Loading Supplier Quotations..." :skeleton="true" />
		<EdgeErrorState v-else-if="error && !loaded" title="Supplier Quotation history unavailable" :message="error" @retry="loadHistory" />
		<div v-else class="supplier-quote-history">
			<div v-if="error" class="supplier-quote-history__error" role="alert">{{ error }}</div>
			<div class="supplier-quote-history__scope">
				<span><strong>Company:</strong> {{ history.company || filters.company || '—' }}</span>
				<span><strong>Branch:</strong> {{ history.branch || 'All permitted' }}</span>
				<span><strong>Supplier:</strong> {{ history.supplier || 'All suppliers' }}</span>
				<span><strong>Showing:</strong> {{ sortedRows.length }} / {{ history.limit || 50 }} max</span>
			</div>
			<p class="supplier-quote-history__note">Restricted users see only quotations attributable to permitted RFQs when Supplier Quotation has no Branch field.</p>

			<EdgeEmptyState v-if="!sortedRows.length" title="No Supplier Quotations" description="No permitted Supplier Quotations match the selected sourcing scope." />
			<div v-else class="table-responsive">
				<table class="table supplier-quote-history__table">
					<thead>
						<tr>
							<th><button type="button" class="sort-button" @click="sortBy('name')">Quotation {{ sortMark('name') }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('transaction_date')">Date {{ sortMark('transaction_date') }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('supplier_name')">Supplier {{ sortMark('supplier_name') }}</button></th>
							<th>RFQ</th>
							<th>Branch</th>
							<th><button type="button" class="sort-button" @click="sortBy('grand_total')">Total {{ sortMark('grand_total') }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('valid_till')">Valid Till {{ sortMark('valid_till') }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('status')">Status {{ sortMark('status') }}</button></th>
							<th>Purchase Order</th>
							<th v-if="nativeFallbackEnabled">Advanced</th>
						</tr>
					</thead>
					<tbody>
						<tr v-for="row in sortedRows" :key="row.name">
							<td><strong>{{ row.name }}</strong><small v-if="row.quotation_number">Supplier ref: {{ row.quotation_number }}</small></td>
							<td>{{ formatDate(row.transaction_date) }}</td>
							<td>{{ row.supplier_name || row.supplier }}</td>
							<td>{{ (row.request_for_quotations || []).join(', ') || '—' }}</td>
							<td>{{ row.branch || '—' }}</td>
							<td>{{ formatMoney(row.grand_total, row.currency) }}</td>
							<td>{{ formatDate(row.valid_till) }}</td>
							<td>{{ row.status || 'Draft' }}</td>
							<td><button v-if="canPreparePurchaseOrder(row)" type="button" class="edge-small-button edge-small-button--primary" @click="preparePurchaseOrder(row.name)">Prepare PO</button><span v-else>—</span></td>
							<td v-if="nativeFallbackEnabled"><button type="button" class="edge-small-button" @click="openAdvanced(row.name)">Advanced: Open in ERPNext</button></td>
						</tr>
					</tbody>
				</table>
			</div>
		</div>

		<template #footer>
			<div class="supplier-quote-history__footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" @click="openAdvancedList">Advanced: Supplier Quotations in ERPNext</button>
				<button type="button" class="edge-button edge-button--primary" @click="close">Close</button>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const HISTORY_METHOD = "retailedge.professional_supplier_quotation.get_supplier_quotation_history";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const OPEN_EVENT = "retailedge-open-professional-supplier-quotation-history";
const PREPARE_PO_EVENT = "retailedge-open-supplier-quotation-purchase-order";
const REFRESH_EVENT = "retailedge-refresh-professional-supplier-quotation-history";
const ACCESS_MODE = "edgesuite_only";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }
function comparable(value) { if (value === null || value === undefined) return ""; if (typeof value === "number") return value; return String(value).toLowerCase(); }

export default {
	name: "ProfessionalSupplierQuotationHistoryOverlay",
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
	created() {
		this._open = () => { this.open = true; this.loadHistory(); };
		this._refresh = () => { if (this.open) this.loadHistory(); };
	},
	mounted() { window.addEventListener(OPEN_EVENT, this._open); window.addEventListener(REFRESH_EVENT, this._refresh); },
	beforeUnmount() { window.removeEventListener(OPEN_EVENT, this._open); window.removeEventListener(REFRESH_EVENT, this._refresh); },
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
			} catch (error) { this.error = errorMessage(error, "Unable to load Supplier Quotation history."); }
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
		canPreparePurchaseOrder(row) {
			const status = String(row?.status || "");
			return Number(row?.docstatus || 0) === 1 && !["Cancelled", "Stopped", "Expired"].includes(status);
		},
		preparePurchaseOrder(name) { if (name) window.dispatchEvent(new CustomEvent(PREPARE_PO_EVENT, { detail: { supplier_quotation: name } })); },
		sortBy(key) { if (this.sort.key === key) this.sort.direction = this.sort.direction === "asc" ? "desc" : "asc"; else this.sort = { key, direction: "asc" }; },
		sortMark(key) { return this.sort.key === key ? (this.sort.direction === "asc" ? "↑" : "↓") : ""; },
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		formatMoney(value, currency) { try { return format_currency(Number(value || 0), currency || frappe.boot?.sysdefaults?.currency || ""); } catch (_error) { return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim(); } },
		openAdvanced(name) { if (this.nativeFallbackEnabled && name) frappe.set_route("Form", "Supplier Quotation", name); },
		openAdvancedList() { if (this.nativeFallbackEnabled) frappe.set_route("List", "Supplier Quotation"); },
		close() { if (!this.loading) { this.open = false; this.error = ""; } },
	},
};
</script>

<style scoped>
.supplier-quote-history { display:grid; gap:1rem; }
.supplier-quote-history__filters { display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)) auto; gap:.75rem; align-items:end; margin-bottom:1rem; }
.supplier-quote-history__scope { display:flex; flex-wrap:wrap; gap:.6rem 1.25rem; font-size:.85rem; opacity:.82; }
.supplier-quote-history__note { margin:0; font-size:.82rem; opacity:.72; }
.supplier-quote-history__error { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.supplier-quote-history__table td { vertical-align:top; }
.supplier-quote-history__table small { display:block; opacity:.72; }
.sort-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; text-transform:inherit; letter-spacing:inherit; }
.edge-small-button { min-height:30px; padding:0 9px; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; background:var(--card-bg,#fff); color:inherit; cursor:pointer; white-space:nowrap; }
.edge-small-button--primary { font-weight:600; }
.supplier-quote-history__footer { width:100%; display:flex; justify-content:space-between; gap:.75rem; }
@media (max-width:900px) { .supplier-quote-history__filters { grid-template-columns:1fr 1fr; } }
@media (max-width:560px) { .supplier-quote-history__filters { grid-template-columns:1fr; } .supplier-quote-history__footer { flex-direction:column; } }
</style>
