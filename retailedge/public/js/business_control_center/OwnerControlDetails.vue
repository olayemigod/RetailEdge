<template>
	<section class="owner-control-details">
		<div class="detail-grid">
			<article class="detail-panel">
				<header class="detail-header">
					<div><strong>Receivables & Collections</strong><small>Current ERPNext outstanding receivables, exposure and collection priorities.</small></div>
					<button class="edge-button" type="button" :disabled="receivablesLoading" @click="$emit('load-receivables')">{{ receivablesLoading ? "Loading…" : receivablesLoaded ? "Refresh" : "Load details" }}</button>
				</header>
				<div v-if="receivablesError" class="detail-error">{{ receivablesError }}</div>
				<template v-else-if="receivablesLoaded">
					<div class="metric-grid">
						<div v-for="card in receivables.summary || []" :key="card.label" class="metric-card"><small>{{ card.label }}</small><strong>{{ formatValue(card.value, card.datatype) }}</strong></div>
					</div>
					<div class="detail-subsection">
						<strong>Collection priorities</strong>
						<div v-if="(receivables.collection_priorities || []).length" class="detail-list">
							<button v-for="row in receivables.collection_priorities.slice(0, 8)" :key="row.invoice" class="detail-row detail-row--button" type="button" @click="openSalesInvoice(row.invoice)">
								<span><strong>{{ row.customer_name || row.customer }}</strong><small>{{ row.invoice }} · {{ row.overdue_days }} days overdue · {{ row.priority }}</small></span>
								<strong>{{ formatValue(row.outstanding, 'Currency') }}</strong>
							</button>
						</div>
						<div v-else class="detail-empty">No overdue collection priorities in this scope.</div>
					</div>
					<div class="detail-subsection">
						<strong>Top customer exposure</strong>
						<div class="detail-list">
							<div v-for="row in (receivables.top_customer_exposures || []).slice(0, 5)" :key="row.customer" class="detail-row">
								<span><strong>{{ row.customer_name || row.customer }}</strong><small>{{ row.invoice_count }} open invoice(s) · {{ formatPercent(row.share_percent) }} of receivables</small></span>
								<strong>{{ formatValue(row.outstanding, 'Currency') }}</strong>
							</div>
						</div>
					</div>
					<p class="detail-note">“Newly overdue” means currently outstanding invoices whose due date fell in the selected period; it is not a reconstructed historical receivables balance.</p>
				</template>
				<div v-else class="detail-empty">Load details when you need customer concentration, ageing and invoice-level collection priorities.</div>
			</article>

			<article class="detail-panel">
				<header class="detail-header">
					<div><strong>Supplier Obligations</strong><small>Current submitted Purchase Invoice obligations and payment-attention priorities.</small></div>
					<button class="edge-button" type="button" :disabled="supplierLoading" @click="$emit('load-suppliers')">{{ supplierLoading ? "Loading…" : supplierLoaded ? "Refresh" : "Load details" }}</button>
				</header>
				<div v-if="supplierError" class="detail-error">{{ supplierError }}</div>
				<template v-else-if="supplierLoaded">
					<div class="metric-grid">
						<div v-for="card in supplier.summary || []" :key="card.label" class="metric-card"><small>{{ card.label }}</small><strong>{{ formatValue(card.value, card.datatype) }}</strong></div>
					</div>
					<div class="detail-subsection">
						<strong>Payment-attention priorities</strong>
						<div v-if="(supplier.payment_priorities || []).length" class="detail-list">
							<button v-for="row in supplier.payment_priorities.slice(0, 8)" :key="row.invoice" class="detail-row detail-row--button" type="button" @click="openPurchaseInvoice(row)">
								<span><strong>{{ row.supplier_name || row.supplier }}</strong><small>{{ row.invoice }} · {{ row.overdue_days }} days overdue · {{ row.priority }}</small></span>
								<strong>{{ formatValue(row.outstanding, 'Currency') }}</strong>
							</button>
						</div>
						<div v-else class="detail-empty">No overdue supplier obligations in this scope.</div>
					</div>
					<div class="detail-subsection">
						<strong>Top supplier exposure</strong>
						<div class="detail-list">
							<div v-for="row in (supplier.supplier_exposure || []).slice(0, 5)" :key="row.supplier" class="detail-row">
								<span><strong>{{ row.supplier_name || row.supplier }}</strong><small>{{ row.open_bills }} open bill(s) · {{ formatPercent(row.share_percent) }} of payables</small></span>
								<strong>{{ formatValue(row.outstanding, 'Currency') }}</strong>
							</div>
						</div>
					</div>
					<p class="detail-note">Payment priority is an ageing-based attention signal only. Contract terms, disputes, available cash and approval remain authoritative.</p>
				</template>
				<div v-else class="detail-empty">Load details when you need supplier concentration, ageing and invoice-level payment attention.</div>
			</article>
		</div>

		<article class="detail-panel detail-panel--wide">
			<header class="detail-header">
				<div><strong>Budget & Spend Governance</strong><small>Submitted ERPNext Budget plus RetailEdge expense actuals and burn-rate signals.</small></div>
			</header>
			<div v-if="budget?.available === false" class="detail-empty">{{ budget.reason || "Budget governance is unavailable for this scope." }}</div>
			<template v-else>
				<div class="metric-grid metric-grid--wide">
					<div v-for="card in budget?.summary || []" :key="card.label" class="metric-card" :class="{ 'metric-card--unavailable': card.available === false }">
						<small>{{ card.label }}</small><strong>{{ card.available === false ? 'Unavailable' : formatValue(card.value, card.datatype) }}</strong>
					</div>
				</div>
				<div class="detail-grid detail-grid--inner">
					<div class="detail-subsection">
						<strong>Governance signals</strong>
						<div v-if="(budget?.controls || []).length" class="detail-list">
							<div v-for="(row, index) in (budget.controls || []).slice(0, 10)" :key="`${row.family}:${row.label}:${index}`" class="detail-row">
								<span><strong>{{ row.label }}</strong><small>{{ row.family }}</small></span><strong>{{ formatValue(row.value, row.datatype) }}</strong>
							</div>
						</div>
						<div v-else class="detail-empty">No budget or spend governance warning is active.</div>
					</div>
					<div class="detail-subsection">
						<strong>Category pressure</strong>
						<div v-if="(budget?.category_pressure || []).length" class="detail-list">
							<div v-for="row in (budget.category_pressure || []).slice(0, 8)" :key="row.category" class="detail-row">
								<span><strong>{{ row.category || 'Unclassified category' }}</strong><small>{{ formatValue(row.actual, 'Currency') }} actual vs {{ formatValue(row.target, 'Currency') }} budget</small></span><strong>{{ formatPercent(row.value) }}</strong>
							</div>
						</div>
						<div v-else class="detail-empty">No category has crossed the configured budget-pressure threshold.</div>
					</div>
				</div>
				<p class="detail-note">Projected spend is a straight-line burn-rate planning signal, not an accounting forecast. Ambiguous category mappings are withheld rather than allocated artificially.</p>
			</template>
		</article>
	</section>
