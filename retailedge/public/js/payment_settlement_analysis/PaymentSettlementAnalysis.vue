<template>
	<div v-if="!edgeUIValid" class="payment-analysis-fallback">
		<strong>Payment & Settlement Analysis could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>

	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Payment & Settlement Analysis"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/payment-settlement-analysis"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Payment & Settlement Analysis"
			eyebrow="Money Intelligence"
			subtitle="Analyse posted receipts, supplier payments, internal transfers and unapplied customer advances from ERPNext Payment Entry truth."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:sort="reportSort"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No matching payments"
			emptyDescription="Adjust the date, Branch, payment type, party or payment method filters and try again."
			loadingMessage="Loading payment analysis…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@sort-change="handleSortChange"
		>
			<template #actions>
				<button v-if="paymentManagementAvailable" type="button" class="secondary-action" @click="openPaymentManagement">
					Payment Management
				</button>
				<EdgeExportMenu
					v-if="rows.length"
					:dataset="exportDataset"
					:loadDataset="loadExportDataset"
				/>
			</template>

			<template #filters>
				<div class="payment-analysis-filters">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						required
						placeholder="Search company"
						:searcher="companySearch"
						@select="onCompanySelected"
					/>
					<EdgeLinkField
						v-model="filters.branch"
						label="Branch"
						placeholder="Permitted branch scope"
						:searcher="branchSearch"
						@select="onBranchSelected"
						@clear="clearBranch"
					/>
					<EdgeDropdown v-model="analysisPreset" :options="analysisPresets" label="Analysis View" @change="onPresetChange" />
					<EdgeDropdown v-model="filters.group_by" :options="groupByOptions" label="Group By" @change="onGroupByChange" />
					<EdgeDropdown v-model="filters.payment_type" :options="paymentTypes" label="Payment Type" />
					<EdgeDropdown v-model="filters.party_type" :options="partyTypes" label="Party Type" @change="onPartyTypeChange" />
					<EdgeLinkField
						v-model="filters.party"
						:selectedLabel="partyLabel"
						label="Party"
						:placeholder="filters.party_type === 'All' ? 'Choose Customer or Supplier first' : 'All parties'"
						:searcher="partySearch"
						:disabled="filters.party_type === 'All'"
						@select="onPartySelected"
						@clear="clearParty"
					/>
					<EdgeLinkField
						v-model="filters.mode_of_payment"
						:selectedLabel="modeLabel"
						label="Mode of Payment"
						placeholder="All payment methods"
						:searcher="modeSearch"
						@select="onModeSelected"
						@clear="clearMode"
					/>
					<label class="edge-field">
						<span class="edge-field-label">From Date</span>
						<input v-model="filters.from_date" type="date" class="edge-input" />
					</label>
					<label class="edge-field">
						<span class="edge-field-label">To Date</span>
						<input v-model="filters.to_date" type="date" class="edge-input" />
					</label>
					<div class="filter-note">
						<span v-if="branchRequired">Choose one of your assigned Branches before loading this report.</span>
						<span>{{ dateRangeLimit }}-day maximum per request</span>
						<span>Submitted Payment Entries only</span>
					</div>
					<div class="filter-action">
						<button class="primary-action full" type="button" :disabled="loading || !filters.company || branchRequired" @click="applyFilters">
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span>{{ scopeLabel }}</span>
				<span>{{ companyCurrency || "Company currency" }}</span>
				<span>Grouped by {{ filters.group_by }}</span>
				<span>Payment Mode comes from Payment Entry, never from Sales Invoice inference</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgeReportShell",
	"EdgeLinkField",
	"EdgeExportMenu",
	"EdgeDropdown",
];

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "payment-settlement-analysis";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

