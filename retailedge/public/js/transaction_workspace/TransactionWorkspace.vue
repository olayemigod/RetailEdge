<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Transaction Workspace could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Transaction Workspace"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/transaction-workspace"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-transaction-workspace-page">
			<EdgePageHeader
				title="Transaction Workspace"
				description="Start sales, purchasing, stock and POS work from one RetailEdge operating context while ERPNext remains the system of record."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadWorkspace" />

			<div v-else class="workspace-content">
				<section class="edge-panel context-panel">
					<div>
						<span class="workspace-kicker">Operating context</span>
						<h3>{{ tenantName || "No operating company" }}</h3>
						<p>{{ branchName || "No operating branch selected" }}</p>
						<p v-if="posProfile" class="muted">POS Profile: {{ posProfile }}</p>
					</div>
					<button type="button" class="edge-button edge-button--secondary" @click="openOperatingContext">Change Operating Context</button>
				</section>

				<section class="edge-panel pos-panel">
					<div class="panel-heading">
						<div>
							<span class="workspace-kicker">Point of sale</span>
							<h3>{{ posProviderLabel }}</h3>
							<p>{{ posDescription }}</p>
						</div>
						<EdgeStatusBadge :status="pos?.provider === 'posnext' ? 'Active' : 'Warning'" />
					</div>
					<div v-if="posLaunchError" class="pos-launch-error" role="alert">{{ posLaunchError }}</div>
					<div class="workspace-actions">
						<button v-if="canStartPos" type="button" class="edge-button edge-button--primary" :disabled="posStarting" @click="startPos">{{ posStarting ? "Checking POS..." : "Start POS" }}</button>
						<button v-if="pos?.opening_doctype" type="button" class="edge-button edge-button--secondary" @click="openDoctype(pos.opening_doctype)">POS Opening</button>
						<button v-if="pos?.closing_doctype" type="button" class="edge-button edge-button--secondary" @click="openDoctype(pos.closing_doctype)">POS Closing</button>
					</div>
					<p v-if="pos?.provider === 'posnext'" class="muted">POSNext remains the POS engine. RetailEdge provides the operating entry point and context visibility; POSNext-specific runtime overrides remain in the ProcessEdge POSNext extension.</p>
				</section>

				<EdgeEmptyState
					v-if="!actions.length"
					title="No transaction actions available"
					description="Your current permissions do not allow creation of the supported transaction documents."
				/>

				<div v-else class="transaction-grid">
					<section v-for="action in actions" :key="action.key" class="edge-panel transaction-card">
						<span class="workspace-kicker">{{ kindLabel(action.kind) }}</span>
						<h3>{{ action.label }}</h3>
						<p>{{ actionDescription(action) }}</p>
						<div class="workspace-actions">
							<button type="button" class="edge-button edge-button--primary" @click="runTransactionAction(action)">{{ actionButtonLabel(action) }}</button>
							<button type="button" class="edge-button edge-button--secondary" @click="openDoctype(action.doctype)">View Records</button>
						</div>
					</section>
				</div>
			</div>

			<SimpleSalesInvoiceDialog
				:open="simpleSalesInvoiceOpen"
				@close="simpleSalesInvoiceOpen = false"
				@saved="handleGuidedSaved"
				@open-native="openNativeSalesInvoice"
			/>
			<SimplePurchaseInvoiceDialog
				:open="simplePurchaseInvoiceOpen"
				@close="simplePurchaseInvoiceOpen = false"
				@saved="handleGuidedSaved"
				@open-native="openNativePurchaseInvoice"
			/>
			<SimpleStockTransferDialog
				:open="simpleStockTransferOpen"
				@close="simpleStockTransferOpen = false"
				@saved="handleGuidedSaved"
				@open-native="openNativeStockTransfer"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import SimplePurchaseInvoiceDialog from "../retailedge_business_hub/SimplePurchaseInvoiceDialog.vue";
import SimpleSalesInvoiceDialog from "../retailedge_business_hub/SimpleSalesInvoiceDialog.vue";
import SimpleStockTransferDialog from "../retailedge_business_hub/SimpleStockTransferDialog.vue";

const REQUIRED_COMPONENTS = [
	"EdgeAppShell",
	"EdgePageLayout",
	"EdgePageHeader",
	"EdgeLoadingState",
	"EdgeErrorState",
	"EdgeEmptyState",
	"EdgeStatusBadge",
];
const GUIDED_DOCTYPES = new Set(["Sales Invoice", "Purchase Invoice", "Stock Entry"]);
const POS_LAUNCH_METHOD = "retailedge.retailedge.page.transaction_workspace.transaction_workspace.prepare_pos_launch";

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

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?._server_messages || fallback;
}

