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
							Use the business menu for daily operations. The Create action is the common
							entry point for new business transactions; each guided flow progressively
							replaces technical ERPNext fields without creating duplicate accounting or
							stock documents.
						</p>
					</div>
					<div class="hub-banner-side">
						<div class="hub-context">
							<span v-if="context.company">{{ context.company }}</span>
							<span v-if="context.branch">{{ context.branch }}</span>
							<span>Product switching suspended</span>
						</div>
						<button
							type="button"
							class="edge-button edge-button--primary hub-create-button"
							:disabled="!quickActions.length"
							@click="openCreatePicker"
						>
							+ Create
						</button>
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
			</div>

			<EdgeModal
				:open="createPickerOpen"
				title="Create"
				subtitle="Choose the business entry you want to record. Only entries you can create are shown."
				size="md"
				@close="closeCreatePicker"
			>
				<div v-if="quickActions.length" class="create-picker-list">
					<button
						v-for="action in quickActions"
						:key="action.key"
						type="button"
						class="create-picker-item"
						@click="runQuickAction(action)"
					>
						<span class="create-picker-icon">{{ iconText(action.icon) }}</span>
						<span class="create-picker-copy">
							<strong>{{ action.label }}</strong>
							<small>{{ action.description }}</small>
						</span>
						<span class="create-picker-mode">{{ actionModeLabel(action) }}</span>
					</button>
				</div>
				<EdgeEmptyState
					v-else
					title="No permitted entries"
					description="Your current roles do not allow creation of the configured business documents."
					icon="lock"
				/>
				<template #footer>
					<button type="button" class="edge-button" @click="closeCreatePicker">Cancel</button>
				</template>
			</EdgeModal>

			<SimpleSalesInvoiceDialog
				:open="simpleSalesInvoiceOpen"
				@close="closeSimpleSalesInvoice"
				@saved="handleSimpleSalesInvoiceSaved"
				@open-native="openNativeSalesInvoice"
			/>

			<SimplePaymentDialog
				:open="simplePaymentOpen"
				:intent="simplePaymentIntent"
				@close="closeSimplePayment"
				@saved="handleSimplePaymentSaved"
				@open-native="openNativePayment"
			/>

			<SimplePurchaseInvoiceDialog
				:open="simplePurchaseInvoiceOpen"
				@close="closeSimplePurchaseInvoice"
				@saved="handleSimplePurchaseInvoiceSaved"
				@open-native="openNativePurchaseInvoice"
			/>

			<SimpleCashierExpenseDialog
				:open="simpleCashierExpenseOpen"
				@close="closeSimpleCashierExpense"
				@saved="handleSimpleCashierExpenseSaved"
				@open-native="openNativeCashierExpense"
			/>

			<SimpleStockTransferDialog
				:open="simpleStockTransferOpen"
				@close="closeSimpleStockTransfer"
				@saved="handleSimpleStockTransferSaved"
				@open-native="openNativeStockTransfer"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import SimpleCashierExpenseDialog from "./SimpleCashierExpenseDialog.vue";
import SimplePaymentDialog from "./SimplePaymentDialog.vue";
import SimplePurchaseInvoiceDialog from "./SimplePurchaseInvoiceDialog.vue";
import SimpleSalesInvoiceDialog from "./SimpleSalesInvoiceDialog.vue";
import SimpleStockTransferDialog from "./SimpleStockTransferDialog.vue";

