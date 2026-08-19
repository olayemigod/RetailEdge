<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Stock Adjustment'"
		:subtitle="formContext.subtitle || 'Record physical quantities in an ERPNext Stock Reconciliation draft.'"
		size="xl"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-adjustment-state">
			<EdgeLoadingState message="Preparing Stock Adjustment..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="guided-adjustment-state">
			<EdgeErrorState title="Stock Adjustment unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="guided-adjustment-form" @submit.prevent="saveDraft">
			<div class="guided-adjustment-context">
				<div><span>Company</span><strong>{{ values.company || 'Not set' }}</strong></div>
				<div v-if="values.branch"><span>Branch</span><strong>{{ values.branch }}</strong></div>
				<div><span>Purpose</span><strong>Physical Stock Reconciliation</strong></div>
			</div>

			<div v-if="saveError" class="guided-adjustment-error" role="alert">{{ saveError }}</div>

			<div class="guided-adjustment-grid">
				<label class="guided-field">
					<span>Posting Date <b>*</b></span>
					<input v-model="values.posting_date" class="form-control" type="date" required />
				</label>
				<EdgeLinkField
					v-if="branchEnabled"
					:modelValue="values.branch"
					label="Branch"
					placeholder="Search permitted branch"
					:searcher="searchBranch"
					:context="searchContext"
					@update:modelValue="setBranch"
				/>
				<EdgeLinkField
					:modelValue="values.warehouse"
					label="Warehouse"
					placeholder="Search permitted warehouse"
					description="Only warehouses valid for the selected company and branch are offered."
					:required="true"
					:searcher="searchWarehouse"
					:context="searchContext"
					@update:modelValue="setWarehouse"
				/>
			</div>

			<EdgeChildTable
				:field="itemTableField"
				:rows="values.items"
				:columns="itemColumns"
				:addLabel="'Add Item'"
				:linkSearcher="searchLineLink"
				:newRowsFirst="true"
				@update:rows="updateItems"
			/>

			<p class="guided-adjustment-hint">
				Enter the physical quantity actually counted. Zero is valid; negative physical counts are not.
				Valuation and cost fields are deliberately not exposed by this guided flow. Serial-numbered or
				batch-managed items must use the full Stock Reconciliation form.
			</p>
		</form>

		<template #footer>
			<div class="guided-adjustment-footer">
				<button type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="guided-adjustment-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveDraft">
						{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}
					</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
import { callMethod, errorMessage, resolveBranchWarehouse } from "./guidedEntryUtils";

const CONTEXT_METHOD = "retailedge.guided_stock_adjustment.get_simple_stock_adjustment_context";
const SEARCH_METHOD = "retailedge.guided_stock_adjustment.search_simple_stock_adjustment_options";
const CREATE_METHOD = "retailedge.guided_stock_adjustment.create_simple_stock_adjustment_draft";
const runtimeComponents = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return { company: "", posting_date: "", branch: "", warehouse: "", items: [{ item_code: "", qty: "" }] };
}

