<template>
	<div v-if="!edgeUIValid" class="receipt-history-fallback">
		<strong>Purchase Receipt History could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Purchase Receipt History"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/purchase-receipt-history"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="purchase-receipt-history-page">
			<EdgePageHeader
				title="Purchase Receipt History"
				description="Review submitted ERPNext Purchase Receipts with persistent filters and pagination. Continue supplier billing without loading a growing history list into a popup."
			/>

			<section class="edge-panel history-controls">
				<div class="history-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
					<label class="history-input"><span>Search</span><input v-model="filters.search" type="search" placeholder="Receipt or supplier" @keyup.enter="applyFilters" /></label>
					<EdgeSmartDateRange
						v-model="smartDate"
						class="history-period-filter"
						label="Period"
						placeholder="e.g. last 30 days, May to June 2026, YTD"
						:referenceDate="smartDateReference || null"
						dateOrder="DMY"
						@resolved="onSmartDateResolved"
					/>
				</div>
				<div class="history-control-actions">
					<button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Refreshing…" : "Apply Filters" }}</button>
					<button type="button" class="edge-button" :disabled="loading" @click="clearOptionalFilters">Clear Optional Filters</button>
					<button type="button" class="edge-button" @click="backToPurchasing">Back to Purchasing</button>
				</div>
			</section>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading Purchase Receipt history..." :skeleton="true" />
			<EdgeErrorState v-else-if="error && !loaded" title="Receipt history unavailable" :message="error" @retry="applyFilters" />
			<section v-else class="edge-panel receipt-history">
				<div v-if="error" class="history-inline-error" role="alert">{{ error }}</div>
				<div class="history-scope">
					<span><strong>Company:</strong> {{ history.company || filters.company || "—" }}</span>
					<span><strong>Branch:</strong> {{ history.branch || "All permitted" }}</span>
					<span><strong>Supplier:</strong> {{ history.supplier || "All suppliers" }}</span>
					<span><strong>Loaded:</strong> {{ rows.length }}</span>
				</div>

				<EdgeEmptyState v-if="!rows.length" title="No submitted Purchase Receipts" description="No permitted submitted non-return receipts match the selected filters." />
				<div v-else class="table-responsive">
					<table class="table receipt-history-table">
						<thead><tr>
							<th>Receipt</th><th>Date</th><th>Supplier</th><th>Purchase Order</th><th class="num">Qty</th><th>Branch</th><th>Status</th><th>Actions</th>
						</tr></thead>
						<tbody>
							<tr v-for="row in rows" :key="row.name">
								<td><strong>{{ row.name }}</strong></td>
								<td>{{ formatDate(row.posting_date) }}</td>
								<td>{{ row.supplier_name || row.supplier }}</td>
								<td>{{ (row.purchase_orders || []).join(", ") || "—" }}</td>
								<td class="num">{{ formatQty(row.total_qty) }}</td>
								<td>{{ row.branch || "—" }}</td>
								<td>{{ row.status || "Submitted" }}</td>
								<td>
									<div class="row-actions">
										<button type="button" class="edge-small-button" @click="openDocumentOutput(row.name)">Print & Share</button>
										<button v-if="row.can_prepare_invoice" type="button" class="edge-small-button edge-small-button--primary" :disabled="preparingInvoice === row.name" @click="prepareInvoice(row)">{{ preparingInvoice === row.name ? "Preparing…" : "Create Invoice" }}</button>
										<button v-if="canUseNativeDesk" type="button" class="edge-small-button" @click="openAdvancedReceipt(row.name)">Advanced: ERPNext</button>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>

				<div class="history-pagination">
					<span>{{ history.has_more ? "More receipts are available." : (rows.length ? "End of matching receipts." : "") }}</span>
					<button v-if="history.has_more" type="button" class="edge-button edge-button--primary" :disabled="loadingMore" @click="loadMore">{{ loadingMore ? "Loading…" : "Load More" }}</button>
				</div>
			</section>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import { openDocumentOutputSharing } from "../documentOutputNavigation";

