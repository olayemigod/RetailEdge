<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Company Profile could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		title="Company Profile"
		:tenantName="profile.label || profile.name"
		:branchName="operatingContext.branch || ''"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/company-profile"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-company-profile-page">
			<EdgePageHeader
				title="Company Profile"
				description="RetailEdge company identity and business profile from the ERPNext Company master."
			/>
			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadProfile" />
			<div v-else class="company-profile-layout">
				<section class="edge-panel company-profile-identity">
					<div class="company-profile-logo" :class="{ 'has-logo': Boolean(profile.logo) }">
						<img v-if="profile.logo" :src="profile.logo" :alt="profile.label || profile.name" />
						<EdgeIcon v-else name="building" size="lg" />
					</div>
					<div>
						<span class="company-profile-kicker">Operating company</span>
						<h3>{{ profile.label || profile.name || "Company" }}</h3>
						<p>{{ profile.name }}</p>
					</div>
				</section>
				<section class="edge-panel company-profile-grid">
					<div><span>Abbreviation</span><strong>{{ profile.abbr || "—" }}</strong></div>
					<div><span>Default currency</span><strong>{{ profile.currency || "—" }}</strong></div>
					<div><span>Country</span><strong>{{ profile.country || "—" }}</strong></div>
					<div><span>Tax ID</span><strong>{{ profile.tax_id || "—" }}</strong></div>
					<div><span>Website</span><strong>{{ profile.website || "—" }}</strong></div>
					<div><span>Working Branch</span><strong>{{ operatingContext.branch || "Company-wide" }}</strong></div>
				</section>
				<section class="edge-panel company-profile-note">
					<strong>ERPNext Company remains authoritative</strong>
					<p>RetailEdge uses this profile for the shell identity, reports and guided workflows. Accounting defaults and submitted documents are not changed here.</p>
					<button v-if="canWrite && canUseNativeDesk" type="button" class="edge-button edge-button--secondary" @click="openAdvanced">
						Advanced: Edit Company in ERPNext
					</button>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeIcon"];
function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
export default {
	name: "RetailEdgeCompanyProfile",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true, missingComponents: [], loading: false, loaded: false, error: "",
			profile: {}, operatingContext: {}, menuItems: [], userName: "", canUseNativeDesk: false, canWrite: false,
		};
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadProfile();
	},
	mounted() {
		window.addEventListener("retailedge-company-profile-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadProfile();
	},
	beforeUnmount() { window.removeEventListener("retailedge-company-profile-page-show", this._onPageShow); },
	methods: {
		async loadProfile() {
			if (this.loading) return;
			this.loading = true; this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [data, navigation] = await Promise.all([
					callMethod("retailedge.company_profile.get_company_profile"),
					navigationPromise,
				]);
				this.profile = data.profile || {};
				this.operatingContext = data.operating_context || {};
				this.canWrite = Boolean(data.can_write);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.userName = navigation.context?.user_name || "";
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.loaded = true;
			} catch (error) {
				this.error = error?.message || error?.exc || "Company Profile could not be loaded.";
			} finally { this.loading = false; }
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; return item.target || ""; },
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (this.canUseNativeDesk && item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (this.canUseNativeDesk && item.target_type === "DocType") frappe.set_route("List", item.target);
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.canWrite || !this.profile.name) return;
			frappe.set_route("Form", "Company", this.profile.name);
		},
	},
};
</script>

<style scoped>
.company-profile-layout { display:grid; gap:1rem; }
.edge-panel { padding:1rem; border:1px solid var(--edge-color-border,var(--edge-border)); border-radius:.75rem; background:var(--edge-color-surface,var(--edge-surface)); color:var(--edge-color-ink-950,var(--edge-text)); }
.company-profile-identity { display:flex; align-items:center; gap:1rem; }
.company-profile-logo { width:4rem; height:4rem; display:grid; place-items:center; border-radius:.75rem; background:var(--edge-color-brand-50); color:var(--edge-color-brand-700); overflow:hidden; }
.company-profile-logo img { width:100%; height:100%; object-fit:contain; background:var(--edge-color-surface); }
.company-profile-kicker,.company-profile-grid span { color:var(--edge-color-ink-500,var(--edge-text-muted)); font-size:.75rem; }
.company-profile-identity h3 { margin:.15rem 0; font-size:1.35rem; }
.company-profile-identity p,.company-profile-note p { margin:0; color:var(--edge-color-ink-500,var(--edge-text-muted)); }
.company-profile-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(12rem,1fr)); gap:1rem; }
.company-profile-grid > div { display:grid; gap:.25rem; min-width:0; }
.company-profile-grid strong { overflow-wrap:anywhere; font-weight:600; }
.company-profile-note { display:grid; gap:.5rem; justify-items:start; }
</style>
