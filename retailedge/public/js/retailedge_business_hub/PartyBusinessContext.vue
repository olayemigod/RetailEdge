<template>
	<section v-if="party" class="party-business-context" aria-live="polite">
		<div class="party-business-context__head">
			<div>
				<span class="party-business-context__kicker">{{ partyType }} context</span>
				<strong>{{ party }}</strong>
			</div>
			<small v-if="context.last_transaction_date">{{ lastTransactionLabel }} {{ formatDate(context.last_transaction_date) }}</small>
		</div>

		<div v-if="loading" class="party-business-context__state">Loading current business context…</div>
		<div v-else-if="error" class="party-business-context__state party-business-context__state--warning">{{ error }}</div>
		<div v-else-if="context.restricted" class="party-business-context__state">{{ context.reason || "Context is restricted for this account." }}</div>
		<template v-else-if="context.available">
			<div class="party-business-context__metrics">
				<article v-for="metric in context.metrics || []" :key="metric.key">
					<span>{{ metric.label }}</span>
					<strong>{{ metric.available === false ? "—" : formatMetric(metric) }}</strong>
				</article>
			</div>
			<div class="party-business-context__meta">
				<span v-if="context.open_document_count !== null && context.open_document_count !== undefined">
					{{ Number(context.open_document_count || 0).toLocaleString() }} open document{{ Number(context.open_document_count || 0) === 1 ? "" : "s" }}
				</span>
				<span v-if="context.partial">Partial balance context</span>
				<span>{{ context.helper }}</span>
			</div>
		</template>
	</section>
</template>

<script>
const METHOD = "retailedge.party_transaction_context.get_party_transaction_context";

function callMethod(args) {
	return new Promise((resolve, reject) => frappe.call({
		method: METHOD,
		args,
		type: "GET",
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

function userError(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

export default {
	name: "PartyBusinessContext",
	props: {
		partyType: { type: String, required: true },
		party: { type: String, default: "" },
		company: { type: String, default: "" },
		branch: { type: String, default: "" },
	},
	data() {
		return {
			loading: false,
			error: "",
			context: {},
			requestToken: 0,
		};
	},
	computed: {
		lastTransactionLabel() {
			return this.partyType === "Supplier" ? "Last purchase" : "Last sale";
		},
	},
	watch: {
		party() { this.loadContext(); },
		company() { this.loadContext(); },
		branch() { this.loadContext(); },
	},
	mounted() {
		this.loadContext();
	},
	methods: {
		async loadContext() {
			const token = ++this.requestToken;
			this.error = "";
			if (!this.party || !this.company) {
				this.context = {};
				this.loading = false;
				return;
			}
			this.loading = true;
			try {
				const result = await callMethod({
					party_type: this.partyType,
					party: this.party,
					company: this.company,
					branch: this.branch || "",
				});
				if (token !== this.requestToken) return;
				this.context = result || {};
			} catch (error) {
				if (token !== this.requestToken) return;
				this.context = {};
				this.error = userError(error, "Party context is unavailable for the current scope.");
			} finally {
				if (token === this.requestToken) this.loading = false;
			}
		},
		formatMetric(metric) {
			const value = Number(metric?.value || 0);
			if (String(metric?.datatype || "").toLowerCase() === "currency") {
				try {
					return window.retailedge.formatPlainValue(value, {
						fieldtype: "Currency",
						options: metric.currency || this.context.currency || "",
					});
				} catch (_error) {
					return value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
				}
			}
			return Number.isFinite(value) ? value.toLocaleString() : String(metric?.value ?? "—");
		},
		formatDate(value) {
			if (!value) return "—";
			try {
				return frappe.datetime.str_to_user(`${value} 00:00:00`).split(" ")[0];
			} catch (_error) {
				return String(value);
			}
		},
	},
};
</script>

<style scoped>
.party-business-context{display:grid;gap:.65rem;padding:.8rem;border:1px solid var(--edge-color-border,var(--edge-border,#e5e7eb));border-radius:.65rem;background:var(--edge-color-surface-muted,var(--edge-surface-muted,#f8fafc))}
.party-business-context__head{display:flex;align-items:flex-start;justify-content:space-between;gap:.75rem}
.party-business-context__head>div{display:grid;gap:.12rem}
.party-business-context__kicker,.party-business-context__head small,.party-business-context__metrics span,.party-business-context__meta{font-size:.75rem;color:var(--edge-color-ink-500,var(--edge-text-muted,#667085))}
.party-business-context__kicker{text-transform:uppercase;letter-spacing:.04em;font-weight:700}
.party-business-context__metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:.5rem}
.party-business-context__metrics article{display:grid;gap:.18rem;padding:.55rem .65rem;border:1px solid var(--edge-color-border,var(--edge-border,#e5e7eb));border-radius:.5rem;background:var(--edge-color-surface,var(--edge-surface,#fff))}
.party-business-context__metrics strong{font-size:.92rem;white-space:nowrap}
.party-business-context__meta{display:flex;gap:.65rem;flex-wrap:wrap}
.party-business-context__state{padding:.55rem;color:var(--edge-color-ink-500,var(--edge-text-muted,#667085))}
.party-business-context__state--warning{color:var(--edge-color-warning-700,#b54708)}
@media(max-width:48rem){.party-business-context__metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:30rem){.party-business-context__metrics{grid-template-columns:1fr}.party-business-context__head{flex-direction:column}}
</style>