export default {
	name: "SimpleStockAdjustmentDialog",
	components: {
		EdgeModal: runtimeComponents.EdgeModal,
		EdgeLinkField: runtimeComponents.EdgeLinkField,
		EdgeChildTable: runtimeComponents.EdgeChildTable,
		EdgeLoadingState: runtimeComponents.EdgeLoadingState,
		EdgeErrorState: runtimeComponents.EdgeErrorState,
	},
	props: { open: { type: Boolean, default: false } },
	emits: ["close", "saved", "open-native"],
	data() {
		return {
			loading: false,
			saving: false,
			loadError: "",
			saveError: "",
			cascadeToken: 0,
			formContext: {},
			values: emptyValues(),
			itemTableField: { label: "Physical Counts", description: "Enter one row per counted stock item." },
			itemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search stock item" },
				{ fieldname: "qty", label: "Physical Qty", fieldtype: "Float", default: "" },
			],
		};
	},
	computed: {
		branchEnabled() { return Boolean(this.formContext.capabilities?.branch_enabled); },
		searchContext() { return { company: this.values.company, branch: this.values.branch, warehouse: this.values.warehouse }; },
	},
	watch: { open(value) { if (value) this.loadContext(); } },
	mounted() { if (this.open) this.loadContext(); },
	methods: {
		async loadContext() {
			this.loading = true; this.loadError = ""; this.saveError = "";
			try {
				const data = await callMethod(CONTEXT_METHOD);
				this.formContext = data || {};
				this.values = { ...emptyValues(), ...(data.defaults || {}), items: (data.defaults?.items || emptyValues().items).map((row) => ({ ...row })) };
			} catch (error) { this.loadError = errorMessage(error, "Unable to prepare Stock Adjustment."); }
			finally { this.loading = false; }
		},
		requestClose() { if (!this.saving) this.$emit("close"); },
		openFullForm() { if (!this.saving) this.$emit("open-native", "Stock Reconciliation"); },
		async searchOptions(fieldname, query) {
			const result = await callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values: { ...this.values, items: undefined }, limit: 20 });
			return Array.isArray(result) ? result : [];
		},
		searchBranch(query) { return this.searchOptions("branch", query); },
		searchWarehouse(query) { return this.searchOptions("warehouse", query); },
		searchLineLink(column, query) { return column?.fieldname === "item_code" ? this.searchOptions("item_code", query) : Promise.resolve([]); },
		async setBranch(next) {
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			if (!branch || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch, preference: "source" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
			} catch (error) { if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch warehouse."); }
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			if (!warehouse || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({ company: this.values.company, branch: this.values.branch, warehouse, preference: "source" });
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || warehouse;
			} catch (error) {
				if (token === this.cascadeToken) { this.values.warehouse = ""; this.saveError = errorMessage(error, "Unable to use the selected Warehouse."); }
			}
		},
		updateItems(rows) { this.values.items = Array.isArray(rows) ? rows.map((row) => ({ ...row })) : []; },
		async saveDraft() {
			if (this.saving || this.loading) return;
			if (!this.values.company || !this.values.warehouse) { this.saveError = "Company and Warehouse are required."; return; }
			const rows = (this.values.items || []).filter((row) => row?.item_code);
			if (!rows.length) { this.saveError = "Add at least one counted Item."; return; }
			if (rows.some((row) => row.qty === "" || row.qty === null || row.qty === undefined || Number(row.qty) < 0)) {
				this.saveError = "Each counted Item needs a physical quantity of zero or more."; return;
			}
			this.saving = true; this.saveError = "";
			try { const result = await callMethod(CREATE_METHOD, { values: { ...this.values, items: rows } }); this.$emit("saved", result); }
			catch (error) { this.saveError = errorMessage(error, "Stock Adjustment could not be saved."); }
			finally { this.saving = false; }
		},
	},
};
</script>

<style scoped>
.guided-adjustment-state { min-height:180px; display:grid; place-items:center; }
.guided-adjustment-form { display:grid; gap:18px; }
.guided-adjustment-context { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; padding:14px; border:1px solid var(--edge-border,#dfe3e8); border-radius:10px; }
.guided-adjustment-context div,.guided-field { display:grid; gap:5px; }
.guided-adjustment-context span,.guided-field span { font-size:.78rem; color:var(--edge-text-muted,#667085); }
.guided-adjustment-grid { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:14px; }
.guided-adjustment-error { padding:10px 12px; border-radius:8px; background:#fef3f2; color:#b42318; }
.guided-adjustment-hint { margin:0; color:var(--edge-text-muted,#667085); font-size:.83rem; line-height:1.5; }
.guided-adjustment-footer,.guided-adjustment-footer-actions { display:flex; align-items:center; gap:10px; }
.guided-adjustment-footer { justify-content:space-between; width:100%; }
@media (max-width:720px) { .guided-adjustment-context,.guided-adjustment-grid { grid-template-columns:1fr; } .guided-adjustment-footer { align-items:stretch; flex-direction:column; } .guided-adjustment-footer-actions { justify-content:flex-end; } }
</style>
