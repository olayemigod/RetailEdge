<template>
	<section class="deposit-register">
		<div class="deposit-filters">
			<EdgeLinkField v-model="filters.company" label="Company" required :selectedLabel="filters.company" :searcher="companySearch" @select="selectCompany" @clear="clearCompany" />
			<EdgeLinkField v-model="filters.branch" label="Branch" :selectedLabel="filters.branch" :searcher="branchSearch" @select="selectBranch" @clear="clearBranch" />
			<EdgeLinkField v-model="filters.cashier" label="Cashier" :selectedLabel="filters.cashier" :searcher="txt => searchOptions('cashier', txt)" @select="option => selectFilter('cashier', option)" @clear="clearFilter('cashier')" />
			<EdgeLinkField v-model="filters.bank_account" label="Destination bank" :selectedLabel="filters.bank_account" :searcher="txt => searchOptions('bank', txt)" @select="option => selectFilter('bank_account', option)" @clear="clearFilter('bank_account')" />
			<EdgeLinkField v-model="filters.opening_shift" label="POS shift" :selectedLabel="filters.opening_shift" :searcher="txt => searchOptions('shift', txt)" @select="option => selectFilter('opening_shift', option)" @clear="clearFilter('opening_shift')" />
			<EdgeDropdown v-model="filters.docstatus" label="Status" :options="statusOptions" @change="invalidateResults" />
			<EdgeSmartDateRange v-model="period" label="Period" @resolved="setPeriod" />
			<EdgeInput v-model="filters.search" type="search" label="Search deposits" placeholder="Payment or teller reference" @update:modelValue="invalidateResults" />
			<div class="deposit-actions">
				<button class="edge-button edge-button--primary" type="button" :disabled="!filters.company || loading || filtersPending" @click="load(1)">Apply filters</button>
				<button class="edge-button edge-button--secondary" type="button" :disabled="loading" @click="resetPeriod">All dates</button>
			</div>
		</div>
		<EdgeErrorState v-if="error" :message="error" @retry="load(1)" />
		<EdgeLoadingState v-else-if="loading" message="Loading cash deposits…" />
		<template v-else-if="loaded">
			<div class="deposit-totals">
				<article v-for="state in ['submitted', 'draft', 'cancelled']" :key="state">
					<h3>{{ stateLabel(state) }}</h3>
					<p v-if="!totals[state]?.length">0 deposits</p>
					<p v-for="group in totals[state] || []" :key="group.currency">
						<strong>{{ money(group.amount, group.currency) }}</strong> · {{ group.count }} deposits
					</p>
				</article>
			</div>
			<p class="deposit-note">Only submitted deposits reduce till cash. Totals include all matching records, not just this page.</p>
			<EdgeEmptyState v-if="!rows.length" title="No cash deposits found" description="Change your filters to find other deposits." />
			<div v-else class="deposit-table-wrap">
				<table class="deposit-table">
					<thead><tr><th>Deposit</th><th>Date</th><th>Branch</th><th>Cashier</th><th>POS shift</th><th>Cash account</th><th>Destination bank</th><th>Teller reference</th><th>Amount</th><th>Status</th><th>Action</th></tr></thead>
					<tbody>
						<tr v-for="row in rows" :key="row.name">
							<td>{{ row.name }}</td><td>{{ row.posting_date }}</td><td>{{ row.retailedge_branch }}</td><td>{{ row.retailedge_cashier }}</td>
							<td>{{ row.retailedge_pos_opening_shift }}</td><td>{{ row.paid_from || "—" }}</td><td>{{ row.bank_account || row.paid_to || "—" }}</td>
							<td>{{ row.reference_no || "—" }}</td><td>{{ money(row.paid_amount, row.paid_from_account_currency) }}</td>
							<td>{{ documentState(row.docstatus) }}</td>
							<td>
								<button v-if="nativeReview && Number(row.docstatus) === 0" class="edge-button edge-button--secondary" type="button" @click="review(row)">Review</button>
								<button v-else-if="nativeReview && canUseNativeDesk" class="edge-button edge-button--secondary" type="button" @click="advanced(row)">Advanced</button>
								<span v-else-if="Number(row.docstatus) === 0">Awaiting authorized review</span>
							</td>
						</tr>
					</tbody>
				</table>
			</div>
			<div class="deposit-actions">
				<button class="edge-button edge-button--secondary" type="button" :disabled="!pagination.has_previous" @click="load(pagination.page - 1)">Previous</button>
				<span>Page {{ pagination.page || 1 }}</span>
				<button class="edge-button edge-button--secondary" type="button" :disabled="!pagination.has_next" @click="load(pagination.page + 1)">Next</button>
			</div>
		</template>
		<p v-else class="deposit-note">Apply filters to view cash deposits.</p>
		<StandardInternalTransferCompletionDialog v-if="selected" :key="selected.name" :open="true" :document="selected" :canUseNativeDesk="canUseNativeDesk" @close="selected = null" @changed="refreshAfterReview" />
	</section>
