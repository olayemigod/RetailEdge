<template>
	<EdgeAppShell
		product="retailedge"
		:menuItems="shellMenuItems"
		activeRoute="/app/retailedge-business-hub"
		title="ProcessEdge Retail"
		subtitle="Structured for Scale."
		:tenantName="context.company_label || context.company"
		:branchName="context.branch"
		:userName="context.user_name"
		:hideNativeSidebar="true"
		@navigate="navigateFromShell"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					title="Business Hub"
					subtitle="Today’s priorities, actions and business position."
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
						<p class="hub-rider">Review the selected period, act on exceptions, and continue daily work from one place.</p>
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

				<section class="home-command-centre hub-experience-section">
					<div class="section-heading">
						<div>
							
							<h3>Business performance</h3>
							<p class="section-rider">Key business indicators for the selected period.</p>
						</div>
						<div class="home-period-controls">
							<EdgeSmartDateRange
								v-model="homeSmartDate"
								class="edge-smart-date--align-end"
								label="Period"
								placeholder="e.g. last 30 days, YTD, this month"
								dateOrder="DMY"
								@resolved="handleHomeDateResolved"
							/>
							<span v-if="homePeriod.from_date" class="home-as-of">{{ formatDisplayDate(homePeriod.from_date) }} – {{ formatDisplayDate(homePeriod.to_date) }}</span>
						</div>
					</div>
					<EdgeLoadingState v-if="homeLoading" message="Loading business performance..." :skeleton="true" />
					<EdgeErrorState v-else-if="homeError" title="Business snapshot unavailable" :message="homeError" @retry="refreshHomeSnapshot" />
					<div v-else>
						<div v-if="homeSnapshot.cards.length" class="home-kpi-grid">
							<button
								v-for="card in homeSnapshot.cards"
								:key="card.label"
								type="button"
								class="home-kpi-card"
								@click="openHomeRoute(card.route, homeRouteFilters(card))"
							>
								<span class="home-kpi-card-heading">
									<span>{{ card.label }}</span>
									<span class="home-kpi-card-icon"><EdgeIcon :name="kpiIcon(card.label)" size="sm" /></span>
								</span>
								<strong :title="formatHomeValue(card, { compact: false })">{{ formatHomeValue(card) }}</strong>
								<small>{{ card.time_basis === "current" ? "Current position" : (homePeriod.label || "Selected period") }}</small>
							</button>
						</div>
						<EdgeEmptyState
							v-else
							title="No management indicators available"
							description="No permitted indicators are available for this period and operating scope."
							icon="bar-chart-2"
						/>
					</div>
				</section>

				<section class="hub-experience-section home-visuals-section">
					<div class="section-heading">
						<div>
							<h3>Business overview</h3>
							<p class="section-rider">Visualise sales, cash, expenses, exposure and stock health for the current operating scope.</p>
						</div>
					</div>
					<EdgeLoadingState v-if="visualLoading" message="Loading business visuals..." :skeleton="true" />
					<EdgeErrorState v-else-if="visualError" title="Business visuals unavailable" :message="visualError" @retry="refreshHomeVisuals" />
					<div v-else-if="homeVisuals.length" class="home-visual-grid">
						<BusinessHubChartCard
							v-for="chart in homeVisuals"
							:key="chart.key"
							:chart="chart"
							:wide="chart.key === 'sales_trend'"
							@open="openHomeVisual"
							@drill="drillHomeVisual"
						/>
					</div>
					<EdgeEmptyState
						v-else
						title="No business visuals available"
						description="No permitted visual dataset is available for the selected Company, Branch and period."
						icon="bar-chart-2"
					/>
				</section>

				<section v-if="homeQuickActions.length" class="home-quick-actions-section hub-experience-section">
					<div class="section-heading">
						<div>
							
							<h3>Quick actions</h3>
							<p class="section-rider">Start the next permitted business task.</p>
						</div>
					</div>
					<div class="home-quick-actions-grid">
						<button
							v-for="shortcut in homeQuickActions"
							:key="shortcut.key"
							type="button"
							class="home-quick-action"
							@click="runHomeQuickAction(shortcut)"
						>
							<span class="home-quick-action-icon"><EdgeIcon :name="displayIcon(shortcut.icon)" size="sm" /></span>
							<span>
								<strong>{{ shortcut.label }}</strong>
								<small>{{ shortcut.description }}</small>
							</span>
						</button>
					</div>
				</section>

				<section class="hub-experience-section">
					<div class="section-heading">
						<div>
							
							<h3>Business indices</h3>
							<p class="section-rider">Sales, cash, stock, expenses, receivables, payables, branch and banking signals with the next useful action.</p>
						</div>
					</div>
					<div v-if="homeSnapshot.indices.length" class="home-intelligence-grid">
						<article
							v-for="index in homeSnapshot.indices"
							:key="index.key"
							:class="['home-intelligence-card', `tone-${index.tone || 'neutral'}`, { 'is-unavailable': !index.available }]"
						>
							<div class="home-intelligence-heading">
								<h4><span class="home-signal-icon"><EdgeIcon :name="signalIcon(index.key)" size="sm" /></span>{{ index.label }}</h4>
								<span :class="['home-index-status', `tone-${index.tone || 'neutral'}`]">{{ indexStatusLabel(index) }}</span>
							</div>
							<template v-if="index.available">
								<div class="home-index-headline">
									<span>{{ index.headline?.label || "Position" }}</span>
									<strong :title="formatHomeValue(index.headline, { compact: false })">{{ formatHomeValue(index.headline) }}</strong>
								</div>
								<div v-if="index.signal?.label" class="home-index-signal">
									<span>{{ index.signal.label }}</span>
									<strong :title="formatHomeValue(index.signal, { compact: false })">{{ formatHomeValue(index.signal) }}</strong>
								</div>
								<p>{{ index.signal?.message || index.recommendation }}</p>
								<button type="button" class="home-index-action" @click="openHomeItem(index)">{{ index.action_label || "Open" }}</button>
							</template>
							<p v-else class="home-unavailable">{{ index.reason || "This index is unavailable for your current permissions and scope." }}</p>
						</article>
					</div>
					<EdgeEmptyState
						v-else
						title="No business indices available"
						description="No permitted business index is available for the selected Company, Branch and period."
						icon="bar-chart-2"
					/>
				</section>

				<section class="hub-experience-section">
					<div class="section-heading">
						<div>
							
							<h3>Needs attention</h3>
							<p class="section-rider">Exceptions and follow-ups that may require action.</p>
						</div>
						<span class="home-attention-count">{{ homeSnapshot.attention.length }}</span>
					</div>
					<div v-if="homeSnapshot.attention.length" class="home-attention-list home-attention-list--wide">
						<button v-for="(item, index) in homeSnapshot.attention" :key="`${item.section || 'attention'}-${index}`" type="button" :class="['home-attention-item', `tone-${item.tone || 'warning'}`]" @click="openHomeItem(item)">
							<span class="home-attention-copy">
								<strong>{{ item.label }}</strong>
								<small v-if="item.recommendation">{{ item.recommendation }}</small>
							</span>
							<span class="home-attention-value">
								<strong :title="formatHomeValue(item, { compact: false })">{{ formatHomeValue(item) }}</strong>
								<small>{{ item.action_label || "Open" }}</small>
							</span>
						</button>
					</div>
					<EdgeEmptyState
						v-else
						title="Nothing needs attention"
						description="No current exception or follow-up item was found in your permitted scope."
						icon="check-circle"
					/>
				</section>
			</div>

			<EdgeModal
				:open="createPickerOpen"
				title="Create"
				subtitle="Choose the business entry you want to record. Only entries you can create are shown."
				size="md"
				@close="closeCreatePicker"
			>
				<div v-if="quickActions.length" class="create-product-menu">
					<header class="create-product-menu-header edge-product-menu__header">
						<div class="edge-product-menu__brand">
							<span class="create-product-menu-mark edge-product-menu__brand-mark"><EdgeIcon name="clipboard" size="sm" /></span>
							<span>
								<strong>Create</strong>
								<small>Retail business actions</small>
							</span>
						</div>
					</header>
					<section class="edge-product-menu__section" aria-label="Permitted business actions">
						<div class="edge-product-menu__section-heading">
							<span class="edge-product-menu__section-icon"><EdgeIcon name="activity" size="sm" /></span>
							<span>
								<h3>Business actions</h3>
								<p>Only entries permitted for your current role and context are shown.</p>
							</span>
						</div>
						<div class="create-picker-list edge-product-menu__items">
							<button
								v-for="action in quickActions"
								:key="action.key"
								type="button"
								class="create-picker-item edge-product-menu__item"
								role="menuitem"
								@click="runQuickAction(action)"
							>
								<span class="create-picker-icon edge-product-menu__item-icon"><EdgeIcon :name="displayIcon(action.icon)" size="sm" /></span>
								<span class="create-picker-copy edge-product-menu__item-copy">
									<strong>{{ action.label }}</strong>
									<small>{{ action.description }}</small>
								</span>
								<span class="create-picker-mode edge-product-menu__item-badge">{{ actionModeLabel(action) }}</span>
							</button>
						</div>
					</section>
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
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleSalesInvoice"
				@saved="handleSimpleSalesInvoiceSaved"
				@open-native="openNativeSalesInvoice"
			/>
			<StandardSalesInvoiceCompletionDialog
				:open="salesInvoiceCompletionOpen"
				:document="salesInvoiceCompletionDocument"
				:canUseNativeDesk="nativeFallbackEnabled"
				@close="closeSalesInvoiceCompletion"
				@changed="handleSalesInvoiceCompletionChanged"
				@completed="handleSalesInvoiceCompletionCompleted"
			/>

			<SimplePaymentDialog
				:open="simplePaymentOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				:intent="simplePaymentIntent"
				@close="closeSimplePayment"
				@saved="handleSimplePaymentSaved"
				@open-native="openNativePayment"
			/>

			<SimpleCashDepositDialog
				:open="simpleCashDepositOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleCashDeposit"
				@saved="handleSimpleCashDepositSaved"
				@open-native="openNativeCashDeposit"
			/>
			<StandardInternalTransferCompletionDialog
				:open="internalTransferCompletionOpen"
				:document="internalTransferCompletionDocument"
				:canUseNativeDesk="nativeFallbackEnabled"
				@close="closeInternalTransferCompletion"
				@changed="handleInternalTransferCompletionChanged"
				@completed="handleInternalTransferCompletionCompleted"
			/>

			<SimpleCashTransferDialog
				:open="simpleCashTransferOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleCashTransfer"
				@saved="handleSimpleCashTransferSaved"
				@open-native="openNativeCashTransfer"
			/>

			<SimplePurchaseInvoiceDialog
				:open="simplePurchaseInvoiceOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimplePurchaseInvoice"
				@saved="handleSimplePurchaseInvoiceSaved"
				@open-native="openNativePurchaseInvoice"
			/>
			<StandardPurchaseInvoiceCompletionDialog
				:open="purchaseInvoiceCompletionOpen"
				:document="purchaseInvoiceCompletionDocument"
				:canUseNativeDesk="nativeFallbackEnabled"
				@close="closePurchaseInvoiceCompletion"
				@changed="handlePurchaseInvoiceCompletionChanged"
				@completed="handlePurchaseInvoiceCompletionCompleted"
			/>

			<SimpleCashierExpenseDialog
				:open="simpleCashierExpenseOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleCashierExpense"
				@saved="handleSimpleCashierExpenseSaved"
				@open-native="openNativeCashierExpense"
			/>
			<GuidedWorkflowCompletionDialog
				:open="cashierExpenseCompletionOpen"
				:document="cashierExpenseCompletionDocument"
				label="Cashier Expense"
				:canUseNativeDesk="nativeFallbackEnabled"
				@close="closeCashierExpenseCompletion"
				@changed="handleCashierExpenseCompletionChanged"
				@completed="handleCashierExpenseCompletionCompleted"
			/>

			<SimpleStockTransferDialog
				:open="simpleStockTransferOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleStockTransfer"
				@saved="handleSimpleStockTransferSaved"
				@open-native="openNativeStockTransfer"
			/>

			<SimpleStockAdjustmentDialog
				:open="simpleStockAdjustmentOpen"
				:native-fallback-enabled="nativeFallbackEnabled"
				@close="closeSimpleStockAdjustment"
				@saved="handleSimpleStockAdjustmentSaved"
				@open-native="openNativeStockAdjustment"
			/>
			<StandardStockCompletionDialog
				:open="stockCompletionOpen"
				:document="stockCompletionDocument"
				:canUseNativeDesk="nativeFallbackEnabled"
				@close="closeStockCompletion"
				@changed="handleStockCompletionChanged"
				@completed="handleStockCompletionCompleted"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import SimpleCashDepositDialog from "./SimpleCashDepositDialog.vue";
