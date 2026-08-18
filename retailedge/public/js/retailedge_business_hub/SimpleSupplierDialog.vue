<template>
	<EdgeModal
		:open="open"
		title="Simple Supplier"
		subtitle="Create an ERPNext Supplier using the common business fields only."
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="simple-supplier-state">
			<EdgeLoadingState message="Preparing Supplier..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="simple-supplier-state">
			<EdgeErrorState title="Supplier entry unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="simple-supplier-form" @submit.prevent="saveSupplier">
			<div v-if="saveError" class="simple-supplier-error" role="alert">{{ saveError }}</div>
			<div class="simple-supplier-grid">
				<label class="guided-field simple-supplier-wide">
					<span>Supplier Name <b>*</b></span>
					<input v-model.trim="values.supplier_name" class="form-control" type="text" required />
				</label>
				<label class="guided-field">
					<span>Supplier Type <b>*</b></span>
					<select v-model="values.supplier_type" class="form-control" required>
						<option v-for="option in supplierTypes" :key="option" :value="option">{{ option }}</option>
					</select>
				</label>
				<EdgeLinkField
					:modelValue="values.supplier_group"
					label="Supplier Group"
					placeholder="Search supplier group"
					:required="true"
					:searcher="searchSupplierGroup"
					@update:modelValue="values.supplier_group = $event || ''"
				/>
				<label class="guided-field">
					<span>Mobile Number</span>
					<input v-model.trim="values.mobile_no" class="form-control" type="tel" />
				</label>
				<label class="guided-field">
					<span>Email</span>
					<input v-model.trim="values.email_id" class="form-control" type="email" />
				</label>
				<label class="guided-field simple-supplier-wide">
					<span>Tax ID</span>
					<input v-model.trim="values.tax_id" class="form-control" type="text" />
				</label>
			</div>
		</form>
		<template #footer>
			<div class="simple-supplier-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="simple-supplier-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveSupplier">
						{{ saving ? "Creating..." : "Create Supplier" }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.guided_supplier.get_simple_supplier_context";
const SEARCH_METHOD = "retailedge.guided_supplier.search_simple_supplier_options";
const CREATE_METHOD = "retailedge.guided_supplier.create_simple_supplier";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		supplier_name: "",
		supplier_type: "Company",
		supplier_group: "",
		mobile_no: "",
		email_id: "",
		tax_id: "",
	};
}

export default {
	name: "SimpleSupplierDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: { open: { type: Boolean, default: false } },
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			values: emptyValues(),
		};
	},
	computed: {
		supplierTypes() {
			return this.formContext.options?.supplier_types || ["Company", "Individual"];
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
				this.values = { ...emptyValues(), ...(data.defaults || {}) };
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Simple Supplier.");
			} finally {
				this.loading = false;
			}
		},
		async searchSupplierGroup(query) {
			const result = await callMethod(SEARCH_METHOD, { fieldname: "supplier_group", txt: query || "" });
			return Array.isArray(result) ? result : [];
		},
		requestClose() {
			if (!this.saving) this.$emit("close");
		},
		openFullForm() {
			if (!this.saving) this.$emit("open-native", "Supplier");
		},
		async saveSupplier() {
			if (this.saving) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: { ...this.values } });
				this.$emit("saved", result || {});
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to create Supplier.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.simple-supplier-state { padding: 18px 0; }
.simple-supplier-form { display: grid; gap: 16px; }
.simple-supplier-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.simple-supplier-wide { grid-column: 1 / -1; }
.simple-supplier-error { padding: 10px 12px; border-radius: 8px; background: var(--edge-danger-soft, #fef2f2); color: var(--edge-danger, #b42318); }
.simple-supplier-footer { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.simple-supplier-footer-actions { display: flex; gap: 8px; }
@media (max-width: 720px) {
	.simple-supplier-grid { grid-template-columns: 1fr; }
	.simple-supplier-wide { grid-column: auto; }
	.simple-supplier-footer { align-items: stretch; flex-direction: column; }
	.simple-supplier-footer-actions { justify-content: flex-end; }
}
</style>
