<template>
	<EdgeModal
		:open="open"
		title="Complete Delivery Note"
		subtitle="Review the saved ERPNext Delivery Note and complete it through native stock submission or the active Frappe Workflow."
		size="xl"
		@close="requestClose"
	>
		<div class="delivery-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing Delivery Note..." />
			<div v-else-if="error" class="delivery-completion-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="delivery-completion-summary">
					<div><span>Delivery Note</span><strong>{{ preview.name }}</strong></div>
					<div><span>Customer</span><strong>{{ preview.customer || "Not set" }}</strong></div>
					<div><span>Source Sales Order</span><strong>{{ preview.source_sales_order || "Not resolved" }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company || "Not set" }}</strong></div>
					<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
					<div><span>Status</span><strong>{{ preview.status || "Draft" }}</strong></div>
				</div>

				<section v-if="preview.can_edit && !completedResult" class="delivery-draft-editor">
					<div class="delivery-editor-heading">
						<div>
							<strong>Edit draft before completion</strong>
							<p>Update the posting date, quantities, rates and Stock Locations, or add new items before submission.</p>
						</div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !draftDirty || !draftValid" @click="saveDraftChanges">
							{{ busy ? "Saving..." : "Save Draft Changes" }}
						</button>
					</div>
					<div class="delivery-editor-grid">
						<EdgeInput v-model="draftPostingDate" id="delivery-draft-posting-date" label="Posting Date" type="date" :disabled="busy" required />
						<EdgeInput v-model="draftRemarks" id="delivery-draft-remarks" label="Remarks" type="text" :disabled="busy" />
					</div>
					<div class="delivery-edit-items">
						<div class="delivery-edit-item delivery-edit-item--head"><span>Item</span><span>Qty</span><span>Rate</span><span>Stock Location</span></div>
						<div v-for="(row, index) in draftItems" :key="row.name || index" class="delivery-edit-item">
							<strong>{{ row.item_code || row.item_name || "Item" }}</strong>
							<EdgeInput v-model="row.qty" :id="`delivery-item-qty-${index}`" label="Qty" type="number" min="0.000001" step="any" :disabled="busy" />
							<EdgeInput v-model="row.rate" :id="`delivery-item-rate-${index}`" label="Rate" type="number" min="0" step="any" :disabled="busy" />
							<EdgeLinkField
								:modelValue="row.warehouse || ''"
								label="Stock Location"
								placeholder="Search stock location"
								:searcher="(query) => searchOptions('warehouse', query)"
								@select="row.warehouse = $event.value || ''"
								@clear="row.warehouse = ''"
							/>
						</div>
					</div>
					<EdgeChildTable
						:field="{ label: 'Additional Items', description: 'Add items to this Delivery Note draft.' }"
						:rows="newItems"
						:columns="newItemColumns"
						:addLabel="'Add Item'"
						:linkSearcher="searchNewItemLink"
						:newRowsFirst="false"
						@update:rows="newItems = $event"
					/>
				</section>

				<div class="delivery-stock-note">
					<strong>Stock posting</strong>
					<p>Submitting this Delivery Note uses ERPNext native stock posting. This workflow does not create Stock Ledger entries or valuation effects directly.</p>
				</div>

				<div v-if="preview.items?.length" class="delivery-completion-items">
					<h4>Delivery items</h4>
					<div v-for="(row, index) in preview.items" :key="`${row.item_code}-${index}`" class="delivery-completion-item">
						<span>{{ row.item_code || row.item_name || "Item" }}</span>
						<span>Qty {{ row.qty }}</span>
						<span>{{ row.warehouse || "No Stock Location" }}</span>
					</div>
					<p v-if="preview.item_count > preview.items.length" class="delivery-completion-hint">
						Showing {{ preview.items.length }} of {{ preview.item_count }} items.
					</p>
				</div>

				<div v-if="preview.blockers?.length" class="delivery-completion-blockers">
					<strong>Standard delivery completion is blocked</strong>
					<ul>
						<li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li>
					</ul>
				</div>

				<div v-if="preview.workflow_readiness?.source === 'frappe'" class="delivery-completion-workflow">
					<div>
						<span>Frappe Workflow</span>
						<strong>{{ preview.workflow_readiness.workflow || "Active Workflow" }}</strong>
					</div>
					<p>{{ preview.workflow_readiness.message }}</p>
					<p v-if="preview.workflow_readiness.current_state">
						Current state: <strong>{{ preview.workflow_readiness.current_state }}</strong>
					</p>
				</div>

				<div v-if="completedResult" class="delivery-next-actions">
					<div>
						<strong>Delivery Note submitted</strong>
						<p>Continue to billing or output without closing the workflow.</p>
					</div>
					<div class="delivery-next-buttons">
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
						<button type="button" class="edge-button edge-button--secondary" @click="emitNextAction('output')">Print & Send</button>
					</div>
				</div>

				<div v-if="actionError" class="delivery-completion-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="delivery-completion-footer">
				<div class="delivery-output-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="printDocument">Print</button>
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="downloadPdf">PDF</button>
				</div>
				<div class="delivery-completion-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">Close</button>
					<template v-if="!completedResult">
						<button
							v-if="preview?.can_edit && draftDirty"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="busy || !draftValid"
							@click="saveDraftChanges"
						>
							{{ busy ? "Saving..." : "Save Changes" }}
						</button>
						<button
							v-if="preview?.can_submit && !draftDirty"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="busy"
							@click="submitDocument"
						>
							{{ busy ? "Submitting..." : "Submit Delivery" }}
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
const PREVIEW_METHOD = "retailedge.standard_delivery_completion.get_standard_delivery_completion_preview";
const UPDATE_DRAFT_METHOD = "retailedge.standard_delivery_completion.update_standard_delivery_draft";
const SUBMIT_METHOD = "retailedge.standard_delivery_completion.submit_standard_delivery_note";
const SEARCH_METHOD = "retailedge.professional_selling.search_professional_selling_options";
const WORKFLOW_METHOD = "retailedge.standard_delivery_completion.apply_standard_delivery_workflow_action";
const OUTPUT_DETAILS_METHOD = "retailedge.document_output.get_output_document_details";
const OUTPUT_PREVIEW_METHOD = "retailedge.document_output.render_document_preview";
const ACTIONS_METHOD = "retailedge.professional_selling.get_professional_selling_record_actions";

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
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
	name: "StandardDeliveryCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
		EdgeInput: runtimeComponents().EdgeInput,
		EdgeChildTable: runtimeComponents().EdgeChildTable,
		EdgeLinkField: runtimeComponents().EdgeLinkField,
	},
	props: {
		open: { type: Boolean, default: false },
		document: { type: Object, default: null },
		canUseNativeDesk: { type: Boolean, default: false },
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
			outputDetails: null,
			draftPostingDate: "",
			draftRemarks: "",
			draftItems: [],
			newItems: [],
			newItemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Rate", fieldtype: "Currency", placeholder: "Auto price" },
				{ fieldname: "warehouse", label: "Stock Location", fieldtype: "Link", placeholder: "Required" },
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
				String(this.draftPostingDate || "") !== String(this.preview?.posting_date || "")
				|| String(this.draftRemarks || "") !== String(this.preview?.remarks || "")
			) return true;
			if (this.newItems.some((row) => row?.item_code)) return true;
			const original = this.preview?.editable_items || [];
			return this.draftItems.some((row, index) => (
				Number(row.qty || 0) !== Number(original[index]?.qty || 0)
				|| Number(row.rate || 0) !== Number(original[index]?.rate || 0)
				|| String(row.warehouse || "") !== String(original[index]?.warehouse || "")
			));
		},
		draftValid() {
			if (!this.preview?.can_edit || !this.draftPostingDate) return false;
			return this.draftItems.every((row) => Number(row.qty) > 0 && Number(row.rate) >= 0 && row.warehouse)
				&& this.newItems.filter((row) => row.item_code).every((row) => Number(row.qty || 0) > 0 && row.warehouse);
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
				if (Number(this.preview?.docstatus || 0) === 0) {
					this.completedResult = null;
					this.hydrateDraft();
				}
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this Delivery Note.");
			} finally {
				this.loading = false;
			}
		},
		hydrateDraft() {
			this.draftPostingDate = this.preview?.posting_date || "";
			this.draftRemarks = this.preview?.remarks || "";
			this.draftItems = (this.preview?.editable_items || []).map((row) => ({ ...row }));
			this.newItems = [];
		},
		searchOptions(fieldname, query) {
			return callMethod(SEARCH_METHOD, {
				document: "delivery-note",
				fieldname,
				txt: query || "",
				values: {
					company: this.preview?.company || "",
					branch: this.preview?.branch || "",
					customer: this.preview?.customer || "",
				},
			}).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchNewItemLink(column, query) {
			if (column?.fieldname === "item_code") return this.searchOptions("item_code", query);
			if (column?.fieldname === "warehouse") return this.searchOptions("warehouse", query);
			return Promise.resolve([]);
		},
		async saveDraftChanges() {
			if (!this.preview?.can_edit || !this.draftDirty || this.busy || !this.draftValid) return;
			this.busy = true;
			this.actionError = "";
			try {
				const additions = this.newItems.filter((row) => row?.item_code).map((row) => ({ ...row }));
				const result = await callMethod(UPDATE_DRAFT_METHOD, {
					name: this.preview.name,
					expected_modified: this.preview.modified,
					values: {
						posting_date: this.draftPostingDate,
						remarks: this.draftRemarks,
						items: [...this.draftItems, ...additions],
					},
				}, "POST");
				this.preview = result;
				this.hydrateDraft();
				this.$emit("changed", result);
				frappe.show_alert?.({ message: "Draft updated", indicator: "green" });
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to save Delivery Note changes.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async submitDocument() {
			if (!this.preview?.can_submit || this.draftDirty || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					name: this.preview.name,
					expected_modified: this.preview.modified,
				}, "POST");
				this.completedResult = await this.decorateCompletedResult(result);
				this.$emit("changed", result);
				this.$emit("completed", this.completedResult);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this Delivery Note.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async applyWorkflow(action) {
			if (!action || this.draftDirty || !this.preview?.workflow_eligible || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					name: this.preview.name,
					action,
					expected_modified: this.preview.modified,
					expected_workflow_state: this.preview.workflow_readiness?.current_state || "",
				}, "POST");
				this.$emit("changed", result);
				if (Number(result?.docstatus || 0) === 1) {
					this.completedResult = await this.decorateCompletedResult({ ...result, customer: result.customer || this.preview?.customer || "" });
					this.$emit("completed", this.completedResult);
					return;
				}
				await this.loadPreview();
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to apply the Delivery Note workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async decorateCompletedResult(result) {
			const resolved = await callMethod(ACTIONS_METHOD, { document: "delivery-note", name: result.name });
			return { ...result, next_actions: resolved.actions || [] };
		},
		async ensureOutputDetails() {
			if (this.outputDetails?.name === this.document?.name) return this.outputDetails;
			this.outputDetails = await callMethod(OUTPUT_DETAILS_METHOD, { document: "delivery-note", name: this.document.name });
			return this.outputDetails;
		},
		async printDocument() {
			if (!this.document?.name || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const details = await this.ensureOutputDetails();
				const result = await callMethod(OUTPUT_PREVIEW_METHOD, {
					document: "delivery-note",
					name: this.document.name,
					print_format: details.recommended_print_format || "Standard",
					no_letterhead: 1,
					show_logo: 1,
					include_qr: 0,
				});
				const frame = document.createElement("iframe");
				Object.assign(frame.style, { position: "fixed", width: "0", height: "0", border: "0" });
				document.body.appendChild(frame);
				frame.contentDocument.open();
				frame.contentDocument.write(result.html || "");
				frame.contentDocument.close();
				frame.contentWindow.focus();
				frame.contentWindow.print();
				window.setTimeout(() => frame.remove(), 1200);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to print this Delivery Note.");
			} finally {
				this.busy = false;
			}
		},
		async downloadPdf() {
			if (!this.document?.name) return;
			try {
				const details = await this.ensureOutputDetails();
				const query = new URLSearchParams({
					document: "delivery-note",
					name: this.document.name,
					print_format: details.recommended_print_format || "Standard",
					no_letterhead: "1",
					show_logo: "1",
					include_qr: "0",
				}).toString();
				window.open("/api/method/retailedge.document_output.download_document_pdf?" + query, "_blank", "noopener,noreferrer");
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to prepare this Delivery Note PDF.");
			}
		},
		emitNextAction(action) {
			if (!this.completedResult?.name || !action) return;
			this.$emit("next-action", {
				action,
				doctype: "Delivery Note",
				name: this.completedResult.name,
				customer: this.completedResult.customer || this.preview?.customer || "",
			});
		},

		requestClose() {
			if (!this.busy) this.$emit("close");
		},
	},
};
</script>

<style scoped>
.delivery-completion { display: grid; gap: 1rem; min-height: 12rem; }
.delivery-completion-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.delivery-completion-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.delivery-completion-summary span, .delivery-completion-workflow span { font-size: .78rem; color: var(--text-muted); }
.delivery-draft-editor { display:grid; gap:1rem; padding:1rem; border:1px solid var(--edge-border-color,var(--border-color)); border-radius:.7rem; background:var(--edge-surface-muted,var(--control-bg)); }
.delivery-editor-heading { display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; }
.delivery-editor-heading p { margin:.25rem 0 0; color:var(--text-muted); }
.delivery-editor-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }
.delivery-edit-items { display:grid; gap:.45rem; }
.delivery-edit-item { display:grid; grid-template-columns:minmax(10rem,1.2fr) minmax(7rem,.6fr) minmax(7rem,.6fr) minmax(12rem,1fr); gap:.6rem; align-items:end; }
.delivery-edit-item--head { color:var(--text-muted); font-size:.75rem; font-weight:700; }
.delivery-stock-note { padding: .8rem; border-radius: .6rem; background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.delivery-stock-note p { margin: .35rem 0 0; }
.delivery-completion-items { display: grid; gap: .45rem; }
.delivery-completion-items h4 { margin: 0; }
.delivery-completion-item { display: grid; grid-template-columns: minmax(0,1fr) auto minmax(10rem,auto); gap: .75rem; padding: .55rem .7rem; border-bottom: 1px solid var(--edge-border-color,var(--border-color)); }
.delivery-completion-blockers, .delivery-completion-workflow, .delivery-completion-error { padding: .8rem; border-radius: .6rem; }
.delivery-completion-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.delivery-completion-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.delivery-completion-workflow { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.delivery-completion-workflow p { margin: .35rem 0 0; }
.delivery-completion-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.delivery-completion-hint { margin: 0; font-size: .82rem; color: var(--text-muted); }
.delivery-next-actions { display:grid; gap:.65rem; padding:.85rem; border:1px solid var(--edge-color-brand-200,var(--blue-200,#bfdbfe)); border-radius:.6rem; background:var(--edge-color-brand-50,var(--blue-50,#eff6ff)); }
.delivery-next-actions p { margin:.2rem 0 0; color:var(--text-muted); }
.delivery-next-buttons,.delivery-output-actions { display:flex; flex-wrap:wrap; gap:.5rem; }
.delivery-completion-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.delivery-completion-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 900px) { .delivery-edit-item { grid-template-columns:1fr 1fr; } }
@media (max-width: 720px) { .delivery-editor-heading { flex-direction:column; } .delivery-editor-grid,.delivery-edit-item { grid-template-columns:1fr; } .delivery-completion-summary { grid-template-columns: 1fr; } .delivery-completion-item { grid-template-columns: 1fr; } .delivery-completion-footer { align-items: stretch; flex-direction: column; } .delivery-completion-actions { justify-content: flex-start; } }
</style>
