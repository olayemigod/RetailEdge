<template>
	<section class="sale-review" aria-label="Sale review before submission">
		<div class="sale-review__heading">
			<div>
				<span class="sale-review__kicker">Review before submission</span>
				<h3>Confirm the sale details</h3>
				<p>Check the customer, items, prices and totals below before submitting. Submission posts the final accounting{{ document.update_stock ? " and stock" : "" }} effects.</p>
			</div>
			<span class="sale-review__count">{{ document.item_count || items.length }} item{{ Number(document.item_count || items.length) === 1 ? "" : "s" }}</span>
		</div>

		<div class="sale-review__context">
			<div><span>Customer</span><strong>{{ document.customer_name || document.customer || "Not set" }}</strong></div>
			<div><span>Company</span><strong>{{ document.company || "Not set" }}</strong></div>
			<div v-if="document.branch"><span>Branch</span><strong>{{ document.branch }}</strong></div>
			<div><span>Posting date</span><strong>{{ document.posting_date || "Not set" }}</strong></div>
			<div v-if="document.selling_price_list"><span>Price list</span><strong>{{ document.selling_price_list }}</strong></div>
			<div><span>Stock posting</span><strong>{{ document.update_stock ? "Update stock on submission" : "Accounting only" }}</strong></div>
		</div>

		<div class="sale-review__table-wrap">
			<table class="sale-review__table">
				<thead>
					<tr>
						<th>Item</th>
						<th>Qty</th>
						<th>Rate</th>
						<th v-if="hasItemDiscount">Discount</th>
						<th>Amount</th>
						<th v-if="document.update_stock">Stock Location</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(item, index) in items" :key="item.name || `${item.item_code}-${index}`">
						<td>
							<strong>{{ item.item_name || item.item_code || "Item" }}</strong>
							<small v-if="item.item_name && item.item_code">{{ item.item_code }}</small>
						</td>
						<td>{{ formatQuantity(item.qty) }}<small v-if="item.uom"> {{ item.uom }}</small></td>
						<td>{{ money(item.rate) }}</td>
						<td v-if="hasItemDiscount">{{ formatPercent(item.discount_percentage) }}</td>
						<td><strong>{{ money(item.amount) }}</strong></td>
						<td v-if="document.update_stock">{{ item.warehouse || "Not set" }}</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div class="sale-review__lower">
			<div class="sale-review__details">
				<div v-if="taxes.length">
					<strong>Taxes & charges</strong>
					<div v-for="(tax, index) in taxes" :key="`${tax.account_head}-${index}`" class="sale-review__detail-row">
						<span>{{ tax.description || tax.account_head || "Tax / charge" }}<template v-if="tax.rate"> · {{ formatPercent(tax.rate) }}</template></span>
						<strong>{{ money(tax.tax_amount) }}</strong>
					</div>
				</div>
				<div v-if="payments.length">
					<strong>Payments recorded</strong>
					<div v-for="(payment, index) in payments" :key="`${payment.mode_of_payment}-${index}`" class="sale-review__detail-row">
						<span>{{ payment.mode_of_payment || "Payment" }}</span>
						<strong>{{ money(payment.amount) }}</strong>
					</div>
				</div>
				<div v-if="document.remarks" class="sale-review__remarks">
					<strong>Remarks</strong>
					<p>{{ document.remarks }}</p>
				</div>
			</div>

			<div class="sale-review__summary" aria-label="Sale totals">
				<div><span>Subtotal</span><strong>{{ money(document.net_total) }}</strong></div>
				<div v-if="Number(document.discount_amount || 0)"><span>Invoice discount</span><strong>-{{ money(document.discount_amount) }}</strong></div>
				<div v-if="Number(document.total_taxes_and_charges || 0)"><span>Taxes & charges</span><strong>{{ money(document.total_taxes_and_charges) }}</strong></div>
				<div class="sale-review__grand"><span>Total</span><strong>{{ money(payableTotal) }}</strong></div>
				<div v-if="Number(document.paid_amount || 0)"><span>Paid</span><strong>{{ money(document.paid_amount) }}</strong></div>
				<div class="sale-review__due"><span>Amount due</span><strong>{{ money(document.outstanding_amount) }}</strong></div>
			</div>
		</div>
	</section>
</template>

