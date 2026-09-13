<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'New Purchase Order'"
		:subtitle="formContext.subtitle || 'Prepare a standard ERPNext Purchase Order draft.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-po-state">
			<EdgeLoadingState message="Preparing Purchase Order..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="guided-po-state">
			<EdgeErrorState title="Purchase Order entry unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="guided-po-form" @submit.prevent="saveDraft">
			<div class="guided-po-context" aria-label="Purchase Order context">
				<div><span>Company</span><strong>{{ values.company || 'Not set' }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || 'No Branch selected' }}</strong></div>
				<div><span>Buying Price List</span><strong>{{ pricingLabel }}</strong><small>{{ pricingSourceLabel }}</small></div>
			</div>

			<div v-if="saveError" class="guided-po-error" role="alert">{{ saveError }}</div>

			<div class="guided-po-grid">
				<EdgeLinkField
					:modelValue="values.supplier"
					label="Supplier"
					placeholder="Search supplier"
					description="Only suppliers permitted by ERPNext are available."
					:required="true"
					:searcher="searchSupplier"
					:context="searchContext"
					:canCreate="canCreateSupplier"
					:creator="createSupplier"
					createLabel="Create Supplier"
					@update:modelValue="setSupplier"
				/>

				<label class="guided-field">
					<span>Order Date <b>*</b></span>
					<input v-model="values.transaction_date" class="form-control" type="date" required />
				</label>

				<label class="guided-field">
					<span>Required By <b>*</b></span>
					<input v-model="values.schedule_date" class="form-control" type="date" :min="values.transaction_date || undefined" required />
				</label>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					description="Changing Branch refreshes the preferred receiving Stock Location."
					:searcher="searchBranch"
					:context="searchContext"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Receiving Stock Location"
					placeholder="Search receiving stock location"
					description="Only Stock Locations valid for the selected Company and Branch are offered."
					:searcher="searchWarehouse"
					:context="searchContext"
					@update:modelValue="setWarehouse"
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

			<p class="guided-po-hint">
				Buying Rate is resolved again on the server from the authenticated user's Buying Price List,
				ERPNext item pricing and last-purchase information. Enter the agreed supplier rate only when no valid configured rate exists or an authorised negotiated rate applies.
			</p>

			<label class="guided-field guided-field--wide">
				<span>Terms / Notes</span>
				<textarea v-model="values.terms" class="form-control" rows="3" placeholder="Optional Purchase Order terms or note"></textarea>
			</label>
		</form>

		<template #footer>
			<div class="guided-po-footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="guided-po-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveDraft">
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft Order' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import {
	callMethod,
	errorMessage,
	quickCreateItem,
	quickCreateSupplier,
	resolveBranchWarehouse,
} from "../retailedge_business_hub/guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.professional_purchase_order.get_professional_purchase_order_context";
const SEARCH_METHOD = "retailedge.professional_purchase_order.search_professional_purchase_order_options";
const PRICING_METHOD = "retailedge.professional_purchase_order.get_professional_purchase_order_item_pricing";
const CREATE_METHOD = "retailedge.professional_purchase_order.create_professional_purchase_order_draft";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return {
		company: "",
		branch: "",
		warehouse: "",
		supplier: "",
		transaction_date: "",
		schedule_date: "",
		terms: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

function sourceLabel(source) {
	return {
		user_default: "User default",
		user_permission: "User-assigned Price List",
		party_default: "Supplier default",
		erpnext_default: "ERPNext default",
		standard_price_list: "Standard Buying",
		item_fallback: "Item fallback",
	}[source] || "ERPNext pricing";
}

export default {
	name: "ProfessionalPurchaseOrderDialog",
	components: {
		EdgeModal: runtime.EdgeModal,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeChildTable: runtime.EdgeChildTable,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
	},
	props: {
		open: { type: Boolean, default: false },
		nativeFallbackEnabled: { type: Boolean, default: true },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			formContext: {},
			values: emptyValues(),
			itemTableField: { label: "Items", description: "Add the goods or services being ordered from this Supplier." },
			itemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Buying Rate", fieldtype: "Currency", placeholder: "Auto buying price" },
			],
		};
	},
	computed: {
		branchEnabled() { return Boolean(this.formContext.capabilities?.branch_enabled); },
		canCreateSupplier() { return Boolean(this.formContext.capabilities?.can_create_supplier); },
		canCreateItem() { return Boolean(this.formContext.capabilities?.can_create_item); },
		pricingLabel() { return this.formContext.pricing?.price_list || "Item buying fallback"; },
		pricingSourceLabel() { return sourceLabel(this.formContext.pricing?.source); },
		searchContext() {
			return {
				company: this.values.company,
				branch: this.values.branch,
				warehouse: this.values.warehouse,
				supplier: this.values.supplier,
			};
		},
	},
	watch: {
		open(next) { if (next) this.loadContext(); },
	},
	mounted() { if (this.open) this.loadContext(); },
	methods: {
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })),
				};
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Purchase Order.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() { if (!this.saving) this.$emit("close"); },
		openFullForm() { if (!this.saving && this.nativeFallbackEnabled) this.$emit("open-native", "Purchase Order"); },
		async searchOptions(fieldname, query) {
			const result = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: this.searchContext,
			});
			return Array.isArray(result) ? result : [];
		},
		searchSupplier(query) { return this.searchOptions("supplier", query); },
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		createSupplier(query) { return quickCreateSupplier(query); },
		canCreateItemLink(column) { return this.canCreateItem && column?.fieldname === "item_code"; },
		createItemLink(column, query) { return column?.fieldname === "item_code" ? quickCreateItem(query) : Promise.resolve(null); },
		itemCreateLabel(column) { return column?.fieldname === "item_code" ? "Create Item" : "Create new"; },
		setSupplier(next) {
			const changed = Boolean(this.values.supplier && this.values.supplier !== next);
			this.values.supplier = next || "";
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
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "purchase" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch receiving Stock Location.");
			}
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			if (!warehouse || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch: this.values.branch,
					warehouse,
					preference: "purchase",
				});
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || warehouse;
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) {
					this.values.warehouse = "";
					this.saveError = errorMessage(error, "Unable to use the selected receiving Stock Location.");
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
			if (!row?.item_code || !this.values.supplier) return;
			const token = `${row.item_code}:${Date.now()}:${Math.random()}`;
			this.pricingTokens[index] = token;
			try {
				const result = await callMethod(PRICING_METHOD, {
					item_code: row.item_code,
					values: { ...this.searchContext, transaction_date: this.values.transaction_date, qty: row.qty || 1 },
				});
				if (this.pricingTokens[index] !== token || this.values.items[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) this.values.items[index] = { ...this.values.items[index], rate: result.rate };
			} catch (error) {
				if (this.pricingTokens[index] === token) this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
			}
		},
		refreshAllItemPricing() {
			if (!this.values.supplier) return;
			this.values.items.forEach((row, index) => {
				if (!row.item_code) return;
				this.values.items[index] = { ...row, rate: "" };
				this.loadItemPricing(index);
			});
		},
		async saveDraft() {
			if (this.saving || this.loading) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result || {});
			} catch (error) {
				this.saveError = errorMessage(error, "Purchase Order draft could not be created.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.guided-po-state { min-height:12rem; display:grid; place-items:center; }
.guided-po-form { display:grid; gap:1rem; }
.guided-po-context { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:.75rem; padding:.9rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.65rem; background:var(--edge-surface-subtle,var(--card-bg)); }
.guided-po-context div,.guided-field { display:flex; flex-direction:column; gap:.25rem; }
.guided-po-context span,.guided-po-context small,.guided-po-hint { color:var(--text-muted); font-size:.8rem; }
.guided-po-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.9rem; }
.guided-field span { font-size:.82rem; font-weight:600; }
.guided-field--wide { width:100%; }
.guided-po-error { padding:.75rem; border:1px solid var(--edge-danger,#b42318); border-radius:.5rem; color:var(--edge-danger,#b42318); }
.guided-po-footer { width:100%; display:flex; justify-content:space-between; align-items:center; gap:.75rem; }
.guided-po-footer-actions { display:flex; gap:.5rem; }
.edge-button { min-height:38px; padding:0 12px; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.5rem; background:var(--edge-surface,var(--card-bg)); color:inherit; font-weight:600; }
.edge-button--primary { background:var(--edge-primary,#0f766e); border-color:var(--edge-primary,#0f766e); color:#fff; }
@media (max-width:760px) { .guided-po-context,.guided-po-grid { grid-template-columns:1fr; } .guided-po-footer { align-items:stretch; flex-direction:column; } .guided-po-footer-actions { width:100%; justify-content:flex-end; } }
</style>
