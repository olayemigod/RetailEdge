<template>
	<section class="edge-panel unfinished-sales" aria-label="Unfinished sales">
		<div class="unfinished-sales__heading">
			<div>
				<span class="unfinished-sales__kicker">Unfinished sales</span>
				<h3>Continue a saved sale</h3>
				<p>Saved drafts remain available after the browser is closed. Only your own drafts for the current Company and Branch are shown.</p>
			</div>
			<button type="button" class="edge-button" :disabled="loading" @click="$emit('refresh')">
				{{ loading ? "Refreshing..." : "Refresh" }}
			</button>
		</div>

		<div v-if="error" class="unfinished-sales__error" role="alert">{{ error }}</div>
		<div v-else-if="loading && !drafts.length" class="unfinished-sales__empty">Checking for unfinished sales...</div>
		<div v-else-if="!drafts.length" class="unfinished-sales__empty">No unfinished sales for you in this Branch.</div>
		<div v-else class="unfinished-sales__list">
			<article v-for="draft in drafts" :key="draft.name" class="unfinished-sales__row">
				<div class="unfinished-sales__identity">
					<strong>{{ draft.name }}</strong>
					<span>{{ draft.customer_name || draft.customer || "Customer not set" }}</span>
					<small>{{ draft.item_count || 0 }} item{{ Number(draft.item_count || 0) === 1 ? "" : "s" }} · {{ draft.posting_date || "No posting date" }}</small>
				</div>
				<div class="unfinished-sales__amount">
					<strong>{{ money(draft) }}</strong>
					<small>Last saved {{ draft.modified || "recently" }}</small>
				</div>
				<div class="unfinished-sales__actions">
					<button type="button" class="edge-button" @click="$emit('review', draft.name)">Review</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="!draft.can_edit" @click="$emit('resume', draft.name)">
						Resume Sale
					</button>
				</div>
			</article>
		</div>
	</section>
</template>

<script>
export default {
	name: "UnfinishedSalesPanel",
	props: {
		drafts: { type: Array, default: () => [] },
		loading: { type: Boolean, default: false },
		error: { type: String, default: "" },
	},
	emits: ["refresh", "resume", "review"],
	methods: {
		money(draft) {
			const currency = String(draft?.currency || "NGN").trim() || "NGN";
			return `${currency} ${Number(draft?.grand_total || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
		},
	},
};
</script>

<style scoped>
.unfinished-sales {
	display: grid;
	gap: 14px;
	padding: 18px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 12px;
	background: var(--edge-color-surface, #fff);
}
.unfinished-sales__heading,
.unfinished-sales__row,
.unfinished-sales__actions {
	display: flex;
	align-items: center;
	gap: 12px;
}
.unfinished-sales__heading {
	justify-content: space-between;
	align-items: flex-start;
}
.unfinished-sales__heading h3 {
	margin: 3px 0 4px;
}
.unfinished-sales__heading p,
.unfinished-sales__identity span,
.unfinished-sales__identity small,
.unfinished-sales__amount small,
.unfinished-sales__empty {
	margin: 0;
	color: var(--edge-color-ink-500, #667085);
}
.unfinished-sales__kicker {
	font-size: .72rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .07em;
	color: var(--edge-color-brand-600, #2563eb);
}
.unfinished-sales__list {
	display: grid;
	gap: 8px;
}
.unfinished-sales__row {
	justify-content: space-between;
	padding: 12px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 9px;
	background: var(--edge-color-surface-muted, #f8fafc);
}
.unfinished-sales__identity,
.unfinished-sales__amount {
	display: grid;
	gap: 2px;
}
.unfinished-sales__identity {
	min-width: 0;
	flex: 1 1 auto;
}
.unfinished-sales__amount {
	text-align: right;
	flex: 0 0 auto;
}
.unfinished-sales__actions {
	flex: 0 0 auto;
}
.unfinished-sales__error {
	padding: 10px 12px;
	border: 1px solid var(--edge-color-danger, #d92d20);
	border-radius: 8px;
	color: var(--edge-color-danger, #b42318);
	background: var(--edge-color-danger-subtle, #fef3f2);
}
:global(:root[data-edge-appearance="dark"]) .unfinished-sales,
:global(:root[data-edge-appearance="dark"]) .unfinished-sales__row {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
@media (max-width: 760px) {
	.unfinished-sales__heading,
	.unfinished-sales__row {
		align-items: stretch;
		flex-direction: column;
	}
	.unfinished-sales__amount {
		text-align: left;
	}
	.unfinished-sales__actions {
		justify-content: flex-start;
		flex-wrap: wrap;
	}
}
</style>
