<template>
	<section
		v-if="readiness.applicable && !readiness.ready"
		class="readiness-guidance"
		role="status"
		aria-live="polite"
		data-retailedge-readiness-guidance="1"
	>
		<div class="readiness-guidance__body">
			<span class="readiness-guidance__kicker">Access setup incomplete</span>
			<strong>{{ readiness.message || fallbackMessage }}</strong>
			<p>Business transactions stay unavailable until an administrator completes your RetailEdge Company and Branch access setup.</p>
		</div>
		<button
			v-if="readiness.can_repair"
			type="button"
			class="edge-button edge-button--secondary"
			@click="openRepair"
		>
			Review User Access
		</button>
	</section>
</template>

<script>
const READINESS_METHOD = "retailedge.user_readiness.get_my_retailedge_user_readiness";

export default {
	name: "RetailEdgeUserReadinessNotice",
	data() {
		return {
			readiness: {
				applicable: false,
				ready: true,
				message: "",
				can_repair: false,
			},
			fallbackMessage: "Your RetailEdge access setup is not complete. Ask an administrator to assign your Company and Branch.",
		};
	},
	mounted() {
		this.refreshReadiness();
	},
	methods: {
		refreshReadiness() {
			if (!window.frappe?.call) return Promise.resolve();
			return new Promise((resolve) => {
				frappe.call({
					method: READINESS_METHOD,
					type: "GET",
					callback: (response) => {
						this.readiness = {
							...this.readiness,
							...(response.message || {}),
						};
						resolve(this.readiness);
					},
					error: () => resolve(this.readiness),
				});
			});
		},
		openRepair() {
			frappe.set_route("branch-assignments");
		},
	},
};
</script>

<style scoped>
.readiness-guidance {
	display: flex;
	align-items: flex-start;
	justify-content: space-between;
	gap: 1rem;
	margin-bottom: 1rem;
	padding: 1rem 1.1rem;
	border: 1px solid var(--orange-300, var(--edge-border-color, var(--border-color)));
	border-radius: 0.75rem;
	background: var(--edge-surface, var(--card-bg));
	color: var(--text-color);
}
.readiness-guidance__body {
	display: grid;
	gap: 0.3rem;
}
.readiness-guidance__kicker {
	font-size: 0.78rem;
	font-weight: 700;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--text-muted);
}
.readiness-guidance p {
	margin: 0;
	color: var(--text-muted);
}
@media (max-width: 760px) {
	.readiness-guidance {
		flex-direction: column;
	}
}
</style>
