<template>
	<EdgeModal
		:open="open"
		title="New Quotation"
		subtitle="Prepare a customer quotation using governed pricing, discounts, tax and the current Operating Context."
		size="xl"
		@close="requestClose"
	>
		<form class="selling-form" @submit.prevent="saveDraft">
			<div class="selling-form-context">
				<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || "Not set" }}</strong></div>
				<div><span>Selling Price List</span><strong>{{ priceListLabel }}</strong></div>
			</div>

			<div v-if="saveError" class="selling-form-error" role="alert">{{ saveError }}</div>

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

				<EdgeInput
					:modelValue="values.transaction_date"
					id="professional-quotation-date"
					label="Quotation Date"
					type="date"
					required
					@update:modelValue="setTransactionDate"
				/>

				<EdgeInput
					:modelValue="values.valid_till"
					id="professional-quotation-valid-till"
					label="Valid Till"
					type="date"
					:min="values.transaction_date || undefined"
					@update:modelValue="values.valid_till = $event || ''"
				/>

				<EdgeLinkField
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					:searcher="searchBranch"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.price_list"
					label="Selling Price List"
					placeholder="Select assigned Price List"
					description="The effective default follows Price List Governance. When switching is allowed, choose from your Branch-assigned Price Lists."
					:required="Boolean(pricingContext.selection_required)"
					:disabled="Boolean(pricingContext.locked) || !Boolean(pricingContext.can_select)"
					:searcher="searchPriceList"
					@update:modelValue="setPriceList"
				/>

				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Stock Location"
					placeholder="Optional stock location"
					description="Used for item availability/pricing context; Quotation does not post stock."
					:searcher="searchWarehouse"
					@update:modelValue="setWarehouse"
				/>

				<EdgeLinkField
					:modelValue="values.shipping_rule"
					label="Shipping Rule"
					placeholder="Optional delivery charge rule"
					description="Only enabled Selling Shipping Rules for this Company are shown."
					:searcher="searchShippingRule"
					@update:modelValue="values.shipping_rule = $event || ''"
				/>
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

			<ProfessionalSalesCommercialPanel
				:values="values"
				documentType="Quotation"
				documentLabel="Quotation"
				:disabled="saving"
				@change="updateCommercialTerms"
				@state="updateCommercialState"
			/>

			<p class="selling-form-hint">
				Selling prices, line discounts, promotions and taxes are resolved again before the draft is saved.
			</p>

			<EdgeTextarea
				v-model="values.terms"
				id="professional-quotation-terms"
				label="Terms / Notes"
				rows="3"
				placeholder="Optional quotation terms or customer note"
			/>
		</form>

		<template #footer>
			<div class="selling-form-footer">
				<button v-if="canUseNativeDesk" type="button" class="edge-button" :disabled="saving" @click="$emit('open-native', 'Quotation')">Advanced: Open Quotation</button>
				<div class="selling-form-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || commercialState.blocked" @click="saveDraft">{{ saving ? "Saving..." : "Save Draft" }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage, quickCreateCustomer, quickCreateItem, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import ProfessionalSalesCommercialPanel from "./ProfessionalSalesCommercialPanel.vue";
import {
	MANUAL_MODE,
	MANUAL_VALUE,
	clearLockedManualDiscounts,
	normaliseManualDiscountRows,
	withManualDiscountEditorColumns,
} from "../selling/manualDiscountEditor";

const SEARCH_METHOD = "retailedge.professional_selling.search_professional_selling_options";
const PRICING_METHOD = "retailedge.professional_selling.get_professional_selling_item_pricing";
const PRICE_CONTEXT_METHOD = "retailedge.guided_pricing.get_allowed_price_list_context";
const CREATE_METHOD = "retailedge.professional_quotation.create_professional_quotation_draft";
const DOCUMENT = "quotation";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function initialValues(context = {}) {
	return {
		company: context.operating?.company || "",
		branch: context.operating?.branch || "",
		warehouse: context.operating?.default_stock_location || "",
		customer: "",
		price_list: context.pricing?.price_list || "",
		transaction_date: context.today || "",
		valid_till: "",
		shipping_rule: "",
		coupon_code: "",
		tax_category: "",
		taxes_and_charges: "",
		additional_discount_percentage: 0,
		discount_amount: 0,
		apply_discount_on: "Grand Total",
		terms: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

export default {
	name: "ProfessionalQuotationDialog",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeInput: runtime.EdgeInput,
		EdgeTextarea: runtime.EdgeTextarea,
		EdgeChildTable: runtime.EdgeChildTable,
		ProfessionalSalesCommercialPanel,
	},
	props: {
		open: { type: Boolean, default: false },
		context: { type: Object, default: () => ({}) },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			saving: false,
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			pricingContext: { ...(this.context.pricing || {}) },
			commercialState: { blocked: true, loading: false, error: "", preview: null },
			values: initialValues(this.context),
			itemTableField: { label: "Items", description: "Add the products or services included in this quotation." },
			itemColumns: withManualDiscountEditorColumns([
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Selling Rate", fieldtype: "Currency", placeholder: "Auto price" },
			]),
		};
	},
	computed: {
		priceListLabel() { return this.pricingContext?.price_list || "Choose Price List"; },
		canCreateCustomer() { return Boolean(frappe.model?.can_create?.("Customer")); },
		canCreateItem() { return Boolean(frappe.model?.can_create?.("Item")); },
	},
	watch: {
		open(next) {
			if (next) {
				this.pricingContext = { ...(this.context.pricing || {}) };
				this.values = initialValues(this.context);
				this.commercialState = { blocked: true, loading: false, error: "", preview: null };
				this.applyRatePermission(this.pricingContext);
				this.saveError = "";
			}
		},
	},
	methods: {
		requestClose() { if (!this.saving) this.$emit("close"); },
		searchOptions(fieldname, query) {
			return callMethod(SEARCH_METHOD, {
				document: DOCUMENT,
				fieldname,
				txt: query || "",
				values: this.values,
			}).then((results) => Array.isArray(results) ? results : []);
		},
		searchCustomer(query) { return this.searchOptions("customer", query); },
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchPriceList(query) { return this.searchOptions("price_list", query); },
		searchShippingRule(query) { return this.searchOptions("shipping_rule", query); },
		updateCommercialTerms(patch) { this.values = { ...this.values, ...(patch || {}) }; },
		updateCommercialState(state) { this.commercialState = { ...this.commercialState, ...(state || {}) }; },
		applyRatePermission(pricing = this.pricingContext || {}) {
			const readOnly = pricing?.allow_rate_change === false;
			this.itemColumns = this.itemColumns.map((column) =>
				["rate", MANUAL_MODE, MANUAL_VALUE].includes(column.fieldname)
					? { ...column, read_only: readOnly ? 1 : 0 }
					: column
			);
			if (readOnly) this.values.items = clearLockedManualDiscounts(this.values.items || []);
		},
		async refreshPriceListContext({ preserveSelection = false } = {}) {
			const pricing = await callMethod(PRICE_CONTEXT_METHOD, { mode: "selling", company: this.values.company, branch: this.values.branch || "", party: this.values.customer || "", selected_price_list: preserveSelection ? (this.values.price_list || "") : "" });
			this.pricingContext = pricing || {};
			this.applyRatePermission(pricing || {});
			if (pricing?.locked || pricing?.price_list || !preserveSelection) this.values.price_list = pricing?.price_list || "";
		},
		async setPriceList(next) {
			if (this.pricingContext?.locked) return;
			this.values.price_list = next || "";
			try {
				await this.refreshPriceListContext({ preserveSelection: true });
				this.refreshAllItemPricing();
			} catch (error) {
				this.values.price_list = "";
				this.saveError = errorMessage(error, "Unable to use the selected Selling Price List.");
			}
		},
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		createCustomer(query) { return quickCreateCustomer(query); },
		canCreateItemLink(column) { return this.canCreateItem && column?.fieldname === "item_code"; },
		createItemLink(column, query) { return column?.fieldname === "item_code" ? quickCreateItem(query) : Promise.resolve(null); },
		itemCreateLabel(column) { return column?.fieldname === "item_code" ? "Create Item" : "Create new"; },
		setTransactionDate(next) {
			const value = next || "";
			if (value === this.values.transaction_date) return;
			this.values.transaction_date = value;
			if (this.values.valid_till && value && this.values.valid_till < value) this.values.valid_till = value;
			this.refreshAllItemPricing();
		},
		setCustomer(next) {
			const value = next || "";
			const changed = this.values.customer !== value;
			this.values.customer = value;
			if (changed) {
				this.values.coupon_code = "";
				this.values.tax_category = "";
				this.values.taxes_and_charges = "";
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "" }));
				this.refreshPriceListContext().then(() => this.refreshAllItemPricing()).catch((error) => { this.saveError = errorMessage(error, "Unable to refresh Selling Price List."); });
			}
		},
		async setBranch(next) {
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			this.values.items = (this.values.items || []).map((row) => ({ ...row, rate: "" }));
			if (!this.values.company) return;
			if (!branch) {
				try {
					await this.refreshPriceListContext();
					this.refreshAllItemPricing();
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to refresh Selling Price List.");
				}
				return;
			}
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
				await this.refreshPriceListContext();
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
			const rows = normaliseManualDiscountRows(nextRows || [], previous);
			const changed = [];
			this.values.items = rows.map((row, index) => {
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
				const result = await callMethod(PRICING_METHOD, {
					document: DOCUMENT,
					item_code: row.item_code,
					values: { ...this.values, qty: row.qty || 1 },
				});
				if (this.pricingTokens[index] !== token || this.values.items[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) this.values.items[index] = { ...this.values.items[index], rate: result.rate };
				this.pricingContext = { ...(this.pricingContext || {}), ...(result || {}) };
				this.applyRatePermission(this.pricingContext);
				if (result?.price_list && (result?.locked || !this.values.price_list)) this.values.price_list = result.price_list;
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
			if (this.commercialState.blocked) {
				this.saveError = this.commercialState.error || "Wait for the current quotation total to finish updating before saving.";
				return;
			}
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Quotation draft.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.selling-form { display: grid; gap: 18px; }
.selling-form-context { display: flex; flex-wrap: wrap; gap: 10px; }
.selling-form-context > div { display: grid; gap: 2px; min-width: 180px; padding: 9px 12px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 8px; background: var(--edge-surface-muted, #f8fafc); }
.selling-form-context span { font-size: 0.78rem; color: var(--edge-text-muted, #667085); }
.selling-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.selling-form-error { padding: 10px 12px; border-radius: 8px; background: var(--red-50, #fef2f2); color: var(--red-700, #b91c1c); border: 1px solid var(--red-200, #fecaca); }
.selling-form-hint { margin: 0; color: var(--edge-text-muted, #667085); font-size: 0.84rem; }
.selling-form-footer, .selling-form-footer-actions { display: flex; align-items: center; gap: 10px; }
.selling-form-footer { justify-content: space-between; width: 100%; }
@media (max-width: 760px) { .selling-form-grid { grid-template-columns: 1fr; } .selling-form-footer { align-items: stretch; flex-direction: column; } .selling-form-footer-actions { justify-content: flex-end; } }
</style>
