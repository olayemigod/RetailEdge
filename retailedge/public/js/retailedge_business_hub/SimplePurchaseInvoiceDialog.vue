<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Simple Purchase Invoice'"
		:subtitle="formContext.subtitle || 'Create a standard ERPNext Purchase Invoice draft.'"
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
			</div>

			<div v-if="saveError" class="guided-purchase-error" role="alert">
				{{ saveError }}
			</div>

			<div class="guided-purchase-grid">
				<EdgeLinkField
					:modelValue="values.supplier"
					label="Supplier"
					placeholder="Search supplier"
					description="Only suppliers you can access are shown."
					:required="true"
					:searcher="searchSupplier"
					:context="searchContext"
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
					description="Changing branch clears the selected warehouse."
					:searcher="searchBranch"
					:context="searchContext"
					@update:modelValue="setBranch"
				/>

				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Warehouse"
					placeholder="Search warehouse"
					description="Required when Update Stock is enabled; otherwise optional."
					:required="Boolean(values.update_stock)"
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
				@update:rows="updateItems"
			/>

			<p class="guided-purchase-hint">
				Buying Rate is optional. Leave it blank to let ERPNext apply supplier/item defaults and
				configured buying prices when the draft is saved.
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
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">
					Open Full Form
				</button>
				<div class="guided-purchase-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">
						Cancel
					</button>
					<button
						type="button"
						class="edge-button edge-button--primary"
						:disabled="saving || loading"
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
const CONTEXT_METHOD = "retailedge.guided_purchase_invoice.get_simple_purchase_invoice_context";
const SEARCH_METHOD = "retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options";
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
		update_stock: 0,
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	if (error?.message) return error.message;
	if (error?.exc_type) return error.exc_type;
	return fallback;
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
		open: { type: Boolean, default: false },
	},
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			values: emptyValues(),
			itemTableField: {
				label: "Items",
				description: "Add the products or services being purchased.",
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
					placeholder: "ERPNext default",
				},
			],
		};
	},
	computed: {
		branchEnabled() {
			return Boolean(this.formContext.capabilities?.branch_enabled);
		},
		searchContext() {
			return {
				company: this.values.company,
				branch: this.values.branch,
				supplier: this.values.supplier,
			};
		},
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
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.values = {
					...emptyValues(),
					...(data.defaults || {}),
					items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })),
				};
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Simple Purchase Invoice.");
			} finally {
				this.loading = false;
			}
		},
		requestClose() {
			if (this.saving) return;
			this.$emit("close");
		},
		openFullForm() {
			if (this.saving) return;
			this.$emit("open-native", "Purchase Invoice");
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: {
					company: this.values.company,
					branch: this.values.branch,
					supplier: this.values.supplier,
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
		searchLineLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve([]);
			return this.searchOptions("item_code", query);
		},
		setSupplier(next) {
			const changed = Boolean(this.values.supplier && this.values.supplier !== next);
			this.values.supplier = next || "";
			if (changed) {
				this.values.items = this.values.items.map((row) => ({
					...row,
					item_code: "",
					rate: "",
				}));
			}
		},
		setBranch(next) {
			if (this.values.branch !== (next || "")) {
				this.values.branch = next || "";
				this.values.warehouse = "";
			}
		},
		setWarehouse(next) {
			this.values.warehouse = next || "";
		},
		updateItems(nextRows) {
			const previous = this.values.items || [];
			this.values.items = (nextRows || []).map((row, index) => {
				const prior = previous[index] || {};
				if (prior.item_code && prior.item_code !== row.item_code) {
					return { ...row, rate: "" };
				}
				return { ...row };
			});
		},
		async saveDraft() {
			if (this.saving || this.loading) return;
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
.guided-purchase-error {
	padding: 10px 12px;
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
</style>
