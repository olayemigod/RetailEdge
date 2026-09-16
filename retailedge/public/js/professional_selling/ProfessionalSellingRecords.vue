<template>
	<section ref="panel" class="edge-panel selling-records-panel">
		<div class="selling-records-heading">
			<div>
				<span class="selling-kicker">Selling records</span>
				<h3>{{ activeDocument?.label || "Selling documents" }}</h3>
				<p>Search, filter, review, output and complete permitted records without changing the table structure.</p>
			</div>
			<button v-if="hasFilters" type="button" class="edge-button edge-button--secondary" @click="clearFilters">
				Clear filters
			</button>
		</div>

		<div class="selling-record-tabs" role="tablist" aria-label="Professional Selling document lists">
			<button
				v-for="document in readableDocuments"
				:key="document.key"
				type="button"
				class="selling-record-tab"
				:class="{ active: document.key === activeKey }"
				role="tab"
				:aria-selected="document.key === activeKey ? 'true' : 'false'"
				@click="selectDocument(document.key)"
			>
				{{ document.label }}
			</button>
		</div>

		<div class="selling-record-filters">
			<EdgeInput
				v-model="filters.search"
				label="Search"
				type="search"
				placeholder="Document, customer or status"
				@input="scheduleReload"
			/>
			<EdgeDropdown
				v-model="filters.status"
				:options="statusOptions"
				label="Status"
				@change="reload"
			/>
			<EdgeInput
				v-model="filters.from_date"
				label="From Date"
				type="date"
				:max="filters.to_date || undefined"
				@change="reload"
			/>
			<EdgeInput
				v-model="filters.to_date"
				label="To Date"
				type="date"
				:min="filters.from_date || undefined"
				@change="reload"
			/>
		</div>

		<p v-if="error" class="selling-record-error" role="alert">{{ error }}</p>
		<EdgeLoadingState v-if="loading && !rows.length" message="Loading selling records..." />
		<EdgeEmptyState
			v-else-if="!loading && !rows.length"
			title="No matching records"
			description="Adjust the filters or create a new document from the selling workflow above."
		/>

		<div v-else class="selling-record-table-wrap">
			<table class="selling-record-table">
				<thead>
					<tr>
						<th scope="col">Document</th>
						<th scope="col">Customer</th>
						<th scope="col">Date</th>
						<th scope="col">Status</th>
						<th scope="col" class="amount-column">Total</th>
						<th scope="col" class="actions-column">Actions</th>
					</tr>
				</thead>
				<tbody>
					<tr v-for="(row, index) in rows" :key="row.name">
						<td>
							<strong class="record-name">{{ row.name }}</strong>
						</td>
						<td class="party-column">{{ partyValue(row) || "—" }}</td>
						<td class="date-column">{{ formatDate(dateValue(row)) }}</td>
						<td>
							<EdgeStatusBadge :status="statusValue(row)" />
						</td>
						<td class="amount-column">
							<span :title="formatAmount(row, false)">{{ formatAmount(row, true) }}</span>
						</td>
						<td class="actions-column">
							<div class="record-actions">
								<button
									type="button"
									class="edge-button edge-button--primary record-primary-action"
									@click="runPrimaryAction(row)"
								>
									{{ primaryActionLabel(row) }}
								</button>
								<EdgeDropdown
									v-if="moreActions(row).length"
									:modelValue="''"
									:options="moreActions(row)"
									placeholder="More"
									aria-label="More record actions"
									:class="['record-more', { 'record-more--fly-up': shouldFlyUp(index) }]"
									@select="runMoreAction(row, $event)"
								/>
								<span v-else class="record-more-placeholder" aria-hidden="true"></span>
							</div>
						</td>
					</tr>
				</tbody>
			</table>
		</div>

		<div v-if="rows.length" class="selling-record-footer">
			<span>{{ rows.length }} record{{ rows.length === 1 ? "" : "s" }} loaded</span>
			<button
				v-if="hasMore"
				type="button"
				class="edge-button edge-button--secondary"
				:disabled="loadingMore"
				@click="loadMore"
			>
				{{ loadingMore ? "Loading..." : "Load more" }}
			</button>
		</div>
	</section>
