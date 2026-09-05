<template>
	<div v-if="!edgeUIValid" class="shift-fallback">
		<strong>Cash Shift Verification could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Cash Shift Verification"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/cash-shift-verification"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Cash Shift Verification"
			eyebrow="Review & Approvals"
			subtitle="Compare expected and actual shift cash, surface shortages or overages, and identify unsynced cash invoices using the existing Daily Sales Audit engine."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No matching cash shifts"
			emptyDescription="Adjust the date or operational filters and try again."
			loadingMessage="Loading cash shift verification…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="handleCellClick"
		>
			<template #filters>
				<div class="shift-filter-grid">
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
						placeholder="All permitted branches"
						:searcher="branchSearch"
						@select="onBranchSelected"
						@clear="clearBranch"
					/>
					<EdgeLinkField
						v-model="filters.pos_profile"
						label="POS Profile"
						placeholder="All POS profiles"
						:searcher="posProfileSearch"
					/>
					<EdgeLinkField
						v-model="filters.cashier"
						:selectedLabel="cashierLabel"
						label="Cashier"
						placeholder="All cashiers"
						:searcher="cashierSearch"
						@select="onCashierSelected"
						@clear="clearCashier"
					/>
					<label class="edge-field"
						><span class="edge-field-label">From Date</span
						><input v-model="filters.from_date" type="date" class="edge-input"
					/></label>
					<label class="edge-field"
						><span class="edge-field-label">To Date</span
						><input v-model="filters.to_date" type="date" class="edge-input"
					/></label>
					<label class="edge-field"
						><span class="edge-field-label">Cash Status</span
						><select v-model="filters.cash_status" class="edge-input">
							<option value="">All</option>
							<option v-for="status in cashStatuses" :key="status" :value="status">
								{{ status }}
							</option>
						</select></label
					>
					<div class="filter-action">
						<button
							class="edge-primary-button"
							type="button"
							:disabled="loading || !filters.company"
							@click="applyFilters"
						>
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
				<details class="advanced-filters">
					<summary>More filters</summary>
					<div class="shift-filter-grid advanced-grid">
						<label class="edge-field"
							><span class="edge-field-label">Review Status</span
							><select v-model="filters.review_status" class="edge-input">
								<option value="">All</option>
								<option
									v-for="status in reviewStatuses"
									:key="status"
									:value="status"
								>
									{{ status }}
								</option>
							</select></label
						>
						<label class="edge-check"
							><input
								v-model="filters.only_unsynced"
								type="checkbox"
								true-value="1"
								false-value="0"
							/><span>Only shifts with unsynced cash invoices</span></label
						>
					</div>
				</details>
			</template>
			<template #resultMeta>
				<span
					>{{ scan.rows || 0 }} matching shift{{
						Number(scan.rows || 0) === 1 ? "" : "s"
					}}</span
				>
				<span
					>Bounded verification dataset · {{ providerDatasetLimit.toLocaleString() }} row
					cap</span
				>
				<span>Legacy Cash Shift Verification retained for detailed comparison</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "cash-shift-verification";
function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) =>
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		})
	);
}
function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

