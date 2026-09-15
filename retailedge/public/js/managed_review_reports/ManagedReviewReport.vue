<template>
	<div v-if="!edgeUIValid" class="managed-report-fallback">
		<strong>{{ title || "Review workspace" }} could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		:title="title || 'Review'"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		:activeRoute="'/app/' + surfaceKey"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			:title="title"
			:eyebrow="eyebrow"
			:subtitle="subtitle"
			:columns="reportColumns"
			:rows="visibleRows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			:emptyTitle="'No ' + title.toLowerCase() + ' found'"
			emptyDescription="Adjust the filters and refresh the review."
			:loadingMessage="'Loading ' + title + '…'"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@sort-change="handleSortChange"
		>
			<template #actions>
				<button v-if="action.route" type="button" class="edge-button edge-button--secondary" @click="openAction">
					{{ action.label }}
				</button>
				<button type="button" class="edge-button edge-button--primary" :disabled="loading" @click="applyFilters">
					{{ loading ? "Refreshing…" : "Refresh" }}
				</button>
			</template>

			<template #filters>
				<div class="managed-filter-grid">
					<template v-for="field in primaryFilterFields" :key="field.fieldname">
						<EdgeLinkField
							v-if="field.fieldtype === 'Link'"
							:modelValue="filters[field.fieldname] || ''"
							:label="field.label"
							:placeholder="'Search ' + field.label.toLowerCase()"
							:searcher="linkSearcher(field)"
							@select="setFilter(field, $event.value || '')"
							@clear="setFilter(field, '')"
						/>
						<EdgeDropdown
							v-else-if="field.fieldtype === 'Select'"
							:modelValue="filters[field.fieldname]"
							:label="field.label"
							:options="field.options || []"
							@update:modelValue="setFilter(field, $event)"
						/>
						<label v-else-if="field.fieldtype === 'Check'" class="managed-check-field">
							<input
								type="checkbox"
								:checked="Boolean(Number(filters[field.fieldname] || 0))"
								@change="setFilter(field, $event.target.checked ? 1 : 0)"
							/>
							<span>{{ field.label }}</span>
						</label>
						<label v-else class="managed-input-field">
							<span>{{ field.label }}</span>
							<input
								class="edge-input"
								:type="inputType(field)"
								:value="filters[field.fieldname] ?? ''"
								:required="Boolean(field.required)"
								@input="setFilter(field, inputValue(field, $event.target.value))"
							/>
						</label>
					</template>
				</div>
				<details v-if="advancedFilterFields.length" class="managed-advanced-filters">
					<summary>More filters</summary>
				<div class="managed-filter-grid managed-filter-grid--advanced">
					<template v-for="field in advancedFilterFields" :key="field.fieldname">
						<EdgeLinkField
							v-if="field.fieldtype === 'Link'"
							:modelValue="filters[field.fieldname] || ''"
							:label="field.label"
							:placeholder="'Search ' + field.label.toLowerCase()"
							:searcher="linkSearcher(field)"
							@select="setFilter(field, $event.value || '')"
							@clear="setFilter(field, '')"
						/>
						<EdgeDropdown
							v-else-if="field.fieldtype === 'Select'"
							:modelValue="filters[field.fieldname]"
							:label="field.label"
							:options="field.options || []"
							@update:modelValue="setFilter(field, $event)"
						/>
						<label v-else-if="field.fieldtype === 'Check'" class="managed-check-field">
							<input
								type="checkbox"
								:checked="Boolean(Number(filters[field.fieldname] || 0))"
								@change="setFilter(field, $event.target.checked ? 1 : 0)"
							/>
							<span>{{ field.label }}</span>
						</label>
						<label v-else class="managed-input-field">
							<span>{{ field.label }}</span>
							<input
								class="edge-input"
								:type="inputType(field)"
								:value="filters[field.fieldname] ?? ''"
								:required="Boolean(field.required)"
								@input="setFilter(field, inputValue(field, $event.target.value))"
							/>
						</label>
					</template>
				</div>
				</details>
			</template>

			<template #resultMeta>
				<span>{{ rows.length.toLocaleString() }} matching row{{ rows.length === 1 ? "" : "s" }}</span>
				<span v-if="filters.branch">Branch: {{ filters.branch }}</span>
				<span v-else-if="filters.company">Company: {{ filters.company }}</span>
				<span v-if="truncated">Showing the first {{ maxVisibleRows.toLocaleString() }} rows. Narrow the filters for a complete review.</span>
			</template>
		</EdgeReportShell>

		<div v-if="message" class="managed-report-message">{{ message }}</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeDropdown"];

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}
function userError(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

export default {
	name: "ManagedReviewReport",
	props: {
		surfaceKey: { type: String, required: true },
	},
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			title: "",
			eyebrow: "",
			subtitle: "",
			action: {},
			filterFields: [],
			filters: {},
			rows: [],
			columns: [],
			summary: [],
			message: "",
			truncated: false,
			maxVisibleRows: 1000,
			pageSize: 50,
			currentPage: 1,
			sort: null,
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			canUseNativeDesk: false,
		};
	},
	computed: {
		primaryFilterFields() { return this.filterFields.slice(0, 6); },
		advancedFilterFields() { return this.filterFields.slice(6); },
		reportColumns() {
			return (this.columns || []).map((column) => ({
				...column,
				fieldtype: column.fieldtype || column.type || "Data",
				clickable: false,
			}));
		},
		sortedRows() {
			if (!this.sort?.field) return this.rows;
			const direction = this.sort.direction === "desc" ? -1 : 1;
			const field = this.sort.field;
			return [...this.rows].sort((left, right) => {
				const a = left?.[field];
				const b = right?.[field];
				if (a === b) return 0;
				if (a === null || a === undefined || a === "") return 1;
				if (b === null || b === undefined || b === "") return -1;
				if (typeof a === "number" && typeof b === "number") return (a - b) * direction;
				return String(a).localeCompare(String(b), undefined, { numeric: true }) * direction;
			});
		},
		visibleRows() {
			const start = (this.currentPage - 1) * this.pageSize;
			return this.sortedRows.slice(start, start + this.pageSize);
		},
		pagination() {
			const totalRows = this.rows.length;
			const totalPages = Math.max(1, Math.ceil(totalRows / this.pageSize));
			return {
				page: this.currentPage,
				page_size: this.pageSize,
				total_rows: totalRows,
				total_pages: totalPages,
				has_previous: this.currentPage > 1,
				has_next: this.currentPage < totalPages,
			};
		},
	},
	created() {
		const runtime = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !runtime[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() {
		if (this.edgeUIValid) this.fetchMetadata();
	},
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext({ force: true })
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.managed_review_reports.get_review_report_context", { surface_key: this.surfaceKey }),
					navigationPromise,
				]);
				this.title = context.title || "Review";
				this.eyebrow = context.eyebrow || "Review & Approvals";
				this.subtitle = context.subtitle || "";
				this.action = context.action || {};
				this.filterFields = context.filters || [];
				this.filters = { ...(context.default_filters || {}) };
				this.maxVisibleRows = Number(context.max_visible_rows || 1000);
				this.tenantName = navigation.context?.company || this.filters.company || "";
				this.branchName = navigation.context?.branch || this.filters.branch || "";
				this.userName = navigation.context?.user_name || frappe.session?.user || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				await this.fetchData();
			} catch (error) {
				this.error = userError(error, "Unable to load this review.");
			} finally {
				this.metadataLoading = false;
			}
		},
		async fetchData() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.managed_review_reports.run_review_report", {
					surface_key: this.surfaceKey,
					filters: this.filters,
				});
				this.rows = result.rows || [];
				this.columns = result.columns || [];
				this.summary = result.summary || [];
				this.message = result.message || "";
				this.truncated = Boolean(result.truncated);
				this.maxVisibleRows = Number(result.max_visible_rows || this.maxVisibleRows || 1000);
				this.currentPage = 1;
			} catch (error) {
				this.rows = [];
				this.columns = [];
				this.summary = [];
				this.error = userError(error, this.title + " could not be loaded.");
			} finally {
				this.loading = false;
			}
		},
		linkSearcher(field) {
			return async (txt) => {
				const result = await callMethod("retailedge.managed_review_reports.search_review_report_options", {
					doctype: field.options,
					txt: txt || "",
					company: this.filters.company || "",
				});
				return Array.isArray(result) ? result : [];
			};
		},
		inputType(field) {
			if (field.fieldtype === "Date") return "date";
			if (["Currency", "Int", "Float"].includes(field.fieldtype)) return "number";
			return "text";
		},
		inputValue(field, value) {
			if (["Currency", "Int", "Float"].includes(field.fieldtype)) {
				return value === "" ? "" : Number(value);
			}
			return value;
		},
		setFilter(field, value) {
			this.filters[field.fieldname] = value;
			if (field.fieldname === "company") {
				this.filters.branch = "";
				this.tenantName = value || "";
				this.branchName = "";
			}
			if (field.fieldname === "branch") this.branchName = value || "";
		},
		applyFilters() {
			for (const field of this.filterFields) {
				if (field.required && !this.filters[field.fieldname]) {
					this.error = field.label + " is required.";
					return;
				}
			}
			this.fetchData();
		},
		handleSortChange(sort) {
			this.sort = sort || null;
			this.currentPage = 1;
		},
		goToPage(page) {
			const totalPages = this.pagination.total_pages;
			this.currentPage = Math.min(Math.max(1, Number(page || 1)), totalPages);
		},
		setPageSize(size) {
			this.pageSize = Number(size || 50);
			this.currentPage = 1;
		},
		rowKey(row, index) {
			return row?.name || row?.row_id || row?.bank_transaction || row?.payment_event || String(index || "");
		},
		formatCell(value, column) {
			if (value === null || value === undefined || value === "") return "—";
			const fieldtype = column?.fieldtype || column?.type || "Data";
			if (fieldtype === "Check") return Number(value) ? "Yes" : "No";
			if (fieldtype === "Currency") {
				const number = Number(value);
				if (!Number.isFinite(number)) return String(value);
				return window.retailedge?.formatPlainValue?.(number, { fieldtype: "Currency" }) || number.toLocaleString();
			}
			if (fieldtype === "Date" || fieldtype === "Datetime") {
				try { return frappe.datetime.str_to_user(String(value)); } catch (_error) { return String(value); }
			}
			return String(value);
		},
		openAction() {
			if (this.action.route) frappe.set_route(this.action.route);
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
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
		},
	},
};
</script>

