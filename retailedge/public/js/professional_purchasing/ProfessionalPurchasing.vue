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
				description="Control Purchase Order receiving from one operational workspace while ERPNext remains authoritative for suppliers, quantities, taxes, stock and accounting."
			/>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading purchasing operations..." />
			<EdgeErrorState v-else-if="error && !loaded" :message="error" @retry="loadWorkspace" />

			<div v-else class="purchasing-content">
				<section class="edge-panel purchasing-hero">
					<div>
						<span class="purchasing-kicker">Purchase operations</span>
						<h3>Purchase Order → Receipt</h3>
						<p>Prepare draft Purchase Receipts only from current submitted ERPNext Purchase Orders. Full native forms remain available for complex buying cases.</p>
					</div>
					<div class="hero-actions">
						<button v-if="capabilities.can_create_purchase_order" type="button" class="edge-button edge-button--primary" @click="newPurchaseOrder">New Purchase Order</button>
						<button v-if="capabilities.can_read_purchase_receipt" type="button" class="edge-button edge-button--secondary" @click="openPurchaseReceipts">Purchase Receipts</button>
					</div>
				</section>

				<section class="edge-panel filter-panel">
					<div class="filter-grid">
						<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
						<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="Operating branch" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
						<EdgeLinkField v-model="filters.supplier" label="Supplier" placeholder="All suppliers" :searcher="supplierSearch" @select="onSupplierSelected" @clear="clearSupplier" />
						<div class="filter-action"><button type="button" class="edge-button edge-button--primary" :disabled="loading || !filters.company" @click="loadOrders">{{ loading ? "Refreshing…" : "Apply Filters" }}</button></div>
					</div>
				</section>

				<div class="metric-grid">
					<article class="edge-panel metric-card"><span>Purchase Orders</span><strong>{{ summary.purchase_orders || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Ready to Receive</span><strong>{{ summary.to_receive || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Draft Orders</span><strong>{{ summary.drafts || 0 }}</strong></article>
					<article class="edge-panel metric-card"><span>Submitted PO Value</span><strong>{{ formatMoney(summary.open_value || 0) }}</strong></article>
				</div>

				<section class="edge-panel orders-panel">
					<div class="panel-heading">
						<div><span class="purchasing-kicker">ERPNext source of truth</span><h3>Purchase Orders</h3></div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="loading" @click="loadOrders">Refresh</button>
					</div>
					<div v-if="error" class="inline-error">{{ error }}</div>
					<EdgeLoadingState v-else-if="loading" message="Refreshing Purchase Orders..." />
					<EdgeEmptyState v-else-if="!rows.length" title="No Purchase Orders found" description="No permitted Purchase Orders match this Company, Branch and Supplier scope." />
					<div v-else class="table-wrap">
						<table class="purchasing-table">
							<thead>
								<tr>
									<th><button type="button" class="sort-button" @click="sortBy('name')">Purchase Order {{ sortMark('name') }}</button></th>
									<th><button type="button" class="sort-button" @click="sortBy('transaction_date')">Date {{ sortMark('transaction_date') }}</button></th>
									<th><button type="button" class="sort-button" @click="sortBy('supplier_name')">Supplier {{ sortMark('supplier_name') }}</button></th>
									<th>Branch</th><th>Status</th>
									<th class="num"><button type="button" class="sort-button" @click="sortBy('per_received')">Received {{ sortMark('per_received') }}</button></th>
									<th class="num"><button type="button" class="sort-button" @click="sortBy('per_billed')">Billed {{ sortMark('per_billed') }}</button></th>
									<th class="num"><button type="button" class="sort-button" @click="sortBy('grand_total')">Total {{ sortMark('grand_total') }}</button></th>
									<th>Actions</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in sortedRows" :key="row.name">
									<td><button type="button" class="link-button" @click="openPurchaseOrder(row.name)">{{ row.name }}</button></td>
									<td>{{ formatDate(row.transaction_date) }}</td>
									<td>{{ row.supplier_name || row.supplier }}</td>
									<td>{{ row.branch || "—" }}</td>
									<td><span class="status-pill">{{ row.status || (row.docstatus === 0 ? "Draft" : "Submitted") }}</span></td>
									<td class="num">{{ formatPercent(row.per_received) }}</td>
									<td class="num">{{ formatPercent(row.per_billed) }}</td>
									<td class="num strong">{{ formatMoney(row.grand_total, row.currency) }}</td>
									<td class="actions-cell">
										<button type="button" class="edge-small-button" @click="openPurchaseOrder(row.name)">Open</button>
										<button v-if="row.can_prepare_receipt" type="button" class="edge-small-button edge-small-button--primary" :disabled="preparing === row.name" @click="prepareReceipt(row)">{{ preparing === row.name ? "Preparing…" : "Prepare Receipt" }}</button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>

				<section class="edge-panel safety-note">
					<strong>Draft-first stock safety.</strong>
					<span>The receipt action uses ERPNext's Purchase Order mapper and creates only a draft Purchase Receipt. Stock changes occur only through the standard ERPNext submission workflow.</span>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.professional_purchasing.get_professional_purchasing_context";
const SEARCH_METHOD = "retailedge.professional_purchasing.search_professional_purchasing_options";
const PREPARE_RECEIPT_METHOD = "retailedge.professional_purchasing.prepare_purchase_receipt_draft";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeLinkField"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?._server_messages || fallback; }
function doctypeSlug(doctype) { return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""); }

export default {
	name: "RetailEdgeProfessionalPurchasing",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			company: "",
			branch: "",
			userName: "",
			menuItems: [],
			filters: { company: "", branch: "", supplier: "" },
			summary: {},
			capabilities: {},
			rows: [],
			preparing: "",
			sort: { key: "transaction_date", direction: "desc" },
		};
	},
	computed: {
		sortedRows() {
			const rows = [...this.rows]; const { key, direction } = this.sort; const factor = direction === "asc" ? 1 : -1;
			return rows.sort((a, b) => {
				const av = a?.[key] ?? ""; const bv = b?.[key] ?? "";
				if (typeof av === "number" || typeof bv === "number") return (Number(av || 0) - Number(bv || 0)) * factor;
				return String(av).localeCompare(String(bv)) * factor;
			});
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadWorkspace();
	},
	mounted() {
		window.addEventListener("retailedge-professional-purchasing-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadWorkspace();
	},
	beforeUnmount() { window.removeEventListener("retailedge-professional-purchasing-page-show", this._onPageShow); },
	methods: {
		async loadWorkspace() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod(CONTEXT_METHOD, { company: this.filters.company || null, branch: this.filters.branch || null, supplier: this.filters.supplier || null, limit: 200 }), navigationPromise]);
				this.applyContext(context || {}); this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []); this.loaded = true;
			} catch (error) { this.error = errorMessage(error, "Professional Purchasing failed to load."); }
			finally { this.loading = false; }
		},
		async loadOrders() { return this.loadWorkspace(); },
		applyContext(context) {
			this.company = context.company || this.filters.company || ""; this.branch = context.branch || this.filters.branch || "";
			if (!this.filters.company) this.filters.company = this.company; if (!this.filters.branch) this.filters.branch = this.branch;
			this.userName = context.user_name || this.userName; this.rows = context.rows || []; this.summary = context.summary || {}; this.capabilities = context.capabilities || {};
		},
		async searchOptions(kind, txt) { const result = await callMethod(SEARCH_METHOD, { kind, txt, company: this.filters.company || null }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); }, supplierSearch(txt) { return this.searchOptions("supplier", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.supplier = ""; this.branch = ""; this.loadWorkspace(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.branch = option.label || option.value; this.loadWorkspace(); },
		clearBranch() { this.filters.branch = ""; this.branch = ""; this.loadWorkspace(); },
		onSupplierSelected(option) { this.filters.supplier = option.value; this.loadWorkspace(); }, clearSupplier() { this.filters.supplier = ""; this.loadWorkspace(); },
		async prepareReceipt(row) {
			if (!row?.name || this.preparing) return; this.preparing = row.name;
			try {
				const result = await callMethod(PREPARE_RECEIPT_METHOD, { purchase_order: row.name });
				frappe.show_alert({ message: __("Draft Purchase Receipt prepared from ERPNext Purchase Order."), indicator: "green" });
				if (result.name) frappe.set_route("Form", "Purchase Receipt", result.name);
			} catch (error) { frappe.msgprint({ title: __("Could not prepare Purchase Receipt"), message: errorMessage(error, "ERPNext could not prepare the receipt draft."), indicator: "red" }); }
			finally { this.preparing = ""; }
		},
		newPurchaseOrder() { frappe.new_doc("Purchase Order"); },
		openPurchaseOrder(name) { frappe.set_route("Form", "Purchase Order", name); },
		openPurchaseReceipts() { frappe.set_route("List", "Purchase Receipt"); },
		sortBy(key) { if (this.sort.key === key) this.sort.direction = this.sort.direction === "asc" ? "desc" : "asc"; else this.sort = { key, direction: "asc" }; },
		sortMark(key) { return this.sort.key === key ? (this.sort.direction === "asc" ? "↑" : "↓") : ""; },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		formatMoney(value, currency) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency", options: currency || "" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatPercent(value) { return `${Number(value || 0).toFixed(1)}%`; },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.purchasing-fallback,.edge-panel { border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
.purchasing-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; }
.purchasing-content { display:flex; flex-direction:column; gap:var(--edge-space-lg,20px); padding-bottom:24px; }
.purchasing-hero,.panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; }
.purchasing-hero,.filter-panel,.orders-panel,.safety-note { padding:18px; }
.purchasing-hero h3,.panel-heading h3 { margin:3px 0 6px; color:var(--edge-text,#101828); }
.purchasing-hero p { margin:0; max-width:820px; color:var(--edge-text-muted,#667085); }
.purchasing-kicker { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--edge-primary,#0f766e); }
.hero-actions,.actions-cell { display:flex; gap:8px; flex-wrap:wrap; }
.filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; }
.filter-action { display:flex; }
.metric-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.metric-card { padding:16px; display:flex; flex-direction:column; gap:6px; }
.metric-card span { color:var(--edge-text-muted,#667085); font-size:.8rem; } .metric-card strong { color:var(--edge-text,#101828); font-size:1.2rem; }
.panel-heading { margin-bottom:14px; }.panel-heading h3 { margin-bottom:0; }
.table-wrap { width:100%; overflow:auto; }.purchasing-table { width:100%; min-width:1080px; border-collapse:collapse; }
.purchasing-table th,.purchasing-table td { padding:10px 9px; border-bottom:1px solid var(--edge-border,#e5e7eb); text-align:left; color:var(--edge-text,#101828); }
.purchasing-table th { font-size:.75rem; color:var(--edge-text-muted,#667085); text-transform:uppercase; letter-spacing:.03em; }.purchasing-table .num { text-align:right; }.strong { font-weight:700; }
.sort-button,.link-button { border:0; background:transparent; padding:0; color:inherit; cursor:pointer; font:inherit; text-transform:inherit; letter-spacing:inherit; }.link-button { color:var(--edge-primary,#0f766e); font-weight:600; }
.status-pill { display:inline-flex; padding:3px 8px; border:1px solid var(--edge-border,#d9d9d9); border-radius:999px; font-size:.75rem; }
.edge-button,.edge-small-button { min-height:38px; border-radius:var(--edge-radius-md,8px); padding:0 12px; font-weight:600; cursor:pointer; border:1px solid var(--edge-border,#d9d9d9); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); }
.edge-button--primary,.edge-small-button--primary { border-color:var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; }.edge-small-button { min-height:30px; padding:0 9px; font-size:.78rem; }button:disabled { opacity:.55; cursor:not-allowed; }
.inline-error { padding:18px; color:var(--edge-danger,#b42318); text-align:center; }.safety-note { display:flex; gap:8px; flex-wrap:wrap; color:var(--edge-text-muted,#667085); }.safety-note strong { color:var(--edge-text,#101828); }
@media (max-width:980px) { .metric-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }.purchasing-hero { flex-direction:column; } }
@media (max-width:560px) { .metric-grid,.filter-grid { grid-template-columns:1fr; } }
</style>
