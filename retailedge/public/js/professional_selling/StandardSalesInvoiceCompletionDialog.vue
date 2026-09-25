<template>
	<EdgeModal
		:open="open"
		title="Complete Sales Invoice"
		subtitle="Review the saved ERPNext Sales Invoice and complete it through native submission or the active Frappe Workflow."
		size="lg"
		@close="requestClose"
	>
		<div class="invoice-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing Sales Invoice..." />
			<div v-else-if="error" class="invoice-completion-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="invoice-completion-summary">
					<div><span>Sales Invoice</span><strong>{{ preview.name }}</strong></div>
					<div><span>Customer</span><strong>{{ preview.customer || "Not set" }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company || "Not set" }}</strong></div>
					<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
					<div><span>Selling Price List</span><strong>{{ preview.selling_price_list || "ERPNext default" }}</strong></div>
					<div><span>Total</span><strong>{{ preview.currency || "" }} {{ preview.grand_total }}</strong></div>
					<div><span>Mode</span><strong>{{ preview.update_stock ? "Accounting + Stock" : "Accounting only" }}</strong></div>
				</div>

				<section v-if="preview.can_edit && !completedResult" class="invoice-draft-editor">
					<div class="invoice-editor-heading">
						<div>
							<strong>Edit draft before completion</strong>
							<p>Update permitted draft fields here. Customer, Company, Branch, item identity and source links remain protected; Stock Location stays branch-governed.</p>
						</div>
						<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !draftDirty || !draftValid" @click="saveDraftChanges">
							{{ busy ? "Saving..." : "Save Draft Changes" }}
						</button>
					</div>
					<div class="invoice-editor-grid">
						<EdgeInput id="invoice-posting-date" v-model="draftPostingDate" label="Posting Date" type="date" :disabled="busy" required />
						<EdgeInput id="invoice-due-date" v-model="draftDueDate" label="Due Date" type="date" :min="draftPostingDate || undefined" :disabled="busy" required />
						<EdgeInput id="invoice-po-number" v-model="draftPoNo" label="Customer PO / Reference" type="text" :disabled="busy" />
						<EdgeInput id="invoice-remarks" v-model="draftRemarks" label="Remarks" type="text" :disabled="busy" />
					</div>
					<div class="invoice-edit-items">
						<div class="invoice-edit-item invoice-edit-item--head"><span>Item</span><span>Qty</span><span>Rate</span><span>Stock Location</span><span>Amount</span><span>Action</span></div>
						<div v-for="(row, index) in draftItems" :key="row.name || `new-${index}`" class="invoice-edit-item">
							<span v-if="row.name" class="invoice-edit-item-label"><strong>{{ row.item_code || row.item_name || "Item" }}</strong><small v-if="row.source_locked">Source-linked</small></span>
							<EdgeLinkField v-else :modelValue="row.item_code || ''" label="Item" placeholder="Search item" :searcher="searchItem" :disabled="busy" @update:modelValue="setDraftItemCode(index, $event)" />
							<EdgeInput :modelValue="row.qty" :id="`invoice-item-qty-${index}`" label="Qty" type="number" min="0.000001" step="any" :disabled="busy" @update:modelValue="setDraftItemQty(index, $event)" />
							<EdgeInput :modelValue="row.rate" :id="`invoice-item-rate-${index}`" label="Rate" type="number" min="0" step="any" :disabled="busy || !canOverrideRate" @update:modelValue="setDraftItemRate(index, $event)" />
							<EdgeLinkField :modelValue="row.warehouse || ''" label="Stock Location" placeholder="Choose Stock Location" :searcher="searchWarehouse" :disabled="busy" @update:modelValue="setDraftItemWarehouse(index, $event)" />
							<span>{{ preview.currency || "" }} {{ lineAmount(row) }}</span>
							<button type="button" class="edge-button edge-button--secondary invoice-remove-item" :disabled="busy || !canRemoveDraftItem(index)" :title="row.source_locked ? 'Source-linked items cannot be removed here.' : 'Remove item'" @click="removeDraftItem(index)">Remove</button>
						</div>
						<div class="invoice-item-actions">
							<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="addDraftItem">Add Item</button>
						</div>
					</div>
					<p v-if="draftItems.some((row) => row.source_locked)" class="invoice-completion-hint">Source-linked items stay attached to their originating document and cannot be removed here.</p>
					<p class="invoice-completion-hint">ERPNext recalculates taxes, totals, source quantity limits and accounting validation when the draft is saved.</p>
				</section>

				<div v-if="preview.source_name" class="invoice-source-note">
					<span>Source</span>
					<strong>{{ preview.source_type }} {{ preview.source_name }}</strong>
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
					<strong>Standard Sales Invoice completion is blocked</strong>
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
						<strong>{{ completedResult.is_return ? "Return / Credit Note submitted" : "Sales Invoice submitted" }}</strong>
						<p>{{ completedResult.is_return ? "ERPNext has posted the governed return. Use output actions or close this review." : "Choose the next permitted workflow. The invoice stays open until you choose an action or close it." }}</p>
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
						<button type="button" class="edge-button edge-button--secondary" @click="emitNextAction('output')">Print & Send</button>
					</div>
				</div>

				<div v-if="actionError" class="invoice-completion-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="invoice-completion-footer">
				<div class="invoice-output-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="printDocument">Print</button>
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="downloadPdf">PDF</button>
				</div>
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
							{{ busy ? "Submitting..." : (preview?.is_return ? "Submit Return / Credit Note" : "Submit Sales Invoice") }}
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
const PREVIEW_METHOD = "retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_preview";
const UPDATE_DRAFT_METHOD = "retailedge.standard_sales_invoice_completion.update_standard_sales_invoice_draft";
const OUTPUT_DETAILS_METHOD = "retailedge.document_output.get_output_document_details";
const OUTPUT_PREVIEW_METHOD = "retailedge.document_output.render_document_preview";
const ACTIONS_METHOD = "retailedge.professional_selling.get_professional_selling_record_actions";
const SUBMIT_METHOD = "retailedge.standard_sales_invoice_completion.submit_standard_sales_invoice";
const WORKFLOW_METHOD = "retailedge.standard_sales_invoice_completion.apply_standard_sales_invoice_workflow_action";
const SEARCH_METHOD = "retailedge.professional_selling.search_professional_selling_options";
const PRICING_METHOD = "retailedge.standard_sales_invoice_completion.get_standard_sales_invoice_completion_item_pricing";

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
	name: "StandardSalesInvoiceCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
		EdgeInput: runtimeComponents().EdgeInput,
		EdgeLinkField: runtimeComponents().EdgeLinkField,
	},
	props: {
		open: { type: Boolean, default: false },
		document: { type: Object, default: null },
		sourceMode: { type: String, default: "standard" },
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
			draftPostingDate: "",
			draftDueDate: "",
			draftPoNo: "",
			draftRemarks: "",
			draftItems: [],
			pricingTokens: {},
			completedResult: null,
			outputDetails: null,
		};
	},
	computed: {
		workflowActions() {
			return this.preview?.workflow_readiness?.available_actions || [];
		},
		canOverrideRate() {
			return this.preview?.pricing?.allow_rate_change !== false;
		},
		draftDirty() {
			if (!this.preview?.can_edit) return false;
			if (
				String(this.draftPostingDate || "") !== String(this.preview?.posting_date || "")
				|| String(this.draftDueDate || "") !== String(this.preview?.due_date || "")
				|| String(this.draftPoNo || "") !== String(this.preview?.po_no || "")
				|| String(this.draftRemarks || "") !== String(this.preview?.remarks || "")
			) return true;
			const original = this.preview?.editable_items || [];
			if (this.draftItems.length !== original.length) return true;
			const originalByName = new Map(original.filter((row) => row?.name).map((row) => [row.name, row]));
			return this.draftItems.some((row) => {
				if (!row?.name) return Boolean(row?.item_code);
				const before = originalByName.get(row.name);
				if (!before) return true;
				return Number(row.qty || 0) !== Number(before.qty || 0)
					|| Number(row.rate || 0) !== Number(before.rate || 0)
					|| String(row.warehouse || "") !== String(before.warehouse || "");
			});
		},
		draftValid() {
			if (!this.draftPostingDate || !this.draftDueDate || String(this.draftDueDate) < String(this.draftPostingDate)) return false;
			if (!this.draftItems.length) return false;
			return this.draftItems.every((row) => (
				Boolean(row?.item_code)
				&& Number(row.qty || 0) > 0
				&& row.rate !== "" && row.rate !== null && row.rate !== undefined
				&& Number(row.rate) >= 0
			));
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
			return Boolean(row && !row.source_locked && this.draftItems.length > 1);
		},
		removeDraftItem(index) {
			if (this.busy || !this.canRemoveDraftItem(index)) return;
			this.draftItems = this.draftItems.filter((_row, rowIndex) => rowIndex !== index);
			this.pricingTokens = {};
		},
		applyPreview(preview) {
			this.preview = preview || null;
			this.draftPostingDate = preview?.posting_date || "";
			this.draftDueDate = preview?.due_date || "";
			this.draftPoNo = preview?.po_no || "";
			this.draftRemarks = preview?.remarks || "";
			this.draftItems = (preview?.editable_items || preview?.items || []).map((row) => ({ ...row }));
			this.pricingTokens = {};
		},
		async loadPreview() {
			if (!this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.applyPreview(await callMethod(PREVIEW_METHOD, { name: this.document.name, source_mode: this.sourceMode || "standard" }));
				if (Number(this.preview?.docstatus || 0) === 0) this.completedResult = null;
			} catch (error) {
				this.applyPreview(null);
				this.error = errorMessage(error, "Unable to review this Sales Invoice.");
			} finally {
				this.loading = false;
			}
		},
		searchOptions(fieldname, query) {
			return callMethod(SEARCH_METHOD, {
				document: "sales-invoice",
				fieldname,
				txt: query || "",
				values: {
					company: this.preview?.company || "",
					branch: this.preview?.branch || "",
					customer: this.preview?.customer || "",
				},
			}).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchItem(query) {
			return this.searchOptions("item_code", query);
		},
		searchWarehouse(query) {
			return this.searchOptions("warehouse", query);
		},
		lineAmount(row) {
			return (Number(row?.qty || 0) * Number(row?.rate || 0)).toFixed(2);
		},
		addDraftItem() {
			this.draftItems = [...this.draftItems, {
				name: "",
				item_code: "",
				item_name: "",
				qty: 1,
				rate: "",
				amount: 0,
				warehouse: this.preview?.default_warehouse || "",
				source_locked: false,
			}];
		},
		setDraftItemCode(index, value) {
			const row = this.draftItems[index];
			if (!row) return;
			row.item_code = value || "";
			row.rate = "";
			if (!row.warehouse) row.warehouse = this.preview?.default_warehouse || "";
			this.draftItems = [...this.draftItems];
			if (row.item_code) this.refreshDraftItemPricing(index);
		},
		setDraftItemQty(index, value) {
			const row = this.draftItems[index];
			if (!row) return;
			row.qty = value;
			this.draftItems = [...this.draftItems];
			if (row.item_code && Number(value || 0) > 0) this.refreshDraftItemPricing(index);
		},
		setDraftItemRate(index, value) {
			if (!this.canOverrideRate) return;
			const row = this.draftItems[index];
			if (!row) return;
			row.rate = value;
			this.draftItems = [...this.draftItems];
		},
		setDraftItemWarehouse(index, value) {
			const row = this.draftItems[index];
			if (!row) return;
			row.warehouse = value || "";
			this.draftItems = [...this.draftItems];
			if (row.item_code) this.refreshDraftItemPricing(index);
		},
		async refreshDraftItemPricing(index) {
			const row = this.draftItems[index];
			if (!row?.item_code || !this.preview?.customer) return;
			const token = (this.pricingTokens[index] || 0) + 1;
			this.pricingTokens[index] = token;
			try {
				const result = await callMethod(PRICING_METHOD, {
					name: this.preview.name,
					item_code: row.item_code,
					qty: Number(row.qty || 1),
					warehouse: row.warehouse || this.preview.default_warehouse || "",
					posting_date: this.draftPostingDate || this.preview.posting_date || "",
				});
				if (this.pricingTokens[index] !== token || this.draftItems[index]?.item_code !== row.item_code) return;
				this.draftItems[index] = {
					...this.draftItems[index],
					rate: result?.rate ?? "",
					warehouse: this.draftItems[index]?.warehouse || this.preview?.default_warehouse || "",
				};
				this.preview = {
					...this.preview,
					selling_price_list: result?.price_list || this.preview?.selling_price_list || "",
					pricing: {
						...(this.preview?.pricing || {}),
						price_list: result?.price_list || this.preview?.pricing?.price_list || "",
						source: result?.source || this.preview?.pricing?.source || "",
						allow_rate_change: result?.allow_rate_change ?? this.preview?.pricing?.allow_rate_change,
					},
				};
				this.draftItems = [...this.draftItems];
			} catch (error) {
				if (this.pricingTokens[index] === token) this.actionError = errorMessage(error, `Unable to price ${row.item_code}.`);
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
					values: {
						posting_date: this.draftPostingDate,
						due_date: this.draftDueDate,
						po_no: this.draftPoNo,
						remarks: this.draftRemarks,
						items: this.draftItems.map((row) => ({
							name: row.name || "",
							item_code: row.item_code,
							qty: Number(row.qty),
							rate: row.rate === "" || row.rate === null || row.rate === undefined ? "" : Number(row.rate),
							warehouse: row.warehouse || "",
						})),
					},
				}, "POST");
				this.applyPreview(result);
				this.$emit("changed", result);
				frappe.show_alert({ message: __("Draft Sales Invoice updated"), indicator: "green" });
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to update this draft Sales Invoice.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async saveDraftDates() {
			return this.saveDraftChanges();
		},

		async submitDocument() {
			if (!this.preview?.can_submit || this.busy || this.draftDirty) return;
			this.busy = true;
			this.actionError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					name: this.preview.name,
					expected_modified: this.preview.modified,
					source_mode: this.sourceMode || "standard",
				}, "POST");
				this.$emit("changed", result);
				const submitted = await callMethod(PREVIEW_METHOD, { name: result.name, source_mode: this.sourceMode || "standard" });
				this.completedResult = await this.decorateCompletedResult(submitted);
				this.$emit("completed", this.completedResult);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this Sales Invoice.");
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
					source_mode: this.sourceMode || "standard",
				}, "POST");
				this.$emit("changed", result);
				if (Number(result?.docstatus || 0) === 1) {
					const submitted = await callMethod(PREVIEW_METHOD, { name: result.name || this.preview.name, source_mode: this.sourceMode || "standard" });
					this.completedResult = await this.decorateCompletedResult(submitted);
					this.$emit("completed", this.completedResult);
					return;
				}
				await this.loadPreview();
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to apply the Sales Invoice workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async decorateCompletedResult(result) {
			const resolved = await callMethod(ACTIONS_METHOD, { document: "sales-invoice", name: result.name });
			return { ...result, next_actions: resolved.actions || [] };
		},
		async ensureOutputDetails() {
			if (this.outputDetails?.name === this.document?.name) return this.outputDetails;
			this.outputDetails = await callMethod(OUTPUT_DETAILS_METHOD, { document: "sales-invoice", name: this.document.name });
			return this.outputDetails;
		},
		async printDocument() {
			if (!this.document?.name || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const details = await this.ensureOutputDetails();
				const result = await callMethod(OUTPUT_PREVIEW_METHOD, {
					document: "sales-invoice",
					name: this.document.name,
					print_format: details.recommended_print_format || "Standard",
					no_letterhead: 1,
					show_logo: 1,
					include_qr: 0,
				});
				const frame = document.createElement("iframe");
				frame.style.position = "fixed";
				frame.style.width = "0";
				frame.style.height = "0";
				frame.style.border = "0";
				document.body.appendChild(frame);
				frame.contentDocument.open();
				frame.contentDocument.write(result.html || "");
				frame.contentDocument.close();
				frame.contentWindow.focus();
				frame.contentWindow.print();
				window.setTimeout(() => frame.remove(), 1200);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to print this Sales Invoice.");
			} finally {
				this.busy = false;
			}
		},
		async downloadPdf() {
			if (!this.document?.name) return;
			try {
				const details = await this.ensureOutputDetails();
				const query = new URLSearchParams({
					document: "sales-invoice",
					name: this.document.name,
					print_format: details.recommended_print_format || "Standard",
					no_letterhead: "1",
					show_logo: "1",
					include_qr: "0",
				}).toString();
				window.open("/api/method/retailedge.document_output.download_document_pdf?" + query, "_blank", "noopener,noreferrer");
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to prepare this Sales Invoice PDF.");
			}
		},
		emitNextAction(action) {
			if (!this.completedResult?.name || !action) return;
			this.$emit("next-action", {
				action,
				doctype: "Sales Invoice",
				name: this.completedResult.name,
				company: this.completedResult.company || this.preview?.company || "",
				branch: this.completedResult.branch || this.preview?.branch || "",
				customer: this.completedResult.customer || this.preview?.customer || "",
			});
		},

		requestClose() {
			if (this.busy) return;
			if (this.preview?.can_edit && !this.completedResult && this.draftDirty) {
				frappe.confirm(__("Discard unsaved Sales Invoice draft changes?"), () => this.$emit("close"));
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
.invoice-completion-summary span, .invoice-completion-workflow span, .invoice-source-note span { font-size: .78rem; color: var(--text-muted); }
.invoice-source-note, .invoice-draft-editor { display: grid; gap: .75rem; padding: .8rem; border-radius: .6rem; border: 1px solid var(--edge-border-color,var(--border-color)); }
.invoice-editor-heading { display:flex; justify-content:space-between; gap:1rem; align-items:flex-start; }
.invoice-editor-heading p { margin:.2rem 0 0; color:var(--text-muted); font-size:.82rem; }
.invoice-editor-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:.75rem; }
.invoice-edit-items { display:grid; gap:.35rem; }
.invoice-edit-item { display:grid; grid-template-columns:minmax(10rem,1.2fr) 7rem 8rem minmax(12rem,1fr) 8rem auto; gap:.6rem; align-items:center; padding:.4rem 0; border-bottom:1px solid var(--edge-border-color,var(--border-color)); }
.invoice-edit-item-label { display:grid; gap:.15rem; }
.invoice-edit-item-label small,.invoice-source-lock { color:var(--text-muted); font-size:.7rem; }
.invoice-edit-item--head { color:var(--text-muted); font-size:.75rem; font-weight:700; }
.invoice-next-actions { display:grid; gap:.65rem; padding:.85rem; border:1px solid var(--edge-color-brand-200,var(--blue-200,#bfdbfe)); border-radius:.6rem; background:var(--edge-color-brand-50,var(--blue-50,#eff6ff)); }
.invoice-next-actions p { margin:.2rem 0 0; color:var(--text-muted); }
.invoice-next-buttons,.invoice-output-actions { display:flex; flex-wrap:wrap; gap:.5rem; }
.invoice-item-actions { display:flex; justify-content:flex-end; padding-top:.35rem; }
.invoice-remove-item { white-space:nowrap; }
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
@media (max-width: 720px) { .invoice-completion-summary, .invoice-editor-grid, .invoice-edit-item { grid-template-columns: 1fr; } .invoice-completion-item { grid-template-columns: 1fr; } .invoice-editor-heading,.invoice-completion-footer { align-items: stretch; flex-direction: column; } .invoice-completion-actions { justify-content: flex-start; } }
</style>
