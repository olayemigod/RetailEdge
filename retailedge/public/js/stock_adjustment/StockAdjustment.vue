<template>
	<EdgeAppShell
		product="retailedge"
		title="Stock Adjustment"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/stock-adjustment"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-stock-adjustment-page">
			<EdgePageHeader
				title="Stock Adjustment"
				description="Use this full-page stock-count workspace for larger physical counts. Quick Adjustment remains available for short corrections."
			/>
			<EdgeLoadingState v-if="loading && !loaded" message="Preparing stock adjustment..." :skeleton="true" />
			<EdgeErrorState v-else-if="loadError" title="Stock Adjustment unavailable" :message="loadError" @retry="loadPage" />

			<div v-else class="transaction-page-content">
				<section v-if="recoveryCandidate" class="edge-panel recovery-panel">
					<div><strong>Unsaved stock count found</strong><small>{{ recoverySummary }}</small></div>
					<div class="page-actions"><button class="edge-button edge-button--primary" type="button" @click="restoreRecovery">Restore</button><button class="edge-button" type="button" @click="discardRecovery">Discard</button></div>
				</section>
				<section v-if="handoffNotice" class="edge-panel notice-panel"><strong>Continued from Quick Adjustment</strong><p>{{ handoffNotice }}</p></section>

				<section v-if="savedDocument" class="edge-panel saved-panel">
					<div><span class="page-kicker">{{ Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved" }}</span><h3>{{ savedDocument.name }}</h3><p>{{ Number(savedDocument.docstatus || 0) === 1 ? "ERPNext has submitted the Stock Reconciliation and owns the posted stock correction." : "The ERPNext Stock Reconciliation draft now owns this stock count." }}</p></div>
					<div class="page-actions"><button v-if="Number(savedDocument.docstatus || 0) === 0" class="edge-button edge-button--primary" type="button" @click="completionOpen = true">Edit / Complete</button><button class="edge-button" type="button" @click="startAnother">Start Another Count</button></div>
				</section>

				<form v-else class="edge-panel transaction-form" @submit.prevent="saveDraft">
					<div class="context-cards">
						<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
						<div v-if="values.branch"><span>Branch</span><strong>{{ values.branch }}</strong></div>
						<div><span>Purpose</span><strong>Physical Stock Reconciliation</strong></div>
					</div>
					<div v-if="saveError" class="form-error" role="alert">{{ saveError }}</div>

					<div class="field-grid">
						<EdgeInput v-model="values.posting_date" id="stock-adjustment-posting-date" label="Posting Date" type="date" required />
						<EdgeLinkField v-if="branchEnabled" :modelValue="values.branch" label="Branch" placeholder="Search permitted branch" :searcher="searchBranch" :context="searchContext" @update:modelValue="setBranch" />
						<EdgeLinkField :modelValue="values.warehouse" label="Stock Location" placeholder="Search permitted stock location" :required="true" :searcher="searchWarehouse" :context="searchContext" @update:modelValue="setWarehouse" />
					</div>

					<div class="items-heading"><div><span class="page-kicker">Physical count</span><h3>Counted items</h3><p>Enter the quantity physically counted. Zero is valid; negative physical quantities are not.</p></div><span class="item-count">{{ populatedItemCount }} item{{ populatedItemCount === 1 ? "" : "s" }}</span></div>
					<EdgeChildTable :field="itemTableField" :rows="values.items" :columns="itemColumns" :addLabel="'Add Item'" :linkSearcher="searchLineLink" :newRowsFirst="true" @update:rows="updateItems" />
					<p class="hint">Valuation fields remain hidden. Serial-numbered or batch-managed items may require Advanced ERPNext review so stock truth is preserved.</p>

					<div class="sticky-actions">
						<div><strong>{{ hasUnsavedChanges ? "Unsaved changes" : "Ready" }}</strong><small>{{ hasUnsavedChanges ? "A temporary browser-session recovery copy is retained until the ERPNext draft is saved." : "Complete the count, then save the draft." }}</small></div>
						<div class="page-actions"><button v-if="canUseNativeDesk" class="edge-button" type="button" :disabled="saving" @click="openAdvancedNative">Advanced: ERPNext</button><button class="edge-button" type="button" :disabled="saving" @click="resetForm">Reset</button><button class="edge-button edge-button--primary" type="submit" :disabled="saving || loading">{{ saving ? "Saving..." : formContext.submit_label || "Save Draft" }}</button></div>
					</div>
				</form>
			</div>

			<StandardStockCompletionDialog :open="completionOpen" :document="savedDocument" :canUseNativeDesk="canUseNativeDesk" @close="completionOpen = false" @changed="handleCompletionChanged" @completed="handleCompletionCompleted" />
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import { callMethod, errorMessage, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import StandardStockCompletionDialog from "../retailedge_business_hub/StandardStockCompletionDialog.vue";

const CONTEXT_METHOD = "retailedge.guided_stock_adjustment.get_simple_stock_adjustment_context";
const SEARCH_METHOD = "retailedge.guided_stock_adjustment.search_simple_stock_adjustment_options";
const CREATE_METHOD = "retailedge.guided_stock_adjustment.create_simple_stock_adjustment_draft";
const SHELL_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const HANDOFF_PREFIX = "retailedge:stock-adjustment:handoff:";
const RECOVERY_PREFIX = "retailedge:stock-adjustment:recovery:";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() { return { company: "", posting_date: "", branch: "", warehouse: "", items: [{ item_code: "", qty: "" }] }; }
function clone(value) { return JSON.parse(JSON.stringify(value || {})); }
function stored(raw, maxAge) {
	if (!raw) return null;
	try { const value = JSON.parse(raw); return value?.createdAt && Date.now() - Number(value.createdAt) <= maxAge && value.values ? value : null; } catch (_error) { return null; }
}

export default {
	name: "RetailEdgeStockAdjustment",
	components: { EdgeAppShell: runtime.EdgeAppShell, EdgePageLayout: runtime.EdgePageLayout, EdgePageHeader: runtime.EdgePageHeader, EdgeLoadingState: runtime.EdgeLoadingState, EdgeErrorState: runtime.EdgeErrorState, EdgeLinkField: runtime.EdgeLinkField, EdgeInput: runtime.EdgeInput, EdgeChildTable: runtime.EdgeChildTable, StandardStockCompletionDialog },
	data() {
		return {
			loading: false, loaded: false, saving: false, loadError: "", saveError: "", cascadeToken: 0, formContext: {}, values: emptyValues(), initialSnapshot: "",
			recoveryCandidate: null, handoffNotice: "", recoveryTimer: null, savedDocument: null, completionOpen: false,
			tenantName: "", branchName: "", userName: "", menuItems: [], canUseNativeDesk: false,
			itemTableField: { label: "Physical Counts", description: "Use the page for larger counts with many stock lines." },
			itemColumns: [{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search stock item" }, { fieldname: "qty", label: "Physical Qty", fieldtype: "Float", default: "" }],
		};
	},
	computed: {
		branchEnabled() { return Boolean(this.formContext.capabilities?.branch_enabled); },
		searchContext() { return { company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse }; },
		hasUnsavedChanges() { return Boolean(this.initialSnapshot && JSON.stringify(this.values) !== this.initialSnapshot); },
		populatedItemCount() { return (this.values.items || []).filter((row) => row?.item_code).length; },
		recoverySummary() { const v = this.recoveryCandidate?.values || {}; const count = (v.items || []).filter((row) => row?.item_code).length; return `${count} counted item${count === 1 ? "" : "s"}${v.warehouse ? ` at ${v.warehouse}` : ""}.`; },
	},
	watch: { values: { deep: true, handler() { if (this.loaded && !this.savedDocument) this.scheduleRecovery(); } } },
	created() {
		this._pageShow = () => { if (!this.loaded && !this.loading) this.loadPage(); };
		this._beforeUnload = (event) => { if (!this.hasUnsavedChanges || this.saving || this.savedDocument) return; event.preventDefault(); event.returnValue = ""; };
	},
	mounted() { window.addEventListener("retailedge-stock-adjustment-page-show", this._pageShow); window.addEventListener("beforeunload", this._beforeUnload); this.loadPage(); },
	beforeUnmount() { window.removeEventListener("retailedge-stock-adjustment-page-show", this._pageShow); window.removeEventListener("beforeunload", this._beforeUnload); if (this.recoveryTimer) clearTimeout(this.recoveryTimer); },
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
			} catch (error) { this.loadError = errorMessage(error, "Unable to prepare Stock Adjustment."); }
			finally { this.loading = false; }
		},
		applyShell(shell) {
			const c = shell.context || {}; this.tenantName = c.company_label || c.company || ""; this.branchName = c.branch || ""; this.userName = c.user_name || "";
			this.canUseNativeDesk = Boolean(shell.access?.can_use_native_desk) && shell.feature_flags?.native_document_fallback_enabled !== false;
			this.menuItems = (shell.navigation_groups || []).map((g) => ({ ...g, items: (g.items || []).map((i) => ({ ...i, route: this.routeForTarget(i) })).filter((i) => i.route) })).filter((g) => g.items.length);
		},
		routeForTarget(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return ""; if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; return item.target || ""; },
		handleNavigation(route) { if (!route || route === "/app/stock-adjustment") return; const go = () => { if (/^https?:\/\//i.test(route)) window.location.assign(route); else frappe.set_route(...String(route).replace(/^\/app\//, "").split("/").filter(Boolean)); }; if (!this.hasUnsavedChanges || this.savedDocument) return go(); frappe.confirm("Leave Stock Adjustment? Unsaved changes are retained temporarily in this browser session.", go); },
		recoveryKey() { return `${RECOVERY_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		handoffKey() { return `${HANDOFF_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		consumeHandoff() { let raw = ""; try { raw = sessionStorage.getItem(this.handoffKey()) || ""; sessionStorage.removeItem(this.handoffKey()); } catch (_error) { return false; } const payload = stored(raw, 10 * 60 * 1000); if (!payload) return false; if (payload.values.company && this.values.company && payload.values.company !== this.values.company) return false; this.values = { ...this.values, ...clone(payload.values), items: (payload.values.items || this.values.items).map((row) => ({ ...row })) }; this.handoffNotice = "Branch, stock location and count lines were carried into the full-page workspace."; return true; },
		loadRecoveryCandidate() { let raw = ""; try { raw = sessionStorage.getItem(this.recoveryKey()) || ""; } catch (_error) { return; } const payload = stored(raw, 12 * 60 * 60 * 1000); if (payload && (!payload.values.company || !this.values.company || payload.values.company === this.values.company)) this.recoveryCandidate = payload; },
		async restoreRecovery() {
			if (!this.recoveryCandidate?.values) return;
			const recovered = clone(this.recoveryCandidate.values);
			this.values = { ...this.values, ...recovered, items: (recovered.items || []).map((row) => ({ ...row })) };
			this.recoveryCandidate = null; this.saveError = "";
			try {
				if (this.values.company && (this.values.branch || this.values.warehouse)) {
					const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch || "", warehouse: this.values.warehouse || "", preference: "source" });
					this.values.branch = r.branch || this.values.branch || "";
					this.values.warehouse = r.warehouse || this.values.warehouse || "";
				}
				this.handoffNotice = "Recovered unsaved stock-count work and revalidated its current Branch / Stock Location access.";
			} catch (error) {
				this.values.branch = ""; this.values.warehouse = "";
				this.saveError = errorMessage(error, "The recovered Branch or Stock Location is no longer available. Choose the current stock context before saving.");
				this.handoffNotice = "Recovered counted items, but the saved Branch / Stock Location was cleared because access could not be revalidated.";
			}
		},
		discardRecovery() { this.recoveryCandidate = null; this.clearRecovery(); },
		scheduleRecovery() { if (this.recoveryTimer) clearTimeout(this.recoveryTimer); this.recoveryTimer = setTimeout(() => { if (!this.hasUnsavedChanges || this.savedDocument) return this.clearRecovery(); try { sessionStorage.setItem(this.recoveryKey(), JSON.stringify({ createdAt: Date.now(), values: clone(this.values) })); } catch (_error) {} }, 250); },
		clearRecovery() { try { sessionStorage.removeItem(this.recoveryKey()); } catch (_error) {} },
		resetForm() { const reset = () => { this.clearRecovery(); this.values = { ...emptyValues(), ...(this.formContext.defaults || {}), items: (this.formContext.defaults?.items || emptyValues().items).map((row) => ({ ...row })) }; this.initialSnapshot = JSON.stringify(this.values); this.saveError = ""; }; if (!this.hasUnsavedChanges) return reset(); frappe.confirm("Discard the unsaved stock adjustment changes?", reset); },
		async searchOptions(fieldname, query) { const rows = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values: { ...this.values, items: undefined }, limit: 20 }); return Array.isArray(rows) ? rows : []; },
		searchBranch(query) { return this.searchOptions("branch", query); }, searchWarehouse(query) { return this.searchOptions("warehouse", query); }, searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		async setBranch(next) { const branch = next || ""; this.values.branch = branch; this.values.warehouse = ""; if (!branch || !this.values.company) return; const token = ++this.cascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "source" }); if (token !== this.cascadeToken) return; this.values.branch = r.branch || branch; this.values.warehouse = r.warehouse || ""; } catch (error) { if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch stock location."); } },
		async setWarehouse(next) { const warehouse = next || ""; this.values.warehouse = warehouse; if (!warehouse || !this.values.company) return; const token = ++this.cascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, warehouse, preference: "source" }); if (token !== this.cascadeToken) return; this.values.branch = r.branch || this.values.branch; this.values.warehouse = r.warehouse || warehouse; } catch (error) { if (token === this.cascadeToken) { this.values.warehouse = ""; this.saveError = errorMessage(error, "Unable to use the selected Stock Location."); } } },
		updateItems(rows) { this.values.items = Array.isArray(rows) ? rows.map((row) => ({ ...row })) : []; },
		async saveDraft() {
			if (this.saving || this.loading) return;
			if (!this.values.company || !this.values.warehouse) { this.saveError = "Company and Stock Location are required."; return; }
			const rows = (this.values.items || []).filter((row) => row?.item_code);
			if (!rows.length) { this.saveError = "Add at least one counted Item."; return; }
			if (rows.some((row) => row.qty === "" || row.qty === null || row.qty === undefined || Number(row.qty) < 0)) { this.saveError = "Each counted Item needs a physical quantity of zero or more."; return; }
			this.saving = true; this.saveError = "";
			try { const result = await callMethod(CREATE_METHOD, { values: { ...this.values, items: rows } }); if (!result?.name) throw new Error("Stock Reconciliation draft was not returned."); this.clearRecovery(); this.initialSnapshot = JSON.stringify(this.values); this.savedDocument = { doctype: result.doctype || "Stock Reconciliation", name: result.name }; this.completionOpen = true; frappe.show_alert?.({ message: `Stock Adjustment ${result.name} saved as Draft`, indicator: "green" }); }
			catch (error) { this.saveError = errorMessage(error, "Stock Adjustment could not be saved."); }
			finally { this.saving = false; }
		},
		handleCompletionChanged() {},
		handleCompletionCompleted(result) {
			if (result?.name) this.savedDocument = { ...this.savedDocument, ...result, doctype: "Stock Reconciliation" };
			this.completionOpen = false;
		},
		async startAnother() { this.savedDocument = null; this.recoveryCandidate = null; this.loaded = false; await this.loadPage(); },
		openAdvancedNative() { if (!this.canUseNativeDesk) return; const go = () => frappe.new_doc("Stock Reconciliation"); if (!this.hasUnsavedChanges) return go(); frappe.confirm("Open the advanced ERPNext Stock Reconciliation form? Save this page first if you want the current count recorded.", go); },
	},
};
</script>

