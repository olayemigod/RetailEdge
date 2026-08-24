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
		<div class="planning-page">
			<header class="planning-header">
				<div>
					<p class="eyebrow">Owner Planning</p>
					<h2>Forecasting & Planning</h2>
					<p class="muted">ERPNext actuals remain authoritative. Forecast and Plan are analytical layers and never create accounting or stock transactions.</p>
				</div>
				<div class="header-actions">
					<button class="edge-button" type="button" @click="newScenario" :disabled="!filters.company">Save as Scenario</button>
					<EdgeExportMenu v-if="rows.length" :dataset="exportDataset" :loadDataset="loadExportDataset" />
				</div>
			</header>

			<section class="panel">
				<div class="filter-grid">
					<EdgeLinkField v-model="filters.company" label="Company" required placeholder="Search company" :searcher="companySearch" @select="onCompanySelected" />
					<EdgeLinkField v-model="filters.branch" label="Branch" placeholder="All permitted branches" :searcher="branchSearch" @select="onBranchSelected" @clear="clearBranch" />
					<EdgeLinkField v-model="scenarioName" label="Planning Scenario" placeholder="Load saved scenario" :searcher="scenarioSearch" @select="onScenarioSelected" @clear="clearScenario" />
					<label class="field"><span>As of Date</span><input v-model="filters.as_of_date" type="date" /></label>
					<label class="field"><span>History Months</span><input v-model.number="filters.history_months" type="number" min="3" max="24" /></label>
					<label class="field"><span>Forecast Months</span><input v-model.number="filters.forecast_months" type="number" min="1" max="12" /></label>
					<label class="field"><span>Sales Plan Adjustment (%)</span><input v-model.number="filters.sales_adjustment_percent" type="number" min="-100" max="1000" /></label>
					<label class="field"><span>Expense Plan Adjustment (%)</span><input v-model.number="filters.expense_adjustment_percent" type="number" min="-100" max="1000" /></label>
					<label class="field"><span>Cash Plan Adjustment (%)</span><input v-model.number="filters.cash_adjustment_percent" type="number" min="-100" max="1000" /></label>
					<label class="field"><span>Inventory Safety Allowance (%)</span><input v-model.number="filters.inventory_safety_percent" type="number" min="0" max="500" /></label>
					<div class="filter-action"><button class="edge-button primary" type="button" @click="fetchData" :disabled="loading || !filters.company">{{ loading ? "Loading…" : "Apply Plan" }}</button></div>
				</div>
			</section>

			<div v-if="error" class="alert error">{{ error }}</div>
			<div v-if="loading || metadataLoading" class="panel muted">Building forecast and plan…</div>

			<template v-else>
				<section v-if="summary.length" class="metric-grid">
					<div v-for="card in summary" :key="card.label" class="metric-card"><span>{{ card.label }}</span><strong>{{ formatCard(card) }}</strong></div>
				</section>

				<section class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Actual / Forecast / Plan</p><h3>Monthly planning view</h3></div><span class="muted">{{ scopeLabel }}</span></div>
					<div v-if="!rows.length" class="empty">No planning rows are available for this scope.</div>
					<div v-else class="table-wrap">
						<table><thead><tr><th>Month</th><th>Domain</th><th>Type</th><th class="num">Actual</th><th class="num">Forecast</th><th class="num">Plan</th><th class="num">Plan vs Forecast</th></tr></thead>
						<tbody><tr v-for="row in rows" :key="`${row.period_start}-${row.domain}-${row.row_type}`"><td>{{ row.period_start }}</td><td>{{ row.domain }}</td><td>{{ row.row_type }}</td><td class="num">{{ money(row.actual) }}</td><td class="num">{{ money(row.forecast) }}</td><td class="num">{{ money(row.plan) }}</td><td class="num">{{ money(row.variance) }}</td></tr></tbody></table>
					</div>
				</section>

				<section v-if="domainWarnings.length" class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Availability</p><h3>Domains not evaluated</h3></div></div>
					<div class="warning-grid"><div v-for="item in domainWarnings" :key="item.key" class="warning-card"><strong>{{ item.title }}</strong><span>{{ item.reason }}</span></div></div>
				</section>

				<section class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Cash Planning</p><h3>Known due commitments</h3></div><span class="muted">Shown separately from the behaviour-based cash forecast; collection/payment is not assumed.</span></div>
					<div v-if="cashCommitmentReason" class="empty">{{ cashCommitmentReason }}</div>
					<div v-else-if="cashCommitments.length" class="table-wrap"><table><thead><tr><th>Month</th><th class="num">Receivables Due</th><th class="num">Payables Due</th><th class="num">Net Known Due</th></tr></thead><tbody><tr v-for="row in cashCommitments" :key="row.period_start"><td>{{ row.period_start }}</td><td class="num">{{ money(row.receivables_due) }}</td><td class="num">{{ money(row.payables_due) }}</td><td class="num">{{ money(row.net_known_due) }}</td></tr></tbody></table></div>
					<div v-else class="empty">No known due commitments fall inside this forecast horizon.</div>
				</section>

				<section class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Budget Governance</p><h3>ERPNext Budget reference</h3></div><span class="muted">R12 does not create a second budget ledger.</span></div>
					<div v-if="budgetReason" class="empty">{{ budgetReason }}</div>
					<div v-else class="metric-grid compact"><div v-for="card in budgetSummary" :key="card.label" class="metric-card"><span>{{ card.label }}</span><strong>{{ formatCard(card) }}</strong></div></div>
				</section>

				<section class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Inventory Planning</p><h3>Cumulative demand vs projected stock</h3></div><span class="muted">No Material Request is created.</span></div>
					<div v-if="inventoryReason" class="empty">{{ inventoryReason }}</div>
					<div v-else-if="inventoryRows.length" class="table-wrap"><table><thead><tr><th>Month</th><th>Item</th><th class="num">Forecast Demand</th><th class="num">Plan + Safety</th><th class="num">Cumulative Plan</th><th class="num">Projected Stock</th><th class="num">Shortfall</th><th>Status</th></tr></thead><tbody><tr v-for="row in inventoryRows" :key="`${row.period_start}-${row.item_code}`"><td>{{ row.period_start }}</td><td><strong>{{ row.item_code }}</strong><small>{{ row.item_name }}</small></td><td class="num">{{ qty(row.forecast_demand_qty, row.stock_uom) }}</td><td class="num">{{ qty(row.planned_demand_qty, row.stock_uom) }}</td><td class="num">{{ qty(row.cumulative_planned_demand_qty, row.stock_uom) }}</td><td class="num">{{ qty(row.current_projected_qty, row.stock_uom) }}</td><td class="num">{{ qty(row.coverage_shortfall_qty, row.stock_uom) }}</td><td><span :class="['pill', row.coverage_risk ? 'risk' : 'ok']">{{ row.coverage_risk ? "Coverage risk" : "Covered" }}</span></td></tr></tbody></table></div>
					<div v-else class="empty">No observed inventory demand is available for this scope.</div>
				</section>

				<section v-if="scenarioName" class="panel">
					<div class="panel-heading"><div><p class="eyebrow">Forecast vs Actual</p><h3>{{ scenarioLabel || scenarioName }}</h3></div><button class="edge-button" type="button" @click="openScenario">Open Scenario</button></div>
					<div v-if="performanceLoading" class="empty">Loading scenario performance…</div>
					<div v-else-if="performanceError" class="alert error">{{ performanceError }}</div>
					<template v-else><div class="metric-grid compact"><div v-for="card in performanceSummary" :key="card.label" class="metric-card"><span>{{ card.label }}</span><strong>{{ formatCard(card) }}</strong></div></div><div v-if="performanceRows.length" class="table-wrap"><table><thead><tr><th>Month</th><th>Domain</th><th class="num">Forecast</th><th class="num">Plan</th><th class="num">Actual</th><th class="num">Forecast Accuracy</th><th class="num">Plan Accuracy</th></tr></thead><tbody><tr v-for="row in performanceRows" :key="`${row.period_start}-${row.domain}`"><td>{{ row.period_start }}</td><td>{{ row.domain }}</td><td class="num">{{ money(row.forecast) }}</td><td class="num">{{ money(row.plan) }}</td><td class="num">{{ money(row.actual) }}</td><td class="num">{{ percent(row.forecast_accuracy_percent) }}</td><td class="num">{{ percent(row.plan_accuracy_percent) }}</td></tr></tbody></table></div><div v-else class="empty">No forecast months in this scenario have completed actuals yet.</div></template>
				</section>
			</template>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField", "EdgeExportMenu"];
