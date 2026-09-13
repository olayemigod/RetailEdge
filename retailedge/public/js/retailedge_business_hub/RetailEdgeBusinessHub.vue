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

				<section class="home-command-centre">
					<div class="section-heading">
						<div>
							<p class="section-kicker">Today</p>
							<h3>Business at a glance</h3>
						</div>
						<span v-if="homeSnapshot.as_of_date" class="home-as-of">As of {{ homeSnapshot.as_of_date }}</span>
					</div>
					<EdgeLoadingState v-if="homeLoading" message="Loading today's business position..." :skeleton="true" />
					<EdgeErrorState v-else-if="homeError" title="Business snapshot unavailable" :message="homeError" @retry="refreshHomeSnapshot" />
					<div v-else>
						<div v-if="homeSnapshot.cards.length" class="home-kpi-grid">
							<button
								v-for="card in homeSnapshot.cards"
								:key="card.label"
								type="button"
								class="home-kpi-card"
								@click="openHomeRoute(card.route)"
							>
								<span>{{ card.label }}</span>
								<strong>{{ formatHomeValue(card) }}</strong>
								<small>{{ card.time_basis === "current" ? "Current position" : "Today" }}</small>
							</button>
						</div>
						<EdgeEmptyState
							v-else
							title="No management cards available"
							description="Your current role can still use the permitted operational actions and pages from the RetailEdge menu."
							icon="bar-chart-2"
						/>
						<div class="home-signal-grid">
							<article v-for="key in ['stock', 'banking', 'branch', 'cash_shift']" :key="key" class="home-signal-card">
								<div class="home-signal-heading">
									<h4>{{ homeSection(key).label || key }}</h4>
									<button v-if="homeSection(key).route && homeSection(key).available" type="button" class="home-link" @click="openHomeRoute(homeSection(key).route)">Open</button>
								</div>
								<div v-if="homeSection(key).available && homeSection(key).summary.length" class="home-signal-list">
									<div v-for="card in homeSection(key).summary.slice(0, 4)" :key="card.label">
										<span>{{ card.label }}</span>
										<strong>{{ formatHomeValue(card) }}</strong>
									</div>
								</div>
								<p v-else class="home-unavailable">{{ homeSection(key).reason || "No signal is available for this scope." }}</p>
							</article>
							<article class="home-signal-card home-attention-card">
								<div class="home-signal-heading"><h4>Attention</h4><span>{{ homeSnapshot.attention.length }}</span></div>
								<div v-if="homeSnapshot.attention.length" class="home-attention-list">
									<button v-for="(item, index) in homeSnapshot.attention" :key="`${item.section || 'attention'}-${index}`" type="button" :class="['home-attention-item', `tone-${item.tone || 'warning'}`]" @click="openHomeRoute(item.route)">
										<span>{{ item.label }}</span>
										<strong>{{ formatHomeValue(item) }}</strong>
									</button>
								</div>
								<p v-else class="home-unavailable">No current attention items were found in the permitted scope.</p>
							</article>
						</div>
					</div>
				</section>

				<section v-if="homeQuickActions.length" class="home-quick-actions-section">
					<div class="section-heading">
						<div>
							<p class="section-kicker">Quick actions</p>
							<h3>Do the next business task</h3>
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
							<span class="home-quick-action-icon">{{ iconText(shortcut.icon) }}</span>
							<span>
								<strong>{{ shortcut.label }}</strong>
								<small>{{ shortcut.description }}</small>
							</span>
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
import SimplePaymentDialog from "./SimplePaymentDialog.vue";
import SimplePurchaseInvoiceDialog from "./SimplePurchaseInvoiceDialog.vue";
import StandardPurchaseInvoiceCompletionDialog from "../professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue";
import SimpleSalesInvoiceDialog from "./SimpleSalesInvoiceDialog.vue";
import StandardSalesInvoiceCompletionDialog from "../professional_selling/StandardSalesInvoiceCompletionDialog.vue";
import SimpleStockAdjustmentDialog from "./SimpleStockAdjustmentDialog.vue";
import SimpleStockTransferDialog from "./SimpleStockTransferDialog.vue";
import StandardStockCompletionDialog from "./StandardStockCompletionDialog.vue";
import { openQuickEntryMaster } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.edgesuite_ui.get_retailedge_business_hub_context";
const HOME_SNAPSHOT_METHOD = "retailedge.business_hub_home.get_business_hub_home_snapshot";
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

