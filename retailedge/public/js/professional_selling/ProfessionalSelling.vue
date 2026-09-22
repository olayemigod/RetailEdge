<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Professional Selling could not start.</strong>
		<div>Required interface components are unavailable. Refresh the page or contact your administrator.</div>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
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
				description="Prepare quotations, orders, deliveries and invoices using the documents your transaction actually needs while ERPNext remains the system of record."
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
						<span class="selling-kicker">Flexible selling paths</span>
						<h3>Use the next document the business transaction requires</h3>
						<p>A Quotation can become an Order or go directly to Invoice. Orders can be delivered or invoiced. Delivery Notes can be invoiced. ERPNext pricing, taxes, Shipping Rules, stock and accounting remain authoritative.</p>
					</div>
					<EdgeStatusBadge :status="shipping.available ? 'Active' : 'Warning'" />
				</section>

				<div class="selling-flow" aria-label="Professional selling documents">
					<section v-for="(document, index) in documents" :key="document.key" class="edge-panel selling-stage">
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
							<span v-if="document.key === 'sales-invoice'">Flexible Conversion</span>
						</div>
						<div class="selling-actions">
							<button v-if="document.can_create" type="button" class="edge-button edge-button--primary" @click="startCreate(document)">{{ createLabel(document) }}</button>
							<button v-if="document.can_read" type="button" class="edge-button edge-button--secondary" @click="openRecords(document)">View records</button>
							<button v-if="document.can_read && canUseNativeDesk" type="button" class="edge-button edge-button--secondary" @click="openAdvancedNative(document)">Advanced: Open in ERPNext</button>
						</div>
					</section>
				</div>

				<ProfessionalSellingRecords
					ref="sellingRecords"
					:documents="documents"
					:canUseNativeDesk="canUseNativeDesk"
					@action="handleRecordAction"
				/>

			</div>

			<ProfessionalQuotationDialog
				:open="quotationOpen"
				:context="sellingContext"
				@close="quotationOpen = false"
				@saved="handleQuotationSaved"
			/>
			<ProfessionalSalesOrderDialog
				:open="salesOrderOpen"
				:context="sellingContext"
				@close="salesOrderOpen = false"
				@saved="handleSalesOrderSaved"
			/>
			<ProfessionalDeliveryDialog
				:open="deliveryOpen"
				:context="sellingContext"
				@close="deliveryOpen = false"
				@saved="handleDeliverySaved"
			/>
			<ProfessionalSalesInvoiceDialog
				:open="salesInvoiceOpen"
				:context="sellingContext"
				:canUseNativeDesk="canUseNativeDesk"
				@close="salesInvoiceOpen = false"
				@saved="handleSalesInvoiceSaved"
			/>
			<StandardSellingCompletionDialog
				:open="completionOpen"
				:document="completionDocument"
				:canUseNativeDesk="canUseNativeDesk"
				@close="closeStandardCompletion"
				@changed="handleCompletionChanged"
				@completed="handleCompletionCompleted"
				@next-action="handleCompletionNextAction"
			/>
			<StandardDeliveryCompletionDialog
				:open="deliveryCompletionOpen"
				:document="deliveryCompletionDocument"
				:canUseNativeDesk="canUseNativeDesk"
				@close="closeDeliveryCompletion"
				@changed="handleDeliveryCompletionChanged"
				@completed="handleDeliveryCompletionCompleted"
				@next-action="handleCompletionNextAction"
			/>
			<StandardSalesInvoiceCompletionDialog
				:open="salesInvoiceCompletionOpen"
				:document="salesInvoiceCompletionDocument"
				:canUseNativeDesk="canUseNativeDesk"
				:showNextActions="true"
				@close="closeSalesInvoiceCompletion"
				@changed="handleSalesInvoiceCompletionChanged"
				@completed="handleSalesInvoiceCompletionCompleted"
				@next-action="handleCompletionNextAction"
			/>
			<SimplePaymentDialog
				:open="paymentOpen"
				:intent="paymentIntent"
				:initialContext="paymentInitialContext"
				:nativeFallbackEnabled="canUseNativeDesk"
				@close="closePayment"
				@saved="handlePaymentSaved"
				@open-native="openNativePayment"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import ProfessionalQuotationDialog from "./ProfessionalQuotationDialog.vue";