import StandardInternalTransferCompletionDialog from "./StandardInternalTransferCompletionDialog.vue";
import SimpleCashTransferDialog from "./SimpleCashTransferDialog.vue";
import SimpleCashierExpenseDialog from "./SimpleCashierExpenseDialog.vue";
import GuidedWorkflowCompletionDialog from "./GuidedWorkflowCompletionDialog.vue";
import SimplePaymentDialog from "./SimplePaymentDialog.vue";
import SimplePurchaseInvoiceDialog from "./SimplePurchaseInvoiceDialog.vue";
import StandardPurchaseInvoiceCompletionDialog from "../professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue";
import SimpleSalesInvoiceDialog from "./SimpleSalesInvoiceDialog.vue";
import StandardSalesInvoiceCompletionDialog from "../professional_selling/StandardSalesInvoiceCompletionDialog.vue";
import SimpleStockAdjustmentDialog from "./SimpleStockAdjustmentDialog.vue";
import SimpleStockTransferDialog from "./SimpleStockTransferDialog.vue";
import StandardStockCompletionDialog from "./StandardStockCompletionDialog.vue";
import BusinessHubChartCard from "./BusinessHubChartCard.vue";
import { openQuickEntryMaster } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const HOME_SNAPSHOT_METHOD = "retailedge.business_hub_home.get_business_hub_home_snapshot";
const HOME_VISUALS_METHOD = "retailedge.business_hub_visuals.get_business_hub_visuals";
const WORKFLOW_READINESS_METHOD = "retailedge.workflow_readiness.get_document_workflow_readiness";
const CONTEXT_CACHE_TTL_MS = 30_000;
const GUIDED_PAYMENT_ACTIONS = new Set(["receive-customer-payment", "pay-supplier"]);
const GUIDED_CASH_DEPOSIT_ACTION = "deposit-cash";
const GUIDED_CASH_TRANSFER_ACTION = "cash-transfer";
const GUIDED_PURCHASE_ACTION = "record-purchase";
const GUIDED_EXPENSE_ACTION = "record-expense";
const GUIDED_STOCK_TRANSFER_ACTION = "transfer-stock";
const GUIDED_STOCK_ADJUSTMENT_ACTION = "adjust-stock";
const QUICK_ENTRY_MASTER_ACTIONS = Object.freeze({
	"new-customer": "Customer",
	"new-supplier": "Supplier",
	"new-item": "Item",
});
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

