<template>
	<EdgeAppShell
		product="retailedge"
		title="ProcessEdge Retail"
		subtitle="Structured for Scale."
		:tenantName="context.company_label || context.company"
		:branchName="context.branch"
		:userName="context.user_name"
		:menuItems="menuItems"
		activeRoute="/app/reports-centre"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="Reports Centre"
					subtitle="Find the right operational, management or financial view without searching across workspaces."
				/>
			</template>

			<EdgeLoadingState v-if="loading" message="Loading permitted reports..." :skeleton="true" />
			<EdgeErrorState
				v-else-if="error"
				title="Reports Centre unavailable"
				:message="error"
				@retry="load"
			/>

			<div v-else class="reports-centre">
				<section class="reports-centre-hero">
					<div>
						<p class="reports-centre-eyebrow">Business reporting</p>
						<h2>One place for trusted reports</h2>
						<p>Open operational and management views already governed by RetailEdge and ERPNext permissions. Reports Centre does not create a second reporting truth.</p>
					</div>
					<div class="reports-centre-count">
						<strong>{{ totalReports }}</strong>
						<span>available reports</span>
					</div>
				</section>

				<section class="reports-centre-search" aria-label="Search reports">
					<label>
						<span>Find a report</span>
						<input
							v-model.trim="query"
							type="search"
							placeholder="Search sales, cash, stock, expenses, receivables..."
							autocomplete="off"
						/>
					</label>
					<div class="reports-centre-context">
						<span v-if="context.company_label || context.company">{{ context.company_label || context.company }}</span>
						<span v-if="context.branch">{{ context.branch }}</span>
					</div>
				</section>

				<div v-if="filteredGroups.length" class="reports-centre-groups">
					<section v-for="group in filteredGroups" :key="group.key" class="reports-centre-group">
						<header>
							<span class="reports-centre-group-icon"><EdgeIcon :name="displayIcon(group.icon)" size="sm" /></span>
							<div>
								<h3>{{ group.label }}</h3>
								<p>{{ group.description }}</p>
							</div>
							<span class="reports-centre-group-count">{{ group.items.length }}</span>
						</header>

						<div class="reports-centre-grid">
							<button
								v-for="item in group.items"
								:key="`${item.target_type}:${item.target}`"
								type="button"
								class="reports-centre-card"
								@click="openReport(item)"
							>
								<span class="reports-centre-card-icon"><EdgeIcon :name="displayIcon(item.icon)" size="sm" /></span>
								<span class="reports-centre-card-copy">
									<strong>{{ item.label }}</strong>
									<small>{{ item.description }}</small>
									<em v-if="item.native_desk">ERPNext financial report</em>
								</span>
								<span class="reports-centre-card-open">Open</span>
							</button>
						</div>
					</section>
				</div>

				<EdgeEmptyState
					v-else
					title="No reports match"
					description="Try a broader search term or clear the search."
					icon="search"
				/>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgePageLayout",
	"EdgePageHeader",
	"EdgeIcon",
	"EdgeEmptyState",
	"EdgeLoadingState",
	"EdgeErrorState",
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

function normalizeSearch(value) {
	return String(value || "")
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, " ")
		.trim();
}

export default {
	name: "ReportsCentre",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			loading: true,
			error: "",
			query: "",
			groups: [],
			menuItems: [],
			canUseNativeDesk: false,
			context: {
				company: "",
				company_label: "",
				branch: "",
				user_name: "",
			},
		};
	},
	computed: {
		totalReports() {
			return this.groups.reduce((total, group) => total + (group.items || []).length, 0);
		},
		filteredGroups() {
			const query = normalizeSearch(this.query);
			if (!query) return this.groups;
			const tokens = query.split(/\s+/).filter(Boolean);
			return this.groups
				.map((group) => ({
					...group,
					items: (group.items || []).filter((item) => {
						const haystack = normalizeSearch([
							group.label,
							item.label,
							item.description,
							...(item.tags || []),
						].join(" "));
						return tokens.every((token) => haystack.includes(token));
					}),
				}))
				.filter((group) => group.items.length);
		},
	},
	created() {
		const components = runtimeComponents();
		const missing = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		if (missing.length) {
			this.error = `Required EdgeSuite UI components are unavailable: ${missing.join(", ")}`;
			this.loading = false;
		}
	},
	mounted() {
		if (!this.error) this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.report_center.get_reports_centre_context");
				this.groups = result.groups || [];
				this.context = { ...this.context, ...(result.context || {}) };
				this.canUseNativeDesk = Boolean(result.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(result.navigation_groups || []);
			} catch (error) {
				this.groups = [];
				this.error =
					window.retailedge?.userErrorMessage?.(error, "Reports Centre could not be loaded.")
					|| error?.message
					|| "Reports Centre could not be loaded.";
			} finally {
				this.loading = false;
			}
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || [])
					.map((item) => ({ ...item, route: this.routeForItem(item) }))
					.filter((item) => item.route),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") {
				return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			}
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems
				.flatMap((group) => group.items || [])
				.find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
		openReport(item) {
			if (!item?.target) return;
			if (item.target_type === "Page") {
				window.retailedgeSetReportRouteHandoff?.(`/app/${item.target}`, {
					company: this.context.company || "",
					branch: this.context.branch || "",
				});
				frappe.set_route(item.target);
				return;
			}
			if (item.target_type === "Report" && this.canUseNativeDesk) {
				frappe.set_route("query-report", item.target);
			}
		},
		displayIcon(icon) {
			return {
				"bar-chart-2": "chart",
				"book-open": "report",
				"file-text": "report",
				"shopping-bag": "grid",
				"trending-up": "chart",
			}[String(icon || "")] || icon || "report";
		},
	},
};
</script>