</template>

<script>
const LIST_METHOD = "retailedge.professional_selling.get_professional_selling_list";
const REQUIRED_COMPONENTS = ["EdgeInput", "EdgeDropdown", "EdgeLoadingState", "EdgeEmptyState", "EdgeStatusBadge"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject });
	});
}

function cleanError(error, fallback) {
	const value = error?.message || error?.responseJSON?.message || error?.exc || "";
	if (value && !String(value).includes("Traceback (most recent call last)")) return String(value);
	return fallback;
}

export default {
	name: "ProfessionalSellingRecords",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	props: {
		documents: { type: Array, default: () => [] },
		canUseNativeDesk: { type: Boolean, default: false },
	},
	emits: ["action"],
	data() {
		return {
			activeKey: "",
			rows: [],
			loading: false,
			loadingMore: false,
			error: "",
			hasMore: false,
			nextStart: 0,
			requestToken: 0,
			searchTimer: null,
			filters: {
				search: "",
				status: "All",
				from_date: "",
				to_date: "",
			},
		};
	},
	computed: {
		readableDocuments() {
			return (this.documents || []).filter((row) => row?.available && row?.can_read);
		},
		activeDocument() {
			return this.readableDocuments.find((row) => row.key === this.activeKey) || this.readableDocuments[0] || null;
		},
		statusOptions() {
			const common = ["All", "Draft", "Submitted", "Cancelled"];
			const byDocument = {
				quotation: ["Open", "Ordered", "Lost", "Expired"],
				"sales-order": ["To Deliver and Bill", "To Deliver", "To Bill", "Completed", "Closed"],
				"delivery-note": ["To Bill", "Completed", "Closed", "Return"],
				"sales-invoice": ["Unpaid", "Overdue", "Partly Paid", "Paid", "Credit Note", "Return"],
			};
			return [...new Set([...common, ...(byDocument[this.activeKey] || [])])].map((value) => ({ value, label: value }));
		},
		hasFilters() {
			return Boolean(
				String(this.filters.search || "").trim()
				|| this.filters.status !== "All"
				|| this.filters.from_date
				|| this.filters.to_date
			);
		},
	},
	watch: {
		documents: {
			deep: true,
			immediate: true,
			handler() {
				if (!this.readableDocuments.length) {
					this.activeKey = "";
					this.rows = [];
					return;
				}
				if (!this.readableDocuments.some((row) => row.key === this.activeKey)) {
					const invoice = this.readableDocuments.find((row) => row.key === "sales-invoice");
					this.activeKey = invoice?.key || this.readableDocuments[0].key;
					this.$nextTick(() => this.reload());
				}
			},
		},
	},
	beforeUnmount() {
		if (this.searchTimer) window.clearTimeout(this.searchTimer);
		this.requestToken += 1;
	},
	methods: {
		selectDocument(key, { focus = true } = {}) {
			if (!this.readableDocuments.some((row) => row.key === key)) return;
			const changed = this.activeKey !== key;
			this.activeKey = key;
			if (changed) this.reload();
			if (focus) this.$nextTick(() => this.$refs.panel?.scrollIntoView?.({ behavior: "smooth", block: "start" }));
		},
		refresh() {
			return this.reload();
		},
		clearFilters() {
			this.filters = { search: "", status: "All", from_date: "", to_date: "" };
			this.reload();
		},
		scheduleReload() {
			if (this.searchTimer) window.clearTimeout(this.searchTimer);
			this.searchTimer = window.setTimeout(() => this.reload(), 280);
		},
		async reload() {
			if (!this.activeDocument) return;
			const token = ++this.requestToken;
			this.loading = true;
			this.error = "";
			try {
				const result = await this.fetchPage(0);
				if (token !== this.requestToken) return;
				this.rows = Array.isArray(result.rows) ? result.rows : [];
				this.hasMore = Boolean(result.has_more);
				this.nextStart = Number(result.next_start || this.rows.length);
			} catch (error) {
				if (token !== this.requestToken) return;
				this.rows = [];
				this.hasMore = false;
				this.nextStart = 0;
				this.error = cleanError(error, `Could not load ${this.activeDocument.label} records.`);
			} finally {
				if (token === this.requestToken) this.loading = false;
			}
		},
		async loadMore() {
			if (!this.activeDocument || !this.hasMore || this.loadingMore) return;
			this.loadingMore = true;
			this.error = "";
			try {
				const result = await this.fetchPage(this.nextStart);
				const nextRows = Array.isArray(result.rows) ? result.rows : [];
				const existing = new Set(this.rows.map((row) => row.name));
				this.rows = [...this.rows, ...nextRows.filter((row) => !existing.has(row.name))];
				this.hasMore = Boolean(result.has_more);
				this.nextStart = Number(result.next_start || this.rows.length);
			} catch (error) {
				this.error = cleanError(error, `Could not load more ${this.activeDocument.label} records.`);
			} finally {
				this.loadingMore = false;
			}
		},
		fetchPage(start) {
			return callMethod(LIST_METHOD, {
				document: this.activeDocument.key,
				search: String(this.filters.search || "").trim(),
				status: this.filters.status || "All",
				from_date: this.filters.from_date || "",
				to_date: this.filters.to_date || "",
				start,
				page_length: 20,
			});
		},
		partyValue(row) {
			return row?.[this.activeDocument?.party_field] || row?.customer || row?.party_name || "";
		},
		dateValue(row) {
			return row?.[this.activeDocument?.date_field] || row?.posting_date || row?.transaction_date || "";
		},
		formatDate(value) {
			const text = String(value || "").trim();
			const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(text);
			return match ? `${match[3]}/${match[2]}/${match[1]}` : text || "—";
		},
		statusValue(row) {
			if (row?.status) return row.status;
			if (Number(row?.docstatus || 0) === 2) return "Cancelled";
			if (Number(row?.docstatus || 0) === 1) return "Submitted";
			return "Draft";
		},
		formatAmount(row, compact = true) {
			if (row?.grand_total === undefined || row?.grand_total === null) return "—";
			const value = Number(row.grand_total || 0);
			const currency = String(row.currency || "").trim();
			let amount;
			if (compact && Math.abs(value) >= 100000) {
				try {
					amount = new Intl.NumberFormat(undefined, { notation: "compact", maximumFractionDigits: 2 }).format(value);
				} catch (_error) {
					amount = value.toLocaleString(undefined, { maximumFractionDigits: 2 });
				}
			} else {
				amount = value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
			}
			return currency ? `${currency} ${amount}` : amount;
		},
		canComplete(row) {
			return Number(row?.docstatus || 0) === 0;
		},
		primaryActionLabel(row) {
			return this.canComplete(row) ? "Edit / Complete" : "View";
		},
		moreActions(row) {
			const actions = (Array.isArray(row?.actions) ? row.actions : [])
				.map((action) => ({
					value: action?.value,
					label: action?.label,
					disabled: Boolean(action?.disabled),
				}))
				.filter((action) => action.value && action.label);
			if (!actions.some((action) => action.value === "output")) {
				actions.push({
					value: "output",
					label: "Print & Send",
				});
			}
			if (this.canUseNativeDesk) {
				actions.push({
					value: "advanced",
					label: "Advanced: Open in ERPNext",
				});
			}
			return actions;
		},
		runPrimaryAction(row) {
			if (this.canComplete(row)) {
				this.$emit("action", { action: "complete", document: this.activeDocument, row });
				return;
			}
			this.$emit("action", { action: "view", document: this.activeDocument, row });
		},
		shouldFlyUp(index) {
			if (!Number.isInteger(index) || this.rows.length < 2) return false;
			return index >= Math.max(0, this.rows.length - 2);
		},
		runMoreAction(row, option) {
			const action = String(option?.value || "");
			if (!action) return;
			this.$emit("action", { action, document: this.activeDocument, row });
		},
	},
};
</script>

