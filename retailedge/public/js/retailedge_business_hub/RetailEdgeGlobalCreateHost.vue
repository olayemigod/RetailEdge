<template>
	<div class="retailedge-global-create-host" aria-live="polite">
		<EdgeModal
			:open="pickerOpen"
			title="Create"
			subtitle="Choose a permitted RetailEdge entry. Quick entries stay on the current page until you explicitly open a full page."
			size="md"
			@close="closePicker"
		>
			<div v-if="loading" class="global-create-state">Preparing permitted entries…</div>
			<div v-else-if="loadError" class="global-create-state global-create-state--error">{{ loadError }}</div>
			<div v-else-if="quickActions.length" class="create-product-menu">
				<header class="create-product-menu-header edge-product-menu__header">
					<div class="edge-product-menu__brand">
						<span class="create-product-menu-mark edge-product-menu__brand-mark"><EdgeIcon name="plus" size="sm" /></span>
						<span><strong>Create</strong><small>Retail business actions</small></span>
					</div>
				</header>
				<section class="edge-product-menu__section" aria-label="Permitted business actions">
					<div class="edge-product-menu__section-heading">
						<span class="edge-product-menu__section-icon"><EdgeIcon name="activity" size="sm" /></span>
						<span><h3>Business actions</h3><p>Only entries permitted for your current role and context are shown.</p></span>
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
							<span class="create-picker-icon edge-product-menu__item-icon"><EdgeIcon :name="action.icon || 'plus'" size="sm" /></span>
							<span class="create-picker-copy edge-product-menu__item-copy">
								<strong>{{ action.label }}</strong>
								<small>{{ action.description }}</small>
							</span>
							<span class="create-picker-mode edge-product-menu__item-badge">Quick</span>
						</button>
					</div>
				</section>
			</div>
			<EdgeEmptyState
				v-else
				title="No permitted entries"
				description="Your current roles do not allow creation of the configured RetailEdge business documents."
				icon="lock"
			/>
			<template #footer>
				<button type="button" class="edge-button" @click="closePicker">Cancel</button>
			</template>
		</EdgeModal>

		<SimpleSalesInvoiceDialog
			:open="simpleSalesInvoiceOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleSalesInvoiceOpen = false"
			@saved="handleSalesInvoiceSaved"
			@open-page="openFullSalesPage"
			@open-native="openNative"
		/>
		<StandardSalesInvoiceCompletionDialog
			:open="salesCompletionOpen"
			:document="salesCompletionDocument"
			:canUseNativeDesk="nativeFallbackEnabled"
			:showNextActions="true"
			@close="closeSalesCompletion"
			@changed="refreshContext"
			@completed="refreshContext"
			@next-action="handleSalesNextAction"
		/>
		<StandardDeliveryCompletionDialog
			:open="deliveryCompletionOpen"
			:document="deliveryCompletionDocument"
			:canUseNativeDesk="nativeFallbackEnabled"
			@close="closeDeliveryCompletion"
			@changed="refreshContext"
			@completed="refreshContext"
			@next-action="handleDeliveryNextAction"
		/>

		<SimplePaymentDialog
			:open="simplePaymentOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			:intent="simplePaymentIntent"
			:initial-context="simplePaymentInitialContext"
			@close="closePayment"
			@saved="handlePaymentSaved"
			@open-native="openNative"
		/>

		<SimpleCashDepositDialog
			:open="simpleCashDepositOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleCashDepositOpen = false"
			@saved="handleInternalTransferSaved"
			@open-native="openNativeInternalTransfer"
		/>
		<SimpleCashTransferDialog
			:open="simpleCashTransferOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleCashTransferOpen = false"
			@saved="handleInternalTransferSaved"
			@open-native="openNativeInternalTransfer"
		/>
		<StandardInternalTransferCompletionDialog
			:open="internalTransferCompletionOpen"
			:document="internalTransferCompletionDocument"
			:canUseNativeDesk="nativeFallbackEnabled"
			@close="closeInternalTransferCompletion"
			@changed="refreshContext"
			@completed="closeInternalTransferCompletion"
		/>

		<SimplePurchaseInvoiceDialog
			:open="simplePurchaseInvoiceOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simplePurchaseInvoiceOpen = false"
			@saved="handlePurchaseInvoiceSaved"
			@open-page="openFullPurchasePage"
			@open-native="openNative"
		/>
		<StandardPurchaseInvoiceCompletionDialog
			:open="purchaseCompletionOpen"
			:document="purchaseCompletionDocument"
			:canUseNativeDesk="nativeFallbackEnabled"
			:showNextActions="true"
			@close="closePurchaseCompletion"
			@changed="refreshContext"
			@completed="refreshContext"
			@next-action="handlePurchaseNextAction"
		/>

		<SimpleCashierExpenseDialog
			:open="simpleCashierExpenseOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleCashierExpenseOpen = false"
			@saved="handleCashierExpenseSaved"
			@open-native="openNative"
		/>
		<GuidedWorkflowCompletionDialog
			:open="cashierExpenseCompletionOpen"
			:document="cashierExpenseCompletionDocument"
			label="Cashier Expense"
			:canUseNativeDesk="nativeFallbackEnabled"
			@close="closeCashierExpenseCompletion"
			@changed="refreshContext"
			@completed="closeCashierExpenseCompletion"
		/>

		<SimpleStockTransferDialog
			:open="simpleStockTransferOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleStockTransferOpen = false"
			@saved="handleStockSaved"
			@open-page="openFullStockTransferPage"
			@open-native="openNativeStockTransfer"
		/>
		<SimpleStockAdjustmentDialog
			:open="simpleStockAdjustmentOpen"
			:native-fallback-enabled="nativeFallbackEnabled"
			@close="simpleStockAdjustmentOpen = false"
			@saved="handleStockSaved"
			@open-page="openFullStockAdjustmentPage"
			@open-native="openNative"
		/>
		<StandardStockCompletionDialog
			:open="stockCompletionOpen"
			:document="stockCompletionDocument"
			:canUseNativeDesk="nativeFallbackEnabled"
			@close="closeStockCompletion"
			@changed="refreshContext"
			@completed="closeStockCompletion"
		/>
	</div>
