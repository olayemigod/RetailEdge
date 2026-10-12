<template>
	<section class="edge-panel sales-commercial-summary" aria-live="polite" aria-label="Sale summary">
		<div class="sales-commercial-summary__header">
			<div>
				<span>Sale summary</span>
				<strong>{{ preview ? "Current invoice value" : "Invoice value" }}</strong>
			</div>
			<small v-if="loading">Updating total…</small>
		</div>

		<div v-if="error" class="sales-commercial-summary__error" role="alert">
			<strong>Unable to calculate this sale</strong>
			<span>{{ error }}</span>
		</div>

		<template v-else-if="preview">
			<div v-if="preview.promotions?.length" class="sales-commercial-summary__promotions" role="status">
				<strong>{{ preview.promotions.length === 1 ? "Promotion applied" : `${preview.promotions.length} promotions applied` }}</strong>
				<span>{{ preview.promotions.join(", ") }}</span>
			</div>

			<div class="sales-commercial-summary__rows">
				<div v-if="Number(preview.item_discount_total || 0)">
					<span>List value</span>
					<strong>{{ formatMoney(preview.list_value) }}</strong>
				</div>
				<div v-if="Number(preview.item_discount_total || 0)" class="sales-commercial-summary__muted-row">
					<span>Item savings</span>
					<strong>−{{ formatMoney(preview.item_discount_total) }}</strong>
				</div>
				<div>
					<span>Subtotal</span>
					<strong>{{ formatMoney(preview.subtotal) }}</strong>
				</div>
				<div v-if="Number(preview.additional_discount || 0)">
					<span>Additional discount</span>
					<strong>−{{ formatMoney(preview.additional_discount) }}</strong>
				</div>
				<div v-if="preview.has_tax || Number(preview.total_taxes_and_charges || 0)">
					<span>{{ preview.all_taxes_included ? "Tax (included)" : "Tax" }}</span>
					<strong>{{ formatMoney(preview.total_taxes_and_charges) }}</strong>
				</div>
				<div v-if="Number(preview.rounding_adjustment || 0)">
					<span>Rounding</span>
					<strong>{{ formatSignedMoney(preview.rounding_adjustment) }}</strong>
				</div>
				<div class="sales-commercial-summary__total">
					<span>Invoice Total</span>
					<strong>{{ formatMoney(preview.invoice_total) }}</strong>
				</div>
			</div>

			<div v-if="preview.taxes_and_charges || preview.tax_category" class="sales-commercial-summary__context">
				<span v-if="preview.taxes_and_charges">{{ preview.taxes_and_charges }}</span>
				<span v-if="preview.tax_category">Tax category: {{ preview.tax_category }}</span>
			</div>

			<details v-if="preview.taxes?.length" class="sales-commercial-summary__taxes">
				<summary>View tax breakdown</summary>
				<div v-for="(tax, index) in preview.taxes" :key="`${tax.description || 'tax'}-${index}`">
					<span>
						{{ tax.description || "Tax" }}
						<small v-if="Number(tax.rate || 0)"> {{ tax.rate }}%</small>
						<small v-if="tax.included_in_print_rate"> · included</small>
					</span>
					<strong>{{ formatMoney(tax.tax_amount) }}</strong>
				</div>
			</details>
		</template>

		<p v-else class="sales-commercial-summary__empty">
			Add a Customer and sale item to see the subtotal, tax and invoice total before saving.
		</p>
	</section>
</template>

<script>
export default {
	name: "SalesCommercialSummary",
	props: {
		preview: { type: Object, default: null },
		loading: { type: Boolean, default: false },
		error: { type: String, default: "" },
	},
	methods: {
		formatMoney(value) {
			const amount = Number(value || 0);
			const currency = this.preview?.currency || "NGN";
			try {
				return new Intl.NumberFormat(undefined, {
					style: "currency",
					currency,
					minimumFractionDigits: 2,
					maximumFractionDigits: 2,
				}).format(amount);
			} catch (_error) {
				return `${currency} ${amount.toFixed(2)}`.trim();
			}
		},
		formatSignedMoney(value) {
			const amount = Number(value || 0);
			if (!amount) return this.formatMoney(0);
			return `${amount > 0 ? "+" : "−"}${this.formatMoney(Math.abs(amount))}`;
		},
	},
};
</script>

<style scoped>
.sales-commercial-summary {
	display: grid;
	gap: 12px;
	padding: 14px 16px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 10px;
	background: var(--edge-color-surface, #fff);
}
.sales-commercial-summary__header,
.sales-commercial-summary__rows > div,
.sales-commercial-summary__taxes > div {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 14px;
}
.sales-commercial-summary__header > div {
	display: grid;
	gap: 2px;
}
.sales-commercial-summary__header span,
.sales-commercial-summary__header small,
.sales-commercial-summary__rows span,
.sales-commercial-summary__context,
.sales-commercial-summary__empty,
.sales-commercial-summary__taxes summary,
.sales-commercial-summary__taxes small {
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.sales-commercial-summary__header span {
	font-size: .72rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .06em;
}
.sales-commercial-summary__promotions {
	display: grid;
	gap: 2px;
	padding: 9px 11px;
	border: 1px solid var(--edge-color-success, #12b76a);
	border-radius: 8px;
	background: var(--edge-color-success-subtle, #ecfdf3);
}
.sales-commercial-summary__promotions strong {
	font-size: .82rem;
	color: var(--edge-color-success, #067647);
}
.sales-commercial-summary__promotions span {
	font-size: .76rem;
	color: var(--edge-color-ink-600, #475467);
}
.sales-commercial-summary__rows {
	display: grid;
	gap: 8px;
}
.sales-commercial-summary__muted-row strong {
	color: var(--edge-color-success, #067647);
}
.sales-commercial-summary__total {
	margin-top: 3px;
	padding-top: 10px;
	border-top: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	font-size: 1.05rem;
}
.sales-commercial-summary__total strong {
	font-size: 1.25rem;
}
.sales-commercial-summary__context {
	display: flex;
	gap: 8px 14px;
	flex-wrap: wrap;
	font-size: .78rem;
}
.sales-commercial-summary__taxes {
	padding-top: 2px;
}
.sales-commercial-summary__taxes summary {
	cursor: pointer;
	font-size: .8rem;
	font-weight: 600;
}
.sales-commercial-summary__taxes > div {
	padding: 7px 0 0;
	font-size: .8rem;
}
.sales-commercial-summary__error {
	display: grid;
	gap: 3px;
	padding: 10px 12px;
	border: 1px solid var(--edge-color-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-color-danger, #b42318);
	background: var(--edge-color-danger-subtle, #fef3f2);
}
.sales-commercial-summary__empty {
	margin: 0;
	font-size: .82rem;
}
:global(:root[data-edge-appearance="dark"]) .sales-commercial-summary {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
</style>
