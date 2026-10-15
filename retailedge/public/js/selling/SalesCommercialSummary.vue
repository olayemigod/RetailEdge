<template>
	<section class="sales-commercial-summary-rail" aria-live="polite" aria-label="Sale summary">
		<div class="edge-panel sales-commercial-summary">
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
				<div v-if="hasPromotion" class="sales-commercial-summary__promotions" role="status">
					<strong>Automatic promotion applied</strong>
					<span>{{ promotionSummary }}</span>
				</div>

				<div class="sales-commercial-summary__rows">
					<div v-if="hasItemPricingEffects">
						<span>Price-list value</span>
						<strong>{{ formatMoney(preview.price_list_value || preview.list_value) }}</strong>
					</div>
					<div v-if="Number(preview.item_promotion_total || 0)" class="sales-commercial-summary__muted-row">
						<span>Item promotions</span>
						<strong>−{{ formatMoney(preview.item_promotion_total) }}</strong>
					</div>
					<div v-if="Number(preview.selling_rate_adjustment_total || 0)" class="sales-commercial-summary__muted-row">
						<span>Selling rate adjustments</span>
						<strong>{{ formatSignedMoney(preview.selling_rate_adjustment_total) }}</strong>
					</div>
					<div v-if="Number(preview.line_discount_total || 0)" class="sales-commercial-summary__muted-row">
						<span>Line discounts</span>
						<strong>−{{ formatMoney(preview.line_discount_total) }}</strong>
					</div>
					<div>
						<span>Items subtotal</span>
						<strong>{{ formatMoney(preview.subtotal) }}</strong>
					</div>

					<template v-if="hasInvoiceAdjustment && invoiceAdjustmentTarget === 'Grand Total'">
						<div v-if="hasTax && !preview.all_taxes_included">
							<span>{{ taxLabel(true) }}</span>
							<strong>{{ formatMoney(preview.tax_before_invoice_adjustment) }}</strong>
						</div>
						<div>
							<span>{{ grandTotalBeforeAdjustmentLabel }}</span>
							<strong>{{ formatMoney(preview.gross_before_invoice_adjustment) }}</strong>
						</div>
						<div class="sales-commercial-summary__muted-row">
							<span>{{ invoiceAdjustmentLabel }}</span>
							<strong>−{{ formatMoney(preview.invoice_adjustment_amount) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

					<template v-else-if="hasInvoiceAdjustment">
						<div class="sales-commercial-summary__muted-row">
							<span>{{ invoiceAdjustmentLabel }}</span>
							<strong>−{{ formatMoney(preview.invoice_adjustment_amount) }}</strong>
						</div>
						<div>
							<span>{{ netAfterAdjustmentLabel }}</span>
							<strong>{{ formatMoney(preview.net_total) }}</strong>
						</div>
						<div v-if="hasTax">
							<span>{{ taxLabel(false) }}</span>
							<strong>{{ formatMoney(preview.tax_after_invoice_adjustment) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

					<template v-else>
						<div v-if="hasTax">
							<span>{{ taxLabel(false) }}</span>
							<strong>{{ formatMoney(preview.total_taxes_and_charges) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

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

				<details v-if="pricingBreakdownItems.length" class="sales-commercial-summary__breakdown">
					<summary>View pricing breakdown</summary>
					<div v-for="(item, index) in pricingBreakdownItems" :key="`${item.item_code || 'item'}-${index}`" class="sales-commercial-summary__breakdown-item">
						<strong>{{ item.item_name || item.item_code || `Item ${index + 1}` }}</strong>
						<span v-if="Number(item.item_promotion_amount || 0)">
							Item promotion<span v-if="Number(item.item_promotion_percentage || 0)"> {{ formatPercent(item.item_promotion_percentage) }}</span>
							· −{{ formatMoney(item.item_promotion_amount) }}
						</span>
						<span v-if="Number(item.selling_rate_adjustment || 0)">
							Selling rate adjustment · {{ formatSignedMoney(item.selling_rate_adjustment) }}
						</span>
						<span v-if="Number(item.line_discount_amount || 0)">
							Line discount<span v-if="Number(item.manual_discount_percentage || 0)"> {{ formatPercent(item.manual_discount_percentage) }}</span>
							· −{{ formatMoney(item.line_discount_amount) }}
						</span>
						<small>Line amount {{ formatMoney(item.amount) }}</small>
					</div>
				</details>

				<details v-if="preview.taxes?.length" class="sales-commercial-summary__taxes">
					<summary>View tax breakdown</summary>
					<div v-for="(tax, index) in preview.taxes" :key="`${tax.description || 'tax'}-${index}`">
						<span>
							{{ tax.description || "Tax" }}
							<small v-if="Number(tax.rate || 0)"> {{ formatPercent(tax.rate) }}</small>
							<small v-if="tax.included_in_print_rate"> · included</small>
							<small v-if="taxChangedByInvoiceAdjustment"> · before {{ invoiceAdjustmentNoun }} {{ formatMoney(tax.tax_amount_before_invoice_adjustment) }}</small>
						</span>
						<strong>{{ formatMoney(tax.tax_amount) }}</strong>
					</div>
				</details>
			</template>

			<p v-else class="sales-commercial-summary__empty">
				Add a Customer and sale item to see the subtotal, tax and invoice total before saving.
			</p>
		</div>
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
	computed: {
		hasItemPricingEffects() {
			return Boolean(
				Number(this.preview?.item_promotion_total || 0) ||
				Number(this.preview?.selling_rate_adjustment_total || 0) ||
				Number(this.preview?.line_discount_total || 0),
			);
		},
		hasInvoiceAdjustment() {
			return Boolean(Number(this.preview?.invoice_adjustment_amount || 0));
		},
		hasTax() {
			return Boolean(this.preview?.has_tax || Number(this.preview?.total_taxes_and_charges || 0));
		},
		hasPromotion() {
			return Boolean(
				Number(this.preview?.item_promotion_total || 0) ||
				this.preview?.invoice_adjustment_kind === "promotion",
			);
		},
		invoiceAdjustmentTarget() {
			return this.preview?.invoice_adjustment_target || this.preview?.apply_discount_on || "";
		},
		invoiceAdjustmentNoun() {
			return this.preview?.invoice_adjustment_kind === "promotion" ? "promotion" : "discount";
		},
		invoiceAdjustmentLabel() {
			const label = this.preview?.invoice_adjustment_kind === "promotion" ? "Invoice promotion" : "Invoice discount";
			const percentage = Number(this.preview?.invoice_adjustment_percentage || 0);
			return percentage ? `${label} ${this.formatPercent(percentage)}` : label;
		},
		grandTotalBeforeAdjustmentLabel() {
			return `Grand total before ${this.invoiceAdjustmentNoun}`;
		},
		netAfterAdjustmentLabel() {
			return `Net after ${this.invoiceAdjustmentNoun}`;
		},
		promotionSummary() {
			const item = Number(this.preview?.item_promotion_total || 0) > 0;
			const invoice = this.preview?.invoice_adjustment_kind === "promotion";
			if (item && invoice) return "Item and invoice promotions are included in the calculation below.";
			if (item) return "Item promotion is included in the item pricing below.";
			return "Invoice promotion is included in the calculation below.";
		},
		pricingBreakdownItems() {
			return (this.preview?.items || []).filter((item) =>
				Number(item?.item_promotion_amount || 0) ||
				Number(item?.selling_rate_adjustment || 0) ||
				Number(item?.line_discount_amount || 0),
			);
		},
		taxChangedByInvoiceAdjustment() {
			return Boolean(
				this.hasInvoiceAdjustment &&
				Number(this.preview?.tax_before_invoice_adjustment || 0) !== Number(this.preview?.tax_after_invoice_adjustment || 0),
			);
		},
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
		formatPercent(value) {
			const amount = Number(value || 0);
			return `${Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}%`;
		},
		taxLabel(beforeAdjustment) {
			const taxes = this.preview?.taxes || [];
			let label = this.preview?.all_taxes_included ? "Tax (included)" : "Tax";
			if (taxes.length === 1) {
				const tax = taxes[0];
				label = tax.description || "Tax";
				if (Number(tax.rate || 0)) label += ` ${this.formatPercent(tax.rate)}`;
				if (tax.included_in_print_rate) label += " (included)";
			}
			if (beforeAdjustment) label += ` before ${this.invoiceAdjustmentNoun}`;
			return label;
		},
	},
};
</script>

<style scoped>
.sales-commercial-summary-rail {
	min-width: 0;
}
.sales-commercial-summary {
	display: grid;
	gap: 9px;
	padding: 12px 14px;
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
	gap: 10px;
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
.sales-commercial-summary__taxes small,
.sales-commercial-summary__breakdown summary,
.sales-commercial-summary__breakdown span,
.sales-commercial-summary__breakdown small {
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.sales-commercial-summary__header span {
	font-size: .7rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .06em;
}
.sales-commercial-summary__promotions {
	display: grid;
	gap: 2px;
	padding: 8px 10px;
	border: 1px solid var(--edge-color-success, #12b76a);
	border-radius: 8px;
	background: var(--edge-color-success-subtle, #ecfdf3);
}
.sales-commercial-summary__promotions strong {
	font-size: .8rem;
	color: var(--edge-color-success, #067647);
}
.sales-commercial-summary__promotions span {
	font-size: .74rem;
	color: var(--edge-color-ink-600, #475467);
}
.sales-commercial-summary__rows {
	display: grid;
	gap: 6px;
}
.sales-commercial-summary__muted-row strong {
	color: var(--edge-color-success, #067647);
}
.sales-commercial-summary__total {
	margin-top: 3px;
	padding-top: 9px;
	border-top: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	font-size: 1rem;
}
.sales-commercial-summary__total strong {
	font-size: 1.15rem;
}
.sales-commercial-summary__context {
	display: flex;
	gap: 6px 12px;
	flex-wrap: wrap;
	font-size: .76rem;
}
.sales-commercial-summary__taxes,
.sales-commercial-summary__breakdown {
	padding-top: 1px;
}
.sales-commercial-summary__taxes summary,
.sales-commercial-summary__breakdown summary {
	cursor: pointer;
	font-size: .78rem;
	font-weight: 600;
}
.sales-commercial-summary__taxes > div {
	padding: 6px 0 0;
	font-size: .78rem;
}
.sales-commercial-summary__breakdown-item {
	display: grid;
	gap: 2px;
	padding: 7px 0;
	border-bottom: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	font-size: .76rem;
}
.sales-commercial-summary__breakdown-item:last-child {
	border-bottom: 0;
}
.sales-commercial-summary__breakdown-item strong {
	font-size: .78rem;
}
.sales-commercial-summary__error {
	display: grid;
	gap: 3px;
	padding: 9px 10px;
	border: 1px solid var(--edge-color-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-color-danger, #b42318);
	background: var(--edge-color-danger-subtle, #fef3f2);
}
.sales-commercial-summary__empty {
	margin: 0;
	font-size: .8rem;
}
:global(:root[data-edge-appearance="dark"]) .sales-commercial-summary {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
</style>