export default {
	name: "PaymentSettlementAnalysis",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			metadataLoading: true,
			loading: false,
			error: "",
			rows: [],
			columns: [],
			summary: [],
			reportSort: null,
			pagination: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			companyCurrency: "",
			dateRangeLimit: 366,
			scopeRestricted: false,
			branchRequired: false,
			groupByOptions: [],
			paymentTypes: [],
			partyTypes: [],
			analysisPreset: "Payment Methods",
			partyLabel: "",
			modeLabel: "",
			canUseNativeDesk: false,
			filters: {
				company: "",
				branch: "",
				from_date: "",
				to_date: "",
				group_by: "Mode of Payment",
				payment_type: "All",
				party_type: "All",
				party: "",
				mode_of_payment: "",
				page_size: 50,
			},
			currentPage: 1,
			analysisPresets: [
				"Payment Methods",
				"Customer Receipts",
				"Supplier Payments",
				"Payments by Branch",
				"Settlement Accounts",
				"Daily Payments",
				"Monthly Payments",
				"Customer Advances",
				"Custom",
			],
		};
	},
	computed: {
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| null;
		},
		reportColumns() {
			return this.columns || [];
		},
		paymentManagementAvailable() {
			return this.menuItems
				.flatMap((group) => group.items || [])
				.some((item) => item.target_type === "Page" && item.target === "payment-management");
		},
		scopeLabel() {
			if (this.filters.branch) return "Branch: " + this.filters.branch;
			if (this.filters.company) return "Company: " + this.filters.company;
			return "Current permitted scope";
		},
		exportDataset() {
			return {
				title: "Payment & Settlement Analysis",
				filename: ("ProcessEdge Retail Payment Settlement Analysis " + (this.filters.company || "")).trim(),
				columns: this.exportColumns(this.columns),
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.exportSummary(this.summary),
				metadata: [
					{ label: "Source", value: "Submitted ERPNext Payment Entry" },
					{ label: "Scope", value: this.scopeLabel },
					{ label: "Grouping", value: this.filters.group_by },
				],
			};
		},
		exportFilters() {
			const labels = {
				company: "Company",
				branch: "Branch",
				from_date: "From Date",
				to_date: "To Date",
				group_by: "Group By",
				payment_type: "Payment Type",
				party_type: "Party Type",
				party: "Party",
				mode_of_payment: "Mode of Payment",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== "All" && entry.value !== null && entry.value !== undefined);
		},
	},
	created() {
		const components = runtimeComponents();
		this.edgeUIValid = REQUIRED_COMPONENTS.every((name) => Boolean(components[name]));
	},
	mounted() {
		this.fetchMetadata();
	},
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.payment_settlement_analysis.get_payment_settlement_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				const handoff = window.retailedgeConsumeBusinessHubRouteOptions?.(REPORT_KEY) || {};
				this.filters = { ...this.filters, ...handoff };
				this.tenantName = handoff.company || context.tenant_name || this.filters.company || "";
				this.branchName = handoff.branch || context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.groupByOptions = context.group_by_options || [];
				this.paymentTypes = context.payment_types || [];
				this.partyTypes = context.party_types || [];
				this.dateRangeLimit = Number(context.limits?.date_range_days || 366);
				this.scopeRestricted = Boolean(context.scope?.restricted);
				this.branchRequired = Boolean(this.scopeRestricted && !this.filters.branch);
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company && !this.branchRequired) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Payment & Settlement Analysis controls.");
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
			if (item.target_type === "Page") return "/app/" + item.target;
			if (item.target_type === "Report") return "/app/query-report/" + encodeURIComponent(item.target);
			if (item.target_type === "DocType") return "/app/" + String(item.target || "").toLowerCase().replace(/\s+/g, "-");
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (["Report", "DocType"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.payment_settlement_analysis.search_payment_settlement_options", {
				kind,
				txt,
				company: this.filters.company,
				branch: this.filters.branch,
				party_type: this.filters.party_type,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		partySearch(txt) {
			if (this.filters.party_type === "All") return Promise.resolve([]);
			return this.searchOptions("party", txt);
		},
		modeSearch(txt) { return this.searchOptions("mode_of_payment", txt); },
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.party = "";
			this.partyLabel = "";
			this.branchName = "";
			this.scopeRestricted = false;
			this.branchRequired = false;
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.branchName = option.label || option.value;
			this.branchRequired = false;
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
			this.branchRequired = this.scopeRestricted;
			this.currentPage = 1;
		},
		onPartyTypeChange() {
			this.filters.party = "";
			this.partyLabel = "";
			this.currentPage = 1;
		},
		onPartySelected(option) {
			this.filters.party = option.value;
			this.partyLabel = option.label || option.value;
			this.currentPage = 1;
		},
		clearParty() {
			this.filters.party = "";
			this.partyLabel = "";
			this.currentPage = 1;
		},
		onModeSelected(option) {
			this.filters.mode_of_payment = option.value;
			this.modeLabel = option.label || option.value;
			this.currentPage = 1;
		},
		clearMode() {
			this.filters.mode_of_payment = "";
			this.modeLabel = "";
			this.currentPage = 1;
		},
		onPresetChange() {
			const presets = {
				"Payment Methods": { group_by: "Mode of Payment", payment_type: "All", party_type: "All" },
				"Customer Receipts": { group_by: "Party", payment_type: "Receive", party_type: "Customer" },
				"Supplier Payments": { group_by: "Party", payment_type: "Pay", party_type: "Supplier" },
				"Payments by Branch": { group_by: "Branch", payment_type: "All", party_type: "All" },
				"Settlement Accounts": { group_by: "Settlement Account", payment_type: "All", party_type: "All" },
				"Daily Payments": { group_by: "Day", payment_type: "All", party_type: "All" },
				"Monthly Payments": { group_by: "Month", payment_type: "All", party_type: "All" },
				"Customer Advances": { group_by: "Party", payment_type: "Receive", party_type: "Customer" },
			};
			const preset = presets[this.analysisPreset];
			if (preset) {
				this.filters.group_by = preset.group_by;
				this.filters.payment_type = preset.payment_type;
				this.filters.party_type = preset.party_type;
				this.filters.party = "";
				this.partyLabel = "";
			}
			this.currentPage = 1;
		},
		onGroupByChange() {
			const presets = {
				"Mode of Payment": "Payment Methods",
				Branch: "Payments by Branch",
				"Settlement Account": "Settlement Accounts",
				Day: "Daily Payments",
				Month: "Monthly Payments",
			};
			this.analysisPreset = presets[this.filters.group_by] || "Custom";
			this.currentPage = 1;
		},
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		providerFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
		},
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error = "The Payment & Settlement Analysis reporting service is unavailable.";
				return;
			}
			this.loading = true;
			this.error = "";
			try {
				const pageSize = Number(this.filters.page_size || 50);
				const start = Math.max(0, (this.currentPage - 1) * pageSize);
				const result = await this.reportProvider.load({
					filters: this.providerFilters(),
					start,
					page_length: pageSize,
					sort: this.reportSort,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.reportSort = result.sort || null;
				this.companyCurrency = result.company_currency || this.companyCurrency;
				const totalRows = Number(result.total || this.rows.length);
				const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
				this.pagination = {
					page: this.currentPage,
					page_size: pageSize,
					total_rows: totalRows,
					total_pages: totalPages,
					has_previous: this.currentPage > 1,
					has_next: this.currentPage < totalPages,
				};
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = errorMessage(error, "Payment & Settlement Analysis failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			const result = await this.reportProvider.export({ filters: this.providerFilters() });
			return {
				columns: this.exportColumns(result.columns || this.columns),
				rows: result.rows || [],
				summary: this.exportSummary(result.summary || this.summary),
				metadata: this.exportDataset.metadata,
			};
		},
		exportColumns(columns) {
			return (columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				options: column.options || column.doctype || undefined,
			}));
		},
		exportSummary(summary) {
			return (summary || []).map((card) => ({
				...card,
				datatype: card.datatype || card.type || "Data",
			}));
		},
		handleSortChange(sort) {
			this.reportSort = sort || null;
			this.currentPage = 1;
			return this.fetchData();
		},
		goToPage(page) {
			const next = Number(page || 1);
			if (next < 1) return;
			this.currentPage = next;
			this.fetchData();
		},
		setPageSize(pageSize) {
			this.filters.page_size = Number(pageSize || 50);
			this.currentPage = 1;
			this.fetchData();
		},
		rowKey(row, index) {
			return row.group_key || "payment-settlement:" + index;
		},
		openPaymentManagement() {
			frappe.set_route("payment-management");
		},
		formatCell(value, column) {
			return this.formatValue(value, column?.type || column?.fieldtype);
		},
		formatValue(value, fieldtype) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try {
					return window.retailedge.formatPlainValue(number, { fieldtype: "Currency" });
				} catch (_error) {
					return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
				}
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			return String(value);
		},
	},
};
</script>

<style scoped>
.payment-analysis-fallback {
	margin: 20px;
	padding: 16px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.payment-analysis-filters {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}
.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: .78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
.edge-input,
.primary-action,
.secondary-action {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d0d5dd);
	border-radius: 8px;
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 0 10px;
}
.primary-action {
	background: var(--edge-primary, #2563eb);
	border-color: var(--edge-primary, #2563eb);
	color: #fff;
	font-weight: 600;
}
.secondary-action { cursor: pointer; font-weight: 600; }
.full { width: 100%; }
.filter-note {
	display: flex;
	flex-direction: column;
	gap: 4px;
	font-size: .75rem;
	color: var(--edge-text-muted, #667085);
}
:global(:root[data-edge-appearance="dark"]) .payment-analysis-fallback,
:global(:root[data-edge-appearance="dark"]) .edge-input,
:global(:root[data-edge-appearance="dark"]) .secondary-action {
	background: var(--edge-surface);
	border-color: var(--edge-border);
	color: var(--edge-text);
}
@media (max-width: 1100px) {
	.payment-analysis-filters { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
	.payment-analysis-filters { grid-template-columns: 1fr; }
}
</style>
