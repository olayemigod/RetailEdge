<template>
	<EdgeModal
		:open="open"
		title="Complete Purchase Invoice"
		subtitle="Review the saved ERPNext Purchase Invoice and complete it through native submission or the active Frappe Workflow."
		size="lg"
		@close="requestClose"
	>
		<div class="invoice-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing Purchase Invoice..." />
			<div v-else-if="error" class="invoice-completion-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="invoice-completion-summary">
					<div><span>Purchase Invoice</span><strong>{{ preview.name }}</strong></div>
					<div><span>Supplier</span><strong>{{ preview.supplier_name || preview.supplier || "Not set" }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company || "Not set" }}</strong></div>
					<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
					<div><span>Total</span><strong>{{ preview.currency || "" }} {{ preview.grand_total }}</strong></div>
					<div><span>Mode</span><strong>{{ preview.update_stock ? "Accounting + Stock" : "Accounting only" }}</strong></div>
				</div>

				<div class="invoice-accounting-note">
					<strong>ERPNext posting authority</strong>
					<p>RetailEdge does not create payable, General Ledger, Payment Ledger, Stock Ledger, valuation or outstanding entries directly. Native Purchase Invoice submission remains authoritative.</p>
				</div>

				<div v-if="preview.items?.length" class="invoice-completion-items">
					<h4>Invoice items</h4>
					<div v-for="(row, index) in preview.items" :key="`${row.item_code}-${index}`" class="invoice-completion-item">
						<span>{{ row.item_code || row.item_name || "Item" }}</span>
						<span>Qty {{ row.qty }}</span>
						<span>{{ preview.currency || "" }} {{ row.amount }}</span>
						<span v-if="preview.update_stock">{{ row.warehouse || "No Warehouse" }}</span>
					</div>
					<p v-if="preview.item_count > preview.items.length" class="invoice-completion-hint">
						Showing {{ preview.items.length }} of {{ preview.item_count }} items.
					</p>
				</div>

				<div v-if="preview.blockers?.length" class="invoice-completion-blockers">
					<strong>Standard Purchase Invoice completion is blocked</strong>
					<ul>
						<li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li>
					</ul>
				</div>

				<div v-if="preview.workflow_readiness?.source === 'frappe'" class="invoice-completion-workflow">
					<div>
						<span>Frappe Workflow</span>
						<strong>{{ preview.workflow_readiness.workflow || "Active Workflow" }}</strong>
					</div>
					<p>{{ preview.workflow_readiness.message }}</p>
					<p v-if="preview.workflow_readiness.current_state">
						Current state: <strong>{{ preview.workflow_readiness.current_state }}</strong>
					</p>
				</div>

				<div v-if="actionError" class="invoice-completion-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="invoice-completion-footer">
				<button
					v-if="canUseNativeDesk && document?.name"
					type="button"
					class="edge-button edge-button--secondary"
					:disabled="busy"
					@click="openAdvanced"
				>
					Advanced: Open in ERPNext
				</button>
				<div class="invoice-completion-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">Close</button>
					<button
						v-if="preview?.can_submit"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy"
						@click="submitDocument"
					>
						{{ busy ? "Submitting..." : "Submit Purchase Invoice" }}
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
const PREVIEW_METHOD = "retailedge.standard_purchase_invoice_completion.get_standard_purchase_invoice_completion_preview";
const SUBMIT_METHOD = "retailedge.standard_purchase_invoice_completion.submit_standard_purchase_invoice";
const WORKFLOW_METHOD = "retailedge.standard_purchase_invoice_completion.apply_standard_purchase_invoice_workflow_action";

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
	name: "StandardPurchaseInvoiceCompletionDialog",
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
				this.error = errorMessage(error, "Unable to review this Purchase Invoice.");
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
					name: this.preview.name,
					expected_modified: this.preview.modified,
				});
				this.$emit("changed", result);
				this.$emit("completed", result);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this Purchase Invoice.");
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
				this.actionError = errorMessage(error, "Unable to apply the Purchase Invoice workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.document?.name) return;
			window.open(
				`/app/purchase-invoice/${encodeURIComponent(this.document.name)}`,
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
.invoice-completion { display: grid; gap: 1rem; min-height: 12rem; }
.invoice-completion-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.invoice-completion-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.invoice-completion-summary span, .invoice-completion-workflow span { font-size: .78rem; color: var(--text-muted); }
.invoice-accounting-note { display: grid; gap: .25rem; padding: .8rem; border-radius: .6rem; background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.invoice-accounting-note p { margin: 0; }
.invoice-completion-items { display: grid; gap: .45rem; }
.invoice-completion-items h4 { margin: 0; }
.invoice-completion-item { display: grid; grid-template-columns: minmax(0,1fr) auto auto minmax(0,auto); gap: .75rem; padding: .55rem .7rem; border-bottom: 1px solid var(--edge-border-color,var(--border-color)); }
.invoice-completion-blockers, .invoice-completion-workflow, .invoice-completion-error { padding: .8rem; border-radius: .6rem; }
.invoice-completion-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.invoice-completion-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.invoice-completion-workflow { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.invoice-completion-workflow p { margin: .35rem 0 0; }
.invoice-completion-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.invoice-completion-hint { margin: 0; font-size: .82rem; color: var(--text-muted); }
.invoice-completion-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.invoice-completion-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) { .invoice-completion-summary { grid-template-columns: 1fr; } .invoice-completion-item { grid-template-columns: 1fr; } .invoice-completion-footer { align-items: stretch; flex-direction: column; } .invoice-completion-actions { justify-content: flex-start; } }
</style>