<style scoped>
.managed-filter-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; align-items:end; width:100%; }
.managed-filter-grid--advanced { margin-top:12px; }
.managed-advanced-filters { width:100%; margin-top:12px; border-top:1px solid var(--edge-border, var(--border-color)); padding-top:10px; }
.managed-advanced-filters summary { cursor:pointer; font-weight:600; color:var(--edge-text, var(--text-color)); }
.managed-input-field { display:grid; gap:6px; min-width:0; }
.managed-input-field > span { font-size:.78rem; font-weight:600; color:var(--edge-text-muted, #667085); }
.managed-check-field { min-height:38px; display:flex; align-items:center; gap:8px; padding:8px 10px; border:1px solid var(--edge-border, var(--border-color)); border-radius:8px; background:var(--edge-surface, var(--card-bg)); }
.managed-check-field input { width:1rem; height:1rem; }
.managed-report-message { margin:0 22px 22px; padding:12px 14px; border:1px solid var(--edge-border, var(--border-color)); border-radius:8px; background:var(--edge-surface, var(--card-bg)); color:var(--edge-text-muted, #667085); }
.managed-report-fallback { margin:20px; padding:16px; border:1px solid var(--edge-border, #d9d9d9); border-radius:10px; display:grid; gap:6px; }
@media (max-width:900px) { .managed-filter-grid { grid-template-columns:repeat(2,minmax(0,1fr)); } }
@media (max-width:640px) { .managed-filter-grid { grid-template-columns:1fr; } }
</style>
