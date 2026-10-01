<template>
	<div v-if="!edgeUIValid" class="payment-history-page-fallback">
		<strong>Payment History could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Payment History"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/payment-history"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="payment-history-page">
			<EdgePageHeader
				title="Payment History"
				description="Review permission-visible ERPNext Payment Entries, allocations and submission status without mixing transaction entry with historical review."
			/>
			<PaymentHistoryPanel />
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import PaymentHistoryPanel from "./PaymentHistoryPanel.vue";

const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

export default {
	name: "RetailEdgePaymentHistoryPage",
	components: {
		PaymentHistoryPanel,
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	},
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			tenantName: "",
			branchName: "",
			userName: "",
			menuItems: [],
			canUseNativeDesk: false,
		};
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() {
		if (this.edgeUIValid) this.loadShell();
	},
	methods: {
		async loadShell() {
			try {
				const context = typeof window.retailedgeGetBusinessHubContext === "function"
					? await window.retailedgeGetBusinessHubContext()
					: await callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const operating = context.context || {};
				this.tenantName = operating.company_label || operating.company || "";
				this.branchName = operating.branch || "";
				this.userName = operating.user_name || "";
				this.canUseNativeDesk = Boolean(context?.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(context.navigation_groups || []);
			} catch (_error) {
				// The history panel still provides its own permission-aware error state.
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
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if ((item.target_type === "Report" || item.target_type === "DocType") && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
	},
};
</script>

<style scoped>
.payment-history-page { min-height: 100%; }
.payment-history-page-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
</style>
