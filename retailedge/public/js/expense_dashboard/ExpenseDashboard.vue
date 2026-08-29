<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Expenses Dashboard could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Expenses Dashboard"
		:tenantName="tenantName || filters.company"
		:branchName="filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/expense-overview"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeDashboardShell
			title="Expenses Dashboard"
			eyebrow="Spend Intelligence"
			subtitle="Understand where money is going, what is driving spend, who or which branch is driving it, and whether spending patterns need attention."
			:summary="headlineSummary"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="capabilities.can_export"
			:printEnabled="capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			loadingMessage="Building expense insights…"
			@retry="fetchData"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #filters>
				<div class="expense-dashboard-filters">
					<label class="edge-field"><span class="edge-field-label">From Date</span><input v-model="filters.from_date" type="date" class="edge-input" /></label>
					<label class="edge-field"><span class="edge-field-label">To Date</span><input v-model="filters.to_date" type="date" class="edge-input" /></label>
					<button class="edge-button edge-button--primary" type="button" :disabled="loading || !filters.company" @click="fetchData">{{ loading ? "Refreshing…" : "Apply / Refresh" }}</button>
				</div>
			</template>

			<EdgeDashboardGrid minColumnWidth="21rem">
				<EdgeDashboardSection title="Spend Trend" description="Current selected period compared with the immediately previous equal-length period.">
					<div class="expense-trend-grid">
						<div class="expense-metric"><span>Current period</span><strong>{{ money(comparison.current_total) }}</strong></div>
						<div class="expense-metric"><span>Previous period</span><strong>{{ money(comparison.previous_total) }}</strong></div>
						<div class="expense-metric"><span>Change</span><strong>{{ comparison.change_pct == null ? "No prior baseline" : percent(comparison.change_pct) }}</strong></div>
						<div class="expense-metric"><span>Daily spend</span><strong>{{ money(comparison.current_daily_average) }}</strong></div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="MTD & Calendar YTD" :description="periodContextDescription">
					<div class="expense-period-grid">
						<div class="expense-period-card">
							<span>{{ periodContext.mtd?.label || "Month to Date" }}</span>
							<strong>{{ money(periodContext.mtd?.total_expenses) }}</strong>
							<small>{{ periodContext.mtd?.expense_count || 0 }} expenses · avg {{ money(periodContext.mtd?.average_expense) }}</small>
							<small>{{ periodContext.mtd?.from_date || "—" }} to {{ periodContext.mtd?.to_date || "—" }}</small>
						</div>
						<div class="expense-period-card">
							<span>{{ periodContext.ytd?.label || "Calendar Year to Date" }}</span>
							<strong>{{ money(periodContext.ytd?.total_expenses) }}</strong>
							<small>{{ periodContext.ytd?.expense_count || 0 }} expenses · avg {{ money(periodContext.ytd?.average_expense) }}</small>
							<small>{{ periodContext.ytd?.from_date || "—" }} to {{ periodContext.ytd?.to_date || "—" }}</small>
						</div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Budget & Burn Rate" :description="budgetDescription">
					<div v-if="budgetInsight.available" class="expense-budget-grid">
						<div class="expense-metric"><span>Budget for period</span><strong>{{ money(budgetInsight.target_amount) }}</strong></div>
						<div class="expense-metric"><span>Actual spend</span><strong>{{ money(budgetInsight.actual_amount) }}</strong></div>
						<div class="expense-metric"><span>Budget used</span><strong>{{ percent(budgetInsight.used_pct) }}</strong></div>
						<div class="expense-metric"><span>Remaining</span><strong>{{ money(budgetInsight.remaining_amount) }}</strong></div>
						<div class="expense-metric"><span>Projected period spend</span><strong>{{ money(budgetInsight.projected_period_spend) }}</strong></div>
						<div class="expense-metric"><span>Projected variance</span><strong>{{ money(budgetInsight.projected_variance) }}</strong></div>
					</div>
					<div v-else class="expense-budget-empty">
						<strong>Budget insight unavailable</strong>
						<span>{{ budgetInsight.reason || "Configure a submitted ERPNext Budget and the required account/cost-centre mappings to compare actual spending with plan." }}</span>
					</div>
					<div v-if="budgetInsight.available" class="expense-budget-status" :class="budgetStatusClass">
						<strong>{{ budgetStatusLabel }}</strong>
						<span>{{ budgetStatusDetail }}</span>
					</div>
					<div v-if="budgetInsight.ambiguous_category_count" class="expense-budget-warning">
						{{ budgetInsight.ambiguous_category_count }} category mapping{{ budgetInsight.ambiguous_category_count === 1 ? " is" : "s are" }} shared across the same account/cost-centre budget. RetailEdge does not split those targets arbitrarily.
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-if="attention.length || budgetAttention.length" title="Attention Required" description="Signals that deserve review; budget warnings use submitted ERPNext Budget targets where available.">
					<div class="expense-attention-list">
						<div v-for="item in budgetAttention" :key="item.label" class="expense-attention-item expense-attention-item--static">
							<span><strong>{{ item.label }}</strong><small>{{ item.detail }}</small></span>
							<strong>{{ item.value }}</strong>
						</div>
						<button v-for="item in attention" :key="item.label" class="expense-attention-item" type="button" @click="openRoute(item.route)">
							<span><strong>{{ item.label }}</strong><small v-if="item.detail">{{ item.detail }}</small></span>
							<strong>{{ formatValue(item.value, item.datatype) }}</strong>
						</button>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-for="dimension in visibleDimensions" :key="dimension.key" :title="dimension.title" :description="dimension.description">
					<div class="expense-ranking">
						<div v-for="row in dimension.rows" :key="row.label" class="expense-ranking-row">
							<div class="expense-ranking-label"><strong>{{ row.label }}</strong><small>{{ row.count }} expense{{ row.count === 1 ? "" : "s" }} · {{ percent(row.share_pct) }}</small></div>
							<strong>{{ money(row.amount) }}</strong>
						</div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection v-if="budgetedCategories.length" title="Budget by Expense Category" description="Only categories with an unambiguous account/cost-centre budget mapping receive a category target.">
					<div class="expense-ranking">
						<div v-for="row in budgetedCategories" :key="row.category" class="expense-ranking-row">
							<div class="expense-ranking-label">
								<strong>{{ row.category }}</strong>
								<small v-if="row.ambiguous">Shared budget mapping — category target not allocated</small>
								<small v-else>{{ percent(row.used_pct) }} used · {{ row.cost_center }}</small>
							</div>
							<strong v-if="row.target != null">{{ money(row.actual) }} / {{ money(row.target) }}</strong>
							<strong v-else>{{ money(row.actual) }}</strong>
						</div>
					</div>
				</EdgeDashboardSection>

				<EdgeDashboardSection title="Recent Expenses" description="Latest rows from the same permission-aware Expense Register dataset." span="2">
					<div class="expense-recent-list">
						<button v-for="row in recentExpenses" :key="row.name" class="expense-recent-row" type="button" @click="openExpense(row.name)">
							<span><strong>{{ row.expense_category || "Uncategorised" }}</strong><small>{{ row.expense_date }} · {{ row.branch || "No branch" }}<template v-if="row.cashier"> · {{ row.cashier }}</template></small></span>
							<strong>{{ money(row.amount) }}</strong>
						</button>
					</div>
					<div class="expense-actions"><button class="edge-button edge-button--secondary" type="button" @click="openRoute('/app/expense-register')">Open Expense Register</button><button class="edge-button edge-button--secondary" type="button" @click="openRoute('/app/expense-review')">Open Expense Review</button></div>
				</EdgeDashboardSection>
			</EdgeDashboardGrid>

			<div class="expense-budget-note">{{ budgetInsight.enforcement_note || metadata.budget_note || "Budget compliance requires an explicit budget or target and is not inferred from spending history alone." }}</div>
		</EdgeDashboardShell>
	</EdgeAppShell>