export default {
	name: "RetailEdgeTransactionWorkspace",
	components: {
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
		SimplePurchaseInvoiceDialog,
		SimpleSalesInvoiceDialog,
		SimpleStockTransferDialog,
	},
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			actions: [],
			pos: {},
			menuItems: [],
			tenantName: "",
			branchName: "",
			posProfile: "",
			userName: "",
			posStarting: false,
			posLaunchError: "",
			simpleSalesInvoiceOpen: false,
			simplePurchaseInvoiceOpen: false,
			simpleStockTransferOpen: false,
		};
	},
	computed: {
		posProviderLabel() {
			return this.pos?.provider === "posnext" ? "POSNext" : "ERPNext Point of Sale";
		},
		posDescription() {
			return this.pos?.provider === "posnext"
				? "Use the installed POSNext provider from the current RetailEdge operating context."
				: "POSNext is not available, so RetailEdge falls back to ERPNext's native Point of Sale where installed.";
		},
		canStartPos() {
			return Boolean(this.pos?.start_target || this.pos?.start_url);
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadWorkspace();
	},
	mounted() {
		window.addEventListener("retailedge-transaction-workspace-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadWorkspace();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-transaction-workspace-page-show", this._onPageShow);
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
				const [workspace, navigation] = await Promise.all([
					callMethod("retailedge.retailedge.page.transaction_workspace.transaction_workspace.get_transaction_workspace_context"),
					navigationPromise,
				]);
				this.actions = Array.isArray(workspace.actions) ? workspace.actions : [];
				this.pos = workspace.pos || {};
				this.tenantName = workspace.operating?.company || navigation.context?.company || "";
				this.branchName = workspace.operating?.branch || navigation.context?.branch || "";
				this.posProfile = workspace.operating?.default_pos_profile || "";
				this.userName = navigation.context?.user_name || workspace.user_name || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.loaded = true;
			} catch (error) {
				this.error = errorMessage(error, "Transaction Workspace failed to load.");
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
		async startPos() {
			if (this.posStarting) return;
			this.posStarting = true;
			this.posLaunchError = "";
			try {
				const launch = await callMethod(POS_LAUNCH_METHOD);
				if (launch.start_link_type === "Page" && launch.start_target) {
					frappe.set_route(launch.start_target);
					return;
				}
				if (launch.start_url) {
					window.location.assign(launch.start_url);
					return;
				}
				throw new Error("No POS launch target is available.");
			} catch (error) {
				this.posLaunchError = errorMessage(error, "POS could not be started from the current Operating Context.");
			} finally {
				this.posStarting = false;
			}
		},
		runTransactionAction(action) {
			if (!action?.doctype) return;
			if (action.doctype === "Sales Invoice") {
				this.simpleSalesInvoiceOpen = true;
				return;
			}
			if (action.doctype === "Purchase Invoice") {
				this.simplePurchaseInvoiceOpen = true;
				return;
			}
			if (action.doctype === "Stock Entry") {
				this.simpleStockTransferOpen = true;
				return;
			}
			this.createDoctype(action.doctype);
		},
		actionButtonLabel(action) {
			return GUIDED_DOCTYPES.has(action?.doctype) ? "Guided Entry" : "Create";
		},
		actionDescription(action) {
			return GUIDED_DOCTYPES.has(action?.doctype)
				? `Use the existing guided ${action.label} flow here, with native ERPNext as the advanced fallback.`
				: `Create a native ERPNext ${action.label} using the current operating context and server-side RetailEdge defaults.`;
		},
		handleGuidedSaved() {
			this.simpleSalesInvoiceOpen = false;
			this.simplePurchaseInvoiceOpen = false;
			this.simpleStockTransferOpen = false;
			this.loadWorkspace();
		},
		openNativeSalesInvoice() {
			this.simpleSalesInvoiceOpen = false;
			this.createDoctype("Sales Invoice");
		},
		openNativePurchaseInvoice() {
			this.simplePurchaseInvoiceOpen = false;
			this.createDoctype("Purchase Invoice");
		},
		openNativeStockTransfer() {
			this.simpleStockTransferOpen = false;
			this.createDoctype("Stock Entry");
		},
		openDoctype(doctype) {
			if (!doctype) return;
			window.open(`/app/${doctypeSlug(doctype)}`, "_blank", "noopener,noreferrer");
		},
		createDoctype(doctype) {
			if (!doctype) return;
			window.open(`/app/${doctypeSlug(doctype)}/new`, "_blank", "noopener,noreferrer");
		},
		openOperatingContext() {
			frappe.set_route("operating-context");
		},
		kindLabel(kind) {
			return ({ sell: "Selling", buy: "Purchasing", stock: "Stock" })[kind] || "Transaction";
		},
	},
};
</script>

<style scoped>
.workspace-content { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.context-panel, .panel-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.context-panel h3, .pos-panel h3, .transaction-card h3 { margin: 0.2rem 0 0.35rem; }
.context-panel p, .pos-panel p, .transaction-card p { margin: 0; color: var(--text-muted); }
.workspace-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.transaction-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.transaction-card { display: flex; flex-direction: column; gap: 0.8rem; min-height: 11rem; }
.workspace-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1rem; }
.muted { color: var(--text-muted); font-size: 0.9rem; }
.pos-launch-error { margin-top: 1rem; padding: 0.75rem 1rem; border: 1px solid var(--red-200, #fecaca); border-radius: 0.6rem; color: var(--red-700, #b91c1c); background: var(--red-50, #fef2f2); }
@media (max-width: 760px) { .transaction-grid { grid-template-columns: 1fr; } .context-panel, .panel-heading { flex-direction: column; } }
</style>
