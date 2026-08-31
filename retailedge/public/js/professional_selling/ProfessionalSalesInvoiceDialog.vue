<template>
	<EdgeModal
		:open="open"
		title="Sales Invoice"
		subtitle="Create a new draft invoice, invoice a submitted source document, or prepare an ERPNext Return / Credit Note without forcing a rigid selling path."
		size="xl"
		@close="requestClose"
	>
		<div class="invoice-mode-switch" role="group" aria-label="Sales Invoice creation mode">
			<button v-for="option in modes" :key="option.key" type="button" class="edge-button" :class="{ 'edge-button--primary': mode === option.key }" :disabled="saving" @click="setMode(option.key)">{{ option.label }}</button>
		</div>

		<div v-if="saveError" class="selling-form-error" role="alert">{{ saveError }}</div>

		<div v-if="mode !== 'new'" class="source-invoice-panel">
			<div class="selling-form-context">
				<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || "Not set" }}</strong></div>
			</div>
			<EdgeLinkField
				:modelValue="sourceDocument"
				:label="sourceLabel"
				:placeholder="`Search submitted ${sourceLabel.toLowerCase()}`"
				:description="sourceDescription"
				:required="true"
				:searcher="searchSource"
				@update:modelValue="sourceDocument = $event || ''"
			/>
			<p class="selling-form-hint">{{ sourceHint }}</p>
		</div>

		<form v-else class="selling-form" @submit.prevent="saveDraft">
			<div class="selling-form-context">
				<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || "Not set" }}</strong></div>
				<div><span>Selling Price List</span><strong>{{ priceListLabel }}</strong></div>
			</div>

			<div class="selling-form-grid">
				<EdgeLinkField
					:modelValue="values.customer"
					label="Customer"
					placeholder="Search customer"
					:required="true"
					:searcher="searchCustomer"
					:canCreate="canCreateCustomer"
					:creator="createCustomer"
					createLabel="Create Customer"
					@update:modelValue="setCustomer"
				/>

				<label class="selling-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>

				<EdgeLinkField
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					:searcher="searchBranch"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Stock Location"
					placeholder="Optional stock location"
					:required="Boolean(values.update_stock)"
					:searcher="searchWarehouse"
					@update:modelValue="setWarehouse"
				/>

				<EdgeLinkField
					:modelValue="values.shipping_rule"
					label="Shipping Rule"
					placeholder="Optional delivery charge rule"
					description="ERPNext calculates delivery charges from the selected Selling Shipping Rule."
					:searcher="searchShippingRule"
					@update:modelValue="values.shipping_rule = $event || ''"
				/>
			</div>

			<CustomerCreditSummary :customer="values.customer" :company="values.company" />

			<label class="guided-check-field">
				<input v-model="values.update_stock" type="checkbox" :true-value="1" :false-value="0" />
				<span><strong>Update Stock</strong><small>Stock moves only if this draft is later submitted by an authorised user.</small></span>
			</label>

			<EdgeChildTable
				:field="itemTableField"
				:rows="values.items"
				:columns="itemColumns"
				:addLabel="'Add Item'"
				:linkSearcher="searchLineLink"
				:linkCanCreate="canCreateItemLink"
				:linkCreator="createItemLink"
				:linkCreateLabel="itemCreateLabel"
				:newRowsFirst="true"
				@update:rows="updateItems"
			/>

			<p class="selling-form-hint">RetailEdge resolves selling prices again on the server. Delivery charges remain ERPNext Shipping Rule calculations.</p>

			<label class="selling-field selling-field--wide">
				<span>Remarks</span>
				<textarea v-model="values.remarks" class="form-control" rows="3" placeholder="Optional invoice note"></textarea>
			</label>
		</form>

		<template #footer>
			<div class="selling-form-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="$emit('open-native', 'Sales Invoice')">Open Full Form</button>
				<div class="selling-form-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || (mode !== 'new' && !sourceDocument)" @click="saveDraft">{{ saving ? "Saving..." : saveLabel }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage, quickCreateCustomer, quickCreateItem, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import CustomerCreditSummary from "./CustomerCreditSummary.vue";

const GUIDED_SEARCH = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const GUIDED_PRICING = "retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing";
const SHIPPING_SEARCH = "retailedge.professional_sales_invoice.search_professional_invoice_shipping_rules";
const SOURCE_SEARCH = "retailedge.professional_sales_invoice.search_professional_invoice_sources";
const CREATE_NEW = "retailedge.professional_sales_invoice.create_professional_sales_invoice_draft";
const CREATE_FROM_QUOTATION = "retailedge.professional_sales_invoice.create_sales_invoice_from_quotation";
const CREATE_FROM_ORDER = "retailedge.professional_sales_invoice.create_sales_invoice_from_sales_order";
const CREATE_FROM_DELIVERY = "retailedge.professional_sales_invoice.create_sales_invoice_from_delivery_note";
const CREATE_RETURN = "retailedge.professional_sales_invoice.create_sales_return_credit_note_draft";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function initialValues(context = {}) {
	return {
		company: context.operating?.company || "",
		branch: context.operating?.branch || "",
		warehouse: context.operating?.default_stock_location || "",
		customer: "",
		posting_date: context.today || "",
		shipping_rule: "",
		update_stock: 0,
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

export default {
	name: "ProfessionalSalesInvoiceDialog",
	components: { EdgeModal: runtime.EdgeModal, EdgeLinkField: runtime.EdgeLinkField, EdgeChildTable: runtime.EdgeChildTable, CustomerCreditSummary },
	props: { open: { type: Boolean, default: false }, context: { type: Object, default: () => ({}) } },
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			mode: "new",
			sourceDocument: "",
			saving: false,
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			values: initialValues(this.context),
			modes: [
				{ key: "new", label: "New Invoice" },
				{ key: "quotation", label: "From Quotation" },
				{ key: "sales-order", label: "From Sales Order" },
				{ key: "delivery-note", label: "From Delivery Note" },
				{ key: "return", label: "Return / Credit Note" },
			],
			itemTableField: { label: "Items", description: "Add the products or services to invoice." },
			itemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Selling Rate", fieldtype: "Currency", placeholder: "Auto price" },
			],
		};
	},
	computed: {
		priceListLabel() { return this.context.pricing?.price_list || "ERPNext default"; },
		canCreateCustomer() { return Boolean(frappe.model?.can_create?.("Customer")); },
		canCreateItem() { return Boolean(frappe.model?.can_create?.("Item")); },
		sourceLabel() {
			return { quotation: "Submitted Quotation", "sales-order": "Submitted Sales Order", "delivery-note": "Submitted Delivery Note", return: "Submitted Sales Invoice" }[this.mode] || "Source Document";
		},
		sourceDescription() {
			if (this.mode === "return") return "ERPNext prepares a draft Return / Credit Note from the selected submitted Sales Invoice. The source remains submitted and unchanged.";
			return this.mode === "quotation"
				? "Create the invoice directly from the accepted Quotation; no Sales Order is created behind the scenes."
				: `ERPNext maps the ${this.sourceLabel.replace("Submitted ", "")} into a new Sales Invoice draft using remaining billable quantities.`;
		},
		sourceHint() {
			if (this.mode === "return") return "ERPNext owns the return quantities, stock rules, taxes and accounting. Review the prepared draft in the standard Sales Invoice form; no refund or Payment Entry is created automatically.";
			return "The source remains submitted and unchanged. RetailEdge creates a new ERPNext Sales Invoice draft only.";
		},
		saveLabel() {
			if (this.mode === "new") return "Save Draft";
			if (this.mode === "return") return "Prepare Draft Return / Credit Note";
			return `Create Draft from ${this.sourceLabel.replace("Submitted ", "")}`;
		},
	},
	watch: {
		open(next) {
			if (next) {
				this.mode = "new";
				this.sourceDocument = "";
				this.values = initialValues(this.context);
				this.saveError = "";
			}
		},
	},
	methods: {
		setMode(mode) { if (!this.saving) { this.mode = mode; this.sourceDocument = ""; this.saveError = ""; } },
		requestClose() { if (!this.saving) this.$emit("close"); },
		searchOptions(fieldname, query) {
			return callMethod(GUIDED_SEARCH, { fieldname, txt: query || "", values: this.values }).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchCustomer(query) { return this.searchOptions("customer", query); },
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchShippingRule(query) {
			return callMethod(SHIPPING_SEARCH, { txt: query || "", values: this.values }).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchSource(query) {
			return callMethod(SOURCE_SEARCH, { source: this.mode, txt: query || "", values: this.values }).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		createCustomer(query) { return quickCreateCustomer(query); },
		canCreateItemLink(column) { return this.canCreateItem && column?.fieldname === "item_code"; },
		createItemLink(column, query) { return column?.fieldname === "item_code" ? quickCreateItem(query) : Promise.resolve(null); },
		itemCreateLabel(column) { return column?.fieldname === "item_code" ? "Create Item" : "Create new"; },
		setCustomer(next) {
			const changed = this.values.customer && this.values.customer !== next;
			this.values.customer = next || "";
			if (changed) {
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "" }));
				this.refreshAllItemPricing();
			}
		},
		async setBranch(next) {
			this.values.branch = next || "";
			this.values.warehouse = "";
			if (!this.values.branch || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || "";
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve Branch Stock Location.");
			}
		},
		async setWarehouse(next) {
			this.values.warehouse = next || "";
			if (!this.values.warehouse || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || this.values.warehouse;
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) {
					this.values.warehouse = "";
					this.saveError = errorMessage(error, "Unable to use the selected Stock Location.");
				}
			}
		},
		updateItems(nextRows) {
			const previous = this.values.items || [];
			const changed = [];
			this.values.items = (nextRows || []).map((row, index) => {
				const prior = previous[index] || {};
				if (row.item_code && row.item_code !== prior.item_code) changed.push(index);
				return { item_code: row.item_code || "", qty: row.qty || 1, rate: row.rate ?? "" };
			});
			changed.forEach((index) => this.refreshItemPricing(index));
		},
		async refreshItemPricing(index) {
			const row = this.values.items[index];
			if (!row?.item_code || !this.values.customer) return;
			const token = (this.pricingTokens[index] || 0) + 1;
			this.pricingTokens[index] = token;
			try {
				const pricing = await callMethod(GUIDED_PRICING, { item_code: row.item_code, values: { ...this.values, qty: row.qty } });
				if (this.pricingTokens[index] !== token) return;
				this.values.items[index] = { ...this.values.items[index], rate: pricing.rate ?? "" };
				this.values.items = [...this.values.items];
			} catch (error) {
				if (this.pricingTokens[index] === token) this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
			}
		},
		refreshAllItemPricing() { this.values.items.forEach((row, index) => { if (row.item_code) this.refreshItemPricing(index); }); },
		async saveDraft() {
			if (this.saving) return;
			this.saving = true;
			this.saveError = "";
			try {
				let method = CREATE_NEW;
				let args = { values: this.values };
				if (this.mode === "quotation") { method = CREATE_FROM_QUOTATION; args = { quotation: this.sourceDocument }; }
				if (this.mode === "sales-order") { method = CREATE_FROM_ORDER; args = { sales_order: this.sourceDocument }; }
				if (this.mode === "delivery-note") { method = CREATE_FROM_DELIVERY; args = { delivery_note: this.sourceDocument }; }
				if (this.mode === "return") { method = CREATE_RETURN; args = { sales_invoice: this.sourceDocument }; }
				const result = await callMethod(method, args);
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, this.mode === "return" ? "Return / Credit Note draft could not be prepared." : "Sales Invoice draft could not be created.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.invoice-mode-switch { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1rem; }
.source-invoice-panel { display: grid; gap: 1rem; }
.selling-form { display: grid; gap: 1rem; }
.selling-form-context { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
.selling-form-context > div { display: grid; gap: 0.2rem; }
.selling-form-context span, .selling-form-hint, .guided-check-field small { color: var(--text-muted); font-size: 0.8rem; }
.selling-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.9rem; }
.selling-field { display: grid; gap: 0.35rem; }
.selling-field--wide { grid-column: 1 / -1; }
.guided-check-field { display: flex; align-items: flex-start; gap: 0.65rem; }
.guided-check-field span { display: grid; gap: 0.2rem; }
.selling-form-footer { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.selling-form-footer-actions { display: flex; gap: 0.5rem; }
.selling-form-error { padding: 0.75rem; margin-bottom: 1rem; border: 1px solid var(--red-300, #f1aeb5); border-radius: 0.5rem; }
@media (max-width: 720px) { .selling-form-context, .selling-form-grid { grid-template-columns: 1fr; } .selling-form-footer { align-items: stretch; flex-direction: column; } .selling-form-footer-actions { justify-content: flex-end; } }
</style>
