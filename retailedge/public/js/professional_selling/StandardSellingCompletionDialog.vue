<template>
	<EdgeModal
		:open="open"
		:title="dialogTitle"
		subtitle="Review the saved ERPNext draft and complete it through native submission or the active Frappe Workflow."
		size="lg"
		@close="requestClose"
	>
		<div class="selling-completion">
			<EdgeLoadingState v-if="loading" message="Reviewing saved draft..." />
			<div v-else-if="error" class="selling-completion-error" role="alert">{{ error }}</div>
			<template v-else-if="preview">
				<div class="selling-completion-summary">
					<div><span>Document</span><strong>{{ preview.name }}</strong></div>
					<div><span>Customer</span><strong>{{ preview.party || "Not set" }}</strong></div>
					<div><span>Company</span><strong>{{ preview.company || "Not set" }}</strong></div>
					<div><span>Branch</span><strong>{{ preview.branch || "Company-wide" }}</strong></div>
					<div><span>Total</span><strong>{{ preview.currency || "" }} {{ preview.grand_total }}</strong></div>
					<div><span>Status</span><strong>{{ preview.status || "Draft" }}</strong></div>
				</div>

				<div v-if="preview.items?.length" class="selling-completion-items">
					<h4>Items</h4>
					<div v-for="(row, index) in preview.items" :key="`${row.item_code}-${index}`" class="selling-completion-item">
						<span>{{ row.item_code || row.item_name || "Item" }}</span>
						<span>Qty {{ row.qty }}</span>
						<span>{{ preview.currency || "" }} {{ row.amount }}</span>
					</div>
					<p v-if="preview.item_count > preview.items.length" class="selling-completion-hint">
						Showing {{ preview.items.length }} of {{ preview.item_count }} items.
					</p>
				</div>

				<div v-if="preview.blockers?.length" class="selling-completion-blockers">
					<strong>Standard completion is blocked</strong>
					<ul>
						<li v-for="blocker in preview.blockers" :key="blocker">{{ blocker }}</li>
					</ul>
				</div>

				<div v-if="preview.workflow_readiness?.source === 'frappe'" class="selling-completion-workflow">
					<div>
						<span>Frappe Workflow</span>
						<strong>{{ preview.workflow_readiness.workflow || "Active Workflow" }}</strong>
					</div>
					<p>{{ preview.workflow_readiness.message }}</p>
					<p v-if="preview.workflow_readiness.current_state">
						Current state: <strong>{{ preview.workflow_readiness.current_state }}</strong>
					</p>
				</div>

				<div v-if="completedResult" class="selling-next-actions">
					<div>
						<strong>{{ completedResult.doctype }} submitted</strong>
						<p>Continue with the next permitted sales workflow or close this review.</p>
					</div>
					<div class="selling-next-buttons">
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
						<button type="button" class="edge-button edge-button--secondary" @click="emitNextAction('output')">View / Print / Send</button>
					</div>
				</div>

				<div v-if="actionError" class="selling-completion-error" role="alert">{{ actionError }}</div>
			</template>
		</div>

		<template #footer>
			<div class="selling-completion-footer">
				<div class="selling-output-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="printDocument">Print</button>
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy || !document?.name" @click="downloadPdf">PDF</button>
				</div>
				<div class="selling-completion-actions">
					<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="requestClose">Close</button>
					<button
						v-if="preview?.can_submit"
						type="button"
						class="edge-button edge-button--primary"
						:disabled="busy"
						@click="submitDocument"
					>
						{{ busy ? "Submitting..." : "Submit" }}
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
const PREVIEW_METHOD = "retailedge.standard_selling_completion.get_standard_selling_completion_preview";
const SUBMIT_METHOD = "retailedge.standard_selling_completion.submit_standard_selling_document";
const WORKFLOW_METHOD = "retailedge.standard_selling_completion.apply_standard_selling_workflow_action";
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
	return error?.message || error?.exc || error?._server_messages || fallback;
}