</template>

<script>
import StandardInternalTransferCompletionDialog from "../retailedge_business_hub/StandardInternalTransferCompletionDialog.vue";

const COMPONENTS = ["EdgeLinkField", "EdgeDropdown", "EdgeSmartDateRange", "EdgeInput", "EdgeErrorState", "EdgeLoadingState", "EdgeEmptyState"];
const api = (method, args = {}) => new Promise((resolve, reject) => frappe.call({
	method, args, type: "GET", callback: response => resolve(response.message), error: reject,
}));
const options = values => (values || []).map(value => ({ value, label: value }));
const matching = (values, txt) => options(values).filter(row => row.label.toLowerCase().includes(String(txt || "").toLowerCase()));
const initialFilters = () => ({ company: "", branch: "", cashier: "", bank_account: "", opening_shift: "", docstatus: "all", from_date: "", to_date: "", search: "" });

export default {
	name: "CashDepositRegisterPanel",
	components: { StandardInternalTransferCompletionDialog, ...Object.fromEntries(COMPONENTS.map(name => [name, window.EdgeSuiteUI?.components?.[name]])) },
	props: { canUseNativeDesk: { type: Boolean, default: false } },
	data() {
		return {
			filters: initialFilters(), period: {}, companies: [], branches: [], rows: [], totals: {}, pagination: {},
			loading: false, loaded: false, error: "", selected: null, nativeReview: false, requestVersion: 0, contextVersion: 0, filtersPending: false,
			statusOptions: [{ value: "all", label: "All statuses" }, { value: "draft", label: "Draft" }, { value: "submitted", label: "Submitted" }, { value: "cancelled", label: "Cancelled" }],
		};
	},
	mounted() {
		this._show = () => this.initialize();
		window.addEventListener("retailedge-cash-deposit-register-page-show", this._show);
		this.initialize();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-cash-deposit-register-page-show", this._show);
		this.requestVersion++;
		this.contextVersion++;
	},
	methods: {
		async initialize() {
			const version = ++this.contextVersion;
			this.invalidateResults();
			this.filtersPending = false;
			this.filters = initialFilters();
			this.period = {};
			try {
				const context = await api("retailedge.operating_context.get_allowed_operating_contexts");
				if (version !== this.contextVersion) return;
				this.companies = context.companies || [];
				this.branches = context.branches || [];
				this.filters.company = context.selected_company || "";
				const branch = context.current?.branch;
				this.filters.branch = this.branches.includes(branch) ? branch : "";
				const route = frappe.route_options || {};
				if (route.cash_deposit_register === 1) {
					if (route.company === this.filters.company && route.branch === this.filters.branch) this.filters.opening_shift = String(route.opening_shift || "");
					frappe.route_options = null;
				}
				if (this.filters.company) await this.load(1);
			} catch (error) {
				if (version === this.contextVersion) this.error = window.retailedge?.userErrorMessage?.(error, "Unable to load cash deposit filters.") || "Unable to load cash deposit filters.";
			}
		},
		companySearch(txt) { return matching(this.companies, txt); },
		branchSearch(txt) { return matching(this.branches, txt); },
		async searchOptions(kind, txt) {
			if (!this.filters.company) return [];
			const { company, branch, cashier, opening_shift, bank_account } = this.filters;
			const snapshot = JSON.stringify([company, branch, cashier, opening_shift, bank_account]);
			const rows = await api("retailedge.cash_deposit_register.search_cash_deposit_options", { company, branch, cashier, opening_shift, bank_account, kind, txt: txt || "" });
			if (snapshot !== JSON.stringify(["company", "branch", "cashier", "opening_shift", "bank_account"].map(key => this.filters[key]))) return [];
			return rows || [];
		},
		async selectCompany(option) {
			const company = option?.value || "";
			const version = ++this.contextVersion;
			const previous = { ...this.filters };
			this.filters.company = company;
			this.filters.branch = "";
			this.branches = [];
			this.clearDependent();
			this.filtersPending = Boolean(company);
			if (!company) return;
			try {
				const context = await api("retailedge.operating_context.get_allowed_operating_contexts", { company });
				if (version !== this.contextVersion) return;
				this.branches = context.branches || [];
				if (this.branches.includes(previous.branch)) this.filters.branch = previous.branch;
				await this.restoreValidChildren(previous, version);
			} catch (error) {
				if (version === this.contextVersion) this.error = window.retailedge?.userErrorMessage?.(error, "Unable to load branches.") || "Unable to load branches.";
			} finally {
				if (version === this.contextVersion) this.filtersPending = false;
			}
		},
		clearCompany() { return this.selectCompany({ value: "" }); },
		async selectBranch(option) {
			const previous = { ...this.filters };
			const version = ++this.contextVersion;
			this.filters.branch = option?.value || "";
			this.clearDependent();
			this.filtersPending = true;
			try { await this.restoreValidChildren(previous, version); }
			catch (error) {
				if (version === this.contextVersion) this.error = window.retailedge?.userErrorMessage?.(error, "Unable to validate deposit filters.") || "Unable to validate deposit filters.";
			} finally { if (version === this.contextVersion) this.filtersPending = false; }
		},
		clearBranch() { return this.selectBranch({ value: "" }); },
		async restoreValidChildren(previous, version) {
			for (const [field, kind] of [["cashier", "cashier"], ["bank_account", "bank"], ["opening_shift", "shift"]]) {
				if (!previous[field] || version !== this.contextVersion) continue;
				const rows = await this.searchOptions(kind, previous[field]);
				if (version !== this.contextVersion) return;
				if (!this.filters[field] && rows.some(row => row.value === previous[field])) this.filters[field] = previous[field];
			}
		},
		clearDependent() {
			for (const key of ["cashier", "bank_account", "opening_shift"]) this.filters[key] = "";
			this.invalidateResults();
		},
		selectFilter(key, option) {
			this.filters[key] = option?.value || "";
			this.invalidateResults();
		},
		clearFilter(key) { this.filters[key] = ""; this.invalidateResults(); },
		setPeriod(value) {
			this.filters.from_date = value?.from_date || "";
			this.filters.to_date = value?.to_date || "";
			this.invalidateResults();
		},
		resetPeriod() { this.period = {}; this.setPeriod({}); },
		invalidateResults() {
			this.requestVersion++;
			this.rows = [];
			this.totals = {};
			this.nativeReview = false;
			this.pagination = {};
			this.loaded = false;
			this.loading = false;
			this.error = "";
			this.selected = null;
		},
		async load(page) {
			const version = ++this.requestVersion;
			if (!this.filters.company || this.filtersPending) return;
			this.loading = true;
			this.error = "";
			this.loaded = false;
			try {
				const result = await api("retailedge.cash_deposit_register.list_cash_deposits", { ...this.filters, page });
				if (version !== this.requestVersion) return;
				this.nativeReview = result.native_review === true;
				this.rows = result.rows || [];
				this.totals = result.totals || {};
				this.pagination = result.pagination || {};
				this.loaded = true;
			} catch (error) {
				if (version === this.requestVersion) {
					this.rows = [];
					this.totals = {};
					this.error = window.retailedge?.userErrorMessage?.(error, "Unable to load cash deposits.") || "Unable to load cash deposits.";
				}
			} finally {
				if (version === this.requestVersion) this.loading = false;
			}
		},
		review(row) { if (this.nativeReview && Number(row.docstatus) === 0) this.selected = { name: row.name }; },
		advanced(row) { if (this.nativeReview && this.canUseNativeDesk) frappe.set_route("Form", "Payment Entry", row.name); },
		refreshAfterReview() { this.selected = null; this.load(1); },
		documentState(state) { return ["Draft", "Submitted", "Cancelled"][Number(state)] || "Unknown"; },
		stateLabel(state) { return { submitted: "Submitted deposits", draft: "Pending deposits", cancelled: "Cancelled deposits" }[state]; },
		money(amount, currency) { return [currency, Number(amount || 0).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })].filter(Boolean).join(" "); },
	},
};
</script>

<style scoped>
.deposit-register { display:grid; gap:16px; color:var(--edge-text); }
.deposit-filters { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:12px; align-items:end; }
.deposit-actions { display:flex; flex-wrap:wrap; gap:12px; align-items:center; }
.deposit-totals { display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:12px; }
.deposit-totals article { padding:16px; border:1px solid var(--edge-border); border-radius:var(--edge-radius-lg); background:var(--edge-surface); }
.deposit-totals h3 { font-size:1rem; margin:0 0 8px; }
.deposit-note { color:var(--edge-text-muted); }
.deposit-table-wrap { overflow:auto; border:1px solid var(--edge-border); border-radius:var(--edge-radius-lg); }
.deposit-table { width:100%; border-collapse:collapse; text-align:left; }
.deposit-table th,.deposit-table td { padding:12px; border-bottom:1px solid var(--edge-border); overflow-wrap:anywhere; }
.deposit-table th { background:var(--edge-surface); }
</style>
