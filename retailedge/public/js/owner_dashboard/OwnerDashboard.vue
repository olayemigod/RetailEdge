<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Financial Dashboard could not start.</strong>
		<div>Required EdgeSuite financial components are unavailable. Install the approved EdgeSuite UI dashboard candidate and refresh.</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Financial Dashboard"
		:tenantName="tenantName || filters.company"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/owner-dashboard"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgeFinancialDashboard
			:payload="payload"
			:dateModel="smartDate"
			dateOrder="DMY"
			:loading="loading || metadataLoading"
			:error="error"
			:exportEnabled="hasData && capabilities.can_export"
			:printEnabled="hasData && capabilities.can_print"
			:exportBusy="exportBusy"
			:printBusy="printBusy"
			:exportInitialOptions="exportOptions"
			@update:dateModel="smartDate = $event"
			@date-resolved="onSmartDateResolved"
			@refresh="fetchData"
			@quick-reports="openQuickReports"
			@retry="fetchData"
			@action="handleDashboardAction"
			@export="handleExport"
			@print="handlePrint"
		>
			<template #comparison>
				<EdgeDropdown
					v-model="filters.comparison_mode"
					:options="comparisonOptions"
					label="Compare"
					:disabled="loading || metadataLoading"
					@change="onComparisonChanged"
				/>
			</template>
		</EdgeFinancialDashboard>
	</EdgeAppShell>
</template>

<script>
import {
	defaultDashboardExportOptions,
	exportDashboard,
	getDashboardCapabilities,
	printDashboard,
} from "../retailedge_dashboard_actions";

const DASHBOARD_KEY = "owner-dashboard";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeFinancialDashboard", "EdgeDropdown"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || window.EdgeUI?.components || {};
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

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

function routeForTarget(item = {}) {
	if (item.target_type === "Page") return `/app/${item.target}`;
	if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
	if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
	return item.target || "";
}

function setRouteHandoff(destination, filters = {}) {
	const cleanFilters = Object.fromEntries(
		Object.entries(filters || {}).filter(([, value]) => value !== undefined && value !== null && value !== "")
	);
	window.__retailedgeBusinessHubRouteHandoff = {
		target: destination,
		filters: cleanFilters,
		createdAt: Date.now(),
	};
	frappe.route_options = {
		...cleanFilters,
		retailedge_business_hub_handoff: 1,
		retailedge_business_hub_target: destination,
	};
}

