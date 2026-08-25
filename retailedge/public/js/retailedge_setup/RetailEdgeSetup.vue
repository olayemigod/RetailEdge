<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Setup could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Setup"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/retailedge-setup"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-setup-page">
			<EdgePageHeader
				title="Setup"
				description="Configure RetailEdge operating controls and open the authoritative ERPNext/Frappe setup records from one place."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadSetup" />

			<div v-else class="setup-content">
				<section class="edge-panel setup-guidance">
					<div>
						<span class="setup-kicker">Configuration hub</span>
						<h3>Business setup without duplicate records</h3>
						<p>RetailEdge keeps the existing DocTypes as the system of record. This page guides you to the permitted setup record; advanced editing still uses the native validated form.</p>
					</div>
					<button type="button" class="edge-button edge-button--secondary" @click="openOperatingContext">Operating Context</button>
				</section>

				<EdgeEmptyState
					v-if="!resources.length"
					title="No setup resources available"
					description="Your current permissions do not allow access to RetailEdge setup records."
				/>

				<div v-else class="setup-grid">
					<section v-for="resource in resources" :key="resource.key" class="edge-panel setup-card">
						<div class="setup-card-heading">
							<div>
								<span class="setup-kicker">{{ resource.singleton ? "Configuration" : "Master data" }}</span>
								<h3>{{ resource.label }}</h3>
							</div>
							<EdgeStatusBadge v-if="resource.count !== null && resource.count !== undefined" :status="resource.count ? 'Active' : 'Warning'" />
						</div>
						<p>{{ resource.description }}</p>
						<div v-if="resource.count !== null && resource.count !== undefined" class="setup-count">
							<strong>{{ resource.count }}{{ resource.count_capped ? "+" : "" }}</strong>
							<span>visible record{{ Number(resource.count) === 1 ? "" : "s" }}</span>
						</div>
						<div class="setup-actions">
							<button type="button" class="edge-button edge-button--primary" @click="openResource(resource)">
								{{ resource.singleton ? "Open Settings" : "View Records" }}
							</button>
							<button v-if="resource.can_create" type="button" class="edge-button edge-button--secondary" @click="createResource(resource)">Add New</button>
						</div>
					</section>
				</div>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgePageLayout",
	"EdgePageHeader",
	"EdgeLoadingState",
	"EdgeErrorState",
	"EdgeEmptyState",
	"EdgeStatusBadge",
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
			error: (error) => reject(error),
		});
	});
}

function doctypeSlug(doctype) {
	return String(doctype || "")
		.trim()
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "");
}

export default {
	name: "RetailEdgeSetup",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			resources: [],
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
		};
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadSetup();
	},
	mounted() {
		window.addEventListener("retailedge-setup-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadSetup();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-setup-page-show", this._onPageShow);
	},
	methods: {
		async loadSetup() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [setup, navigation] = await Promise.all([
					callMethod("retailedge.retailedge.page.retailedge_setup.retailedge_setup.get_setup_context"),
					navigationPromise,
				]);
				this.resources = Array.isArray(setup.resources) ? setup.resources : [];
				this.userName = navigation.context?.user_name || setup.user_name || "";
				this.tenantName = navigation.context?.company || "";
				this.branchName = navigation.context?.branch || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.loaded = true;
			} catch (error) {
				this.error = error?.message || error?.exc || "RetailEdge Setup failed to load.";
			} finally {
				this.loading = false;
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
			if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer");
			else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer");
		},
		openResource(resource) {
			if (!resource?.doctype) return;
			window.open(`/app/${doctypeSlug(resource.doctype)}`, "_blank", "noopener,noreferrer");
		},
		createResource(resource) {
			if (!resource?.doctype || !resource.can_create || resource.singleton) return;
			window.open(`/app/${doctypeSlug(resource.doctype)}/new`, "_blank", "noopener,noreferrer");
		},
		openOperatingContext() {
			frappe.set_route("operating-context");
		},
	},
};
</script>

<style scoped>
.setup-content { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.setup-guidance { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.setup-guidance h3, .setup-card h3 { margin: 0.2rem 0 0.35rem; }
.setup-guidance p, .setup-card p { margin: 0; color: var(--text-muted); }
.setup-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.setup-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.setup-card { display: flex; flex-direction: column; gap: 1rem; min-height: 13rem; }
.setup-card-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.setup-count { display: flex; align-items: baseline; gap: 0.45rem; margin-top: auto; }
.setup-count strong { font-size: 1.35rem; }
.setup-count span { color: var(--text-muted); }
.setup-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; }
@media (max-width: 760px) { .setup-grid { grid-template-columns: 1fr; } .setup-guidance { flex-direction: column; } }
</style>
