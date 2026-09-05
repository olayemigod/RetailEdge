<template>
	<EdgeModal
		:open="open"
		:title="formContext.title || 'Cash / Bank Transfer'"
		:subtitle="formContext.subtitle || 'Move funds safely between permitted Cash and Bank accounts.'"
		size="lg"
		@close="requestClose"
	>
		<div v-if="loading" class="guided-transfer-state">
			<EdgeLoadingState message="Preparing transfer..." :skeleton="true" />
		</div>
		<div v-else-if="loadError" class="guided-transfer-state">
			<EdgeErrorState title="Transfer unavailable" :message="loadError" @retry="loadContext" />
		</div>
		<form v-else class="guided-transfer-form" @submit.prevent="saveDraft">
			<div class="guided-transfer-context">
				<div><span>Company</span><strong>{{ values.company || 'Not set' }}</strong></div>
				<div v-if="values.branch"><span>Branch</span><strong>{{ values.branch }}</strong></div>
				<div><span>Transfer Type</span><strong>Internal Transfer</strong></div>
			</div>
			<div v-if="saveError" class="guided-transfer-error" role="alert">{{ saveError }}</div>
			<div class="guided-transfer-grid">
				<label class="guided-field"><span>Posting Date <b>*</b></span><input v-model="values.posting_date" class="form-control" type="date" required /></label>
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
					:modelValue="values.from_account"
					label="From Account"
					placeholder="Search Cash or Bank account"
					:required="true"
					:searcher="searchFromAccount"
					:context="searchContext"
					@update:modelValue="setFromAccount"
				/>
				<EdgeLinkField
					:modelValue="values.to_account"
					label="To Account"
					placeholder="Search Cash or Bank account"
					:required="true"
					:searcher="searchToAccount"
					:context="searchContext"
					@update:modelValue="setToAccount"
				/>
				<label class="guided-field"><span>Amount <b>*</b></span><input v-model.number="values.amount" class="form-control" type="number" min="0.01" step="0.01" required /></label>
				<label class="guided-field"><span>Reference No</span><input v-model="values.reference_no" class="form-control" type="text" placeholder="Required when a bank account is involved" /></label>
				<label class="guided-field"><span>Reference Date</span><input v-model="values.reference_date" class="form-control" type="date" /></label>
			</div>
			<p class="guided-transfer-hint">Only permitted posting Cash and Bank accounts are offered. Multi-currency transfers remain on the full ERPNext Payment Entry form.</p>
			<label class="guided-field guided-field--wide"><span>Remarks</span><textarea v-model="values.remarks" class="form-control" rows="3" placeholder="Optional transfer note"></textarea></label>
		</form>
		<template #footer>
			<div class="guided-transfer-footer">
				<button v-if="nativeFallbackEnabled" type="button" class="edge-button" :disabled="saving" @click="openFullForm">Open Full Form</button>
				<div class="guided-transfer-footer-actions">
					<button type="button" class="edge-button" :disabled="saving" @click="requestClose">Cancel</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="saving || loading" @click="saveDraft">{{ saving ? 'Saving...' : formContext.submit_label || 'Save Draft' }}</button>
				</div>
			</div>
		</template>
	</EdgeModal>
</template>

<script>
const CONTEXT_METHOD = "retailedge.guided_cash_transfer.get_simple_cash_transfer_context";
const SEARCH_METHOD = "retailedge.guided_cash_transfer.search_simple_cash_transfer_options";
const CREATE_METHOD = "retailedge.guided_cash_transfer.create_simple_cash_transfer_draft";
const runtimeComponents = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return { company: "", branch: "", posting_date: "", from_account: "", to_account: "", amount: "", reference_no: "", reference_date: "", remarks: "" };
}
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function errorMessage(error, fallback) { return error?.message || error?.exc_type || fallback; }
function optionValue(option) { return typeof option === "string" ? option : option?.value || ""; }