</template>

<script>
import { defaultDashboardExportOptions, exportDashboard, getDashboardCapabilities, printDashboard } from "../retailedge_dashboard_actions";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeDashboardShell", "EdgeDashboardGrid", "EdgeDashboardSection"];
const DASHBOARD_KEY = "expense-overview";
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) { return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject })); }
function errorMessage(error, fallback) { return error?.message || error?.exc || error?.exception || fallback; }

export default {
	name: "ExpenseDashboard",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], metadataLoading: true, loading: false, error: "",
			exportBusy: false, printBusy: false, capabilities: { can_view: true, can_print: false, can_export: false },
			exportOptions: defaultDashboardExportOptions(), headlineSummary: [], attention: [], breakdowns: {}, comparison: {}, recentExpenses: [], metadata: {},
			budgetInsight: { available: false, reason: "", category_targets: [] }, periodContext: { mtd: {}, ytd: {}, metadata: {} }, menuItems: [], tenantName: "", userName: "",
			filters: { company: "", branch: "", from_date: "", to_date: "", expense_category: "", expense_status: "" },
		};
	},
	computed: {
		visibleDimensions() {
			const defs = [
				["category", "What are we spending on?", "Top expense categories by amount and share of spend."],
				["branch", "Where are we spending?", "Branches driving the selected-period expense total."],
				["cashier", "Who is spending?", "Cashier/user concentration where your permissions allow that view."],
				["funding_source", "How are expenses funded?", "Payment accounts used to fund expenses; visible only with Account read permission."],
				["expense_account", "Which expense accounts?", "Accounting classification behind recorded expenses."],
				["cost_center", "Which cost centres?", "Cost-centre concentration behind recorded expenses."],
			];
			return defs.map(([key, title, description]) => ({ key, title, description, rows: this.breakdowns[key] || [] })).filter((item) => item.rows.length);
		},
		budgetedCategories() { return (this.budgetInsight.category_targets || []).filter((row) => row.actual || row.target || row.ambiguous).slice(0, 10); },
		periodContextDescription() {
			const anchor = this.periodContext.anchor_date || this.filters.to_date || "the selected To Date";
			return `Month-to-date and calendar-year-to-date spend as of ${anchor}, using the same branch/category/status permissions as Expense Register.`;
		},
		budgetDescription() {
			if (!this.budgetInsight.available) return "Native ERPNext Budget targets are shown only when your permissions and account/cost-centre mappings allow a reliable comparison.";
			return `${this.budgetInsight.budget_count || 0} submitted ERPNext budget${this.budgetInsight.budget_count === 1 ? "" : "s"} matched this period. Projection uses current daily burn rate across the selected period.`;
		},
		budgetStatusLabel() {
			if (this.budgetInsight.over_budget) return "Over budget";
			if (this.budgetInsight.projected_over_budget) return "Projected to exceed budget";
			return "Within current budget trajectory";
		},
		budgetStatusDetail() {
			if (this.budgetInsight.over_budget) return `Actual spend has exceeded the selected-period budget by ${this.money(Math.abs(this.budgetInsight.remaining_amount || 0))}.`;
			if (this.budgetInsight.projected_over_budget) return `At the current daily spend rate, projected spend is ${this.money(this.budgetInsight.projected_period_spend)}.`;
			return `${this.money(this.budgetInsight.remaining_amount)} remains against the selected-period budget.`;
		},
		budgetStatusClass() {
			if (this.budgetInsight.over_budget) return "expense-budget-status--danger";
			if (this.budgetInsight.projected_over_budget) return "expense-budget-status--warning";
			return "expense-budget-status--ok";
		},
		budgetAttention() {
			const items = [];
			if (this.budgetInsight.over_budget) items.push({ label: "Selected-period expense budget has been exceeded", detail: "Actual vs submitted ERPNext Budget", value: this.money(Math.abs(this.budgetInsight.remaining_amount || 0)) + " over" });
			else if (this.budgetInsight.projected_over_budget) items.push({ label: "Current burn rate projects an overspend", detail: "Projection is informational and does not change ERPNext budget enforcement", value: this.money(Math.abs(this.budgetInsight.projected_variance || 0)) + " projected over" });
			return items;
		},
	},
	created() { const components = runtimeComponents(); this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]); this.edgeUIValid = this.missingComponents.length === 0; },
	mounted() { this.fetchMetadata(); },
	methods: {
		async fetchMetadata() {
			this.metadataLoading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function" ? window.retailedgeGetBusinessHubContext() : callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod("retailedge.expense_dashboard.get_expense_dashboard_context"), navigationPromise]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) }; this.capabilities = context.capabilities || this.capabilities;
				this.tenantName = context.tenant_name || this.filters.company || ""; this.userName = context.user_name || ""; this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) { this.error = errorMessage(error, "Failed to load Expenses Dashboard controls."); }
			finally { this.metadataLoading = false; }
		},
		async fetchData() {
			if (!this.filters.company) return; this.loading = true; this.error = "";
			try {
				const [result, budgetInsight, periodContext, capabilities] = await Promise.all([
					callMethod("retailedge.expense_dashboard.get_expense_dashboard_data", { filters: this.filters }),
					callMethod("retailedge.expense_budget_api.get_expense_budget_insight", { filters: this.filters }),
					callMethod("retailedge.expense_period_context.get_expense_period_context", { filters: this.filters }),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				this.headlineSummary = result.headline_summary || []; this.attention = result.attention || []; this.breakdowns = result.breakdowns || {};
				this.comparison = result.comparison || {}; this.recentExpenses = result.recent_expenses || []; this.metadata = result.metadata || {};
				this.budgetInsight = budgetInsight || { available: false, reason: "Budget insight unavailable.", category_targets: [] };
				this.periodContext = periodContext || { mtd: {}, ytd: {}, metadata: {} }; this.capabilities = capabilities || this.capabilities;
			} catch (error) { this.error = errorMessage(error, "Expenses Dashboard failed to load."); }
			finally { this.loading = false; }
		},
		async handleExport(options) { if (!this.capabilities.can_export) return; this.exportBusy = true; try { await exportDashboard(DASHBOARD_KEY, this.filters, options); } finally { this.exportBusy = false; } },
		async handlePrint() { if (!this.capabilities.can_print) return; this.printBusy = true; try { await printDashboard(DASHBOARD_KEY, this.filters); } finally { this.printBusy = false; } },
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`; return item.target || ""; },
		handleNavigation(route) { const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route); if (!item) return; if (item.target_type === "Page") frappe.set_route(item.target); else if (item.target_type === "Report") frappe.set_route("query-report", item.target); else if (item.target_type === "DocType") frappe.set_route("List", item.target); },
		openRoute(route) { if (route) window.location.assign(route); },
		openExpense(name) { if (name) frappe.set_route("Form", "RetailEdge Cashier Expense", name); },
		money(value) { try { return frappe.format(value || 0, { fieldtype: "Currency" }); } catch (_error) { return value ?? "—"; } },
		percent(value) { if (value == null) return "—"; return `${Number(value).toFixed(1)}%`; },
		formatValue(value, datatype) { if (datatype === "Percent") return this.percent(value); try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value ?? "—"; } },
	},
};
</script>

<style scoped>
.expense-dashboard-filters { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; align-items: end; }
.expense-trend-grid, .expense-budget-grid, .expense-period-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
.expense-metric, .expense-period-card { display: grid; gap: 4px; padding: 12px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
.expense-metric span, .expense-period-card span, .expense-period-card small, .expense-ranking-row small, .expense-recent-row small, .expense-attention-item small, .expense-budget-empty span { color: var(--edge-text-muted); font-size: 12px; }
.expense-attention-list, .expense-ranking, .expense-recent-list { display: grid; gap: 8px; }
.expense-attention-item, .expense-recent-row { display: flex; justify-content: space-between; gap: 14px; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); color: var(--edge-text); text-align: left; cursor: pointer; }
.expense-attention-item--static { cursor: default; }
.expense-attention-item span, .expense-recent-row span, .expense-ranking-label, .expense-budget-empty { display: grid; gap: 3px; }
.expense-ranking-row { display: flex; justify-content: space-between; gap: 14px; align-items: center; padding: 10px 0; border-bottom: 1px solid var(--edge-border); }
.expense-ranking-row:last-child { border-bottom: 0; }
.expense-actions { display: flex; gap: 10px; margin-top: 14px; flex-wrap: wrap; }
.expense-budget-status, .expense-budget-warning, .expense-budget-empty { margin-top: 12px; padding: 10px 12px; border: 1px solid var(--edge-border); border-radius: 8px; }
.expense-budget-status { display: grid; gap: 3px; }
.expense-budget-status--danger { border-color: var(--red-300, var(--edge-border)); }
.expense-budget-status--warning, .expense-budget-warning { border-color: var(--orange-300, var(--edge-border)); }
.expense-budget-status--ok { border-color: var(--green-300, var(--edge-border)); }
.expense-budget-warning { font-size: 12px; color: var(--edge-text-muted); }
.expense-budget-note { margin-top: 14px; padding: 12px 14px; border: 1px solid var(--edge-border); border-radius: 8px; color: var(--edge-text-muted); background: var(--edge-surface); font-size: 13px; }
@media (max-width: 720px) { .expense-dashboard-filters, .expense-trend-grid, .expense-budget-grid, .expense-period-grid { grid-template-columns: 1fr; } }
</style>
