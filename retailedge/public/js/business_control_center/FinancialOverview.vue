<template>
	<div class="financial-overview">
		<div class="overview-section">
			<div class="overview-heading">
				<span><strong>Liquidity & Near-Term Position</strong><small>Current cash position and selected-period cash movement are shown separately.</small></span>
				<small v-if="liquidity.horizon_days">{{ liquidity.horizon_days }}-day control horizon</small>
			</div>
			<div v-if="hasLiquidity" class="metric-grid">
				<div v-for="metric in liquidityMetrics" :key="metric.label" class="metric-card">
					<span>{{ metric.label }}</span>
					<strong>{{ formatMetric(metric) }}</strong>
					<small>{{ metric.note }}</small>
				</div>
			</div>
			<div v-else class="overview-empty">Liquidity detail is unavailable for this scope.</div>
			<div v-if="cashUnavailableReason" class="overview-note">{{ cashUnavailableReason }}</div>
		</div>

		<div class="overview-section">
			<div class="overview-heading">
				<span><strong>Financial Position Snapshot</strong><small>Loaded only when requested so the Business Control Centre does not repeatedly run the heavier owner/accounting snapshot.</small></span>
				<button class="edge-button" type="button" :disabled="loadingPosition" @click="$emit('load-position')">{{ loadingPosition ? "Loading…" : positionLoaded ? "Refresh snapshot" : "Load snapshot" }}</button>
			</div>
			<div v-if="positionError" class="overview-note overview-note--danger">{{ positionError }}</div>
			<template v-if="positionLoaded && !positionError">
				<div class="snapshot-group">
					<strong>Current position</strong>
					<div class="metric-grid">
						<div v-for="card in availablePositionCards" :key="card.label" class="metric-card">
							<span>{{ card.label }}</span>
							<strong>{{ formatValue(card.value, card.datatype) }}</strong>
							<small>Current position</small>
						</div>
					</div>
					<div v-for="card in unavailablePositionCards" :key="`unavailable-${card.label}`" class="overview-note"><strong>{{ card.label }} unavailable.</strong> {{ card.reason || "This value is withheld for the current scope." }}</div>
				</div>
				<div class="snapshot-group">
					<strong>Selected-period performance & movement</strong>
					<div class="metric-grid">
						<div v-for="card in availablePeriodCards" :key="card.label" class="metric-card">
							<span>{{ card.label }}</span>
							<strong>{{ formatValue(card.value, card.datatype) }}</strong>
							<small>Selected period</small>
						</div>
					</div>
				</div>
				<div class="overview-note">Net Trade Position means current receivables minus current payables. It is not accounting net assets or complete working capital. Net Cash Movement is period movement, not available cash.</div>
			</template>
		</div>
	</div>
</template>

<script>
export default {
	name: "RetailEdgeFinancialOverview",
	props: {
		earlyWarning: { type: Object, default: () => ({}) },
		position: { type: Object, default: () => ({}) },
		positionLoaded: { type: Boolean, default: false },
		loadingPosition: { type: Boolean, default: false },
		positionError: { type: String, default: "" },
	},
	emits: ["load-position"],
	computed: {
		liquidity() { return this.earlyWarning?.liquidity || {}; },
		currentLiquidity() { return this.liquidity.current_liquidity || {}; },
		periodFlow() { return this.liquidity.period_flow || {}; },
		hasLiquidity() { return Object.keys(this.currentLiquidity).length > 0 || Object.keys(this.periodFlow).length > 0; },
		cashUnavailableReason() { return this.currentLiquidity.cash_bank_available === false ? this.currentLiquidity.cash_bank_unavailable_reason || "Cash & Bank closing balance is withheld for this scope." : ""; },
		liquidityMetrics() {
			return [
				{ label: "Cash & Bank Balance", value: this.currentLiquidity.cash_bank_balance, datatype: "Currency", available: this.currentLiquidity.cash_bank_available !== false, note: "Current closing balance" },
				{ label: "Receivables Due", value: this.currentLiquidity.receivables_due_within_horizon, datatype: "Currency", note: "Current outstanding due within horizon" },
				{ label: "Supplier Obligations Due", value: this.currentLiquidity.supplier_obligations_due_within_horizon, datatype: "Currency", note: "Current outstanding due within horizon" },
				{ label: "Immediate Coverage", value: this.currentLiquidity.immediate_obligation_coverage_ratio, datatype: "Float", suffix: "×", note: "Cash ÷ obligations due" },
				{ label: "Indicative Coverage", value: this.currentLiquidity.indicative_coverage_ratio_including_due_receivables, datatype: "Float", suffix: "×", note: "Cash + due receivables ÷ obligations due" },
				{ label: "Indicative Liquidity Gap", value: this.currentLiquidity.indicative_liquidity_gap, datatype: "Currency", note: "Management indicator, not forecast" },
				{ label: "Money In", value: this.periodFlow.money_in, datatype: "Currency", note: "Selected-period movement" },
				{ label: "Money Out", value: this.periodFlow.money_out, datatype: "Currency", note: "Selected-period movement" },
				{ label: "Net Cash Movement", value: this.periodFlow.net_cash_movement, datatype: "Currency", note: "Selected-period movement, not balance" },
			];
		},
		availablePositionCards() { return (this.position.current_position || []).filter((card) => card.available !== false); },
		unavailablePositionCards() { return (this.position.current_position || []).filter((card) => card.available === false); },
		availablePeriodCards() { return (this.position.selected_period || []).filter((card) => card.available !== false); },
	},
	methods: {
		formatMetric(metric) {
			if (metric.available === false || metric.value === null || metric.value === undefined) return "—";
			const formatted = this.formatValue(metric.value, metric.datatype);
			return metric.suffix ? `${formatted}${metric.suffix}` : formatted;
		},
		formatValue(value, datatype) { try { return frappe.format(value, { fieldtype: datatype || "Data" }); } catch (_error) { return value ?? "—"; } },
	},
};
</script>

<style scoped>
.financial-overview, .overview-section, .snapshot-group { display: grid; gap: 12px; }
.overview-section { padding: 14px; border: 1px solid var(--edge-border); border-radius: 8px; background: var(--edge-surface); }
.overview-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 14px; }
.overview-heading span { display: grid; gap: 4px; }
.overview-heading small, .metric-card small, .overview-empty, .overview-note { color: var(--edge-text-muted); font-size: 12px; }
.metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 9px; }
.metric-card { display: grid; gap: 4px; padding: 10px 12px; border: 1px solid var(--edge-border); border-radius: 7px; background: var(--edge-surface-soft, var(--edge-surface)); }
.metric-card span { color: var(--edge-text-muted); font-size: 12px; }
.overview-note { padding: 10px 12px; border: 1px solid var(--edge-border); border-radius: 7px; }
.overview-note--danger { border-color: var(--red-300, var(--edge-border)); }
@media (max-width: 900px) { .metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 640px) { .metric-grid { grid-template-columns: 1fr; } .overview-heading { display: grid; } }
</style>
