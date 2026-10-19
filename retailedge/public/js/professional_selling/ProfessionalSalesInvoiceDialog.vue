<template>
	<EdgeModal
		:open="open"
		title="Sales Invoice"
		subtitle="Create a new draft invoice, invoice a submitted sales document, or prepare a Return / Credit Note from one guided workspace."
		size="xl"
		@close="requestClose"
	>
		<div class="invoice-mode-switch" role="group" aria-label="Sales Invoice creation mode">
			<button v-for="option in visibleModes" :key="option.key" type="button" class="edge-button" :class="{ 'edge-button--primary': mode === option.key }" :disabled="saving" @click="setMode(option.key)">{{ option.label }}</button>
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

				<EdgeInput
					:modelValue="values.posting_date"
					id="professional-sales-invoice-posting-date"
					label="Posting Date"
					type="date"
					required
					@update:modelValue="postingDateChanged"
				/>

				<EdgeLinkField
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					:searcher="searchBranch"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					v-if="mode === 'new'"
					:modelValue="values.price_list"
					label="Selling Price List"
					placeholder="Select assigned Price List"
					description="The effective default follows Price List Governance. Source-document conversions keep their existing commercial terms."
					:required="Boolean(pricingContext.selection_required)"
					:disabled="Boolean(pricingContext.locked) || !Boolean(pricingContext.can_select)"
					:searcher="searchPriceList"
					@update:modelValue="setPriceList"
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
					label="Delivery Charge Rule"
					placeholder="Optional delivery charge rule"
					description="Delivery charges follow the selected Shipping Rule when the draft is saved."
					:searcher="searchShippingRule"
					@update:modelValue="values.shipping_rule = $event || ''"
				/>
			</div>

			<CustomerCreditSummary :customer="values.customer" :company="values.company" />

			<section v-if="values.customer" class="loyalty-panel" aria-live="polite">
				<div class="loyalty-panel-heading">
					<div>
						<span class="loyalty-kicker">Loyalty & Rewards</span>
						<strong>{{ loyaltyStatus.loyalty_program || "Customer programme" }}</strong>
					</div>
					<a v-if="loyaltyStatus.can_manage_programs" :href="loyaltyStatus.native_route || '/app/loyalty-program'" target="_blank" rel="noopener noreferrer">Manage Programmes</a>
				</div>
				<p v-if="loyaltyLoading" class="selling-form-hint">Checking current Loyalty Points...</p>
				<template v-else-if="loyaltyStatus.enrolled">
					<div class="loyalty-summary">
						<div><span>Available Points</span><strong>{{ loyaltyStatus.available_points || 0 }}</strong></div>
						<div><span>Current Tier</span><strong>{{ loyaltyStatus.tier_name || "Standard" }}</strong></div>
						<div><span>Point Value</span><strong>{{ loyaltyStatus.currency || "" }} {{ loyaltyStatus.conversion_factor || 0 }}</strong></div>
						<div><span>Available Value</span><strong>{{ loyaltyStatus.currency || "" }} {{ loyaltyStatus.available_redemption_value || 0 }}</strong></div>
					</div>
					<p v-if="loyaltyStatus.from_date || loyaltyStatus.to_date" class="selling-form-hint">Programme validity: {{ formatDate(loyaltyStatus.from_date, "No start limit") }} – {{ formatDate(loyaltyStatus.to_date, "No end limit") }}</p>
					<EdgeInput
						:modelValue="values.loyalty_points"
						id="professional-sales-invoice-loyalty-points"
						label="Points to Redeem"
						type="number"
						min="0"
						step="1"
						:max="loyaltyStatus.available_points || 0"
						placeholder="0"
						@update:modelValue="setLoyaltyPoints"
					/>
					<p class="selling-form-hint">Estimated redemption: {{ loyaltyRedemptionLabel }}. Available points and the final invoice value are revalidated before saving the draft.</p>
				</template>
				<p v-else class="selling-form-hint">{{ loyaltyStatus.message || "No Loyalty Program is assigned to this Customer." }}</p>
			</section>

			<EdgeCheckbox
				:modelValue="Boolean(values.update_stock)"
				label="Update Stock"
				:description="canEditUpdateStock ? 'Post stock movement when the invoice is eventually submitted.' : 'Update Stock is required by the current sales settings.'"
				:disabled="!canEditUpdateStock || loadingContext"
				@update:modelValue="setUpdateStock"
			/>

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

			<SalesCommercialTermsControls
				:values="values"
				:capabilities="commercialTermCapabilities"
				:preview="commercialPreview"
				:searcher="searchCommercialTerm"
				:disabled="saving || previewLoading"
				@change="updateCommercialTerms"
			/>

			<SalesCommercialSummary
				:preview="commercialPreview"
				:loading="previewLoading"
				:error="previewError"
			/>

			<p v-if="commercialFinalizationNote" class="selling-form-hint">{{ commercialFinalizationNote }}</p>
			<p class="selling-form-hint">Selling prices, discounts and taxes are resolved again before saving. Delivery charges follow the selected Shipping Rule.</p>

			<EdgeTextarea
				v-model="values.remarks"
				id="professional-sales-invoice-remarks"
				label="Remarks"
				rows="3"
				placeholder="Optional invoice note"
			/>
		</form>

		<template #footer>
			<div class="selling-form-footer">
				<div class="selling-form-footer-actions">
					<button v-if="mode === 'new'" type="button" class="edge-button" :disabled="saving" @click="openMakeSalePage">Continue in Make Sale</button>
					<button v-if="canUseNativeDesk" type="button" class="edge-button" :disabled="saving" @click="$emit('open-native', 'Sales Invoice')">Advanced: Open Sales Invoice</button>
				</div>
				<div class="selling-form-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || (mode !== 'new' && !sourceDocument) || (mode === 'new' && commercialPreviewBlocked)" @click="saveDraft">{{ saving ? "Saving..." : saveLabel }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage, quickCreateCustomer, quickCreateItem, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import SalesCommercialSummary from "../selling/SalesCommercialSummary.vue";
import SalesCommercialTermsControls from "../selling/SalesCommercialTermsControls.vue";
import CustomerCreditSummary from "./CustomerCreditSummary.vue";

const GUIDED_CONTEXT = "retailedge.guided_sales_invoice.get_simple_sales_invoice_context";
const GUIDED_SEARCH = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const GUIDED_PRICING = "retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing";
const PRICE_CONTEXT_METHOD = "retailedge.guided_pricing.get_allowed_price_list_context";
const COMMERCIAL_PREVIEW_METHOD = "retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview";
const SHIPPING_SEARCH = "retailedge.professional_sales_invoice.search_professional_invoice_shipping_rules";
const SOURCE_SEARCH = "retailedge.professional_sales_invoice.search_professional_invoice_sources";
const LOYALTY_STATUS = "retailedge.loyalty_rewards.get_customer_loyalty_status";
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
		price_list: context.pricing?.price_list || "",
		posting_date: context.today || "",
		shipping_rule: "",
		loyalty_points: 0,
		update_stock: 1,
		coupon_code: "",
		tax_category: "",
		taxes_and_charges: "",
		additional_discount_percentage: 0,
		discount_amount: 0,
		apply_discount_on: "Grand Total",
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

export default {
	name: "ProfessionalSalesInvoiceDialog",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeInput: runtime.EdgeInput,
		EdgeTextarea: runtime.EdgeTextarea,
		EdgeCheckbox: runtime.EdgeCheckbox,
		EdgeChildTable: runtime.EdgeChildTable,
		CustomerCreditSummary,
		SalesCommercialSummary,
		SalesCommercialTermsControls,
	},
	props: {
		open: { type: Boolean, default: false },
		context: { type: Object, default: () => ({}) },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native", "open-page"],
	data() {
		return {
			mode: "new",
			sourceDocument: "",
			saving: false,
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			pricingContext: { ...(this.context.pricing || {}) },
			guidedContext: null,
			loadingContext: false,
			loyaltyToken: 0,
			loyaltyLoading: false,
			loyaltyStatus: {},
			previewLoading: false,
			previewError: "",
			previewToken: 0,
			previewTimer: null,
			previewAppliedSignature: "",
			commercialPreview: null,
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
				{ fieldname: "uom", label: "UOM", fieldtype: "Data", read_only: 1 },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Selling Rate", fieldtype: "Currency", placeholder: "Auto price" },
				{ fieldname: "discount_percentage", label: "Discount %", fieldtype: "Float", read_only: 1 },
				{ fieldname: "amount", label: "Amount", fieldtype: "Currency", read_only: 1 },
			],
		};
	},
	computed: {
		visibleModes() {
			return this.modes;
		},
		priceListLabel() { return this.pricingContext?.price_list || "Choose Price List"; },
		loyaltyRedemptionLabel() {
			const value = Number(this.values.loyalty_points || 0) * Number(this.loyaltyStatus.conversion_factor || 0);
			return `${this.loyaltyStatus.currency || ""} ${value.toFixed(2)}`.trim();
		},
		canEditUpdateStock() { return Boolean(this.guidedContext?.capabilities?.can_edit_update_stock); },
		requiresBranchSelection() { return Boolean(this.guidedContext?.capabilities?.requires_branch_selection); },
		canCreateCustomer() { return Boolean(frappe.model?.can_create?.("Customer")); },
		canCreateItem() { return Boolean(frappe.model?.can_create?.("Item")); },
		commercialTermCapabilities() {
			return this.commercialPreview?.commercial_term_capabilities
				|| this.guidedContext?.capabilities?.commercial_terms
				|| {};
		},
		populatedItemCount() {
			return (this.values.items || []).filter((row) => row?.item_code).length;
		},
		transactionContextReady() {
			if (!this.values.update_stock) return true;
			if (this.requiresBranchSelection && !this.values.branch) return false;
			return Boolean(this.values.warehouse);
		},
		commercialPreviewRequired() {
			return Boolean(
				this.open
				&& this.mode === "new"
				&& this.values.company
				&& this.values.customer
				&& this.populatedItemCount
				&& this.transactionContextReady
			);
		},
		commercialPreviewSignature() {
			return JSON.stringify({
				mode: this.mode,
				company: this.values.company || "",
				branch: this.values.branch || "",
				warehouse: this.values.warehouse || "",
				customer: this.values.customer || "",
				price_list: this.values.price_list || "",
				posting_date: this.values.posting_date || "",
				update_stock: Number(this.values.update_stock || 0),
				shipping_rule: this.values.shipping_rule || "",
				coupon_code: this.values.coupon_code || "",
				tax_category: this.values.tax_category || "",
				taxes_and_charges: this.values.taxes_and_charges || "",
				additional_discount_percentage: Number(this.values.additional_discount_percentage || 0),
				discount_amount: Number(this.values.discount_amount || 0),
				apply_discount_on: this.values.apply_discount_on || "Grand Total",
				items: (this.values.items || [])
					.filter((row) => row?.item_code)
					.map((row) => ({
						item_code: row.item_code,
						qty: Number(row.qty || 0),
						rate: row.rate === "" ? "" : Number(row.rate || 0),
					})),
			});
		},
		commercialPreviewBlocked() {
			if (this.mode !== "new") return false;
			if (!this.commercialPreviewRequired) return true;
			return Boolean(
				this.previewLoading
				|| this.previewError
				|| !this.commercialPreview
				|| this.previewAppliedSignature !== this.commercialPreviewSignature
			);
		},
		commercialFinalizationNote() {
			const notes = [];
			if (this.values.shipping_rule) notes.push("The selected delivery charge is applied when the draft is saved and is not included in this live discount/tax preview.");
			if (Number(this.values.loyalty_points || 0) > 0) notes.push("Loyalty redemption is revalidated and applied when the draft is saved.");
			return notes.join(" ");
		},
		sourceLabel() {
			return { quotation: "Submitted Quotation", "sales-order": "Submitted Sales Order", "delivery-note": "Submitted Delivery Note", return: "Submitted Sales Invoice" }[this.mode] || "Source Document";
		},
		sourceDescription() {
			if (this.mode === "return") return "Prepare a draft Return / Credit Note from the selected submitted Sales Invoice. The source remains submitted and unchanged.";
			return this.mode === "quotation"
				? "Create the invoice directly from the accepted Quotation; no Sales Order is created behind the scenes."
				: `Create a new Sales Invoice draft from the ${this.sourceLabel.replace("Submitted ", "")} using remaining billable quantities.`;
		},
		sourceHint() {
			if (this.mode === "return") return "Return quantities, stock rules, taxes and accounting are revalidated before submission. Any configured approval workflow is respected; no refund or payment record is created automatically.";
			return "The source remains submitted and unchanged. This workflow creates a new Sales Invoice draft only.";
		},
		saveLabel() {
			if (this.mode === "new") return "Save Draft";
			if (this.mode === "return") return "Prepare Draft Return / Credit Note";
			return `Create Draft from ${this.sourceLabel.replace("Submitted ", "")}`;
		},
	},
	watch: {
		async open(next) {
			if (next) {
				this.mode = "new";
				this.sourceDocument = "";
				this.guidedContext = null;
				this.pricingContext = { ...(this.context.pricing || {}) };
				this.values = initialValues(this.context);
				this.applyRatePermission(this.pricingContext);
				this.loyaltyToken += 1;
				this.loyaltyStatus = {};
				this.loyaltyLoading = false;
				this.saveError = "";
				this.invalidateCommercialPreview();
				await this.loadGuidedContext();
			} else {
				this.invalidateCommercialPreview();
			}
		},
		commercialPreviewSignature(next, previous) {
			if (next === previous || !this.open || this.mode !== "new") return;
			this.invalidateCommercialPreview();
			this.queueCommercialPreview();
		},
	},
	beforeUnmount() {
		if (this.previewTimer) window.clearTimeout(this.previewTimer);
		this.previewToken += 1;
	},
	methods: {
		openMakeSalePage() {
			if (this.saving || this.mode !== "new") return;
			this.$emit("open-page", { values: JSON.parse(JSON.stringify(this.values || {})) });
		},
		async loadGuidedContext() {
			if (this.loadingContext) return;
			this.loadingContext = true;
			try {
				const guided = await callMethod(GUIDED_CONTEXT);
				this.guidedContext = guided || {};
				const defaults = guided?.defaults || {};
				this.values = {
					...this.values,
					company: defaults.company || this.values.company,
					branch: defaults.branch || this.values.branch,
					warehouse: defaults.warehouse || this.values.warehouse,
					posting_date: defaults.posting_date || this.values.posting_date,
					price_list: defaults.price_list || guided?.pricing?.price_list || this.values.price_list,
					update_stock: Number(defaults.update_stock ?? 1),
				};
				if (!guided?.capabilities?.can_edit_update_stock) this.values.update_stock = 1;
				this.pricingContext = { ...(guided?.pricing || this.pricingContext || {}) };
				this.applyRatePermission(this.pricingContext);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to resolve the Sales Invoice operating context.");
			} finally {
				this.loadingContext = false;
			}
		},
		formatDate(value, fallback = "—") { if (!value) return fallback; try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; } catch (_error) { return String(value); } },
		setMode(mode) {
			if (this.saving) return;
			this.mode = mode;
			this.sourceDocument = "";
			this.saveError = "";
			this.invalidateCommercialPreview();
			if (mode === "new") this.queueCommercialPreview(0);
		},
		requestClose() { if (!this.saving) this.$emit("close"); },
		searchOptions(fieldname, query) {
			return callMethod(GUIDED_SEARCH, { fieldname, txt: query || "", values: this.values }).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchCustomer(query) { return this.searchOptions("customer", query); },
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchPriceList(query) { return this.searchOptions("price_list", query); },
		searchCommercialTerm(fieldname, query) { return this.searchOptions(fieldname, query); },
		updateCommercialTerms(patch) { this.values = { ...this.values, ...(patch || {}) }; },
		applyRatePermission(pricing = this.pricingContext || {}) {
			const readOnly = pricing?.allow_rate_change === false;
			this.itemColumns = this.itemColumns.map((column) =>
				column.fieldname === "rate" ? { ...column, read_only: readOnly ? 1 : 0 } : column
			);
		},
		async refreshPriceListContext({ preserveSelection = false } = {}) { const pricing = await callMethod(PRICE_CONTEXT_METHOD, { mode: "selling", company: this.values.company, branch: this.values.branch || "", party: this.values.customer || "", selected_price_list: preserveSelection ? (this.values.price_list || "") : "" }); this.pricingContext = pricing || {}; this.applyRatePermission(pricing || {}); if (pricing?.locked || pricing?.price_list || !preserveSelection) this.values.price_list = pricing?.price_list || ""; },
		async setPriceList(next) { if (this.pricingContext?.locked || this.mode !== "new") return; this.values.price_list = next || ""; try { await this.refreshPriceListContext({ preserveSelection: true }); this.refreshAllItemPricing(); } catch (error) { this.values.price_list = ""; this.saveError = errorMessage(error, "Unable to use the selected Selling Price List."); } },
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
			const value = next || "";
			const changed = this.values.customer !== value;
			this.values.customer = value;
			this.loyaltyToken += 1;
			this.values.loyalty_points = 0;
			this.loyaltyStatus = {};
			if (this.values.customer) this.loadLoyaltyStatus();
			if (changed) {
				this.values.coupon_code = "";
				this.values.tax_category = "";
				this.values.taxes_and_charges = "";
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "", uom: "", discount_percentage: "", amount: "" }));
				this.refreshPriceListContext().then(() => this.refreshAllItemPricing()).catch((error) => { this.saveError = errorMessage(error, "Unable to refresh Selling Price List."); });
			}
		},
		postingDateChanged(next) {
			const value = next || "";
			if (this.values.posting_date === value) return;
			this.values.posting_date = value;
			this.values.loyalty_points = 0;
			this.loyaltyStatus = {};
			if (this.values.customer) this.loadLoyaltyStatus();
			this.refreshAllItemPricing();
		},
		setLoyaltyPoints(next) { this.values.loyalty_points = Math.max(0, Number(next || 0)); },
		setUpdateStock(next) { this.values.update_stock = next ? 1 : 0; },
		async loadLoyaltyStatus() {
			if (!this.values.customer) return;
			const token = ++this.loyaltyToken;
			this.loyaltyLoading = true;
			try {
				const status = await callMethod(LOYALTY_STATUS, {
					values: {
						company: this.values.company,
						branch: this.values.branch,
						warehouse: this.values.warehouse,
						customer: this.values.customer,
						posting_date: this.values.posting_date,
					},
				});
				if (token === this.loyaltyToken) this.loyaltyStatus = status || {};
			} catch (error) {
				if (token === this.loyaltyToken) {
					this.loyaltyStatus = {};
					this.saveError = errorMessage(error, "Unable to load Loyalty Points.");
				}
			} finally {
				if (token === this.loyaltyToken) this.loyaltyLoading = false;
			}
		},
		async setBranch(next) {
			this.values.branch = next || "";
			this.values.warehouse = "";
			this.values.items = (this.values.items || []).map((row) => ({ ...row, rate: "", uom: "", discount_percentage: "", amount: "" }));
			if (!this.values.company) return;
			if (!this.values.branch) {
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
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, preference: "sales" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || "";
				await this.refreshPriceListContext();
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
			let rateOnlyChanged = false;
			this.values.items = (nextRows || []).map((row, index) => {
				const prior = previous[index] || {};
				const itemChanged = row.item_code !== prior.item_code;
				const quantityChanged = Number(row.qty || 1) !== Number(prior.qty || 1);
				const rateChanged = String(row.rate ?? "") !== String(prior.rate ?? "");
				if (row.item_code && (itemChanged || quantityChanged)) {
					changed.push(index);
					return { ...row, rate: "", uom: "", discount_percentage: "", amount: "" };
				}
				if (row.item_code && rateChanged) rateOnlyChanged = true;
				return { ...row };
			});
			this.invalidateCommercialPreview();
			for (const index of changed) this.refreshItemPricing(index);
			if (!changed.length || rateOnlyChanged) this.queueCommercialPreview();
		},
		async refreshItemPricing(index) {
			const row = this.values.items[index];
			if (!row?.item_code || !this.values.customer) return;
			const token = (this.pricingTokens[index] || 0) + 1;
			this.pricingTokens[index] = token;
			try {
				const pricing = await callMethod(GUIDED_PRICING, { item_code: row.item_code, values: { ...this.values, qty: row.qty } });
				if (this.pricingTokens[index] !== token) return;
				this.values.items[index] = { ...this.values.items[index], rate: pricing.rate ?? "", uom: "", discount_percentage: "", amount: "" };
				this.values.items = [...this.values.items];
				this.pricingContext = { ...(this.pricingContext || {}), ...(pricing || {}) }; this.applyRatePermission(this.pricingContext);
				if (pricing?.price_list && (pricing?.locked || !this.values.price_list)) this.values.price_list = pricing.price_list;
				this.queueCommercialPreview();
			} catch (error) {
				if (this.pricingTokens[index] === token) {
					this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
					this.invalidateCommercialPreview();
				}
			}
		},
		refreshAllItemPricing() {
			this.invalidateCommercialPreview();
			let pending = 0;
			this.values.items.forEach((row, index) => {
				if (!row.item_code) return;
				pending += 1;
				this.values.items[index] = { ...row, rate: "", uom: "", discount_percentage: "", amount: "" };
				this.refreshItemPricing(index);
			});
			if (!pending) this.queueCommercialPreview();
		},
		invalidateCommercialPreview() {
			if (this.previewTimer) {
				window.clearTimeout(this.previewTimer);
				this.previewTimer = null;
			}
			this.previewToken += 1;
			this.previewLoading = false;
			this.previewError = "";
			this.previewAppliedSignature = "";
			this.commercialPreview = null;
		},
		queueCommercialPreview(delay = 120) {
			if (this.previewTimer) window.clearTimeout(this.previewTimer);
			this.previewAppliedSignature = "";
			this.previewError = "";
			if (!this.commercialPreviewRequired) {
				this.previewLoading = false;
				this.commercialPreview = null;
				return;
			}
			this.previewLoading = true;
			this.previewTimer = window.setTimeout(() => {
				this.previewTimer = null;
				this.refreshCommercialPreview();
			}, Math.max(0, Number(delay || 0)));
		},
		async refreshCommercialPreview() {
			if (!this.commercialPreviewRequired) {
				this.previewLoading = false;
				return;
			}
			const signature = this.commercialPreviewSignature;
			const token = ++this.previewToken;
			this.previewLoading = true;
			this.previewError = "";
			try {
				const result = await callMethod(COMMERCIAL_PREVIEW_METHOD, { values: this.values }, "POST");
				if (token !== this.previewToken || signature !== this.commercialPreviewSignature) return;
				this.commercialPreview = result || null;
				this.previewAppliedSignature = signature;
				this.applyCommercialPreviewItems(result?.items || []);
			} catch (error) {
				if (token !== this.previewToken) return;
				this.commercialPreview = null;
				this.previewAppliedSignature = "";
				this.previewError = errorMessage(error, "Check the Customer, items, pricing, discount or tax setup and try again.");
			} finally {
				if (token === this.previewToken) this.previewLoading = false;
			}
		},
		applyCommercialPreviewItems(items) {
			const rows = (items || []).filter((row) => !row?.is_free_item);
			let cursor = 0;
			this.values.items = (this.values.items || []).map((row) => {
				if (!row?.item_code) return { ...row };
				const previewRow = rows[cursor++] || {};
				return {
					...row,
					uom: previewRow.uom || "",
					discount_percentage: Number(previewRow.discount_percentage || 0),
					amount: Number(previewRow.amount || 0),
				};
			});
		},
		async saveDraft() {
			if (this.saving) return;
			if (this.mode === "new" && this.commercialPreviewBlocked) {
				this.saveError = this.previewError || "Wait for the current invoice total to finish updating before saving.";
				this.queueCommercialPreview(0);
				return;
			}
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
.loyalty-panel { display: grid; gap: 0.75rem; padding: 0.9rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.65rem; }
.loyalty-panel-heading { display: flex; justify-content: space-between; gap: 1rem; align-items: flex-start; }
.loyalty-panel-heading > div { display: grid; gap: 0.2rem; }
.loyalty-kicker, .loyalty-summary span { color: var(--text-muted); font-size: 0.8rem; }
.loyalty-summary { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0.75rem; }
.loyalty-summary > div { display: grid; gap: 0.2rem; }
.selling-form-context { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 0.75rem; }
.selling-form-context > div { display: grid; gap: 0.2rem; }
.selling-form-context span, .selling-form-hint { color: var(--text-muted); font-size: 0.8rem; }
.selling-form-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.9rem; }
.selling-form-footer { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
.selling-form-footer-actions { display: flex; gap: 0.5rem; }
.selling-form-error { padding: 0.75rem; margin-bottom: 1rem; border: 1px solid var(--red-300, #f1aeb5); border-radius: 0.5rem; }
@media (max-width: 720px) { .selling-form-context, .selling-form-grid, .loyalty-summary { grid-template-columns: 1fr; } .selling-form-footer, .loyalty-panel-heading { align-items: stretch; flex-direction: column; } .selling-form-footer-actions { justify-content: flex-end; } }
</style>