</template>

<script>
export default {
	name: "RetailEdgeOwnerControlDetails",
	props: {
		receivables: { type: Object, default: () => ({}) },
		receivablesLoaded: Boolean,
		receivablesLoading: Boolean,
		receivablesError: { type: String, default: "" },
		supplier: { type: Object, default: () => ({}) },
		supplierLoaded: Boolean,
		supplierLoading: Boolean,
		supplierError: { type: String, default: "" },
		budget: { type: Object, default: () => ({}) },
	},
	emits: ["load-receivables", "load-suppliers"],
	methods: {
		formatValue(value, datatype) { if (value === null || value === undefined) return "—"; try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value; } },
		formatPercent(value) { return value === null || value === undefined ? "—" : `${Number(value).toFixed(1)}%`; },
		openSalesInvoice(invoice) { if (invoice) window.open(`/app/sales-invoice/${encodeURIComponent(invoice)}`, "_blank", "noopener,noreferrer"); },
		openPurchaseInvoice(row) { const route = row?.route || (row?.invoice ? `/app/purchase-invoice/${encodeURIComponent(row.invoice)}` : ""); if (route) window.open(route, "_blank", "noopener,noreferrer"); },
	},
};
</script>

<style scoped>
.owner-control-details { display: grid; gap: 14px; margin-bottom: 16px; }
.detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 14px; }
.detail-grid--inner { margin-top: 14px; }
.detail-panel { display: grid; gap: 14px; padding: 14px; border: 1px solid var(--edge-border); border-radius: 10px; background: var(--edge-surface); color: var(--edge-text); }
.detail-panel--wide { grid-column: 1 / -1; }
.detail-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; }
.detail-header > div, .detail-row span { display: grid; gap: 4px; }
.detail-header small, .detail-row small, .detail-note, .detail-empty { color: var(--edge-text-muted); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; }
.metric-grid--wide { grid-template-columns: repeat(6, minmax(0, 1fr)); }
.metric-card { display: grid; gap: 4px; padding: 10px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface-soft, var(--edge-surface)); }
.metric-card small { color: var(--edge-text-muted); font-size: 11px; }
.metric-card--unavailable { opacity: .72; }
.detail-subsection { display: grid; gap: 8px; }
.detail-list { display: grid; gap: 6px; }
.detail-row { display: flex; justify-content: space-between; align-items: center; gap: 12px; padding: 9px 10px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface-soft, var(--edge-surface)); color: var(--edge-text); }
.detail-row--button { width: 100%; text-align: left; cursor: pointer; }
.detail-row--button:hover { border-color: var(--edge-primary, var(--edge-border)); }
.detail-error { padding: 10px; border: 1px solid var(--red-300, var(--edge-border)); border-radius: 8px; color: var(--edge-text); }
.detail-note { margin: 0; }
@media (max-width: 1100px) { .metric-grid--wide { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (max-width: 850px) { .detail-grid { grid-template-columns: 1fr; } .metric-grid, .metric-grid--wide { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 560px) { .detail-header, .detail-row { align-items: flex-start; } .metric-grid, .metric-grid--wide { grid-template-columns: 1fr; } }
</style>