function components() { return window.EdgeSuiteUI?.components || {}; }
function call(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (r) => resolve(r.message ?? {}), error: reject })); }
function message(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ForecastingPlanning",
	props: { pageMethod: { type: String, required: true }, exportMethod: { type: String, required: true } },
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, components()[name]])),
	data() { return {
		edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
		rows: [], columns: [], summary: [], domains: {}, scope: {}, metadata: {}, companyCurrency: "",
		tenantName: "", branchName: "", userName: "", menuItems: [],
		scenarioName: "", scenarioLabel: "", performanceRows: [], performanceSummary: [], performanceLoading: false, performanceError: "",
		filters: { company: "", branch: "", as_of_date: "", history_months: 6, forecast_months: 3, sales_adjustment_percent: 0, expense_adjustment_percent: 0, cash_adjustment_percent: 0, inventory_safety_percent: 10 },
	}; },
	computed: {
		scopeLabel() { return this.scope.branch ? `Branch: ${this.scope.branch}` : (this.scope.company ? `Company: ${this.scope.company}` : "Permitted planning scope"); },
		domainWarnings() { return Object.entries(this.domains || {}).filter(([, d]) => d && d.available === false).map(([key, d]) => ({ key, title: d.title || key.replace(/_/g, " "), reason: d.reason || "Not safely available for this scope." })); },
		inventoryRows() { return this.domains?.inventory?.available ? (this.domains.inventory.rows || []) : []; },
		inventoryReason() { const d = this.domains?.inventory; return d && d.available === false ? d.reason : ""; },
		cashCommitments() { return this.domains?.cash?.available ? (this.domains.cash.commitment_rows || []) : []; },
		cashCommitmentReason() { const d = this.domains?.cash; if (!d) return ""; if (d.available === false) return d.reason || "Cash planning is unavailable."; const meta = d.metadata?.known_due_schedule || {}; return meta.available === false ? (meta.reason || "Known due commitments are unavailable.") : ""; },
		budgetSummary() { return this.domains?.budget?.available ? (this.domains.budget.summary || []) : []; },
		budgetReason() { const d = this.domains?.budget; return d && d.available === false ? d.reason : ""; },
		exportDataset() { return { title: "Forecasting & Planning", filename: `RetailEdge Forecasting Planning ${this.filters.company || ""}`.trim(), columns: this.columns, rows: this.rows, filters: this.exportFilters, summary: this.summary, metadata: this.exportMetadata }; },
		exportFilters() { return Object.entries({ company: "Company", branch: "Branch", as_of_date: "As of Date", history_months: "History Months", forecast_months: "Forecast Months", sales_adjustment_percent: "Sales Adjustment (%)", expense_adjustment_percent: "Expense Adjustment (%)", cash_adjustment_percent: "Cash Adjustment (%)", inventory_safety_percent: "Inventory Safety (%)" }).map(([key, label]) => ({ label, value: this.filters[key] })).filter((x) => x.value !== "" && x.value !== null && x.value !== undefined); },
		exportMetadata() { return [{ label: "Accounting Truth", value: this.metadata.accounting_truth || "ERPNext GL / P&L" }, { label: "Budget Truth", value: this.metadata.budget_truth || "Submitted ERPNext Budget" }, { label: "Scenario Model", value: this.metadata.scenario_truth || "Assumptions only" }]; },
	},
	created() { const c = components(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !c[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.bootstrap(); },
	methods: {
		async bootstrap() {
			this.metadataLoading = true;
			try {
				const [context, navigation] = await Promise.all([call("retailedge.sales_reporting.get_sales_reporting_context"), call("retailedge.edgesuite_ui.get_retailedge_business_hub_context")]);
				this.filters.company = context.default_filters?.company || ""; this.filters.branch = context.default_filters?.branch || ""; this.filters.as_of_date = frappe.datetime.get_today();
				this.tenantName = context.tenant_name || this.filters.company; this.branchName = context.branch_name || this.filters.branch; this.userName = context.user_name || ""; this.companyCurrency = context.company_currency || "";
				this.menuItems = this.mapNavigation(navigation.navigation_groups || []);
				const opts = frappe.route_options || {}; if (opts.company) this.filters.company = opts.company; if (opts.branch !== undefined) this.filters.branch = opts.branch || "";
				if (opts.scenario) { this.scenarioName = opts.scenario; await this.loadScenario(opts.scenario); } else if (this.filters.company) await this.fetchData();
			} catch (e) { this.error = message(e, "Failed to load Forecasting & Planning controls."); }
			finally { this.metadataLoading = false; }
		},
		mapNavigation(groups) { return groups.map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeFor(item) })) })); },
		routeFor(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((g) => g.items || []).find((x) => x.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else window.open(route, "_blank", "noopener,noreferrer"); },
		async searchOptions(kind, txt) { const result = await call("retailedge.sales_reporting.search_sales_reporting_options", { kind, txt, company: this.filters.company, branch: this.filters.branch }); return Array.isArray(result) ? result : []; },
		companySearch(txt) { return this.searchOptions("company", txt); }, branchSearch(txt) { return this.searchOptions("branch", txt); },
		async scenarioSearch(txt) { if (!this.filters.company) return []; const rows = await call("frappe.client.get_list", { doctype: "RetailEdge Planning Scenario", filters: { company: this.filters.company }, fields: ["name", "scenario_name"], limit_page_length: 20, order_by: "modified desc" }); return (Array.isArray(rows) ? rows : []).filter((r) => !txt || `${r.name} ${r.scenario_name || ""}`.toLowerCase().includes(String(txt).toLowerCase())).map((r) => ({ value: r.name, label: r.scenario_name || r.name })); },
		onCompanySelected(option) { this.filters.company = option?.value || ""; this.filters.branch = ""; this.clearScenario(); }, onBranchSelected(option) { this.filters.branch = option?.value || ""; this.clearScenario(); }, clearBranch() { this.filters.branch = ""; this.clearScenario(); },
		async onScenarioSelected(option) { this.scenarioName = option?.value || ""; this.scenarioLabel = option?.label || this.scenarioName; if (this.scenarioName) await this.loadScenario(this.scenarioName); },
		clearScenario() { this.scenarioName = ""; this.scenarioLabel = ""; this.performanceRows = []; this.performanceSummary = []; this.performanceError = ""; },
		async loadScenario(name) { const doc = await call("frappe.client.get", { doctype: "RetailEdge Planning Scenario", name }); this.scenarioName = doc.name; this.scenarioLabel = doc.scenario_name || doc.name; this.filters = { ...this.filters, company: doc.company, branch: doc.branch || "", as_of_date: doc.as_of_date, history_months: Number(doc.history_months || 6), forecast_months: Number(doc.horizon_months || 3), sales_adjustment_percent: Number(doc.sales_adjustment_percent || 0), expense_adjustment_percent: Number(doc.expense_adjustment_percent || 0), cash_adjustment_percent: Number(doc.cash_adjustment_percent || 0), inventory_safety_percent: Number(doc.inventory_safety_percent || 0) }; await Promise.all([this.fetchData(), this.fetchPerformance()]); },
		async fetchData() { if (!this.filters.company) return; this.loading = true; this.error = ""; try { const result = await call(this.pageMethod, { filters: { ...this.filters } }); this.rows = result.rows || []; this.columns = result.columns || []; this.summary = result.summary || []; this.domains = result.domains || {}; this.scope = result.scope || {}; this.metadata = result.metadata || {}; this.companyCurrency = result.company_currency || this.companyCurrency; } catch (e) { this.error = message(e, "Failed to build Forecasting & Planning data."); } finally { this.loading = false; } },
		async fetchPerformance() { if (!this.scenarioName) return; this.performanceLoading = true; this.performanceError = ""; try { const result = await call("retailedge.scenario_performance.get_scenario_performance", { scenario: this.scenarioName }); this.performanceRows = result.rows || []; this.performanceSummary = result.summary || []; } catch (e) { this.performanceError = message(e, "Failed to load forecast-vs-actual performance."); } finally { this.performanceLoading = false; } },
		newScenario() { frappe.route_options = { company: this.filters.company, branch: this.filters.branch, as_of_date: this.filters.as_of_date, history_months: this.filters.history_months, horizon_months: this.filters.forecast_months, sales_adjustment_percent: this.filters.sales_adjustment_percent, expense_adjustment_percent: this.filters.expense_adjustment_percent, cash_adjustment_percent: this.filters.cash_adjustment_percent, inventory_safety_percent: this.filters.inventory_safety_percent }; frappe.new_doc("RetailEdge Planning Scenario"); },
		openScenario() { if (this.scenarioName) frappe.set_route("Form", "RetailEdge Planning Scenario", this.scenarioName); },
		loadExportDataset() { return call(this.exportMethod, { filters: { ...this.filters } }); },
		money(value) { return value === null || value === undefined || value === "" ? "—" : format_currency(Number(value || 0), this.companyCurrency || undefined); },
		percent(value) { return value === null || value === undefined || value === "" ? "—" : `${Number(value).toFixed(1)}%`; },
		qty(value, uom) { return value === null || value === undefined ? "—" : `${Number(value || 0).toFixed(2)}${uom ? ` ${uom}` : ""}`; },
		formatCard(card) { if (card.value === null || card.value === undefined) return "—"; if (card.datatype === "Currency") return this.money(card.value); if (card.datatype === "Percent") return this.percent(card.value); return String(card.value); },
	},
};
</script>

