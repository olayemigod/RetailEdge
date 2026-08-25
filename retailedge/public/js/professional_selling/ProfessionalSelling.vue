<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Professional Selling could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Professional Selling"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/professional-selling"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-professional-selling-page">
			<EdgePageHeader
				title="Professional Selling"
				description="Manage the customer journey from quotation to order and delivery while ERPNext remains the system of record."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadWorkspace" />

			<div v-else class="selling-content">
				<section class="edge-panel selling-context">
					<div>
						<span class="selling-kicker">Operating context</span>
						<h3>{{ tenantName || "No operating company" }}</h3>
						<p>{{ branchName || "No operating branch selected" }}</p>
					</div>
					<div class="context-meta">
						<span>Selling Price List</span>
						<strong>{{ pricing.price_list || "ERPNext default" }}</strong>
					</div>
					<button type="button" class="edge-button edge-button--secondary" @click="openOperatingContext">Change Operating Context</button>
				</section>

				<section class="edge-panel policy-panel">
					<div>
						<span class="selling-kicker">Commercial controls</span>
						<h3>ERPNext pricing and delivery charges stay authoritative</h3>
						<p>Price Lists, Pricing Rules, taxes and Shipping Rules are applied through ERPNext. RetailEdge does not maintain a separate sales or delivery-charge ledger.</p>
					</div>
					<EdgeStatusBadge :status="shipping.available ? 'Active' : 'Warning'" />
				</section>

				<div class="selling-flow" aria-label="Selling workflow">
					<template v-for="(document, index) in documents" :key="document.key">
						<section class="edge-panel selling-stage">
							<div class="stage-heading">
								<span class="stage-number">{{ index + 1 }}</span>
								<div>
									<span class="selling-kicker">{{ document.stage }}</span>
									<h3>{{ document.label }}</h3>
								</div>
							</div>
							<p>{{ stageDescription(document.key) }}</p>
							<div class="stage-flags">
								<span v-if="document.selling_price_list_field">Price List</span>
								<span v-if="document.shipping_rule_field">Shipping Rule</span>
								<span v-if="document.source_warehouse_field">Stock Location</span>
							</div>
							<div class="selling-actions">
								<button v-if="document.can_create" type="button" class="edge-button edge-button--primary" @click="createNative(document)">Create {{ document.label }}</button>
								<button v-if="document.can_read" type="button" class="edge-button edge-button--secondary" @click="openNative(document)">View Records</button>
								<button v-if="document.can_read" type="button" class="edge-button edge-button--secondary" @click="loadRecent(document)">Recent</button>
							</div>
						</section>
						<div v-if="index < documents.length - 1" class="flow-arrow" aria-hidden="true">→</div>
					</template>
				</div>

				<section v-if="recentDocument" class="edge-panel recent-panel">
					<div class="recent-heading">
						<div>
							<span class="selling-kicker">Recent {{ recentDocument.label }}</span>
							<h3>Latest records</h3>
						</div>
						<button type="button" class="edge-button edge-button--secondary" @click="clearRecent">Close</button>
					</div>
					<EdgeLoadingState v-if="recentLoading" message="Loading recent records..." />
					<EdgeEmptyState v-else-if="!recentRows.length" title="No records found" description="No permitted records are available for this document type." />
					<div v-else class="recent-list">
						<button v-for="row in recentRows" :key="row.name" type="button" class="recent-row" @click="openRecord(recentDocument, row.name)">
							<strong>{{ row.name }}</strong>
							<span>{{ row.customer || row.party_name || row.status || "Draft" }}</span>
							<span v-if="row.grand_total !== undefined">{{ row.currency || "" }} {{ row.grand_total }}</span>
						</button>
					</div>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.professional_selling.get_professional_selling_context";
const RECENT_METHOD = "retailedge.professional_selling.get_recent_selling_documents";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeStatusBadge"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function doctypeSlug(doctype) {
	return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?._server_messages || fallback;
}