<style scoped>
.reports-centre {
	display: grid;
	gap: 22px;
	padding-bottom: 32px;
}
.reports-centre-hero {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 24px;
	padding: 20px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 14px;
	background: var(--edge-color-surface, #fff);
}
.reports-centre-hero h2 {
	margin: 4px 0 7px;
	font-size: 1.35rem;
}
.reports-centre-hero p {
	max-width: 760px;
	margin: 0;
	color: var(--edge-color-ink-500, #667085);
	font-size: .84rem;
	line-height: 1.5;
}
.reports-centre-eyebrow {
	text-transform: uppercase;
	letter-spacing: .07em;
	font-size: .68rem !important;
	font-weight: 700;
	color: var(--edge-color-brand-600, #2563eb) !important;
}
.reports-centre-count {
	display: grid;
	min-width: 120px;
	justify-items: end;
}
.reports-centre-count strong {
	font-size: 1.55rem;
	font-variant-numeric: tabular-nums;
}
.reports-centre-count span {
	color: var(--edge-color-ink-500, #667085);
	font-size: .72rem;
}
.reports-centre-search {
	display: flex;
	align-items: end;
	justify-content: space-between;
	gap: 16px;
}
.reports-centre-search label {
	display: grid;
	gap: 6px;
	width: min(36rem, 100%);
}
.reports-centre-search label > span {
	font-size: .76rem;
	font-weight: 650;
}
.reports-centre-search input {
	width: 100%;
	min-height: 42px;
	padding: 9px 12px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 9px;
	background: var(--edge-color-surface, #fff);
	color: var(--edge-color-ink-950, #101828);
	font: inherit;
}
.reports-centre-search input:focus {
	outline: 2px solid color-mix(in srgb, var(--edge-color-brand-600, #2563eb) 35%, transparent);
	outline-offset: 1px;
}
.reports-centre-context {
	display: flex;
	flex-wrap: wrap;
	justify-content: flex-end;
	gap: 6px;
}
.reports-centre-context span,
.reports-centre-group-count {
	display: inline-flex;
	align-items: center;
	min-height: 26px;
	padding: 0 9px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 999px;
	background: var(--edge-color-surface-muted, #f8fafc);
	color: var(--edge-color-ink-500, #667085);
	font-size: .7rem;
}
.reports-centre-groups {
	display: grid;
	gap: 24px;
}
.reports-centre-group {
	display: grid;
	gap: 12px;
}
.reports-centre-group > header {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	align-items: center;
	gap: 10px;
}
.reports-centre-group h3 {
	margin: 0;
	font-size: 1rem;
}
.reports-centre-group header p {
	margin: 3px 0 0;
	color: var(--edge-color-ink-500, #667085);
	font-size: .76rem;
}
.reports-centre-group-icon,
.reports-centre-card-icon {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 8px;
	background: var(--edge-color-brand-50, #eef7ff);
	color: var(--edge-color-brand-700, #0c4f87);
}
.reports-centre-group-icon {
	width: 32px;
	height: 32px;
}
.reports-centre-grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}
.reports-centre-card {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	align-items: start;
	gap: 10px;
	min-width: 0;
	padding: 13px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 11px;
	background: var(--edge-color-surface, #fff);
	color: var(--edge-color-ink-950, #101828);
	text-align: left;
	cursor: pointer;
}
.reports-centre-card:hover,
.reports-centre-card:focus-visible {
	border-color: var(--edge-color-brand-600, #2563eb);
}
.reports-centre-card-icon {
	width: 30px;
	height: 30px;
	flex: 0 0 auto;
}
.reports-centre-card-copy {
	display: grid;
	gap: 4px;
	min-width: 0;
}
.reports-centre-card-copy strong {
	font-size: .84rem;
}
.reports-centre-card-copy small {
	color: var(--edge-color-ink-500, #667085);
	font-size: .73rem;
	line-height: 1.4;
}
.reports-centre-card-copy em {
	color: var(--edge-color-ink-500, #667085);
	font-size: .66rem;
	font-style: normal;
	font-weight: 650;
}
.reports-centre-card-open {
	align-self: center;
	color: var(--edge-color-brand-600, #2563eb);
	font-size: .7rem;
	font-weight: 700;
}
:global(:root[data-edge-appearance="dark"]) .reports-centre-hero,
:global(:root[data-edge-appearance="dark"]) .reports-centre-card,
:global(:root[data-edge-appearance="dark"]) .reports-centre-search input {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
	color: var(--edge-color-ink-950);
}
:global(:root[data-edge-appearance="dark"]) .reports-centre-context span,
:global(:root[data-edge-appearance="dark"]) .reports-centre-group-count {
	background: var(--edge-color-surface-muted);
	border-color: var(--edge-color-border);
}
@media (max-width: 1100px) {
	.reports-centre-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 720px) {
	.reports-centre-hero,
	.reports-centre-search {
		align-items: flex-start;
		flex-direction: column;
	}
	.reports-centre-count {
		justify-items: start;
	}
	.reports-centre-context {
		justify-content: flex-start;
	}
	.reports-centre-grid {
		grid-template-columns: 1fr;
	}
	.reports-centre-card {
		grid-template-columns: auto minmax(0, 1fr);
	}
	.reports-centre-card-open {
		grid-column: 2;
	}
}
</style>