export default {
	name: "SimpleCashTransferDialog",
	components: { EdgeModal: runtimeComponents.EdgeModal, EdgeLinkField: runtimeComponents.EdgeLinkField, EdgeLoadingState: runtimeComponents.EdgeLoadingState, EdgeErrorState: runtimeComponents.EdgeErrorState },
	props: {
		open: { type: Boolean, default: false },
		nativeFallbackEnabled: { type: Boolean, default: true },
	},
	emits: ["close", "saved", "open-native"],
	data() { return { loading: false, saving: false, loadError: "", saveError: "", formContext: {}, values: emptyValues() }; },
	computed: {
		branchEnabled() { return Boolean(this.formContext?.capabilities?.branch_enabled); },
		searchContext() { return { ...this.values }; },
	},
	watch: { open(value) { if (value) this.loadContext(); else this.reset(); } },
	mounted() { if (this.open) this.loadContext(); },
	methods: {
		reset() { this.loading = false; this.saving = false; this.loadError = ""; this.saveError = ""; this.formContext = {}; this.values = emptyValues(); },
		async loadContext() {
			this.loading = true; this.loadError = ""; this.saveError = "";
			try { const result = await callMethod(CONTEXT_METHOD); this.formContext = result || {}; this.values = { ...emptyValues(), ...(result?.defaults || {}) }; }
			catch (error) { this.loadError = errorMessage(error, "Unable to prepare Cash / Bank Transfer."); }
			finally { this.loading = false; }
		},
		async searchOptions(fieldname, txt) {
			const result = await callMethod(SEARCH_METHOD, { fieldname, txt: txt || "", values: { ...this.values }, limit: 20 });
			return Array.isArray(result) ? result : [];
		},
		searchBranch(txt) { return this.searchOptions("branch", txt); },
		searchFromAccount(txt) { return this.searchOptions("from_account", txt); },
		searchToAccount(txt) { return this.searchOptions("to_account", txt); },
		setBranch(option) { this.values.branch = optionValue(option); },
		setFromAccount(option) { this.values.from_account = optionValue(option); if (this.values.to_account === this.values.from_account) this.values.to_account = ""; },
		setToAccount(option) { this.values.to_account = optionValue(option); if (this.values.from_account === this.values.to_account) this.values.from_account = ""; },
		requestClose() { if (!this.saving) this.$emit("close"); },
		openFullForm() { if (!this.saving) this.$emit("open-native", this.formContext.full_form_doctype || "Payment Entry"); },
		async saveDraft() {
			if (this.saving || this.loading) return;
			if (!this.values.company || !this.values.from_account || !this.values.to_account || Number(this.values.amount || 0) <= 0) { this.saveError = "Company, From Account, To Account and a positive Amount are required."; return; }
			this.saving = true; this.saveError = "";
			try { const result = await callMethod(CREATE_METHOD, { values: { ...this.values } }); this.$emit("saved", result); }
			catch (error) { this.saveError = errorMessage(error, "Cash / Bank Transfer could not be saved."); }
			finally { this.saving = false; }
		},
	},
};
</script>

<style scoped>
.guided-transfer-state { min-height:180px; display:grid; place-items:center; }
.guided-transfer-form { display:grid; gap:18px; }
.guided-transfer-context { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; padding:14px; border:1px solid var(--edge-border,#dfe3e8); border-radius:10px; }
.guided-transfer-context div,.guided-field { display:grid; gap:5px; }
.guided-transfer-context span,.guided-field span { font-size:.78rem; color:var(--edge-text-muted,#667085); }
.guided-transfer-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
.guided-field--wide { grid-column:1/-1; }
.guided-transfer-error { padding:10px 12px; border-radius:8px; background:#fef3f2; color:#b42318; }
.guided-transfer-hint { margin:0; color:var(--edge-text-muted,#667085); font-size:.83rem; }
.guided-transfer-footer,.guided-transfer-footer-actions { display:flex; align-items:center; gap:10px; }
.guided-transfer-footer { justify-content:space-between; width:100%; }
@media (max-width:720px) { .guided-transfer-context,.guided-transfer-grid { grid-template-columns:1fr; } .guided-transfer-footer { align-items:stretch; flex-direction:column; } .guided-transfer-footer-actions { justify-content:flex-end; } }
</style>
