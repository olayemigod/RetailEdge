<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Purchase Invoice'"
		:subtitle="formContext.subtitle || 'Create a Purchase Invoice draft using ERPNext buying and stock controls.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-purchase-state">
			<EdgeLoadingState message="Preparing Purchase Invoice..." :skeleton="true" />
		</div>

		<div v-else-if="loadError" class="guided-purchase-state">
			<EdgeErrorState
				title="Purchase Invoice entry unavailable"
				:message="loadError"
				@retry="loadContext"
			/>
		</div>

		<form v-else class="guided-purchase-form" @submit.prevent="saveDraft">
			<div class="guided-purchase-context" aria-label="Purchase context">
				<div>
					<span>Company</span>
					<strong>{{ values.company || 'Not set' }}</strong>
				</div>
				<div v-if="values.branch">
					<span>Branch</span>
					<strong>{{ values.branch }}</strong>
				</div>
				<div>
					<span>Buying Price List</span>
					<strong>{{ pricingLabel }}</strong>
					<small>{{ pricingSourceLabel }}</small>
				</div>
			</div>

			<div v-if="saveError" class="guided-purchase-error" role="alert">
				{{ saveError }}
			</div>
			<div v-else-if="stockContextMessage" class="guided-purchase-warning" role="status">
				{{ stockContextMessage }}
			</div>

			<div class="guided-purchase-grid">
				<EdgeLinkField
					:modelValue="values.supplier"
					label="Supplier"
					placeholder="Search supplier"
					description="Only suppliers you can access are shown. Create a new Supplier here when permitted."
					:required="true"
					:searcher="searchSupplier"
					:context="searchContext"
					:canCreate="canCreateSupplier"
					:creator="createSupplier"
					createLabel="Create Supplier"
					@update:modelValue="setSupplier"
				/>

				<label class="guided-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>

				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search branch"
					description="Only enabled Branch Setup entries for the active Company are shown. Selecting one loads its preferred receiving stock location."
					:searcher="searchBranch"
					:context="searchContext"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.price_list"
					label="Buying Price List"
					placeholder="Select assigned Price List"
					description="Branch default takes precedence. Otherwise choose from Price Lists assigned to you for this Branch."
					:required="Boolean(formContext.pricing?.selection_required)"
					:disabled="Boolean(formContext.pricing?.locked) || !Boolean(formContext.pricing?.can_select)"
					:searcher="searchPriceList"
					:context="searchContext"
					@update:modelValue="setPriceList"
				/>

				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Receiving Stock Location"
					placeholder="Search receiving stock location"
					description="Receiving Stock Locations are limited to the selected Company and enabled Branch Setup."
					:required="Boolean(values.update_stock)"
					:disabled="requiresBranchSelection && !values.branch"
					:searcher="searchWarehouse"
					:context="searchContext"
					@update:modelValue="setWarehouse"
				/>

				<label class="guided-field">
					<span>Supplier Bill No</span>
					<input
						v-model="values.bill_no"
						class="form-control"
						type="text"
						placeholder="Supplier invoice/reference"
					/>
				</label>

				<label v-if="values.bill_no" class="guided-field">
					<span>Supplier Bill Date</span>
					<input v-model="values.bill_date" class="form-control" type="date" />
				</label>
			</div>

			<label class="guided-check-field">
				<input v-model="values.update_stock" type="checkbox" :true-value="1" :false-value="0" />
				<span>
					<strong>Update Stock</strong>
					<small>Add received stock when the Purchase Invoice is eventually submitted.</small>
				</span>
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
			<p v-if="quickEntryTooLarge" class="guided-entry-size-warning" role="alert">
				Quick Purchase is limited to {{ QUICK_ENTRY_MAX_LINES }} populated item lines. Continue in the full page to keep working on this larger transaction.
			</p>

			<p class="guided-purchase-hint">
				The Branch default Buying Price List takes precedence. Otherwise the current valid default remains selected and Branch-assigned alternatives can be chosen.
				Changing the Price List automatically re-prices entered items. If no valid buying rate is available, enter the agreed supplier rate or configure Item Price before saving.
			</p>

			<label class="guided-field guided-field--wide">
				<span>Remarks</span>
				<textarea
					v-model="values.remarks"
					class="form-control"
					rows="3"
					placeholder="Optional purchase note"
				></textarea>
			</label>
		</form>

		<template #footer>
			<div class="guided-purchase-footer">
				<div class="guided-purchase-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="continueInRecordPurchase">Continue in Record Purchase</button>
					<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">Advanced: Open in ERPNext</button>
				</div>
				<div class="guided-purchase-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">
						Cancel
					</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading || !transactionContextReady || quickEntryTooLarge"
						@click="saveDraft"
					>
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}
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
	QUICK_ENTRY_MAX_LINES,
} from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.guided_purchase_invoice.get_simple_purchase_invoice_context";
const SEARCH_METHOD = "retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options";
const PRICING_METHOD = "retailedge.guided_purchase_invoice.get_simple_purchase_invoice_item_pricing";
const PRICE_CONTEXT_METHOD = "retailedge.guided_pricing.get_allowed_price_list_context";
const CREATE_METHOD = "retailedge.guided_purchase_invoice.create_simple_purchase_invoice_draft";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		company: "",
		branch: "",
		posting_date: "",
		bill_no: "",
		bill_date: "",
		warehouse: "",
		supplier: "",
		price_list: "",
		update_stock: 0,
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

