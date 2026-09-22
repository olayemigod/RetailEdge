<template>
	<EdgeAppShell
		product="retailedge"
		title="Transfer Stock"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/transfer-stock"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-transfer-stock-page">
			<EdgePageHeader
				title="Transfer Stock"
				description="Use this full-page workspace for multi-item stock transfers. Quick Transfer remains available for short movements."
			/>
			<EdgeLoadingState v-if="loading && !loaded" message="Preparing stock transfer..." :skeleton="true" />
			<EdgeErrorState v-else-if="loadError" title="Transfer Stock unavailable" :message="loadError" @retry="loadPage" />

			<div v-else class="transaction-page-content">
				<section v-if="recoveryCandidate" class="edge-panel recovery-panel">
					<div><strong>Unsaved transfer found</strong><small>{{ recoverySummary }}</small></div>
					<div class="page-actions"><button class="edge-button edge-button--primary" type="button" @click="restoreRecovery">Restore</button><button class="edge-button" type="button" @click="discardRecovery">Discard</button></div>
				</section>
				<section v-if="handoffNotice" class="edge-panel notice-panel"><strong>Continued from Quick Transfer</strong><p>{{ handoffNotice }}</p></section>

				<section v-if="savedDocument && !editingSavedDraft" class="edge-panel saved-panel">
					<div><span class="page-kicker">{{ Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved" }}</span><h3>{{ savedDocument.name }}</h3><p>{{ Number(savedDocument.docstatus || 0) === 1 ? "ERPNext has submitted the Stock Entry and owns the posted stock movement." : "The ERPNext Stock Entry draft now owns the transfer." }}</p></div>
					<div class="page-actions"><button v-if="Number(savedDocument.docstatus || 0) === 0" class="edge-button edge-button--primary" type="button" @click="beginSavedDraftEdit">Continue Editing on Page</button><button v-if="Number(savedDocument.docstatus || 0) === 0" class="edge-button" type="button" @click="openCompletion">Review / Complete</button><button class="edge-button" type="button" @click="startAnother">Start Another Transfer</button></div>
				</section>

				<form v-if="!savedDocument || editingSavedDraft" class="edge-panel transaction-form" @submit.prevent="saveDraft">
					<div class="context-cards">
						<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
						<div><span>Purpose</span><strong>{{ formContext.purpose || "Material Transfer" }}</strong></div>
					</div>
					<div v-if="saveError" class="form-error" role="alert">{{ saveError }}</div>
					<div v-if="sameWarehouse" class="form-warning" role="alert">Source and Destination Stock Location must be different.</div>

					<div class="field-grid">
						<EdgeInput v-model="values.posting_date" id="transfer-stock-posting-date" label="Posting Date" type="date" required />
						<EdgeLinkField v-if="branchEnabled" :modelValue="values.source_branch" label="Source Branch" placeholder="Search source branch" :searcher="searchSourceBranch" :context="searchContext" :disabled="editingSavedDraft" @update:modelValue="setSourceBranch" />
						<EdgeLinkField :modelValue="values.source_warehouse" label="Source Stock Location" placeholder="Search source stock location" :required="true" :disabled="editingSavedDraft || (requiresBranchSelection && !values.source_branch)" :searcher="searchSourceWarehouse" :context="searchContext" @update:modelValue="setSourceWarehouse" />
						<EdgeLinkField v-if="branchEnabled" :modelValue="values.target_branch" label="Destination Branch" placeholder="Search destination branch" :searcher="searchTargetBranch" :context="searchContext" :disabled="editingSavedDraft" @update:modelValue="setTargetBranch" />
						<EdgeLinkField :modelValue="values.target_warehouse" label="Destination Stock Location" placeholder="Search destination stock location" :required="true" :disabled="editingSavedDraft || (requiresBranchSelection && !values.target_branch)" :searcher="searchTargetWarehouse" :context="searchContext" @update:modelValue="setTargetWarehouse" />
					</div>

					<div class="items-heading"><div><span class="page-kicker">Transfer items</span><h3>Products to move</h3><p>Use this page when the transfer contains many stock lines instead of keeping the transaction inside a modal.</p></div><span class="item-count">{{ populatedItemCount }} item{{ populatedItemCount === 1 ? "" : "s" }}</span></div>
					<EdgeChildTable :field="itemTableField" :rows="values.items" :columns="itemColumns" :addLabel="'Add Item'" :linkSearcher="searchLineLink" :linkCanCreate="canCreateItemLink" :linkCreator="createItemLink" :linkCreateLabel="itemCreateLabel" :newRowsFirst="true" @update:rows="updateItems" />
					<p class="hint">Serial-numbered or batch-managed items may require Advanced ERPNext review so exact serial/batch allocations remain authoritative.</p>
					<label class="field"><span>Remarks</span><textarea v-model="values.remarks" class="form-control" rows="4" placeholder="Optional transfer note"></textarea></label>

					<div class="sticky-actions">
						<div><strong>{{ hasUnsavedChanges ? "Unsaved changes" : "Ready" }}</strong><small>{{ hasUnsavedChanges ? "A temporary browser-session recovery copy is retained until the ERPNext draft is saved." : "Complete the required fields, then save the draft." }}</small></div>
						<div class="page-actions"><button v-if="canUseNativeDesk" class="edge-button" type="button" :disabled="saving" @click="openAdvancedNative">Advanced: ERPNext</button><button v-if="editingSavedDraft" class="edge-button" type="button" :disabled="saving" @click="cancelSavedDraftEdit">Cancel Edit</button><button v-else class="edge-button" type="button" :disabled="saving" @click="resetForm">Reset</button><button class="edge-button edge-button--primary" type="submit" :disabled="saving || loading || !transferContextReady">{{ saving ? "Saving..." : (editingSavedDraft ? "Update Draft" : (formContext.submit_label || "Save Draft")) }}</button></div>
					</div>
				</form>
			</div>

			<StandardStockCompletionDialog :open="completionOpen" :document="savedDocument" :canUseNativeDesk="canUseNativeDesk" @close="completionOpen = false" @changed="handleCompletionChanged" @completed="handleCompletionCompleted" />
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import { callMethod, errorMessage, quickCreateItem, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import StandardStockCompletionDialog from "../retailedge_business_hub/StandardStockCompletionDialog.vue";

const CONTEXT_METHOD = "retailedge.guided_stock_transfer.get_simple_stock_transfer_context";
const SEARCH_METHOD = "retailedge.guided_stock_transfer.search_simple_stock_transfer_options";
const CREATE_METHOD = "retailedge.guided_stock_transfer.create_simple_stock_transfer_draft";
const UPDATE_METHOD = "retailedge.standard_stock_completion.update_standard_stock_document_draft";
const PREVIEW_METHOD = "retailedge.standard_stock_completion.get_standard_stock_completion_preview";
const SHELL_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const HANDOFF_PREFIX = "retailedge:transfer-stock:handoff:";
const RECOVERY_PREFIX = "retailedge:transfer-stock:recovery:";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return { company: "", posting_date: "", source_branch: "", target_branch: "", source_warehouse: "", target_warehouse: "", remarks: "", items: [{ item_code: "", qty: 1 }] };
}
function clone(value) { return JSON.parse(JSON.stringify(value || {})); }
function stored(raw, maxAge) {
	if (!raw) return null;
	try { const value = JSON.parse(raw); return value?.createdAt && Date.now() - Number(value.createdAt) <= maxAge && value.values ? value : null; } catch (_error) { return null; }
}

export default {
	name: "RetailEdgeTransferStock",
	components: { EdgeAppShell: runtime.EdgeAppShell, EdgePageLayout: runtime.EdgePageLayout, EdgePageHeader: runtime.EdgePageHeader, EdgeLoadingState: runtime.EdgeLoadingState, EdgeErrorState: runtime.EdgeErrorState, EdgeLinkField: runtime.EdgeLinkField, EdgeInput: runtime.EdgeInput, EdgeChildTable: runtime.EdgeChildTable, StandardStockCompletionDialog },
	data() {
		return {
			loading: false, loaded: false, saving: false, loadError: "", saveError: "", formContext: {}, values: emptyValues(), initialSnapshot: "",
			sourceCascadeToken: 0, targetCascadeToken: 0, recoveryCandidate: null, handoffNotice: "", recoveryTimer: null, savedDocument: null, editingSavedDraft: false, completionOpen: false,
			tenantName: "", branchName: "", userName: "", menuItems: [], canUseNativeDesk: false,
			itemTableField: { label: "Items", description: "Use the page for larger stock movements with many item rows." },
			itemColumns: [{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search stock item" }, { fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 }],
		};
	},
	computed: {
		branchEnabled() { return Boolean(this.formContext.capabilities?.branch_enabled); },
		requiresBranchSelection() { return Boolean(this.formContext.capabilities?.requires_branch_selection); },
		canCreateItem() { return Boolean(this.formContext.capabilities?.can_create_item); },
		searchContext() { return { company: this.values.company, source_branch: this.values.source_branch, target_branch: this.values.target_branch, source_warehouse: this.values.source_warehouse, target_warehouse: this.values.target_warehouse }; },
		sameWarehouse() { return Boolean(this.values.source_warehouse && this.values.target_warehouse && this.values.source_warehouse === this.values.target_warehouse); },
		transferContextReady() { if (this.sameWarehouse || !this.values.source_warehouse || !this.values.target_warehouse) return false; if (this.requiresBranchSelection && (!this.values.source_branch || !this.values.target_branch)) return false; return true; },
		hasUnsavedChanges() { return Boolean(this.initialSnapshot && JSON.stringify(this.values) !== this.initialSnapshot); },
		populatedItemCount() { return (this.values.items || []).filter((row) => row?.item_code).length; },
		recoverySummary() { const v = this.recoveryCandidate?.values || {}; const count = (v.items || []).filter((row) => row?.item_code).length; return `${count} item${count === 1 ? "" : "s"} entered${v.source_warehouse ? ` from ${v.source_warehouse}` : ""}${v.target_warehouse ? ` to ${v.target_warehouse}` : ""}.`; },
	},
	watch: { values: { deep: true, handler() { if (this.loaded && !this.savedDocument) this.scheduleRecovery(); } } },
	created() {
		this._pageShow = () => { if (!this.loaded && !this.loading) this.loadPage(); };
		this._beforeUnload = (event) => { if (!this.hasUnsavedChanges || this.saving || (this.savedDocument && !this.editingSavedDraft)) return; event.preventDefault(); event.returnValue = ""; };
	},
	mounted() { window.addEventListener("retailedge-transfer-stock-page-show", this._pageShow); window.addEventListener("beforeunload", this._beforeUnload); this.loadPage(); },
	beforeUnmount() { window.removeEventListener("retailedge-transfer-stock-page-show", this._pageShow); window.removeEventListener("beforeunload", this._beforeUnload); if (this.recoveryTimer) clearTimeout(this.recoveryTimer); },
	methods: {
		async loadPage() {
			if (this.loading) return;
			this.loading = true; this.loadError = ""; this.saveError = ""; this.savedDocument = null; this.completionOpen = false;
			try {
				const [data, shell] = await Promise.all([callMethod(CONTEXT_METHOD), callMethod(SHELL_METHOD)]);
				this.formContext = data || {}; this.applyShell(shell || {});
				this.values = { ...emptyValues(), ...(data.defaults || {}), items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })) };
				this.initialSnapshot = JSON.stringify(this.values);
				if (!this.consumeHandoff()) this.loadRecoveryCandidate();
				this.loaded = true;
			} catch (error) { this.loadError = errorMessage(error, "Unable to prepare Transfer Stock."); }
			finally { this.loading = false; }
		},
		applyShell(shell) {
			const c = shell.context || {}; this.tenantName = c.company_label || c.company || ""; this.branchName = c.branch || ""; this.userName = c.user_name || "";
			this.canUseNativeDesk = Boolean(shell.access?.can_use_native_desk) && shell.feature_flags?.native_document_fallback_enabled !== false;
			this.menuItems = (shell.navigation_groups || []).map((g) => ({ ...g, items: (g.items || []).map((i) => ({ ...i, route: this.routeForTarget(i) })).filter((i) => i.route) })).filter((g) => g.items.length);
		},
		routeForTarget(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return ""; if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; return item.target || ""; },
		handleNavigation(route) { if (!route || route === "/app/transfer-stock") return; const go = () => { if (/^https?:\/\//i.test(route)) window.location.assign(route); else frappe.set_route(...String(route).replace(/^\/app\//, "").split("/").filter(Boolean)); }; if (!this.hasUnsavedChanges || (this.savedDocument && !this.editingSavedDraft)) return go(); frappe.confirm("Leave Transfer Stock? Unsaved changes are retained temporarily in this browser session.", go); },
		recoveryKey() { return `${RECOVERY_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		handoffKey() { return `${HANDOFF_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		consumeHandoff() { let raw = ""; try { raw = sessionStorage.getItem(this.handoffKey()) || ""; sessionStorage.removeItem(this.handoffKey()); } catch (_error) { return false; } const payload = stored(raw, 10 * 60 * 1000); if (!payload) return false; if (payload.values.company && this.values.company && payload.values.company !== this.values.company) return false; this.values = { ...this.values, ...clone(payload.values), items: (payload.values.items || this.values.items).map((row) => ({ ...row })) }; this.handoffNotice = "Source, destination and item lines were carried into the full-page workspace."; return true; },
		loadRecoveryCandidate() { let raw = ""; try { raw = sessionStorage.getItem(this.recoveryKey()) || ""; } catch (_error) { return; } const payload = stored(raw, 12 * 60 * 60 * 1000); if (payload && (!payload.values.company || !this.values.company || payload.values.company === this.values.company)) this.recoveryCandidate = payload; },
		async restoreRecovery() {
			if (!this.recoveryCandidate?.values) return;
			const recovered = clone(this.recoveryCandidate.values);
			this.values = { ...this.values, ...recovered, items: (recovered.items || []).map((row) => ({ ...row })) };
			this.recoveryCandidate = null; this.saveError = "";
			try {
				if (this.values.company && (this.values.source_branch || this.values.source_warehouse)) {
					const source = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.source_branch || "", warehouse: this.values.source_warehouse || "", preference: "source" });
					this.values.source_branch = source.branch || this.values.source_branch || "";
					this.values.source_warehouse = source.warehouse || this.values.source_warehouse || "";
				}
				if (this.values.company && (this.values.target_branch || this.values.target_warehouse)) {
					const target = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.target_branch || "", warehouse: this.values.target_warehouse || "", preference: "target" });
					this.values.target_branch = target.branch || this.values.target_branch || "";
					this.values.target_warehouse = target.warehouse || this.values.target_warehouse || "";
				}
				if (this.values.source_warehouse && this.values.source_warehouse === this.values.target_warehouse) this.values.target_warehouse = "";
				this.handoffNotice = "Recovered unsaved transfer work and revalidated current source / destination access.";
			} catch (error) {
				this.values.source_branch = ""; this.values.source_warehouse = ""; this.values.target_branch = ""; this.values.target_warehouse = "";
				this.saveError = errorMessage(error, "Recovered transfer locations are no longer available. Choose the current source and destination before saving.");
				this.handoffNotice = "Recovered transfer lines, but saved source / destination context was cleared because access could not be revalidated.";
			}
		},
		discardRecovery() { this.recoveryCandidate = null; this.clearRecovery(); },
		scheduleRecovery() { if (this.recoveryTimer) clearTimeout(this.recoveryTimer); this.recoveryTimer = setTimeout(() => { if (!this.hasUnsavedChanges || this.savedDocument) return this.clearRecovery(); try { sessionStorage.setItem(this.recoveryKey(), JSON.stringify({ createdAt: Date.now(), values: clone(this.values) })); } catch (_error) {} }, 250); },
		clearRecovery() { try { sessionStorage.removeItem(this.recoveryKey()); } catch (_error) {} },
		resetForm() { const reset = () => { this.clearRecovery(); this.values = { ...emptyValues(), ...(this.formContext.defaults || {}), items: (this.formContext.defaults?.items || emptyValues().items).map((row) => ({ ...row })) }; this.initialSnapshot = JSON.stringify(this.values); this.saveError = ""; }; if (!this.hasUnsavedChanges) return reset(); frappe.confirm("Discard the unsaved stock transfer changes?", reset); },
		async searchOptions(fieldname, query) { const rows = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values: { ...this.values, items: undefined } }); return Array.isArray(rows) ? rows : []; },
		searchSourceBranch(query) { return this.searchOptions("source_branch", query); }, searchTargetBranch(query) { return this.searchOptions("target_branch", query); }, searchSourceWarehouse(query) { return this.searchOptions("source_warehouse", query); }, searchTargetWarehouse(query) { return this.searchOptions("target_warehouse", query); },
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		canCreateItemLink(column) { return this.canCreateItem && column?.fieldname === "item_code"; }, createItemLink(column, query) { return column?.fieldname === "item_code" ? quickCreateItem(query, { stockItem: true }) : Promise.resolve(null); }, itemCreateLabel(column) { return column?.fieldname === "item_code" ? "Create Stock Item" : "Create new"; },
		async setSourceBranch(next) { const branch = next || ""; this.values.source_branch = branch; this.values.source_warehouse = ""; if (!branch || !this.values.company) return; const token = ++this.sourceCascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "source" }); if (token !== this.sourceCascadeToken) return; this.values.source_branch = r.branch || branch; this.values.source_warehouse = r.warehouse || ""; if (this.sameWarehouse) this.values.target_warehouse = ""; } catch (error) { if (token === this.sourceCascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Source Branch stock location."); } },
		async setTargetBranch(next) { const branch = next || ""; this.values.target_branch = branch; this.values.target_warehouse = ""; if (!branch || !this.values.company) return; const token = ++this.targetCascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "target" }); if (token !== this.targetCascadeToken) return; this.values.target_branch = r.branch || branch; this.values.target_warehouse = r.warehouse && r.warehouse !== this.values.source_warehouse ? r.warehouse : ""; } catch (error) { if (token === this.targetCascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Destination Branch stock location."); } },
		async setSourceWarehouse(next) { const warehouse = next || ""; this.values.source_warehouse = warehouse; if (!warehouse || !this.values.company) return; const token = ++this.sourceCascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.source_branch, warehouse, preference: "source" }); if (token !== this.sourceCascadeToken) return; this.values.source_branch = r.branch || this.values.source_branch; this.values.source_warehouse = r.warehouse || warehouse; if (this.sameWarehouse) this.values.target_warehouse = ""; } catch (error) { if (token === this.sourceCascadeToken) { this.values.source_warehouse = ""; this.saveError = errorMessage(error, "Unable to use the selected Source Stock Location."); } } },
		async setTargetWarehouse(next) { const warehouse = next || ""; this.values.target_warehouse = warehouse; if (!warehouse || !this.values.company) return; if (warehouse === this.values.source_warehouse) { this.values.target_warehouse = ""; this.saveError = "Source and Destination Stock Location must be different."; return; } const token = ++this.targetCascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.target_branch, warehouse, preference: "target" }); if (token !== this.targetCascadeToken) return; this.values.target_branch = r.branch || this.values.target_branch; this.values.target_warehouse = r.warehouse || warehouse; } catch (error) { if (token === this.targetCascadeToken) { this.values.target_warehouse = ""; this.saveError = errorMessage(error, "Unable to use the selected Destination Stock Location."); } } },
		updateItems(rows) { this.values.items = (rows || []).map((row) => ({ ...row })); },
		async saveDraft() {
			if (this.saving || this.loading || !this.transferContextReady) return;
			this.saving = true; this.saveError = "";
			try {
				let result;
				if (this.savedDocument?.name && this.editingSavedDraft) {
					result = await callMethod(UPDATE_METHOD, {
						doctype: "Stock Entry",
						name: this.savedDocument.name,
						expected_modified: this.savedDocument.modified || "",
						values: {
							posting_date: this.values.posting_date,
							remarks: this.values.remarks || "",
							items: (this.values.items || []).filter((row) => row?.item_code).map((row) => ({ name: row.name || "", item_code: row.item_code, qty: Number(row.qty || 0) })),
						},
					}, "POST");
					this.syncPageFromDraftPreview(result);
					this.savedDocument = { ...this.savedDocument, ...result, doctype: "Stock Entry" };
					this.initialSnapshot = JSON.stringify(this.values);
					this.editingSavedDraft = false;
					frappe.show_alert?.({ message: `Stock Transfer ${result.name} draft updated`, indicator: "green" });
					return;
				}
				result = await callMethod(CREATE_METHOD, { values: this.values });
				if (!result?.name) throw new Error("Stock Entry draft was not returned.");
				this.clearRecovery(); this.initialSnapshot = JSON.stringify(this.values);
				this.savedDocument = { ...result, doctype: result.doctype || "Stock Entry" };
				this.completionOpen = false;
				frappe.show_alert?.({ message: `Stock Transfer ${result.name} saved as Draft`, indicator: "green" });
			} catch (error) { this.saveError = errorMessage(error, "Unable to save the Stock Transfer draft."); }
			finally { this.saving = false; }
		},
		async beginSavedDraftEdit() {
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 0 || this.saving) return;
			this.saveError = ""; this.saving = true;
			try {
				const preview = await callMethod(PREVIEW_METHOD, { doctype: "Stock Entry", name: this.savedDocument.name }, "GET");
				this.savedDocument = { ...this.savedDocument, ...preview, doctype: "Stock Entry" };
				if (!preview?.can_edit) { this.saveError = (preview?.blockers || [])[0] || "This Stock Transfer draft is no longer editable in the standard page."; return; }
				this.syncPageFromDraftPreview(preview);
				this.editingSavedDraft = true; this.completionOpen = false; this.initialSnapshot = JSON.stringify(this.values);
			} catch (error) { this.saveError = errorMessage(error, "Unable to reload this Stock Transfer draft for editing."); }
			finally { this.saving = false; }
		},
		cancelSavedDraftEdit() { const close = () => { try { this.values = JSON.parse(this.initialSnapshot || "{}"); } catch (_error) {} this.editingSavedDraft = false; this.saveError = ""; }; if (!this.hasUnsavedChanges) return close(); frappe.confirm("Discard unsaved changes to this saved Stock Transfer draft?", close); },
		syncPageFromDraftPreview(result) { if (!result) return; if (result.posting_date) this.values.posting_date = result.posting_date; if (Object.prototype.hasOwnProperty.call(result, "remarks")) this.values.remarks = result.remarks || ""; if (Array.isArray(result.editable_items)) this.values.items = result.editable_items.map((row) => ({ name: row.name || "", item_code: row.item_code || "", qty: row.qty })); },
		openCompletion() { if (this.savedDocument?.name) { this.editingSavedDraft = false; this.completionOpen = true; } },
		handleCompletionChanged(result) { if (!result?.name) return; this.savedDocument = { ...this.savedDocument, ...result, doctype: "Stock Entry" }; if (Number(result.docstatus || 0) === 0) { this.syncPageFromDraftPreview(result); this.initialSnapshot = JSON.stringify(this.values); } },
		handleCompletionCompleted(result) {
			this.editingSavedDraft = false;
			if (result?.name) this.savedDocument = { ...this.savedDocument, ...result, doctype: "Stock Entry" };
			this.completionOpen = false;
		},
		async startAnother() { this.savedDocument = null; this.editingSavedDraft = false; this.recoveryCandidate = null; this.loaded = false; await this.loadPage(); },
		openAdvancedNative() { if (!this.canUseNativeDesk) return; const go = () => frappe.new_doc("Stock Entry", { purpose: "Material Transfer" }); if (!this.hasUnsavedChanges) return go(); frappe.confirm("Open the advanced ERPNext Stock Entry form? Save this page first if you want the current transfer recorded.", go); },
	},
};
</script>