export default {
	name: "CashShiftVerificationReport",
	components: Object.fromEntries(
		REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])
	),
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
			scan: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			cashierLabel: "",
			currentPage: 1,
			filters: {
				company: "",
				branch: "",
				pos_profile: "",
				cashier: "",
				cash_status: "",
				review_status: "",
				only_unsynced: 0,
				from_date: "",
				to_date: "",
				page_size: 50,
			},
			cashStatuses: [
				"Balanced",
				"Shortage",
				"Overage",
				"Needs Review",
				"Missing Closing Shift",
				"Missing Opening Shift",
			],
			reviewStatuses: [
				"Draft",
				"Ready for Review",
				"In Review",
				"Balanced",
				"Variance Found",
				"Clarification Required",
				"Approved",
				"Rejected",
				"Cancelled",
				"Reopened",
			],
		};
	},
	computed: {
		reportProvider() {
			return (
				window.EdgeSuiteReports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) ||
				window.EdgeSuiteUI?.reports?.getProvider?.(REPORT_PRODUCT, REPORT_KEY) ||
				null
			);
		},
		providerDatasetLimit() {
			return Number(this.reportProvider?.max_dataset_rows || 1000);
		},
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || "Data",
				clickable: [
					"daily_sales_audit",
					"cashier",
					"pos_profile",
					"opening_shift",
					"closing_shift",
				].includes(column.fieldname),
			}));
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
				const navigationPromise =
					typeof window.retailedgeGetBusinessHubContext === "function"
						? window.retailedgeGetBusinessHubContext()
						: callMethod(
								"retailedge.edgesuite_ui.get_retailedge_business_hub_context"
						  );
				const [context, navigation] = await Promise.all([
					callMethod(
						"retailedge.cash_shift_verification.get_cash_shift_verification_context"
					),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(
					error,
					"Failed to load Cash Shift Verification controls."
				);
			} finally {
				this.metadataLoading = false;
			}
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({
					...item,
					route: this.routeForItem(item),
				})),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report")
				return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType")
				return `/app/${String(item.target || "")
					.toLowerCase()
					.replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems
				.flatMap((group) => group.items || [])
				.find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target)
				window.location.assign(item.target);
		},
		async searchOptions(kind, txt) {
			const result = await callMethod(
				"retailedge.cash_shift_verification.search_cash_shift_verification_options",
				{ kind, txt, company: this.filters.company, branch: this.filters.branch }
			);
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) {
			return this.searchOptions("company", txt);
		},
		branchSearch(txt) {
			return this.searchOptions("branch", txt);
		},
		cashierSearch(txt) {
			return this.searchOptions("cashier", txt);
		},
		posProfileSearch(txt) {
			return this.searchOptions("pos_profile", txt);
		},
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.branch = "";
			this.filters.pos_profile = "";
			this.filters.cashier = "";
			this.branchName = "";
			this.cashierLabel = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option.value;
			this.filters.pos_profile = "";
			this.filters.cashier = "";
			this.branchName = option.label || option.value;
			this.cashierLabel = "";
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.filters.pos_profile = "";
			this.filters.cashier = "";
			this.branchName = "";
			this.cashierLabel = "";
			this.currentPage = 1;
		},
		onCashierSelected(option) {
			this.filters.cashier = option.value;
			this.cashierLabel = option.label || option.value;
			this.currentPage = 1;
		},
		clearCashier() {
			this.filters.cashier = "";
			this.cashierLabel = "";
			this.currentPage = 1;
		},
		providerFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
		},
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		async fetchData() {
			if (!this.filters.company) return;
			if (!this.reportProvider?.load) {
				this.error =
					"The shared EdgeSuite Cash Shift Verification provider is unavailable.";
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
				this.scan = result.metadata?.scan || {};
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
				this.error = errorMessage(error, "Cash Shift Verification failed to load.");
			} finally {
				this.loading = false;
			}
		},
		goToPage(page) {
			const next = Math.max(1, Number(page || 1));
			if (next === this.currentPage) return;
			this.currentPage = next;
			this.fetchData();
		},
		setPageSize(pageSize) {
			this.filters.page_size = Number(pageSize || 50);
			this.currentPage = 1;
			this.fetchData();
		},
		rowKey(row, index) {
			return (
				row.daily_sales_audit ||
				`${row.shift_date || "shift"}:${row.cashier || ""}:${index}`
			);
		},
		handleCellClick(payload) {
			const column = payload?.column;
			const row = payload?.row;
			if (!column || !row) return;
			const value = row[column.fieldname];
			if (!value) return;
			if (column.fieldname === "daily_sales_audit")
				frappe.set_route("Form", "RetailEdge Daily Sales Audit", value);
			else if (column.fieldname === "cashier") frappe.set_route("Form", "User", value);
			else if (column.fieldname === "pos_profile")
				frappe.set_route("Form", "POS Profile", value);
			else if (column.fieldname === "opening_shift")
				frappe.set_route("Form", "POS Opening Shift", value);
			else if (column.fieldname === "closing_shift")
				frappe.set_route("Form", "POS Closing Shift", value);
		},
		formatCell(value, column) {
			if (value === null || value === undefined || value === "") return "—";
			if (column.fieldtype === "Currency") {
				try {
					return frappe.format(Number(value), { fieldtype: "Currency" });
				} catch (_error) {
					return Number(value).toLocaleString(undefined, {
						minimumFractionDigits: 2,
						maximumFractionDigits: 2,
					});
				}
			}
			if (column.fieldtype === "Int") return Number(value).toLocaleString();
			if (column.fieldtype === "Date") {
				try {
					return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0];
				} catch (_error) {
					return String(value);
				}
			}
			return String(value);
		},
	},
};
</script>

<style scoped>
.shift-fallback {
	margin: 20px;
	padding: 24px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.shift-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}
.advanced-filters {
	margin-top: var(--edge-space-md, 16px);
}
.advanced-filters summary {
	cursor: pointer;
	font-weight: 600;
	color: var(--edge-text, #101828);
}
.advanced-grid {
	margin-top: var(--edge-space-sm, 10px);
}
.edge-field {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}
.edge-field-label {
	font-size: 0.78rem;
	font-weight: 600;
	color: var(--edge-text-muted, #667085);
}
.edge-input,
.edge-primary-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 0 10px;
}
.edge-check {
	min-height: 38px;
	display: flex;
	align-items: center;
	gap: 8px;
	color: var(--edge-text, #101828);
}
.edge-primary-button {
	background: var(--edge-primary, #0f766e);
	color: #fff;
	border-color: var(--edge-primary, #0f766e);
	font-weight: 600;
	cursor: pointer;
}
.edge-primary-button:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}
@media (max-width: 1180px) {
	.shift-filter-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
}
@media (max-width: 860px) {
	.shift-filter-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 560px) {
	.shift-filter-grid {
		grid-template-columns: 1fr;
	}
}
</style>
