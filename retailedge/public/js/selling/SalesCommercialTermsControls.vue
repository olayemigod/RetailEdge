<template>
	<details class="sales-commercial-terms" :open="openByDefault">
		<summary>
			<span>
				<strong>Discount &amp; tax</strong>
				<small>Optional commercial terms. Invoice totals update before saving.</small>
			</span>
			<span v-if="activeTermCount" class="term-count">{{ activeTermCount }} applied</span>
		</summary>

		<div class="sales-commercial-terms__body">
			<div v-if="capabilities.can_edit_additional_discount" class="sales-commercial-terms__grid">
				<EdgeDropdown
					:modelValue="discountMode"
					:options="discountModeOptions"
					label="Additional discount"
					:disabled="disabled"
					@update:modelValue="setDiscountMode"
				/>

				<EdgeInput
					v-if="discountMode === 'percentage'"
					:modelValue="values.additional_discount_percentage"
					label="Discount %"
					type="number"
					min="0"
					max="100"
					step="0.01"
					:disabled="disabled"
					@update:modelValue="setDiscountPercentage"
				/>

				<EdgeInput
					v-else-if="discountMode === 'amount'"
					:modelValue="values.discount_amount"
					label="Discount amount"
					type="number"
					min="0"
					step="0.01"
					:disabled="disabled"
					@update:modelValue="setDiscountAmount"
				/>

				<EdgeDropdown
					v-if="discountMode !== 'none'"
					:modelValue="values.apply_discount_on || 'Grand Total'"
					:options="discountTargetOptions"
					label="Apply discount to"
					:disabled="disabled"
					@update:modelValue="setDiscountTarget"
				/>
			</div>

			<div class="sales-commercial-terms__grid">
				<EdgeLinkField
					v-if="capabilities.can_use_coupon"
					:modelValue="values.coupon_code || ''"
					label="Coupon"
					placeholder="Search valid coupon"
					description="Only coupons you can use for this customer are shown."
					:searcher="searchCoupon"
					:disabled="disabled"
					@update:modelValue="setCoupon"
				/>

				<EdgeLinkField
					v-if="capabilities.can_select_tax_category"
					:modelValue="values.tax_category || ''"
					label="Tax category"
					placeholder="Automatic tax category"
					description="Choose an enabled Tax Category you can use. Changing it refreshes the compatible tax treatment."
					:searcher="searchTaxCategory"
					:disabled="disabled"
					@update:modelValue="setTaxCategory"
				/>

				<EdgeLinkField
					v-if="capabilities.can_select_tax_template"
					:modelValue="values.taxes_and_charges || ''"
					label="Tax template"
					placeholder="Automatic tax treatment"
					:description="values.tax_category ? 'Only templates compatible with the selected Tax Category are shown. Leave blank for automatic tax treatment.' : 'Leave blank to use automatic tax treatment.'"
					:searcher="searchTaxTemplate"
					:disabled="disabled"
					@update:modelValue="setTaxTemplate"
				/>
			</div>

			<div v-if="resolvedTaxLabel || resolvedTaxCategory" class="resolved-tax" role="status">
				<span>Current tax treatment</span>
				<strong>{{ resolvedTaxLabel || "Automatic tax treatment" }}</strong>
				<small v-if="resolvedTaxCategory">Tax category: {{ resolvedTaxCategory }}</small>
			</div>
		</div>
	</details>
</template>

<script>
const runtimeComponents =
	typeof window !== "undefined" && window.EdgeSuiteUI
		? window.EdgeSuiteUI.components || window.EdgeSuiteUI
		: {};

function discountModeFromValues(values = {}) {
	if (Number(values.additional_discount_percentage || 0) > 0) return "percentage";
	if (Number(values.discount_amount || 0) > 0) return "amount";
	return "none";
}

