<template>
	<EdgeModal
		:open="open"
		:title="`Complete ${label}`"
		subtitle="Continue the saved draft through the workflow actions currently permitted for you."
		size="lg"
		@close="requestClose"
	>
		<div class="guided-workflow">
			<EdgeLoadingState v-if="loading" :message="`Reviewing ${label}...`" />
			<div v-else-if="error" class="workflow-error" role="alert">{{ error }}</div>
			<template v-else-if="readiness">
				<div class="workflow-summary">
					<div>
						<span>Document</span>
						<strong>{{ document?.name }}</strong>
					</div>
					<div>
						<span>State</span>
						<strong>{{ readiness.current_state || (readiness.docstatus === 0 ? "Draft" : "Submitted") }}</strong>
					</div>
					<div>
						<span>Workflow</span>
						<strong>{{ readiness.workflow || "Normal document process" }}</strong>
					</div>
				</div>

				<div :class="['workflow-message', readiness.requires_action ? 'needs-action' : 'complete']">
					<strong>{{ readiness.requires_action ? "Next action required" : "Current step complete" }}</strong>
					<p>{{ readiness.message }}</p>
				</div>

				<label v-if="actions.length" class="workflow-remarks">
					<span>Remarks <small>Required when rejecting; optional otherwise.</small></span>
					<textarea v-model="remarks" class="form-control" rows="3" placeholder="Optional workflow note"></textarea>
				</label>

				<div v-if="actionError" class="workflow-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="workflow-footer">
				<button
					v-if="canUseNativeDesk && document?.name"
					type="button"
					class="edge-button edge-button--secondary"
					:disabled="busy"
					@click="openAdvanced"
				>
					Advanced: Open in ERPNext
				</button>
				<div class="workflow-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">
						Close
					</button>
					<button
						v-for="action in actions"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy"
						@click="applyAction(action.action)"
					>
						{{ busy ? "Working..." : action.action }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const READINESS_METHOD = "retailedge.workflow_readiness.get_document_workflow_readiness";
const ACTION_METHOD = "retailedge.workflow_actions.apply_document_workflow_action";

function runtimeComponents() {
	const runtime = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
	return runtime?.components || runtime || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?._server_messages || fallback;
}

export default {
	name: "GuidedWorkflowCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
	},
	props: {
		open: { type: Boolean, default: false },
		document: { type: Object, default: null },
		label: { type: String, default: "Document" },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["close", "changed", "completed"],
	data() {
		return {
			readiness: null,
			loading: false,
			busy: false,
			error: "",
			actionError: "",
			remarks: "",
		};
	},
	computed: {
		actions() {
			return this.readiness?.available_actions || [];
		},
	},
	watch: {
		open: {
			immediate: true,
			handler(value) {
				if (value) this.loadReadiness();
			},
		},
		document: {
			deep: true,
			handler() {
				if (this.open) this.loadReadiness();
			},
		},
	},
	methods: {
		async loadReadiness() {
			if (!this.document?.doctype || !this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.readiness = await callMethod(READINESS_METHOD, {
					doctype: this.document.doctype,
					name: this.document.name,
				});
			} catch (error) {
				this.readiness = null;
				this.error = errorMessage(error, `Unable to review this ${this.label}.`);
			} finally {
				this.loading = false;
			}
		},
		async applyAction(action) {
			if (!action || !this.readiness || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(ACTION_METHOD, {
					doctype: this.document.doctype,
					name: this.document.name,
					action,
					expected_modified: this.readiness.modified || "",
					expected_state: this.readiness.current_state || "",
					remarks: this.remarks || "",
				});
				this.$emit("changed", result);
				this.remarks = "";
				const next = result?.workflow_readiness || {};
				this.readiness = {
					...next,
					doctype: result?.doctype || this.document.doctype,
					name: result?.name || this.document.name,
					modified: result?.modified || "",
				};
				if (next?.requires_action === false) {
					this.$emit("completed", result);
				}
			} catch (error) {
				this.actionError = errorMessage(error, `Unable to continue this ${this.label}.`);
				await this.loadReadiness();
			} finally {
				this.busy = false;
			}
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.document?.doctype || !this.document?.name) return;
			const slug = frappe.router.slug(this.document.doctype);
			window.open(
				`/app/${slug}/${encodeURIComponent(this.document.name)}`,
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
.guided-workflow { display: grid; gap: 1rem; min-height: 10rem; }
.workflow-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .7rem; }
.workflow-summary > div { display: grid; gap: .2rem; padding: .7rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.workflow-summary span, .workflow-remarks span { font-size: .78rem; color: var(--text-muted); }
.workflow-message, .workflow-error { padding: .8rem; border-radius: .6rem; }
.workflow-message p { margin: .35rem 0 0; }
.workflow-message.needs-action { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.workflow-message.complete { background: var(--green-50,#f0fdf4); border: 1px solid var(--green-200,#bbf7d0); }
.workflow-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.workflow-remarks { display: grid; gap: .4rem; }
.workflow-remarks small { font-weight: 400; }
.workflow-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.workflow-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) {
	.workflow-summary { grid-template-columns: 1fr; }
	.workflow-footer { align-items: stretch; flex-direction: column; }
	.workflow-actions { justify-content: flex-start; }
}
</style>
