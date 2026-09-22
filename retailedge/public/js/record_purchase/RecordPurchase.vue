<template>
	<EdgeAppShell
		product="retailedge"
		title="Record Purchase"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/record-purchase"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-record-purchase-page">
			<EdgePageHeader
				title="Record Purchase"
				description="Use this full-page workspace for purchases with longer item lists. Quick Purchase remains available for short entries."
			/>
			<EdgeLoadingState v-if="loading && !loaded" message="Preparing purchase entry..." :skeleton="true" />
			<EdgeErrorState v-else-if="loadError" title="Record Purchase unavailable" :message="loadError" @retry="loadPage" />

			<div v-else class="transaction-page-content">
				<section v-if="recoveryCandidate" class="edge-panel recovery-panel">
					<div><strong>Unsaved purchase found</strong><small>{{ recoverySummary }}</small></div>
					<div class="page-actions"><button class="edge-button edge-button--primary" type="button" @click="restoreRecovery">Restore</button><button class="edge-button" type="button" @click="discardRecovery">Discard</button></div>
				</section>
				<section v-if="handoffNotice" class="edge-panel notice-panel"><strong>Continued from Quick Purchase</strong><p>{{ handoffNotice }}</p></section>

				<section v-if="savedDocument && !editingSavedDraft" class="edge-panel saved-panel">
					<div><span class="page-kicker">{{ Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved" }}</span><h3>{{ savedDocument.name }}</h3><p>{{ Number(savedDocument.docstatus || 0) === 1 ? "ERPNext has submitted the Purchase Invoice. Continue to supplier settlement, payables review or document output." : "The ERPNext Purchase Invoice draft now owns the transaction." }}</p></div>
					<div class="page-actions">
						<button v-if="Number(savedDocument.docstatus || 0) === 0" class="edge-button edge-button--primary" type="button" @click="beginSavedDraftEdit">Continue Editing on Page</button><button v-if="Number(savedDocument.docstatus || 0) === 0" class="edge-button" type="button" @click="openCompletion">Review / Complete</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('pay-supplier')" class="edge-button edge-button--primary" type="button" @click="runSavedNextAction('pay-supplier')">Pay Supplier</button><button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('create-supplier-debit-note')" class="edge-button" type="button" @click="runSavedNextAction('create-supplier-debit-note')">Supplier Debit Note</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1" class="edge-button" type="button" @click="runSavedNextAction('supplier-payables')">Supplier Payables</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1" class="edge-button" type="button" @click="runSavedNextAction('output')">Print / Share</button>
						<button class="edge-button" type="button" @click="startAnother">Start Another Purchase</button>
					</div>
				</section>

				<form v-if="!savedDocument || editingSavedDraft" class="edge-panel transaction-form" @submit.prevent="saveDraft">
					<div class="context-cards">
						<div><span>Company</span><strong>{{ values.company || "Not set" }}</strong></div>
						<div v-if="values.branch"><span>Branch</span><strong>{{ values.branch }}</strong></div>
						<div><span>Buying Price List</span><strong>{{ pricingLabel }}</strong><small>{{ pricingSourceLabel }}</small></div>
					</div>

					<div v-if="saveError" class="form-error" role="alert">{{ saveError }}</div>
					<div v-else-if="stockContextMessage" class="form-warning" role="status">{{ stockContextMessage }}</div>

					<div class="field-grid">
						<EdgeLinkField :modelValue="values.supplier" label="Supplier" placeholder="Search supplier" :required="true" :searcher="searchSupplier" :context="searchContext" :canCreate="!editingSavedDraft && canCreateSupplier" :creator="createSupplier" createLabel="Create Supplier" :disabled="editingSavedDraft" @update:modelValue="setSupplier" />
						<EdgeInput v-model="values.posting_date" id="record-purchase-posting-date" label="Posting Date" type="date" required />
						<EdgeLinkField v-if="branchEnabled" :modelValue="values.branch" label="Branch" placeholder="Search branch" :searcher="searchBranch" :context="searchContext" :disabled="editingSavedDraft" @update:modelValue="setBranch" />
						<EdgeLinkField :modelValue="values.warehouse" label="Receiving Stock Location" placeholder="Search receiving stock location" :required="Boolean(values.update_stock)" :disabled="editingSavedDraft || (requiresBranchSelection && !values.branch)" :searcher="searchWarehouse" :context="searchContext" @update:modelValue="setWarehouse" />
						<EdgeInput v-model="values.bill_no" id="record-purchase-bill-no" label="Supplier Bill No" type="text" placeholder="Supplier invoice/reference" />
						<EdgeInput v-if="values.bill_no" v-model="values.bill_date" id="record-purchase-bill-date" label="Supplier Bill Date" type="date" />
					</div>

					<label class="check-field"><input v-model="values.update_stock" type="checkbox" :true-value="1" :false-value="0" /><span><strong>Update Stock</strong><small>Add received stock when this Purchase Invoice is submitted.</small></span></label>

					<div class="items-heading"><div><span class="page-kicker">Purchase items</span><h3>Products and services</h3><p>Use the page for larger purchases instead of keeping a long transaction inside a modal.</p></div><span class="item-count">{{ populatedItemCount }} item{{ populatedItemCount === 1 ? "" : "s" }}</span></div>
					<EdgeChildTable :field="itemTableField" :rows="values.items" :columns="itemColumns" :addLabel="'Add Item'" :linkSearcher="searchLineLink" :linkCanCreate="canCreateItemLink" :linkCreator="createItemLink" :linkCreateLabel="itemCreateLabel" :newRowsFirst="true" @update:rows="updateItems" />
					<p class="hint">Buying rates follow the assigned Buying Price List and ERPNext buying defaults. The server validates all rates and stock context again before saving.</p>
					<label class="field"><span>Remarks</span><textarea v-model="values.remarks" class="form-control" rows="4" placeholder="Optional purchase note"></textarea></label>

					<div class="sticky-actions">
						<div><strong>{{ hasUnsavedChanges ? "Unsaved changes" : "Ready" }}</strong><small>{{ hasUnsavedChanges ? "A temporary browser-session recovery copy is retained until the ERPNext draft is saved." : "Complete the required fields, then save the draft." }}</small></div>
						<div class="page-actions"><button v-if="canUseNativeDesk" class="edge-button" type="button" :disabled="saving" @click="openAdvancedNative">Advanced: ERPNext</button><button v-if="editingSavedDraft" class="edge-button" type="button" :disabled="saving" @click="cancelSavedDraftEdit">Cancel Edit</button><button v-else class="edge-button" type="button" :disabled="saving" @click="resetForm">Reset</button><button class="edge-button edge-button--primary" type="submit" :disabled="saving || loading || !transactionContextReady">{{ saving ? "Saving..." : (editingSavedDraft ? "Update Draft" : (formContext.submit_label || "Save Draft")) }}</button></div>
					</div>
				</form>
			</div>

			<StandardPurchaseInvoiceCompletionDialog :open="completionOpen" :document="savedDocument" :canUseNativeDesk="canUseNativeDesk" :showNextActions="true" @close="completionOpen = false" @changed="handleCompletionChanged" @completed="handleCompletionCompleted" @next-action="handleCompletionNextAction" />
			<SimplePaymentDialog :open="paymentOpen" intent="pay-supplier" :initialContext="paymentInitialContext" :nativeFallbackEnabled="canUseNativeDesk" @close="closePayment" @saved="closePayment" />
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import { callMethod, errorMessage, quickCreateItem, quickCreateSupplier, resolveBranchWarehouse } from "../retailedge_business_hub/guidedEntryUtils";
import StandardPurchaseInvoiceCompletionDialog from "../professional_purchasing/StandardPurchaseInvoiceCompletionDialog.vue";
import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue";

const CONTEXT_METHOD = "retailedge.guided_purchase_invoice.get_simple_purchase_invoice_context";
const SEARCH_METHOD = "retailedge.guided_purchase_invoice.search_simple_purchase_invoice_options";
const PRICING_METHOD = "retailedge.guided_purchase_invoice.get_simple_purchase_invoice_item_pricing";
const CREATE_METHOD = "retailedge.guided_purchase_invoice.create_simple_purchase_invoice_draft";
const UPDATE_METHOD = "retailedge.standard_purchase_invoice_completion.update_standard_purchase_invoice_draft";
const SHELL_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const HANDOFF_PREFIX = "retailedge:record-purchase:handoff:";
const RECOVERY_PREFIX = "retailedge:record-purchase:recovery:";
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return { company: "", branch: "", posting_date: "", bill_no: "", bill_date: "", warehouse: "", supplier: "", update_stock: 0, remarks: "", items: [{ item_code: "", qty: 1, rate: "" }] };
}
function sourceLabel(source) {
	return { user_default: "User default", user_permission: "User-assigned Price List", party_default: "Supplier default", erpnext_default: "ERPNext default", standard_price_list: "Standard Buying", item_fallback: "Item fallback" }[source] || "ERPNext pricing";
}
function clone(value) { return JSON.parse(JSON.stringify(value || {})); }
function stored(raw, maxAge) {
	if (!raw) return null;
	try { const value = JSON.parse(raw); return value?.createdAt && Date.now() - Number(value.createdAt) <= maxAge && value.values ? value : null; } catch (_error) { return null; }
}

export default {
	name: "RetailEdgeRecordPurchase",
	components: { EdgeAppShell: runtime.EdgeAppShell, EdgePageLayout: runtime.EdgePageLayout, EdgePageHeader: runtime.EdgePageHeader, EdgeLoadingState: runtime.EdgeLoadingState, EdgeErrorState: runtime.EdgeErrorState, EdgeLinkField: runtime.EdgeLinkField, EdgeInput: runtime.EdgeInput, EdgeChildTable: runtime.EdgeChildTable, StandardPurchaseInvoiceCompletionDialog, SimplePaymentDialog },
	data() {
		return {
			loading: false, loaded: false, saving: false, loadError: "", saveError: "", formContext: {}, values: emptyValues(), initialSnapshot: "", cascadeToken: 0,
			pricingTokens: {}, pricingCache: new Map(), recoveryCandidate: null, handoffNotice: "", recoveryTimer: null, savedDocument: null, editingSavedDraft: false, completionOpen: false,
			paymentOpen: false, paymentInitialContext: {},
			tenantName: "", branchName: "", userName: "", menuItems: [], canUseNativeDesk: false,
			itemTableField: { label: "Items", description: "Use this full-page table for purchases with many lines." },
			itemColumns: [{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" }, { fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 }, { fieldname: "rate", label: "Buying Rate", fieldtype: "Currency", placeholder: "Auto buying price" }],
		};
	},
	computed: {
		branchEnabled() { return Boolean(this.formContext.capabilities?.branch_enabled); },
		requiresBranchSelection() { return Boolean(this.formContext.capabilities?.requires_branch_selection); },
		transactionContextReady() { if (!this.values.update_stock) return true; if (this.requiresBranchSelection && !this.values.branch) return false; return Boolean(this.values.warehouse); },
		stockContextMessage() { if (!this.values.update_stock) return ""; if (this.requiresBranchSelection && !this.values.branch) return "Choose a Branch before selecting the Receiving Stock Location."; if (!this.values.warehouse) return "Choose a Receiving Stock Location before saving this stock-updating purchase."; return ""; },
		canCreateSupplier() { return Boolean(this.formContext.capabilities?.can_create_supplier); },
		canCreateItem() { return Boolean(this.formContext.capabilities?.can_create_item); },
		pricingLabel() { return this.formContext.pricing?.price_list || "Item buying fallback"; },
		pricingSourceLabel() { return sourceLabel(this.formContext.pricing?.source); },
		searchContext() { return { company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse, supplier: this.values.supplier }; },
		hasUnsavedChanges() { return Boolean(this.initialSnapshot && JSON.stringify(this.values) !== this.initialSnapshot); },
		populatedItemCount() { return (this.values.items || []).filter((row) => row?.item_code).length; },
		recoverySummary() { const v = this.recoveryCandidate?.values || {}; const count = (v.items || []).filter((row) => row?.item_code).length; return `${v.supplier ? `Supplier: ${v.supplier}. ` : ""}${count} item${count === 1 ? "" : "s"} entered.`; },
	},
	watch: { values: { deep: true, handler() { if (this.loaded && !this.savedDocument) this.scheduleRecovery(); } } },
	created() {
		this._pageShow = () => { if (!this.loaded && !this.loading) this.loadPage(); };
		this._beforeUnload = (event) => { if (!this.hasUnsavedChanges || this.saving || (this.savedDocument && !this.editingSavedDraft)) return; event.preventDefault(); event.returnValue = ""; };
	},
	mounted() { window.addEventListener("retailedge-record-purchase-page-show", this._pageShow); window.addEventListener("beforeunload", this._beforeUnload); this.loadPage(); },
	beforeUnmount() { window.removeEventListener("retailedge-record-purchase-page-show", this._pageShow); window.removeEventListener("beforeunload", this._beforeUnload); if (this.recoveryTimer) window.clearTimeout(this.recoveryTimer); },
	methods: {
		async loadPage() {
			if (this.loading) return;
			this.loading = true; this.loadError = ""; this.saveError = ""; this.savedDocument = null; this.completionOpen = false; this.pricingCache.clear();
			try {
				const [data, shell] = await Promise.all([callMethod(CONTEXT_METHOD), callMethod(SHELL_METHOD)]);
				this.formContext = data || {}; this.applyShell(shell || {}); this.applyDefaults(data?.defaults || {});
				if (!this.consumeHandoff()) this.loadRecoveryCandidate();
				this.loaded = true;
			} catch (error) { this.loadError = errorMessage(error, "Unable to prepare Record Purchase."); }
			finally { this.loading = false; }
		},
		applyDefaults(defaults) { this.values = { ...emptyValues(), ...(defaults || {}), items: (defaults?.items || emptyValues().items).map((row) => ({ ...row })) }; this.initialSnapshot = JSON.stringify(this.values); },
		applyShell(shell) {
			const c = shell.context || {}; this.tenantName = c.company_label || c.company || ""; this.branchName = c.branch || ""; this.userName = c.user_name || "";
			this.canUseNativeDesk = Boolean(shell.access?.can_use_native_desk) && shell.feature_flags?.native_document_fallback_enabled !== false;
			this.menuItems = (shell.navigation_groups || []).map((g) => ({ ...g, items: (g.items || []).map((i) => ({ ...i, route: this.routeForTarget(i) })).filter((i) => i.route) })).filter((g) => g.items.length);
		},
		routeForTarget(item) { if (item.target_type === "Page") return `/app/${item.target}`; if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return ""; if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`; if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`; return item.target || ""; },
		handleNavigation(route) {
			if (!route || route === "/app/record-purchase") return;
			const go = () => { if (/^https?:\/\//i.test(route)) window.location.assign(route); else frappe.set_route(...String(route).replace(/^\/app\//, "").split("/").filter(Boolean)); };
			if (!this.hasUnsavedChanges || (this.savedDocument && !this.editingSavedDraft)) return go();
			frappe.confirm("Leave Record Purchase? Unsaved changes are retained temporarily in this browser session.", go);
		},
		recoveryKey() { return `${RECOVERY_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		handoffKey() { return `${HANDOFF_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`; },
		consumeHandoff() {
			let raw = ""; try { raw = sessionStorage.getItem(this.handoffKey()) || ""; sessionStorage.removeItem(this.handoffKey()); } catch (_error) { return false; }
			const payload = stored(raw, 10 * 60 * 1000); if (!payload) return false;
			if (payload.values.company && this.values.company && payload.values.company !== this.values.company) return false;
			this.values = { ...this.values, ...clone(payload.values), items: (payload.values.items || this.values.items).map((row) => ({ ...row })) };
			this.handoffNotice = "Supplier, context and item lines were carried into the full-page workspace."; return true;
		},
		loadRecoveryCandidate() { let raw = ""; try { raw = sessionStorage.getItem(this.recoveryKey()) || ""; } catch (_error) { return; } const payload = stored(raw, 12 * 60 * 60 * 1000); if (payload && (!payload.values.company || !this.values.company || payload.values.company === this.values.company)) this.recoveryCandidate = payload; },
		async restoreRecovery() {
			if (!this.recoveryCandidate?.values) return;
			const recovered = clone(this.recoveryCandidate.values);
			this.values = { ...this.values, ...recovered, items: (recovered.items || []).map((row) => ({ ...row })) };
			this.recoveryCandidate = null; this.saveError = "";
			try {
				if (this.values.company && (this.values.branch || this.values.warehouse)) {
					const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch || "", warehouse: this.values.warehouse || "", preference: "purchase" });
					this.values.branch = r.branch || this.values.branch || "";
					this.values.warehouse = r.warehouse || this.values.warehouse || "";
				}
				this.handoffNotice = "Recovered unsaved purchase work and revalidated its current Branch / Receiving Stock Location access.";
			} catch (error) {
				this.values.branch = ""; this.values.warehouse = "";
				this.saveError = errorMessage(error, "The recovered Branch or Receiving Stock Location is no longer available. Choose the current transaction context before saving.");
				this.handoffNotice = "Recovered purchase lines, but the saved Branch / Receiving Stock Location was cleared because access could not be revalidated.";
			}
		},
		discardRecovery() { this.recoveryCandidate = null; this.clearRecovery(); },
		scheduleRecovery() { if (this.recoveryTimer) clearTimeout(this.recoveryTimer); this.recoveryTimer = setTimeout(() => { if (!this.hasUnsavedChanges || this.savedDocument) return this.clearRecovery(); try { sessionStorage.setItem(this.recoveryKey(), JSON.stringify({ createdAt: Date.now(), values: clone(this.values) })); } catch (_error) {} }, 250); },
		clearRecovery() { try { sessionStorage.removeItem(this.recoveryKey()); } catch (_error) {} },
		resetForm() { const reset = () => { this.clearRecovery(); this.applyDefaults(this.formContext.defaults || {}); this.saveError = ""; }; if (!this.hasUnsavedChanges) return reset(); frappe.confirm("Discard the unsaved purchase changes?", reset); },
		async searchOptions(fieldname, query) { const rows = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values: { company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse, supplier: this.values.supplier } }); return Array.isArray(rows) ? rows : []; },
		searchSupplier(query) { return this.searchOptions("supplier", query); }, searchBranch(query) { return this.searchOptions("branch", query); }, searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		createSupplier(query) { return quickCreateSupplier(query); }, canCreateItemLink(column) { return this.canCreateItem && column?.fieldname === "item_code"; }, createItemLink(column, query) { return column?.fieldname === "item_code" ? quickCreateItem(query) : Promise.resolve(null); }, itemCreateLabel(column) { return column?.fieldname === "item_code" ? "Create Item" : "Create new"; },
		setSupplier(next) { const changed = Boolean(this.values.supplier && this.values.supplier !== next); this.values.supplier = next || ""; this.pricingCache.clear(); if (changed) { this.values.items = this.values.items.map((row) => ({ ...row, rate: "" })); this.refreshAllItemPricing(); } },
		async setBranch(next) { const branch = next || ""; this.values.branch = branch; this.values.warehouse = ""; this.pricingCache.clear(); if (!branch || !this.values.company) return; const token = ++this.cascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "purchase" }); if (token !== this.cascadeToken) return; this.values.branch = r.branch || branch; this.values.warehouse = r.warehouse || ""; this.refreshAllItemPricing(); } catch (error) { if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch receiving stock location."); } },
		async setWarehouse(next) { const warehouse = next || ""; this.values.warehouse = warehouse; this.pricingCache.clear(); if (!warehouse || !this.values.company) return; const token = ++this.cascadeToken; try { const r = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, warehouse, preference: "purchase" }); if (token !== this.cascadeToken) return; this.values.branch = r.branch || this.values.branch; this.values.warehouse = r.warehouse || warehouse; this.refreshAllItemPricing(); } catch (error) { if (token === this.cascadeToken) { this.values.warehouse = ""; this.saveError = errorMessage(error, "Unable to use the selected Receiving Stock Location."); } } },
		updateItems(rows) { const previous = this.values.items || []; const changed = []; this.values.items = (rows || []).map((row, index) => { if (row.item_code && row.item_code !== previous[index]?.item_code) { changed.push(index); return { ...row, rate: "" }; } return { ...row }; }); changed.forEach((i) => this.loadItemPricing(i)); },
		pricingCacheKey(row) { return [this.values.company, this.values.branch, this.values.warehouse, this.values.supplier, this.values.posting_date, row.item_code, row.qty || 1].join("|"); },
		async loadItemPricing(index) { const row = this.values.items[index]; if (!row?.item_code || !this.values.supplier) return; const key = this.pricingCacheKey(row); const token = `${row.item_code}:${Date.now()}:${Math.random()}`; this.pricingTokens[index] = token; try { let result = this.pricingCache.get(key); if (!result) { result = await callMethod(PRICING_METHOD, { item_code: row.item_code, values: { company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse, supplier: this.values.supplier, posting_date: this.values.posting_date, qty: row.qty || 1 } }); this.pricingCache.set(key, result); } if (this.pricingTokens[index] !== token) return; if (result?.rate !== null && result?.rate !== undefined) this.values.items[index] = { ...this.values.items[index], rate: result.rate }; else this.saveError = `No buying price is configured for ${row.item_code}. Enter the agreed rate or configure Item Price.`; this.formContext.pricing = { ...(this.formContext.pricing || {}), price_list: result?.price_list || this.formContext.pricing?.price_list || "", source: result?.source || this.formContext.pricing?.source || "item_fallback" }; } catch (error) { if (this.pricingTokens[index] === token) this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`); } },
		refreshAllItemPricing() { if (!this.values.supplier) return; this.values.items.forEach((row, index) => { if (row.item_code) { this.values.items[index] = { ...row, rate: "" }; this.loadItemPricing(index); } }); },
		async saveDraft() {
			if (this.saving || this.loading || !this.transactionContextReady) return;
			this.saving = true; this.saveError = "";
			try {
				let result;
				if (this.savedDocument?.name && this.editingSavedDraft) {
					result = await callMethod(UPDATE_METHOD, {
						name: this.savedDocument.name,
						expected_modified: this.savedDocument.modified || "",
						source_mode: "direct",
						values: {
							posting_date: this.values.posting_date,
							bill_no: this.values.bill_no || "",
							bill_date: this.values.bill_date || "",
							remarks: this.values.remarks || "",
							items: (this.values.items || []).filter((row) => row?.item_code).map((row) => ({
								name: row.name || "",
								item_code: row.item_code,
								qty: Number(row.qty || 0),
								rate: row.rate,
							})),
						},
					}, "POST");
					this.syncPageFromDraftPreview(result);
					this.savedDocument = { ...this.savedDocument, ...result, doctype: "Purchase Invoice" };
					this.initialSnapshot = JSON.stringify(this.values);
					this.editingSavedDraft = false;
					frappe.show_alert?.({ message: `Purchase Invoice ${result.name} draft updated`, indicator: "green" });
					return;
				}
				result = await callMethod(CREATE_METHOD, { values: this.values });
				if (!result?.name) throw new Error("Purchase Invoice draft was not returned.");
				this.clearRecovery();
				this.initialSnapshot = JSON.stringify(this.values);
				this.savedDocument = { ...result, doctype: result.doctype || "Purchase Invoice" };
				this.completionOpen = false;
				frappe.show_alert?.({ message: `Purchase Invoice ${result.name} saved as Draft`, indicator: "green" });
			} catch (error) { this.saveError = errorMessage(error, "Unable to save the Purchase Invoice draft."); }
			finally { this.saving = false; }
		},
		beginSavedDraftEdit() {
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 0) return;
			this.editingSavedDraft = true; this.completionOpen = false; this.initialSnapshot = JSON.stringify(this.values);
		},
		cancelSavedDraftEdit() {
			const close = () => { try { this.values = JSON.parse(this.initialSnapshot || "{}"); } catch (_error) {} this.editingSavedDraft = false; this.saveError = ""; };
			if (!this.hasUnsavedChanges) return close();
			frappe.confirm("Discard unsaved changes to this saved Purchase Invoice draft?", close);
		},
		syncPageFromDraftPreview(result) {
			if (!result) return;
			if (result.posting_date) this.values.posting_date = result.posting_date;
			if (Object.prototype.hasOwnProperty.call(result, "bill_no")) this.values.bill_no = result.bill_no || "";
			if (Object.prototype.hasOwnProperty.call(result, "bill_date")) this.values.bill_date = result.bill_date || "";
			if (Object.prototype.hasOwnProperty.call(result, "remarks")) this.values.remarks = result.remarks || "";
			if (Array.isArray(result.editable_items)) this.values.items = result.editable_items.map((row) => ({ name: row.name || "", item_code: row.item_code || "", qty: row.qty, rate: row.rate }));
		},
		openCompletion() { if (this.savedDocument?.name) { this.editingSavedDraft = false; this.completionOpen = true; } },
		handleCompletionChanged(result) {
			if (!result?.name) return;
			this.savedDocument = { ...this.savedDocument, ...result, doctype: "Purchase Invoice" };
			if (Number(result.docstatus || 0) === 0) { this.syncPageFromDraftPreview(result); this.initialSnapshot = JSON.stringify(this.values); }
		},
		handleCompletionCompleted(result) { this.editingSavedDraft = false; if (result?.name) this.savedDocument = { ...this.savedDocument, ...result, doctype: "Purchase Invoice" }; },
		hasSavedNextAction(action) { return (this.savedDocument?.next_actions || []).some((row) => row?.value === action); },
		runSavedNextAction(action) { if (!this.savedDocument?.name) return; this.handleCompletionNextAction({ action, doctype: "Purchase Invoice", name: this.savedDocument.name, supplier: this.savedDocument.supplier || this.values.supplier || "", company: this.savedDocument.company || this.values.company || "", branch: this.savedDocument.branch || this.values.branch || "" }); },
		handleCompletionNextAction(payload) {
			if (!payload?.action || !payload?.name) return;
			this.completionOpen = false;
			if (payload.action === "pay-supplier") {
				this.paymentInitialContext = { company: payload.company || this.values.company || "", branch: payload.branch || this.values.branch || "", party: payload.supplier || this.values.supplier || "", reference_name: payload.name };
				this.paymentOpen = true;
				return;
			}
			if (payload.action === "create-supplier-debit-note") {
				window.retailedgeProfessionalPurchasingTarget = { action: "supplier-debit-note", source_name: payload.name };
				frappe.set_route("professional-purchasing");
				return;
			}
			if (payload.action === "supplier-payables") {
				const filters = { company: payload.company || this.values.company || "", branch: payload.branch || this.values.branch || "", supplier: payload.supplier || this.values.supplier || "" };
				const cleanFilters = Object.fromEntries(Object.entries(filters).filter(([, value]) => value));
				window.__retailedgeBusinessHubRouteHandoff = { target: "supplier-payables", filters: cleanFilters, createdAt: Date.now() };
				frappe.route_options = { ...cleanFilters, retailedge_business_hub_handoff: 1, retailedge_business_hub_target: "supplier-payables" };
				frappe.set_route("supplier-payables");
				return;
			}
			if (payload.action === "output") { window.retailedgeDocumentOutputTarget = { document: "purchase-invoice", name: payload.name, mode: "share" }; frappe.set_route("document-output-sharing"); }
		},
		closePayment() { this.paymentOpen = false; this.paymentInitialContext = {}; },
		async startAnother() { this.savedDocument = null; this.editingSavedDraft = false; this.recoveryCandidate = null; this.loaded = false; await this.loadPage(); },
		openAdvancedNative() { if (!this.canUseNativeDesk) return; const go = () => frappe.new_doc("Purchase Invoice"); if (!this.hasUnsavedChanges) return go(); frappe.confirm("Open the advanced ERPNext Purchase Invoice form? Save this page first if you want the current entries recorded.", go); },
	},
};
</script>

<style scoped>
.transaction-page-content,.transaction-form{display:grid;gap:18px}.transaction-page-content{padding-bottom:28px}.transaction-form,.recovery-panel,.notice-panel,.saved-panel{padding:18px;border:1px solid var(--edge-color-border,var(--edge-border,#dfe3e8));border-radius:12px;background:var(--edge-color-surface,#fff)}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{display:flex;align-items:center;justify-content:space-between;gap:16px}.recovery-panel>div:first-child,.saved-panel>div:first-child,.sticky-actions>div:first-child{display:grid;gap:4px}.notice-panel{display:grid;gap:4px}.notice-panel p,.saved-panel p,.items-heading p,.sticky-actions small{margin:0;color:var(--edge-color-ink-500,#667085)}.page-kicker{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.07em;color:var(--edge-color-brand-600,#2563eb)}.context-cards{display:flex;flex-wrap:wrap;gap:10px}.context-cards>div{display:grid;gap:2px;min-width:180px;padding:9px 12px;border:1px solid var(--edge-color-border,#e5e7eb);border-radius:8px;background:var(--edge-color-surface-muted,#f8fafc)}.context-cards span,.field span{font-size:.78rem;color:var(--edge-color-ink-500,#667085)}.context-cards small{font-size:.72rem;color:var(--edge-color-ink-500,#667085)}.field-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.field{display:grid;gap:6px}.field span{font-weight:600}.check-field{display:flex;gap:10px;padding:11px 12px;border:1px solid var(--edge-color-border,#e5e7eb);border-radius:8px}.check-field span{display:grid;gap:2px}.hint{margin:-8px 0 0;font-size:.8rem;color:var(--edge-color-ink-500,#667085)}.form-error,.form-warning{padding:10px 12px;border-radius:8px}.form-error{border:1px solid var(--edge-color-danger,#d92d20);color:var(--edge-color-danger,#b42318);background:var(--edge-color-danger-subtle,#fef3f2)}.form-warning{border:1px solid var(--edge-color-warning,#f79009);background:var(--edge-color-warning-subtle,#fffaeb)}.items-heading h3{margin:3px 0 4px}.item-count{white-space:nowrap;font-size:.8rem;font-weight:700;padding:6px 9px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:999px}.sticky-actions{position:sticky;bottom:0;z-index:5;padding:14px;border:1px solid var(--edge-color-border,#dfe3e8);border-radius:10px;background:color-mix(in srgb,var(--edge-color-surface,#fff) 94%,transparent);backdrop-filter:blur(8px)}.page-actions{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}@media(max-width:760px){.field-grid{grid-template-columns:1fr}.recovery-panel,.saved-panel,.items-heading,.sticky-actions{align-items:stretch;flex-direction:column}.page-actions{justify-content:flex-start}}
</style>