function fetchHomeSnapshot(company, branch) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method: HOME_SNAPSHOT_METHOD,
			args: { company: company || "", branch: branch || "" },
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
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
		StandardInternalTransferCompletionDialog,
		SimpleCashTransferDialog,
		SimpleCashierExpenseDialog,
		SimplePaymentDialog,
		SimplePurchaseInvoiceDialog,
		StandardPurchaseInvoiceCompletionDialog,
		SimpleSalesInvoiceDialog,
		StandardSalesInvoiceCompletionDialog,
		SimpleStockAdjustmentDialog,
		SimpleStockTransferDialog,
		StandardStockCompletionDialog,
	},
	data() {
		return {
			loading: true,
			error: "",
			homeLoading: false,
			homeError: "",
			homeSnapshot: { as_of_date: "", cards: [], sections: {}, attention: [] },
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
			simpleStockTransferOpen: false,
			simpleStockAdjustmentOpen: false,
			stockCompletionOpen: false,
			stockCompletionDocument: null,
			programmeExperiences: [],
			navigationGroups: [],
			quickActions: [],
			context: { user: "", user_name: "", company: "", branch: "" },
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
			this.programmeExperiences = data.programme_experiences || [];
			this.navigationGroups = data.navigation_groups || [];
			this.quickActions = data.quick_actions || [];
			this.context = { ...this.context, ...(data.context || {}) };
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
		refreshHomeSnapshot() {
			if (!this.context.company) {
				this.homeSnapshot = { as_of_date: "", cards: [], sections: {}, attention: [] };
				return Promise.resolve();
			}
			this.homeLoading = true;
			this.homeError = "";
			return fetchHomeSnapshot(this.context.company, this.context.branch)
				.then((snapshot) => {
					this.homeSnapshot = {
						as_of_date: snapshot.as_of_date || "",
						cards: snapshot.cards || [],
						sections: snapshot.sections || {},
						attention: snapshot.attention || [],
					};
				})
				.catch((error) => {
					this.homeSnapshot = { as_of_date: "", cards: [], sections: {}, attention: [] };
					this.homeError = error?.message || "Unable to load the current business snapshot.";
				})
				.finally(() => {
					this.homeLoading = false;
				});
		},
		homeSection(key) {
			return this.homeSnapshot.sections?.[key] || { available: false, label: key, summary: [], route: "", reason: "" };
		},
		formatHomeValue(card) {
			const value = card?.value ?? 0;
			const datatype = card?.datatype || card?.type || "Data";
			if (datatype === "Currency") {
				try { return frappe.format(value, { fieldtype: "Currency" }); } catch (_error) { return Number(value || 0).toLocaleString(); }
			}
			if (datatype === "Percent") return `${Number(value || 0).toLocaleString()}%`;
			if (datatype === "Int" || datatype === "Float") return Number(value || 0).toLocaleString();
			return String(value ?? "");
		},
		openHomeRoute(route) {
			if (!route) return;
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
				frappe.show_alert?.({ message: "This account is limited to EdgeSuite operational pages.", indicator: "orange" });
				return;
			}
			frappe.new_doc(action.doctype);
		},
		notifyGuidedDraftSaved(result, fallbackDoctype, label) {
			if (!result?.name) return;
			const doctype = result.doctype || fallbackDoctype;
			if (this.nativeFallbackEnabled) {
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
			this.notifyGuidedDraftSaved(result, "RetailEdge Cashier Expense", "Cashier Expense");
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
			if (action?.mode === "page") return "EdgeSuite";
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
.home-as-of {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.home-kpi-grid {
	display: grid;
	grid-template-columns: repeat(5, minmax(0, 1fr));
	gap: 12px;
	margin-bottom: 14px;
}
.home-kpi-card,
.home-signal-card {
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-surface, #ffffff);
}
.home-kpi-card {
	display: grid;
	gap: 6px;
	padding: 16px;
	text-align: left;
	cursor: pointer;
}
.home-kpi-card:hover,
.home-kpi-card:focus-visible {
	border-color: var(--edge-primary, #2563eb);
}
.home-kpi-card span,
.home-kpi-card small,
.home-signal-list span,
.home-unavailable {
	color: var(--edge-text-muted, #667085);
}
.home-kpi-card strong {
	font-size: 1.2rem;
}
.home-kpi-card small {
	font-size: 0.72rem;
}
.home-signal-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 12px;
}
.home-signal-card {
	padding: 16px;
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
	color: var(--edge-primary, #2563eb);
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
	background: var(--edge-surface-muted, #f8fafc);
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
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 9px;
	background: var(--edge-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.home-attention-item.tone-danger {
	border-color: var(--edge-danger, #d92d20);
}
.home-attention-item.tone-warning {
	border-color: var(--edge-warning, #f79009);
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
	border: 1px solid var(--edge-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-surface, #ffffff);
	text-align: left;
	cursor: pointer;
}
.home-quick-action:hover,
.home-quick-action:focus-visible {
	border-color: var(--edge-primary, #2563eb);
}
.home-quick-action > span:last-child {
	display: grid;
	gap: 4px;
}
.home-quick-action small {
	color: var(--edge-text-muted, #667085);
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
	.home-kpi-grid {
		grid-template-columns: repeat(3, minmax(0, 1fr));
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
</style>
