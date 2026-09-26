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

				<div v-if="preview.source_name" class="invoice-source-note">
					<span>Source</span>
					<strong>{{ preview.source_type }} {{ preview.source_name }}</strong>
				</div>

				<section v-if="preview.can_edit && !completedResult" class="invoice-draft-editor">
					<div class="invoice-editor-heading">
						<div>
							<strong>Edit draft before completion</strong>
							<p>Company, Supplier, Branch, stock mode, warehouses and PO/Receipt source links remain protected. ERPNext recalculates the draft when saved.</p>
						</div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !draftDirty || !draftValid" @click="saveDraftChanges">{{ busy ? "Saving..." : "Save Draft Changes" }}</button>
					</div>
					<div class="invoice-editor-grid">
						<EdgeInput v-model="draftPostingDate" id="purchase-invoice-posting-date" label="Posting Date" type="date" :disabled="busy" required />
						<EdgeInput v-model="draftDueDate" id="purchase-invoice-due-date" label="Due Date" type="date" :min="draftPostingDate || undefined" :disabled="busy" />
						<EdgeInput v-model="draftBillNo" id="purchase-invoice-bill-no" label="Supplier Bill No" type="text" :disabled="busy" />
						<EdgeInput v-model="draftBillDate" id="purchase-invoice-bill-date" label="Supplier Bill Date" type="date" :disabled="busy" />
						<EdgeInput v-model="draftRemarks" id="purchase-invoice-remarks" label="Remarks" type="text" :disabled="busy" />
					</div>
					<div v-if="draftItems.length" class="invoice-edit-items">
						<div class="invoice-edit-item invoice-edit-item--head"><span>Item</span><span>Qty</span><span>Rate</span><span>Amount</span><span>Action</span></div>
						<div v-for="(row, index) in draftItems" :key="row.name || index" class="invoice-edit-item">
							<span>{{ row.item_code || row.item_name || "Item" }}<small v-if="row.source_locked">Source-linked</small></span>
							<EdgeInput v-model="row.qty" :id="`purchase-invoice-item-qty-${index}`" label="Qty" type="number" min="0.000001" step="any" :disabled="busy" />
							<EdgeInput v-model="row.rate" :id="`purchase-invoice-item-rate-${index}`" label="Rate" type="number" min="0" step="any" :disabled="busy" />
							<span>{{ preview.currency || "" }} {{ row.amount }}</span>
							<button v-if="!row.source_locked" type="button" class="edge-button edge-button--secondary" :disabled="busy || !canRemoveDraftItem(index)" @click="removeDraftItem(index)">Remove</button>
							<span v-else class="invoice-source-lock">Protected</span>
						</div>
					</div>
					<EdgeChildTable
						v-if="preview.allow_new_items"
						:field="{ label: 'Additional Items', description: 'Add products or services to this direct Purchase Invoice draft before submission.' }"
						:rows="newItems"
						:columns="newItemColumns"
						:addLabel="'Add Item'"
						:linkSearcher="searchLineLink"
						:newRowsFirst="true"
						@update:rows="updateNewItems"
					/>
					<p v-else class="invoice-completion-hint">This invoice came from {{ preview.source_type }} {{ preview.source_name }}. Add or remove source rows from the owning purchasing document, not from this completion step.</p>
				</section>

				<div class="invoice-accounting-note">
					<strong>ERPNext posting authority</strong>
					<p>This workflow does not create payable, General Ledger, Payment Ledger, Stock Ledger, valuation or outstanding entries directly. Native Purchase Invoice submission remains authoritative.</p>
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

				<div v-if="completedResult && showNextActions" class="invoice-next-actions">
					<div>
						<strong>Purchase Invoice submitted</strong>
						<p>Continue with the next permitted payable workflow without reopening the transaction.</p>
					</div>
					<div class="invoice-next-buttons">
						<button
							v-for="(action, index) in completedResult.next_actions || []"
							:key="action.value"
							type="button"
							class="edge-button"
							:class="{ 'edge-button--primary': index === 0, 'edge-button--secondary': index !== 0 }"
							@click="emitNextAction(action.value)"
						>
							{{ action.label }}
						</button>
						<button type="button" class="edge-button edge-button--secondary" @click="emitNextAction('supplier-payables')">Supplier Payables</button>
						<button type="button" class="edge-button edge-button--secondary" @click="emitNextAction('output')">Print & Share</button>
					</div>
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
					<template v-if="!completedResult">
						<button
							v-if="preview?.can_submit"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="busy || draftDirty"
							@click="submitDocument"
						>
							{{ busy ? "Submitting..." : "Submit Purchase Invoice" }}
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
					</template>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const PREVIEW_METHOD = "retailedge.standard_purchase_invoice_completion.get_standard_purchase_invoice_completion_preview";