function doctypeSlug(doctype) {
	return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default {
	name: "StandardSellingCompletionDialog",
	components: {
		EdgeModal: runtimeComponents().EdgeModal,
		EdgeLoadingState: runtimeComponents().EdgeLoadingState,
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
		};
	},
	computed: {
		dialogTitle() {
			return this.document?.doctype ? `Complete ${this.document.doctype}` : "Complete Selling Document";
		},
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
			if (!this.document?.doctype || !this.document?.name || this.loading) return;
			this.loading = true;
			this.error = "";
			this.actionError = "";
			try {
				this.preview = await callMethod(PREVIEW_METHOD, {
					doctype: this.document.doctype,
					name: this.document.name,
				});
				if (Number(this.preview?.docstatus || 0) === 0) this.completedResult = null;
			} catch (error) {
				this.preview = null;
				this.error = errorMessage(error, "Unable to review this selling document.");
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
				}, "POST");
				this.completedResult = await this.decorateCompletedResult(result);
				this.$emit("changed", result);
				this.$emit("completed", this.completedResult);
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to submit this document.");
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
				}, "POST");
				this.$emit("changed", result);
				if (Number(result?.docstatus || 0) === 1) {
					this.completedResult = await this.decorateCompletedResult({
						...result,
						doctype: result.doctype || this.preview.doctype,
						name: result.name || this.preview.name,
						party: result.party || this.preview.party,
					});
					this.$emit("completed", this.completedResult);
					return;
				}
				await this.loadPreview();
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to apply the workflow action.");
				await this.loadPreview();
			} finally {
				this.busy = false;
			}
		},
		async decorateCompletedResult(result) {
			const document = result?.doctype === "Quotation" ? "quotation" : "sales-order";
			const resolved = await callMethod(ACTIONS_METHOD, { document, name: result.name });
			return { ...result, next_actions: resolved.actions || [] };
		},
		documentKey() {
			return this.document?.doctype === "Quotation" ? "quotation" : "sales-order";
		},
		async ensureOutputDetails() {
			if (this.outputDetails?.name === this.document?.name) return this.outputDetails;
			this.outputDetails = await callMethod(OUTPUT_DETAILS_METHOD, { document: this.documentKey(), name: this.document.name });
			return this.outputDetails;
		},
		async printDocument() {
			if (!this.document?.name || this.busy) return;
			this.busy = true;
			this.actionError = "";
			try {
				const details = await this.ensureOutputDetails();
				const result = await callMethod(OUTPUT_PREVIEW_METHOD, {
					document: this.documentKey(),
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
				this.actionError = errorMessage(error, "Unable to print this document.");
			} finally {
				this.busy = false;
			}
		},
		async downloadPdf() {
			if (!this.document?.name) return;
			try {
				const details = await this.ensureOutputDetails();
				const query = new URLSearchParams({
					document: this.documentKey(),
					name: this.document.name,
					print_format: details.recommended_print_format || "Standard",
					no_letterhead: "1",
					show_logo: "1",
					include_qr: "0",
				}).toString();
				window.open("/api/method/retailedge.document_output.download_document_pdf?" + query, "_blank", "noopener,noreferrer");
			} catch (error) {
				this.actionError = errorMessage(error, "Unable to prepare this document PDF.");
			}
		},
		emitNextAction(action) {
			if (!this.completedResult?.name || !action) return;
			this.$emit("next-action", {
				action,
				doctype: this.completedResult.doctype || this.preview?.doctype,
				name: this.completedResult.name,
				customer: this.completedResult.party || this.preview?.party || "",
			});
		},

		requestClose() {
			if (!this.busy) this.$emit("close");
		},
	},
};
</script>

<style scoped>
.selling-completion { display: grid; gap: 1rem; min-height: 12rem; }
.selling-completion-summary { display: grid; grid-template-columns: repeat(3,minmax(0,1fr)); gap: .75rem; }
.selling-completion-summary > div { display: grid; gap: .2rem; padding: .75rem; border: 1px solid var(--edge-border-color,var(--border-color)); border-radius: .6rem; }
.selling-completion-summary span, .selling-completion-workflow span { font-size: .78rem; color: var(--text-muted); }
.selling-completion-items { display: grid; gap: .45rem; }
.selling-completion-items h4 { margin: 0; }
.selling-completion-item { display: grid; grid-template-columns: minmax(0,1fr) auto auto; gap: .75rem; padding: .55rem .7rem; border-bottom: 1px solid var(--edge-border-color,var(--border-color)); }
.selling-completion-blockers, .selling-completion-workflow, .selling-completion-error { padding: .8rem; border-radius: .6rem; }
.selling-completion-blockers { background: var(--yellow-50,#fffbeb); border: 1px solid var(--yellow-200,#fde68a); }
.selling-completion-blockers ul { margin: .45rem 0 0; padding-left: 1.2rem; }
.selling-completion-workflow { background: var(--blue-50,#eff6ff); border: 1px solid var(--blue-200,#bfdbfe); }
.selling-completion-workflow p { margin: .35rem 0 0; }
.selling-completion-error { background: var(--red-50,#fef2f2); border: 1px solid var(--red-200,#fecaca); color: var(--red-700,#b91c1c); }
.selling-completion-hint { margin: 0; font-size: .82rem; color: var(--text-muted); }
.selling-next-actions { display:grid; gap:.65rem; padding:.85rem; border:1px solid var(--edge-color-brand-200,var(--blue-200,#bfdbfe)); border-radius:.6rem; background:var(--edge-color-brand-50,var(--blue-50,#eff6ff)); }
.selling-next-actions p { margin:.2rem 0 0; color:var(--text-muted); }
.selling-next-buttons,.selling-output-actions { display:flex; flex-wrap:wrap; gap:.5rem; }
.selling-completion-footer { display: flex; justify-content: space-between; align-items: center; gap: .75rem; width: 100%; }
.selling-completion-actions { display: flex; flex-wrap: wrap; justify-content: flex-end; gap: .5rem; }
@media (max-width: 720px) { .selling-completion-summary { grid-template-columns: 1fr; } .selling-completion-item { grid-template-columns: 1fr; } .selling-completion-footer { align-items: stretch; flex-direction: column; } .selling-completion-actions { justify-content: flex-start; } }
</style>