<style scoped>
.transaction-page-content,.transaction-form{display:grid;gap:18px}.transaction-page-content{padding-bottom:28px}.transaction-form,.recovery-panel,.notice-panel,.saved-panel{padding:18px;border:1px solid var(--edge-color-border,var(--edge-border,#dfe3e8));border-radius:12px;background:var(--edge-color-surface,#fff)}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.recovery-panel>div:first-child,.saved-panel>div:first-child,.sticky-actions>div:first-child{display:grid;gap:4px}.notice-panel{display:grid;gap:4px}.notice-panel p,.saved-panel p,.items-heading p,.sticky-actions small{margin:0;color:var(--edge-color-ink-500,#667085)}.page-kicker{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--edge-color-brand-600,#2563eb)}.context-cards{display:flex;flex-wrap:wrap;gap:10px}.context-cards>div{display:grid;gap:2px;min-width:180px;padding:9px 12px;border:1px solid var(--edge-color-border,#e5e7eb);border-radius:8px;background:var(--edge-color-surface-muted,#f8fafc)}.context-cards span,.field span{font-size:.78rem;color:var(--edge-color-ink-500,#667085)}.field-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.field{display:grid;gap:6px}.field span{font-weight:600}.hint{margin:-8px 0 0;font-size:.8rem;color:var(--edge-color-ink-500,#667085)}.form-error{padding:10px 12px;border:1px solid var(--edge-color-danger,#d92d20);border-radius:8px;color:var(--edge-color-danger,#b42318);background:var(--edge-color-danger-subtle,#fef3f2)}.items-heading h3{margin:3px 0 4px}.item-count{white-space:nowrap;font-size:.8rem;font-weight:700;padding:6px 9px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:999px}.sticky-actions{position:sticky;bottom:0;z-index:5;padding:14px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:10px;background:color-mix(in srgb,var(--edge-color-surface,#fff) 94%,transparent);backdrop-filter:blur(8px)}.page-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}@media(max-width:760px){.field-grid{grid-template-columns:1fr}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{align-items:stretch;flex-direction:column}.page-actions{justify-content:flex-start}}
</style>
