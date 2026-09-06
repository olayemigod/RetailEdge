<template>
	<div v-if="!edgeUIValid" class="integrity-fallback">
		<strong>Stock & Accounting Integrity could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Stock & Accounting Integrity"
		:tenantName="tenantName || filters.company"
		branchName="Company-wide"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/stock-accounting-integrity"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Stock & Accounting Integrity"
			eyebrow="Accounting Control"
			subtitle="Read-only ERPNext stock-versus-accounting exceptions. Values and mismatch logic come from the native Stock and Account Value Comparison report."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:pagination="pagination"
			:loading="loading || metadataLoading"
			:error="error"
			:rowKey="rowKey"
			:formatter="formatCell"
			:pageSizes="[25, 50, 100]"
			emptyTitle="No stock/accounting mismatches"
			emptyDescription="ERPNext returned no stock-versus-accounting exceptions for this Company, Stock Account, and date range."
			loadingMessage="Checking ERPNext stock and accounting integrity…"
			@retry="fetchData"
			@page-change="goToPage"
			@page-size-change="setPageSize"
			@cell-click="openReportCell"
		>
			<template #actions>
				<div class="integrity-actions">
					<button
						v-if="canOpenNativeReport"
						class="edge-secondary-button"
						type="button"
						@click="openNativeReport"
					>
						Open ERPNext Advanced Report
					</button>
					<EdgeExportMenu
						v-if="rows.length"
						:dataset="exportDataset"
						:loadDataset="loadExportDataset"
					/>
				</div>
			</template>

			<template #filters>
				<div class="integrity-filter-grid">
					<EdgeLinkField
						v-model="filters.company"
						label="Company"
						required
						placeholder="Search company"
						:searcher="companySearch"
						@select="onCompanySelected"
					/>
					<EdgeLinkField
						v-model="filters.account"
						:selectedLabel="accountLabel"
						label="Stock Account"
						placeholder="All stock accounts"
						:searcher="accountSearch"
						@select="onAccountSelected"
						@clear="clearAccount"
					/>
					<label class="edge-field">
						<span class="edge-field-label">From Date</span>
						<input v-model="filters.from_date" class="edge-input" type="date" required />
					</label>
					<label class="edge-field">
						<span class="edge-field-label">As On Date</span>
						<input v-model="filters.as_on_date" class="edge-input" type="date" required />
					</label>
					<div class="filter-action">
						<button
							class="edge-primary-button"
							type="button"
							:disabled="loading || !filters.company || !filters.from_date || !filters.as_on_date"
							@click="applyFilters"
						>
							{{ loading ? "Checking…" : "Apply / Refresh" }}
						</button>
					</div>
				</div>
			</template>

			<template #resultMeta>
				<span>Company-wide accounting control · no Branch allocation</span>
				<span v-if="scope.account">Stock Account: {{ scope.account }}</span>
				<span v-if="scope.from_date && scope.as_on_date">{{ scope.from_date }} to {{ scope.as_on_date }}</span>
				<span v-if="scan.mismatch_rows !== undefined">{{ scan.mismatch_rows }} ERPNext exception row{{ scan.mismatch_rows === 1 ? "" : "s" }}</span>
				<span v-if="companyCurrency">Amounts in {{ companyCurrency }}</span>
				<span>Read-only review: corrections and reposting remain in authorised ERPNext workflows.</span>
			</template>
		</EdgeReportShell>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];
