<template>
	<EdgeModal
		:open="open"
		title="New Sales Order"
		subtitle="Create a new ERPNext Sales Order draft or convert a submitted Customer Quotation using ERPNext's native mapping."
		size="xl"
		@close="requestClose"
	>
		<div class="order-mode-switch" role="group" aria-label="Sales Order creation mode">
			<button type="button" class="edge-button" :class="{ 'edge-button--primary': mode === 'new' }" :disabled="saving" @click="setMode('new')">New Order</button>
			<button type="button" class="edge-button" :class="{ 'edge-button--primary': mode === 'quotation' }" :disabled="saving" @click="setMode('quotation')">From Submitted Quotation</button>
		</div>

		<div v-if="saveError" class="selling-form-error" role="alert">{{ saveError }}</div>

		<div v-if="mode === 'quotation'" class="source-order-panel">
			<div class="selling-form-context">
				<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || "Not set" }}</strong></div>
			</div>
			<EdgeLinkField
				:modelValue="sourceQuotation"
				label="Submitted Quotation"
				placeholder="Search submitted customer quotation"
				description="ERPNext will map the submitted Quotation into a new draft Sales Order. The source Quotation is not modified."
				:required="true"
				:searcher="searchSourceQuotation"
				@update:modelValue="sourceQuotation = $event || ''"
			/>
			<p class="selling-form-hint">Expired, lost, cancelled and fully ordered quotations are not offered here. ERPNext performs the final conversion eligibility checks.</p>
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
					<span>Order Date <b>*</b></span>
					<input v-model="values.transaction_date" class="form-control" type="date" required />
				</label>

				<label class="selling-field">
					<span>Delivery Date <b>*</b></span>
					<input v-model="values.delivery_date" class="form-control" type="date" :min="values.transaction_date || undefined" required />
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
					label="Source Stock Location"
					placeholder="Optional stock location"
					description="The Stock Location is applied to order items where relevant."
					:searcher="searchWarehouse"
					@update:modelValue="setWarehouse"
				/>

				<EdgeLinkField
					:modelValue="values.shipping_rule"
					label="Shipping Rule"
					placeholder="Optional delivery charge rule"
					description="Only enabled ERPNext Selling Shipping Rules for this Company are shown."
					:searcher="searchShippingRule"
					@update:modelValue="values.shipping_rule = $event || ''"
				/>

				<label class="selling-field">
					<span>Customer Purchase Order</span>
					<input v-model="values.po_no" class="form-control" type="text" placeholder="Optional customer PO reference" />
				</label>
			</div>

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

			<p class="selling-form-hint">Rates are resolved again on the server. Shipping charges are applied through ERPNext's native Shipping Rule engine.</p>

			<label class="selling-field selling-field--wide">
				<span>Terms / Notes</span>
				<textarea v-model="values.terms" class="form-control" rows="3" placeholder="Optional order terms or customer note"></textarea>
			</label>
		</form>

		<template #footer>
			<div class="selling-form-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="$emit('open-native', 'Sales Order')">Open Full Form</button>
				<div class="selling-form-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || (mode === 'quotation' && !sourceQuotation)" @click="saveDraft">{{ saving ? "Saving..." : mode === 'quotation' ? "Create Draft from Quotation" : "Save Draft" }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage, quickCreateCustomer, quickCreateItem, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";

const SEARCH_METHOD = "retailedge.professional_selling.search_professional_selling_options";
const SOURCE_METHOD = "retailedge.professional_selling_sources.search_professional_selling_sources";
const PRICING_METHOD = "retailedge.professional_selling.get_professional_selling_item_pricing";
const CREATE_METHOD = "retailedge.professional_sales_order.create_professional_sales_order_draft";
const MAP_METHOD = "retailedge.professional_sales_order.create_sales_order_from_quotation";
const DOCUMENT = "sales-order";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function initialValues(context = {}) {
	const today = context.today || "";
	return {
		company: context.operating?.company || "",
		branch: context.operating?.branch || "",
		warehouse: context.operating?.default_stock_location || "",
		customer: "",
		transaction_date: today,
		delivery_date: today,
		shipping_rule: "",
		po_no: "",
		terms: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

export default {
	name: "ProfessionalSalesOrderDialog",
	components: { EdgeModal: runtime.EdgeModal, EdgeLinkField: runtime.EdgeLinkField, EdgeChildTable: runtime.EdgeChildTable },
	props: { open: { type: Boolean, default: false }, context: { type: Object, default: () => ({}) } },
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			mode: "new",
			sourceQuotation: "",
			saving: false,
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			values: initialValues(this.context),
			itemTableField: { label: "Items", description: "Add the products or services included in this order." },
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
	},
	watch: {
		open(next) {
			if (next) {
				this.mode = "new";
				this.sourceQuotation = "";
				this.values = initialValues(this.context);
				this.saveError = "";
			}
		},
	},
	methods: {
		setMode(mode) { if (!this.saving) { this.mode = mode; this.saveError = ""; } },
		requestClose() { if (!this.saving) this.$emit("close"); },
		searchOptions(fieldname, query) {
			return callMethod(SEARCH_METHOD, { document: DOCUMENT, fieldname, txt: query || "", values: this.values })
				.then((results) => Array.isArray(results) ? results : []);
		},
		searchSourceQuotation(query) {
			return callMethod(SOURCE_METHOD, { target: DOCUMENT, txt: query || "", values: this.values })
				.then((results) => Array.isArray(results) ? results : []);
		},
		searchCustomer(query) { return this.searchOptions("customer", query); },
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchShippingRule(query) { return this.searchOptions("shipping_rule", query); },
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
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			if (!branch || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve Branch Stock Location.");
			}
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			if (!warehouse || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, warehouse, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || warehouse;
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
				if (row.item_code && row.item_code !== prior.item_code) {
					changed.push(index);
					return { ...row, rate: "" };
				}
				return { ...row };
			});
			changed.forEach((index) => this.loadItemPricing(index));
		},
		async loadItemPricing(index) {
			const row = this.values.items[index];
			if (!row?.item_code || !this.values.customer) return;
			const token = `${row.item_code}:${Date.now()}:${Math.random()}`;
			this.pricingTokens[index] = token;
			try {
				const result = await callMethod(PRICING_METHOD, { document: DOCUMENT, item_code: row.item_code, values: { ...this.values, qty: row.qty || 1 } });
				if (this.pricingTokens[index] !== token || this.values.items[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) this.values.items[index] = { ...this.values.items[index], rate: result.rate };
			} catch (error) {
				if (this.pricingTokens[index] === token) this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
			}
		},
		refreshAllItemPricing() {
			if (!this.values.customer) return;
			this.values.items.forEach((row, index) => {
				if (row.item_code) {
					this.values.items[index] = { ...row, rate: "" };
					this.loadItemPricing(index);
				}
			});
		},
		async saveDraft() {
			if (this.saving) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = this.mode === "quotation"
					? await callMethod(MAP_METHOD, { quotation: this.sourceQuotation })
					: await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Sales Order draft.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.order-mode-switch { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
.source-order-panel, .selling-form { display: grid; gap: 18px; }
.selling-form-context { display: flex; flex-wrap: wrap; gap: 10px; }
.selling-form-context > div { display: grid; gap: 2px; min-width: 180px; padding: 9px 12px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 8px; background: var(--edge-surface-muted, #f8fafc); }
.selling-form-context span, .selling-field > span { font-size: 0.78rem; color: var(--edge-text-muted, #667085); }
.selling-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.selling-field { display: grid; gap: 6px; }
.selling-field--wide { grid-column: 1 / -1; }
.selling-form-error { margin-bottom: 1rem; padding: 10px 12px; border-radius: 8px; background: var(--red-50, #fef2f2); color: var(--red-700, #b91c1c); border: 1px solid var(--red-200, #fecaca); }
.selling-form-hint { margin: 0; color: var(--edge-text-muted, #667085); font-size: 0.84rem; }
.selling-form-footer, .selling-form-footer-actions { display: flex; align-items: center; gap: 10px; }
.selling-form-footer { justify-content: space-between; width: 100%; }
@media (max-width: 760px) { .selling-form-grid { grid-template-columns: 1fr; } .order-mode-switch { flex-direction: column; } .selling-form-footer { align-items: stretch; flex-direction: column; } .selling-form-footer-actions { justify-content: flex-end; } }
</style>
