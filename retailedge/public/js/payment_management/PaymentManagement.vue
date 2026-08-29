<template>
	<div v-if="!edgeUIValid" class="payment-fallback">
		<strong>Payment Management could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Payment Management"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/payment-management"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<section class="payment-page">
			<header class="payment-hero">
				<div>
					<div class="payment-eyebrow">Customers & Receivables</div>
					<h2>Advanced Payment Management</h2>
					<p>Record customer advances, see unapplied receipts, and apply them to submitted Sales Invoices using ERPNext Payment Entry and Payment Reconciliation accounting truth.</p>
				</div>
				<div class="hero-actions">
					<button class="edge-secondary-button" type="button" @click="openPaymentEntries">Payment Entries</button>
					<button class="edge-primary-button" type="button" :disabled="!filters.company" @click="openAdvanceDialog">Record Advance</button>
				</div>
			</header>

			<div class="payment-cards">
				<article class="metric-card"><span>Available Advances</span><strong>{{ formatCurrency(context.available_advance || 0) }}</strong></article>
				<article class="metric-card"><span>Unapplied Receipts</span><strong>{{ context.advance_count || 0 }}</strong></article>
				<article class="metric-card"><span>Accounting Source</span><strong>Payment Entry</strong></article>
			</div>

			<section class="payment-panel">
				<div class="panel-head">
					<div><h3>Customer Advances</h3><p>Submitted customer receipts with a positive ERPNext unallocated amount.</p></div>
					<button class="edge-secondary-button" type="button" :disabled="loading" @click="loadAdvances">{{ loading ? "Refreshing…" : "Refresh" }}</button>
				</div>
				<div class="filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="filters.customer" :selectedLabel="customerLabel" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="loadAdvances">Apply Filters</button></div>
				</div>

				<div v-if="error" class="payment-error">{{ error }}</div>
				<div v-else-if="loading" class="payment-state">Loading customer advances…</div>
				<div v-else-if="!advances.length" class="payment-state">No unapplied customer advances match the current scope.</div>
				<div v-else class="table-wrap">
					<table class="payment-table">
						<thead><tr><th>Payment</th><th>Date</th><th>Customer</th><th>Branch</th><th>Mode</th><th class="num">Received</th><th class="num">Available</th><th>Actions</th></tr></thead>
						<tbody>
							<tr v-for="row in advances" :key="row.name">
								<td><button class="link-button" @click="openPayment(row.name)">{{ row.name }}</button></td>
								<td>{{ formatDate(row.posting_date) }}</td>
								<td>{{ row.customer }}</td>
								<td>{{ row.branch || "—" }}</td>
								<td>{{ row.mode_of_payment || "—" }}</td>
								<td class="num">{{ formatCurrency(row.received_amount) }}</td>
								<td class="num strong">{{ formatCurrency(row.unallocated_amount) }}</td>
								<td><button class="edge-small-button" type="button" @click="openApplyDialog(row)">Apply to Invoice</button></td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<div class="accounting-note">
				<strong>Accounting safety:</strong> RetailEdge does not maintain a separate advance balance. The available amount above is the current ERPNext Payment Entry <code>unallocated_amount</code>. Allocation is performed through ERPNext Payment Reconciliation.
			</div>
		</section>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "PaymentManagement",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			error: "",
			context: {},
			advances: [],
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			customerLabel: "",
			filters: { company: "", branch: "", customer: "" },
		};
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() { this.loadMetadata(); },
	methods: {
		async loadMetadata() {
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [receivablesContext, navigation] = await Promise.all([
					callMethod("retailedge.customer_receivables.get_customer_receivables_context"),
					navigationPromise,
				]);
				this.filters.company = receivablesContext.default_filters?.company || "";
				this.filters.branch = receivablesContext.default_filters?.branch || "";
				this.tenantName = receivablesContext.tenant_name || this.filters.company;
				this.branchName = receivablesContext.branch_name || this.filters.branch;
				this.userName = receivablesContext.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.loadAdvances();
			} catch (error) { this.error = errorMessage(error, "Failed to load Payment Management controls."); }
		},
		async loadAdvances() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod("retailedge.advanced_payments.get_customer_advance_context", {
					customer: this.filters.customer || null,
					company: this.filters.company,
					branch: this.filters.branch || null,
					limit: 100,
				});
				this.context = result || {};
				this.advances = result.advances || [];
			} catch (error) { this.advances = []; this.context = {}; this.error = errorMessage(error, "Customer advances failed to load."); }
			finally { this.loading = false; }
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.customer_receivables.search_customer_receivables_options", { kind, txt, company: this.filters.company });
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		customerSearch(txt) { return this.searchOptions("customer", txt); },
		onCompanySelected(option) { this.filters.company = option.value; this.filters.branch = ""; this.filters.customer = ""; this.branchName = ""; this.customerLabel = ""; this.loadAdvances(); },
		onBranchSelected(option) { this.filters.branch = option.value; this.branchName = option.label || option.value; this.loadAdvances(); },
		clearBranch() { this.filters.branch = ""; this.branchName = ""; this.loadAdvances(); },
		onCustomerSelected(option) { this.filters.customer = option.value; this.customerLabel = option.label || option.value; this.loadAdvances(); },
		clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; this.loadAdvances(); },
		openAdvanceDialog() {
			const dialog = new frappe.ui.Dialog({
				title: __("Record Customer Advance"),
				fields: [
					{ fieldname: "company", fieldtype: "Link", options: "Company", label: __("Company"), reqd: 1, default: this.filters.company, read_only: 1 },
					{ fieldname: "branch", fieldtype: "Link", options: "Branch", label: __("Branch"), default: this.filters.branch || "" },
					{ fieldname: "customer", fieldtype: "Link", options: "Customer", label: __("Customer"), reqd: 1, default: this.filters.customer || "" },
					{ fieldname: "posting_date", fieldtype: "Date", label: __("Posting Date"), reqd: 1, default: frappe.datetime.get_today() },
					{ fieldname: "mode_of_payment", fieldtype: "Link", options: "Mode of Payment", label: __("Mode of Payment"), reqd: 1 },
					{ fieldname: "amount", fieldtype: "Currency", label: __("Amount"), reqd: 1 },
					{ fieldname: "reference_no", fieldtype: "Data", label: __("Reference No") },
					{ fieldname: "reference_date", fieldtype: "Date", label: __("Reference Date") },
					{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks") },
				],
				primary_action_label: __("Create Draft Payment"),
				primary_action: async (values) => {
					try {
						const result = await callMethod("retailedge.advanced_payments.create_customer_advance_draft", { values });
						dialog.hide();
						frappe.show_alert({ message: __("Customer advance draft created."), indicator: "green" });
						if (result.name) frappe.set_route("Form", "Payment Entry", result.name);
					} catch (error) { frappe.msgprint({ title: __("Could not create advance"), message: errorMessage(error, "Payment Entry draft could not be created."), indicator: "red" }); }
				},
			});
			dialog.show();
		},
		openApplyDialog(row) {
			const dialog = new frappe.ui.Dialog({
				title: __("Apply Customer Advance"),
				fields: [
					{ fieldname: "payment_entry", fieldtype: "Data", label: __("Payment Entry"), default: row.name, read_only: 1 },
					{ fieldname: "customer", fieldtype: "Data", label: __("Customer"), default: row.customer, read_only: 1 },
					{ fieldname: "available", fieldtype: "Currency", label: __("Available Advance"), default: row.unallocated_amount, read_only: 1 },
					{ fieldname: "sales_invoice", fieldtype: "Link", options: "Sales Invoice", label: __("Sales Invoice"), reqd: 1, get_query: () => ({ filters: { company: row.company, customer: row.customer, docstatus: 1 } }) },
					{ fieldname: "allocated_amount", fieldtype: "Currency", label: __("Amount to Apply"), reqd: 1 },
				],
				primary_action_label: __("Apply through ERPNext"),
				primary_action: async (values) => {
					try {
						const invoiceContext = await callMethod("retailedge.advanced_payments.get_sales_invoice_advance_context", { sales_invoice: values.sales_invoice, limit: 100 });
						const eligible = (invoiceContext.eligible_advances || []).some((advance) => advance.name === row.name);
						if (!eligible) throw new Error(__("This advance is not eligible for the selected Sales Invoice."));
						await callMethod("retailedge.payment_application.apply_customer_advance", {
							sales_invoice: values.sales_invoice,
							payment_entry: row.name,
							allocated_amount: values.allocated_amount,
						});
						dialog.hide();
						frappe.show_alert({ message: __("Advance applied through ERPNext Payment Reconciliation."), indicator: "green" });
						await this.loadAdvances();
					} catch (error) { frappe.msgprint({ title: __("Could not apply advance"), message: errorMessage(error, "Payment reconciliation failed."), indicator: "red" }); }
				},
			});
			dialog.show();
		},
		openPaymentEntries() { frappe.set_route("List", "Payment Entry"); },
		openPayment(name) { frappe.set_route("Form", "Payment Entry", name); },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); else if (item.target_type === "URL" && item.target) window.location.assign(item.target); },
		formatCurrency(value) { try { return frappe.format(Number(value || 0), { fieldtype: "Currency", options: this.context.currency || "" }); } catch (_error) { return Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); } },
		formatDate(value) { if (!value) return "—"; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
	},
};
</script>

