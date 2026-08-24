<template>
	<div v-if="!edgeUIValid" class="planning-fallback">
		<strong>Forecasting & Planning could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Forecasting & Planning"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/forecasting-planning"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeReportShell
			title="Forecasting & Planning"
			eyebrow="Owner Planning"
			subtitle="Separate ERPNext actuals, explainable forecasts and owner plans for sales, cash, expenses, profitability and inventory demand."
			:columns="reportColumns"
			:rows="rows"
			:summary="summary"
			:loading="loading || metadataLoading"
			:error="error"
			rowKey="planning_key"
			:formatter="formatCell"
			emptyTitle="No planning data available"
			emptyDescription="Select a permitted company and planning window, then apply the filters."
			loadingMessage="Building forecast and plan…"
			@retry="fetchData"
		>
			<template #actions>
				<div class="planning-actions">
					<button class="edge-secondary-button" type="button" @click="newScenario">Save as Scenario</button>
					<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
				</div>
			</template>

			<template #filters>
				<div class="planning-filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="scenarioName" label="Planning Scenario" placeholder="Load saved scenario" :searcher="scenarioSearch" @select="onScenarioSelected" @clear="clearScenario" />
					<label class="edge-field"><span class="edge-field-label">As of Date</span><input v-model="filters.as_of_date" class="edge-input" type="date" /></label>
					<label class="edge-field"><span class="edge-field-label">History Months</span><input v-model.number="filters.history_months" class="edge-input" type="number" min="3" max="24" /></label>
					<label class="edge-field"><span class="edge-field-label">Forecast Months</span><input v-model.number="filters.forecast_months" class="edge-input" type="number" min="1" max="12" /></label>
					<label class="edge-field"><span class="edge-field-label">Sales Plan Adjustment (%)</span><input v-model.number="filters.sales_adjustment_percent" class="edge-input" type="number" min="-100" max="1000" step="1" /></label>
					<label class="edge-field"><span class="edge-field-label">Expense Plan Adjustment (%)</span><input v-model.number="filters.expense_adjustment_percent" class="edge-input" type="number" min="-100" max="1000" step="1" /></label>
					<label class="edge-field"><span class="edge-field-label">Cash Plan Adjustment (%)</span><input v-model.number="filters.cash_adjustment_percent" class="edge-input" type="number" min="-100" max="1000" step="1" /></label>
					<label class="edge-field"><span class="edge-field-label">Inventory Safety Allowance (%)</span><input v-model.number="filters.inventory_safety_percent" class="edge-input" type="number" min="0" max="500" step="1" /></label>
					<div class="filter-action"><button class="edge-primary-button" type="button" :disabled="loading || !filters.company" @click="applyFilters">{{ loading ? "Loading…" : "Apply Plan" }}</button></div>
				</div>
			</template>

			<template #resultMeta>
				<span>{{ scopeLabel }}</span>
				<span>Actual, Forecast and Plan are separate; forecasts never create ERPNext accounting or stock transactions.</span>
				<span>Accounting expense/profit planning is company-level unless valid ERPNext branch accounting attribution exists.</span>
			</template>
		</EdgeReportShell>

		<section v-if="domainWarnings.length" class="planning-panel">
			<div class="panel-heading"><div><p class="panel-eyebrow">Availability</p><h3>Domains not evaluated</h3></div></div>
			<div class="warning-grid">
				<div v-for="item in domainWarnings" :key="item.key" class="warning-card">
					<strong>{{ item.title }}</strong><span>{{ item.reason }}</span>
				</div>
			</div>
		</section>

		<section class="planning-panel">
			<div class="panel-heading">
				<div><p class="panel-eyebrow">Inventory Planning</p><h3>Forecast demand vs projected stock</h3></div>
				<span class="panel-note">Demand is observational; no Material Request is created.</span>
			</div>
			<div v-if="inventoryUnavailable" class="panel-empty">{{ inventoryUnavailable }}</div>
			<div v-else-if="!inventoryRows.length" class="panel-empty">No inventory demand rows are available for this scope.</div>
			<div v-else class="table-wrap">
				<table class="planning-table">
					<thead><tr><th>Month</th><th>Item</th><th>Forecast Demand</th><th>Plan + Safety</th><th>Projected Stock</th><th>Status</th></tr></thead>
					<tbody>
						<tr v-for="row in inventoryRows" :key="`${row.period_start}-${row.item_code}`">
							<td>{{ row.period_start }}</td><td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td>
							<td>{{ formatQty(row.forecast_demand_qty, row.stock_uom) }}</td><td>{{ formatQty(row.planned_demand_qty, row.stock_uom) }}</td><td>{{ formatQty(row.current_projected_qty, row.stock_uom) }}</td>
							<td><span :class="['status-pill', Number(row.planned_demand_qty || 0) > Number(row.current_projected_qty || 0) ? 'status-risk' : 'status-ok']">{{ Number(row.planned_demand_qty || 0) > Number(row.current_projected_qty || 0) ? "Coverage risk" : "Covered" }}</span></td>
						</tr>
					</tbody>
				</table>
			</div>
		</section>

		<section v-if="scenarioName" class="planning-panel">
			<div class="panel-heading">
				<div><p class="panel-eyebrow">Forecast vs Actual</p><h3>{{ scenarioLabel || scenarioName }}</h3></div>
				<button class="edge-secondary-button" type="button" @click="openScenario">Open Scenario</button>
			</div>
			<div v-if="performanceLoading" class="panel-empty">Loading scenario performance…</div>
			<div v-else-if="performanceError" class="panel-empty panel-error">{{ performanceError }}</div>
			<template v-else>
				<div class="performance-summary"><div v-for="card in performanceSummary" :key="card.label" class="metric-card"><span>{{ card.label }}</span><strong>{{ formatSummary(card) }}</strong></div></div>
				<div v-if="performanceRows.length" class="table-wrap">
					<table class="planning-table"><thead><tr><th>Month</th><th>Forecast</th><th>Plan</th><th>Actual</th><th>Forecast Accuracy</th><th>Plan Accuracy</th></tr></thead><tbody>
						<tr v-for="row in performanceRows" :key="row.period_start"><td>{{ row.period_start }}</td><td>{{ money(row.forecast) }}</td><td>{{ money(row.plan) }}</td><td>{{ money(row.actual) }}</td><td>{{ percent(row.forecast_accuracy_percent) }}</td><td>{{ percent(row.plan_accuracy_percent) }}</td></tr>
					</tbody></table>
				</div>
				<div v-else class="panel-empty">No forecast months in this scenario have completed actuals yet.</div>
			</template>
		</section>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeReportShell", "EdgeLinkField", "EdgeExportMenu"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message ?? {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ForecastingPlanning",
	props: { pageMethod: { type: String, required: true }, exportMethod: { type: String, required: true } },
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			rows: [], columns: [], summary: [], scope: {}, domains: {}, metadata: {}, menuItems: [],
			tenantName: "", branchName: "", userName: "", companyCurrency: "",
			scenarioName: "", scenarioLabel: "", performanceRows: [], performanceSummary: [], performanceLoading: false, performanceError: "",
			filters: { company: "", branch: "", as_of_date: "", history_months: 6, forecast_months: 3, sales_adjustment_percent: 0, expense_adjustment_percent: 0, cash_adjustment_percent: 0, inventory_safety_percent: 10 },
		};
	},
	computed: {
		reportColumns() { return (this.columns || []).map((column) => ({ ...column, fieldtype: column.fieldtype || column.type || "Data", sortable: true })); },
		scopeLabel() { return this.scope.branch ? `Branch: ${this.scope.branch}` : (this.scope.company ? `Company: ${this.scope.company}` : "Permitted planning scope"); },
		inventoryRows() { return this.domains?.inventory?.available ? (this.domains.inventory.rows || []) : []; },
		inventoryUnavailable() { const domain = this.domains?.inventory; return domain && !domain.available ? domain.reason || "Inventory planning is unavailable." : ""; },
		domainWarnings() {
			return Object.entries(this.domains || {}).filter(([, domain]) => domain && domain.available === false).map(([key, domain]) => ({ key, title: domain.title || key.replace(/_/g, " "), reason: domain.reason || "This domain could not be evaluated safely." }));
		},
		exportDataset() { return { title: "Forecasting & Planning", filename: `RetailEdge Forecasting Planning ${this.filters.company || ""}`.trim(), columns: this.columns, rows: this.rows, filters: this.exportFilters, summary: this.summary, metadata: this.exportMetadata }; },
		exportFilters() {
			const labels = { company: "Company", branch: "Branch", as_of_date: "As of Date", history_months: "History Months", forecast_months: "Forecast Months", sales_adjustment_percent: "Sales Plan Adjustment (%)", expense_adjustment_percent: "Expense Plan Adjustment (%)", cash_adjustment_percent: "Cash Plan Adjustment (%)", inventory_safety_percent: "Inventory Safety Allowance (%)" };
			return Object.entries(labels).map(([key, label]) => ({ label, value: this.filters[key] })).filter((entry) => entry.value !== "" && entry.value !== null && entry.value !== undefined);
		},
		exportMetadata() { return [{ label: "Accounting Truth", value: this.metadata.accounting_truth || "ERPNext General Ledger / Profit and Loss" }, { label: "Sales Truth", value: this.metadata.sales_truth || "Submitted ERPNext Sales Invoice / Item" }, { label: "Inventory Truth", value: this.metadata.inventory_truth || "ERPNext Stock Ledger / Bin / Item Reorder" }, { label: "Scenario Model", value: this.metadata.scenario_truth || "Assumptions only; no forecasted accounting transactions are persisted" }]; },
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.sales_reporting.get_sales_reporting_context"), navigationPromise]);
				this.filters = { ...this.filters, company: context.default_filters?.company || "", branch: context.default_filters?.branch || "", as_of_date: frappe.datetime.get_today() };
				this.tenantName = context.tenant_name || this.filters.company || ""; this.branchName = context.branch_name || this.filters.branch || ""; this.userName = context.user_name || ""; this.companyCurrency = context.company_currency || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				const options = frappe.route_options || {};
				if (options.company) this.filters.company = options.company;
				if (options.branch !== undefined) this.filters.branch = options.branch || "";
				if (options.scenario) { this.scenarioName = options.scenario; await this.loadScenario(options.scenario); }
				else if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Forecasting & Planning controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer"); else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer"); },
		async searchOptions(kind, txt) { const result = await callMethod("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); },
		async scenarioSearch(txt) {
			if (!this.filters.company) return [];
			const rows = await callMethod("frappe.client.get_list", { doctype: "RetailEdge Planning Scenario", fields: ["name", "scenario_name", "scenario_type", "status"], filters: { company: this.filters.company, ...(this.filters.branch ? { branch: this.filters.branch } : {}) }, or_filters: [["name", "like", `%${txt || ""}%`], ["scenario_name", "like", `%${txt || ""}%`]], order_by: "modified desc", limit_page_length: 20 });
			return (Array.isArray(rows) ? rows : []).map((row) => ({ value: row.name, label: row.scenario_name || row.name, description: [row.scenario_type, row.status, row.name].filter(Boolean).join(" · ") }));
		},
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.clearScenario(); },
		onBranchSelected(option) { this.filters.branch = option?.value || ""; this.clearScenario(); }, clearBranch() { this.filters.branch = ""; this.clearScenario(); },
		async onScenarioSelected(option) { this.scenarioName = option?.value || ""; this.scenarioLabel = option?.label || this.scenarioName; if (this.scenarioName) await this.loadScenario(this.scenarioName); },
		clearScenario() { this.scenarioName = ""; this.scenarioLabel = ""; this.performanceRows = []; this.performanceSummary = []; this.performanceError = ""; },
		async loadScenario(name) {
			this.performanceLoading = true; this.performanceError = "";
			try {
				const doc = await callMethod("frappe.client.get", { doctype: "RetailEdge Planning Scenario", name });
				this.scenarioName = doc.name || name; this.scenarioLabel = doc.scenario_name || doc.name || name;
				this.filters = { ...this.filters, company: doc.company || this.filters.company, branch: doc.branch || "", as_of_date: doc.as_of_date || this.filters.as_of_date, history_months: Number(doc.history_months || 6), forecast_months: Number(doc.horizon_months || 3), sales_adjustment_percent: Number(doc.sales_adjustment_percent || 0), expense_adjustment_percent: Number(doc.expense_adjustment_percent || 0), cash_adjustment_percent: Number(doc.cash_adjustment_percent || 0), inventory_safety_percent: Number(doc.inventory_safety_percent || 10) };
				await this.fetchData();
				const performance = await callMethod("retailedge.scenario_performance.get_scenario_performance", { scenario: name });
				this.performanceRows = performance.rows || []; this.performanceSummary = performance.summary || [];
			} catch (error) { this.performanceError = errorMessage(error, "Failed to load scenario performance."); }
			finally { this.performanceLoading = false; }
		},
		newScenario() {
			if (!this.filters.company) return;
			frappe.route_options = { company: this.filters.company, branch: this.filters.branch || "", as_of_date: this.filters.as_of_date, history_months: this.filters.history_months, horizon_months: this.filters.forecast_months, sales_adjustment_percent: this.filters.sales_adjustment_percent, expense_adjustment_percent: this.filters.expense_adjustment_percent, cash_adjustment_percent: this.filters.cash_adjustment_percent, inventory_safety_percent: this.filters.inventory_safety_percent };
			frappe.new_doc("RetailEdge Planning Scenario");
		},
		openScenario() { if (this.scenarioName) frappe.set_route("Form", "RetailEdge Planning Scenario", this.scenarioName); },
		async applyFilters() { this.clearScenario(); await this.fetchData(); },
		async fetchData() {
			if (!this.filters.company) return;
			this.loading = true; this.error = "";
			try {
				const result = await callMethod(this.pageMethod, { filters: { ...this.filters } });
				this.rows = (result.rows || []).map((row, index) => ({ ...row, planning_key: `${row.domain || "domain"}-${row.period_start || index}-${row.row_type || "row"}` }));
				this.columns = result.columns || []; this.summary = result.summary || []; this.scope = result.scope || {}; this.domains = result.domains || {}; this.metadata = result.metadata || {}; this.companyCurrency = result.company_currency || this.companyCurrency;
			} catch (error) { this.error = errorMessage(error, "Failed to load Forecasting & Planning."); }
			finally { this.loading = false; }
		},
		async loadExportDataset() { return callMethod(this.exportMethod, { filters: { ...this.filters } }); },
		formatCell(value, column) { if (value === null || value === undefined || value === "") return "—"; const type = column?.fieldtype || column?.type; if (type === "Currency") return this.money(value); if (type === "Percent") return this.percent(value); if (type === "Int") return String(Number(value || 0)); return String(value); },
		money(value) { return format_currency(Number(value || 0), this.companyCurrency || undefined); }, percent(value) { return value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`; },
		formatQty(value, uom) { return `${Number(value || 0).toFixed(2)}${uom ? ` ${uom}` : ""}`; },
		formatSummary(card) { if (card.datatype === "Currency") return this.money(card.value); if (card.datatype === "Percent") return this.percent(card.value); return card.value === null || card.value === undefined ? "—" : String(card.value); },
	},
};
</script>

<style scoped>
.planning-fallback,.panel-empty{display:grid;gap:.5rem;padding:1.5rem}.planning-filter-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(185px,1fr));gap:.85rem;align-items:end}.edge-field{display:grid;gap:.35rem}.edge-field-label,.panel-eyebrow{font-size:.78rem;font-weight:600}.edge-input{width:100%;min-height:38px;border:1px solid var(--border-color,#dfe3e8);border-radius:8px;padding:.45rem .65rem;background:var(--control-bg,transparent);color:inherit}.filter-action,.planning-actions{display:flex;gap:.6rem;align-items:end}.edge-primary-button,.edge-secondary-button{min-height:38px;border-radius:8px;padding:.5rem .9rem;font-weight:600}.edge-primary-button{width:100%;border:0;background:var(--primary,#171717);color:var(--primary-foreground,#fff)}.edge-secondary-button{border:1px solid var(--border-color,#dfe3e8);background:var(--control-bg,transparent);color:inherit}.edge-primary-button:disabled{opacity:.55}.planning-panel{margin:1rem;padding:1rem;border:1px solid var(--border-color,#dfe3e8);border-radius:12px;background:var(--card-bg,var(--fg-color,#fff))}.panel-heading{display:flex;justify-content:space-between;gap:1rem;align-items:center;margin-bottom:1rem}.panel-heading h3,.panel-heading p{margin:0}.panel-note,.warning-card span,td small{display:block;color:var(--text-muted,#6b7280);font-size:.82rem}.warning-grid,.performance-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:.75rem}.warning-card,.metric-card{display:grid;gap:.35rem;padding:.85rem;border:1px solid var(--border-color,#dfe3e8);border-radius:10px}.metric-card span{font-size:.78rem;color:var(--text-muted,#6b7280)}.metric-card strong{font-size:1.05rem}.table-wrap{overflow:auto}.planning-table{width:100%;border-collapse:collapse}.planning-table th,.planning-table td{text-align:left;padding:.7rem;border-bottom:1px solid var(--border-color,#e5e7eb);white-space:nowrap}.planning-table th{font-size:.78rem;color:var(--text-muted,#6b7280)}.status-pill{display:inline-flex;padding:.2rem .5rem;border-radius:999px;font-size:.75rem;font-weight:600}.status-risk{background:rgba(220,38,38,.1);color:#b91c1c}.status-ok{background:rgba(22,163,74,.1);color:#15803d}.panel-error{color:var(--red-600,#dc2626)}@media(max-width:720px){.panel-heading{align-items:flex-start;flex-direction:column}.planning-actions{width:100%;flex-wrap:wrap}}
</style>
