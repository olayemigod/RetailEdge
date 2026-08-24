<template>
	<div v-if="!edgeUIValid" class="customer-opportunity-fallback">
		<strong>Customer Retention & Opportunity Intelligence could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Customer Retention & Opportunity Intelligence"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/customer-opportunity-intelligence"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Customer Retention & Opportunity Intelligence"
			eyebrow="Retention & Growth"
			subtitle="Compare the selected period with the immediately preceding equal-length period to find explainable follow-up and growth signals without labelling customers as churned."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="customer"
			:formatter="formatCell"
			emptyTitle="No comparable customer activity found"
			emptyDescription="Adjust the period, company, branch, customer or threshold and try again."
			loadingMessage="Comparing customer behaviour…"
			@retry="fetchData"
			@cell-click="openReportCell"
		>
			<template #actions>
				<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
			</template>

			<template #filters>
				<div class="customer-opportunity-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<label class="edge-field">
						<span class="edge-field-label">Current From Date</span>
						<input v-model="filters.from_date" class="edge-input" type="date" />
					</label>
					<label class="edge-field">
						<span class="edge-field-label">Current To Date</span>
						<input v-model="filters.to_date" class="edge-input" type="date" />
					</label>
					<EdgeLinkField v-model="filters.customer" :selectedLabel="customerLabel" label="Customer" placeholder="All customers" :searcher="customerSearch" @select="onCustomerSelected" @clear="clearCustomer" />
					<label class="edge-field">
						<span class="edge-field-label">Change Threshold (%)</span>
						<input v-model.number="filters.change_threshold_percent" class="edge-input" type="number" min="5" max="90" step="5" />
					</label>
					<div class="filter-action">
						<button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="fetchData">
							{{ loading ? "Comparing…" : "Compare Periods" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span v-if="scope.current_from_date && scope.current_to_date">Current: {{ scope.current_from_date }} to {{ scope.current_to_date }}</span>
				<span v-if="scope.prior_from_date && scope.prior_to_date">Prior: {{ scope.prior_from_date }} to {{ scope.prior_to_date }}</span>
				<span>Threshold: {{ scope.change_threshold_percent || filters.change_threshold_percent }}%</span>
				<span>Signals describe observed comparable-period behaviour; RetailEdge does not call these customers churned</span>
				<span>Outstanding and overdue values are current ERPNext receivable exposure</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "CustomerOpportunityIntelligence",
	props: {
		pageMethod: { type: String, required: true },
		exportMethod: { type: String, required: true },
	},
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			rows: [],
			columns: [],
			summary: [],
			scope: {},
			metadata: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			customerLabel: "",
			filters: {
				company: "",
				branch: "",
				from_date: "",
				to_date: "",
				customer: "",
				change_threshold_percent: 25,
			},
		};
	},
	computed: {
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || "Data",
				clickable: column.fieldname === "customer",
				sortable: false,
			}));
		},
		exportDataset() {
			return {
				title: "Customer Retention & Opportunity Intelligence",
				filename: `RetailEdge Customer Retention Opportunity ${this.filters.company || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company",
				branch: "Branch",
				from_date: "Current From Date",
				to_date: "Current To Date",
				customer: "Customer",
				change_threshold_percent: "Change Threshold (%)",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() {
			return [
				{ label: "Sales Source", value: this.metadata.sales_truth || "Submitted ERPNext Sales Invoice" },
				{ label: "Comparison", value: this.metadata.comparison_basis || "Current versus preceding equal-length period" },
				{ label: "Receivables", value: this.metadata.receivable_truth || "Current ERPNext outstanding exposure" },
				{ label: "Interpretation", value: this.metadata.signal_rule || "Observed behaviour only; no churn claim" },
			];
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.sales_reporting.get_sales_reporting_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}), change_threshold_percent: 25 };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load retention and opportunity controls.");
			} finally {
				this.metadataLoading = false;
			}
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
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer");
			else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer");
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		customerSearch(txt) { return this.searchOptions("customer", txt); },
		onCompanySelected(option) {
			this.filters.company = option?.value || "";
			this.filters.branch = "";
			this.clearCustomer();
		},
		onBranchSelected(option) {
			this.filters.branch = option?.value || "";
			this.clearCustomer();
		},
		clearBranch() { this.filters.branch = ""; this.clearCustomer(); },
		onCustomerSelected(option) {
			this.filters.customer = option?.value || "";
			this.customerLabel = option?.label || option?.value || "";
		},
		clearCustomer() { this.filters.customer = ""; this.customerLabel = ""; },
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(this.pageMethod, { filters: { ...this.filters } });
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.scope = result.scope || {};
				this.metadata = result.metadata || {};
				this.companyCurrency = result.company_currency || this.companyCurrency;
			} catch (error) {
				this.error = errorMessage(error, "Failed to compare customer behaviour.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			return callMethod(this.exportMethod, { filters: { ...this.filters } });
		},
		openReportCell({ column, row }) {
			if (column?.fieldname !== "customer" || !row?.customer) return;
			frappe.route_options = {
				customer: row.customer,
				customer_name: row.customer_name || row.customer,
				company: this.filters.company,
				branch: this.filters.branch,
				from_date: this.filters.from_date,
				to_date: this.filters.to_date,
			};
			frappe.set_route("customer-360");
		},
		formatCell(value, column) {
			if (value === null || value === undefined || value === "") return "—";
			const fieldtype = column?.fieldtype;
			if (fieldtype === "Currency") return format_currency(Number(value || 0), this.companyCurrency || undefined);
			if (fieldtype === "Percent") return `${Number(value || 0).toFixed(1)}%`;
			if (fieldtype === "Int") return String(Number(value || 0));
			return String(value);
		},
	},
};
</script>

<style scoped>
.customer-opportunity-fallback { display: grid; gap: 0.5rem; padding: 1.5rem; }
.customer-opportunity-filter-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 0.85rem; align-items: end; }
.edge-field { display: grid; gap: 0.35rem; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; }
.edge-input { width: 100%; min-height: 38px; border: 1px solid var(--border-color, #dfe3e8); border-radius: 8px; padding: 0.45rem 0.65rem; background: var(--control-bg, transparent); color: inherit; }
.filter-action { display: flex; align-items: end; }
.edge-primary-button { width: 100%; min-height: 38px; border: 0; border-radius: 8px; padding: 0.5rem 0.9rem; font-weight: 600; background: var(--primary, #171717); color: var(--primary-foreground, #fff); }
.edge-primary-button:disabled { opacity: 0.55; cursor: not-allowed; }
</style>
