<template>
	<EdgeModal
		:open="open"
		:title="dialogTitle"
		subtitle="Review the saved ERPNext stock draft and complete the standard operation without leaving RetailEdge."
		size="lg"
		@close="requestClose"
	>
		<div class="stock-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing stock draft..." />
			<div v-else-if="error" class="stock-completion-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="stock-completion-summary">
					<div><span>Document</span><strong>{{ preview.name }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company || "Not set" }}</strong></div>
					<div><span>Posting Date</span><strong>{{ preview.posting_date || "Not set" }}</strong></div>
					<template v-if="preview.kind === 'transfer'">
						<div><span>Source</span><strong>{{ preview.source_warehouse || "Not set" }}</strong></div>
						<div><span>Target</span><strong>{{ preview.target_warehouse || "Not set" }}</strong></div>
						<div><span>Branch Scope</span><strong>{{ transferBranchLabel }}</strong></div>
					</template>
					<template v-else>
						<div><span>Warehouse</span><strong>{{ preview.warehouse || "Not set" }}</strong></div>
						<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
						<div><span>Mode</span><strong>Physical quantity adjustment</strong></div>
					</template>
				</div>

				<div class="stock-authority-note">
					<strong>ERPNext stock authority</strong>
					<p>
						Completion uses ERPNext native submission. RetailEdge does not write Stock Ledger,
						valuation, or accounting entries directly.
					</p>
				</div>

				<div v-if="preview.items?.length" class="stock-completion-items">
					<h4>Items</h4>
					<div v-for="(row, index) in preview.items" :key="`${row.item_code}-${index}`" class="stock-completion-item">
						<span>{{ row.item_code || "Item" }}</span>
						<span>Qty {{ row.qty }}</span>
						<span v-if="preview.kind === 'transfer'">{{ row.source_warehouse }} → {{ row.target_warehouse }}</span>
						<span v-else>{{ row.warehouse || preview.warehouse }}</span>
					</div>
					<p v-if="preview.item_count > preview.items.length" class="stock-completion-hint">
						Showing {{ preview.items.length }} of {{ preview.item_count }} items.
					</p>
				</div>

				<div v-if="preview.blockers?.length" class="stock-completion-blockers">
					<strong>Standard EdgeSuite completion is blocked</strong>
					<ul>
						<li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li>
					</ul>
				</div>

				<div v-if="preview.workflow_readiness?.source === 'frappe'" class="stock-completion-workflow">
					<div>
						<span>Frappe Workflow</span>
						<strong>{{ preview.workflow_readiness.workflow || "Active Workflow" }}</strong>
					</div>
					<p>{{ preview.workflow_readiness.message }}</p>
					<p v-if="preview.workflow_readiness.current_state">
						Current state: <strong>{{ preview.workflow_readiness.current_state }}</strong>
					</p>
				</div>

				<div v-if="actionError" class="stock-completion-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="stock-completion-footer">
				<button
					v-if="canUseNativeDesk && document?.name"
					type="button"
					class="edge-button edge-button--secondary"
					:disabled="busy"
					@click="openAdvanced"
				>
					Advanced: Open in ERPNext
				</button>
				<div class="stock-completion-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">Close</button>
					<button
						v-if="preview?.can_submit"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy"
						@click="submitDocument"
					>
						{{ busy ? "Submitting..." : submitLabel }}
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
const PREVIEW_METHOD = "retailedge.standard_stock_completion.get_standard_stock_completion_preview";
const SUBMIT_METHOD = "retailedge.standard_stock_completion.submit_standard_stock_document";
const WORKFLOW_METHOD = "retailedge.standard_stock_completion.apply_standard_stock_workflow_action";

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
	name: "StandardStockCompletionDialog",
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
		dialogTitle() {
			return this.preview?.title || (this.document?.doctype === "Stock Reconciliation" ? "Complete Stock Adjustment" : "Complete Stock Transfer");
		},
		submitLabel() {
			return this.preview?.kind === "adjustment" ? "Submit Stock Adjustment" : "Submit Stock Transfer";
		},
		transferBranchLabel() {
			if (!this.preview) return "Not set";
			const source = this.preview.source_branch || "Company-wide";
			const target = this.preview.target_branch || "Company-wide";
			return source === target ? source : `${source} → ${target}`;
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
			if (!this.document?.doctype || !this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.preview = await callMethod(PREVIEW_METHOD, {
					doctype: this.document.doctype,
					name: this.document.name,
				});
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this stock draft.");
			} finally {
				this.loading = false;
			}
		},
		async submitDocument() {
			if (!this.preview?.can_submit || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					doctype: this.preview.doctype,
					name: this.preview.name,
					expected_modified: this.preview.modified,
				});
				this.$emit("changed", result);
				this.$emit("completed", result);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this stock document.");
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
					doctype: this.preview.doctype,
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
				this.actionError = errorMessage(error, "Unable to apply this stock workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.document?.name) return;
			const slug = this.document.doctype === "Stock Reconciliation" ? "stock-reconciliation" : "stock-entry";
			window.open(`/app/${slug}/${encodeURIComponent(this.document.name)}`, "_blank", "noopener,noreferrer");
		},
		requestClose() {
			if (!this.busy) this.$emit("close");
		},
	},
};
</script>

<style scoped>
.stock-completion { display: grid; gap: 1rem; min-height: 12rem; }
.stock-completion-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.stock-completion-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.stock-completion-summary span, .stock-completion-workflow span { font-size: .78rem; color: var(--text-muted); }
.stock-authority-note { display: grid; gap: .25rem; padding: .8rem; border-radius: .6rem; background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.stock-authority-note p { margin: 0; }
.stock-completion-items { display: grid; gap: .45rem; }
.stock-completion-items h4 { margin: 0; }
.stock-completion-item { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(0,1fr); gap: .75rem; padding: .55rem .7rem; border-bottom: 1px solid var(--edge-border-color,var(--border-color)); }
.stock-completion-blockers, .stock-completion-workflow, .stock-completion-error { padding: .8rem; border-radius: .6rem; }
.stock-completion-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.stock-completion-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.stock-completion-workflow { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.stock-completion-workflow p { margin: .35rem 0 0; }
.stock-completion-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.stock-completion-hint { margin: 0; font-size: .82rem; color: var(--text-muted); }
.stock-completion-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.stock-completion-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) {
	.stock-completion-summary, .stock-completion-item { grid-template-columns: 1fr; }
	.stock-completion-footer { align-items: stretch; flex-direction: column; }
	.stock-completion-actions { justify-content: flex-start; }
}
</style>
