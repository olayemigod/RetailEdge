<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Purchase Receipt History could not start.</strong>
		<div>Required interface components are unavailable. Refresh the page or contact your administrator.</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Purchase Receipt History"
		:tenantName="tenantName || filters.company"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/purchase-receipt-history"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="purchase-receipt-history-page">
			<EdgePageHeader
				title="Purchase Receipt History"
				description="Review submitted stock receipts in a persistent workspace within your permitted Company and Branch scope."
			/>
			<section class="edge-panel receipt-history__filters">
				<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
				<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
				<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
				<button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="loadHistory">{{ loading ? "Refreshing..." : "Apply Filters" }}</button>
			</section>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading Purchase Receipt history..." :skeleton="true" />
			<EdgeErrorState v-else-if="error && !loaded" title="Receipt history unavailable" :message="error" @retry="loadHistory" />
			<section v-else class="edge-panel receipt-history">
				<div v-if="error" class="receipt-history__inline-error" role="alert">{{ error }}</div>
				<div class="receipt-history__scope">
					<span><strong>Company:</strong> {{ history.company || filters.company || "—" }}</span>
					<span><strong>Branch:</strong> {{ history.branch || "All permitted" }}</span>
					<span><strong>Supplier:</strong> {{ history.supplier || "All suppliers" }}</span>
					<span><strong>Showing:</strong> {{ sortedReceipts.length }} / {{ history.limit || 100 }} max</span>
				</div>

				<EdgeEmptyState v-if="!sortedReceipts.length" title="No submitted Purchase Receipts" description="No permitted submitted non-return receipts match the selected scope." />
				<div v-else class="table-responsive">
					<table class="table receipt-history__table">
						<thead><tr>
							<th><button type="button" class="sort-button" @click="sortBy('name')">Receipt {{ sortMark("name") }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('posting_date')">Date {{ sortMark("posting_date") }}</button></th>
							<th><button type="button" class="sort-button" @click="sortBy('supplier_name')">Supplier {{ sortMark("supplier_name") }}</button></th>
							<th>Purchase Order</th>
							<th><button type="button" class="sort-button" @click="sortBy('total_qty')">Qty {{ sortMark("total_qty") }}</button></th>
							<th>Branch</th>
							<th><button type="button" class="sort-button" @click="sortBy('status')">Status {{ sortMark("status") }}</button></th>
							<th>Actions</th>
						</tr></thead>
						<tbody>
							<tr v-for="row in sortedReceipts" :key="row.name">
								<td><strong>{{ row.name }}</strong></td>
								<td>{{ formatDate(row.posting_date) }}</td>
								<td>{{ row.supplier_name || row.supplier }}</td>
								<td>{{ (row.purchase_orders || []).join(", ") || "—" }}</td>
								<td>{{ formatQty(row.total_qty) }}</td>
								<td>{{ row.branch || "—" }}</td>
								<td>{{ row.status || "Submitted" }}</td>
								<td>
									<div class="receipt-history__actions">
										<button type="button" class="edge-small-button" @click="openDocumentOutput(row.name)">Print & Share</button>
										<button v-if="row.can_prepare_invoice" type="button" class="edge-small-button edge-small-button--primary" :disabled="preparingInvoice === row.name" @click="prepareInvoice(row)">{{ preparingInvoice === row.name ? "Preparing…" : "Create Invoice" }}</button>
										<button v-if="canUseNativeDesk" type="button" class="edge-small-button" @click="openAdvancedReceipt(row.name)">Advanced: Open in ERPNext</button>
									</div>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
				<div class="receipt-history__footer">
					<button type="button" class="edge-button" @click="openPurchasing">Back to Purchasing</button>
					<button v-if="canUseNativeDesk" type="button" class="edge-button" @click="openAdvancedList">Advanced: Purchase Receipts in ERPNext</button>
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
const CONTEXT_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};
const REQUIRED = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLinkField", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState"];

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return window.retailedge?.userErrorMessage?.(error, fallback) || error?.message || fallback; }
function comparable(value) { if (value === null || value === undefined) return ""; if (typeof value === "number") return value; return String(value).toLowerCase(); }
function doctypeSlug(doctype) { return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

export default {
	name: "PurchaseReceiptHistoryPage",
	components: Object.fromEntries(REQUIRED.map((name) => [name, runtime[name]])),
	data() {
		return {
			edgeUIValid: REQUIRED.every((name) => Boolean(runtime[name])),
			loading: false,
			loaded: false,
			error: "",
			preparingInvoice: "",
			history: { company: "", branch: "", supplier: "", limit: 100, receipts: [] },
			filters: { company: "", branch: "", supplier: "" },
			sort: { key: "posting_date", direction: "desc" },
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			canUseNativeDesk: false,
		};
	},
	computed: {
		sortedReceipts() {
			const rows = [...(this.history.receipts || [])];
			const { key, direction } = this.sort;
			return rows.sort((left, right) => {
				const a = comparable(left?.[key]); const b = comparable(right?.[key]);
				if (a === b) return 0;
				const result = a > b ? 1 : -1;
				return direction === "asc" ? result : -result;
			});
		},
	},
	mounted() { if (this.edgeUIValid) this.loadPage(); },
	methods: {
		async loadPage() {
			try {
				const navigation = await callMethod(CONTEXT_METHOD);
				this.tenantName = navigation.context?.company || "";
				this.branchName = navigation.context?.branch || "";
				this.userName = navigation.context?.user_name || "";
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (!this.filters.company) this.filters.company = this.tenantName;
				if (!this.filters.branch) this.filters.branch = this.branchName;
			} catch (_error) {
				// Receipt history remains permission-safe without navigation chrome metadata.
			}
			await this.loadHistory();
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target) window.open(route || item.target, "_blank", "noopener,noreferrer");
		},
		async loadHistory() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod(HISTORY_METHOD, {
					company: this.filters.company || null,
					branch: this.filters.branch || null,
					supplier: this.filters.supplier || null,
					limit: 100,
				});
				this.history = { ...this.history, ...(result || {}) };
				if (!this.filters.company) this.filters.company = result.company || "";
				if (!this.filters.branch && result.branch) this.filters.branch = result.branch;
				this.loaded = true;
			} catch (error) {
				this.error = errorMessage(error, "Unable to load Purchase Receipt history.");
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
		async prepareInvoice(row) {
			if (!row?.name || !row.can_prepare_invoice || this.preparingInvoice) return;
			this.preparingInvoice = row.name; this.error = "";
			try {
				const result = await callMethod(PREPARE_INVOICE_METHOD, { purchase_receipt: row.name }, "POST");
				if (!result?.name) throw new Error("Purchase Invoice draft was not returned.");
				frappe.show_alert?.({ message: `Purchase Invoice ${result.name} ready for review.`, indicator: "green" });
				frappe.set_route("professional-purchasing");
				window.setTimeout(() => window.dispatchEvent(new CustomEvent("retailedge-professional-purchasing-purchase-invoice-ready", { detail: result })), 0);
			} catch (error) {
				this.error = errorMessage(error, "Unable to prepare the Purchase Invoice from this receipt.");
			} finally { this.preparingInvoice = ""; }
		},
		formatDate(value) { return value ? frappe.datetime.str_to_user(value) : "—"; },
		formatQty(value) { const number = Number(value || 0); return Number.isFinite(number) ? number.toLocaleString(undefined, { maximumFractionDigits: 3 }) : "0"; },
		openDocumentOutput(name) { if (name) openDocumentOutputSharing("purchase-receipt", name); },
		openAdvancedReceipt(name) { if (this.canUseNativeDesk && name) frappe.set_route("Form", "Purchase Receipt", name); },
		openAdvancedList() { if (this.canUseNativeDesk) frappe.set_route("List", "Purchase Receipt"); },
		openPurchasing() { frappe.set_route("professional-purchasing"); },
	},
};
</script>

<style scoped>
.purchase-receipt-history-page,.receipt-history { display:grid; gap:1rem; }
.receipt-history__filters { display:grid; grid-template-columns:repeat(3,minmax(180px,1fr)) auto; gap:.75rem; align-items:end; }
.receipt-history__scope { display:flex; flex-wrap:wrap; gap:.6rem 1.25rem; font-size:.85rem; opacity:.82; }
.receipt-history__inline-error { padding:.75rem; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; }
.receipt-history__table td { vertical-align:top; }
.sort-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; }
.edge-small-button { min-height:30px; padding:0 9px; border:1px solid var(--border-color,#d1d8dd); border-radius:.5rem; background:var(--card-bg,#fff); color:inherit; cursor:pointer; white-space:nowrap; }
.edge-small-button--primary { border-color:var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; }
.receipt-history__actions,.receipt-history__footer { display:flex; gap:.5rem; flex-wrap:wrap; }
.receipt-history__footer { justify-content:space-between; padding-top:.5rem; }
@media (max-width:900px) { .receipt-history__filters { grid-template-columns:1fr 1fr; } }
@media (max-width:560px) { .receipt-history__filters { grid-template-columns:1fr; } .receipt-history__footer { flex-direction:column; } }
</style>
