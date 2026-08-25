<template>
	<EdgeModal
		:open="open"
		title="Create Delivery"
		subtitle="Create a draft Delivery Note from the remaining quantities on a submitted Sales Order using ERPNext's native mapping."
		size="lg"
		@close="requestClose"
	>
		<div class="delivery-form">
			<div class="selling-form-context">
				<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
				<div><span>Branch</span><strong>{{ values.branch || "Not set" }}</strong></div>
			</div>

			<div v-if="saveError" class="selling-form-error" role="alert">{{ saveError }}</div>

			<EdgeLinkField
				:modelValue="salesOrder"
				label="Submitted Sales Order"
				placeholder="Search open sales order"
				description="Only submitted orders for the current Company with remaining delivery quantities are offered."
				:required="true"
				:searcher="searchSalesOrder"
				@update:modelValue="salesOrder = $event || ''"
			/>

			<section class="delivery-safety-note">
				<strong>ERPNext keeps delivery truth.</strong>
				<p>Remaining quantities, Sales Order item links, Stock Locations, packed items, taxes and stock validation are mapped by ERPNext. RetailEdge creates a draft only and never changes the submitted Sales Order.</p>
			</section>
		</div>

		<template #footer>
			<div class="selling-form-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="$emit('open-native', 'Delivery Note')">Open Full Form</button>
				<div class="selling-form-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || !salesOrder" @click="createDraft">{{ saving ? "Creating..." : "Create Delivery Draft" }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage } from "../retailedge_business_hub/guidedEntryUtils";

const SOURCE_METHOD = "retailedge.professional_selling_sources.search_professional_selling_sources";
const CREATE_METHOD = "retailedge.professional_delivery.create_delivery_note_from_sales_order";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

export default {
	name: "ProfessionalDeliveryDialog",
	components: { EdgeModal: runtime.EdgeModal, EdgeLinkField: runtime.EdgeLinkField },
	props: { open: { type: Boolean, default: false }, context: { type: Object, default: () => ({}) } },
	emits: ["close", "saved", "open-native"],
	data() {
		return { salesOrder: "", saving: false, saveError: "" };
	},
	computed: {
		values() {
			return {
				company: this.context.operating?.company || "",
				branch: this.context.operating?.branch || "",
				warehouse: this.context.operating?.default_stock_location || "",
			};
		},
	},
	watch: {
		open(next) {
			if (next) {
				this.salesOrder = "";
				this.saveError = "";
			}
		},
	},
	methods: {
		requestClose() { if (!this.saving) this.$emit("close"); },
		searchSalesOrder(query) {
			return callMethod(SOURCE_METHOD, { target: "delivery-note", txt: query || "", values: this.values })
				.then((results) => Array.isArray(results) ? results : []);
		},
		async createDraft() {
			if (this.saving || !this.salesOrder) return;
			this.saving = true;
			this.saveError = "";
			try {
				const result = await callMethod(CREATE_METHOD, { sales_order: this.salesOrder });
				this.$emit("saved", result);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to create the Delivery Note draft.");
			} finally {
				this.saving = false;
			}
		},
	},
};
</script>

<style scoped>
.delivery-form { display: grid; gap: 18px; }
.selling-form-context { display: flex; flex-wrap: wrap; gap: 10px; }
.selling-form-context > div { display: grid; gap: 2px; min-width: 180px; padding: 9px 12px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 8px; background: var(--edge-surface-muted, #f8fafc); }
.selling-form-context span { font-size: 0.78rem; color: var(--edge-text-muted, #667085); }
.selling-form-error { padding: 10px 12px; border-radius: 8px; background: var(--red-50, #fef2f2); color: var(--red-700, #b91c1c); border: 1px solid var(--red-200, #fecaca); }
.delivery-safety-note { padding: 12px; border: 1px solid var(--edge-border, #e5e7eb); border-radius: 8px; background: var(--edge-surface-muted, #f8fafc); }
.delivery-safety-note p { margin: 0.35rem 0 0; color: var(--edge-text-muted, #667085); }
.selling-form-footer, .selling-form-footer-actions { display: flex; align-items: center; gap: 10px; }
.selling-form-footer { justify-content: space-between; width: 100%; }
@media (max-width: 680px) { .selling-form-footer { align-items: stretch; flex-direction: column; } .selling-form-footer-actions { justify-content: flex-end; } }
</style>
