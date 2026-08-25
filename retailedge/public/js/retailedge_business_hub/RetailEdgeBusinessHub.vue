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
					title="Business Hub"
					subtitle="Navigate, act, operate, understand, and respond from one business-focused workspace."
					:withBackButton="false"
				/>
			</template>

			<div v-if="loading" class="hub-state">
				<EdgeLoadingState message="Loading your permitted business tools..." :skeleton="true" />
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
							Use the business menu for daily operations. The Create action shows only business
							entries your current permissions allow, while guided flows keep ERPNext documents
							and accounting truth underneath.
						</p>
					</div>
					<div class="hub-banner-side">
						<div class="hub-context">
							<span v-if="context.company">{{ context.company }}</span>
							<span v-if="context.branch">{{ context.branch }}</span>
						</div>
						<button
							v-if="quickActions.length"
							type="button"
							class="edge-button edge-button--primary hub-create-button"
							@click="openCreatePicker"
						>
							+ Create
						</button>
					</div>
				</section>

				<section>
					<div class="section-heading">
						<div>
							<p class="section-kicker">Business workflow</p>
							<h3>Five connected experiences</h3>
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
								<EdgeStatusBadge :label="experience.status" :status="experience.status" />
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

			<SimpleCashDepositDialog
				:open="simpleCashDepositOpen"
				@close="closeSimpleCashDeposit"
				@saved="handleSimpleCashDepositSaved"
				@open-native="openNativeCashDeposit"
			/>

			<SimpleCashTransferDialog
				:open="simpleCashTransferOpen"
				@close="closeSimpleCashTransfer"
				@saved="handleSimpleCashTransferSaved"
				@open-native="openNativeCashTransfer"
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

			<SimpleStockAdjustmentDialog
				:open="simpleStockAdjustmentOpen"
				@close="closeSimpleStockAdjustment"
				@saved="handleSimpleStockAdjustmentSaved"
				@open-native="openNativeStockAdjustment"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import SimpleCashDepositDialog from "./SimpleCashDepositDialog.vue";
import SimpleCashTransferDialog from "./SimpleCashTransferDialog.vue";
import SimpleCashierExpenseDialog from "./SimpleCashierExpenseDialog.vue";
import SimplePaymentDialog from "./SimplePaymentDialog.vue";
import SimplePurchaseInvoiceDialog from "./SimplePurchaseInvoiceDialog.vue";
import SimpleSalesInvoiceDialog from "./SimpleSalesInvoiceDialog.vue";
import SimpleStockAdjustmentDialog from "./SimpleStockAdjustmentDialog.vue";
import SimpleStockTransferDialog from "./SimpleStockTransferDialog.vue";

