<template>
	<div v-if="!edgeUIValid" class="project-fallback">
		<strong>Project Operations could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell v-else product="RetailEdge" title="Project Operations" :tenantName="context.company || ''" :branchName="branch" :userName="userName" :menuItems="menuItems" activeRoute="/app/project-operations" :hideNativeSidebar="true" @navigate="handleNavigation">
		<section class="project-page">
			<header class="project-hero">
				<div>
					<div class="project-eyebrow">Projects & Funds</div>
					<h2>{{ context.project_name || "Project Operations" }}</h2>
					<p>Operational and financial visibility over ERPNext Project, Payment Entry and native project accounting dimensions.</p>
				</div>
				<div class="hero-actions">
					<button class="edge-secondary-button" type="button" :disabled="!project" @click="openProject">Open ERPNext Project</button>
					<button class="edge-primary-button" type="button" :disabled="!project || !context.customer" @click="openReceiptDialog">Record Project Receipt</button>
				</div>
			</header>

			<section class="project-panel">
				<div class="filter-grid">
					<EdgeLinkField v-model="project" :selectedLabel="projectLabel" label="Project" required placeholder="Search projects" :searcher="projectSearch" @select="onProjectSelected" @clear="clearProject" />
					<div class="field-block"><label>Branch</label><input v-model="branch" class="form-control" placeholder="Optional branch scope" @change="loadContext" /></div>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !project" @click="loadContext">{{ loading ? "Refreshing…" : "Refresh" }}</button></div>
				</div>
			</section>

			<div v-if="error" class="project-error">{{ error }}</div>
			<div v-else-if="loading" class="project-state">Loading project funds…</div>
			<template v-else-if="project && context.project">
				<div class="project-cards">
					<article class="metric-card"><span>Sales Order Value</span><strong>{{ money(context.sales_order_value) }}</strong></article>
					<article class="metric-card"><span>Billed</span><strong>{{ money(context.billed_amount) }}</strong></article>
					<article class="metric-card"><span>Funds Received</span><strong>{{ money(context.funds_received) }}</strong></article>
					<article class="metric-card"><span>Funds Paid Out</span><strong>{{ money(context.funds_paid_out) }}</strong></article>
					<article class="metric-card"><span>Cash Funds Position</span><strong>{{ money(context.cash_funds_position) }}</strong></article>
					<article class="metric-card"><span>Tracked Cost</span><strong>{{ money(context.tracked_cost) }}</strong></article>
					<article class="metric-card"><span>Gross Margin</span><strong>{{ money(context.gross_margin) }}</strong></article>
					<article class="metric-card"><span>Progress</span><strong>{{ context.percent_complete || 0 }}%</strong></article>
				</div>

				<section class="project-panel">
					<div class="panel-head"><div><h3>Project Summary</h3><p>ERPNext Project remains authoritative for project identity, costing, billing and margin.</p></div></div>
					<div class="summary-grid">
						<div><span>Project</span><strong>{{ context.project }}</strong></div>
						<div><span>Status</span><strong>{{ context.status || "—" }}</strong></div>
						<div><span>Customer</span><strong>{{ context.customer || "—" }}</strong></div>
						<div><span>Company</span><strong>{{ context.company || "—" }}</strong></div>
						<div><span>Cost Center</span><strong>{{ context.cost_center || "—" }}</strong></div>
						<div><span>Unapplied Receipts</span><strong>{{ money(context.unallocated_receipts) }}</strong></div>
					</div>
				</section>

				<section class="project-panel">
					<div class="panel-head"><div><h3>Project Transaction Timeline</h3><p>Read-only view of permitted ERPNext Sales Orders, Sales Invoices, Purchase Invoices, Expense Claims and Stock Entries linked to this Project. Cancelled documents are excluded.</p></div><span>{{ context.timeline_count || 0 }} records</span></div>
					<div v-if="!context.timeline?.length" class="project-state">No project-linked operational documents found for the current scope.</div>
					<div v-else class="table-wrap"><table class="project-table"><thead><tr><th>Date</th><th>Type</th><th>Document</th><th>Status</th><th>Party</th><th class="num">Amount</th></tr></thead><tbody><tr v-for="row in context.timeline" :key="`${row.doctype}-${row.name}`"><td>{{ row.date || "—" }}</td><td>{{ row.label }}</td><td><button class="link-button" @click="openTimelineDoc(row)">{{ row.name }}</button></td><td>{{ row.status || "—" }}</td><td>{{ row.party || "—" }}</td><td class="num">{{ row.amount ? money(row.amount) : "—" }}</td></tr></tbody></table></div>
				</section>

				<section class="project-panel">
					<div class="panel-head"><div><h3>Project Receipts</h3><p>Submitted ERPNext Payment Entries explicitly linked to this Project.</p></div></div>
					<div v-if="!context.customer_receipts?.length" class="project-state">No submitted project receipts found.</div>
					<div v-else class="table-wrap"><table class="project-table"><thead><tr><th>Payment</th><th>Date</th><th>Party</th><th>Mode</th><th class="num">Received</th><th class="num">Unapplied</th></tr></thead><tbody><tr v-for="row in context.customer_receipts" :key="row.name"><td><button class="link-button" @click="openPayment(row.name)">{{ row.name }}</button></td><td>{{ row.posting_date }}</td><td>{{ row.party }}</td><td>{{ row.mode_of_payment || "—" }}</td><td class="num">{{ money(row.received_amount) }}</td><td class="num">{{ money(row.unallocated_amount) }}</td></tr></tbody></table></div>
				</section>

				<section class="project-panel">
					<div class="panel-head"><div><h3>Project Payments</h3><p>Submitted outgoing Payment Entries explicitly attributed to this Project.</p></div></div>
					<div v-if="!context.project_payments?.length" class="project-state">No submitted project payments found.</div>
					<div v-else class="table-wrap"><table class="project-table"><thead><tr><th>Payment</th><th>Date</th><th>Party</th><th>Mode</th><th class="num">Paid</th></tr></thead><tbody><tr v-for="row in context.project_payments" :key="row.name"><td><button class="link-button" @click="openPayment(row.name)">{{ row.name }}</button></td><td>{{ row.posting_date }}</td><td>{{ row.party }}</td><td>{{ row.mode_of_payment || "—" }}</td><td class="num">{{ money(row.paid_amount) }}</td></tr></tbody></table></div>
				</section>

				<div class="accounting-note"><strong>Accounting safety:</strong> Project Funds is a derived management view. ERPNext Project and project-linked native documents remain the source of truth; RetailEdge does not maintain a project wallet or separate ledger.</div>
			</template>
		</section>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (r) => resolve(r.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ProjectOperations",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() { return { edgeUIValid: true, missingComponents: [], loading: false, error: "", project: "", projectLabel: "", branch: "", context: {}, menuItems: [], userName: "" }; },
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.loadNavigation(); },
	methods: {
		async loadNavigation() { try { const navigation = typeof window.retailedgeGetBusinessHubContext === "function" ? await window.retailedgeGetBusinessHubContext() : await callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context"); this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []); this.userName = navigation.user_name || navigation.context?.user_name || ""; } catch (error) { this.error = errorMessage(error, "Failed to load Project Operations navigation."); } },
		async projectSearch(txt) { const result = await callMethod("retailedge.project_search.search_projects", { txt, limit: 20 }); return Array.isArray(result) ? result : []; },
		onProjectSelected(option) { this.project = option.value; this.projectLabel = option.label || option.value; this.loadContext(); },
		clearProject() { this.project = ""; this.projectLabel = ""; this.context = {}; this.error = ""; },
		async loadContext() { if (!this.project) return; this.loading = true; this.error = ""; try { this.context = await callMethod("retailedge.project_operations.get_project_funds_context", { project: this.project, branch: this.branch || null }); } catch (error) { this.context = {}; this.error = errorMessage(error, "Project funds failed to load."); } finally { this.loading = false; } },
		openReceiptDialog() { const dialog = new frappe.ui.Dialog({ title: __("Record Project Receipt"), fields: [ { fieldname: "project", fieldtype: "Data", label: __("Project"), default: this.project, read_only: 1 }, { fieldname: "customer", fieldtype: "Data", label: __("Customer"), default: this.context.customer, read_only: 1 }, { fieldname: "company", fieldtype: "Data", label: __("Company"), default: this.context.company, read_only: 1 }, { fieldname: "branch", fieldtype: "Data", label: __("Branch"), default: this.branch || "" }, { fieldname: "posting_date", fieldtype: "Date", label: __("Posting Date"), default: frappe.datetime.get_today(), reqd: 1 }, { fieldname: "mode_of_payment", fieldtype: "Link", options: "Mode of Payment", label: __("Mode of Payment"), reqd: 1 }, { fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1 }, { fieldname: "reference_no", fieldtype: "Data", label: __("Reference No") }, { fieldname: "reference_date", fieldtype: "Date", label: __("Reference Date") }, { fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") } ], primary_action_label: __("Create Draft Payment"), primary_action: async (values) => { try { const result = await callMethod("retailedge.project_receipts.create_project_receipt_draft", { values }); dialog.hide(); frappe.show_alert({ message: __("Project receipt draft created."), indicator: "green" }); if (result.name) frappe.set_route("Form", "Payment Entry", result.name); } catch (error) { frappe.msgprint({ title: __("Could not create project receipt"), message: errorMessage(error, "Project receipt draft could not be created."), indicator: "red" }); } } }); dialog.show(); },
		openProject() { if (this.project) frappe.set_route("Form", "Project", this.project); },
		openPayment(name) { frappe.set_route("Form", "Payment Entry", name); },
		openTimelineDoc(row) { if (row?.doctype && row?.name) frappe.set_route("Form", row.doctype, row.name); },
		money(value) { return format_currency(Number(value || 0), this.context.currency || undefined); },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target) window.location.href = item.target; },
	},
};
</script>

<style scoped>
.project-page{display:grid;gap:16px;padding:18px}.project-hero,.panel-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.project-eyebrow{font-size:12px;text-transform:uppercase;letter-spacing:.08em;opacity:.7}.hero-actions{display:flex;gap:8px;flex-wrap:wrap}.project-panel,.metric-card,.accounting-note{border:1px solid var(--border-color);border-radius:12px;padding:16px;background:var(--card-bg)}.filter-grid,.project-cards,.summary-grid{display:grid;gap:12px}.filter-grid{grid-template-columns:minmax(260px,1fr) minmax(180px,.5fr) auto;align-items:end}.project-cards{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))}.summary-grid{grid-template-columns:repeat(auto-fit,minmax(180px,1fr))}.metric-card span,.summary-grid span{display:block;font-size:12px;opacity:.7}.metric-card strong{display:block;font-size:20px;margin-top:6px}.summary-grid strong{display:block;margin-top:4px}.table-wrap{overflow:auto}.project-table{width:100%;border-collapse:collapse}.project-table th,.project-table td{padding:10px;border-bottom:1px solid var(--border-color);text-align:left}.project-table .num{text-align:right}.link-button{background:none;border:0;padding:0;color:var(--primary);cursor:pointer}.project-error{padding:12px;border-radius:8px;background:var(--alert-bg-danger);color:var(--text-color)}.project-state{padding:18px;text-align:center;opacity:.7}.accounting-note{font-size:13px}.field-block label{display:block;font-size:12px;margin-bottom:6px}.filter-action{padding-bottom:1px}@media(max-width:800px){.project-hero,.panel-head{flex-direction:column}.filter-grid{grid-template-columns:1fr}.hero-actions{width:100%}}
</style>