<style scoped>
.transaction-page-content,.transaction-form{display:grid;gap:18px}.transaction-page-content{padding-bottom:28px}.transaction-form,.recovery-panel,.notice-panel,.saved-panel{padding:18px;border:1px solid var(--edge-color-border,var(--edge-border,#dfe3e8));border-radius:12px;background:var(--edge-color-surface,#fff)}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.recovery-panel>div:first-child,.saved-panel>div:first-child,.sticky-actions>div:first-child{display:grid;gap:4px}.notice-panel{display:grid;gap:4px}.notice-panel p,.saved-panel p,.items-heading p,.sticky-actions small{margin:0;color:var(--edge-color-ink-500,#667085)}.page-kicker{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--edge-color-brand-600,#2563eb)}.context-cards{display:flex;flex-wrap:wrap;gap:10px}.context-cards>div{display:grid;gap:2px;min-width:180px;padding:9px 12px;border:1px solid var(--edge-color-border,#e5e7eb);border-radius:8px;background:var(--edge-color-surface-muted,#f8fafc)}.context-cards span,.field span{font-size:.78rem;color:var(--edge-color-ink-500,#667085)}.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.field{display:grid;gap:6px}.field span{font-weight:600}.hint{margin:-8px 0 0;font-size:.8rem;color:var(--edge-color-ink-500,#667085)}.form-error,.form-warning{padding:10px 12px;border-radius:8px}.form-error{border:1px solid var(--edge-color-danger,#d92d20);color:var(--edge-color-danger,#b42318);background:var(--edge-color-danger-subtle,#fef3f2)}.form-warning{border:1px solid var(--edge-color-warning,#f79009);background:var(--edge-color-warning-subtle,#fffaeb)}.items-heading h3{margin:3px 0 4px}.item-count{white-space:nowrap;font-size:.8rem;font-weight:700;padding:6px 9px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:999px}.sticky-actions{position:sticky;bottom:0;z-index:5;padding:14px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:10px;background:color-mix(in srgb,var(--edge-color-surface,#fff) 94%,transparent);backdrop-filter:blur(8px)}.page-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}@media(max-width:760px){.field-grid{grid-template-columns:1fr}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{align-items:stretch;flex-direction:column}.page-actions{justify-content:flex-start}}
</style>