<style scoped>
.payment-fallback,.payment-panel,.accounting-note,.metric-card { border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
.payment-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; }
.payment-page { display:flex; flex-direction:column; gap:var(--edge-space-lg,20px); padding-bottom:24px; }
.payment-hero { display:flex; justify-content:space-between; gap:20px; align-items:flex-start; padding:8px 2px; }
.payment-hero h2 { margin:4px 0 6px; color:var(--edge-text,#101828); }
.payment-hero p { margin:0; max-width:850px; color:var(--edge-text-muted,#667085); }
.payment-eyebrow { font-size:.78rem; font-weight:700; text-transform:uppercase; letter-spacing:.05em; color:var(--edge-primary,#0f766e); }
.hero-actions { display:flex; gap:8px; flex-wrap:wrap; }
.payment-cards { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.metric-card { padding:16px; display:flex; flex-direction:column; gap:6px; }
.metric-card span { color:var(--edge-text-muted,#667085); font-size:.8rem; }
.metric-card strong { color:var(--edge-text,#101828); font-size:1.25rem; }
.payment-panel { padding:18px; }
.panel-head { display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:16px; }
.panel-head h3 { margin:0 0 4px; color:var(--edge-text,#101828); }
.panel-head p { margin:0; color:var(--edge-text-muted,#667085); }
.filter-grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; margin-bottom:18px; }
.filter-action { display:flex; }
.edge-primary-button,.edge-secondary-button,.edge-small-button { min-height:38px; border-radius:var(--edge-radius-md,8px); padding:0 12px; font-weight:600; cursor:pointer; }
.edge-primary-button { border:1px solid var(--edge-primary,#0f766e); background:var(--edge-primary,#0f766e); color:#fff; }
.edge-secondary-button,.edge-small-button { border:1px solid var(--edge-border,#d9d9d9); background:var(--edge-surface,#fff); color:var(--edge-text,#101828); }
.edge-small-button { min-height:30px; padding:0 9px; font-size:.78rem; }
button:disabled { opacity:.55; cursor:not-allowed; }
.table-wrap { width:100%; overflow:auto; }
.payment-table { width:100%; border-collapse:collapse; min-width:900px; }
.payment-table th,.payment-table td { padding:10px 9px; border-bottom:1px solid var(--edge-border,#e5e7eb); text-align:left; color:var(--edge-text,#101828); }
.payment-table th { font-size:.76rem; color:var(--edge-text-muted,#667085); text-transform:uppercase; letter-spacing:.03em; }
.payment-table .num { text-align:right; }
.payment-table .strong { font-weight:700; }
.link-button { border:0; background:transparent; color:var(--edge-primary,#0f766e); padding:0; cursor:pointer; font-weight:600; }
.payment-state,.payment-error { padding:28px; text-align:center; color:var(--edge-text-muted,#667085); }
.payment-error { color:var(--edge-danger,#b42318); }
.accounting-note { padding:14px 16px; color:var(--edge-text-muted,#667085); }
.accounting-note strong { color:var(--edge-text,#101828); }
@media (max-width:900px) { .payment-hero { flex-direction:column; } .payment-cards { grid-template-columns:1fr; } .filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:560px) { .filter-grid { grid-template-columns:1fr; } }
</style>
