<template>
	<EdgeAppShell
		product="retailedge"
		:menuItems="shellMenuItems"
		activeRoute="/app/retailedge-business-hub"
		title="RetailEdge"
		:tenantName="context.company"
		:branchName="context.branch"
		:userName="context.user_name"
		:hideNativeSidebar="true"
		@navigate="navigateFromShell"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="RetailEdge Business Hub"
					subtitle="Navigate, act, operate, understand, and respond from one business-focused workspace."
					:withBackButton="false"
				/>
			</template>

			<div v-if="loading" class="hub-state">
				<EdgeLoadingState
					message="Loading your permitted RetailEdge tools..."
					:skeleton="true"
				/>
			</div>

			<div v-else-if="error" class="hub-state">
				<EdgeErrorState
					title="Business Hub unavailable"
					:message="error"
					@retry="refreshContext({ force: true })"
				/>
			</div>

			<div v-else class="retailedge-business-hub">
				<section class="hub-banner">
					<div>
						<p class="hub-eyebrow">Retail operations simplified</p>
						<h2>{{ greeting }}</h2>
						<p>
							Use the business menu for daily operations and the actions below for current
							transactions. Guided RetailEdge entries will progressively replace technical
							ERPNext fields without creating duplicate accounting documents.
						</p>
					</div>
					<div class="hub-context">
						<span v-if="context.company">{{ context.company }}</span>
						<span v-if="context.branch">{{ context.branch }}</span>
						<span>Product switching suspended</span>
					</div>
				</section>

				<section>
					<div class="section-heading">
						<div>
							<p class="section-kicker">Programme structure</p>
							<h3>Five connected RetailEdge experiences</h3>
						</div>
					</div>
					<div class="experience-grid">
						<article
							v-for="experience in programmeExperiences"
							:key="experience.key"
							class="experience-card"
						>
							<div class="experience-card-top">
								<span class="experience-icon">{{ iconText(experience.icon) }}</span>
								<EdgeStatusBadge
									:label="experience.status"
									:status="experience.status"
								/>
							</div>
							<h4>{{ experience.label }}</h4>
							<p>{{ experience.description }}</p>
						</article>
					</div>
				</section>

				<section>
					<div class="section-heading">
						<div>
							<p class="section-kicker">Act</p>
							<h3>Quick business actions</h3>
						</div>
						<p>Every action creates a standard ERPNext or RetailEdge document.</p>
					</div>
					<div v-if="quickActions.length" class="quick-action-grid">
						<button
							v-for="action in quickActions"
							:key="action.key"
							type="button"
							class="quick-action-card"
							@click="runQuickAction(action)"
						>
							<span class="quick-action-icon">{{ iconText(action.icon) }}</span>
							<span class="quick-action-copy">
								<strong>{{ action.label }}</strong>
								<small>{{ action.description }}</small>
							</span>
							<span class="quick-action-mode">{{ actionModeLabel(action.mode) }}</span>
						</button>
					</div>
					<EdgeEmptyState
						v-else
						title="No permitted quick actions"
						description="Your current roles do not allow creation of the configured business documents."
						icon="lock"
					/>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.edgesuite_ui.get_retailedge_business_hub_context";
const CONTEXT_CACHE_TTL_MS = 30_000;
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function readSharedContext() {
	const cache = window.__retailedgeBusinessHubContextCache;
	if (!cache || !cache.data || !cache.fetchedAt) return null;
	if (Date.now() - cache.fetchedAt > CONTEXT_CACHE_TTL_MS) return null;
	return cache.data;
}

function cacheSharedContext(data) {
	if (typeof window.retailedgeCacheBusinessHubContext === "function") {
		return window.retailedgeCacheBusinessHubContext(data);
	}
	const normalized = data || {};
	window.__retailedgeBusinessHubContextCache = {
		data: normalized,
		fetchedAt: Date.now(),
	};
	return normalized;
}