const HISTORY_METHOD = "retailedge.professional_purchase_receipt.get_professional_purchase_receipt_history";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const PREPARE_INVOICE_METHOD = "retailedge.professional_purchasing.prepare_purchase_invoice_from_purchase_receipt";
const PAGE_SIZE = 40;
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeSmartDateRange"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }

export default {
	name: "PurchaseReceiptHistoryPage",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			tenantName: "",
			branchName: "",
			userName: "",
			menuItems: [],
			canUseNativeDesk: false,
			loading: false,
			loadingMore: false,
			loaded: false,
			error: "",
			preparingInvoice: "",
			smartDate: {},
			smartDateReference: window.frappe?.datetime?.get_today?.() || "",
			filters: { company: "", branch: "", supplier: "", search: "", from_date: "", to_date: "" },
			history: { receipts: [], has_more: false, next_start: 0 },
		};
	},
	computed: {
		rows() { return Array.isArray(this.history.receipts) ? this.history.receipts : []; },
	},
	created() {
		this.edgeUIValid = REQUIRED_COMPONENTS.every((name) => Boolean(runtimeComponents()[name]));
	},
	mounted() {
		if (!this.edgeUIValid) return;
		this.loadShellAndHistory();
		this._showHandler = () => { if (this.loaded) this.applyFilters(); };
		window.addEventListener("retailedge-purchase-receipt-history-page-show", this._showHandler);
	},
	beforeUnmount() { if (this._showHandler) window.removeEventListener("retailedge-purchase-receipt-history-page-show", this._showHandler); },
	methods: {
		async loadShellAndHistory() {
			try {
				const [context, operating] = await Promise.all([
					callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context"),
					callMethod("retailedge.operating_context.get_operating_context"),
				]);
				const shell = context.context || {};
				this.tenantName = operating.company_label || operating.company || shell.company || "";
				this.branchName = operating.branch || "";
				this.userName = shell.user_name || shell.user || "";
				this.canUseNativeDesk = Boolean(context?.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(context.navigation_groups || []);
				this.filters.company = operating.company || shell.company || "";
				this.filters.branch = operating.branch || "";
			} catch (_error) {
				// History API remains authoritative and will return a permission-aware error.
			}
			await this.applyFilters();
		},
		onSmartDateResolved(value) {
			if (!value?.from_date || !value?.to_date) return;
			this.smartDate = { ...value };
			this.filters.from_date = value.from_date;
			this.filters.to_date = value.to_date;
		},
		async fetchHistory(start = 0) {
			return callMethod(HISTORY_METHOD, {
				company: this.filters.company || null,
				branch: this.filters.branch || null,
				supplier: this.filters.supplier || null,
				search: this.filters.search || null,
				from_date: this.filters.from_date || null,
				to_date: this.filters.to_date || null,
				start,
				page_length: PAGE_SIZE,
			});
		},
		async applyFilters() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const result = await this.fetchHistory(0);
				this.history = { ...(result || {}), receipts: result?.receipts || [] };
				if (!this.filters.company) this.filters.company = result.company || "";
				if (!this.filters.branch && result.branch) this.filters.branch = result.branch;
				this.loaded = true;
			} catch (error) {
				this.error = errorMessage(error, "Unable to load Purchase Receipt history.");
			} finally { this.loading = false; }
		},
		async loadMore() {
			if (this.loadingMore || !this.history.has_more) return;
			this.loadingMore = true; this.error = "";
			try {
				const result = await this.fetchHistory(Number(this.history.next_start || this.rows.length));
				const existing = new Set(this.rows.map((row) => row.name));
				this.history = {
					...this.history,
					...(result || {}),
					receipts: [...this.rows, ...(result?.receipts || []).filter((row) => !existing.has(row.name))],
				};
			} catch (error) { this.error = errorMessage(error, "Unable to load more Purchase Receipts."); }
			finally { this.loadingMore = false; }
		},
		async searchOptions(kind, txt) {
			const result = await callMethod(SEARCH_METHOD, { kind, txt, company: this.filters.company || null });
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		supplierSearch(txt) { return this.searchOptions("supplier", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.supplier = ""; this.applyFilters(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.applyFilters(); },
		clearBranch() { this.filters.branch = ""; this.applyFilters(); },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.applyFilters(); },
		clearSupplier() { this.filters.supplier = ""; this.applyFilters(); },
		clearOptionalFilters() {
			this.filters = { ...this.filters, branch: "", supplier: "", search: "", from_date: "", to_date: "" };
			this.smartDate = {};
			this.applyFilters();
		},
		async prepareInvoice(row) {
			if (!row?.name || !row.can_prepare_invoice || this.preparingInvoice) return;
			this.preparingInvoice = row.name; this.error = "";
			try {
				const result = await callMethod(PREPARE_INVOICE_METHOD, { purchase_receipt: row.name }, "POST");
				if (!result?.name) throw new Error("Purchase Invoice draft was not returned.");
				window.retailedgeProfessionalPurchasingTarget = {
					user: frappe.session?.user || "",
					action: "purchase-invoice-ready",
					result,
					createdAt: Date.now(),
				};
				frappe.set_route("professional-purchasing");
			} catch (error) {
				this.error = errorMessage(error, "Unable to prepare the Purchase Invoice from this receipt.");
			} finally { this.preparingInvoice = ""; }
		},
		openDocumentOutput(name) { if (name) openDocumentOutputSharing("purchase-receipt", name); },
		openAdvancedReceipt(name) { if (this.canUseNativeDesk && name) frappe.set_route("Form", "Purchase Receipt", name); },
		backToPurchasing() { frappe.set_route("professional-purchasing"); },
		formatDate(value) { return value ? frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0] : "—"; },
		formatQty(value) { const number = Number(value || 0); return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "0"; },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
	},
};
</script>