function sourceLabel(source) {
	return {
		branch_default: "Branch default",
		user_selected: "Selected Price List",
		branch_assignment: "Branch-assigned Price List",
		user_default: "User default",
		user_permission: "User-assigned Price List",
		party_default: "Supplier default",
		erpnext_default: "ERPNext default",
		standard_price_list: "Standard Buying",
		item_fallback: "Item fallback",
	}[source] || "ERPNext pricing";
}

export default {
	name: "SimplePurchaseInvoiceDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeChildTable: runtimeComponents.EdgeChildTable,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: {
		nativeFallbackEnabled: { type: Boolean, default: false },
		open: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native", "open-page"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			cascadeToken: 0,
			pricingTokens: {},
			pricingCache: new Map(),
			initialValuesSnapshot: "",
			formContext: {},
			values: emptyValues(),
			itemTableField: {
				label: "Items",
				description: "Newest item rows stay at the top for faster multi-item entry.",
			},
			itemColumns: [
				{
					fieldname: "item_code",
					label: "Item",
					fieldtype: "Link",
					placeholder: "Search item",
				},
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{
					fieldname: "rate",
					label: "Buying Rate",
					fieldtype: "Currency",
					placeholder: "Auto buying price",
				},
			],
		};
	},
	computed: {
		branchEnabled() {
			return Boolean(this.formContext.capabilities?.branch_enabled);
		},
		requiresBranchSelection() {
			return Boolean(this.formContext.capabilities?.requires_branch_selection);
		},
		transactionContextReady() {
			if (!this.values.update_stock) return true;
			if (this.requiresBranchSelection && !this.values.branch) return false;
			return Boolean(this.values.warehouse);
		},
		stockContextMessage() {
			if (!this.values.update_stock) return "";
			if (this.requiresBranchSelection && !this.values.branch) {
				return "Choose a Branch before selecting the Receiving Stock Location.";
			}
			if (!this.values.warehouse) return "Choose a Receiving Stock Location before saving this stock-updating purchase.";
			return "";
		},
		canCreateSupplier() {
			return Boolean(this.formContext.capabilities?.can_create_supplier);
		},
		canCreateItem() {
			return Boolean(this.formContext.capabilities?.can_create_item);
		},
		pricingLabel() {
			return this.formContext.pricing?.price_list || "Item buying fallback";
		},
		pricingSourceLabel() {
			return sourceLabel(this.formContext.pricing?.source);
		},
		searchContext() {
			return {
				company: this.values.company,
				branch: this.values.branch,
				warehouse: this.values.warehouse,
				supplier: this.values.supplier,
				price_list: this.values.price_list,
			};
		},
		hasUnsavedChanges() {
			return Boolean(this.initialValuesSnapshot && JSON.stringify(this.values) !== this.initialValuesSnapshot);
		},
		populatedItemCount() { return (this.values.items || []).filter((row) => row?.item_code).length; },
		quickEntryTooLarge() { return this.populatedItemCount > QUICK_ENTRY_MAX_LINES; },
		QUICK_ENTRY_MAX_LINES() { return QUICK_ENTRY_MAX_LINES; },
	},
	watch: {
		open(next) {
			if (next) this.loadContext();
		},
	},
	mounted() {
		if (this.open) this.loadContext();
	},
	methods: {
		async loadContext() {
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			this.pricingCache.clear();
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })),
				};
				this.initialValuesSnapshot = JSON.stringify(this.values);
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Purchase Invoice.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() {
			if (this.saving) return;
			if (!this.hasUnsavedChanges) { this.$emit("close"); return; }
			frappe.confirm("Discard the unsaved Quick Purchase changes?", () => this.$emit("close"));
		},
		continueInRecordPurchase() {
			if (this.saving) return;
			this.$emit("open-page", { values: JSON.parse(JSON.stringify(this.values || {})) });
		},
		openFullForm() {
			if (this.saving || !this.nativeFallbackEnabled) return;
			this.$emit("open-native", "Purchase Invoice");
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: {
					company: this.values.company,
					branch: this.values.branch,
					warehouse: this.values.warehouse,
					supplier: this.values.supplier,
					price_list: this.values.price_list,
				},
			});
			return Array.isArray(results) ? results : [];
		},
		searchSupplier(query) {
			return this.searchOptions("supplier", query);
		},
		searchBranch(query) {
			return this.searchOptions("branch", query);
		},
		searchWarehouse(query) {
			return this.searchOptions("warehouse", query);
		},
		searchPriceList(query) {
			return this.searchOptions("price_list", query);
		},
		async refreshPriceListContext({ preserveSelection = false } = {}) {
			if (!this.values.company) return;
			const pricing = await callMethod(PRICE_CONTEXT_METHOD, { mode: "buying", company: this.values.company, branch: this.values.branch || "", party: this.values.supplier || "", selected_price_list: preserveSelection ? (this.values.price_list || "") : "" });
			this.formContext.pricing = pricing || {};
			if (pricing?.locked || pricing?.price_list || !preserveSelection) this.values.price_list = pricing?.price_list || "";
		},
		async setPriceList(next) {
			if (this.formContext.pricing?.locked) return;
			this.values.price_list = next || "";
			this.pricingCache.clear();
			try { await this.refreshPriceListContext({ preserveSelection: true }); this.refreshAllItemPricing(); }
			catch (error) { this.values.price_list = ""; this.saveError = errorMessage(error, "Unable to use the selected Buying Price List."); }
		},
		searchLineLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve([]);
			return this.searchOptions("item_code", query);
		},
		createSupplier(query) {
			return quickCreateSupplier(query);
		},
		canCreateItemLink(column) {
			return this.canCreateItem && column?.fieldname === "item_code";
		},
		createItemLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve(null);
			return quickCreateItem(query);
		},
		itemCreateLabel(column) {
			return column?.fieldname === "item_code" ? "Create Item" : "Create new";
		},
		setSupplier(next) {
			const value = next || "";
			const changed = this.values.supplier !== value;
			this.values.supplier = value;
			this.pricingCache.clear();
			if (changed) {
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "" }));
				this.refreshPriceListContext().then(() => this.refreshAllItemPricing()).catch((error) => { this.saveError = errorMessage(error, "Unable to refresh Buying Price List."); });
			}
		},
		async setBranch(next) {
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			this.values.items = (this.values.items || []).map((row) => ({ ...row, rate: "" }));
			this.pricingCache.clear();
			if (!this.values.company) return;
			if (!branch) {
				try {
					await this.refreshPriceListContext();
					this.refreshAllItemPricing();
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to refresh Buying Price List.");
				}
				return;
			}
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch,
					preference: "purchase",
				});
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
				await this.refreshPriceListContext();
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) {
					this.saveError = errorMessage(error, "Unable to resolve the Branch receiving stock location.");
				}
			}
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			this.pricingCache.clear();
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
					this.saveError = errorMessage(error, "Unable to use the selected Receiving Stock Location.");
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
			for (const index of changed) this.loadItemPricing(index);
		},
		pricingCacheKey(row) {
			return [
				this.values.company,
				this.values.branch,
				this.values.warehouse,
				this.values.supplier,
				this.values.price_list,
				this.values.posting_date,
				row.item_code,
				row.qty || 1,
			].join("|");
		},
		async loadItemPricing(index) {
			const row = this.values.items[index];
			if (!row?.item_code || !this.values.supplier) return;
			const key = this.pricingCacheKey(row);
			const token = `${row.item_code}:${Date.now()}:${Math.random()}`;
			this.pricingTokens[index] = token;
			try {
				let result = this.pricingCache.get(key);
				if (!result) {
					result = await callMethod(PRICING_METHOD, {
						item_code: row.item_code,
						values: {
							company: this.values.company,
							branch: this.values.branch,
							warehouse: this.values.warehouse,
							supplier: this.values.supplier,
							price_list: this.values.price_list,
							posting_date: this.values.posting_date,
							qty: row.qty || 1,
						},
					});
					this.pricingCache.set(key, result);
				}
				if (this.pricingTokens[index] !== token || this.values.items[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) {
					this.values.items[index] = { ...this.values.items[index], rate: result.rate };
				} else {
					this.saveError = `No buying price is configured for ${row.item_code}. Enter the agreed buying rate or configure Item Price.`;
				}
				this.formContext.pricing = {
					...(this.formContext.pricing || {}),
					...result,
					price_list: result?.price_list || this.formContext.pricing?.price_list || "",
					source: result?.source || this.formContext.pricing?.source || "item_fallback",
				};
				if (result?.price_list && (result?.locked || !this.values.price_list)) this.values.price_list = result.price_list;
			} catch (error) {
				if (this.pricingTokens[index] === token) {
					this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
				}
			}
		},
		refreshAllItemPricing() {
			if (!this.values.supplier) return;
			this.values.items.forEach((row, index) => {
				if (row.item_code) {
					this.values.items[index] = { ...row, rate: "" };
					this.loadItemPricing(index);
				}
			});
		},
		async saveDraft() {
			if (this.saving || this.loading || !this.transactionContextReady) return;
			if (this.quickEntryTooLarge) { this.saveError = `Quick Purchase supports up to ${QUICK_ENTRY_MAX_LINES} populated item lines. Continue in the full page for larger transactions.`; return; }
			this.saveError = "";
			this.saving = true;
			try {
				const result = await callMethod(CREATE_METHOD, { values: this.values });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Purchase Invoice draft.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.guided-purchase-state {
	min-height: 220px;
	padding: 18px 0;
}
.guided-purchase-form {
	display: grid;
	gap: 18px;
}
.guided-purchase-context {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
}
.guided-purchase-context > div {
	display: grid;
	gap: 2px;
	min-width: 180px;
	padding: 9px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
	background: var(--edge-surface-muted, #f8fafc);
}
.guided-purchase-context span,
.guided-field > span {
	font-size: 0.78rem;
	color: var(--edge-text-muted, #667085);
}
.guided-purchase-context small {
	font-size: 0.72rem;
	color: var(--edge-text-muted, #667085);
}
.guided-purchase-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
}
.guided-field {
	display: grid;
	gap: 6px;
}
.guided-field > span {
	font-weight: 600;
	color: var(--edge-text, #344054);
}
.guided-field--wide {
	grid-column: 1 / -1;
}
.guided-check-field {
	display: flex;
	align-items: flex-start;
	gap: 10px;
	padding: 11px 12px;
	border: 1px solid var(--edge-border, #e5e7eb);
	border-radius: 8px;
}
.guided-check-field span {
	display: grid;
	gap: 2px;
}
.guided-check-field small,
.guided-purchase-hint {
	color: var(--edge-text-muted, #667085);
}
.guided-purchase-hint {
	margin: -8px 0 0;
	font-size: 0.8rem;
}
.guided-purchase-warning,
.guided-purchase-error {
	padding: 10px 12px;
}
.guided-purchase-warning {
	border: 1px solid var(--edge-warning, #f79009);
	border-radius: 8px;
	color: var(--edge-text, #344054);
	background: var(--edge-warning-subtle, #fffaeb);
}
.guided-purchase-error {
	border: 1px solid var(--edge-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-danger, #b42318);
	background: var(--edge-danger-subtle, #fef3f2);
}
.guided-purchase-footer,
.guided-purchase-footer-actions {
	display: flex;
	align-items: center;
	gap: 8px;
}
.guided-purchase-footer {
	width: 100%;
	justify-content: space-between;
}
@media (max-width: 720px) {
	.guided-purchase-grid {
		grid-template-columns: 1fr;
	}
	.guided-purchase-footer {
		align-items: stretch;
		flex-direction: column-reverse;
	}
	.guided-purchase-footer-actions {
		justify-content: flex-end;
	}
}
.guided-entry-size-warning { margin: 0; padding: 10px 12px; border: 1px solid var(--edge-warning, #f79009); border-radius: 8px; background: var(--edge-warning-subtle, #fffaeb); color: var(--edge-warning-text, #7a2e0e); font-size: .82rem; }
</style>