const UPDATE_DRAFT_METHOD = "retailedge.standard_purchase_invoice_completion.update_standard_purchase_invoice_draft";
const SEARCH_METHOD = "retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options";
const PRICING_METHOD = "retailedge.standard_purchase_invoice_completion.get_standard_purchase_invoice_completion_item_pricing";
const SUBMIT_METHOD = "retailedge.standard_purchase_invoice_completion.submit_standard_purchase_invoice";
const WORKFLOW_METHOD = "retailedge.standard_purchase_invoice_completion.apply_standard_purchase_invoice_workflow_action";

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
	name: "StandardPurchaseInvoiceCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
		EdgeInput: runtimeComponents().EdgeInput,
		EdgeChildTable: runtimeComponents().EdgeChildTable,
	},
	props: {
		open: { type: Boolean, default: false },
		document: { type: Object, default: null },
		sourceMode: { type: String, default: "direct" },
		canUseNativeDesk: { type: Boolean, default: false },
		showNextActions: { type: Boolean, default: false },
	},
	emits: ["close", "changed", "completed", "next-action"],
	data() {
		return {
			preview: null,
			loading: false,
			busy: false,
			error: "",
			actionError: "",
			completedResult: null,
			draftPostingDate: "",
			draftDueDate: "",
			draftBillNo: "",
			draftBillDate: "",
			draftRemarks: "",
			draftItems: [],
			newItems: [],
			newItemPricingTokens: {},
			newItemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Buying Rate", fieldtype: "Currency", placeholder: "Auto buying price" },
			],
		};
	},
	computed: {
		workflowActions() {
			return this.preview?.workflow_readiness?.available_actions || [];
		},
		draftDirty() {
			if (!this.preview?.can_edit) return false;
			if (
				String(this.draftPostingDate || "") !== String(this.preview.posting_date || "")
				|| String(this.draftDueDate || "") !== String(this.preview.due_date || "")
				|| String(this.draftBillNo || "") !== String(this.preview.bill_no || "")
				|| String(this.draftBillDate || "") !== String(this.preview.bill_date || "")
				|| String(this.draftRemarks || "") !== String(this.preview.remarks || "")
			) return true;
			if (this.newItems.some((row) => row?.item_code)) return true;
			const original = this.preview.editable_items || [];
			if (this.draftItems.length !== original.length) return true;
			return this.draftItems.some((row, index) =>
				Number(row.qty || 0) !== Number(original[index]?.qty || 0)
				|| Number(row.rate || 0) !== Number(original[index]?.rate || 0)
			);
		},
		draftValid() {
			if (!this.draftPostingDate) return false;
			if (this.draftDueDate && String(this.draftDueDate) < String(this.draftPostingDate)) return false;
			const populatedNewItems = this.newItems.filter((row) => row?.item_code);
			if (this.draftItems.length + populatedNewItems.length < 1) return false;
			return this.draftItems.every((row) => Number(row.qty || 0) > 0 && Number(row.rate || 0) >= 0)
				&& populatedNewItems.every((row) => Number(row.qty || 0) > 0 && (row.rate === "" || row.rate === null || row.rate === undefined || Number(row.rate) >= 0));
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
		canRemoveDraftItem(index) {
			const row = this.draftItems[index];
			if (!row || row.source_locked) return false;
			const populatedNewItems = this.newItems.filter((item) => item?.item_code).length;
			return this.draftItems.length + populatedNewItems > 1;
		},
		removeDraftItem(index) {
			if (this.busy || !this.canRemoveDraftItem(index)) return;
			this.draftItems.splice(index, 1);
		},
		syncDraftEditor(preview) {
			this.draftPostingDate = preview?.posting_date || "";
			this.draftDueDate = preview?.due_date || "";
			this.draftBillNo = preview?.bill_no || "";
			this.draftBillDate = preview?.bill_date || "";
			this.draftRemarks = preview?.remarks || "";
			this.draftItems = (preview?.editable_items || []).map((row) => ({ ...row }));
			this.newItems = [];
		},
		async loadPreview() {
			if (!this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.preview = await callMethod(PREVIEW_METHOD, { name: this.document.name, source_mode: this.sourceMode || "direct" });
				if (Number(this.preview?.docstatus || 0) === 0) {
					this.completedResult = null;
					this.syncDraftEditor(this.preview);
				}
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this Purchase Invoice.");
			} finally {
				this.loading = false;
			}
		},
		async searchLineLink(column, query) {
			if (column?.fieldname !== "item_code") return [];
			const rows = await callMethod(SEARCH_METHOD, {
				fieldname: "item_code",
				txt: query || "",
				values: {
					company: this.preview?.company || "",
					branch: this.preview?.branch || "",
					warehouse: this.preview?.update_stock ? (this.preview?.default_warehouse || "") : "",
					supplier: this.preview?.supplier || "",
				},
			});
			return Array.isArray(rows) ? rows : [];
		},
		updateNewItems(rows) {
			const previous = this.newItems || [];
			const changed = [];
			this.newItems = (rows || []).map((row, index) => {
				const prior = previous[index] || {};
				if (row.item_code && row.item_code !== prior.item_code) {
					changed.push(index);
					return { ...row, rate: "" };
				}
				return { ...row };
			});
			changed.forEach((index) => this.priceNewItem(index));
		},
		async priceNewItem(index) {
			const row = this.newItems[index];
			if (!row?.item_code || !this.preview?.supplier) return;
			const token = `${row.item_code}:${Date.now()}:${Math.random()}`;
			this.newItemPricingTokens[index] = token;
			try {
				const result = await callMethod(PRICING_METHOD, {
					name: this.preview.name,
					item_code: row.item_code,
					qty: row.qty || 1,
					warehouse: this.preview.default_warehouse || "",
					posting_date: this.draftPostingDate || this.preview.posting_date || "",
				});
				if (this.newItemPricingTokens[index] !== token || this.newItems[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) this.newItems[index] = { ...this.newItems[index], rate: result.rate };
			} catch (error) {
				if (this.newItemPricingTokens[index] === token) this.actionError = errorMessage(error, `Unable to price ${row.item_code}.`);
			}
		},
		async saveDraftChanges() {
			if (!this.preview?.can_edit || !this.draftDirty || !this.draftValid || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(UPDATE_DRAFT_METHOD, {
					name: this.preview.name,
					expected_modified: this.preview.modified,
					source_mode: this.sourceMode || "direct",
					values: {
						posting_date: this.draftPostingDate,
						due_date: this.draftDueDate,
						bill_no: this.draftBillNo,
						bill_date: this.draftBillDate,
						remarks: this.draftRemarks,
						items: [
							...this.draftItems.map((row) => ({ name: row.name, item_code: row.item_code, qty: Number(row.qty), rate: row.rate === "" || row.rate === null || row.rate === undefined ? "" : Number(row.rate) })),
							...this.newItems.filter((row) => row?.item_code).map((row) => ({ item_code: row.item_code, qty: Number(row.qty), rate: row.rate })),
						],
					},
				}, "POST");
				this.preview = result;
				this.syncDraftEditor(result);
				this.$emit("changed", result);
				frappe.show_alert?.({ message: __("Draft Purchase Invoice updated"), indicator: "green" });
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to update this draft Purchase Invoice.");
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
					name: this.preview.name,
					expected_modified: this.preview.modified,
					source_mode: this.sourceMode || "direct",
				}, "POST");
				this.completedResult = result;
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
			if (!action || !this.preview?.workflow_eligible || this.busy || this.draftDirty) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					name: this.preview.name,
					action,
					expected_modified: this.preview.modified,
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
					source_mode: this.sourceMode || "direct",
				}, "POST");
				this.$emit("changed", result);
				if (Number(result?.docstatus || 0) === 1) {
					this.completedResult = result;
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
		emitNextAction(action) {
			if (!this.completedResult?.name || !action) return;
			this.$emit("next-action", {
				action,
				doctype: "Purchase Invoice",
				name: this.completedResult.name,
				supplier: this.completedResult.supplier || this.preview?.supplier || "",
				company: this.completedResult.company || this.preview?.company || "",
				branch: this.completedResult.branch || this.preview?.branch || "",
			});
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
			if (this.busy) return;
			if (this.preview?.can_edit && !this.completedResult && this.draftDirty) {
				frappe.confirm(__("Discard unsaved Purchase Invoice draft changes?"), () => this.$emit("close"));
				return;
			}
			this.$emit("close");
		},
	},
};
</script>