const CONTEXT_METHOD = "retailedge.edgesuite_ui.get_retailedge_business_hub_context";
const CONTEXT_CACHE_TTL_MS = 30_000;
const GUIDED_PAYMENT_ACTIONS = new Set(["receive-customer-payment", "pay-supplier"]);
const GUIDED_PURCHASE_ACTION = "record-purchase";
const GUIDED_EXPENSE_ACTION = "record-expense";
const GUIDED_STOCK_TRANSFER_ACTION = "transfer-stock";
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
		EdgeModal: runtimeComponents.EdgeModal,
		SimpleCashierExpenseDialog,
		SimplePaymentDialog,
		SimplePurchaseInvoiceDialog,
		SimpleSalesInvoiceDialog,
		SimpleStockTransferDialog,
	},
	data() {
		return {
			loading: true,
			error: "",
			createPickerOpen: false,
			simpleSalesInvoiceOpen: false,
			simplePaymentOpen: false,
			simplePaymentIntent: "",
			simplePurchaseInvoiceOpen: false,
			simpleCashierExpenseOpen: false,
			simpleStockTransferOpen: false,
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
		openCreatePicker() {
			if (!this.quickActions.length) return;
			this.createPickerOpen = true;
		},
		closeCreatePicker() {
			this.createPickerOpen = false;
		},
		runQuickAction(action) {
			if (!action || !action.doctype) return;
			this.closeCreatePicker();
			if (action.key === "new-sales-invoice") {
				this.simpleSalesInvoiceOpen = true;
				return;
			}
			if (GUIDED_PAYMENT_ACTIONS.has(action.key)) {
				this.simplePaymentIntent = action.key;
				this.simplePaymentOpen = true;
				return;
			}
			if (action.key === GUIDED_PURCHASE_ACTION) {
				this.simplePurchaseInvoiceOpen = true;
				return;
			}
			if (action.key === GUIDED_EXPENSE_ACTION) {
				this.simpleCashierExpenseOpen = true;
				return;
			}
			if (action.key === GUIDED_STOCK_TRANSFER_ACTION) {
				this.simpleStockTransferOpen = true;
				return;
			}
			frappe.new_doc(action.doctype);
		},
		closeSimpleSalesInvoice() {
			this.simpleSalesInvoiceOpen = false;
		},
		handleSimpleSalesInvoiceSaved(result) {
			this.simpleSalesInvoiceOpen = false;
			if (!result?.name) return;
			frappe.show_alert?.({
				message: `Sales Invoice ${result.name} saved as Draft`,
				indicator: "green",
			});
			frappe.set_route("Form", result.doctype || "Sales Invoice", result.name);
		},
		openNativeSalesInvoice(doctype = "Sales Invoice") {
			this.simpleSalesInvoiceOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimplePayment() {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
		},
		handleSimplePaymentSaved(result) {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			if (!result?.name) return;
			frappe.show_alert?.({
				message: `Payment Entry ${result.name} saved as Draft`,
				indicator: "green",
			});
			frappe.set_route("Form", result.doctype || "Payment Entry", result.name);
		},
		openNativePayment(doctype = "Payment Entry") {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			frappe.new_doc(doctype);
		},
		closeSimplePurchaseInvoice() {
			this.simplePurchaseInvoiceOpen = false;
		},
		handleSimplePurchaseInvoiceSaved(result) {
			this.simplePurchaseInvoiceOpen = false;
			if (!result?.name) return;
			frappe.show_alert?.({
				message: `Purchase Invoice ${result.name} saved as Draft`,
				indicator: "green",
			});
			frappe.set_route("Form", result.doctype || "Purchase Invoice", result.name);
		},
		openNativePurchaseInvoice(doctype = "Purchase Invoice") {
			this.simplePurchaseInvoiceOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimpleCashierExpense() {
			this.simpleCashierExpenseOpen = false;
		},
		handleSimpleCashierExpenseSaved(result) {
			this.simpleCashierExpenseOpen = false;
			if (!result?.name) return;
			frappe.show_alert?.({
				message: `Cashier Expense ${result.name} saved`,
				indicator: "green",
			});
			frappe.set_route("Form", result.doctype || "RetailEdge Cashier Expense", result.name);
		},
		openNativeCashierExpense(doctype = "RetailEdge Cashier Expense") {
			this.simpleCashierExpenseOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimpleStockTransfer() {
			this.simpleStockTransferOpen = false;
		},
		handleSimpleStockTransferSaved(result) {
			this.simpleStockTransferOpen = false;
			if (!result?.name) return;
			frappe.show_alert?.({
				message: `Stock Transfer ${result.name} saved as Draft`,
				indicator: "green",
			});
			frappe.set_route("Form", result.doctype || "Stock Entry", result.name);
		},
		openNativeStockTransfer(doctype = "Stock Entry") {
			this.simpleStockTransferOpen = false;
			frappe.new_doc(doctype, { stock_entry_type: "Material Transfer" });
		},
		navigateFromShell(item) {
			if (!item?.route) return;
			if (item.route.startsWith("/app/")) {
				frappe.set_route(item.route.replace(/^\/app\//, ""));
				return;
			}
			window.location.href = item.route;
		},
		routeForTarget(item) {
			if (!item) return "";
			if (item.route) return item.route;
			if (!item.target) return "";
			if (item.type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.type === "Page") return `/app/${frappe.router.slug(item.target)}`;
			if (item.type === "DocType") return `/app/${frappe.router.slug(item.target)}`;
			return "";
		},
		iconText(icon) {
			return (icon || "•")
				.split("-")
				.map((part) => part.charAt(0).toUpperCase())
				.join("")
				.slice(0, 2);
		},
		actionModeLabel(action) {
			if (action?.mode === "available") return "RetailEdge entry";
			return action?.mode === "available" ? "RetailEdge entry" : "Full form";
		},
	},
};
</script>
