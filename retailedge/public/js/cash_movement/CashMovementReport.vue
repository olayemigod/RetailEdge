<template>
	<div v-if="!edgeUIValid" class="cash-movement-fallback">
		<strong>Cash Movement could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Cash Movement"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/cash-movement"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Cash Movement"
			eyebrow="Money Control"
			subtitle="See posted money moving into and out of Cash and Bank accounts without creating a second ledger."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No cash movements found"
			emptyDescription="Adjust the date, Branch, Cash/Bank Account or Movement Type filters and try again."
			loadingMessage="Loading cash movements…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="openReportCell"
		>
			<template #actions>
				<button type="button" class="secondary-action" @click="openPayments">Payments</button>
				<EdgeExportMenu
					v-if="rows.length"
					:dataset="exportDataset"
					:loadDataset="loadExportDataset"
				/>
			</template>

			<template #filters>
				<div class="cash-filter-grid">
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
					<EdgeLinkField
						v-model="filters.account"
						:selectedLabel="accountLabel"
						label="Cash / Bank Account"
						placeholder="All permitted cash and bank accounts"
						:searcher="accountSearch"
						@select="onAccountSelected"
						@clear="clearAccount"
					/>
					<label class="edge-field">
						<span class="edge-field-label">Movement Type</span>
						<select v-model="filters.movement_type" class="edge-input">
							<option value="">All movements</option>
							<option v-for="movement in movementTypes" :key="movement" :value="movement">{{ movement }}</option>
						</select>
					</label>
					<label class="edge-field">
						<span class="edge-field-label">From Date</span>
						<input v-model="filters.from_date" type="date" class="edge-input" />
					</label>
					<label class="edge-field">
						<span class="edge-field-label">To Date</span>
						<input v-model="filters.to_date" type="date" class="edge-input" />
					</label>
					<div class="filter-note">
						<span>{{ dateRangeLimit }}-day maximum per request</span>
						<span>Posted accounting entries only</span>
					</div>
					<div class="filter-action">
						<button class="primary-action full" type="button" :disabled="loading || !filters.company" @click="applyFilters">
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span>{{ scope.branch_scope || scopeLabel }}</span>
				<span>{{ scope.currency || "Company currency" }}</span>
				<span>Source: {{ dataPolicy.source || "Posted ERPNext General Ledger Cash/Bank entries" }}</span>
				<span v-if="scope.includes_unattributed">Includes unattributed company-level adjustments</span>
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
];

const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "cash-movement";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

export default {
	name: "CashMovementReport",
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
			pagination: {},
			scope: {},
			dataPolicy: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			movementTypes: [],
			dateRangeLimit: 366,
			accountLabel: "",
			filters: {
				company: "",
				branch: "",
				from_date: "",
				to_date: "",
				account: "",
				movement_type: "",
				page_size: 50,
			},
			currentPage: 1,
		};
	},
	computed: {
		reportProvider() {
			return window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY)
				|| null;
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: column.fieldname === "voucher_no",
			}));
		},
		scopeLabel() {
			if (this.filters.branch) return `Branch: ${this.filters.branch}`;
			if (this.filters.company) return `Company: ${this.filters.company}`;
			return "Current permitted scope";
		},
		exportDataset() {
			return {
				title: "Cash Movement",
				filename: `RetailEdge Cash Movement ${this.filters.company || ""}`.trim(),
				columns: this.exportColumns(this.columns),
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.exportSummary(this.summary),
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			const labels = {
				company: "Company",
				branch: "Branch",
				from_date: "From Date",
				to_date: "To Date",
				account: "Cash / Bank Account",
				movement_type: "Movement Type",
			};
			return Object.entries(labels)
				.map(([key, label]) => ({ label, value: this.filters[key] }))
				.filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() {
			return [
				{ label: "Accounting Source", value: "Posted ERPNext General Ledger Cash/Bank entries" },
				{ label: "Scope", value: this.scope.branch_scope || this.scopeLabel },
				{ label: "Currency", value: this.scope.currency || "Company currency" },
			];
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
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
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.cash_movement.get_cash_movement_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.movementTypes = context.movement_types || [];
				this.dateRangeLimit = Number(context.limits?.date_range_days || 366);
				this.dataPolicy = context.data_policy || {};
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Cash Movement controls.");
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
			const items = this.menuItems.flatMap((group) => group.items || []);
			const item = items.find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod("retailedge.cash_movement.search_cash_movement_options", {
				kind,
				txt,
				company: this.filters.company,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) { return this.searchOptions("company", txt); },
		branchSearch(txt) { return this.searchOptions("branch", txt); },
		accountSearch(txt) { return this.searchOptions("account", txt); },
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.account = "";
			this.branchName = "";
			this.accountLabel = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.branchName = option.label || option.value;
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onAccountSelected(option) {
			this.filters.account = option.value;
			this.accountLabel = option.label || option.value;
			this.currentPage = 1;
		},
		clearAccount() {
			this.filters.account = "";
			this.accountLabel = "";
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
				this.error = "The shared EdgeSuite Cash Movement provider is unavailable.";
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
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.scope = result.metadata?.scope || {};
				this.dataPolicy = { ...this.dataPolicy, ...(result.metadata?.data_policy || {}) };
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
				this.error = errorMessage(error, "Cash Movement failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			const result = this.reportProvider?.export
				? await this.reportProvider.export({ filters: this.providerFilters() })
				: await callMethod("retailedge.cash_movement.get_cash_movement_export", {
					filters: this.providerFilters(),
				});
			return {
				columns: this.exportColumns(result.columns || this.columns),
				rows: result.rows || [],
				summary: this.exportSummary(result.summary || this.summary),
				metadata: this.exportMetadata,
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
			return `${row?.voucher_type || ""}-${row?.voucher_no || ""}-${row?.account || ""}-${index}`;
		},
		openReportCell(payload) {
			if (payload?.column?.fieldname === "voucher_no") this.openSource(payload.row);
		},
		openSource(row) {
			if (row?.voucher_type && row?.voucher_no) frappe.set_route("Form", row.voucher_type, row.voucher_no);
		},
		openPayments() {
			frappe.set_route("List", "Payment Entry");
		},
		formatCell(value, column, row) {
			const fieldname = column?.fieldname || column?.key;
			if (fieldname === "branch") return row?.branch || "Unattributed";
			return this.formatValue(value, column?.type || column?.fieldtype);
		},
		formatValue(value, fieldtype) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				try { return frappe.format(number, { fieldtype: "Currency" }); }
				catch (_error) { return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }); }
			}
			if (fieldtype === "Int") return Number(value).toLocaleString();
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(String(value)); }
				catch (_error) { return String(value); }
			}
			return String(value);
		},
	},
};
</script>

<style scoped>
.cash-movement-fallback {
	margin: 20px;
	padding: 16px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 6px;
}

.cash-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}

.edge-field { display: flex; flex-direction: column; gap: 6px; min-width: 0; }
.edge-field-label { font-size: 0.78rem; font-weight: 600; color: var(--edge-text-muted, #667085); }
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
.primary-action { background: var(--edge-primary, #2563eb); border-color: var(--edge-primary, #2563eb); color: #fff; font-weight: 600; }
.secondary-action { cursor: pointer; font-weight: 600; }
.full { width: 100%; }
.filter-note { display: flex; flex-direction: column; gap: 4px; font-size: 0.75rem; color: var(--edge-text-muted, #667085); }

@media (max-width: 1100px) { .cash-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .cash-filter-grid { grid-template-columns: 1fr; } }
</style>