import ProfessionalSalesOrderDialog from "./ProfessionalSalesOrderDialog.vue";
import ProfessionalDeliveryDialog from "./ProfessionalDeliveryDialog.vue";
import ProfessionalSalesInvoiceDialog from "./ProfessionalSalesInvoiceDialog.vue";
import StandardSellingCompletionDialog from "./StandardSellingCompletionDialog.vue";
import StandardDeliveryCompletionDialog from "./StandardDeliveryCompletionDialog.vue";
import StandardSalesInvoiceCompletionDialog from "./StandardSalesInvoiceCompletionDialog.vue";
import ProfessionalSellingRecords from "./ProfessionalSellingRecords.vue";
import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue";

const CONTEXT_METHOD = "retailedge.professional_selling.get_professional_selling_context";
const INVOICE_CAPABILITY_METHOD = "retailedge.professional_sales_invoice.get_professional_sales_invoice_capability";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeEmptyState", "EdgeStatusBadge"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function doctypeSlug(doctype) {
	return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

export default {
	name: "RetailEdgeProfessionalSelling",
	components: {
		...Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
		ProfessionalQuotationDialog,
		ProfessionalSalesOrderDialog,
		ProfessionalDeliveryDialog,
		ProfessionalSalesInvoiceDialog,
		StandardSellingCompletionDialog,
		StandardDeliveryCompletionDialog,
		StandardSalesInvoiceCompletionDialog,
		ProfessionalSellingRecords,
		SimplePaymentDialog,
	},
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
			sellingContext: {},
			canUseNativeDesk: false,
			quotationOpen: false,
			salesOrderOpen: false,
			deliveryOpen: false,
			salesInvoiceOpen: false,
			completionOpen: false,
			completionDocument: null,
			deliveryCompletionOpen: false,
			deliveryCompletionDocument: null,
			salesInvoiceCompletionOpen: false,
			salesInvoiceCompletionDocument: null,
			paymentOpen: false,
			paymentIntent: "",
			paymentInitialContext: {},
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
				const [selling, invoice, navigation] = await Promise.all([
					callMethod(CONTEXT_METHOD),
					callMethod(INVOICE_CAPABILITY_METHOD),
					navigationPromise,
				]);
				this.sellingContext = selling || {};
				this.tenantName = selling.operating?.company || navigation.context?.company || "";
				this.branchName = selling.operating?.branch || navigation.context?.branch || "";
				this.userName = navigation.context?.user_name || selling.user_name || "";
				this.pricing = selling.pricing || {};
				this.shipping = selling.shipping || {};
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				const allDocuments = [...(Array.isArray(selling.documents) ? selling.documents : []), invoice];
				this.documents = allDocuments.filter((row) => row?.available && (row.can_read || row.can_create));
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.loaded = true;
				this.applyPendingTarget();
			} catch (error) {
				this.error = errorMessage(error, "Professional Selling failed to load.");
			} finally {
				this.loading = false;
			}
		},
		applyPendingTarget() {
			const target = window.retailedgeProfessionalSellingTarget;
			if (!target?.doctype || !target?.name) return;
			delete window.retailedgeProfessionalSellingTarget;
			if (target.doctype === "Sales Invoice") this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: target.name });
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
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target) window.open(item.target, "_blank", "noopener,noreferrer");
		},
		stageDescription(key) {
			return ({
				quotation: "Prepare a customer offer using ERPNext pricing, taxes and optional Shipping Rule before commitment.",
				"sales-order": "Confirm an order when the business needs order tracking, fulfilment or a customer PO workflow.",
				"delivery-note": "Record fulfilment from a submitted Sales Order using ERPNext remaining quantities and stock truth.",
				"sales-invoice": "Invoice directly, from an accepted Quotation, from a Sales Order, or from a Delivery Note while preserving ERPNext accounting controls.",
			})[key] || "Continue the selling workflow.";
		},
		createLabel(document) {
			if (document?.key === "quotation") return "Guided Quotation";
			if (document?.key === "sales-order") return "Guided Sales Order";
			if (document?.key === "delivery-note") return "Create Delivery";
			if (document?.key === "sales-invoice") return "Create / Convert Invoice";
			return `Create ${document?.label || "Document"}`;
		},
		startCreate(document) {
			if (document?.key === "quotation") { this.quotationOpen = true; return; }
			if (document?.key === "sales-order") { this.salesOrderOpen = true; return; }
			if (document?.key === "delivery-note") { this.deliveryOpen = true; return; }
			if (document?.key === "sales-invoice") { this.salesInvoiceOpen = true; }
		},
		openAdvancedNative(document) {
			if (!this.canUseNativeDesk || !document?.doctype) return;
			window.open(document.native_route || `/app/${doctypeSlug(document.doctype)}`, "_blank", "noopener,noreferrer");
		},
		openAdvancedRecord(document, name) {
			if (!this.canUseNativeDesk || !document?.doctype || !name) return;
			window.open(`/app/${doctypeSlug(document.doctype)}/${encodeURIComponent(name)}`, "_blank", "noopener,noreferrer");
		},
		handleQuotationSaved(result) {
			this.quotationOpen = false;
			if (result?.name) this.openStandardCompletion({ doctype: "Quotation", name: result.name });
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleSalesOrderSaved(result) {
			this.salesOrderOpen = false;
			if (result?.name) this.openStandardCompletion({ doctype: "Sales Order", name: result.name });
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleDeliverySaved(result) {
			this.deliveryOpen = false;
			if (result?.name) this.openDeliveryCompletion({ doctype: "Delivery Note", name: result.name });
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleSalesInvoiceSaved(result) {
			this.salesInvoiceOpen = false;
			if (result?.name && result?.is_return) {
				if (this.canUseNativeDesk) {
					frappe.show_alert({ message: __("Draft Return / Credit Note prepared for Advanced ERPNext review."), indicator: "orange" });
					frappe.set_route("Form", "Sales Invoice", result.name);
				}
			} else if (result?.name) {
				this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: result.name });
			}
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		openRecords(document) {
			if (!document?.key) return;
			this.$refs.sellingRecords?.selectDocument?.(document.key);
		},
		async handleRecordAction(payload) {
			const action = payload?.action;
			const document = payload?.document;
			const row = payload?.row;
			if (!document?.key || !row?.name) return;
			if (action === "view") { this.openDocumentOutput(document, row, "view"); return; }
			if (action === "output") { this.openDocumentOutput(document, row, "share"); return; }
			if (action === "advanced") { this.openAdvancedRecord(document, row.name); return; }
			if (action === "make-payment") { this.openCustomerPayment(document, row); return; }
			if (["create-sales-order", "create-delivery-note", "create-sales-invoice"].includes(action)) {
				await this.runConversionAction(action, document, row);
				return;
			}
			if (action !== "complete" || Number(row.docstatus || 0) !== 0) return;
			if (document.key === "quotation") { this.openStandardCompletion({ doctype: "Quotation", name: row.name }); return; }
			if (document.key === "sales-order") { this.openStandardCompletion({ doctype: "Sales Order", name: row.name }); return; }
			if (document.key === "delivery-note") { this.openDeliveryCompletion({ doctype: "Delivery Note", name: row.name }); return; }
			if (document.key === "sales-invoice") this.openSalesInvoiceCompletion({ doctype: "Sales Invoice", name: row.name });
		},
		async runConversionAction(action, document, row) {
			const route = {
				"create-sales-order": { method: "retailedge.professional_sales_order.create_sales_order_from_quotation", args: { quotation: row.name } },
				"create-sales-invoice": document.key === "quotation"
					? { method: "retailedge.professional_sales_invoice.create_sales_invoice_from_quotation", args: { quotation: row.name } }
					: document.key === "sales-order"
						? { method: "retailedge.professional_sales_invoice.create_sales_invoice_from_sales_order", args: { sales_order: row.name } }
						: { method: "retailedge.professional_sales_invoice.create_sales_invoice_from_delivery_note", args: { delivery_note: row.name } },
				"create-delivery-note": document.key === "sales-invoice"
					? { method: "retailedge.professional_delivery.create_delivery_note_from_sales_invoice", args: { sales_invoice: row.name } }
					: { method: "retailedge.professional_delivery.create_delivery_note_from_sales_order", args: { sales_order: row.name } },
			}[action];
			if (!route?.method) return;
			try {
				const result = await callMethod(route.method, route.args, "POST");
				this.$refs.sellingRecords?.refresh?.();

				if (result.existing) {
					const label = (result.doctype || "Document") + " " + (result.name || "");
					if (result.requires_amend || Number(result.docstatus || 0) === 2) {
						frappe.msgprint({
							title: __("Existing cancelled invoice"),
							message: __(label + " already came from this Quotation. Open it and use Amend instead of creating another invoice."),
							indicator: "orange",
						});
						if (this.canUseNativeDesk) frappe.set_route("Form", "Sales Invoice", result.name);
						return;
					}
					frappe.show_alert({ message: __(label + " already exists. Opening it instead."), indicator: "blue" });
					if (Number(result.docstatus || 0) === 0) {
						if (result.doctype === "Sales Order") this.openStandardCompletion(result);
						else if (result.doctype === "Delivery Note") this.openDeliveryCompletion(result);
						else if (result.doctype === "Sales Invoice") this.openSalesInvoiceCompletion(result);
						else {
							const existingDocument = this.documents.find((item) => item.doctype === result.doctype) || document;
							this.openDocumentOutput(existingDocument, result, "view");
						}
					} else {
						const existingDocument = this.documents.find((item) => item.doctype === result.doctype) || document;
						this.openDocumentOutput(existingDocument, result, "view");
					}
					return;
				}

				frappe.show_alert({ message: __((result.doctype || "Document") + " " + (result.name || "") + " created as draft"), indicator: "green" });
				if (result.doctype === "Sales Order") this.openStandardCompletion(result);
				else if (result.doctype === "Delivery Note") this.openDeliveryCompletion(result);
				else if (result.doctype === "Sales Invoice") this.openSalesInvoiceCompletion(result);
			} catch (error) {
				frappe.msgprint({ title: __("Unable to continue selling workflow"), message: errorMessage(error, "ERPNext could not create the requested downstream document."), indicator: "red" });
			}
		},
		openCustomerPayment(document, row) {
			if (!["sales-order", "sales-invoice"].includes(document?.key) || !row?.name) return;
			this.paymentIntent = document.key === "sales-order" ? "receive-sales-order-payment" : "receive-customer-payment";
			this.paymentInitialContext = {
				company: this.sellingContext?.operating?.company || this.tenantName || "",
				branch: row.branch || row.retailedge_branch || this.sellingContext?.operating?.branch || this.branchName || "",
				party: row.customer || "",
				reference_name: row.name,
			};
			this.paymentOpen = true;
		},
		closePayment() {
			this.paymentOpen = false;
			this.paymentIntent = "";
			this.paymentInitialContext = {};
			this.$refs.sellingRecords?.refresh?.();
		},
		handlePaymentSaved() { this.closePayment(); this.loadWorkspace(); },
		openNativePayment() {
			if (!this.canUseNativeDesk) return;
			window.open("/app/payment-entry/new-payment-entry", "_blank", "noopener,noreferrer");
		},
		handleCompletionNextAction(payload) {
			const doctypeToKey = { "Quotation": "quotation", "Sales Order": "sales-order", "Delivery Note": "delivery-note", "Sales Invoice": "sales-invoice" };
			const key = doctypeToKey[payload?.doctype];
			if (!key || !payload?.name || !payload?.action) return;

			// Keep the completed review visible until the user chooses what to do.
			// Once chosen, transition cleanly into the next workflow without stacked modals.
			if (["Quotation", "Sales Order"].includes(payload.doctype)) this.closeStandardCompletion();
			else if (payload.doctype === "Delivery Note") this.closeDeliveryCompletion();
			else if (payload.doctype === "Sales Invoice") this.closeSalesInvoiceCompletion();

			const document = this.documents.find((row) => row.key === key) || { key, doctype: payload.doctype };
			this.handleRecordAction({
				action: payload.action,
				document,
				row: { name: payload.name, docstatus: 1, customer: payload.customer || "" },
			});
		},

		openDocumentOutput(document, row, mode = "share") {
			if (!document?.key || !row?.name) return;
			window.retailedgeDocumentOutputTarget = { document: document.key, name: row.name, mode };
			frappe.set_route("document-output-sharing");
		},

		openStandardCompletion(document) {
			if (!["Quotation", "Sales Order"].includes(document?.doctype) || !document?.name) return;
			this.completionDocument = { doctype: document.doctype, name: document.name };
			this.completionOpen = true;
		},
		closeStandardCompletion() {
			this.completionOpen = false;
			this.completionDocument = null;
		},
		handleCompletionChanged() {
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleCompletionCompleted() {
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		openDeliveryCompletion(document) {
			if (document?.doctype !== "Delivery Note" || !document?.name) return;
			this.deliveryCompletionDocument = { doctype: "Delivery Note", name: document.name };
			this.deliveryCompletionOpen = true;
		},
		closeDeliveryCompletion() {
			this.deliveryCompletionOpen = false;
			this.deliveryCompletionDocument = null;
		},
		handleDeliveryCompletionChanged() {
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleDeliveryCompletionCompleted() {
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
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
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		handleSalesInvoiceCompletionCompleted() {
			this.loadWorkspace();
			this.$refs.sellingRecords?.refresh?.();
		},
		openOperatingContext() { frappe.set_route("operating-context"); },
	},
};
</script>

<style scoped>
.selling-content { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.selling-context, .policy-panel { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.selling-context h3, .policy-panel h3, .selling-stage h3 { margin: 0.2rem 0 0.35rem; }
.selling-context p, .policy-panel p, .selling-stage p { margin: 0; color: var(--text-muted); }
.selling-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.context-meta { display: grid; gap: 0.2rem; min-width: 12rem; }
.context-meta span { color: var(--text-muted); font-size: 0.8rem; }
.selling-flow { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; align-items: stretch; }
.selling-stage { min-height: 14rem; display: flex; flex-direction: column; gap: 0.8rem; }
.stage-heading { display: flex; gap: 0.75rem; align-items: flex-start; }
.stage-number { width: 2rem; height: 2rem; border-radius: 999px; display: inline-grid; place-items: center; background: var(--subtle-fg, var(--control-bg)); font-weight: 700; }
.stage-flags, .selling-actions { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: auto; }
.stage-flags span { padding: 0.2rem 0.5rem; border-radius: 999px; background: var(--subtle-fg, var(--control-bg)); color: var(--text-muted); font-size: 0.75rem; }
:deep(.selling-form-footer > .edge-button:first-child) { display: none !important; }
@media (max-width: 1100px) { .selling-flow { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .selling-flow { grid-template-columns: 1fr; } .selling-context, .policy-panel { flex-direction: column; } }
</style>