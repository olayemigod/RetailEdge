<template>
	<EdgeModal
		:open="open"
		title="Simple Customer"
		subtitle="Create an ERPNext Customer using the common business fields only."
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="simple-customer-state">
			<EdgeLoadingState message="Preparing Customer..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="simple-customer-state">
			<EdgeErrorState title="Customer entry unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="simple-customer-form" @submit.prevent="saveCustomer">
			<div v-if="saveError" class="simple-customer-error" role="alert">{{ saveError }}</div>
			<div class="simple-customer-grid">
				<label class="guided-field simple-customer-wide">
					<span>Customer Name <b>*</b></span>
					<input v-model.trim="values.customer_name" class="form-control" type="text" required />
				</label>
				<label class="guided-field">
					<span>Customer Type <b>*</b></span>
					<select v-model="values.customer_type" class="form-control" required>
						<option v-for="option in customerTypes" :key="option" :value="option">{{ option }}</option>
					</select>
				</label>
				<EdgeLinkField
					:modelValue="values.customer_group"
					label="Customer Group"
					placeholder="Search customer group"
					:required="true"
					:searcher="searchCustomerGroup"
					@update:modelValue="values.customer_group = $event || ''"
				/>
				<EdgeLinkField
					:modelValue="values.territory"
					label="Territory"
					placeholder="Search territory"
					:required="true"
					:searcher="searchTerritory"
					@update:modelValue="values.territory = $event || ''"
				/>
				<label class="guided-field">
					<span>Mobile Number</span>
					<input v-model.trim="values.mobile_no" class="form-control" type="tel" />
				</label>
				<label class="guided-field">
					<span>Email</span>
					<input v-model.trim="values.email_id" class="form-control" type="email" />
				</label>
				<label class="guided-field simple-customer-wide">
					<span>Tax ID</span>
					<input v-model.trim="values.tax_id" class="form-control" type="text" />
				</label>
			</div>
		</form>
		<template #footer>
			<div class="simple-customer-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="simple-customer-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveCustomer">
						{{ saving ? "Creating..." : "Create Customer" }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.guided_customer.get_simple_customer_context";
const SEARCH_METHOD = "retailedge.guided_customer.search_simple_customer_options";
const CREATE_METHOD = "retailedge.guided_customer.create_simple_customer";
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function emptyValues() {
	return {
		customer_name: "",
		customer_type: "Company",
		customer_group: "",
		territory: "",
		mobile_no: "",
		email_id: "",
		tax_id: "",
	};
}

export default {
	name: "SimpleCustomerDialog",
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
		customerTypes() {
			return this.formContext.options?.customer_types || ["Company", "Individual"];
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
				this.loadError = errorMessage(error, "Unable to prepare Simple Customer.");
			} finally {
				this.loading = false;
			}
		},
		async searchOptions(fieldname, query) {
			const result = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "" });
			return Array.isArray(result) ? result : [];
		},
		searchCustomerGroup(query) {
			return this.searchOptions("customer_group", query);
		},
		searchTerritory(query) {
			return this.searchOptions("territory", query);
		},
		requestClose() {
			if (!this.saving) this.$emit("close");
		},
		openFullForm() {
			if (!this.saving) this.$emit("open-native", "Customer");
		},
		async saveCustomer() {
			if (this.saving) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { values: { ...this.values } });
				this.$emit("saved", result || {});
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to create Customer.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.simple-customer-state { padding: 18px 0; }
.simple-customer-form { display: grid; gap: 16px; }
.simple-customer-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.simple-customer-wide { grid-column: 1 / -1; }
.simple-customer-error { padding: 10px 12px; border-radius: 8px; background: var(--edge-danger-soft, #fef2f2); color: var(--edge-danger, #b42318); }
.simple-customer-footer { width: 100%; display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.simple-customer-footer-actions { display: flex; gap: 8px; }
@media (max-width: 720px) {
	.simple-customer-grid { grid-template-columns: 1fr; }
	.simple-customer-wide { grid-column: auto; }
	.simple-customer-footer { align-items: stretch; flex-direction: column; }
	.simple-customer-footer-actions { justify-content: flex-end; }
}
</style>
