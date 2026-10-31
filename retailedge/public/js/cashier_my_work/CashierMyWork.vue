<template>
	<div v-if="!edgeUIValid" class="cashier-work-fallback">
		<strong>My Work could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		title="ProcessEdge Retail"
		subtitle="Structured for Scale."
		:tenantName="companyLabel || company"
		:branchName="branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/cashier-my-work"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<template #brand>
			<img
				v-if="productLogo && !productLogoFailed"
				class="cashier-work-brand-logo"
				:src="productLogo"
				alt="ProcessEdge Retail"
				@error="productLogoFailed = true"
			/>
			<span v-else class="cashier-work-brand-fallback" aria-hidden="true">R</span>
		</template>

		<div class="cashier-work-page">
			<section class="cashier-work-hero">
				<div>
					<div class="cashier-work-eyebrow" role="heading" aria-level="1">My Work</div>
					<h2>{{ greeting }}</h2>
					<p>{{ dateLabel }} · {{ branch || "Current branch" }}</p>
				</div>
				<div class="cashier-work-hero-actions">
					<span v-if="isToday" class="cashier-work-shift-pill" :class="{ 'is-open': shift.open }">
						{{ shift.open ? "Shift open" : "No open shift" }}
					</span>
					<button v-if="startPosItem" class="edge-button edge-button--primary" type="button" @click="openItem(startPosItem)">
						Start POS
					</button>
				</div>
			</section>

			<section class="cashier-work-date-bar" aria-label="Choose work date">
				<EdgeInput
					v-model="selectedDate"
					type="date"
					label="Work date"
					:max="today"
					:disabled="loading"
					@change="changeDate"
				/>
				<div class="cashier-work-date-actions">
					<span>{{ isToday ? "Showing today" : "Showing historical activity" }}</span>
					<button v-if="!isToday && today" class="edge-button edge-button--secondary" type="button" :disabled="loading" @click="showToday">
						Today
					</button>
				</div>
			</section>

			<div v-if="loading" class="cashier-work-state">Loading your work…</div>
			<div v-else-if="error" class="cashier-work-state cashier-work-error">
				<strong>Unable to load your work.</strong>
				<span>{{ error }}</span>
				<button class="edge-button edge-button--secondary" type="button" @click="load">Retry</button>
			</div>
			<template v-else>
				<section class="cashier-work-summary" :aria-label="`${dateLabel} summary`">
					<article class="cashier-work-card">
						<span>Sales</span>
						<strong>{{ money(summary.gross_sales) }}</strong>
						<small>{{ summary.sales_count || 0 }} sale{{ Number(summary.sales_count || 0) === 1 ? "" : "s" }}</small>
					</article>
					<article class="cashier-work-card">
						<span>Payments recorded</span>
						<strong>{{ money(summary.payments_total) }}</strong>
						<small>Across your sales for this day</small>
					</article>
					<article class="cashier-work-card">
						<span>Returns</span>
						<strong>{{ money(summary.returns_total) }}</strong>
						<small>{{ summary.returns_count || 0 }} return{{ Number(summary.returns_count || 0) === 1 ? "" : "s" }}</small>
					</article>
					<article class="cashier-work-card">
						<span>Net sales</span>
						<strong>{{ money(summary.net_sales) }}</strong>
						<small>{{ summary.transaction_count || 0 }} transaction{{ Number(summary.transaction_count || 0) === 1 ? "" : "s" }}</small>
					</article>
				</section>

				<section class="cashier-work-grid" :class="{ 'cashier-work-grid--history': !isToday }">
					<article v-if="isToday" class="cashier-work-panel">
						<div class="cashier-work-panel-heading">
							<div>
								<div class="cashier-work-eyebrow">Current shift</div>
								<h3>{{ shift.open ? (shift.opening_shift || "Open shift") : "No open POS shift" }}</h3>
							</div>
							<span v-if="shift.pos_profile" class="cashier-work-muted">{{ shift.pos_profile }}</span>
						</div>
						<div v-if="shift.open" class="cashier-work-metrics">
							<div><span>Opening cash</span><strong>{{ money(shift.opening_cash) }}</strong></div>
							<div><span>Cash sales</span><strong>{{ money(shift.cash_sales) }}</strong></div>
							<div><span>Expenses</span><strong>{{ money(shift.prior_expenses) }}</strong></div>
							<div><span>Available cash</span><strong>{{ money(shift.available_cash) }}</strong></div>
						</div>
						<div v-else class="cashier-work-empty compact">
							<p>Open your POS shift to start selling and see live shift totals here.</p>
							<button v-if="startPosItem" class="edge-button edge-button--primary" type="button" @click="openItem(startPosItem)">Start POS</button>
						</div>
						<p v-if="shift.message" class="cashier-work-note">{{ shift.message }}</p>
					</article>

					<article class="cashier-work-panel">
						<div class="cashier-work-panel-heading">
							<div>
								<div class="cashier-work-eyebrow">Payments</div>
								<h3>Payment mix</h3>
							</div>
						</div>
						<div v-if="paymentBreakdown.length" class="cashier-work-payment-list">
							<div v-for="payment in paymentBreakdown" :key="payment.mode_of_payment">
								<span>{{ payment.mode_of_payment }}</span>
								<strong>{{ money(payment.amount) }}</strong>
							</div>
						</div>
						<div v-else class="cashier-work-empty compact">No payments were recorded on your sales for this day.</div>
					</article>
				</section>

				<section class="cashier-work-panel">
					<div class="cashier-work-panel-heading">
						<div>
							<div class="cashier-work-eyebrow">Work activity</div>
							<h3>My sales and returns</h3>
							<p>Only transactions recorded by your account are shown.</p>
						</div>
						<span v-if="activityTruncated" class="cashier-work-muted">Showing latest {{ activityLimit }} of {{ activityTotal }}</span>
					</div>
					<div v-if="recentActivity.length" class="cashier-work-table-wrap">
						<table class="cashier-work-table">
							<thead>
								<tr><th>Time</th><th>Reference</th><th>Type</th><th>Customer</th><th>Total</th><th>Paid</th><th>Status</th></tr>
							</thead>
							<tbody>
								<tr v-for="row in recentActivity" :key="row.reference">
									<td>{{ timeLabel(row.posting_time) }}</td>
									<td>{{ row.reference }}</td>
									<td><span class="cashier-work-type" :class="{ 'is-return': row.type === 'Return' }">{{ row.type }}</span></td>
									<td>{{ row.customer || "—" }}</td>
									<td>{{ money(row.total) }}</td>
									<td>{{ money(row.paid_amount) }}</td>
									<td>{{ row.status || "Submitted" }}</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-else class="cashier-work-empty">
						<strong>No activity for this day.</strong>
						<p>{{ emptyMessage || "Your sales and returns for the selected day will appear here." }}</p>
						<button v-if="isToday && startPosItem" class="edge-button edge-button--primary" type="button" @click="openItem(startPosItem)">Start POS</button>
					</div>
				</section>
			</template>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeInput"];