const REPORT_PRODUCT = "RetailEdge";
const REPORT_KEY = "stock-accounting-integrity";

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
	name: "StockAccountingIntegrityReport",
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
			scan: {},
			scope: {},
			menuItems: [],
			tenantName: "",
			userName: "",
			companyCurrency: "",
			accountLabel: "",
			nativeReportName: "Stock and Account Value Comparison",
			canOpenNativeReport: false,
			filters: {
				company: "",
				account: "",
				from_date: "",
				as_on_date: "",
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
				clickable: ["name", "voucher_no"].includes(column.fieldname),
			}));
		},
		exportDataset() {
			return {
				title: "Stock & Accounting Integrity",
				filename: `RetailEdge Stock Accounting Integrity ${this.filters.company || ""}`.trim(),
				columns: this.columns,
				rows: this.rows,
				filters: this.exportFilters,
				summary: this.summary,
				metadata: this.exportMetadata,
			};
		},
		exportFilters() {
			return [
				{ label: "Company", value: this.filters.company },
				{ label: "Stock Account", value: this.filters.account },
				{ label: "From Date", value: this.filters.from_date },
				{ label: "As On Date", value: this.filters.as_on_date },
			].filter((entry) => entry.value);
		},
		exportMetadata() {
			return [
				{ label: "Source", value: "ERPNext Stock and Account Value Comparison" },
				{ label: "Scope", value: "Company-wide accounting control" },
				{ label: "Correction Mode", value: "Read-only in RetailEdge" },
			].concat(this.companyCurrency ? [{ label: "Company Currency", value: this.companyCurrency }] : []);
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
					callMethod("retailedge.stock_accounting_integrity.get_stock_accounting_integrity_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.userName = context.user_name || "";
				this.companyCurrency = context.company_currency || "";
				this.nativeReportName = context.native_report_name || this.nativeReportName;
				this.canOpenNativeReport = Boolean(Number(context.can_open_native_report));
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Stock & Accounting Integrity controls.");
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
			const result = await callMethod("retailedge.stock_accounting_integrity.search_stock_accounting_integrity_options", {
				kind,
				txt,
				company: this.filters.company,
			});
			return Array.isArray(result) ? result : [];
		},
		companySearch(txt) {
			return this.searchOptions("company", txt);
		},
		accountSearch(txt) {
			if (!this.filters.company) return [];
			return this.searchOptions("account", txt);
		},
		onCompanySelected(option) {
			this.filters.company = option.value;
			this.filters.account = "";
			this.accountLabel = "";
			this.tenantName = option.label || option.value;
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
			if (!this.filters.company || !this.filters.from_date || !this.filters.as_on_date) return;
			if (!this.reportProvider?.load) {
				this.error = "The shared EdgeSuite Stock & Accounting Integrity provider is unavailable.";
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
				this.scope = result.metadata?.scope || {};
				this.companyCurrency = result.metadata?.company_currency || this.companyCurrency;
				this.nativeReportName = result.metadata?.native_report_name || this.nativeReportName;
				const totalRows = Number(result.total || this.rows.length);
				const totalPages = Math.max(1, Math.ceil(totalRows / pageSize));
				if (this.currentPage > totalPages) this.currentPage = totalPages;
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
				this.pagination = {};
				this.error = errorMessage(error, "Stock & Accounting Integrity failed to load.");
			} finally {
				this.loading = false;
			}
		},
		async loadExportDataset() {
			const result = this.reportProvider?.export
				? await this.reportProvider.export({ filters: this.providerFilters() })
				: {};
			return {
				columns: result.columns || this.columns,
				rows: result.rows || [],
				summary: result.summary || this.summary,
				metadata: [
					{ label: "Source", value: "ERPNext Stock and Account Value Comparison" },
					{ label: "Scope", value: "Company-wide accounting control" },
					{ label: "Correction Mode", value: "Read-only in RetailEdge" },
				].concat(result.company_currency ? [{ label: "Company Currency", value: result.company_currency }] : []),
			};
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
		openReportCell(payload) {
			if (payload?.column?.fieldname === "voucher_no" && payload?.row?.voucher_type && payload.value) {
				frappe.set_route("Form", payload.row.voucher_type, payload.value);
				return;
			}
			if (payload?.column?.fieldname === "name" && payload?.row?.ledger_type && payload.value) {
				frappe.set_route("Form", payload.row.ledger_type, payload.value);
			}
		},
		openNativeReport() {
			if (!this.canOpenNativeReport || !this.nativeReportName) return;
			frappe.route_options = {
				company: this.filters.company,
				account: this.filters.account || undefined,
				from_date: this.filters.from_date,
				as_on_date: this.filters.as_on_date,
			};
			frappe.set_route("query-report", this.nativeReportName);
		},
		rowKey(row, index) {
			return `${row.ledger_type || "ledger"}:${row.name || row.voucher_no || index}`;
		},
		formatCell(value, column) {
			return this.formatValue(value, column.fieldtype, column.options || this.companyCurrency);
		},
		formatValue(value, fieldtype, currency) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldtype === "Date") {
				try { return frappe.datetime.str_to_user(value); }
				catch (_error) { return value; }
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
.integrity-fallback {
	display: grid;
	gap: 8px;
	padding: 24px;
}
.integrity-filter-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
	gap: 12px;
	align-items: end;
	width: 100%;
}
.integrity-actions {
	display: flex;
	gap: 8px;
	align-items: center;
	flex-wrap: wrap;
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
.edge-primary-button,
.edge-secondary-button {
	min-height: 38px;
	border: 1px solid var(--edge-border, #d0d5dd);
	border-radius: var(--edge-radius-md, 8px);
	background: var(--edge-surface, #fff);
	color: var(--edge-text, #101828);
	padding: 8px 10px;
}
.edge-input,
.edge-primary-button {
	width: 100%;
}
.edge-primary-button {
	font-weight: 600;
}
.edge-secondary-button {
	font-weight: 600;
}
@media (max-width: 980px) {
	.integrity-filter-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 640px) {
	.integrity-filter-grid { grid-template-columns: 1fr; }
	.filter-action button { width: 100%; }
}
</style>