<style scoped>
.purchase-receipt-history-page{min-height:100%;display:grid;gap:1rem}.receipt-history-fallback,.edge-panel{border:1px solid var(--edge-border,#d9d9d9);border-radius:var(--edge-radius-lg,10px);background:var(--edge-surface,#fff)}.receipt-history-fallback{margin:20px;padding:24px;display:flex;flex-direction:column;gap:8px}.history-controls,.receipt-history{padding:18px}.history-filter-grid{display:grid;grid-template-columns:repeat(3,minmax(180px,1fr));gap:.75rem}.history-period-filter{min-width:0;width:100%}.history-input{display:grid;gap:.35rem;color:var(--edge-text-muted,#667085);font-size:.8rem;font-weight:600}.history-input input{min-height:40px;border:1px solid var(--edge-border,#d9d9d9);border-radius:8px;background:var(--edge-surface,#fff);color:inherit;padding:0 .7rem}.history-control-actions,.row-actions,.history-scope,.history-pagination{display:flex;gap:.55rem;flex-wrap:wrap;align-items:center}.history-control-actions{margin-top:.85rem}.history-scope{margin-bottom:.8rem;color:var(--edge-text-muted,#667085);font-size:.82rem}.history-inline-error{margin-bottom:.8rem;padding:.65rem .75rem;border:1px solid var(--red-400,#f04438);border-radius:.5rem;color:var(--red-700,#b42318)}.table-responsive{overflow:auto}.receipt-history-table{min-width:960px;width:100%}.receipt-history-table td{vertical-align:top}.num{text-align:right}.history-pagination{justify-content:space-between;margin-top:1rem}.edge-button,.edge-small-button{border:1px solid var(--edge-border,#d9d9d9);border-radius:8px;background:var(--edge-surface,#fff);color:inherit;cursor:pointer;font-weight:600}.edge-button{min-height:38px;padding:0 12px}.edge-small-button{min-height:30px;padding:0 9px;white-space:nowrap}.edge-button--primary,.edge-small-button--primary{border-color:var(--edge-primary,#0f766e);background:var(--edge-primary,#0f766e);color:#fff}button:disabled{opacity:.55;cursor:not-allowed}@media(max-width:900px){.history-filter-grid{grid-template-columns:repeat(2,minmax(160px,1fr))}}@media(max-width:560px){.history-filter-grid{grid-template-columns:1fr}.history-control-actions{flex-direction:column;align-items:stretch}.history-control-actions .edge-button{width:100%}}
</style>