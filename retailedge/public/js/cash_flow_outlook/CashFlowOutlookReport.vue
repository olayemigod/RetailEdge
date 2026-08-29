<template>
	<div v-if="!edgeUIValid" class="outlook-fallback">
		<strong>Cash Flow Outlook could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Cash Flow Outlook"
		:tenantName="tenantName || filters.company"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/cash-flow-outlook"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Cash Flow Outlook"
			eyebrow="Liquidity Planning"
			subtitle="A 13-week schedule of current ERPNext receivables and payables using native payment terms and due dates. It is not a projected bank balance."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			emptyTitle="No scheduled receivables or payables"
			emptyDescription="No current invoice payment schedules fall within this scope."
			loadingMessage="Building cash flow outlook…"
			@retry="fetchData"
		>
			<template #filters>
				<div class="outlook-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<div class="outlook-filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Loading…" : "Apply / Refresh" }}</button></div>
				</div>
			</template>
			<template #resultMeta>
				<span>As of {{ asOfDate || "today" }} · {{ horizonWeeks }}-week horizon</span>
				<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				<span>ERPNext current outstanding allocated by native payment terms and due dates</span>
				<span>Journal Entries, future orders and manual scenarios are excluded from this first outlook</span>
				<span>Net scheduled movement is not a bank or cash balance</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "cash-flow-outlook";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "CashFlowOutlookReport",
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
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			asOfDate: "",
			horizonWeeks: 13,
			filters: { company: "", branch: "" },
		};
	},
	computed: {
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| null;
		},
		reportColumns() { return (this.columns || []).filter((column) => !column.hidden); },
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
					callMethod("retailedge.cash_flow_outlook.get_cash_flow_outlook_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.asOfDate = context.as_of_date || "";
				this.horizonWeeks = Number(context.outlook_weeks || 13);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Cash Flow Outlook controls.");
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
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.cash_flow_outlook.search_cash_flow_outlook_options", {
				kind,
				txt,
				company: this.filters.company,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.branchName = "";
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.branchName = option.label || option.value;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
		},
		applyFilters() { return this.fetchData(); },
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error = "The shared EdgeSuite Cash Flow Outlook provider is unavailable.";
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const result = await this.reportProvider.load({ filters: { ...this.filters }, start: 0, page_length: 25 });
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.companyCurrency = result.metadata?.company_currency || this.companyCurrency;
				this.asOfDate = result.metadata?.as_of_date || this.asOfDate;
				this.horizonWeeks = Number(result.metadata?.horizon_weeks || this.horizonWeeks || 13);
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = errorMessage(error, "Cash Flow Outlook failed to load.");
			} finally {
				this.loading = false;
			}
		},
		rowKey(row, index) { return row.bucket || `cash-flow-outlook:${index}`; },
		formatCell(value, column) { return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency); },
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(value); } catch (_error) { return value; }
			}
			if (fieldtype === "Currency") {
				try { return frappe.format(value, { fieldtype: "Currency", options: currency || this.companyCurrency }); }
				catch (_error) { return Number(value || 0).toLocaleString(); }
			}
			try { return frappe.format(value, { fieldtype: fieldtype || "Data" }); }
			catch (_error) { return String(value); }
		},
	},
};
</script>

<style scoped>
.outlook-fallback { display: grid; gap: .35rem; padding: 1.5rem; }
.outlook-filter-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)) auto; gap: 12px; align-items: end; }
.outlook-filter-action { display: flex; justify-content: flex-end; }
@media (max-width: 760px) { .outlook-filter-grid { grid-template-columns: 1fr; } .outlook-filter-action { justify-content: stretch; } .outlook-filter-action button { width: 100%; } }
</style>