const CONTEXT_METHOD = "retailedge.edgesuite_ui.get_retailedge_business_hub_context";
const WORKFLOW_READINESS_METHOD = "retailedge.workflow_readiness.get_document_workflow_readiness";
const CONTEXT_CACHE_TTL_MS = 30_000;
const GUIDED_PAYMENT_ACTIONS = new Set(["receive-customer-payment", "pay-supplier"]);
const GUIDED_CASH_DEPOSIT_ACTION = "deposit-cash";
const GUIDED_CASH_TRANSFER_ACTION = "cash-transfer";
const GUIDED_PURCHASE_ACTION = "record-purchase";
const GUIDED_EXPENSE_ACTION = "record-expense";
const GUIDED_STOCK_TRANSFER_ACTION = "transfer-stock";
const GUIDED_STOCK_ADJUSTMENT_ACTION = "adjust-stock";
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
	window.__retailedgeBusinessHubContextCache = { data: normalized, fetchedAt: Date.now() };
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
		SimpleCashDepositDialog,
		SimpleCashTransferDialog,
		SimpleCashierExpenseDialog,
		SimplePaymentDialog,
		SimplePurchaseInvoiceDialog,
		SimpleSalesInvoiceDialog,
		SimpleStockAdjustmentDialog,
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
			simpleCashDepositOpen: false,
			simpleCashTransferOpen: false,
			simplePurchaseInvoiceOpen: false,
			simpleCashierExpenseOpen: false,
			simpleStockTransferOpen: false,
			simpleStockAdjustmentOpen: false,
			programmeExperiences: [],
			navigationGroups: [],
			quickActions: [],
			context: { user: "", user_name: "", company: "", branch: "" },
			featureFlags: {},
		};
	},
	computed: {
		greeting() {
			return this.context.user_name
				? `Welcome, ${this.context.user_name}`
				: "Your business command centre";
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
			if (!this.quickActions.length) this.createPickerOpen = false;
		},
		refreshContext({ force = false } = {}) {
			this.loading = true;
			this.error = "";
			return fetchSharedContext({ force })
				.then((data) => this.applyContext(data || {}))
				.catch((error) => {
					this.error = error?.message || "Unable to load Business Hub context.";
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
			if (action.key === GUIDED_CASH_DEPOSIT_ACTION) {
				this.simpleCashDepositOpen = true;
				return;
			}
			if (action.key === GUIDED_CASH_TRANSFER_ACTION) {
				this.simpleCashTransferOpen = true;
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
			if (action.key === GUIDED_STOCK_ADJUSTMENT_ACTION) {
				this.simpleStockAdjustmentOpen = true;
				return;
			}
			frappe.new_doc(action.doctype);
		},
		notifyGuidedDraftSaved(result, fallbackDoctype, label) {
			if (!result?.name) return;
			const doctype = result.doctype || fallbackDoctype;
			frappe.set_route("Form", doctype, result.name);
			frappe.call({
				method: WORKFLOW_READINESS_METHOD,
				args: { doctype, name: result.name },
				callback: (response) => {
					const readiness = response.message || {};
					if (!readiness.enabled) {
						frappe.show_alert?.({ message: `${label} ${result.name} saved as Draft`, indicator: "green" });
						return;
					}
					const state = readiness.current_state ? ` Current state: ${readiness.current_state}.` : "";
					const actions = (readiness.available_actions || []).map((item) => item.action).filter(Boolean);
					const next = actions.length
						? ` Available workflow action${actions.length === 1 ? "" : "s"}: ${actions.join(", ")}.`
						: " No workflow action is currently available to you; another authorised user may be required.";
					frappe.show_alert?.({
						message: `${label} ${result.name} saved as Draft. Workflow approval is still required.${state}${next}`,
						indicator: "orange",
					}, 10);
				},
				error: () => {
					frappe.show_alert?.({ message: `${label} ${result.name} saved as Draft`, indicator: "green" });
				},
			});
		},
		closeSimpleSalesInvoice() {
			this.simpleSalesInvoiceOpen = false;
		},
		handleSimpleSalesInvoiceSaved(result) {
			this.simpleSalesInvoiceOpen = false;
			this.notifyGuidedDraftSaved(result, "Sales Invoice", "Sales Invoice");
		},
		openNativeSalesInvoice(doctype = "Sales Invoice") {
			this.simpleSalesInvoiceOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimplePayment() {
			this.simplePaymentOpen = false;
		},
		handleSimplePaymentSaved(result) {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			this.notifyGuidedDraftSaved(result, "Payment Entry", "Payment Entry");
		},
		openNativePayment(doctype = "Payment Entry") {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			frappe.new_doc(doctype);
		},
		closeSimpleCashDeposit() {
			this.simpleCashDepositOpen = false;
		},
		handleSimpleCashDepositSaved(result) {
			this.simpleCashDepositOpen = false;
			this.notifyGuidedDraftSaved(result, "Payment Entry", "Cash Deposit");
		},
		openNativeCashDeposit(doctype = "Payment Entry") {
			this.simpleCashDepositOpen = false;
			frappe.new_doc(doctype, { payment_type: "Internal Transfer" });
		},
		closeSimpleCashTransfer() {
			this.simpleCashTransferOpen = false;
		},
		handleSimpleCashTransferSaved(result) {
			this.simpleCashTransferOpen = false;
			this.notifyGuidedDraftSaved(result, "Payment Entry", "Payment Entry");
		},
		openNativeCashTransfer(doctype = "Payment Entry") {
			this.simpleCashTransferOpen = false;
			frappe.new_doc(doctype, { payment_type: "Internal Transfer" });
		},
		closeSimplePurchaseInvoice() {
			this.simplePurchaseInvoiceOpen = false;
		},
		handleSimplePurchaseInvoiceSaved(result) {
			this.simplePurchaseInvoiceOpen = false;
			this.notifyGuidedDraftSaved(result, "Purchase Invoice", "Purchase Invoice");
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
			this.notifyGuidedDraftSaved(result, "RetailEdge Cashier Expense", "Cashier Expense");
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
			this.notifyGuidedDraftSaved(result, "Stock Entry", "Stock Transfer");
		},
		openNativeStockTransfer(doctype = "Stock Entry") {
			this.simpleStockTransferOpen = false;
			frappe.new_doc(doctype, { stock_entry_type: "Material Transfer" });
		},
		closeSimpleStockAdjustment() {
			this.simpleStockAdjustmentOpen = false;
		},
		handleSimpleStockAdjustmentSaved(result) {
			this.simpleStockAdjustmentOpen = false;
			this.notifyGuidedDraftSaved(result, "Stock Reconciliation", "Stock Reconciliation");
		},
		openNativeStockAdjustment(doctype = "Stock Reconciliation") {
			this.simpleStockAdjustmentOpen = false;
			frappe.new_doc(doctype, { purpose: "Stock Reconciliation" });
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
			if (item.target_type === "Page") frappe.set_route(item.target);
		},
		routeForTarget(item) {
			if (!item) return "";
			if (item.target_type === "URL") return item.target;
			if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "Page") return `/app/${item.target}`;
			return "";
		},
		actionModeLabel(action) {
			return action?.mode === "available" ? "Guided entry" : "Full form";
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
.hub-banner-side,
.hub-context {
	display: flex;
	flex-direction: column;
	align-items: flex-end;
}
.hub-banner-side {
	justify-content: space-between;
	gap: 18px;
	min-width: 180px;
}
.hub-context {
	gap: 6px;
	font-size: 0.82rem;
	color: var(--edge-text-muted, #667085);
}
.hub-create-button {
	min-width: 120px;
	justify-content: center;
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
.experience-grid {
	display: grid;
	grid-template-columns: repeat(5, minmax(0, 1fr));
	gap: 14px;
}
.experience-card {
	padding: 18px;
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-surface, #ffffff);
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
.create-picker-icon {
	font-size: 1.3rem;
}
.create-picker-list {
	display: grid;
	gap: 8px;
}
.create-picker-item {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	align-items: center;
	gap: 12px;
	width: 100%;
	padding: 13px 14px;
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 10px;
	background: var(--edge-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.create-picker-item:hover,
.create-picker-item:focus-visible {
	border-color: var(--edge-primary, #2563eb);
}
.create-picker-copy {
	display: grid;
	gap: 3px;
	min-width: 0;
}
.create-picker-copy small,
.create-picker-mode {
	color: var(--edge-text-muted, #667085);
}
.create-picker-copy small {
	line-height: 1.35;
}
.create-picker-mode {
	font-size: 0.72rem;
	white-space: nowrap;
}
@media (max-width: 1200px) {
	.experience-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
}
@media (max-width: 720px) {
	.hub-banner,
	.section-heading {
		align-items: flex-start;
		flex-direction: column;
	}
	.hub-banner-side,
	.hub-context {
		align-items: flex-start;
	}
	.hub-banner-side {
		width: 100%;
	}
	.experience-grid {
		grid-template-columns: 1fr;
	}
	.create-picker-item {
		grid-template-columns: auto minmax(0, 1fr);
	}
	.create-picker-mode {
		grid-column: 2;
	}
}
</style>