</template>

<script>
import GuidedWorkflowCompletionDialog from "./GuidedWorkflowCompletionDialog.vue";
import SimpleCashDepositDialog from "./SimpleCashDepositDialog.vue";
import SimpleCashTransferDialog from "./SimpleCashTransferDialog.vue";
import SimpleCashierExpenseDialog from "./SimpleCashierExpenseDialog.vue";
import SimplePaymentDialog from "./SimplePaymentDialog.vue";
import SimplePurchaseInvoiceDialog from "./SimplePurchaseInvoiceDialog.vue";
import SimpleSalesInvoiceDialog from "./SimpleSalesInvoiceDialog.vue";
import SimpleStockAdjustmentDialog from "./SimpleStockAdjustmentDialog.vue";
import SimpleStockTransferDialog from "./SimpleStockTransferDialog.vue";
import StandardInternalTransferCompletionDialog from "./StandardInternalTransferCompletionDialog.vue";
import StandardStockCompletionDialog from "./StandardStockCompletionDialog.vue";
import StandardDeliveryCompletionDialog from "../professional_selling/StandardDeliveryCompletionDialog.vue";
import StandardSalesInvoiceCompletionDialog from "../professional_selling/StandardSalesInvoiceCompletionDialog.vue";
import StandardPurchaseInvoiceCompletionDialog from "../professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue";
import { callMethod } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const CREATE_DELIVERY_METHOD = "retailedge.professional_delivery.create_delivery_note_from_sales_invoice";
const CREATE_RETURN_METHOD = "retailedge.professional_sales_invoice.create_sales_return_credit_note_draft";
const GLOBAL_CREATE_EVENT = "retailedge-open-global-create";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function writeHandoff(prefix, values) {
	try {
		window.sessionStorage.setItem(
			`${prefix}${encodeURIComponent(frappe.session?.user || "Guest")}`,
			JSON.stringify({ createdAt: Date.now(), values: values || {} })
		);
	} catch (_error) {}
}

