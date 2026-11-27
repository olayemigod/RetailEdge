<template>
	<div v-if="!edgeUIValid" class="cash-deposits-page-fallback">
		<strong>Cash Deposits could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Cash Deposits"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/cash-deposits"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="cash-deposits-page">
			<EdgePageHeader
				title="Cash Deposits"
				description="Review your cash deposits, including drafts and submitted deposits."
			/>
			<CashDepositRegisterPanel :can-use-native-desk="canUseNativeDesk" />
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import CashDepositRegisterPanel from "./CashDepositRegisterPanel.vue";

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
	name: "RetailEdgeCashDepositRegisterPage",
	components: {
		CashDepositRegisterPanel,
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
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, operatingContext] = await Promise.all([
					navigationPromise,
					callMethod("retailedge.operating_context.get_operating_context"),
				]);
				const shell = context.context || {};
				this.tenantName = operatingContext.company_label || operatingContext.company || shell.company || "";
				this.branchName = operatingContext.branch || "";
				this.userName = shell.user_name || shell.user || "";
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
.cash-deposits-page { min-height: 100%; }
.cash-deposits-page-fallback { margin:20px; padding:24px; display:flex; flex-direction:column; gap:8px; border:1px solid var(--edge-border,#d9d9d9); border-radius:var(--edge-radius-lg,10px); background:var(--edge-surface,#fff); }
</style>