export default {
	name: "OwnerDashboard",
	components: Object.fromEntries(
		REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])
	),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			metadataLoading: true,
			loading: false,
			error: "",
			payload: { schema_version: 1, summary: [], collection_metrics: [], alerts: [], report_links: [] },
			filters: { company: "", branch: "", from_date: "", to_date: "", comparison_mode: "Previous Period" },
			comparisonOptions: ["Previous Period", "Off"],
			smartDate: {},
			capabilities: { can_view: true, can_print: false, can_export: false },
			exportBusy: false,
			printBusy: false,
			exportOptions: { ...defaultDashboardExportOptions(), include_charts: true },
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			nativeFallbackEnabled: false,
			requestId: 0,
		};
	},
	computed: {
		hasData() {
			return Boolean(
				(this.payload.summary || []).length ||
				(this.payload.collection_metrics || []).length ||
				(this.payload.alerts || []).length
			);
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() {
		this.fetchMetadata();
		document.addEventListener("edgesuite-context-changed", this.handleContextChanged);
		document.addEventListener("retailedge-operating-context-changed", this.handleContextChanged);
	},
	beforeUnmount() {
		document.removeEventListener("edgesuite-context-changed", this.handleContextChanged);
		document.removeEventListener("retailedge-operating-context-changed", this.handleContextChanged);
	},
	methods: {
		async fetchMetadata() {
			if (!this.edgeUIValid) return;
			this.metadataLoading = true;
			this.error = "";
			try {
				const navigationPromise =
					typeof window.retailedgeGetBusinessHubContext === "function"
						? window.retailedgeGetBusinessHubContext()
						: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.financial_dashboard.get_financial_dashboard_context"),
					navigationPromise,
				]);
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				const handoff =
					window.retailedgeConsumeBusinessHubRouteOptions?.("owner-dashboard") || {};
				this.filters = { ...this.filters, ...handoff };
				this.syncSmartDateFromFilters();
				this.capabilities = context.capabilities || this.capabilities;
				this.comparisonOptions = context.comparison_options || this.comparisonOptions;
				this.tenantName = context.tenant_name || this.filters.company || "";
				this.branchName = context.branch_name || this.filters.branch || "";
				this.userName = context.user_name || "";
				this.nativeFallbackEnabled = Boolean(navigation.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (this.filters.company) await this.fetchData();
			} catch (error) {
				this.error = errorMessage(error, "Failed to load Financial Dashboard controls.");
			} finally {
				this.metadataLoading = false;
			}
		},
		syncSmartDateFromFilters() {
			if (!this.filters.from_date || !this.filters.to_date) {
				this.smartDate = {};
				return;
			}
			this.smartDate = {
				expression: "custom",
				from_date: this.filters.from_date,
				to_date: this.filters.to_date,
				label:
					this.filters.from_date === this.filters.to_date
						? this.filters.from_date
						: `${this.filters.from_date} – ${this.filters.to_date}`,
			};
		},
		onSmartDateResolved(value) {
			if (!value?.from_date || !value?.to_date) return;
			this.smartDate = { ...value };
			this.filters.from_date = value.from_date;
			this.filters.to_date = value.to_date;
			this.fetchData();
		},
		onComparisonChanged() {
			this.fetchData();
		},
		async fetchData() {
			if (!this.filters.company || !this.edgeUIValid) return;
			const requestId = ++this.requestId;
			this.loading = true;
			this.error = "";
			try {
				const [result, capabilities] = await Promise.all([
					callMethod("retailedge.financial_dashboard.get_financial_dashboard_data", {
						filters: this.filters,
					}),
					getDashboardCapabilities(DASHBOARD_KEY, this.filters),
				]);
				if (requestId !== this.requestId) return;
				const responseContext = result.context || {};
				if (
					String(responseContext.company || "") !== String(this.filters.company || "") ||
					String(responseContext.branch || "") !== String(this.filters.branch || "") ||
					String(responseContext.from_date || "") !== String(this.filters.from_date || "") ||
					String(responseContext.to_date || "") !== String(this.filters.to_date || "") ||
					String(responseContext.comparison_mode || "") !== String(this.filters.comparison_mode || "")
				) {
					return;
				}
				this.payload = result || this.payload;
				this.capabilities = capabilities || result.capabilities || this.capabilities;
				this.tenantName = responseContext.company || this.tenantName;
				this.branchName = responseContext.branch || "";
			} catch (error) {
				if (requestId !== this.requestId) return;
				this.error = errorMessage(error, "Failed to load the Financial Dashboard.");
			} finally {
				if (requestId === this.requestId) this.loading = false;
			}
		},
		async handleExport(options) {
			this.exportBusy = true;
			this.error = "";
			try {
				await exportDashboard(DASHBOARD_KEY, this.filters, options);
			} catch (error) {
				this.error = errorMessage(error, "Financial Dashboard export failed.");
			} finally {
				this.exportBusy = false;
			}
		},
		async handlePrint() {
			this.printBusy = true;
			this.error = "";
			try {
				await printDashboard(DASHBOARD_KEY, this.filters);
			} catch (error) {
				this.error = errorMessage(error, "Financial Dashboard print failed.");
			} finally {
				this.printBusy = false;
			}
		},
		handleDashboardAction(action = {}) {
			const destination = String(action.destination || action.target || "").trim();
			if (!destination) return;
			const filters = { ...(action.filters || {}) };
			setRouteHandoff(destination, filters);
			if (String(action.kind || "page") === "report") {
				frappe.set_route("query-report", destination);
				return;
			}
			frappe.set_route(destination);
		},
		openQuickReports() {
			setRouteHandoff("reports-centre", {
				company: this.filters.company,
				branch: this.filters.branch,
				from_date: this.filters.from_date,
				to_date: this.filters.to_date,
			});
			frappe.set_route("reports-centre");
		},
		mapNavigationGroups(groups) {
			return (groups || [])
				.map((group) => ({
					...group,
					items: (group.items || [])
						.filter(
							(item) =>
								this.nativeFallbackEnabled ||
								!["DocType", "Report"].includes(item.target_type)
						)
						.map((item) => ({ ...item, route: routeForTarget(item) })),
				}))
				.filter((group) => (group.items || []).length);
		},
		handleNavigation(route) {
			const item = this.menuItems
				.flatMap((group) => group.items || [])
				.find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.nativeFallbackEnabled) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
		},
		handleContextChanged(event) {
			const detail = event?.detail || {};
			if (detail.product && detail.product !== "retailedge") return;
			this.requestId += 1;
			this.fetchMetadata();
		},
	},
};
</script>