export default {
	name: "RetailEdgeGlobalCreateHost",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeEmptyState: runtimeComponents.EdgeEmptyState,
		EdgeIcon: runtimeComponents.EdgeIcon,
		SimpleSalesInvoiceDialog,
		StandardSalesInvoiceCompletionDialog,
		StandardDeliveryCompletionDialog,
		SimplePaymentDialog,
		SimpleCashDepositDialog,
		SimpleCashTransferDialog,
		StandardInternalTransferCompletionDialog,
		SimplePurchaseInvoiceDialog,
		StandardPurchaseInvoiceCompletionDialog,
		SimpleCashierExpenseDialog,
		GuidedWorkflowCompletionDialog,
		SimpleStockTransferDialog,
		SimpleStockAdjustmentDialog,
		StandardStockCompletionDialog,
	},
	data() {
		return {
			pickerOpen: false,
			loading: false,
			loadError: "",
			quickActions: [],
			context: {},
			nativeFallbackEnabled: false,
			simpleSalesInvoiceOpen: false,
			salesCompletionOpen: false,
			salesCompletionDocument: null,
			deliveryCompletionOpen: false,
			deliveryCompletionDocument: null,
			simplePaymentOpen: false,
			simplePaymentIntent: "",
			simplePaymentInitialContext: {},
			simpleCashDepositOpen: false,
			simpleCashTransferOpen: false,
			internalTransferCompletionOpen: false,
			internalTransferCompletionDocument: null,
			simplePurchaseInvoiceOpen: false,
			purchaseCompletionOpen: false,
			purchaseCompletionDocument: null,
			simpleCashierExpenseOpen: false,
			cashierExpenseCompletionOpen: false,
			cashierExpenseCompletionDocument: null,
			simpleStockTransferOpen: false,
			simpleStockAdjustmentOpen: false,
			stockCompletionOpen: false,
			stockCompletionDocument: null,
		};
	},
	mounted() {
		this._openRequest = () => this.openPicker();
		document.addEventListener(GLOBAL_CREATE_EVENT, this._openRequest);
	},
	beforeUnmount() {
		document.removeEventListener(GLOBAL_CREATE_EVENT, this._openRequest);
	},
	methods: {
		async refreshContext() {
			this.loadError = "";
			try {
				let data = null;
				if (typeof window.retailedgeGetBusinessHubContext === "function") {
					data = await window.retailedgeGetBusinessHubContext({ force: true });
				} else {
					data = await callMethod(CONTEXT_METHOD, {}, "GET");
				}
				this.quickActions = Array.isArray(data?.quick_actions) ? data.quick_actions : [];
				this.context = data?.context || {};
				this.nativeFallbackEnabled = Boolean(data?.access?.can_use_native_desk);
				return data || {};
			} catch (error) {
				this.loadError = window.retailedge?.userErrorMessage?.(error, "Unable to load permitted Create actions.") || "Unable to load permitted Create actions.";
				return null;
			}
		},
		async openPicker() {
			if (this.loading) return;
			this.loading = true;
			this.pickerOpen = true;
			await this.refreshContext();
			this.loading = false;
		},
		closePicker() {
			this.pickerOpen = false;
		},
		async runQuickAction(action) {
			if (!action?.key) return;
			this.closePicker();
			switch (action.key) {
				case "new-sales-invoice":
					this.simpleSalesInvoiceOpen = true;
					return;
				case "receive-customer-payment":
				case "pay-supplier":
					this.simplePaymentIntent = action.key;
					this.simplePaymentInitialContext = {};
					this.simplePaymentOpen = true;
					return;
				case "deposit-cash":
					this.simpleCashDepositOpen = true;
					return;
				case "cash-transfer":
					this.simpleCashTransferOpen = true;
					return;
				case "record-purchase":
					this.simplePurchaseInvoiceOpen = true;
					return;
				case "record-expense":
					if (action.doctype === "RetailEdge Business Expense" || action.target === "business-expenses") {
						frappe.route_options = { action: "new" };
						frappe.set_route("business-expenses");
					} else {
						this.simpleCashierExpenseOpen = true;
					}
					return;
				case "transfer-stock":
					this.simpleStockTransferOpen = true;
					return;
				case "adjust-stock":
					this.simpleStockAdjustmentOpen = true;
					return;
				default:
					break;
			}
			const edgeUI = window.EdgeSuiteUI;
			if (action.doctype && typeof edgeUI?.openCreateSurface === "function") {
				try {
					await edgeUI.openCreateSurface(action.doctype, { allowRestricted: true });
				} catch (error) {
					frappe.show_alert?.({ message: window.retailedge?.userErrorMessage?.(error, `Unable to create ${action.doctype}.`) || `Unable to create ${action.doctype}.`, indicator: "red" }, 7);
				}
			}
		},
		openNative(doctype) {
			if (!this.nativeFallbackEnabled || !doctype) return;
			this.resetQuickDialogs();
			frappe.new_doc(doctype);
		},
		openNativeInternalTransfer(doctype = "Payment Entry") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleCashDepositOpen = false;
			this.simpleCashTransferOpen = false;
			frappe.new_doc(doctype, { payment_type: "Internal Transfer" });
		},
		openNativeStockTransfer(doctype = "Stock Entry") {
			if (!this.nativeFallbackEnabled) return;
			this.simpleStockTransferOpen = false;
			frappe.new_doc(doctype, { stock_entry_type: "Material Transfer" });
		},
		resetQuickDialogs() {
			this.simpleSalesInvoiceOpen = false;
			this.simplePaymentOpen = false;
			this.simpleCashDepositOpen = false;
			this.simpleCashTransferOpen = false;
			this.simplePurchaseInvoiceOpen = false;
			this.simpleCashierExpenseOpen = false;
			this.simpleStockTransferOpen = false;
			this.simpleStockAdjustmentOpen = false;
		},
		openFullSalesPage(payload = {}) {
			writeHandoff("retailedge:make-sale:handoff:", payload?.values || {});
			this.simpleSalesInvoiceOpen = false;
			frappe.set_route("make-sale");
		},
		openFullPurchasePage(payload = {}) {
			writeHandoff("retailedge:record-purchase:handoff:", payload?.values || {});
			this.simplePurchaseInvoiceOpen = false;
			frappe.set_route("record-purchase");
		},
		openFullStockTransferPage(payload = {}) {
			writeHandoff("retailedge:transfer-stock:handoff:", payload?.values || {});
			this.simpleStockTransferOpen = false;
			frappe.set_route("transfer-stock");
		},
		openFullStockAdjustmentPage(payload = {}) {
			writeHandoff("retailedge:stock-adjustment:handoff:", payload?.values || {});
			this.simpleStockAdjustmentOpen = false;
			frappe.set_route("stock-adjustment");
		},
		handleSalesInvoiceSaved(result) {
			this.simpleSalesInvoiceOpen = false;
			if (!result?.name) return;
			this.salesCompletionDocument = { doctype: "Sales Invoice", name: result.name };
			this.salesCompletionOpen = true;
		},
		closeSalesCompletion() {
			this.salesCompletionOpen = false;
			this.salesCompletionDocument = null;
		},
		async handleSalesNextAction(payload) {
			if (!payload?.action || !payload?.name) return;
			this.closeSalesCompletion();
			if (payload.action === "make-payment") {
				this.simplePaymentIntent = "receive-customer-payment";
				this.simplePaymentInitialContext = {
					company: payload.company || this.context.company || "",
					branch: payload.branch || this.context.branch || "",
					party: payload.customer || "",
					reference_name: payload.name,
				};
				this.simplePaymentOpen = true;
				return;
			}
			if (payload.action === "create-delivery-note") {
				try {
					const result = await callMethod(CREATE_DELIVERY_METHOD, { sales_invoice: payload.name }, "POST");
					if (result?.name) {
						this.deliveryCompletionDocument = { doctype: "Delivery Note", name: result.name };
						this.deliveryCompletionOpen = true;
					}
				} catch (error) {
					frappe.show_alert?.({ message: window.retailedge?.userErrorMessage?.(error, "Unable to prepare Delivery Note.") || "Unable to prepare Delivery Note.", indicator: "red" }, 8);
				}
				return;
			}
			if (payload.action === "create-return-credit-note") {
				try {
					const result = await callMethod(CREATE_RETURN_METHOD, { sales_invoice: payload.name }, "POST");
					if (result?.name) {
						window.retailedgeProfessionalSellingTarget = { doctype: "Sales Invoice", name: result.name, source_mode: "sales_return", user: frappe.session?.user || "Guest" };
						frappe.set_route("professional-selling");
					}
				} catch (error) {
					frappe.show_alert?.({ message: window.retailedge?.userErrorMessage?.(error, "Unable to prepare Return / Credit Note.") || "Unable to prepare Return / Credit Note.", indicator: "red" }, 8);
				}
				return;
			}
			if (payload.action === "output") this.openOutput("sales-invoice", payload.name);
		},
		closeDeliveryCompletion() {
			this.deliveryCompletionOpen = false;
			this.deliveryCompletionDocument = null;
		},
		handleDeliveryNextAction(payload) {
			if (payload?.action === "output" && payload?.name) {
				this.closeDeliveryCompletion();
				this.openOutput("delivery-note", payload.name);
			}
		},
		closePayment() {
			this.simplePaymentOpen = false;
			this.simplePaymentIntent = "";
			this.simplePaymentInitialContext = {};
		},
		handlePaymentSaved(result) {
			this.closePayment();
			frappe.show_alert?.({ message: `Payment Entry ${result?.name || ""} ${Number(result?.docstatus || 0) === 1 ? "submitted" : "saved as Draft"}`, indicator: "green" }, 7);
			this.refreshContext();
		},
		handleInternalTransferSaved(result) {
			this.simpleCashDepositOpen = false;
			this.simpleCashTransferOpen = false;
			if (!result?.name) return;
			this.internalTransferCompletionDocument = { doctype: "Payment Entry", name: result.name };
			this.internalTransferCompletionOpen = true;
		},
		closeInternalTransferCompletion() {
			this.internalTransferCompletionOpen = false;
			this.internalTransferCompletionDocument = null;
			this.refreshContext();
		},
		handlePurchaseInvoiceSaved(result) {
			this.simplePurchaseInvoiceOpen = false;
			if (!result?.name) return;
			this.purchaseCompletionDocument = { doctype: "Purchase Invoice", name: result.name };
			this.purchaseCompletionOpen = true;
		},
		closePurchaseCompletion() {
			this.purchaseCompletionOpen = false;
			this.purchaseCompletionDocument = null;
		},
		handlePurchaseNextAction(payload) {
			if (!payload?.action || !payload?.name) return;
			this.closePurchaseCompletion();
			if (payload.action === "pay-supplier") {
				this.simplePaymentIntent = "pay-supplier";
				this.simplePaymentInitialContext = {
					company: payload.company || this.context.company || "",
					branch: payload.branch || this.context.branch || "",
					party: payload.supplier || "",
					reference_name: payload.name,
				};
				this.simplePaymentOpen = true;
				return;
			}
			if (payload.action === "create-supplier-debit-note") {
				window.retailedgeProfessionalPurchasingTarget = { action: "supplier-debit-note", source_name: payload.name, user: frappe.session?.user || "Guest" };
				frappe.set_route("professional-purchasing");
				return;
			}
			if (payload.action === "supplier-payables") {
				frappe.route_options = {
					company: payload.company || this.context.company || "",
					branch: payload.branch || this.context.branch || "",
					supplier: payload.supplier || "",
				};
				frappe.set_route("supplier-payables");
				return;
			}
			if (payload.action === "output") this.openOutput("purchase-invoice", payload.name);
		},
		handleCashierExpenseSaved(result) {
			this.simpleCashierExpenseOpen = false;
			const completion = result?.completion || {};
			const name = completion.name || result?.name || "";
			if (!name) return;
			this.cashierExpenseCompletionDocument = {
				doctype: completion.doctype || result?.doctype || "RetailEdge Cashier Expense",
				name,
			};
			this.cashierExpenseCompletionOpen = true;
		},
		closeCashierExpenseCompletion() {
			this.cashierExpenseCompletionOpen = false;
			this.cashierExpenseCompletionDocument = null;
			this.refreshContext();
		},
		handleStockSaved(result) {
			this.simpleStockTransferOpen = false;
			this.simpleStockAdjustmentOpen = false;
			if (!result?.name) return;
			const doctype = result?.doctype || (result?.stock_entry_type ? "Stock Entry" : "Stock Reconciliation");
			this.stockCompletionDocument = { doctype, name: result.name };
			this.stockCompletionOpen = true;
		},
		closeStockCompletion() {
			this.stockCompletionOpen = false;
			this.stockCompletionDocument = null;
			this.refreshContext();
		},
		openOutput(document, name) {
			window.retailedgeDocumentOutputTarget = { document, name, mode: "share" };
			frappe.set_route("document-output-sharing");
		},
	},
};
</script>

<style scoped>
.retailedge-global-create-host { position: relative; z-index: 1; }
.global-create-state { padding: 2rem; text-align: center; color: var(--text-muted); }
.global-create-state--error { color: var(--red-700, #b42318); }
</style>