function fetchHomeSnapshot(company, branch, datePreset, resolvedRange = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: HOME_SNAPSHOT_METHOD,
			args: {
				company: company || "",
				branch: branch || "",
				date_preset: datePreset || "Today",
				from_date: resolvedRange?.from_date || "",
				to_date: resolvedRange?.to_date || "",
				date_label: resolvedRange?.expression && resolvedRange.expression !== "custom"
					? resolvedRange.expression
					: (resolvedRange?.label || resolvedRange?.display_value || ""),
			},
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function fetchHomeVisuals(company, branch, period = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: HOME_VISUALS_METHOD,
			args: {
				company: company || "",
				branch: branch || "",
				from_date: period?.from_date || "",
				to_date: period?.to_date || "",
			},
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function routeTarget(route) {
	return String(route || "").replace(/^\/app\//, "").split("/").filter(Boolean)[0] || "";
}

function setBusinessHubRouteHandoff(route, filters = {}) {
	const target = routeTarget(route);
	if (!target) return;
	const cleanFilters = Object.fromEntries(
		Object.entries(filters || {}).filter(([, value]) => value !== undefined && value !== null && value !== "")
	);
	window.__retailedgeBusinessHubRouteHandoff = {
		target,
		filters: cleanFilters,
		createdAt: Date.now(),
	};
	frappe.route_options = {
		...cleanFilters,
		retailedge_business_hub_handoff: 1,
		retailedge_business_hub_target: target,
	};
}

window.retailedgeConsumeBusinessHubRouteOptions = function consumeBusinessHubRouteOptions(target) {
	const handoff = window.__retailedgeBusinessHubRouteHandoff;
	if (!handoff || Date.now() - Number(handoff.createdAt || 0) > 60_000) {
		delete window.__retailedgeBusinessHubRouteHandoff;
		return {};
	}
	if (String(handoff.target || "") !== String(target || "")) return {};
	const filters = { ...(handoff.filters || {}) };
	delete window.__retailedgeBusinessHubRouteHandoff;
	if (frappe.route_options?.retailedge_business_hub_handoff) frappe.route_options = null;
	return filters;
};

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
		EdgeIcon: runtimeComponents.EdgeIcon,
		EdgeSmartDateRange: runtimeComponents.EdgeSmartDateRange,
		SimpleCashDepositDialog,
		StandardInternalTransferCompletionDialog,
		SimpleCashTransferDialog,
		SimpleCashierExpenseDialog,
		GuidedWorkflowCompletionDialog,
		SimplePaymentDialog,
		SimplePurchaseInvoiceDialog,
		StandardPurchaseInvoiceCompletionDialog,
		SimpleSalesInvoiceDialog,
		StandardSalesInvoiceCompletionDialog,
		SimpleStockAdjustmentDialog,
		SimpleStockTransferDialog,
		StandardStockCompletionDialog,
		BusinessHubChartCard,
	},
	data() {
		return {
			loading: true,
			error: "",
			homeLoading: false,
			homeError: "",
			visualLoading: false,
			visualError: "",
			homeVisuals: [],
			homeSnapshot: { as_of_date: "", period: {}, cards: [], sections: {}, indices: [], settings: {}, attention: [] },
			homePeriodPreset: "Today",
			homeSmartDate: {},
			homePeriod: { preset: "Today", label: "Today", from_date: "", to_date: "" },
			createPickerOpen: false,
			simpleSalesInvoiceOpen: false,
			salesInvoiceCompletionOpen: false,
			salesInvoiceCompletionDocument: null,
			simplePaymentOpen: false,
			simplePaymentIntent: "",
			simpleCashDepositOpen: false,
			internalTransferCompletionOpen: false,
			internalTransferCompletionDocument: null,
			simpleCashTransferOpen: false,
			simplePurchaseInvoiceOpen: false,
			purchaseInvoiceCompletionOpen: false,
			purchaseInvoiceCompletionDocument: null,
			simpleCashierExpenseOpen: false,
			cashierExpenseCompletionOpen: false,
			cashierExpenseCompletionDocument: null,
			simpleStockTransferOpen: false,
			simpleStockAdjustmentOpen: false,
			stockCompletionOpen: false,
			stockCompletionDocument: null,
			navigationGroups: [],
			quickActions: [],
			context: { user: "", user_name: "", company: "", company_label: "", company_logo: "", company_currency: "", branch: "" },
			featureFlags: {},
			accessContext: { mode: "native_desk", restricted_to_edgesuite: false, can_use_native_desk: true },
		};
	},
	computed: {
		greeting() {
			return this.context.user_name
				? `Welcome, ${this.context.user_name}`
				: "Your business command centre";
		},
		nativeFallbackEnabled() {
			return (
				this.accessContext.can_use_native_desk !== false &&
				this.featureFlags.native_document_fallback_enabled !== false
			);
		},
		homeQuickActions() {
			const byKey = new Map((this.quickActions || []).map((action) => [action.key, action]));
			const pageTargets = new Set(
				(this.navigationGroups || [])
					.flatMap((group) => group.items || [])
					.filter((item) => item.target_type === "Page")
					.map((item) => item.target)
			);
			const shortcuts = [];
			const addAction = (key, label = "") => {
				const action = byKey.get(key);
				if (!action) return;
				shortcuts.push({
					key: `action:${key}`,
					kind: "action",
					label: label || action.label,
					description: action.description || "",
					icon: action.icon || "zap",
					action,
				});
			};
			const addPage = (target, label, description, icon) => {
				if (!pageTargets.has(target)) return;
				shortcuts.push({
					key: `page:${target}`,
					kind: "page",
					target,
					label,
					description,
					icon,
				});
			};
			addAction("new-sales-invoice", "Make Sale");
			addAction("receive-customer-payment");
			addAction("pay-supplier");
			addAction("record-expense");
			addPage("professional-purchasing", "Receive Stock", "Open ready-to-receive Purchase Orders and prepare Purchase Receipts.", "download");
			addAction("transfer-stock");
			addAction("record-purchase");
			addPage("bank-matching-reconciliation", "Match Bank Transactions", "Review imported bank transactions, suggestions and reconciliation queues.", "repeat");
			return shortcuts;
		},
		shellMenuItems() {
			return this.navigationGroups
				.map((group) => ({
					key: group.key,
					label: group.label,
					icon: group.icon || "layers",
					defaultCollapsed: group.key !== "home",
					items: (group.items || [])
						.filter((item) => this.nativeFallbackEnabled || !["DocType", "Report"].includes(item.target_type))
						.map((item) => ({
							label: item.label,
							description: item.description || "",
							route: this.routeForTarget(item),
							icon: item.icon || "list",
							link_type: item.target_type,
							link_to: item.target,
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
			this.navigationGroups = data.navigation_groups || [];
			this.quickActions = data.quick_actions || [];
			this.context = { ...this.context, ...(data.context || {}) };
			if (typeof window.retailedgeSyncShellIdentity === "function") {
				window.retailedgeSyncShellIdentity({
					active_company: this.context.company || "",
					active_branch: this.context.branch || "",
					branch_options: Array.isArray(this.context.branch_options) ? this.context.branch_options : [],
					can_switch_branch: Boolean(this.context.can_switch_branch),
				});
			}
			this.featureFlags = data.feature_flags || {};
			this.accessContext = { ...this.accessContext, ...(data.access || {}) };
			if (!this.quickActions.length) this.createPickerOpen = false;
		},
		refreshContext({ force = false } = {}) {
			this.loading = true;
			this.error = "";
			return fetchSharedContext({ force })
				.then((data) => {
					this.applyContext(data || {});
					return this.refreshHomeSnapshot();
				})
				.catch((error) => {
					this.error = error?.message || "Unable to load Business Hub context.";
				})
				.finally(() => {
					this.loading = false;
				});
		},
		refreshHomeSnapshot(resolvedRange = null) {
			if (!this.context.company) {
				this.homeSnapshot = { as_of_date: "", period: {}, cards: [], sections: {}, indices: [], settings: {}, attention: [] };
				this.homeVisuals = [];
				this.visualError = "";
				return Promise.resolve();
			}
			this.homeLoading = true;
			this.homeError = "";
			const range = resolvedRange || this.homeSmartDate || {};
			return fetchHomeSnapshot(this.context.company, this.context.branch, this.homePeriodPreset, range)
				.then((snapshot) => {
					this.homePeriod = { ...this.homePeriod, ...(snapshot.period || {}) };
					this.homePeriodPreset = this.homePeriod.preset || this.homePeriodPreset;
					this.homeSmartDate = {
						...this.homeSmartDate,
						expression: this.homeSmartDate.expression
							|| (this.homePeriod.preset === "Custom Period" ? "custom" : this.homePeriod.preset || "Today"),
						from_date: this.homePeriod.from_date || "",
						to_date: this.homePeriod.to_date || "",
						label: this.homePeriod.label || "",
					};
					this.homeSnapshot = {
						as_of_date: snapshot.as_of_date || "",
						period: snapshot.period || {},
						cards: snapshot.cards || [],
						sections: snapshot.sections || {},
						indices: snapshot.indices || [],
						settings: snapshot.settings || {},
						attention: snapshot.attention || [],
					};
					this.refreshHomeVisuals();
				})
				.catch((error) => {
					this.homeSnapshot = { as_of_date: "", cards: [], sections: {}, indices: [], settings: {}, attention: [] };
					this.homeError = error?.message || "Unable to load the current business snapshot.";
				})
				.finally(() => {
					this.homeLoading = false;
				});
		},
		refreshHomeVisuals() {
			if (!this.context.company || !this.homePeriod.from_date || !this.homePeriod.to_date) {
				this.homeVisuals = [];
				this.visualError = "";
				return Promise.resolve();
			}
			this.visualLoading = true;
			this.visualError = "";
			return fetchHomeVisuals(this.context.company, this.context.branch, this.homePeriod)
				.then((payload) => {
					this.homeVisuals = payload.visuals || [];
				})
				.catch((error) => {
					this.homeVisuals = [];
					this.visualError = error?.message || "Unable to load business visuals.";
				})
				.finally(() => {
					this.visualLoading = false;
				});
		},
		openHomeVisual(chart) {
			if (!chart?.route) return;
			this.openHomeRoute(chart.route, chart.route_filters || {});
		},
		drillHomeVisual(chart, row, series) {
			if (!chart?.route || !row) return;
			let route = chart.route;
			if (chart.key === "exposure" && series?.key === "payables" && chart.secondary_route) {
				route = chart.secondary_route;
			}
			const filters = { ...(chart.route_filters || {}) };
			if (row.from_date && row.to_date) {
				filters.from_date = row.from_date;
				filters.to_date = row.to_date;
			}
			if (row.drill_field && row.drill_value) {
				filters[row.drill_field] = row.drill_value;
			}
			this.openHomeRoute(route, filters);
		},
		handleHomeDateResolved(value) {
			if (!value?.from_date || !value?.to_date) return;
			this.homeSmartDate = { ...(value || {}) };
			this.homePeriodPreset = "Custom Period";
			return this.refreshHomeSnapshot(value);
		},
		handleHomePeriodChange(value) {
			// Compatibility hook for older cached bundles.
			this.homePeriodPreset = value || "Today";
			this.homeSmartDate = {};
			return this.refreshHomeSnapshot();
		},
		formatDisplayDate(value) {
			const text = String(value || "").trim();
			const iso = /^(\d{4})-(\d{2})-(\d{2})$/.exec(text);
			if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
			return frappe.datetime?.str_to_user?.(text) || text;
		},
		homeSection(key) {
			return this.homeSnapshot.sections?.[key] || { available: false, label: key, summary: [], route: "", reason: "" };
		},
		compactNumber(value, { maximumFractionDigits = 2 } = {}) {
			const number = Number(value || 0);
			if (!Number.isFinite(number)) return String(value ?? "");
			const absolute = Math.abs(number);
			if (absolute < 100000) return number.toLocaleString(undefined, { maximumFractionDigits });
			try {
				return new Intl.NumberFormat(undefined, {
					notation: "compact",
					compactDisplay: "short",
					maximumFractionDigits,
				}).format(number);
			} catch (_error) {
				const units = [
					{ value: 1e12, suffix: "T" },
					{ value: 1e9, suffix: "B" },
					{ value: 1e6, suffix: "M" },
					{ value: 1e3, suffix: "K" },
				];
				const unit = units.find((row) => absolute >= row.value);
				if (!unit) return number.toLocaleString(undefined, { maximumFractionDigits });
				const scaled = (number / unit.value).toFixed(maximumFractionDigits).replace(/\.0+$|(?<=\.[0-9])0+$/g, "");
				return `${scaled}${unit.suffix}`;
			}
		},
		currencyMark() {
			const formatter = window.retailedge?.formatPlainValue;
			if (!formatter) return "";
			try {
				return String(formatter(0, { fieldtype: "Currency" }) || "")
					.replace(/[0-9.,\s()+-]/g, "")
					.trim();
			} catch (_error) {
				return "";
			}
		},
		formatHomeValue(card, { compact = true } = {}) {
			const value = card?.value ?? 0;
			const datatype = card?.datatype || card?.type || "Data";
			if (datatype === "Currency") {
				const number = Number(value || 0);
				const formatter = window.retailedge?.formatPlainValue;
				if (!compact || Math.abs(number) < 100000) {
					if (formatter) return formatter(value, { fieldtype: "Currency" });
					return number.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
				}
				const mark = this.currencyMark();
				const amount = this.compactNumber(number, { maximumFractionDigits: 2 });
				return mark ? `${mark} ${amount}` : amount;
			}
			if (datatype === "Percent") return `${Number(value || 0).toLocaleString()}%`;
			if (datatype === "Int" || datatype === "Float") {
				return compact ? this.compactNumber(value) : Number(value || 0).toLocaleString();
			}
			return window.retailedge?.toPlainText?.(value) ?? String(value ?? "");
		},
		displayIcon(icon) {
			return {
				"file-text": "report",
				download: "wallet",
				upload: "wallet",
				"credit-card": "wallet",
				"shopping-bag": "layers",
				"shopping-cart": "grid",
				repeat: "activity",
				zap: "activity",
				plus: "clipboard",
				stock: "layers",
				"bar-chart-2": "chart",
			}[String(icon || "")] || icon || "list";
		},
		kpiIcon(label) {
			return {
				Sales: "chart",
				Expenses: "wallet",
				Receivables: "report",
				Payables: "wallet",
				"Stock Value": "layers",
			}[String(label || "")] || "chart";
		},
		signalIcon(key) {
			return {
				stock: "layers",
				banking: "wallet",
				branch: "building",
				cash_shift: "wallet",
				sales: "chart",
				cash: "wallet",
				expenses: "wallet",
				receivables: "report",
				payables: "wallet",
			}[String(key || "")] || "chart";
		},
		homeRouteFilters(card = {}) {
			const filters = { company: this.context.company || "" };
			if (this.context.branch) filters.branch = this.context.branch;
			if (card?.time_basis !== "current") {
				filters.from_date = this.homePeriod.from_date || "";
				filters.to_date = this.homePeriod.to_date || "";
			}
			return filters;
		},
		indexStatusLabel(index) {
			if (!index?.available) return "Unavailable";
			if (index?.requires_action && index?.tone === "danger") return "Act now";
			if (index?.requires_action) return "Review";
			return "On track";
		},
		openHomeItem(item) {
			if (!item?.route) return;
			this.openHomeRoute(item.route, item.route_filters || {});
		},
		openHomeRoute(route, filters = {}) {
			if (!route) return;
			setBusinessHubRouteHandoff(route, filters);
			const normalized = String(route).replace(/^\/app\//, "");
			frappe.set_route(...normalized.split("/").filter(Boolean));
		},
		openCreatePicker() {
			if (!this.quickActions.length) return;
			this.createPickerOpen = true;
		},
		closeCreatePicker() {
			this.createPickerOpen = false;
		},
		runHomeQuickAction(shortcut) {
			if (!shortcut) return;
			if (shortcut.kind === "action" && shortcut.action) {
				this.runQuickAction(shortcut.action);
				return;
			}
			if (shortcut.kind === "page" && shortcut.target) {
				frappe.set_route(shortcut.target);
			}
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
				if (action.doctype === "RetailEdge Business Expense" || action.target === "business-expenses") {
					frappe.route_options = { action: "new" };
					frappe.set_route("business-expenses");
					return;
				}
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
			const quickEntryDoctype = QUICK_ENTRY_MASTER_ACTIONS[action.key];
			if (quickEntryDoctype) {
				openQuickEntryMaster(quickEntryDoctype)
					.then((created) => {
						if (!created?.value) return;
						frappe.show_alert?.({
							message: `${created.label || created.value} created`,
							indicator: "green",
						});
					})
					.catch((error) => {
						frappe.show_alert?.({
							message: error?.message || `Unable to create ${quickEntryDoctype}.`,
							indicator: "red",
						}, 7);
					});
				return;
			}
			if (!this.nativeFallbackEnabled) {
				frappe.show_alert?.({ message: "This account is limited to guided operational pages.", indicator: "orange" });
				return;
			}
			frappe.new_doc(action.doctype);
		},
		notifyGuidedDraftSaved(result, fallbackDoctype, label, { stayInEdgeSuite = false } = {}) {
			if (!result?.name) return;
			const doctype = result.doctype || fallbackDoctype;
			if (this.nativeFallbackEnabled && !stayInEdgeSuite) {
				frappe.set_route("Form", doctype, result.name);
			}
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
			if (result?.name) {
				this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: result.name });
			}
		},
		openSalesInvoiceCompletion(document) {
			if (document?.doctype !== "Sales Invoice" || !document?.name) return;
			this.salesInvoiceCompletionDocument = { doctype: "Sales Invoice", name: document.name };
			this.salesInvoiceCompletionOpen = true;
		},
		closeSalesInvoiceCompletion() {
			this.salesInvoiceCompletionOpen = false;
			this.salesInvoiceCompletionDocument = null;
		},
		handleSalesInvoiceCompletionChanged() {
			this.refreshContext({ force: true });
		},
		handleSalesInvoiceCompletionCompleted() {
			this.closeSalesInvoiceCompletion();
			this.refreshContext({ force: true });
		},
		openNativeSalesInvoice(doctype = "Sales Invoice") {
			if (!this.nativeFallbackEnabled) return;
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
			if (!this.nativeFallbackEnabled) return;
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			frappe.new_doc(doctype);
		},
		closeSimpleCashDeposit() {
			this.simpleCashDepositOpen = false;
		},
		handleSimpleCashDepositSaved(result) {
			this.simpleCashDepositOpen = false;
			if (result?.name) {
				this.openInternalTransferCompletion({ doctype: "Payment Entry", name: result.name });
			}
		},
		openNativeCashDeposit(doctype = "Payment Entry") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleCashDepositOpen = false;
			frappe.new_doc(doctype, { payment_type: "Internal Transfer" });
		},
		closeSimpleCashTransfer() {
			this.simpleCashTransferOpen = false;
		},
		handleSimpleCashTransferSaved(result) {
			this.simpleCashTransferOpen = false;
			if (result?.name) {
				this.openInternalTransferCompletion({ doctype: "Payment Entry", name: result.name });
			}
		},
		openInternalTransferCompletion(document) {
			if (document?.doctype !== "Payment Entry" || !document?.name) return;
			this.internalTransferCompletionDocument = { doctype: "Payment Entry", name: document.name };
			this.internalTransferCompletionOpen = true;
		},
		closeInternalTransferCompletion() {
			this.internalTransferCompletionOpen = false;
			this.internalTransferCompletionDocument = null;
		},
		handleInternalTransferCompletionChanged() {
			this.refreshContext({ force: true });
		},
		handleInternalTransferCompletionCompleted() {
			this.closeInternalTransferCompletion();
			this.refreshContext({ force: true });
		},
		openNativeCashTransfer(doctype = "Payment Entry") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleCashTransferOpen = false;
			frappe.new_doc(doctype, { payment_type: "Internal Transfer" });
		},
		closeSimplePurchaseInvoice() {
			this.simplePurchaseInvoiceOpen = false;
		},
		handleSimplePurchaseInvoiceSaved(result) {
			this.simplePurchaseInvoiceOpen = false;
			if (result?.name) {
				this.openPurchaseInvoiceCompletion({ doctype: "Purchase Invoice", name: result.name });
			}
		},
		openPurchaseInvoiceCompletion(document) {
			if (document?.doctype !== "Purchase Invoice" || !document?.name) return;
			this.purchaseInvoiceCompletionDocument = { doctype: "Purchase Invoice", name: document.name };
			this.purchaseInvoiceCompletionOpen = true;
		},
		closePurchaseInvoiceCompletion() {
			this.purchaseInvoiceCompletionOpen = false;
			this.purchaseInvoiceCompletionDocument = null;
		},
		handlePurchaseInvoiceCompletionChanged() {
			this.refreshContext({ force: true });
		},
		handlePurchaseInvoiceCompletionCompleted() {
			this.closePurchaseInvoiceCompletion();
			this.refreshContext({ force: true });
		},
		openNativePurchaseInvoice(doctype = "Purchase Invoice") {
			if (!this.nativeFallbackEnabled) return;
			this.simplePurchaseInvoiceOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimpleCashierExpense() {
			this.simpleCashierExpenseOpen = false;
		},
		handleSimpleCashierExpenseSaved(result) {
			this.simpleCashierExpenseOpen = false;
			const completion = result?.completion || {};
			const name = completion.name || result?.name || "";
			if (name) {
				this.cashierExpenseCompletionDocument = {
					doctype: completion.doctype || result?.doctype || "RetailEdge Cashier Expense",
					name,
				};
				this.cashierExpenseCompletionOpen = true;
			}
			this.refreshHomeSnapshot();
		},
		closeCashierExpenseCompletion() {
			this.cashierExpenseCompletionOpen = false;
			this.cashierExpenseCompletionDocument = null;
		},
		handleCashierExpenseCompletionChanged() {
			this.refreshHomeSnapshot();
		},
		handleCashierExpenseCompletionCompleted() {
			this.closeCashierExpenseCompletion();
			this.refreshContext({ force: true });
		},
		openNativeCashierExpense(doctype = "RetailEdge Cashier Expense") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleCashierExpenseOpen = false;
			frappe.new_doc(doctype);
		},
		closeSimpleStockTransfer() {
			this.simpleStockTransferOpen = false;
		},
		handleSimpleStockTransferSaved(result) {
			this.simpleStockTransferOpen = false;
			if (result?.name) {
				this.openStockCompletion({ doctype: "Stock Entry", name: result.name });
			}
		},
		openNativeStockTransfer(doctype = "Stock Entry") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleStockTransferOpen = false;
			frappe.new_doc(doctype, { stock_entry_type: "Material Transfer" });
		},
		closeSimpleStockAdjustment() {
			this.simpleStockAdjustmentOpen = false;
		},
		handleSimpleStockAdjustmentSaved(result) {
			this.simpleStockAdjustmentOpen = false;
			if (result?.name) {
				this.openStockCompletion({ doctype: "Stock Reconciliation", name: result.name });
			}
		},
		openStockCompletion(document) {
			if (!["Stock Entry", "Stock Reconciliation"].includes(document?.doctype) || !document?.name) return;
			this.stockCompletionDocument = { doctype: document.doctype, name: document.name };
			this.stockCompletionOpen = true;
		},
		closeStockCompletion() {
			this.stockCompletionOpen = false;
			this.stockCompletionDocument = null;
		},
		handleStockCompletionChanged() {
			this.refreshHomeSnapshot();
		},
		handleStockCompletionCompleted() {
			this.closeStockCompletion();
			this.refreshContext({ force: true });
		},
		openNativeStockAdjustment(doctype = "Stock Reconciliation") {
			if (!this.nativeFallbackEnabled) return;
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
			if (!this.nativeFallbackEnabled && ["DocType", "Report"].includes(item?.target_type)) return;
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
			if (!this.nativeFallbackEnabled && ["DocType", "Report"].includes(item?.target_type)) return "";
			if (item.target_type === "URL") return item.target;
			if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "Page") return `/app/${item.target}`;
			return "";
		},
		actionModeLabel(action) {
			if (action?.mode === "page") return "Guided";
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
.create-product-menu {
	border: 1px solid var(--edge-color-border, #dfe6ec);
	border-radius: 12px;
	overflow: hidden;
	background: var(--edge-color-surface, #fff);
}
.create-product-menu-header {
	display: flex;
	align-items: center;
	gap: 10px;
	padding: 14px 16px;
	border-bottom: 1px solid var(--edge-color-border, #dfe6ec);
	background: var(--edge-color-surface-muted, #f6f8fa);
}
.create-product-menu-header > span:last-child {
	display: grid;
	gap: 2px;
}
.create-product-menu-header small {
	color: var(--edge-color-ink-500, #617589);
}
.create-product-menu-mark,
.create-picker-icon,
.home-kpi-card-icon,
.home-signal-icon {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	border-radius: 8px;
	background: var(--edge-color-brand-50, #eef7ff);
	color: var(--edge-color-brand-700, #0c4f87);
}
.create-product-menu-mark {
	width: 34px;
	height: 34px;
}
.home-kpi-card-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
	min-width: 0;
	width: 100%;
}
.home-kpi-card-heading > span:first-child {
	min-width: 0;
	overflow-wrap: anywhere;
	font-size: .74rem;
	font-weight: 620;
}
.home-kpi-card-icon {
	width: 30px;
	height: 30px;
	flex: 0 0 auto;
}
.home-signal-icon {
	width: 24px;
	height: 24px;
	flex: 0 0 auto;
	border-radius: 6px;
}
.home-signal-icon :deep(svg) {
	width: 14px;
	height: 14px;
}
.home-signal-heading h4 {
	display: inline-flex;
	align-items: center;
	gap: 8px;
}
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
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 14px;
	background: var(--edge-color-surface, #ffffff);
}
.hub-banner h2 {
	margin: 4px 0 8px;
	font-size: 1.55rem;
}
.hub-banner p {
	margin: 0;
	color: var(--edge-color-ink-500, #667085);
	max-width: 760px;
}
.hub-eyebrow,
.section-kicker {
	text-transform: uppercase;
	letter-spacing: 0.08em;
	font-size: 0.72rem;
	font-weight: 700;
	color: var(--edge-color-brand-600, #2563eb);
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
	color: var(--edge-color-ink-500, #667085);
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
.home-as-of {
	font-size: 0.78rem;
	color: var(--edge-color-ink-500, #667085);
}
.home-kpi-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(13.5rem, 1fr));
	gap: 12px;
	margin-bottom: 14px;
}
.home-kpi-card,
.home-signal-card {
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #ffffff);
}
.home-kpi-card {
	display: grid;
	gap: 5px;
	min-width: 0;
	padding: 13px 14px;
	text-align: left;
	cursor: pointer;
}
.home-kpi-card:hover,
.home-kpi-card:focus-visible {
	border-color: var(--edge-color-brand-600, #2563eb);
}
.home-kpi-card span,
.home-kpi-card small,
.home-signal-list span,
.home-unavailable {
	color: var(--edge-color-ink-500, #667085);
}
.home-kpi-card strong {
	display: block;
	min-width: 0;
	max-width: 100%;
	overflow: hidden;
	text-overflow: ellipsis;
	font-size: clamp(1rem, 1.25vw, 1.32rem);
	font-variant-numeric: tabular-nums;
	font-weight: 680;
	letter-spacing: -0.02em;
	line-height: 1.15;
	white-space: nowrap;
}
.home-kpi-card small {
	font-size: 0.72rem;
}
.home-visual-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 12px;
}
.home-visuals-section {
	min-width: 0;
}
.home-signal-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 12px;
}
.home-signal-card {
	padding: 16px;
}
.home-intelligence-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 12px;
}
.home-intelligence-card {
	display: grid;
	gap: 10px;
	min-width: 0;
	padding: 16px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #ffffff);
}
.home-index-headline > span,
.home-index-signal > span {
	min-width: 0;
	overflow-wrap: anywhere;
	font-size: .82rem;
}
.home-index-headline > strong,
.home-index-signal > strong {
	flex: 0 0 auto;
	max-width: 48%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
	text-align: right;
	font-size: .86rem;
	font-weight: 650;
	font-variant-numeric: tabular-nums;
}
.home-intelligence-card p,
.home-index-action,
.home-attention-copy,
.home-attention-value {
	font-size: .82rem;
}
.home-intelligence-heading h4 {
	min-width: 0;
	overflow-wrap: anywhere;
}
.home-attention-copy,
.home-attention-value {
	min-width: 0;
}
.home-attention-value strong {
	display: block;
	max-width: 100%;
	overflow: hidden;
	text-overflow: ellipsis;
	white-space: nowrap;
}
.home-intelligence-card.tone-danger {
	border-color: color-mix(in srgb, var(--edge-color-danger, #d92d20) 55%, var(--edge-color-border, #dfe3e8));
}
.home-intelligence-card.tone-warning {
	border-color: color-mix(in srgb, var(--edge-color-warning, #f79009) 55%, var(--edge-color-border, #dfe3e8));
}
.home-intelligence-card.is-unavailable {
	opacity: .72;
}
.home-intelligence-heading,
.home-index-headline,
.home-index-signal {
	display: flex;
	min-width: 0;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
}
.home-intelligence-heading h4 {
	display: inline-flex;
	align-items: center;
	gap: 7px;
	margin: 0;
	font-size: 0.96rem;
	line-height: 1.25;
	font-weight: 700;
	color: var(--edge-color-ink-950, #101828);
}
.home-index-status {
	display: inline-flex;
	align-items: center;
	min-height: 22px;
	padding: 0 7px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 999px;
	background: var(--edge-color-surface-muted, #f8fafc);
	color: var(--edge-color-ink-700, #344054);
	font-size: .66rem;
	font-weight: 700;
	white-space: nowrap;
}
.home-index-status.tone-danger {
	color: var(--edge-color-danger, #d92d20);
}
.home-index-status.tone-warning {
	color: var(--edge-color-warning, #b54708);
}
.home-index-headline,
.home-index-signal {
	padding: 9px 10px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 9px;
	background: var(--edge-color-surface-muted, #f8fafc);
	color: var(--edge-color-ink-950, #101828);
}
.home-index-headline span,
.home-index-signal span,
.home-intelligence-card p {
	color: var(--edge-color-ink-500, #667085);
}
.home-index-headline strong,
.home-index-signal strong {
	color: var(--edge-color-ink-950, #101828);
	font-size: .86rem;
	font-variant-numeric: tabular-nums;
}
.home-intelligence-card p {
	margin: 0;
	font-size: .8rem;
	line-height: 1.4;
}
.home-index-action {
	justify-self: start;
	padding: 0;
	border: 0;
	background: transparent;
	color: var(--edge-color-brand-600, #2563eb);
	font-weight: 700;
	cursor: pointer;
}
.home-index-action:hover,
.home-index-action:focus-visible {
	text-decoration: underline;
}
.home-signal-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 10px;
	margin-bottom: 12px;
}
.home-signal-heading h4 {
	margin: 0;
}
.home-link {
	border: 0;
	background: transparent;
	color: var(--edge-color-brand-600, #2563eb);
	font-weight: 600;
	cursor: pointer;
}
.home-signal-list {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 10px;
}
.home-signal-list > div {
	display: grid;
	gap: 3px;
	padding: 10px;
	border-radius: 9px;
	background: var(--edge-color-surface-muted, #f8fafc);
}
.home-unavailable {
	margin: 0;
	font-size: 0.84rem;
}
.home-attention-list {
	display: grid;
	gap: 8px;
}
.home-attention-item {
	display: flex;
	justify-content: space-between;
	gap: 12px;
	width: 100%;
	padding: 9px 10px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 9px;
	background: var(--edge-color-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.home-attention-item.tone-danger {
	border-color: var(--edge-color-danger, #d92d20);
}
.home-attention-item.tone-warning {
	border-color: var(--edge-color-warning, #f79009);
}
.home-attention-copy,
.home-attention-value {
	display: grid;
	gap: 3px;
}
.home-attention-copy small,
.home-attention-value small {
	color: var(--edge-color-ink-500, #667085);
	font-size: .74rem;
	line-height: 1.35;
}
.home-attention-value {
	justify-items: end;
	text-align: right;
}
.home-quick-actions-grid {
	display: grid;
	grid-template-columns: repeat(4, minmax(0, 1fr));
	gap: 12px;
}
.home-quick-action {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr);
	align-items: start;
	gap: 10px;
	padding: 14px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.home-quick-action:hover,
.home-quick-action:focus-visible {
	border-color: var(--edge-color-brand-600, #2563eb);
}
.home-quick-action > span:last-child {
	display: grid;
	gap: 4px;
}
.home-quick-action small {
	color: var(--edge-color-ink-500, #667085);
	line-height: 1.35;
}
.home-quick-action-icon {
	font-size: 1.15rem;
}
.experience-grid {
	display: grid;
	grid-template-columns: repeat(5, minmax(0, 1fr));
	gap: 14px;
}
.experience-card {
	padding: 18px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #ffffff);
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
	color: var(--edge-color-ink-500, #667085);
	font-size: 0.88rem;
	line-height: 1.5;
}
.experience-icon,
.create-picker-icon {
	font-size: 1.3rem;
}
.create-picker-list {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 8px;
}
.create-picker-item {
	display: grid;
	grid-template-columns: auto minmax(0, 1fr) auto;
	align-items: center;
	gap: 12px;
	width: 100%;
	padding: 13px 14px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 10px;
	background: var(--edge-color-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.create-picker-item:hover,
.create-picker-item:focus-visible {
	border-color: var(--edge-color-brand-600, #2563eb);
}
.create-picker-copy {
	display: grid;
	gap: 3px;
	min-width: 0;
}
.create-picker-copy small,
.create-picker-mode {
	color: var(--edge-color-ink-500, #667085);
}
.create-picker-copy small {
	line-height: 1.35;
}
.create-picker-mode {
	font-size: 0.72rem;
	white-space: nowrap;
}
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .hub-banner,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-kpi-card,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-intelligence-card,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-quick-action,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-attention-item,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-signal-card,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .create-picker-item,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .create-product-menu {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
	color: var(--edge-color-ink-950);
}

:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-headline,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-signal,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-status,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-signal-list > div {
	background: var(--edge-color-surface-muted);
	border-color: var(--edge-color-border);
	color: var(--edge-color-ink-950);
}

:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .hub-banner h2,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-intelligence-heading h4,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-headline strong,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-signal strong,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-quick-action strong {
	color: var(--edge-color-ink-950);
}

:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .hub-rider,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .hub-context,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .section-rider,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-headline span,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-signal span,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-intelligence-card p,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-quick-action small {
	color: var(--edge-color-ink-500);
}

:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-index-status:not(.tone-warning):not(.tone-danger) {
	background: color-mix(in srgb, var(--edge-color-success) 14%, var(--edge-color-surface-muted));
	border-color: color-mix(in srgb, var(--edge-color-success) 32%, var(--edge-color-border));
	color: var(--edge-color-success);
}

:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-quick-action-icon,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-signal-icon,
:global(:root[data-edge-appearance="dark"]) .retailedge-business-hub .home-kpi-card-icon {
	background: color-mix(in srgb, var(--edge-color-brand-600) 18%, var(--edge-color-surface));
	color: var(--edge-color-brand-500);
}

@media (max-width: 1200px) {
	.home-kpi-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
	}
	.home-intelligence-grid {
		grid-template-columns: repeat(2, minmax(0, 1fr));
	}
	.home-quick-actions-grid,
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
	.home-kpi-grid,
	.home-visual-grid,
	.home-intelligence-grid,
	.home-signal-grid,
	.home-signal-list,
	.home-quick-actions-grid,
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
@media (max-width: 760px) {
	.create-picker-list {
		grid-template-columns: 1fr;
	}
}

.hub-rider,
.section-rider,
.home-quick-action small,
.home-unavailable {
	font-size: .82rem;
	line-height: 1.45;
}
.section-rider {
	margin: 4px 0 0;
	color: var(--edge-color-ink-500, #667085);
}
.home-period-controls {
	display: flex;
	align-items: flex-end;
	justify-content: flex-end;
	gap: 10px;
	flex-wrap: wrap;
	position: relative;
	z-index: 20;
	overflow: visible;
}
.home-command-centre,
.hub-experience-section,
.section-heading {
	overflow: visible;
}
:deep(.home-period-controls .edge-smart-date__picker) {
	z-index: 2600;
	max-width: calc(100vw - 1.5rem);
}
.home-period-controls .edge-field,
.home-period-controls .edge-smart-date-range,
.home-period-controls .edge-smart-date {
	min-width: min(24rem, 100%);
	margin: 0;
}
.home-attention-count {
	display: inline-flex;
	align-items: center;
	justify-content: center;
	min-width: 30px;
	height: 30px;
	padding: 0 9px;
	border: 1px solid var(--edge-color-border, #d9e2ec);
	border-radius: 999px;
	font-size: .8rem;
	font-weight: 700;
}
.home-attention-list--wide {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 10px;
}
@media (max-width: 760px) {
	.home-period-controls {
		justify-content: flex-start;
	}
	.home-attention-list--wide {
		grid-template-columns: 1fr;
	}
}
</style>