const DEFAULT_PRODUCT_LOGO = "/assets/retailedge/images/processedge_retail/processedge-retail-mark.svg";

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

function shellIdentity() {
	return frappe.boot?.edgesuite_ui_identity?.retailedge || frappe.boot?.retailedge_ui_identity || {};
}

export default {
	name: "CashierMyWork",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			loading: true,
			error: "",
			company: "",
			companyLabel: "",
			branch: "",
			userName: "",
			currency: "",
			date: "",
			today: "",
			selectedDate: "",
			isToday: true,
			menuItems: [],
			summary: {},
			shift: {},
			paymentBreakdown: [],
			recentActivity: [],
			activityTotal: 0,
			activityLimit: 0,
			activityTruncated: false,
			emptyMessage: "",
			productLogo: shellIdentity().product_logo || DEFAULT_PRODUCT_LOGO,
			productLogoFailed: false,
		};
	},
	computed: {
		greeting() {
			if (this.isToday) return this.userName ? `Today, ${this.userName}` : "Today at a glance";
			return this.userName ? `Work for ${this.userName}` : "Historical work";
		},
		dateLabel() {
			if (!this.date) return this.isToday ? "Today" : "Selected day";
			try {
				return new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long", year: "numeric" }).format(new Date(`${this.date}T00:00:00`));
			} catch (_error) {
				return this.date;
			}
		},
		startPosItem() {
			return this.menuItems.flatMap((group) => group.items || []).find((item) => item.label === "Start POS" || item.target === "/pos/") || null;
		},
	},
	created() {
		const components = runtimeComponents();
		this.edgeUIValid = REQUIRED_COMPONENTS.every((name) => Boolean(components[name]));
	},
	mounted() {
		this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [activity, navigation] = await Promise.all([
					callMethod("retailedge.cashier_self_service.get_my_cashier_activity", {
						work_date: this.selectedDate,
					}),
					navigationPromise,
				]);
				const context = navigation?.context || {};
				const identity = shellIdentity();
				this.productLogo = identity.product_logo || DEFAULT_PRODUCT_LOGO;
				this.productLogoFailed = false;
				this.company = activity.company || context.company || "";
				this.companyLabel = context.company_label || this.company;
				this.branch = activity.branch || context.branch || "";
				this.userName = context.user_name || activity.user || "";
				this.currency = activity.currency || context.company_currency || "";
				this.date = activity.date || "";
				this.today = activity.today || this.date || "";
				this.selectedDate = this.date;
				this.isToday = activity.is_today !== false;
				this.summary = activity.summary || {};
				this.shift = activity.shift || {};
				this.paymentBreakdown = Array.isArray(activity.payment_breakdown) ? activity.payment_breakdown : [];
				this.recentActivity = Array.isArray(activity.recent_activity) ? activity.recent_activity : [];
				this.activityTotal = Number(activity.activity_total || this.recentActivity.length || 0);
				this.activityLimit = Number(activity.activity_limit || this.recentActivity.length || 0);
				this.activityTruncated = Boolean(activity.activity_truncated);
				this.emptyMessage = activity.empty_message || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
			} catch (error) {
				this.error = error?.message || error?.exc || "My Work could not be loaded.";
			} finally {
				this.loading = false;
			}
		},
		changeDate(value) {
			if (!value || value === this.date) return;
			this.selectedDate = value;
			this.load();
		},
		showToday() {
			if (!this.today) return;
			this.selectedDate = this.today;
			this.load();
		},
		mapNavigationGroups(groups) {
			return (groups || [])
				.map((group) => ({
					...group,
					items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
				}))
				.filter((group) => group.items.length);
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "URL") return item.target || "";
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (item) this.openItem(item);
		},
		openItem(item) {
			if (!item) return;
			if (item.target_type === "URL" && item.target) {
				if (item.target === "/pos/") {
					window.open(item.target, "_blank", "noopener,noreferrer");
					return;
				}
				window.location.assign(item.target);
			}
			else if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
		},
		money(value) {
			const amount = Number(value || 0);
			try {
				if (this.currency) return new Intl.NumberFormat(undefined, { style: "currency", currency: this.currency, maximumFractionDigits: 2 }).format(amount);
			} catch (_error) {
				// Fall through to a numeric amount when currency metadata is unavailable.
			}
			return new Intl.NumberFormat(undefined, { maximumFractionDigits: 2 }).format(amount);
		},
		timeLabel(value) {
			if (!value) return "—";
			return String(value).slice(0, 5);
		},
	},
};
</script>