<script>
export default {
	name: "SalesInvoiceSubmissionReview",
	props: {
		document: { type: Object, required: true },
	},
	computed: {
		items() {
			return Array.isArray(this.document?.items) ? this.document.items : [];
		},
		taxes() {
			return Array.isArray(this.document?.taxes) ? this.document.taxes.filter((row) => Number(row?.tax_amount || 0) !== 0) : [];
		},
		payments() {
			return Array.isArray(this.document?.payments) ? this.document.payments.filter((row) => Number(row?.amount || 0) !== 0) : [];
		},
		hasItemDiscount() {
			return this.items.some((row) => Number(row?.discount_percentage || 0) !== 0);
		},
		payableTotal() {
			return Number(this.document?.rounded_total || 0) || Number(this.document?.grand_total || 0);
		},
	},
	methods: {
		money(value) {
			const currency = String(this.document?.currency || "NGN").trim() || "NGN";
			return `${currency} ${Number(value || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
		},
		formatQuantity(value) {
			return Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 3 });
		},
		formatPercent(value) {
			return `${Number(value || 0).toLocaleString(undefined, { maximumFractionDigits: 2 })}%`;
		},
	},
};
</script>

<style scoped>
.sale-review {
	display: grid;
	gap: 16px;
	padding: 16px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 10px;
	background: var(--edge-color-surface-muted, #f8fafc);
}
.sale-review__heading,
.sale-review__lower,
.sale-review__detail-row,
.sale-review__summary > div {
	display: flex;
	justify-content: space-between;
	gap: 16px;
}
.sale-review__heading {
	align-items: flex-start;
}
.sale-review__heading h3 {
	margin: 3px 0 4px;
}
.sale-review__heading p,
.sale-review__remarks p {
	margin: 0;
	color: var(--edge-color-ink-500, #667085);
}
.sale-review__kicker {
	font-size: .72rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .07em;
	color: var(--edge-color-brand-600, #2563eb);
}
.sale-review__count {
	white-space: nowrap;
	font-size: .8rem;
	font-weight: 700;
	padding: 6px 9px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 999px;
}
.sale-review__context {
	display: grid;
	grid-template-columns: repeat(3, minmax(0, 1fr));
	gap: 10px;
}
.sale-review__context > div {
	display: grid;
	gap: 3px;
	padding: 10px 12px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 8px;
	background: var(--edge-color-surface, #fff);
}
.sale-review__context span,
.sale-review__table small,
.sale-review__summary span,
.sale-review__detail-row span {
	color: var(--edge-color-ink-500, #667085);
}
.sale-review__context span,
.sale-review__table small {
	font-size: .78rem;
}
.sale-review__table-wrap {
	overflow-x: auto;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 8px;
	background: var(--edge-color-surface, #fff);
}
.sale-review__table {
	width: 100%;
	border-collapse: collapse;
	min-width: 720px;
}
.sale-review__table th,
.sale-review__table td {
	padding: 10px 12px;
	text-align: left;
	border-bottom: 1px solid var(--edge-color-border, #dfe3e8);
}
.sale-review__table th {
	font-size: .78rem;
	color: var(--edge-color-ink-500, #667085);
	background: var(--edge-color-surface-muted, #f8fafc);
}
.sale-review__table tbody tr:last-child td {
	border-bottom: 0;
}
.sale-review__table td:first-child {
	display: grid;
	gap: 2px;
}
.sale-review__lower {
	align-items: flex-start;
}
.sale-review__details,
.sale-review__summary {
	display: grid;
	gap: 8px;
}
.sale-review__details {
	flex: 1 1 auto;
}
.sale-review__details > div {
	display: grid;
	gap: 6px;
}
.sale-review__summary {
	flex: 0 0 min(360px, 100%);
	padding: 12px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 8px;
	background: var(--edge-color-surface, #fff);
}
.sale-review__grand,
.sale-review__due {
	padding-top: 8px;
	border-top: 1px solid var(--edge-color-border, #dfe3e8);
}
.sale-review__grand strong,
.sale-review__due strong {
	font-size: 1.05rem;
}
:global(:root[data-edge-appearance="dark"]) .sale-review,
:global(:root[data-edge-appearance="dark"]) .sale-review__context > div,
:global(:root[data-edge-appearance="dark"]) .sale-review__table-wrap,
:global(:root[data-edge-appearance="dark"]) .sale-review__summary {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
@media (max-width: 760px) {
	.sale-review__heading,
	.sale-review__lower {
		flex-direction: column;
	}
	.sale-review__context {
		grid-template-columns: 1fr;
	}
	.sale-review__summary {
		width: 100%;
	}
}
</style>
