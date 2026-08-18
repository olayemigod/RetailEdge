<template>
	<EdgeModal
		:open="open"
		title="Simple Product"
		subtitle="Create an ERPNext Item without exposing cost or valuation fields."
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="simple-item-state">
			<EdgeLoadingState message="Preparing Product..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="simple-item-state">
			<EdgeErrorState title="Product entry unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="simple-item-form" @submit.prevent="saveItem">
			<div v-if="saveError" class="simple-item-error" role="alert">{{ saveError }}</div>
			<div class="simple-item-grid">
				<label class="guided-field">
					<span>Item Code <b>*</b></span>
					<input v-model.trim="values.item_code" class="form-control" type="text" required />
				</label>
				<label class="guided-field">
					<span>Item Name</span>
					<input v-model.trim="values.item_name" class="form-control" type="text" />
				</label>
				<EdgeLinkField
					:modelValue="values.item_group"
					label="Item Group"
					placeholder="Search item group"
					:required="true"
					:searcher="searchItemGroup"
					@update:modelValue="values.item_group = $event || ''"
				/>
				<EdgeLinkField
					:modelValue="values.stock_uom"
					label="Stock UOM"
					placeholder="Search UOM"
					:required="true"
					:searcher="searchStockUom"
					@update:modelValue="values.stock_uom = $event || ''"
				/>
				<label class="guided-check-field simple-item-wide">
					<input v-model="values.is_stock_item" type="checkbox" :true-value="1" :false-value="0" />
					<span><strong>Stock Item</strong><small>Turn off for services and non-stock products.</small></span>
				</label>
				<label class="guided-field">
					<span>Barcode</span>
					<input v-model.trim="values.barcode" class="form-control" type="text" />
				</label>
				<label class="guided-field simple-item-wide">
					<span>Description</span>
					<textarea v-model.trim="values.description" class="form-control" rows="3"></textarea>
				</label>
			</div>
			<p class="simple-item-note">Cost, valuation and buying-price fields are intentionally excluded from this simple form.</p>
		</form>
		<template #footer>
			<div class="simple-item-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="simple-item-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveItem">
						{{ saving ? "Creating..." : "Create Product" }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.guided_item.get_simple_item_context";
const SEARCH_METHOD = "retailedge.guided_item.search_simple_item_options";
const CREATE_METHOD = "retailedge.guided_item.create_simple_item";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		item_code: "",
		item_name: "",
		is_stock_item: 1,
		item_group: "",
		stock_uom: "",
		barcode: "",
		description: "",
	};
}

export default {
	name: "SimpleItemDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: { open: { type: Boolean, default: false } },
	emits: ["close", "saved", "open-native"],
	data() {
		return { loading: false, saving: false, loadError: "", saveError: "", formContext: {}, values: emptyValues() };
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
				this.values = { ...emptyValues(), ...(data.defaults || {}) };
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Simple Product.");
			} finally {
				this.loading = false;
			}
		},
		async searchOptions(fieldname, query) {
			const result = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "" });
			return Array.isArray(result) ? result : [];
		},
		searchItemGroup(query) {
			return this.searchOptions("item_group", query);
		},
		searchStockUom(query) {
			return this.searchOptions("stock_uom", query);
		},
		requestClose() {
			if (!this.saving) this.$emit("close");
		},
		openFullForm() {
			if (!this.saving) this.$emit("open-native", "Item");
		},
		async saveItem() {
			if (this.saving) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: { ...this.values } });
				this.$emit("saved", result || {});
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to create Product.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.simple-item-state { padding: 18px 0; }
.simple-item-form { display: grid; gap: 16px; }
.simple-item-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.simple-item-wide { grid-column: 1 / -1; }
.simple-item-error { padding: 10px 12px; border-radius: 8px; background: var(--edge-danger-soft, #fef2f2); color: var(--edge-danger, #b42318); }
.simple-item-note { margin: 0; font-size: 12px; color: var(--edge-text-muted, #667085); }
.simple-item-footer { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.simple-item-footer-actions { display: flex; gap: 8px; }
@media (max-width: 720px) {
	.simple-item-grid { grid-template-columns: 1fr; }
	.simple-item-wide { grid-column: auto; }
	.simple-item-footer { align-items: stretch; flex-direction: column; }
	.simple-item-footer-actions { justify-content: flex-end; }
}
</style>