<style scoped>
.cashier-work-page { display: grid; gap: 1rem; padding: 1.25rem; }
.cashier-work-hero,
.cashier-work-panel,
.cashier-work-card,
.cashier-work-state,
.cashier-work-date-bar { border: 1px solid var(--border-color); background: var(--card-bg, var(--fg-color)); border-radius: var(--border-radius-lg, 12px); }
.cashier-work-hero { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; padding: 1.25rem; }
.cashier-work-hero h2, .cashier-work-panel h3 { margin: 0; color: var(--heading-color, var(--text-color)); }
.cashier-work-hero p, .cashier-work-panel-heading p { margin: .35rem 0 0; color: var(--text-muted); }
.cashier-work-eyebrow { font-size: .75rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: var(--text-muted); margin-bottom: .25rem; }
.cashier-work-hero-actions { display: flex; align-items: center; gap: .65rem; flex-wrap: wrap; justify-content: flex-end; }
.cashier-work-shift-pill, .cashier-work-type { border: 1px solid var(--border-color); border-radius: 999px; padding: .35rem .6rem; font-size: .8rem; font-weight: 600; }
.cashier-work-shift-pill.is-open { background: var(--green-50, var(--subtle-fg)); }
.cashier-work-date-bar { display: flex; align-items: end; justify-content: space-between; gap: 1rem; padding: .85rem 1rem; }
.cashier-work-date-bar :deep(.edge-input) { width: min(18rem, 100%); }
.cashier-work-date-actions { display: flex; align-items: center; justify-content: flex-end; gap: .75rem; color: var(--text-muted); font-size: .82rem; }
.cashier-work-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .85rem; }
.cashier-work-card { display: grid; gap: .25rem; padding: 1rem; min-width: 0; }
.cashier-work-card > span, .cashier-work-metrics span, .cashier-work-payment-list span { color: var(--text-muted); font-size: .82rem; }
.cashier-work-card strong { font-size: 1.35rem; overflow: hidden; text-overflow: ellipsis; }
.cashier-work-card small { color: var(--text-muted); }
.cashier-work-grid { display: grid; grid-template-columns: 1.25fr .75fr; gap: 1rem; }
.cashier-work-grid--history { grid-template-columns: 1fr; }
.cashier-work-panel { padding: 1.1rem; min-width: 0; }
.cashier-work-panel-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.cashier-work-muted, .cashier-work-note { color: var(--text-muted); font-size: .82rem; }
.cashier-work-note { margin: .85rem 0 0; }
.cashier-work-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .75rem; margin-top: 1rem; }
.cashier-work-metrics > div, .cashier-work-payment-list > div { display: flex; justify-content: space-between; gap: .75rem; padding: .75rem; border: 1px solid var(--border-color); border-radius: var(--border-radius, 8px); }
.cashier-work-payment-list { display: grid; gap: .55rem; margin-top: 1rem; }
.cashier-work-table-wrap { overflow-x: auto; margin-top: 1rem; }
.cashier-work-table { width: 100%; border-collapse: collapse; }
.cashier-work-table th, .cashier-work-table td { padding: .7rem; text-align: left; white-space: nowrap; border-bottom: 1px solid var(--border-color); }
.cashier-work-table th { color: var(--text-muted); font-size: .78rem; font-weight: 600; }
.cashier-work-type.is-return { background: var(--red-50, var(--subtle-fg)); }
.cashier-work-empty { display: grid; justify-items: start; gap: .5rem; padding: 1.5rem 0 .5rem; color: var(--text-muted); }
.cashier-work-empty.compact { padding: 1rem 0 0; }
.cashier-work-empty p { margin: 0; }
.cashier-work-state { display: grid; gap: .65rem; justify-items: start; padding: 1.25rem; color: var(--text-muted); }
.cashier-work-error { color: var(--red-600, var(--text-color)); }
.cashier-work-brand-logo { width: 30px; height: 30px; object-fit: contain; display: block; border-radius: 6px; }
.cashier-work-brand-fallback { display: grid; place-items: center; width: 30px; height: 30px; border: 1px solid var(--border-color); border-radius: 7px; font-weight: 700; }
.cashier-work-fallback { display: grid; gap: .5rem; padding: 1.5rem; }
@media (max-width: 900px) {
	.cashier-work-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
	.cashier-work-grid { grid-template-columns: 1fr; }
}
@media (max-width: 600px) {
	.cashier-work-page { padding: .75rem; }
	.cashier-work-hero { flex-direction: column; align-items: stretch; }
	.cashier-work-hero-actions { justify-content: flex-start; }
	.cashier-work-date-bar { align-items: stretch; flex-direction: column; }
	.cashier-work-date-bar :deep(.edge-input) { width: 100%; }
	.cashier-work-date-actions { justify-content: space-between; }
	.cashier-work-summary { grid-template-columns: 1fr; }
	.cashier-work-metrics { grid-template-columns: 1fr; }
}
</style>