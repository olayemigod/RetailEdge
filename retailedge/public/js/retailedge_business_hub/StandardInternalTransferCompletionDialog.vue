<template>
	<EdgeModal
		:open="open"
		title="Complete Cash Movement"
		subtitle="Review the saved ERPNext Internal Transfer and complete it through native submission or the active Frappe Workflow."
		size="lg"
		@close="requestClose"
	>
		<div class="transfer-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing cash movement..." />
			<div v-else-if="error" class="transfer-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="transfer-summary">
					<div><span>Type</span><strong>{{ preview.transfer_kind }}</strong></div>
					<div><span>Payment Entry</span><strong>{{ preview.name }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company }}</strong></div>
					<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
					<div><span>Amount</span><strong>{{ preview.currency || "" }} {{ preview.amount }}</strong></div>
					<div><span>Status</span><strong>{{ preview.status || "Draft" }}</strong></div>
				</div>

				<div class="account-flow">
					<div>
						<span>From</span>
						<strong>{{ preview.from_account }}</strong>
						<small>{{ preview.from_account_type || "Posting account" }}</small>
					</div>
					<div class="flow-arrow">→</div>
					<div>
						<span>To</span>
						<strong>{{ preview.to_account }}</strong>
						<small>{{ preview.to_account_type || "Posting account" }}</small>
					</div>
				</div>

				<div v-if="preview.transfer_kind === 'Cash Deposit'" class="custody-note">
					<strong>Cash custody</strong>
					<p>Cashier: {{ preview.cashier || "Not set" }} · Shift: {{ preview.pos_opening_shift || "Not set" }}</p>
					<p v-if="preview.custody">
						Available shift cash now: {{ preview.currency || "" }} {{ preview.custody.available_cash }}
					</p>
					<p>Final submission rechecks cashier custody and the approved Bank Account through the existing ERPNext before-submit hook.</p>
				</div>

				<div class="authority-note">
					<strong>ERPNext posting authority</strong>
					<p>RetailEdge does not create General Ledger or Payment Ledger entries directly. Native Payment Entry submission remains authoritative.</p>
				</div>

				<div v-if="preview.blockers?.length" class="transfer-blockers">
					<strong>Standard completion is blocked</strong>
					<ul>
						<li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li>
					</ul>
				</div>

				<div v-if="preview.workflow_readiness?.source === 'frappe'" class="workflow-note">
					<div>
						<span>Frappe Workflow</span>
						<strong>{{ preview.workflow_readiness.workflow || "Active Workflow" }}</strong>
					</div>
					<p>{{ preview.workflow_readiness.message }}</p>
					<p v-if="preview.workflow_readiness.current_state">
						Current state: <strong>{{ preview.workflow_readiness.current_state }}</strong>
					</p>
				</div>

				<div v-if="actionError" class="transfer-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="transfer-footer">
				<button
					v-if="canUseNativeDesk && document?.name"
					type="button"
					class="edge-button edge-button--secondary"
					:disabled="busy"
					@click="openAdvanced"
				>
					Advanced: Open in ERPNext
				</button>
				<div class="transfer-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">Close</button>
					<button
						v-if="preview?.can_submit"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy"
						@click="submitTransfer"
					>
						{{ busy ? "Submitting..." : "Submit Transfer" }}
					</button>
					<button
						v-for="action in workflowActions"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy || !preview?.workflow_eligible"
						@click="applyWorkflow(action.action)"
					>
						{{ action.action }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.standard_internal_transfer_completion.get_standard_internal_transfer_completion_preview";
const SUBMIT_METHOD = "retailedge.standard_internal_transfer_completion.submit_standard_internal_transfer";
const WORKFLOW_METHOD = "retailedge.standard_internal_transfer_completion.apply_standard_internal_transfer_workflow_action";

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?._server_messages || fallback;
}

export default {
	name: "StandardInternalTransferCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
	},
	props: {
		open: { type: Boolean, default: false },
		document: { type: Object, default: null },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["close", "changed", "completed"],
	data() {
		return {
			preview: null,
			loading: false,
			busy: false,
			error: "",
			actionError: "",
		};
	},
	computed: {
		workflowActions() {
			return this.preview?.workflow_readiness?.available_actions || [];
		},
	},
	watch: {
		open: {
			immediate: true,
			handler(value) {
				if (value) this.loadPreview();
			},
		},
		document: {
			deep: true,
			handler() {
				if (this.open) this.loadPreview();
			},
		},
	},
	methods: {
		async loadPreview() {
			if (!this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.preview = await callMethod(PREVIEW_METHOD, { name: this.document.name });
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this cash movement.");
			} finally {
				this.loading = false;
			}
		},
		async submitTransfer() {
			if (!this.preview?.can_submit || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					name: this.preview.name,
					expected_modified: this.preview.modified,
				});
				this.$emit("changed", result);
				this.$emit("completed", result);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this cash movement.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async applyWorkflow(action) {
			if (!action || !this.preview?.workflow_eligible || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					name: this.preview.name,
					action,
					expected_modified: this.preview.modified,
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
				});
				this.$emit("changed", result);
				if (Number(result?.docstatus || 0) === 1) {
					this.$emit("completed", result);
					return;
				}
				await this.loadPreview();
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to apply the Payment Entry workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.document?.name) return;
			window.open(
				`/app/payment-entry/${encodeURIComponent(this.document.name)}`,
				"_blank",
				"noopener,noreferrer",
			);
		},
		requestClose() {
			if (!this.busy) this.$emit("close");
		},
	},
};
</script>

<style scoped>
.transfer-completion { display: grid; gap: 1rem; min-height: 12rem; }
.transfer-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.transfer-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.transfer-summary span, .account-flow span, .workflow-note span { font-size: .78rem; color: var(--text-muted); }
.account-flow { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(0,1fr); align-items: center; gap: 1rem; padding: .8rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.account-flow > div:not(.flow-arrow) { display: grid; gap: .2rem; }
.flow-arrow { font-size: 1.4rem; }
.custody-note, .authority-note, .workflow-note, .transfer-blockers, .transfer-error { padding: .8rem; border-radius: .6rem; }
.custody-note, .authority-note, .workflow-note { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.custody-note p, .authority-note p, .workflow-note p { margin: .35rem 0 0; }
.transfer-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.transfer-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.transfer-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.transfer-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.transfer-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) { .transfer-summary, .account-flow { grid-template-columns: 1fr; } .flow-arrow { transform: rotate(90deg); justify-self: start; } .transfer-footer { align-items: stretch; flex-direction: column; } .transfer-actions { justify-content: flex-start; } }
</style>