<style scoped>
.planning-page { display:grid; gap:1rem; padding:1rem; }
.planning-header,.panel-heading,.header-actions { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
.planning-header h2,.panel-heading h3 { margin:.15rem 0; }
.eyebrow { margin:0; font-size:.72rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; opacity:.7; }
.muted { opacity:.72; }
.panel { border:1px solid var(--border-color,#dfe3e8); border-radius:12px; padding:1rem; background:var(--card-bg,var(--fg-color,#fff)); }
.filter-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:.8rem; align-items:end; }
.field { display:grid; gap:.35rem; font-size:.78rem; font-weight:600; }
.field input { min-height:38px; border:1px solid var(--border-color,#dfe3e8); border-radius:8px; padding:.45rem .65rem; background:var(--control-bg,transparent); color:inherit; }
.filter-action { display:flex; align-items:end; }
.edge-button { min-height:38px; border:1px solid var(--border-color,#dfe3e8); border-radius:8px; padding:.45rem .8rem; background:var(--control-bg,transparent); color:inherit; font-weight:600; }
.edge-button.primary { width:100%; background:var(--primary,#171717); color:var(--primary-foreground,#fff); border-color:transparent; }
.edge-button:disabled { opacity:.55; cursor:not-allowed; }
.metric-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:.75rem; }
.metric-grid.compact { margin-top:.75rem; }
.metric-card { border:1px solid var(--border-color,#dfe3e8); border-radius:10px; padding:.8rem; display:grid; gap:.3rem; }
.metric-card span { font-size:.76rem; opacity:.7; } .metric-card strong { font-size:1.05rem; }
.table-wrap { overflow:auto; margin-top:.75rem; } table { width:100%; border-collapse:collapse; min-width:760px; } th,td { padding:.65rem; border-bottom:1px solid var(--border-color,#e8ebee); text-align:left; vertical-align:top; } th { font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; } .num { text-align:right; font-variant-numeric:tabular-nums; } td small { display:block; opacity:.65; margin-top:.1rem; }
.warning-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:.75rem; margin-top:.75rem; } .warning-card { border:1px solid var(--border-color,#dfe3e8); border-radius:10px; padding:.8rem; display:grid; gap:.3rem; }
.pill { display:inline-block; border-radius:999px; padding:.2rem .55rem; font-size:.74rem; font-weight:700; } .pill.risk { background:rgba(220,38,38,.12); } .pill.ok { background:rgba(22,163,74,.12); }
.empty { padding:.8rem 0; opacity:.72; } .alert.error,.planning-fallback { border:1px solid rgba(220,38,38,.35); border-radius:10px; padding:1rem; } .planning-fallback { display:grid; gap:.35rem; }
@media (max-width:720px) { .planning-header,.panel-heading { flex-direction:column; } .header-actions { width:100%; flex-wrap:wrap; } }
</style>