export default {
	name: "RetailEdgeProfessionalSelling",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			tenantName: "",
			branchName: "",
			userName: "",
			menuItems: [],
			pricing: {},
			shipping: {},
			documents: [],
			recentDocument: null,
			recentRows: [],
			recentLoading: false,
		};
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadWorkspace();
	},
	mounted() {
		window.addEventListener("retailedge-professional-selling-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadWorkspace();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-professional-selling-page-show", this._onPageShow);
	},
	methods: {
		async loadWorkspace() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [selling, navigation] = await Promise.all([callMethod(CONTEXT_METHOD), navigationPromise]);
				this.tenantName = selling.operating?.company || navigation.context?.company || "";
				this.branchName = selling.operating?.branch || navigation.context?.branch || "";
				this.userName = navigation.context?.user_name || selling.user_name || "";
				this.pricing = selling.pricing || {};
				this.shipping = selling.shipping || {};
				this.documents = Array.isArray(selling.documents) ? selling.documents.filter((row) => row.available && (row.can_read || row.can_create)) : [];
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.loaded = true;
			} catch (error) {
				this.error = errorMessage(error, "Professional Selling failed to load.");
			} finally {
				this.loading = false;
			}
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) }));
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
			else if (item.target) window.open(route || item.target, "_blank", "noopener,noreferrer");
		},
		stageDescription(key) {
			return ({
				quotation: "Prepare a customer offer using ERPNext pricing, taxes and optional Shipping Rule before commitment.",
				"sales-order": "Confirm the customer's order, requested delivery date and source Stock Location without bypassing ERPNext controls.",
				"delivery-note": "Fulfil stock from the approved order or create a permitted delivery using ERPNext stock truth and delivery charges.",
			})[key] || "Continue the selling workflow.";
		},
		createNative(document) {
			window.open(`/app/${doctypeSlug(document.doctype)}/new`, "_blank", "noopener,noreferrer");
		},
		openNative(document) {
			window.open(document.native_route || `/app/${doctypeSlug(document.doctype)}`, "_blank", "noopener,noreferrer");
		},
		openRecord(document, name) {
			window.open(`/app/${doctypeSlug(document.doctype)}/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer");
		},
		async loadRecent(document) {
			this.recentDocument = document;
			this.recentRows = [];
			this.recentLoading = true;
			try {
				const rows = await callMethod(RECENT_METHOD, { document: document.key, limit: 8 });
				this.recentRows = Array.isArray(rows) ? rows : [];
			} catch (error) {
				this.error = errorMessage(error, `Could not load recent ${document.label}.`);
			} finally {
				this.recentLoading = false;
			}
		},
		clearRecent() {
			this.recentDocument = null;
			this.recentRows = [];
		},
		openOperatingContext() {
			frappe.set_route("operating-context");
		},
	},
};
</script>

<style scoped>
.selling-content { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.selling-context, .policy-panel, .recent-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.selling-context h3, .policy-panel h3, .selling-stage h3, .recent-panel h3 { margin: 0.2rem 0 0.35rem; }
.selling-context p, .policy-panel p, .selling-stage p { margin: 0; color: var(--text-muted); }
.selling-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.context-meta { display: grid; gap: 0.2rem; min-width: 12rem; }
.context-meta span { color: var(--text-muted); font-size: 0.8rem; }
.selling-flow { display: grid; grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr) auto minmax(0, 1fr); gap: 0.75rem; align-items: stretch; }
.selling-stage { min-height: 14rem; display: flex; flex-direction: column; gap: 0.8rem; }
.stage-heading { display: flex; gap: 0.75rem; align-items: flex-start; }
.stage-number { width: 2rem; height: 2rem; border-radius: 999px; display: inline-grid; place-items: center; background: var(--subtle-fg, var(--control-bg)); font-weight: 700; }
.flow-arrow { display: grid; place-items: center; color: var(--text-muted); font-size: 1.4rem; }
.stage-flags, .selling-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: auto; }
.stage-flags span { padding: 0.2rem 0.5rem; border-radius: 999px; background: var(--subtle-fg, var(--control-bg)); color: var(--text-muted); font-size: 0.75rem; }
.recent-list { display: grid; gap: 0.5rem; margin-top: 1rem; }
.recent-row { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) auto; gap: 1rem; text-align: left; align-items: center; width: 100%; padding: 0.75rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.6rem; background: transparent; color: inherit; }
@media (max-width: 900px) { .selling-flow { grid-template-columns: 1fr; } .flow-arrow { transform: rotate(90deg); } }
@media (max-width: 680px) { .selling-context, .policy-panel, .recent-heading { flex-direction: column; } .recent-row { grid-template-columns: 1fr; } }
</style>
