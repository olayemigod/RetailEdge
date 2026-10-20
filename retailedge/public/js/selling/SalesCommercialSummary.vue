<template>
	<section class="sales-commercial-summary-rail" aria-live="polite" :aria-label="summaryKicker">
		<div class="edge-panel sales-commercial-summary">
			<div class="sales-commercial-summary__header">
				<div>
					<span>{{ summaryKicker }}</span>
					<strong>{{ currentValueLabel }}</strong>
				</div>
				<small v-if="loading">Updating total…</small>
			</div>

			<div v-if="error" class="sales-commercial-summary__error" role="alert">
				<strong>{{ calculationErrorLabel }}</strong>
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
						<strong class="sales-commercial-summary__negative-amount">−{{ formatMoney(preview.item_promotion_total) }}</strong>
					</div>
					<div v-if="Number(preview.selling_rate_adjustment_total || 0)" class="sales-commercial-summary__muted-row">
						<span>Rate adjustments</span>
						<strong :class="amountClass(preview.selling_rate_adjustment_total)">{{ formatSignedMoney(preview.selling_rate_adjustment_total) }}</strong>
					</div>
					<div v-if="Number(preview.line_discount_total || 0)" class="sales-commercial-summary__muted-row">
						<span>Line discounts</span>
						<strong class="sales-commercial-summary__negative-amount">−{{ formatMoney(preview.line_discount_total) }}</strong>
					</div>
					<div>
						<span>Items subtotal</span>
						<strong>{{ formatMoney(preview.subtotal) }}</strong>
					</div>

					<template v-if="hasInvoiceAdjustment && invoiceAdjustmentTarget === 'Grand Total'">
						<div>
							<span>{{ grandTotalBeforeAdjustmentLabel }}</span>
							<strong>{{ formatMoney(preview.gross_before_invoice_adjustment) }}</strong>
						</div>
						<div class="sales-commercial-summary__muted-row">
							<span>{{ invoiceAdjustmentLabel }}</span>
							<strong class="sales-commercial-summary__negative-amount">−{{ formatMoney(preview.invoice_adjustment_amount) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

					<template v-else-if="hasInvoiceAdjustment">
						<div class="sales-commercial-summary__muted-row">
							<span>{{ invoiceAdjustmentLabel }}</span>
							<strong class="sales-commercial-summary__negative-amount">−{{ formatMoney(preview.invoice_adjustment_amount) }}</strong>
						</div>
						<div>
							<span>{{ netAfterAdjustmentLabel }}</span>
							<strong>{{ formatMoney(preview.net_total) }}</strong>
						</div>
						<div v-if="hasTax">
							<span>{{ taxLabel() }}</span>
							<strong>{{ formatMoney(preview.tax_after_invoice_adjustment) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

					<template v-else>
						<div v-if="hasTax">
							<span>{{ taxLabel() }}</span>
							<strong>{{ formatMoney(preview.total_taxes_and_charges) }}</strong>
						</div>
						<div v-if="Number(preview.rounding_adjustment || 0)">
							<span>Total before rounding</span>
							<strong>{{ formatMoney(preview.grand_total) }}</strong>
						</div>
					</template>

					<div v-if="Number(preview.rounding_adjustment || 0)">
						<span>Rounding</span>
						<strong :class="amountClass(preview.rounding_adjustment)">{{ formatSignedMoney(preview.rounding_adjustment) }}</strong>
					</div>
					<div class="sales-commercial-summary__total">
						<span>{{ totalLabel }}</span>
						<strong>{{ formatMoney(preview.document_total ?? preview.invoice_total) }}</strong>
					</div>
				</div>

				<div
					v-if="hasTax && hasInvoiceAdjustment && invoiceAdjustmentTarget === 'Grand Total'"
					class="sales-commercial-summary__final-tax"
				>
					<span>{{ finalTaxLabel }}</span>
					<strong>{{ formatMoney(preview.tax_after_invoice_adjustment) }}</strong>
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
							· <span class="sales-commercial-summary__negative-amount">−{{ formatMoney(item.item_promotion_amount) }}</span>
						</span>
						<span v-if="Number(item.selling_rate_adjustment || 0)">
							Rate adjustment · <span :class="amountClass(item.selling_rate_adjustment)">{{ formatSignedMoney(item.selling_rate_adjustment) }}</span>
						</span>
						<span v-if="Number(item.line_discount_amount || 0)">
							Line discount<span v-if="Number(item.manual_discount_percentage || 0)"> {{ formatPercent(item.manual_discount_percentage) }}</span>
							· <span class="sales-commercial-summary__negative-amount">−{{ formatMoney(item.line_discount_amount) }}</span>
						</span>
						<small>Line amount {{ formatMoney(item.amount) }}</small>
					</div>
				</details>

				<details v-if="preview.taxes?.length" class="sales-commercial-summary__taxes">
					<summary>View tax breakdown</summary>
					<div v-for="(tax, index) in preview.taxes" :key="`${tax.description || 'tax'}-${index}`" class="sales-commercial-summary__tax-item">
						<div class="sales-commercial-summary__tax-row">
							<span>
								{{ taxDisplayName(tax) }}
								<small v-if="tax.included_in_print_rate"> · included</small>
								<small v-if="taxChanged(tax)"> · final after {{ invoiceAdjustmentNoun }}</small>
							</span>
							<strong>{{ formatMoney(tax.tax_amount) }}</strong>
						</div>
						<div v-if="taxChanged(tax)" class="sales-commercial-summary__tax-history">
							<span>Before {{ invoiceAdjustmentNoun }}</span>
							<strong>{{ formatMoney(tax.tax_amount_before_invoice_adjustment) }}</strong>
							<span>Tax change</span>
							<strong :class="amountClass(taxChangeAmount(tax))">{{ formatSignedMoney(taxChangeAmount(tax)) }}</strong>
						</div>
					</div>
				</details>
			</template>

			<p v-else class="sales-commercial-summary__empty">{{ emptyMessage }}</p>
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
		documentLabel: { type: String, default: "Invoice" },
	},
	computed: {
		documentNoun() {
			return String(this.documentLabel || "Invoice").trim().toLowerCase() || "invoice";
		},
		summaryKicker() {
			return this.documentLabel === "Invoice" ? "Sale summary" : `${this.documentLabel} summary`;
		},
		currentValueLabel() {
			if (this.documentLabel === "Invoice") return this.preview ? "Current invoice value" : "Invoice value";
			return this.preview ? `Current ${this.documentNoun} value` : `${this.documentLabel} value`;
		},
		calculationErrorLabel() {
			return this.documentLabel === "Invoice" ? "Unable to calculate this sale" : `Unable to calculate this ${this.documentNoun}`;
		},
		totalLabel() {
			return this.documentLabel === "Invoice" ? "Invoice Total" : `${this.documentLabel} Total`;
		},
		emptyMessage() {
			if (this.documentLabel === "Invoice") return "Add a Customer and sale item to see the subtotal, tax and invoice total before saving.";
			return `Add a Customer and item to see the subtotal, tax and ${this.documentNoun} total before saving.`;
		},
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
			const adjustment = this.preview?.invoice_adjustment_kind === "promotion" ? "promotion" : "discount";
			const prefix = this.documentLabel === "Invoice" ? "Invoice" : this.documentLabel;
			const percentage = Number(this.preview?.invoice_adjustment_percentage || 0);
			const label = `${prefix} ${adjustment}`;
			return percentage ? `${label} ${this.formatPercent(percentage)}` : label;
		},
		grandTotalBeforeAdjustmentLabel() {
			return `Before ${this.documentNoun} ${this.invoiceAdjustmentNoun}`;
		},
		netAfterAdjustmentLabel() {
			return `Net after ${this.invoiceAdjustmentNoun}`;
		},
		finalTaxLabel() {
			const taxes = this.preview?.taxes || [];
			if (taxes.length === 1) return `Final ${this.taxDisplayName(taxes[0])}`;
			return "Final tax";
		},
		promotionSummary() {
			const item = Number(this.preview?.item_promotion_total || 0) > 0;
			const documentPromotion = this.preview?.invoice_adjustment_kind === "promotion";
			if (item && documentPromotion) {
				return this.documentLabel === "Invoice"
					? "Item and invoice promotions are included in the calculation below."
					: `Item and ${this.documentNoun} promotions are included in the calculation below.`;
			}
			if (item) return "Item promotion is included in the item pricing below.";
			return this.documentLabel === "Invoice"
				? "Invoice promotion is included in the calculation below."
				: `${this.documentLabel} promotion is included in the calculation below.`;
		},
		pricingBreakdownItems() {
			return (this.preview?.items || []).filter((item) =>
				Number(item?.item_promotion_amount || 0) ||
				Number(item?.selling_rate_adjustment || 0) ||
				Number(item?.line_discount_amount || 0),
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
		amountClass(value) {
			const amount = Number(value || 0);
			if (amount < 0) return "sales-commercial-summary__negative-amount";
			if (amount > 0) return "sales-commercial-summary__positive-amount";
			return "";
		},
		formatPercent(value) {
			const amount = Number(value || 0);
			return `${Number.isInteger(amount) ? amount.toFixed(0) : amount.toFixed(2).replace(/0+$/, "").replace(/\.$/, "")}%`;
		},
		taxDescriptionIncludesRate(description, rate) {
			const expected = Number(rate || 0);
			if (!expected) return false;
			const matches = String(description || "").match(/-?\d+(?:\.\d+)?\s*%/g) || [];
			return matches.some((match) => Math.abs(Number.parseFloat(match) - expected) < 0.000001);
		},
		configuredTaxDisplayName(tax) {
			let label = String(tax?.description || "Tax").trim() || "Tax";
			const rate = Number(tax?.rate || 0);
			if (!rate) return label;
			const configuredRate = this.formatPercent(rate);
			const atRate = /(@\s*)-?\d+(?:\.\d+)?\s*%?\s*$/i;
			if (atRate.test(label)) return label.replace(atRate, `$1${configuredRate}`);
			const trailingPercentage = /-?\d+(?:\.\d+)?\s*%\s*$/;
			if (trailingPercentage.test(label)) return label.replace(trailingPercentage, configuredRate);
			if (!this.taxDescriptionIncludesRate(label, rate)) label += ` ${configuredRate}`;
			return label;
		},
		taxDisplayName(tax) {
			return this.configuredTaxDisplayName(tax);
		},
		taxLabel() {
			const taxes = this.preview?.taxes || [];
			let label = this.preview?.all_taxes_included ? "Tax (included)" : "Tax";
			if (taxes.length === 1) {
				const tax = taxes[0];
				label = this.taxDisplayName(tax);
				if (tax.included_in_print_rate) label += " (included)";
			}
			return label;
		},
		taxChanged(tax) {
			return Boolean(
				this.hasInvoiceAdjustment &&
				Number(tax?.tax_amount_before_invoice_adjustment || 0) !== Number(tax?.tax_amount || 0),
			);
		},
		taxChangeAmount(tax) {
			return Number(tax?.tax_amount || 0) - Number(tax?.tax_amount_before_invoice_adjustment || 0);
		},
	},
};
</script>

<style scoped>
.sales-commercial-summary-rail { min-width: 0; }
.sales-commercial-summary {
	display: grid;
	gap: 7px;
	padding: 10px 12px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 10px;
	background: var(--edge-color-surface, #fff);
}
.sales-commercial-summary__header,
.sales-commercial-summary__rows > div,
.sales-commercial-summary__tax-row,
.sales-commercial-summary__final-tax {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 8px;
}
.sales-commercial-summary__header > div { display: grid; gap: 1px; }
.sales-commercial-summary__header span,
.sales-commercial-summary__header small,
.sales-commercial-summary__rows span,
.sales-commercial-summary__context,
.sales-commercial-summary__empty,
.sales-commercial-summary__taxes summary,
.sales-commercial-summary__taxes small,
.sales-commercial-summary__breakdown summary,
.sales-commercial-summary__breakdown span,
.sales-commercial-summary__breakdown small,
.sales-commercial-summary__final-tax span {
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.sales-commercial-summary__header span {
	font-size: .66rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .05em;
}
.sales-commercial-summary__header strong { font-size: .9rem; line-height: 1.2; }
.sales-commercial-summary__promotions {
	display: grid;
	gap: 1px;
	padding: 6px 8px;
	border: 1px solid var(--edge-color-success, #12b76a);
	border-radius: 8px;
	background: var(--edge-color-success-subtle, #ecfdf3);
}
.sales-commercial-summary__promotions strong { font-size: .76rem; color: var(--edge-color-success, #067647); }
.sales-commercial-summary__promotions span { font-size: .7rem; line-height: 1.2; color: var(--edge-color-ink-600, #475467); }
.sales-commercial-summary__rows { display: grid; gap: 4px; }
.sales-commercial-summary__rows span { font-size: .76rem; font-weight: 500; line-height: 1.2; }
.sales-commercial-summary__rows strong { font-size: .78rem; font-weight: 700; line-height: 1.2; white-space: nowrap; }
.sales-commercial-summary__negative-amount { color: var(--edge-color-danger, #d92d20) !important; }
.sales-commercial-summary__positive-amount { color: var(--edge-color-success, #067647) !important; }
.sales-commercial-summary__total {
	margin-top: 2px;
	padding-top: 7px;
	border-top: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
}
.sales-commercial-summary__total span { font-size: .82rem; font-weight: 600; }
.sales-commercial-summary__total strong { font-size: 1.02rem; font-weight: 700; }
.sales-commercial-summary__final-tax { padding-top: 2px; font-size: .72rem; line-height: 1.2; }
.sales-commercial-summary__final-tax span { font-weight: 500; }
.sales-commercial-summary__final-tax strong { font-size: .74rem; font-weight: 650; white-space: nowrap; }
.sales-commercial-summary__context { display: flex; gap: 4px 10px; flex-wrap: wrap; font-size: .7rem; line-height: 1.2; }
.sales-commercial-summary__taxes,
.sales-commercial-summary__breakdown { padding-top: 0; }
.sales-commercial-summary__taxes summary,
.sales-commercial-summary__breakdown summary { cursor: pointer; font-size: .72rem; font-weight: 600; line-height: 1.2; }
.sales-commercial-summary__tax-item { padding: 4px 0 0; font-size: .72rem; }
.sales-commercial-summary__tax-row { line-height: 1.2; }
.sales-commercial-summary__tax-row > span { min-width: 0; font-weight: 500; }
.sales-commercial-summary__tax-row > strong { font-size: .74rem; font-weight: 650; white-space: nowrap; }
.sales-commercial-summary__tax-row small { font-size: .68rem; font-weight: 400; }
.sales-commercial-summary__tax-history {
	display: grid;
	grid-template-columns: minmax(0, 1fr) auto;
	gap: 2px 8px;
	padding: 3px 0 0 8px;
	font-size: .68rem;
	line-height: 1.2;
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.sales-commercial-summary__tax-history strong { font-size: .69rem; font-weight: 600; white-space: nowrap; }
.sales-commercial-summary__breakdown-item {
	display: grid;
	gap: 1px;
	padding: 4px 0;
	border-bottom: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	font-size: .72rem;
	line-height: 1.2;
}
.sales-commercial-summary__breakdown-item:last-child { border-bottom: 0; }
.sales-commercial-summary__breakdown-item strong { font-size: .74rem; font-weight: 650; }
.sales-commercial-summary__breakdown-item span,
.sales-commercial-summary__breakdown-item small { font-weight: 400; }
.sales-commercial-summary__error {
	display: grid;
	gap: 3px;
	padding: 8px 9px;
	border: 1px solid var(--edge-color-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-color-danger, #b42318);
	background: var(--edge-color-danger-subtle, #fef3f2);
}
.sales-commercial-summary__empty { margin: 0; font-size: .76rem; }
:global(:root[data-edge-appearance="dark"]) .sales-commercial-summary {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
</style>
