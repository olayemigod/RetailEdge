<template>
	<div v-if="!edgeUIValid" class="quota-fallback">
		<strong>Quota Operations could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Quota Operations"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/quota-operations"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Quota Operations"
			eyebrow="Operations Review"
			subtitle="Review sales quota finalization, retry safe pending operations, and surface transactions that require platform reconciliation without changing ERPNext accounting truth."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No matching quota operations"
			emptyDescription="No quota exceptions match the current Company, Branch and status filters."
			loadingMessage="Loading quota operations…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="handleCellClick"
		>
			<template #filters>
				<div class="quota-filter-grid">
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
					<EdgeDropdown
						v-model="filters.status"
						:options="statusOptions"
						label="Status"
					/>
					<EdgeDropdown
						v-model="filters.source_doctype"
						:options="sourceOptions"
						label="Source Type"
						placeholder="All"
					/>
					<label class="quota-search-field">
						<span>Search</span>
						<input
							v-model.trim="filters.search"
							type="search"
							placeholder="Invoice, reason or message"
							@keyup.enter="applyFilters"
						/>
					</label>
					<div class="quota-filter-action">
						<button
							class="quota-primary-button"
							type="button"
							:disabled="loading || !filters.company"
							@click="applyFilters"
						>
							{{ loading ? "Loading…" : "Apply Filters" }}
						</button>
					</div>
				</div>
				<div class="quota-guidance">
					<strong>Safe actions only.</strong>
					<span>
						Pending Finalize may be retried. Needs Review is intentionally read-only until
						a governed CoreEdge reconciliation action exists.
					</span>
				</div>
			</template>
			<template #resultMeta>
				<span>{{ pagination.total_rows || 0 }} matching operation{{ Number(pagination.total_rows || 0) === 1 ? "" : "s" }}</span>
				<span>Bounded permission-aware dataset · {{ datasetLimit.toLocaleString() }} row cap</span>
				<span>Submitted accounting documents are never changed from this page</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgeReportShell",
	"EdgeLinkField",
	"EdgeDropdown",
];

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
	name: "QuotaOperationsCenter",
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
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			canUseNativeDesk: false,
			canRetry: false,
			datasetLimit: 2000,
			currentPage: 1,
			filters: {
				company: "",
				branch: "",
				status: "Open",
				source_doctype: "",
				search: "",
				page_size: 50,
			},
			statusOptions: [
				"Open",
				"Needs Review",
				"Pending Finalize",
				"Finalized",
				"All",
			],
			sourceOptions: ["Sales Invoice", "POS Invoice"],
		};
	},
	computed: {
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				clickable:
					column.fieldname === "action" ||
					(column.fieldname === "source" && this.canUseNativeDesk),
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
						"retailedge.coreedge_quota_operations_center.get_quota_operations_center_context"
					),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.canRetry = Boolean(context.can_retry);
				this.datasetLimit = Number(context.limits?.rows || 2000);
				this.canUseNativeDesk = Boolean(navigation?.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation?.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Quota Operations controls.");
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
			if (item.target_type === "Report") {
				return `/app/query-report/${encodeURIComponent(item.target)}`;
			}
			if (item.target_type === "DocType") {
				return `/app/${String(item.target || "")
					.toLowerCase()
					.replace(/\s+/g, "-")}`;
			}
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems
				.flatMap((group) => group.items || [])
				.find((candidate) => candidate.route === route);
			if (!item) return;
			if (
				(item.target_type === "DocType" || item.target_type === "Report") &&
				!this.canUseNativeDesk
			) {
				return;
			}
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") {
				frappe.set_route("query-report", item.target);
			} else if (item.target_type === "DocType") {
				frappe.set_route("List", item.target);
			} else if (item.target_type === "URL" && item.target) {
				window.location.assign(item.target);
			}
		},
		async searchOptions(kind, txt) {
			const result = await callMethod(
				"retailedge.coreedge_quota_operations_center.search_quota_operations_options",
				{ kind, txt, company: this.filters.company }
			);
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) {
			return this.searchOptions("company", txt);
		},
		branchSearch(txt) {
			return this.searchOptions("branch", txt);
		},
		onCompanySelected(option) {
			this.filters.company = option?.value || "";
			this.filters.branch = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		onBranchSelected(option) {
			this.filters.branch = option?.value || "";
			this.branchName = option?.label || option?.value || "";
			this.currentPage = 1;
		},
		clearBranch() {
			this.filters.branch = "";
			this.branchName = "";
			this.currentPage = 1;
		},
		applyFilters() {
			this.currentPage = 1;
			return this.fetchData();
		},
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(
					"retailedge.coreedge_quota_operations_center.get_quota_operations",
					{
						filters: this.providerFilters(),
						page: this.currentPage,
						page_size: Number(this.filters.page_size || 50),
					}
				);
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.pagination = result.pagination || {};
				this.currentPage = Number(this.pagination.page || this.currentPage || 1);
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.pagination = {};
				this.error = errorMessage(error, "Quota Operations failed to load.");
			} finally {
				this.loading = false;
			}
		},
		providerFilters() {
			const { page_size: _pageSize, ...filters } = this.filters;
			return filters;
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
			return row.name || `quota-operation-${index}`;
		},
		handleCellClick(payload) {
			const column = payload?.column;
			const row = payload?.row;
			if (!column || !row) return;
			if (
				column.fieldname === "source" &&
				this.canUseNativeDesk &&
				row.source_openable &&
				row.source_doctype &&
				row.source_name
			) {
				frappe.set_route("Form", row.source_doctype, row.source_name);
				return;
			}
			if (column.fieldname === "action" && row.can_retry) {
				this.confirmRetry(row);
			}
		},
		confirmRetry(row) {
			frappe.confirm(
				__(
					"Queue another CoreEdge finalization attempt for {0}?",
					[row.source || row.name]
				),
				() => this.retryOperation(row)
			);
		},
		async retryOperation(row) {
			if (!this.canRetry || !row?.can_retry || !row?.name) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod(
					"retailedge.coreedge_quota_operations_center.retry_quota_operation",
					{ operation_name: row.name }
				);
				frappe.show_alert({
					message: result.message || __("Quota finalization retry queued."),
					indicator: "green",
				});
				await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Quota finalization retry could not be queued.");
			} finally {
				this.loading = false;
			}
		},
		formatCell(value, column) {
			if (value === null || value === undefined || value === "") return "—";
			if (column.fieldtype === "Int") return Number(value).toLocaleString();
			if (column.fieldtype === "Datetime") {
				try {
					return frappe.datetime.str_to_user(value);
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
.quota-fallback,
.quota-guidance {
	margin: 16px 0;
	padding: 16px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-lg, 10px);
	background: var(--edge-surface, #fff);
}
.quota-fallback,
.quota-guidance {
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.quota-filter-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: var(--edge-space-md, 16px);
	align-items: end;
	width: 100%;
}
.quota-search-field {
	display: flex;
	flex-direction: column;
	gap: 6px;
	min-width: 0;
}
.quota-search-field span {
	font-size: 0.78rem;
	font-weight: 600;
	color: var(--edge-text-muted, #667085);
}
.quota-search-field input,
.quota-primary-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d9d9d9);
	border-radius: var(--edge-radius-md, 8px);
	padding: 0 10px;
}
.quota-search-field input {
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
}
.quota-primary-button {
	width: 100%;
	background: var(--edge-primary, #0f766e);
	border-color: var(--edge-primary, #0f766e);
	color: #fff;
	font-weight: 600;
	cursor: pointer;
}
.quota-primary-button:disabled {
	opacity: 0.55;
	cursor: not-allowed;
}
.quota-guidance {
	font-size: 0.86rem;
	color: var(--edge-text-muted, #667085);
}
.quota-guidance strong {
	color: var(--edge-text, #101828);
}
@media (max-width: 980px) {
	.quota-filter-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 620px) {
	.quota-filter-grid {
		grid-template-columns: 1fr;
	}
}
</style>
