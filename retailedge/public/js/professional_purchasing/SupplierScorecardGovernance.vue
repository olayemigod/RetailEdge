<template>
	<section class="edge-panel supplier-scorecard-panel">
		<div class="scorecard-heading">
			<div>
				<span class="scorecard-kicker">Supplier governance</span>
				<h3>Supplier Scorecard &amp; Governance</h3>
				<p>Review ERPNext's native supplier score and effective RFQ / Purchase Order governance without recalculating, refreshing or changing the scorecard from RetailEdge.</p>
			</div>
			<div class="scorecard-actions">
				<button v-if="capability.can_read_scorecard" type="button" class="edge-button edge-button--secondary" @click="openScorecardList">Scorecards</button>
				<button v-if="capability.can_create_scorecard && supplier && !summary.scorecard_exists" type="button" class="edge-button edge-button--primary" @click="newScorecard">New Native Scorecard</button>
			</div>
		</div>

		<div v-if="!capability.can_read_scorecard" class="scorecard-permission-note">
			<strong>Native ERPNext permission required.</strong>
			<span>Supplier Scorecard is available here only to users who already have ERPNext permission to read it. RetailEdge does not broaden that access.</span>
		</div>

		<EdgeEmptyState
			v-else-if="!supplier"
			title="Select a Supplier"
			description="Use the Supplier filter above to load that supplier's native ERPNext scorecard and effective purchasing governance."
		/>

		<p v-else-if="loading" class="scorecard-loading">Loading native ERPNext supplier governance…</p>

		<div v-else-if="error" class="scorecard-feedback scorecard-feedback--error">
			<strong>Supplier governance needs attention</strong>
			<span>{{ error }}</span>
			<button type="button" class="edge-small-button" @click="loadSummary">Retry</button>
		</div>

		<div v-else-if="summary.supplier" class="scorecard-content">
			<div class="scorecard-supplier-row">
				<div>
					<span>Supplier</span>
					<strong>{{ summary.supplier_name || summary.supplier }}</strong>
					<small>{{ summary.supplier }}</small>
				</div>
				<button v-if="summary.scorecard_exists" type="button" class="edge-button edge-button--secondary" @click="openScorecard">Open Native Scorecard</button>
			</div>

			<div v-if="summary.scorecard_exists && summary.scorecard" class="scorecard-metrics">
				<article><span>Supplier Score</span><strong>{{ formatScore(summary.scorecard.supplier_score) }}</strong></article>
				<article><span>Standing</span><strong>{{ summary.scorecard.status || "Unknown" }}</strong></article>
				<article><span>Evaluation Period</span><strong>{{ summary.scorecard.period || "—" }}</strong></article>
			</div>

			<div v-else class="scorecard-empty">
				<strong>No native Supplier Scorecard exists for this supplier.</strong>
				<span v-if="capability.can_create_scorecard">Use New Native Scorecard to continue configuration in ERPNext. No scorecard is created automatically.</span>
				<span v-else>Creating a scorecard requires ERPNext's native create permission.</span>
			</div>

			<div class="governance-grid">
				<article>
					<span>Request for Quotations</span>
					<strong>{{ governanceState("rfq") }}</strong>
					<small>{{ governanceDescription("rfq") }}</small>
				</article>
				<article>
					<span>Purchase Orders</span>
					<strong>{{ governanceState("po") }}</strong>
					<small>{{ governanceDescription("po") }}</small>
				</article>
			</div>

			<div v-if="capability.can_read_periods && summary.periods && summary.periods.length" class="scorecard-periods">
				<div class="period-heading">
					<strong>Recent evaluated periods</strong>
					<span>Latest {{ summary.period_count }} of up to {{ summary.periods_bounded_to }} permitted submitted periods.</span>
				</div>
				<div class="period-table-wrap">
					<table class="period-table">
						<thead><tr><th>Period</th><th>Start</th><th>End</th><th>Score</th></tr></thead>
						<tbody>
							<tr v-for="period in summary.periods" :key="period.name">
								<td>{{ period.name }}</td>
								<td>{{ formatDate(period.start_date) }}</td>
								<td>{{ formatDate(period.end_date) }}</td>
								<td>{{ formatScore(period.total_score) }}</td>
							</tr>
						</tbody>
					</table>
				</div>
			</div>

			<p class="scorecard-safety">ERPNext standings remain authoritative. A standing may warn or prevent new RFQs and Purchase Orders. Change criteria, standings or actions only on the native ERPNext Supplier Scorecard with appropriate System Manager access.</p>
		</div>
	</section>
</template>

<script>
const CAPABILITY_METHOD = "retailedge.supplier_scorecard_governance.get_supplier_scorecard_capability";
const SUMMARY_METHOD = "retailedge.supplier_scorecard_governance.get_supplier_scorecard_summary";

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response?.message ?? response),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc_type || error?._server_messages || fallback;
}