export default {
	name: "SalesCommercialTermsControls",
	components: {
		EdgeDropdown: runtimeComponents.EdgeDropdown,
		EdgeInput: runtimeComponents.EdgeInput,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
	},
	props: {
		values: { type: Object, required: true },
		capabilities: { type: Object, default: () => ({}) },
		preview: { type: Object, default: null },
		searcher: { type: Function, required: true },
		disabled: { type: Boolean, default: false },
		openByDefault: { type: Boolean, default: false },
	},
	emits: ["change"],
	data() {
		return {
			selectedDiscountMode: discountModeFromValues(this.values),
		};
	},
	computed: {
		discountMode() {
			return this.selectedDiscountMode;
		},
		discountModeOptions() {
			return [
				{ value: "none", label: "No manual discount" },
				{ value: "percentage", label: "Percentage" },
				{ value: "amount", label: "Fixed amount" },
			];
		},
		discountTargetOptions() {
			return [
				{ value: "Grand Total", label: "Grand Total" },
				{ value: "Net Total", label: "Net Total" },
			];
		},
		resolvedTaxLabel() {
			return this.preview?.taxes_and_charges || "";
		},
		resolvedTaxCategory() {
			return this.preview?.tax_category || "";
		},
		activeTermCount() {
			let count = 0;
			if (Number(this.values.additional_discount_percentage || 0) > 0 || Number(this.values.discount_amount || 0) > 0) count += 1;
			if (this.values.coupon_code) count += 1;
			if (this.values.tax_category) count += 1;
			if (this.values.taxes_and_charges) count += 1;
			return count;
		},
	},
	watch: {
		"values.additional_discount_percentage"(value) {
			if (Number(value || 0) > 0) this.selectedDiscountMode = "percentage";
		},
		"values.discount_amount"(value) {
			if (Number(value || 0) > 0) this.selectedDiscountMode = "amount";
		},
		"values.customer"(value, previous) {
			if (value !== previous) this.selectedDiscountMode = discountModeFromValues(this.values);
		},
		"values.company"(value, previous) {
			if (value !== previous) this.selectedDiscountMode = discountModeFromValues(this.values);
		},
	},
	methods: {
		emitChange(patch) {
			this.$emit("change", patch);
		},
		setDiscountMode(mode) {
			const next = mode || "none";
			this.selectedDiscountMode = next;
			if (next === "percentage") {
				this.emitChange({ discount_amount: 0, additional_discount_percentage: Number(this.values.additional_discount_percentage || 0), apply_discount_on: this.values.apply_discount_on || "Grand Total" });
				return;
			}
			if (next === "amount") {
				this.emitChange({ additional_discount_percentage: 0, discount_amount: Number(this.values.discount_amount || 0), apply_discount_on: this.values.apply_discount_on || "Grand Total" });
				return;
			}
			this.emitChange({ additional_discount_percentage: 0, discount_amount: 0, apply_discount_on: this.values.apply_discount_on || "Grand Total" });
		},
		setDiscountPercentage(value) {
			this.selectedDiscountMode = "percentage";
			this.emitChange({ additional_discount_percentage: Number(value || 0), discount_amount: 0 });
		},
		setDiscountAmount(value) {
			this.selectedDiscountMode = "amount";
			this.emitChange({ discount_amount: Number(value || 0), additional_discount_percentage: 0 });
		},
		setDiscountTarget(value) {
			this.emitChange({ apply_discount_on: value || "Grand Total" });
		},
		setCoupon(value) {
			this.emitChange({ coupon_code: value || "" });
		},
		setTaxCategory(value) {
			this.emitChange({ tax_category: value || "", taxes_and_charges: "" });
		},
		setTaxTemplate(value) {
			this.emitChange({ taxes_and_charges: value || "" });
		},
		searchCoupon(query) {
			return this.searcher("coupon_code", query || "");
		},
		searchTaxCategory(query) {
			return this.searcher("tax_category", query || "");
		},
		searchTaxTemplate(query) {
			return this.searcher("taxes_and_charges", query || "");
		},
	},
};
</script>

<style scoped>
.sales-commercial-terms {
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 10px;
	background: var(--edge-color-surface, var(--edge-surface, #fff));
}
.sales-commercial-terms summary {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 12px;
	padding: 12px 14px;
	cursor: pointer;
	color: var(--edge-color-ink-700, var(--edge-text, #344054));
}
.sales-commercial-terms summary > span:first-child {
	display: grid;
	gap: 2px;
}
.sales-commercial-terms summary small,
.resolved-tax small,
.resolved-tax span {
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.term-count {
	font-size: .75rem;
	font-weight: 600;
	white-space: nowrap;
}
.sales-commercial-terms__body {
	display: grid;
	gap: 14px;
	padding: 0 14px 14px;
}
.sales-commercial-terms__grid {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 12px;
}
.resolved-tax {
	display: grid;
	gap: 2px;
	padding: 10px 12px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 8px;
	background: var(--edge-color-surface-muted, var(--edge-surface-muted, #f8fafc));
}
@media (max-width: 720px) {
	.sales-commercial-terms__grid {
		grid-template-columns: 1fr;
	}
}
</style>