function fetchSharedContext({ force = false } = {}) {
	if (typeof window.retailedgeGetBusinessHubContext === "function") {
		return window.retailedgeGetBusinessHubContext({ force });
	}
	if (!force) {
		const cached = readSharedContext();
		if (cached) return Promise.resolve(cached);
	}
	if (window.__retailedgeBusinessHubContextRequest) {
		return window.__retailedgeBusinessHubContextRequest;
	}
	const request = new Promise((resolve, reject) => {
		frappe.call({
			method: CONTEXT_METHOD,
			callback: (response) => resolve(cacheSharedContext(response.message || {})),
			error: (error) => reject(error),
		});
	});
	window.__retailedgeBusinessHubContextRequest = request;
	request.finally(() => {
		if (window.__retailedgeBusinessHubContextRequest === request) {
			window.__retailedgeBusinessHubContextRequest = null;
		}
	});
	return request;
}

export default {
	name: "RetailEdgeBusinessHub",
	components: {
		EdgeAppShell: runtimeComponents.EdgeAppShell,
		EdgePageLayout: runtimeComponents.EdgePageLayout,
		EdgePageHeader: runtimeComponents.EdgePageHeader,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
		EdgeEmptyState: runtimeComponents.EdgeEmptyState,
		EdgeStatusBadge: runtimeComponents.EdgeStatusBadge,
	},
	data() {
		return {
			loading: true,
			error: "",
			programmeExperiences: [],
			navigationGroups: [],
			quickActions: [],
			context: {
				user: "",
				user_name: "",
				company: "",
				branch: "",
			},
			featureFlags: {},
		};
	},
	computed: {
		greeting() {
			return this.context.user_name
				? `Welcome, ${this.context.user_name}`
				: "Your RetailEdge command centre";
		},
		shellMenuItems() {
			return this.navigationGroups
				.map((group) => ({
					key: group.key,
					label: group.label,
					icon: group.icon || "layers",
					defaultCollapsed: group.key !== "home",
					items: (group.items || [])
						.map((item) => ({
							label: item.label,
							description: item.description || "",
							route: this.routeForTarget(item),
							icon: item.icon || "list",
							source: item,
						}))
						.filter((item) => item.route),
				}))
				.filter((group) => group.items.length);
		},
	},
	mounted() {
		this.refreshContext();
	},
	methods: {
		applyContext(data) {
			this.programmeExperiences = data.programme_experiences || [];
			this.navigationGroups = data.navigation_groups || [];
			this.quickActions = data.quick_actions || [];
			this.context = { ...this.context, ...(data.context || {}) };
			this.featureFlags = data.feature_flags || {};
		},
		refreshContext({ force = false } = {}) {
			this.loading = true;
			this.error = "";
			return fetchSharedContext({ force })
				.then((data) => {
					this.applyContext(data || {});
				})
				.catch((error) => {
					this.error =
						error && error.message
							? error.message
							: "Unable to load RetailEdge Business Hub context.";
				})
				.finally(() => {
					this.loading = false;
				});
		},
		runQuickAction(action) {
			if (!action || !action.doctype) return;
			frappe.new_doc(action.doctype);
		},
		navigateFromShell(route) {
			const item = this.shellMenuItems
				.flatMap((group) => group.items || [])
				.find((entry) => entry.route === route);
			if (item && item.source) {
				this.openTarget(item.source);
				return;
			}
			if (route) frappe.set_route(route);
		},
		openTarget(item) {
			if (!item) return;
			if (item.target_type === "URL") {
				window.location.assign(item.target);
				return;
			}
			if (item.target_type === "DocType") {
				frappe.set_route("List", item.target);
				return;
			}
			if (item.target_type === "Report") {
				frappe.set_route("query-report", item.target);
				return;
			}
			if (item.target_type === "Page") {
				frappe.set_route(item.target);
			}
		},
		routeForTarget(item) {
			if (!item) return "";
			if (item.target_type === "URL") return item.target;
			if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`;
			if (item.target_type === "Report")
				return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "Page") return `/app/${item.target}`;
			return "";
		},
		actionModeLabel(mode) {
			return mode === "available" ? "RetailEdge flow" : "Native form now";
		},
		iconText(icon) {
			const icons = {
				grid: "▦",
				zap: "⚡",
				briefcase: "▣",
				"bar-chart-2": "▥",
				bell: "◉",
				"file-text": "▤",
				download: "↓",
				upload: "↑",
				"credit-card": "▭",
				"shopping-bag": "▰",
				repeat: "⇄",
			};
			return icons[icon] || "•";
		},
	},
};
</script>

<style scoped>
.retailedge-business-hub {
	display: grid;
	gap: 28px;
	padding-bottom: 32px;
}
.hub-state {
	padding: 24px;
}
.hub-banner {
	display: flex;
	justify-content: space-between;
	gap: 24px;
	padding: 24px;
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 14px;
	background: var(--edge-surface, #ffffff);
}
.hub-banner h2 {
	margin: 4px 0 8px;
	font-size: 1.55rem;
}
.hub-banner p {
	margin: 0;
	color: var(--edge-text-muted, #667085);
	max-width: 760px;
}
.hub-eyebrow,
.section-kicker {
	text-transform: uppercase;
	letter-spacing: 0.08em;
	font-size: 0.72rem;
	font-weight: 700;
	color: var(--edge-primary, #2563eb);
}
.hub-context {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
	gap: 6px;
	font-size: 0.82rem;
	color: var(--edge-text-muted, #667085);
}
.section-heading {
	display: flex;
	align-items: end;
	justify-content: space-between;
	gap: 18px;
	margin-bottom: 14px;
}
.section-heading h3 {
	margin: 2px 0 0;
}
.section-heading > p {
	margin: 0;
	color: var(--edge-text-muted, #667085);
	font-size: 0.88rem;
}
.experience-grid,
.quick-action-grid {
	display: grid;
	gap: 14px;
}
.experience-grid {
	grid-template-columns: repeat(5, minmax(0, 1fr));
}
.quick-action-grid {
	grid-template-columns: repeat(3, minmax(0, 1fr));
}
.experience-card,
.quick-action-card {
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-surface, #ffffff);
}
.experience-card {
	padding: 18px;
}
.experience-card-top {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
}
.experience-card h4 {
	margin: 14px 0 8px;
}
.experience-card p {
	margin: 0;
	color: var(--edge-text-muted, #667085);
	font-size: 0.88rem;
	line-height: 1.5;
}
.experience-icon,
.quick-action-icon {
	font-size: 1.3rem;
}
.quick-action-card {
	display: grid;
	grid-template-columns: auto 1fr auto;
	align-items: center;
	gap: 12px;
	padding: 16px;
	text-align: left;
	cursor: pointer;
}
.quick-action-card:hover {
	border-color: var(--edge-primary, #2563eb);
}
.quick-action-copy {
	display: grid;
	gap: 4px;
}
.quick-action-copy small {
	color: var(--edge-text-muted, #667085);
	line-height: 1.35;
}
.quick-action-mode {
	font-size: 0.72rem;
	color: var(--edge-text-muted, #667085);
	white-space: nowrap;
}
@media (max-width: 1200px) {
	.experience-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.quick-action-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
}
@media (max-width: 720px) {
	.hub-banner,
	.section-heading {
		align-items: flex-start;
		flex-direction: column;
	}
	.hub-context {
		align-items: flex-start;
	}
	.experience-grid,
	.quick-action-grid {
		grid-template-columns: 1fr;
	}
	.quick-action-card {
		grid-template-columns: auto 1fr;
	}
	.quick-action-mode {
		grid-column: 2;
	}
}
</style>