export default {
	name: "SupplierScorecardGovernance",
	components: {
		EdgeEmptyState: runtimeComponents().EdgeEmptyState,
	},
	props: {
		company: { type: String, default: "" },
		branch: { type: String, default: "" },
		supplier: { type: String, default: "" },
	},
	data() {
		return {
			capability: {
				can_read_scorecard: false,
				can_create_scorecard: false,
				can_read_periods: false,
			},
			summary: {},
			loading: false,
			error: "",
		};
	},
	watch: {
		company() { this.resetAndLoad(); },
		branch() { this.resetAndLoad(); },
		supplier() { this.resetAndLoad(); },
	},
	async mounted() {
		try {
			this.capability = { ...this.capability, ...(await callMethod(CAPABILITY_METHOD) || {}) };
			if (this.capability.can_read_scorecard && this.supplier) await this.loadSummary();
		} catch (error) {
			this.error = errorMessage(error, "Supplier Scorecard capability could not be loaded.");
		}
	},
	methods: {
		async resetAndLoad() {
			this.summary = {};
			this.error = "";
			if (this.capability.can_read_scorecard && this.supplier) await this.loadSummary();
		},
		async loadSummary() {
			if (!this.capability.can_read_scorecard || !this.supplier || this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				this.summary = await callMethod(SUMMARY_METHOD, {
					supplier: this.supplier,
					company: this.company || null,
					branch: this.branch || null,
				}) || {};
			} catch (error) {
				this.summary = {};
				this.error = errorMessage(error, "ERPNext could not load this Supplier Scorecard.");
			} finally {
				this.loading = false;
			}
		},
		governanceState(kind) {
			const governance = this.summary.governance || {};
			if (kind === "rfq") {
				if (governance.prevent_rfqs) return "Prevented";
				if (governance.warn_rfqs) return "Warning";
				return "Allowed";
			}
			if (governance.prevent_pos) return "Prevented";
			if (governance.warn_pos) return "Warning";
			return "Allowed";
		},
		governanceDescription(kind) {
			const state = this.governanceState(kind);
			if (state === "Prevented") return `ERPNext currently prevents new ${kind === "rfq" ? "RFQs" : "Purchase Orders"} for this supplier.`;
			if (state === "Warning") return `ERPNext currently warns users before new ${kind === "rfq" ? "RFQs" : "Purchase Orders"}.`;
			return `ERPNext currently allows new ${kind === "rfq" ? "RFQs" : "Purchase Orders"} without a scorecard warning.`;
		},
		openScorecard() {
			if (this.summary.scorecard?.name) frappe.set_route("Form", "Supplier Scorecard", this.summary.scorecard.name);
		},
		openScorecardList() {
			frappe.set_route("List", "Supplier Scorecard");
		},
		newScorecard() {
			if (this.capability.can_create_scorecard && this.supplier && !this.summary.scorecard_exists) {
				frappe.new_doc("Supplier Scorecard", { supplier: this.supplier });
			}
		},
		formatScore(value) {
			if (value === null || value === undefined || value === "") return "—";
			const number = Number(value);
			return Number.isFinite(number) ? `${number.toFixed(1).replace(/\.0$/, "")}%` : String(value);
		},
		formatDate(value) {
			if (!value) return "—";
			try { return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0]; }
			catch (_error) { return String(value); }
		},
	},
};
</script>

<style scoped>
.supplier-scorecard-panel { display:grid; gap:16px; padding:18px; }
.scorecard-heading { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.scorecard-heading h3 { margin:4px 0 6px; }
.scorecard-heading p,.scorecard-safety { margin:0; max-width:860px; opacity:.78; line-height:1.5; }
.scorecard-kicker { font-size:.78rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; opacity:.72; }
.scorecard-actions { display:flex; gap:8px; flex-wrap:wrap; }
.scorecard-permission-note,.scorecard-feedback,.scorecard-empty { display:grid; gap:4px; padding:13px 14px; border:1px solid var(--edge-border-subtle,var(--border-color)); border-radius:10px; }
.scorecard-feedback--error { border-color:var(--edge-color-danger,var(--red-400)); }
.scorecard-loading { margin:0; opacity:.72; }
.scorecard-content { display:grid; gap:14px; }
.scorecard-supplier-row { display:flex; justify-content:space-between; align-items:center; gap:14px; }
.scorecard-supplier-row > div { display:grid; gap:2px; }
.scorecard-supplier-row span,.scorecard-metrics span,.governance-grid span { font-size:.78rem; opacity:.68; }
.scorecard-supplier-row small,.governance-grid small,.period-heading span { opacity:.68; }
.scorecard-metrics,.governance-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.scorecard-metrics article,.governance-grid article { display:grid; gap:4px; padding:12px; border:1px solid var(--edge-border-subtle,var(--border-color)); border-radius:10px; }
.governance-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
.scorecard-periods { display:grid; gap:10px; }
.period-heading { display:flex; justify-content:space-between; gap:12px; align-items:baseline; }
.period-table-wrap { overflow-x:auto; }
.period-table { width:100%; border-collapse:collapse; }
.period-table th,.period-table td { padding:9px 10px; border-bottom:1px solid var(--edge-border-subtle,var(--border-color)); text-align:left; }
.period-table th { font-size:.76rem; text-transform:uppercase; letter-spacing:.04em; opacity:.68; }
@media (max-width:800px) {
	.scorecard-heading,.scorecard-supplier-row,.period-heading { display:grid; }
	.scorecard-metrics,.governance-grid { grid-template-columns:1fr; }
}
</style>