<style scoped>
.selling-records-panel { display:grid; gap:1rem; min-width:0; }
.selling-records-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
.selling-records-heading h3 { margin:.2rem 0 .3rem; }
.selling-records-heading p { margin:0; color:var(--edge-color-ink-500,var(--text-muted)); }
.selling-record-tabs { display:flex; gap:.35rem; overflow-x:auto; padding-bottom:.15rem; border-bottom:1px solid var(--edge-color-border,var(--border-color)); }
.selling-record-tab { appearance:none; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--edge-color-ink-500,var(--text-muted)); padding:.65rem .85rem; font:inherit; font-weight:650; white-space:nowrap; cursor:pointer; }
.selling-record-tab:hover { color:var(--edge-color-ink-950,var(--text-color)); background:var(--edge-color-surface-muted,var(--control-bg)); }
.selling-record-tab.active { color:var(--edge-color-brand-700,var(--primary)); border-bottom-color:var(--edge-color-brand-600,var(--primary)); }
.selling-record-filters { display:grid; grid-template-columns:minmax(15rem,2fr) minmax(10rem,1fr) minmax(10rem,1fr) minmax(10rem,1fr); gap:.75rem; align-items:end; }
.selling-record-table-wrap { width:100%; overflow-x:auto; border:1px solid var(--edge-color-border,var(--border-color)); border-radius:.7rem; background:var(--edge-color-surface,var(--card-bg)); }
.selling-record-table { width:100%; min-width:58rem; border-collapse:collapse; table-layout:fixed; }
.selling-record-table th,.selling-record-table td { padding:.75rem .8rem; border-bottom:1px solid var(--edge-color-border,var(--border-color)); text-align:left; vertical-align:middle; }
.selling-record-table th { background:var(--edge-color-surface-muted,var(--control-bg)); color:var(--edge-color-ink-500,var(--text-muted)); font-size:.72rem; font-weight:700; letter-spacing:.035em; text-transform:uppercase; }
.selling-record-table tbody tr:last-child td { border-bottom:0; }
.selling-record-table tbody tr:hover { background:color-mix(in srgb,var(--edge-color-brand-50) 38%,transparent); }
.record-name { display:block; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:var(--edge-color-ink-950,var(--text-color)); }
.party-column { overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.date-column { white-space:nowrap; }
.amount-column { width:9.5rem; text-align:right !important; font-variant-numeric:tabular-nums; white-space:nowrap; }
.actions-column { width:20rem; }
.record-actions { display:grid; grid-template-columns:minmax(8.5rem,1fr) 9.25rem; gap:.5rem; align-items:center; }
.record-primary-action { width:100%; white-space:nowrap; font-size:.76rem; padding-inline:.55rem; }
.record-more { min-width:0; width:100%; font-size:.78rem; }
.record-more-placeholder { display:block; min-width:0; }
:deep(.edge-dropdown__trigger.record-more + .edge-dropdown__menu) {
	left:auto;
	right:0;
	width:min(15rem,calc(100vw - 2rem));
	min-width:min(15rem,calc(100vw - 2rem));
	max-width:none;
}
:deep(.edge-dropdown__trigger.record-more.record-more--fly-up + .edge-dropdown__menu) {
	top:auto;
	bottom:calc(100% + .25rem);
}
:deep(.edge-dropdown__trigger.record-more + .edge-dropdown__menu .edge-dropdown__option-label) {
	overflow:visible;
	text-overflow:clip;
	white-space:normal;
}
.selling-record-footer { display:flex; justify-content:space-between; align-items:center; gap:1rem; color:var(--edge-color-ink-500,var(--text-muted)); font-size:.82rem; }
.selling-record-error { margin:0; padding:.7rem .85rem; border:1px solid var(--edge-color-danger); border-radius:.6rem; color:var(--edge-color-danger); background:color-mix(in srgb,var(--edge-color-danger) 7%,var(--edge-color-surface)); }
@media (max-width: 960px) {
	.selling-record-filters { grid-template-columns:repeat(2,minmax(0,1fr)); }
}
@media (max-width: 620px) {
	.selling-records-heading,.selling-record-footer { align-items:stretch; flex-direction:column; }
	.selling-record-filters { grid-template-columns:1fr; }
}
</style>
