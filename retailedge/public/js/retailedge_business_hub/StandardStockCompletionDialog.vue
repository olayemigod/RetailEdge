<template>
	<EdgeModal
		:open="open"
		:title="dialogTitle"
		subtitle="Review the saved ERPNext stock draft and complete the standard operation without leaving this workspace."
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
						Completion uses ERPNext native submission. This workflow does not write Stock Ledger,
						valuation, or accounting entries directly.
					</p>
				</div>

				<section v-if="preview.can_edit" class="stock-draft-editor">
					<div class="stock-editor-heading">
						<div>
							<strong>Edit draft items</strong>
							<p>Company, Branch, purpose and warehouse scope stay fixed. ERPNext revalidates every quantity and item when this draft is saved.</p>
						</div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !draftDirty || !draftValid" @click="saveDraftChanges">{{ busy ? "Saving..." : "Save Draft Changes" }}</button>
					</div>
					<div class="stock-edit-items">
						<div class="stock-edit-item stock-edit-item--head"><span>Item</span><span>Qty</span><span></span></div>
						<div v-for="(row, index) in draftItems" :key="row.name || index" class="stock-edit-item">
							<span>{{ row.item_code || row.item_name || "Item" }}</span>
							<EdgeInput v-model="row.qty" :id="`stock-item-qty-${index}`" label="Qty" type="number" :min="preview.kind === 'adjustment' ? 0 : 0.000001" step="any" :disabled="busy" />
							<button type="button" class="edge-button edge-button--secondary" :disabled="busy || draftItems.length <= 1" @click="removeDraftItem(index)">Remove</button>
						</div>
					</div>
					<EdgeChildTable
						:field="{ label: 'Additional Items', description: preview.kind === 'adjustment' ? 'Add more items to this physical count.' : 'Add more items to this stock transfer.' }"
						:rows="newItems"
						:columns="newItemColumns"
						:addLabel="'Add Item'"
						:linkSearcher="searchLineLink"
						:newRowsFirst="true"
						@update:rows="newItems = $event"
					/>
				</section>

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
					<strong>Standard completion is blocked</strong>
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
						:disabled="busy || draftDirty"
						@click="submitDocument"
					>
						{{ busy ? "Submitting..." : submitLabel }}
					</button>
					<button
						v-for="action in workflowActions"
						:key="action.action"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy || draftDirty || !preview?.workflow_eligible"
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
const UPDATE_DRAFT_METHOD = "retailedge.standard_stock_completion.update_standard_stock_document_draft";
const TRANSFER_SEARCH_METHOD = "retailedge.guided_stock_transfer.search_simple_stock_transfer_options";
const ADJUSTMENT_SEARCH_METHOD = "retailedge.guided_stock_adjustment.search_simple_stock_adjustment_options";
const SUBMIT_METHOD = "retailedge.standard_stock_completion.submit_standard_stock_document";
const WORKFLOW_METHOD = "retailedge.standard_stock_completion.apply_standard_stock_workflow_action";

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, type, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function errorMessage(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

export default {
	name: "StandardStockCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
		EdgeInput: runtimeComponents().EdgeInput,
		EdgeChildTable: runtimeComponents().EdgeChildTable,
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
			draftItems: [],
			newItems: [],
			newItemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search stock item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
			],
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
		draftDirty() {
			if (!this.preview?.can_edit) return false;
			if (this.newItems.some((row) => row?.item_code)) return true;
			const original = this.preview.editable_items || [];
			if (this.draftItems.length !== original.length) return true;
			return this.draftItems.some((row, index) => Number(row.qty ?? 0) !== Number(original[index]?.qty ?? 0));
		},
		draftValid() {
			if (!this.draftItems.length) return false;
			const validQty = (row) => this.preview?.kind === "adjustment" ? Number(row.qty) >= 0 : Number(row.qty) > 0;
			return this.draftItems.every(validQty) && this.newItems.filter((row) => row?.item_code).every(validQty);
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
		syncDraftEditor(preview) {
			this.draftItems = (preview?.editable_items || []).map((row) => ({ ...row }));
			this.newItems = [];
		},
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
				if (Number(this.preview?.docstatus || 0) === 0) this.syncDraftEditor(this.preview);
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this stock draft.");
			} finally {
				this.loading = false;
			}
		},
		removeDraftItem(index) {
			if (this.busy || this.draftItems.length <= 1) return;
			this.draftItems.splice(index, 1);
		},
		async searchLineLink(column, query) {
			if (column?.fieldname !== "item_code" || !this.preview) return [];
			const method = this.preview.kind === "adjustment" ? ADJUSTMENT_SEARCH_METHOD : TRANSFER_SEARCH_METHOD;
			const values = this.preview.kind === "adjustment"
				? { company: this.preview.company, branch: this.preview.branch || "", warehouse: this.preview.warehouse || "" }
				: { company: this.preview.company, source_branch: this.preview.source_branch || "", target_branch: this.preview.target_branch || "", source_warehouse: this.preview.source_warehouse || "", target_warehouse: this.preview.target_warehouse || "" };
			const rows = await callMethod(method, { fieldname: "item_code", txt: query || "", values });
			return Array.isArray(rows) ? rows : [];
		},
		async saveDraftChanges() {
			if (!this.preview?.can_edit || !this.draftDirty || !this.draftValid || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(UPDATE_DRAFT_METHOD, {
					doctype: this.preview.doctype,
					name: this.preview.name,
					expected_modified: this.preview.modified,
					items: [
						...this.draftItems.map((row) => ({ name: row.name, item_code: row.item_code, qty: Number(row.qty) })),
						...this.newItems.filter((row) => row?.item_code).map((row) => ({ item_code: row.item_code, qty: Number(row.qty) })),
					],
				}, "POST");
				this.preview = result;
				this.syncDraftEditor(result);
				this.$emit("changed", result);
				frappe.show_alert?.({ message: __("Draft stock document updated"), indicator: "green" });
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to update this stock draft.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async submitDocument() {
			if (!this.preview?.can_submit || this.busy || this.draftDirty) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					doctype: this.preview.doctype,
					name: this.preview.name,
					expected_modified: this.preview.modified,
				}, "POST");
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
			if (!action || !this.preview?.workflow_eligible || this.busy || this.draftDirty) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					doctype: this.preview.doctype,
					name: this.preview.name,
					action,
					expected_modified: this.preview.modified,
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
				}, "POST");
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
			if (this.busy) return;
			if (this.preview?.can_edit && this.draftDirty) {
				frappe.confirm(__("Discard unsaved stock draft changes?"), () => this.$emit("close"));
				return;
			}
			this.$emit("close");
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
.stock-draft-editor { display:grid; gap:.75rem; padding:.8rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.6rem; }
.stock-editor-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
.stock-editor-heading p { margin:.2rem 0 0; color:var(--text-muted); font-size:.82rem; }
.stock-edit-items { display:grid; gap:.35rem; }
.stock-edit-item { display:grid; grid-template-columns:minmax(0,1fr) 9rem auto; gap:.6rem; align-items:center; padding:.4rem 0; border-bottom:1px solid var(--edge-border-color,var(--border-color)); }
.stock-edit-item--head { color:var(--text-muted); font-size:.75rem; font-weight:700; }
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
	.stock-completion-summary, .stock-completion-item, .stock-edit-item { grid-template-columns: 1fr; }
	.stock-editor-heading { flex-direction:column; align-items:stretch; }
	.stock-completion-footer { align-items: stretch; flex-direction: column; }
	.stock-completion-actions { justify-content: flex-start; }
}
</style>