<style scoped>
.invoice-completion { display: grid; gap: 1rem; min-height: 12rem; }
.invoice-completion-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.invoice-completion-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.invoice-completion-summary span, .invoice-completion-workflow span { font-size: .78rem; color: var(--text-muted); }
.invoice-source-note { display:flex; gap:.5rem; align-items:center; padding:.7rem .8rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.6rem; background:var(--edge-surface-subtle,#f8fafc); }
.invoice-draft-editor { display:grid; gap:.75rem; padding:.8rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.6rem; }
.invoice-editor-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
.invoice-editor-heading p { margin:.2rem 0 0; color:var(--text-muted); font-size:.82rem; }
.invoice-editor-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }
.invoice-edit-items { display:grid; gap:.35rem; }
.invoice-edit-item { display:grid; grid-template-columns:minmax(0,1fr) 8rem 9rem 8rem 6.5rem; gap:.6rem; align-items:center; padding:.4rem 0; border-bottom:1px solid var(--edge-border-color,var(--border-color)); }
.invoice-edit-item--head { color:var(--text-muted); font-size:.75rem; font-weight:700; }
.invoice-edit-item > span { display:grid; gap:.15rem; }
.invoice-edit-item small,.invoice-source-lock { color:var(--text-muted); font-size:.7rem; }
.invoice-source-note span { color:var(--text-muted); }
.invoice-accounting-note { display: grid; gap: .25rem; padding: .8rem; border-radius: .6rem; background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.invoice-accounting-note p { margin: 0; }
.invoice-completion-items { display: grid; gap: .45rem; }
.invoice-completion-items h4 { margin: 0; }
.invoice-completion-item { display: grid; grid-template-columns: minmax(0,1fr) auto auto minmax(0,auto); gap: .75rem; padding: .55rem .7rem; border-bottom: 1px solid var(--edge-border-color,var(--border-color)); }
.invoice-completion-blockers, .invoice-completion-workflow, .invoice-completion-error, .invoice-next-actions { padding: .8rem; border-radius: .6rem; }
.invoice-next-actions { display: grid; gap: .7rem; border: 1px solid var(--edge-border-color,var(--border-color)); background: var(--edge-surface-subtle,#f8fafc); }
.invoice-next-actions p { margin: .25rem 0 0; color: var(--text-muted); }
.invoice-next-buttons { display: flex; flex-wrap: wrap; gap: .5rem; }
.invoice-completion-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.invoice-completion-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.invoice-completion-workflow { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.invoice-completion-workflow p { margin: .35rem 0 0; }
.invoice-completion-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.invoice-completion-hint { margin: 0; font-size: .82rem; color: var(--text-muted); }
.invoice-completion-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.invoice-completion-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) { .invoice-completion-summary, .invoice-editor-grid, .invoice-edit-item { grid-template-columns: 1fr; } .invoice-completion-item { grid-template-columns: 1fr; } .invoice-completion-footer { align-items: stretch; flex-direction: column; } .invoice-completion-actions { justify-content: flex-start; } }
</style>
