<template>
	<div v-if="!edgeUIValid" class="purchasing-fallback">
		<strong>Professional Purchasing could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Professional Purchasing"
		:tenantName="company"
		:branchName="branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/professional-purchasing"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="professional-purchasing-page">
			<EdgePageHeader
				title="Professional Purchasing"
				description="Move from Purchase Request to RFQ, Purchase Order and Receipt while ERPNext remains authoritative for sourcing, suppliers, quantities, stock and accounting."
			/>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading purchasing operations..." />
			<EdgeErrorState v-else-if="error && !loaded" :message="error" @retry="loadWorkspace" />

			<div v-else class="purchasing-content">
				<section class="edge-panel purchasing-hero">
					<div>
						<span class="purchasing-kicker">Purchase operations</span>
						<h3>Purchase Request → RFQ → Order → Receipt</h3>
						<p>Use guided draft preparation and exception visibility for standard procurement. ERPNext native forms and reports remain authoritative for supplier communication, detailed quantities, stock and accounting.</p>
					</div>
					<div class="hero-actions">
						<button v-if="capabilities.can_create_purchase_order" type="button" class="edge-button edge-button--primary" @click="newPurchaseOrder">New Purchase Order</button>
						<button v-if="capabilities.can_read_request_for_quotation" type="button" class="edge-button edge-button--secondary" @click="openRequestsForQuotation">RFQs</button>
						<button v-if="capabilities.can_read_supplier_quotation" type="button" class="edge-button edge-button--secondary" @click="openSupplierQuotations">Supplier Quotations</button>
						<button v-if="capabilities.can_compare_supplier_quotations" type="button" class="edge-button edge-button--secondary" @click="openSupplierQuotationComparison">Compare Quotations</button>
						<button v-if="capabilities.can_open_purchase_order_analysis" type="button" class="edge-button edge-button--secondary" @click="openPurchaseOrderAnalysis">PO Analysis</button>
						<button v-if="procurementTracker.available" type="button" class="edge-button edge-button--secondary" @click="openProcurementTracker">Procurement Tracker</button>
						<button v-if="capabilities.can_read_purchase_receipt" type="button" class="edge-button edge-button--secondary" @click="openPurchaseReceipts">Purchase Receipts</button>
					</div>
				</section>

				<section class="edge-panel filter-panel">
					<div class="filter-grid">
						<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
						<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="Operating branch" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
						<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
						<div class="filter-action"><button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="loadWorkspace">{{ loading ? "Refreshing…" : "Apply Filters" }}</button></div>
					</div>
					<p class="filter-help">Company and Branch scope purchasing operations. Supplier filters the Purchase Order queue, guided returns and landed-cost source lists.</p>
				</section>

				<div class="metric-grid">
					<article class="edge-panel metric-card"><span>Purchase Requests</span><strong>{{ summary.purchase_requests || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Ready for RFQ</span><strong>{{ summary.ready_for_rfq || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Purchase Orders</span><strong>{{ summary.purchase_orders || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Needs Review</span><strong>{{ summary.attention_total || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Overdue Receipt</span><strong>{{ summary.overdue_receipt || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Received Not Billed</span><strong>{{ summary.received_not_billed || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Billed Ahead of Receipt</span><strong>{{ summary.billed_ahead_of_receipt || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Ready to Receive</span><strong>{{ summary.ready_to_receive || summary.to_receive || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Submitted PO Value</span><strong>{{ formatMoney(summary.open_value || 0) }}</strong></article>
				</div>

				<section v-if="actionNotice || actionError" class="edge-panel action-feedback" :class="{ 'action-feedback--error': actionError }">
					<strong>{{ actionError ? "Action needs attention" : "Action complete" }}</strong>
					<span>{{ actionError || actionNotice }}</span>
					<button type="button" class="edge-small-button" @click="clearActionFeedback">Dismiss</button>
				</section>

				<section v-if="returnCapabilities.can_prepare_purchase_return || returnCapabilities.can_prepare_supplier_debit_note" class="edge-panel returns-panel">
					<div class="panel-heading">
						<div>
							<span class="purchasing-kicker">Corrections after receipt or billing</span>
							<h3>Returns & Supplier Credits</h3>
							<p>Choose the business intent explicitly. RetailEdge prepares one native ERPNext draft only and never chains a stock return and supplier debit note automatically.</p>
						</div>
					</div>
					<div class="return-grid">
						<article v-if="returnCapabilities.can_prepare_purchase_return" class="return-card">
							<div><h4>Return Received Goods</h4><p>Use when physical stock received on a submitted Purchase Receipt is being sent back to the supplier. ERPNext remains authoritative for quantities, warehouses, batch/serial rules and stock effects.</p></div>
							<EdgeLinkField v-model="returnSources.purchaseReceipt" label="Submitted Purchase Receipt" placeholder="Search permitted receipt" :searcher="purchaseReturnSourceSearch" @select="onPurchaseReturnSourceSelected" @clear="clearPurchaseReturnSource" />
							<button type="button" class="edge-button edge-button--primary" :disabled="preparingReturn || !returnSources.purchaseReceipt" @click="preparePurchaseReturn">{{ preparingReturn === "purchase_receipt" ? "Preparing…" : "Prepare Draft Return" }}</button>
						</article>
						<article v-if="returnCapabilities.can_prepare_supplier_debit_note" class="return-card">
							<div><h4>Create Supplier Debit Note</h4><p>Use when correcting or crediting a submitted supplier invoice. If the Purchase Invoice uses Update Stock, ERPNext preserves that native stock behavior for review before submission.</p></div>
							<EdgeLinkField v-model="returnSources.purchaseInvoice" label="Submitted Purchase Invoice" placeholder="Search permitted supplier invoice" :searcher="debitNoteSourceSearch" @select="onDebitNoteSourceSelected" @clear="clearDebitNoteSource" />
							<button type="button" class="edge-button edge-button--primary" :disabled="preparingReturn || !returnSources.purchaseInvoice" @click="prepareSupplierDebitNote">{{ preparingReturn === "purchase_invoice" ? "Preparing…" : "Prepare Draft Debit Note" }}</button>
						</article>
					</div>
				</section>

				<section v-if="landedCostCapability.can_prepare_landed_cost" class="edge-panel landed-cost-panel">
					<div class="panel-heading">
						<div>
							<span class="purchasing-kicker">True inventory cost</span>
							<h3>Allocate Landed Cost</h3>
							<p>Prepare ERPNext's native Landed Cost Voucher from received stock. Freight, clearing, customs duty, insurance, expense accounts and final allocation stay on the native voucher; nothing is saved or posted by this guided handoff.</p>
						</div>
					</div>
					<div class="landed-cost-source-types" aria-label="Landed cost source type">
						<button v-if="landedCostCapability.can_use_purchase_receipt" type="button" class="attention-chip" :class="{ 'attention-chip--active': landedCost.sourceType === 'purchase_receipt' }" @click="setLandedCostSourceType('purchase_receipt')">Purchase Receipt</button>
						<button v-if="landedCostCapability.can_use_purchase_invoice" type="button" class="attention-chip" :class="{ 'attention-chip--active': landedCost.sourceType === 'purchase_invoice' }" @click="setLandedCostSourceType('purchase_invoice')">Stock-updating Purchase Invoice</button>
					</div>
					<div class="landed-cost-controls">
						<EdgeLinkField
							v-model="landedCost.source"
							:label="landedCost.sourceType === 'purchase_invoice' ? 'Stock-updating Purchase Invoice' : 'Submitted Purchase Receipt'"
							placeholder="Search permitted stock receipt"
							:searcher="landedCostSourceSearch"
							@select="onLandedCostSourceSelected"
							@clear="clearLandedCostSource"
						/>
						<label class="edge-select-field">
							<span>Distribution basis</span>
							<select v-model="landedCost.distributionMethod">
								<option value="Amount">Amount</option>
								<option value="Qty">Quantity</option>
								<option value="Distribute Manually">Distribute Manually</option>
							</select>
						</label>
						<button type="button" class="edge-button edge-button--primary" :disabled="preparingLandedCost || !landedCost.source" @click="prepareLandedCost">{{ preparingLandedCost ? "Preparing…" : "Prepare Landed Cost Draft" }}</button>
					</div>
					<p class="landed-cost-help">The prepared voucher remains unsaved until you enter the mandatory landed-cost charges on ERPNext's Landed Cost Voucher form. Valuation, Stock Ledger and General Ledger changes occur only through standard ERPNext submission.</p>
				</section>

				<section v-if="capabilities.can_read_material_request" class="edge-panel sourcing-panel">
					<div class="panel-heading">
						<div><span class="purchasing-kicker">ERPNext sourcing demand</span><h3>Purchase Material Requests</h3></div>
						<div class="hero-actions">
							<button type="button" class="edge-button edge-button--secondary" @click="openMaterialRequests">Material Requests</button>
							<button type="button" class="edge-button edge-button--secondary" :disabled="loading" @click="loadWorkspace">Refresh</button>
						</div>
					</div>
					<EdgeLoadingState v-if="loading" message="Refreshing Purchase Material Requests..." />
					<EdgeEmptyState v-else-if="!materialRequests.length" title="No Purchase Material Requests" description="No permitted submitted Purchase Material Requests with remaining procurement quantity match this Company and Branch." />
					<div v-else class="table-wrap">
						<table class="purchasing-table">
							<thead><tr>
								<th><button type="button" class="sort-button" @click="sortMaterialBy('name')">Material Request {{ materialSortMark('name') }}</button></th>
								<th><button type="button" class="sort-button" @click="sortMaterialBy('transaction_date')">Date {{ materialSortMark('transaction_date') }}</button></th>
								<th>Required</th><th>Branch</th><th>Status</th>
								<th class="num"><button type="button" class="sort-button" @click="sortMaterialBy('per_ordered')">Ordered {{ materialSortMark('per_ordered') }}</button></th>
								<th>Actions</th>
							</tr></thead>
							<tbody><tr v-for="row in sortedMaterialRequests" :key="row.name">
								<td><button type="button" class="link-button" @click="openMaterialRequest(row.name)">{{ row.name }}</button><small v-if="row.title && row.title !== row.name" class="row-subtitle">{{ row.title }}</small></td>
								<td>{{ formatDate(row.transaction_date) }}</td><td>{{ formatDate(row.schedule_date) }}</td><td>{{ row.branch || "—" }}</td>
								<td><span class="status-pill">{{ row.status || "Submitted" }}</span></td><td class="num">{{ formatPercent(row.per_ordered) }}</td>
								<td class="actions-cell"><button type="button" class="edge-small-button" @click="openMaterialRequest(row.name)">Open</button><button v-if="row.can_start_rfq" type="button" class="edge-small-button edge-small-button--primary" @click="startRfq(row)">Start RFQ</button></td>
							</tr></tbody>
						</table>
					</div>
				</section>

				<section v-if="rfqDraft.material_request" class="edge-panel rfq-panel">
					<div class="panel-heading">
						<div><span class="purchasing-kicker">Draft-first sourcing</span><h3>Prepare RFQ from {{ rfqDraft.material_request }}</h3><p>Choose suppliers for the draft. Email is disabled; review contacts, terms and communication in the standard ERPNext RFQ before submission.</p></div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="preparingRfq" @click="cancelRfq">Cancel</button>
					</div>
					<div class="rfq-controls">
						<EdgeLinkField v-model="rfqSupplierInput" label="Add Supplier" placeholder="Search permitted supplier" :searcher="rfqSupplierSearch" @select="addRfqSupplier" @clear="clearRfqSupplierInput" />
						<div class="supplier-selection">
							<span v-if="!rfqDraft.suppliers.length" class="selection-empty">Select at least one supplier. Maximum {{ limits.rfq_suppliers || 20 }}.</span>
							<span v-for="supplier in rfqDraft.suppliers" :key="supplier.value" class="supplier-chip">{{ supplier.label || supplier.value }}<button type="button" aria-label="Remove supplier" @click="removeRfqSupplier(supplier.value)">×</button></span>
						</div>
						<button type="button" class="edge-button edge-button--primary" :disabled="preparingRfq || !rfqDraft.suppliers.length" @click="prepareRfq">{{ preparingRfq ? "Preparing RFQ…" : "Prepare Draft RFQ" }}</button>
					</div>
				</section>

				<section class="edge-panel orders-panel">
					<div class="panel-heading">
						<div><span class="purchasing-kicker">ERPNext order truth</span><h3>Purchase Orders & Attention</h3><p>Attention flags are server-derived guidance from current ERPNext PO dates and progress. Use PO Analysis for item-level quantities and amounts.</p></div>
						<div class="hero-actions"><button v-if="capabilities.can_open_purchase_order_analysis" type="button" class="edge-button edge-button--secondary" @click="openPurchaseOrderAnalysis">Open PO Analysis</button><button type="button" class="edge-button edge-button--secondary" :disabled="loading" @click="loadWorkspace">Refresh</button></div>
					</div>
					<div class="attention-controls" aria-label="Purchase Order attention filter">
						<button v-for="option in attentionOptions" :key="option.key" type="button" class="attention-chip" :class="{ 'attention-chip--active': attentionFilter === option.key }" @click="setAttentionFilter(option.key)">{{ option.label }} <strong>{{ attentionCount(option.key) }}</strong></button>
					</div>
					<div v-if="error" class="inline-error">{{ error }}</div>
					<EdgeLoadingState v-else-if="loading" message="Refreshing Purchase Orders..." />
					<EdgeEmptyState v-else-if="!rows.length" title="No Purchase Orders found" description="No permitted Purchase Orders match this Company, Branch and Supplier scope." />
					<EdgeEmptyState v-else-if="!visibleRows.length" title="No Purchase Orders in this attention view" description="Choose another attention filter or broaden the authorised Company, Branch or Supplier scope." />
					<div v-else class="table-wrap">
						<table class="purchasing-table purchasing-table--orders">
							<thead><tr>
								<th><button type="button" class="sort-button" @click="sortBy('name')">Purchase Order {{ sortMark('name') }}</button></th>
								<th><button type="button" class="sort-button" @click="sortBy('transaction_date')">Date {{ sortMark('transaction_date') }}</button></th>
								<th><button type="button" class="sort-button" @click="sortBy('supplier_name')">Supplier {{ sortMark('supplier_name') }}</button></th>
								<th>Branch</th><th>Status</th><th>Attention</th>
								<th class="num"><button type="button" class="sort-button" @click="sortBy('per_received')">Received {{ sortMark('per_received') }}</button></th>
								<th class="num"><button type="button" class="sort-button" @click="sortBy('per_billed')">Billed {{ sortMark('per_billed') }}</button></th>
								<th class="num"><button type="button" class="sort-button" @click="sortBy('grand_total')">Total {{ sortMark('grand_total') }}</button></th><th>Actions</th>
							</tr></thead>
							<tbody><tr v-for="row in visibleRows" :key="row.name">
								<td><button type="button" class="link-button" @click="openPurchaseOrder(row.name)">{{ row.name }}</button></td><td>{{ formatDate(row.transaction_date) }}</td><td>{{ row.supplier_name || row.supplier }}</td><td>{{ row.branch || "—" }}</td>
								<td><span class="status-pill">{{ row.status || (row.docstatus === 0 ? "Draft" : "Submitted") }}</span></td>
								<td><div class="attention-badges"><span v-if="!row.attention_flags?.length" class="attention-badge attention-badge--clear">Clear</span><span v-for="flag in row.attention_flags || []" :key="flag.key" class="attention-badge" :class="`attention-badge--${flag.kind || 'readiness'}`">{{ flag.label }}</span></div></td>
								<td class="num">{{ formatPercent(row.per_received) }}</td><td class="num">{{ formatPercent(row.per_billed) }}</td><td class="num strong">{{ formatMoney(row.grand_total, row.currency) }}</td>
								<td class="actions-cell"><button type="button" class="edge-small-button" @click="openPurchaseOrder(row.name)">Open</button><button v-if="row.can_prepare_receipt" type="button" class="edge-small-button edge-small-button--primary" :disabled="preparingReceipt === row.name" @click="prepareReceipt(row)">{{ preparingReceipt === row.name ? "Preparing…" : "Prepare Receipt" }}</button></td>
							</tr></tbody>
						</table>
					</div>
				</section>

				<section class="edge-panel safety-note"><strong>Draft-first procurement safety.</strong><span>RFQ, receipt, physical-return and supplier-debit-note actions delegate to ERPNext mappers and create drafts only. Landed Cost delegates to ERPNext's native unsaved voucher handoff so mandatory charge/accounting rows are reviewed before the first save. Supplier email, submission, stock movement, detailed PO analysis and accounting consequences remain standard ERPNext workflows.</span></section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.professional_purchasing.get_professional_purchasing_context";
const PROCUREMENT_TRACKER_HANDOFF_METHOD = "retailedge.procurement_tracker_handoff.get_procurement_tracker_handoff";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const PREPARE_RFQ_METHOD = "retailedge.professional_purchasing.prepare_request_for_quotation_draft";
const PREPARE_RECEIPT_METHOD = "retailedge.professional_purchasing.prepare_purchase_receipt_draft";
const RETURN_CAPABILITY_METHOD = "retailedge.professional_purchasing.get_purchase_return_capability";
const RETURN_SEARCH_METHOD = "retailedge.professional_purchasing.search_purchase_return_sources";
const PREPARE_PURCHASE_RETURN_METHOD = "retailedge.professional_purchasing.prepare_purchase_return_draft";
const PREPARE_DEBIT_NOTE_METHOD = "retailedge.professional_purchasing.prepare_supplier_debit_note_draft";
const LANDED_COST_CAPABILITY_METHOD = "retailedge.landed_cost_allocation.get_landed_cost_capability";
const LANDED_COST_SEARCH_METHOD = "retailedge.landed_cost_allocation.search_landed_cost_sources";
const PREPARE_LANDED_COST_METHOD = "retailedge.landed_cost_allocation.prepare_landed_cost_voucher_draft";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeLinkField"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }
function doctypeSlug(doctype) { return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }
function sortedCopy(rows, sort) {
	const result = [...rows]; const { key, direction } = sort; const factor = direction === "asc" ? 1 : -1;
	return result.sort((a, b) => { const av = a?.[key] ?? ""; const bv = b?.[key] ?? ""; if (typeof av === "number" || typeof bv === "number") return (Number(av || 0) - Number(bv || 0)) * factor; return String(av).localeCompare(String(bv)) * factor; });
}

export default {
	name: "RetailEdgeProfessionalPurchasing",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], loading: false, loaded: false, error: "", actionError: "", actionNotice: "", company: "", branch: "", userName: "", menuItems: [],
			filters: { company: "", branch: "", supplier: "" }, summary: {}, capabilities: {}, limits: {}, rows: [], materialRequests: [], serverToday: "",
			procurementTracker: { available: false, company: "", branch: "", report: "Procurement Tracker", reason: "" },
			returnCapabilities: { can_prepare_purchase_return: false, can_prepare_supplier_debit_note: false }, returnSources: { purchaseReceipt: "", purchaseInvoice: "" }, preparingReturn: "",
			landedCostCapability: { can_prepare_landed_cost: false, can_use_purchase_receipt: false, can_use_purchase_invoice: false }, landedCost: { sourceType: "purchase_receipt", source: "", distributionMethod: "Amount" }, preparingLandedCost: false,
			preparingReceipt: "", preparingRfq: false, rfqSupplierInput: "", rfqDraft: { material_request: "", suppliers: [] },
			sort: { key: "transaction_date", direction: "desc" }, materialSort: { key: "transaction_date", direction: "desc" }, attentionFilter: "all",
			attentionOptions: [
				{ key: "all", label: "All" }, { key: "needs_review", label: "Needs Review" }, { key: "overdue_receipt", label: "Overdue" },
				{ key: "received_not_billed", label: "Received Not Billed" }, { key: "billed_ahead_of_receipt", label: "Billed Ahead" }, { key: "ready_to_receive", label: "Ready to Receive" },
			],
		};
	},
	computed: {
		sortedRows() { return sortedCopy(this.rows, this.sort); },
		visibleRows() {
			if (this.attentionFilter === "all") return this.sortedRows;
			if (this.attentionFilter === "needs_review") return this.sortedRows.filter((row) => row.attention_level === "Review");
			return this.sortedRows.filter((row) => (row.attention_flags || []).some((flag) => flag.key === this.attentionFilter));
		},
		sortedMaterialRequests() { return sortedCopy(this.materialRequests, this.materialSort); },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; this._onPageShow = () => this.loadWorkspace(); },
	mounted() { window.addEventListener("retailedge-professional-purchasing-page-show", this._onPageShow); if (this.edgeUIValid) this.loadWorkspace(); },
	beforeUnmount() { window.removeEventListener("retailedge-professional-purchasing-page-show", this._onPageShow); },
	methods: {
		async loadWorkspace() {
			if (this.loading) return; this.loading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation, procurementTracker, returnCapabilities, landedCostCapability] = await Promise.all([
					callMethod(CONTEXT_METHOD, { company: this.filters.company || null, branch: this.filters.branch || null, supplier: this.filters.supplier || null, limit: 200 }),
					navigationPromise,
					callMethod(PROCUREMENT_TRACKER_HANDOFF_METHOD, { company: this.filters.company || null, branch: this.filters.branch || null }),
					callMethod(RETURN_CAPABILITY_METHOD),
					callMethod(LANDED_COST_CAPABILITY_METHOD),
				]);
				this.applyContext(context || {}); this.procurementTracker = procurementTracker || this.procurementTracker; this.returnCapabilities = returnCapabilities || this.returnCapabilities; this.applyLandedCostCapability(landedCostCapability || {}); this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []); this.loaded = true;
			} catch (error) { this.error = errorMessage(error, "Professional Purchasing failed to load."); } finally { this.loading = false; }
		},
		applyContext(context) {
			this.company = context.company || this.filters.company || ""; this.branch = context.branch || this.filters.branch || "";
			if (!this.filters.company) this.filters.company = this.company; if (!this.filters.branch) this.filters.branch = this.branch;
			this.userName = context.user_name || this.userName; this.rows = context.rows || []; this.materialRequests = context.material_requests || []; this.summary = context.summary || {}; this.capabilities = context.capabilities || {}; this.limits = context.limits || {}; this.serverToday = context.server_today || "";
		},
		applyLandedCostCapability(capability) {
			this.landedCostCapability = { ...this.landedCostCapability, ...(capability || {}) };
			if (!this.landedCostCapability.can_use_purchase_receipt && this.landedCostCapability.can_use_purchase_invoice) this.landedCost.sourceType = "purchase_invoice";
			if (!this.landedCostCapability.can_use_purchase_invoice && this.landedCost.sourceType === "purchase_invoice") this.landedCost.sourceType = "purchase_receipt";
		},
		async searchOptions(kind, txt) { const result = await callMethod(SEARCH_METHOD, { kind, txt, company: this.filters.company || null }); return Array.isArray(result) ? result : []; },
		async searchReturnSources(kind, txt) { const result = await callMethod(RETURN_SEARCH_METHOD, { kind, txt, company: this.filters.company || null, branch: this.filters.branch || null, supplier: this.filters.supplier || null }); return Array.isArray(result) ? result : []; },
		async searchLandedCostSources(txt) { const result = await callMethod(LANDED_COST_SEARCH_METHOD, { source_type: this.landedCost.sourceType, txt, company: this.filters.company || null, branch: this.filters.branch || null, supplier: this.filters.supplier || null }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, supplierSearch(txt) { return this.searchOptions("supplier", txt); }, rfqSupplierSearch(txt) { return this.searchOptions("rfq_supplier", txt); },
		purchaseReturnSourceSearch(txt) { return this.searchReturnSources("purchase_receipt", txt); }, debitNoteSourceSearch(txt) { return this.searchReturnSources("purchase_invoice", txt); }, landedCostSourceSearch(txt) { return this.searchLandedCostSources(txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.supplier = ""; this.branch = ""; this.attentionFilter = "all"; this.cancelRfq(); this.clearReturnSources(); this.clearLandedCostSource(); this.loadWorkspace(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.branch = option.label || option.value; this.attentionFilter = "all"; this.cancelRfq(); this.clearReturnSources(); this.clearLandedCostSource(); this.loadWorkspace(); },
		clearBranch() { this.filters.branch = ""; this.branch = ""; this.attentionFilter = "all"; this.cancelRfq(); this.clearReturnSources(); this.clearLandedCostSource(); this.loadWorkspace(); },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.attentionFilter = "all"; this.clearReturnSources(); this.clearLandedCostSource(); this.loadWorkspace(); }, clearSupplier() { this.filters.supplier = ""; this.attentionFilter = "all"; this.clearReturnSources(); this.clearLandedCostSource(); this.loadWorkspace(); },
		onPurchaseReturnSourceSelected(option) { this.returnSources.purchaseReceipt = option?.value || ""; }, clearPurchaseReturnSource() { this.returnSources.purchaseReceipt = ""; },
		onDebitNoteSourceSelected(option) { this.returnSources.purchaseInvoice = option?.value || ""; }, clearDebitNoteSource() { this.returnSources.purchaseInvoice = ""; },
		clearReturnSources() { this.returnSources = { purchaseReceipt: "", purchaseInvoice: "" }; },
		setLandedCostSourceType(sourceType) { if (this.landedCost.sourceType === sourceType) return; this.landedCost.sourceType = sourceType; this.clearLandedCostSource(); },
		onLandedCostSourceSelected(option) { this.landedCost.source = option?.value || ""; }, clearLandedCostSource() { this.landedCost.source = ""; },
		setAttentionFilter(key) { this.attentionFilter = key || "all"; },
		attentionCount(key) {
			if (key === "all") return Number(this.summary.purchase_orders || 0); if (key === "needs_review") return Number(this.summary.attention_total || 0); return Number(this.summary[key] || 0);
		},
		startRfq(row) { if (!row?.name || !row.can_start_rfq) return; this.clearActionFeedback(); this.rfqSupplierInput = ""; this.rfqDraft = { material_request: row.name, suppliers: [] }; },
		addRfqSupplier(option) {
			const value = option?.value || ""; if (!value) return;
			if (this.rfqDraft.suppliers.some((supplier) => supplier.value === value)) { this.actionError = `${value} is already selected for this RFQ.`; this.rfqSupplierInput = ""; return; }
			const maximum = Number(this.limits.rfq_suppliers || 20); if (this.rfqDraft.suppliers.length >= maximum) { this.actionError = `A guided RFQ can include at most ${maximum} suppliers.`; this.rfqSupplierInput = ""; return; }
			this.clearActionFeedback(); this.rfqDraft.suppliers.push({ value, label: option.label || value }); this.rfqSupplierInput = "";
		},
		removeRfqSupplier(value) { this.rfqDraft.suppliers = this.rfqDraft.suppliers.filter((supplier) => supplier.value !== value); }, clearRfqSupplierInput() { this.rfqSupplierInput = ""; }, cancelRfq() { this.rfqSupplierInput = ""; this.rfqDraft = { material_request: "", suppliers: [] }; },
		async prepareRfq() {
			if (!this.rfqDraft.material_request || !this.rfqDraft.suppliers.length || this.preparingRfq) return; this.preparingRfq = true; this.clearActionFeedback();
			try { const result = await callMethod(PREPARE_RFQ_METHOD, { material_request: this.rfqDraft.material_request, suppliers: this.rfqDraft.suppliers.map((supplier) => supplier.value) }); this.actionNotice = `Draft Request for Quotation ${result.name || ""} prepared. Supplier email remains disabled until native ERPNext review.`; this.cancelRfq(); if (result.name) frappe.set_route("Form", "Request for Quotation", result.name); }
			catch (error) { this.actionError = errorMessage(error, "ERPNext could not prepare the RFQ draft."); } finally { this.preparingRfq = false; }
		},
		async prepareReceipt(row) {
			if (!row?.name || this.preparingReceipt) return; this.preparingReceipt = row.name; this.clearActionFeedback();
			try { const result = await callMethod(PREPARE_RECEIPT_METHOD, { purchase_order: row.name }); this.actionNotice = `Draft Purchase Receipt ${result.name || ""} prepared from ERPNext Purchase Order.`; if (result.name) frappe.set_route("Form", "Purchase Receipt", result.name); }
			catch (error) { this.actionError = errorMessage(error, "ERPNext could not prepare the receipt draft."); } finally { this.preparingReceipt = ""; }
		},
		async preparePurchaseReturn() {
			if (!this.returnSources.purchaseReceipt || this.preparingReturn) return; this.preparingReturn = "purchase_receipt"; this.clearActionFeedback();
			try { const result = await callMethod(PREPARE_PURCHASE_RETURN_METHOD, { purchase_receipt: this.returnSources.purchaseReceipt }); this.actionNotice = `Draft Purchase Receipt return ${result.name || ""} prepared. Review native ERPNext quantities, warehouses and stock details before submission.`; this.clearReturnSources(); if (result.name) frappe.set_route("Form", "Purchase Receipt", result.name); }
			catch (error) { this.actionError = errorMessage(error, "ERPNext could not prepare the Purchase Receipt return draft."); } finally { this.preparingReturn = ""; }
		},
		async prepareSupplierDebitNote() {
			if (!this.returnSources.purchaseInvoice || this.preparingReturn) return; this.preparingReturn = "purchase_invoice"; this.clearActionFeedback();
			try { const result = await callMethod(PREPARE_DEBIT_NOTE_METHOD, { purchase_invoice: this.returnSources.purchaseInvoice }); this.actionNotice = result.update_stock ? `Draft supplier Debit Note ${result.name || ""} prepared. ERPNext Update Stock remains enabled; review stock and accounting effects before submission.` : `Draft supplier Debit Note ${result.name || ""} prepared. Review native ERPNext tax, value and accounting details before submission.`; this.clearReturnSources(); if (result.name) frappe.set_route("Form", "Purchase Invoice", result.name); }
			catch (error) { this.actionError = errorMessage(error, "ERPNext could not prepare the supplier Debit Note draft."); } finally { this.preparingReturn = ""; }
		},
		async prepareLandedCost() {
			if (!this.landedCost.source || this.preparingLandedCost) return; this.preparingLandedCost = true; this.clearActionFeedback();
			try {
				const result = await callMethod(PREPARE_LANDED_COST_METHOD, { source_type: this.landedCost.sourceType, source_name: this.landedCost.source, distribution_method: this.landedCost.distributionMethod });
				const synced = frappe.model.sync(result.document || {}); const document = Array.isArray(synced) ? synced[0] : null;
				if (!document?.name) throw new Error("ERPNext did not return an unsaved Landed Cost Voucher document.");
				this.actionNotice = `Unsaved Landed Cost Voucher prepared from ${result.source_type || "purchase source"}. Enter and review landed-cost charges on the native ERPNext form before saving or submitting.`;
				this.clearLandedCostSource(); frappe.set_route("Form", "Landed Cost Voucher", document.name);
			} catch (error) { this.actionError = errorMessage(error, "ERPNext could not prepare the Landed Cost Voucher."); } finally { this.preparingLandedCost = false; }
		},
		clearActionFeedback() { this.actionError = ""; this.actionNotice = ""; }, newPurchaseOrder() { frappe.new_doc("Purchase Order"); },
		openMaterialRequest(name) { frappe.set_route("Form", "Material Request", name); }, openMaterialRequests() { frappe.set_route("List", "Material Request"); }, openRequestsForQuotation() { frappe.set_route("List", "Request for Quotation"); }, openSupplierQuotations() { frappe.set_route("List", "Supplier Quotation"); }, openSupplierQuotationComparison() { frappe.set_route("query-report", "Supplier Quotation Comparison"); },
		openPurchaseOrderAnalysis() { frappe.route_options = { company: this.filters.company || this.company || "" }; frappe.set_route("query-report", "Purchase Order Analysis"); },
		openProcurementTracker() { if (!this.procurementTracker?.available) return; frappe.route_options = { company: this.procurementTracker.company || this.filters.company || this.company || "" }; frappe.set_route("query-report", this.procurementTracker.report || "Procurement Tracker"); },
		openPurchaseOrder(name) { frappe.set_route("Form", "Purchase Order", name); }, openPurchaseReceipts() { frappe.set_route("List", "Purchase Receipt"); },
		sortBy(key) { if (this.sort.key === key) this.sort.direction = this.sort.direction === "asc" ? "desc" : "asc"; else this.sort = { key, direction: "asc" }; }, sortMark(key) { return this.sort.key === key ? (this.sort.direction === "asc" ? "↑" : "↓") : ""; },
		sortMaterialBy(key) { if (this.materialSort.key === key) this.materialSort.direction = this.materialSort.direction === "asc" ? "desc" : "asc"; else this.materialSort = { key, direction: "asc" }; }, materialSortMark(key) { return this.materialSort.key === key ? (this.materialSort.direction === "asc" ? "↑" : "↓") : ""; },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target) window.open(item.target, "_blank", "noopener,noreferrer"); },
		formatMoney(value, currency) { try { return format_currency(Number(value || 0), currency || frappe.boot?.sysdefaults?.currency || "NGN"); } catch (_error) { return `${currency || ""} ${Number(value || 0).toLocaleString()}`.trim(); } },
		formatPercent(value) { return `${Number(value || 0).toFixed(1).replace(/\.0$/, "")}%`; },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.purchasing-fallback,.edge-panel { border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
.purchasing-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; }.purchasing-content { display:flex; flex-direction:column; gap:var(--edge-space-lg,20px); padding-bottom:24px; }
.purchasing-hero,.panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }.purchasing-hero,.filter-panel,.orders-panel,.sourcing-panel,.rfq-panel,.returns-panel,.landed-cost-panel,.safety-note,.action-feedback { padding:18px; }
.purchasing-hero h3,.panel-heading h3 { margin:3px 0 6px; color:var(--edge-text,#101828); }.purchasing-hero p,.panel-heading p,.filter-help { margin:0; max-width:820px; color:var(--edge-text-muted,#667085); }.filter-help { margin-top:10px; font-size:.82rem; }
.purchasing-kicker { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--edge-primary,#0f766e); }.hero-actions,.actions-cell { display:flex; gap:8px; flex-wrap:wrap; }
.filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; }.filter-action { display:flex; }.metric-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }.metric-card { padding:16px; display:flex; flex-direction:column; gap:6px; }.metric-card span { color:var(--edge-text-muted,#667085); font-size:.8rem; }.metric-card strong { color:var(--edge-text,#101828); font-size:1.2rem; }
.return-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }.return-card { border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); padding:16px; display:flex; flex-direction:column; gap:14px; background:var(--edge-surface-subtle,#f8fafc); }.return-card h4 { margin:0 0 6px; color:var(--edge-text,#101828); }.return-card p { margin:0; color:var(--edge-text-muted,#667085); }
.landed-cost-source-types { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:14px; }.landed-cost-controls { display:grid; grid-template-columns:minmax(260px,1.5fr) minmax(180px,.8fr) auto; gap:14px; align-items:end; }.edge-select-field { display:flex; flex-direction:column; gap:6px; color:var(--edge-text-muted,#667085); font-size:.82rem; font-weight:600; }.edge-select-field select { min-height:40px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-md,8px); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); padding:0 10px; }.landed-cost-help { margin:12px 0 0; color:var(--edge-text-muted,#667085); font-size:.82rem; max-width:900px; }
.panel-heading { margin-bottom:14px; }.panel-heading h3 { margin-bottom:0; }.table-wrap { width:100%; overflow:auto; }.purchasing-table { width:100%; min-width:850px; border-collapse:collapse; }.purchasing-table--orders { min-width:1120px; }.purchasing-table th,.purchasing-table td { padding:10px 9px; border-bottom:1px solid var(--edge-border,#e5e7eb); text-align:left; vertical-align:top; }.purchasing-table th { color:var(--edge-text-muted,#667085); font-size:.76rem; text-transform:uppercase; letter-spacing:.04em; }.purchasing-table .num { text-align:right; }.purchasing-table .strong { font-weight:700; }.row-subtitle { display:block; margin-top:3px; color:var(--edge-text-muted,#667085); max-width:260px; }
.sort-button,.link-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; text-transform:inherit; letter-spacing:inherit; }.link-button { color:var(--edge-primary,#0f766e); font-weight:600; }.status-pill { display:inline-flex; padding:3px 8px; border:1px solid var(--edge-border,#d9d9d9); border-radius:999px; font-size:.75rem; }
.edge-button,.edge-small-button { min-height:38px; border-radius:var(--edge-radius-md,8px); padding:0 12px; font-weight:600; cursor:pointer; border:1px solid var(--edge-border,#d9d9d9); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); }.edge-button--primary,.edge-small-button--primary { border-color:var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; }.edge-small-button { min-height:30px; padding:0 9px; font-size:.78rem; }button:disabled { opacity:.55; cursor:not-allowed; }
.rfq-controls { display:grid; grid-template-columns:minmax(240px,1fr) minmax(280px,2fr) auto; gap:14px; align-items:end; }.supplier-selection { min-height:42px; display:flex; align-items:center; gap:7px; flex-wrap:wrap; }.selection-empty { color:var(--edge-text-muted,#667085); }.supplier-chip { display:inline-flex; align-items:center; gap:6px; padding:5px 8px; border:1px solid var(--edge-border,#d9d9d9); border-radius:999px; background:var(--edge-surface-subtle,#f8fafc); }.supplier-chip button { border:0; background:transparent; color:inherit; cursor:pointer; font-size:1rem; line-height:1; }
.attention-controls,.attention-badges { display:flex; gap:7px; flex-wrap:wrap; }.attention-controls { margin:0 0 14px; }.attention-chip { min-height:32px; padding:0 10px; border:1px solid var(--edge-border,#d9d9d9); border-radius:999px; background:var(--edge-surface,#fff); color:var(--edge-text,#101828); cursor:pointer; }.attention-chip--active { border-color:var(--edge-primary,#0f766e); box-shadow:inset 0 0 0 1px var(--edge-primary,#0f766e); }.attention-badges { display:flex; gap:7px; flex-wrap:wrap; }.attention-badge { display:inline-flex; padding:3px 7px; border-radius:999px; border:1px solid var(--edge-border,#d9d9d9); font-size:.72rem; white-space:nowrap; }.attention-badge--exception { border-color:var(--edge-danger,#b42318); color:var(--edge-danger,#b42318); }.attention-badge--review { border-color:var(--edge-warning,#b54708); color:var(--edge-warning,#b54708); }.attention-badge--readiness { border-color:var(--edge-primary,#0f766e); color:var(--edge-primary,#0f766e); }.attention-badge--clear { color:var(--edge-text-muted,#667085); }
.action-feedback { display:flex; align-items:center; gap:10px; flex-wrap:wrap; color:var(--edge-text-muted,#667085); }.action-feedback strong { color:var(--edge-text,#101828); }.action-feedback--error { border-color:var(--edge-danger,#b42318); }.action-feedback--error strong,.action-feedback--error span { color:var(--edge-danger,#b42318); }.inline-error { padding:18px; color:var(--edge-danger,#b42318); text-align:center; }.safety-note { display:flex; gap:8px; flex-wrap:wrap; color:var(--edge-text-muted,#667085); }.safety-note strong { color:var(--edge-text,#101828); }
@media (max-width:1100px) { .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.rfq-controls,.return-grid,.landed-cost-controls { grid-template-columns:1fr; } } @media (max-width:980px) { .filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.purchasing-hero,.panel-heading { flex-direction:column; } } @media (max-width:560px) { .metric-grid,.filter-grid { grid-template-columns:1fr; } }
</style>