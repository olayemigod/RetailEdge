<template>
	<div v-if="!edgeUIValid" class="quota-review-fallback">
		<strong>Quota Operations Review could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		title="Quota Operations Review"
		:tenantName="tenantName"
		:branchName="branchName || filters.branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/quota-operations-review"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<div class="quota-review-shell">
			<header class="quota-review-header">
				<div>
					<div class="quota-review-eyebrow">{{ context.eyebrow || "Operations Review" }}</div>
					<h2>{{ context.title || "Quota Operations Review" }}</h2>
					<p>{{ context.subtitle }}</p>
				</div>
				<button class="edge-button edge-button--primary" :disabled="loading" @click="fetchData">
					{{ loading ? "Refreshing…" : "Refresh" }}
				</button>
			</header>

			<div v-if="error" class="quota-review-alert quota-review-alert--danger">{{ error }}</div>
			<div v-if="notice" class="quota-review-alert">{{ notice }}</div>

			<section class="quota-review-status">
				<div>
					<strong>Sales quota</strong>
					<span>{{ context.sales_quota?.enabled ? "Enabled" : "Disabled" }}</span>
				</div>
				<div>
					<strong>CoreEdge service</strong>
					<span>{{ context.remote_usage?.ready ? "Ready" : "Not ready" }}</span>
				</div>
				<div>
					<strong>Actions</strong>
					<span>{{ context.can_reconcile ? "Manager access" : "Read only" }}</span>
				</div>
			</section>

			<section class="quota-review-summary">
				<div class="quota-summary-card">
					<span>Needs Review</span>
					<strong>{{ number(summary.needs_review) }}</strong>
				</div>
				<div class="quota-summary-card">
					<span>Pending Finalize</span>
					<strong>{{ number(summary.pending_finalize) }}</strong>
				</div>
				<div class="quota-summary-card">
					<span>Finalized</span>
					<strong>{{ number(summary.finalized) }}</strong>
				</div>
				<div class="quota-summary-card">
					<span>Total in scope</span>
					<strong>{{ number(summary.total) }}</strong>
				</div>
			</section>

			<section class="quota-review-filters">
				<EdgeDropdown
					:modelValue="filters.status"
					label="Status"
					:options="context.status_options || []"
					@update:modelValue="setFilter('status', $event)"
				/>
				<EdgeLinkField
					:modelValue="filters.company || ''"
					label="Company"
					placeholder="Search company"
					:searcher="companySearcher"
					@select="setCompany($event.value || '')"
					@clear="setCompany('')"
				/>
				<EdgeLinkField
					:modelValue="filters.branch || ''"
					label="Branch"
					placeholder="Search branch"
					:searcher="branchSearcher"
					@select="setFilter('branch', $event.value || '')"
					@clear="setFilter('branch', '')"
				/>
				<EdgeDropdown
					:modelValue="filters.source_doctype"
					label="Source"
					:options="context.source_doctype_options || []"
					@update:modelValue="setFilter('source_doctype', $event)"
				/>
				<label class="quota-input-field">
					<span>From date</span>
					<input class="edge-input" type="date" :value="filters.from_date || ''" @input="setFilter('from_date', $event.target.value)" />
				</label>
				<label class="quota-input-field">
					<span>To date</span>
					<input class="edge-input" type="date" :value="filters.to_date || ''" @input="setFilter('to_date', $event.target.value)" />
				</label>
				<label class="quota-input-field quota-input-field--search">
					<span>Search</span>
					<input
						class="edge-input"
						type="search"
						placeholder="Invoice, reservation, reason…"
						:value="filters.search || ''"
						@keyup.enter="applyFilters"
						@input="setFilter('search', $event.target.value)"
					/>
				</label>
				<button class="edge-button edge-button--secondary" :disabled="loading" @click="applyFilters">
					Apply
				</button>
			</section>

			<section class="quota-review-table-card">
				<div v-if="loading" class="quota-review-empty">Loading quota operations…</div>
				<div v-else-if="!rows.length" class="quota-review-empty">
					<strong>No quota operations found.</strong>
					<span>Adjust the filters or return after sales quota enforcement has recorded activity.</span>
				</div>
				<div v-else class="quota-review-table-wrap">
					<table class="quota-review-table">
						<thead>
							<tr>
								<th>Status</th>
								<th>Source document</th>
								<th>Company / Branch</th>
								<th>Reservation</th>
								<th>Reason</th>
								<th>Attempts</th>
								<th>Last review</th>
								<th>Actions</th>
							</tr>
						</thead>
						<tbody>
							<tr v-for="row in rows" :key="row.name">
								<td><span :class="statusClass(row.status)">{{ row.status }}</span></td>
								<td>
									<button class="quota-link" type="button" @click="openSource(row)">
										{{ row.source_doctype }} · {{ row.source_name }}
									</button>
									<small>{{ dateTime(row.creation) }}</small>
								</td>
								<td>
									<span>{{ row.company || "—" }}</span>
									<small>{{ row.branch || "No branch captured" }}</small>
								</td>
								<td>
									<span>{{ row.reservation_reference || "Unreserved" }}</span>
									<small v-if="row.reservation_expires_on">Expires {{ dateTime(row.reservation_expires_on) }}</small>
								</td>
								<td>
									<span>{{ row.reason_code || "—" }}</span>
									<small>{{ row.last_error || row.remote_message || "" }}</small>
								</td>
								<td>{{ number(row.attempt_count) }}</td>
								<td>
									<span>{{ row.review_action || "—" }}</span>
									<small v-if="row.reviewed_by">{{ row.reviewed_by }} · {{ dateTime(row.reviewed_on) }}</small>
								</td>
								<td class="quota-actions">
									<button class="edge-button edge-button--secondary" type="button" @click="openSource(row)">Open</button>
									<button
										v-if="actionKind(row) === 'retry'"
										class="edge-button edge-button--primary"
										type="button"
										:disabled="acting === row.name"
										@click="retry(row)"
									>
										Retry
									</button>
									<button
										v-if="actionKind(row) === 'review-retry'"
										class="edge-button edge-button--primary"
										type="button"
										:disabled="acting === row.name"
										@click="promptAction(row, 'review-retry')"
									>
										Review & Retry
									</button>
									<button
										v-if="actionKind(row) === 'reconcile'"
										class="edge-button edge-button--primary"
										type="button"
										:disabled="acting === row.name"
										@click="promptAction(row, 'reconcile')"
									>
										Attempt Reconciliation
									</button>
									<span v-if="row.status === 'Needs Review' && !actionKind(row)" class="quota-manual">Platform review required</span>
								</td>
							</tr>
						</tbody>
					</table>
				</div>
			</section>

			<footer class="quota-review-pagination">
				<span>{{ pagination.total_rows || 0 }} matching operation{{ Number(pagination.total_rows || 0) === 1 ? "" : "s" }}</span>
				<div>
					<button class="edge-button edge-button--secondary" :disabled="pagination.page <= 1 || loading" @click="goToPage(pagination.page - 1)">Previous</button>
					<span>Page {{ pagination.page || 1 }} of {{ pagination.total_pages || 1 }}</span>
					<button class="edge-button edge-button--secondary" :disabled="pagination.page >= pagination.total_pages || loading" @click="goToPage(pagination.page + 1)">Next</button>
				</div>
			</footer>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeLinkField", "EdgeDropdown"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

function userError(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

export default {
	name: "CoreEdgeQuotaReview",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			context: {},
			filters: {
				status: "Open",
				company: "",
				branch: "",
				source_doctype: "",
				from_date: "",
				to_date: "",
				search: "",
			},
			rows: [],
			summary: {},
			pagination: { page: 1, page_size: 25, total_rows: 0, total_pages: 1 },
			loading: false,
			acting: "",
			error: "",
			notice: "",
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			canUseNativeDesk: false,
		};
	},
	created() {
		this.edgeUIValid = REQUIRED_COMPONENTS.every((name) => Boolean(runtimeComponents()[name]));
	},
	mounted() {
		if (this.edgeUIValid) this.load();
	},
	methods: {
		async load() {
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext({ force: true })
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([
					callMethod("retailedge.coreedge_quota_review.get_quota_review_context"),
					navigationPromise,
				]);
				this.context = context || {};
				this.filters = { ...this.filters, ...(context.default_filters || {}) };
				this.tenantName = navigation.context?.company || this.filters.company || "";
				this.branchName = navigation.context?.branch || this.filters.branch || "";
				this.userName = navigation.context?.user_name || frappe.session?.user || "";
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				await this.fetchData();
			} catch (error) {
				this.error = userError(error, "Unable to load quota operations review.");
			} finally {
				this.loading = false;
			}
		},
		async fetchData(page = this.pagination.page || 1) {
			if (this.loading && this.rows.length) return;
			this.loading = true;
			this.error = "";
			try {
				const result = await callMethod("retailedge.coreedge_quota_review.list_quota_operations", {
					filters: { ...this.filters },
					page,
					page_size: this.pagination.page_size || 25,
				});
				this.rows = result.rows || [];
				this.summary = result.summary || {};
				this.pagination = result.pagination || this.pagination;
				this.context.can_reconcile = Boolean(result.can_reconcile);
			} catch (error) {
				this.rows = [];
				this.error = userError(error, "Quota operations could not be loaded.");
			} finally {
				this.loading = false;
			}
		},
		applyFilters() {
			this.pagination.page = 1;
			this.fetchData(1);
		},
		setFilter(field, value) {
			this.filters[field] = value ?? "";
			if (field === "branch") this.branchName = value || "";
		},
		setCompany(value) {
			this.filters.company = value || "";
			this.filters.branch = "";
			this.tenantName = value || "";
			this.branchName = "";
		},
		companySearcher(txt) {
			return callMethod("retailedge.coreedge_quota_review.search_quota_review_options", {
				doctype: "Company",
				txt: txt || "",
			});
		},
		branchSearcher(txt) {
			return callMethod("retailedge.coreedge_quota_review.search_quota_review_options", {
				doctype: "Branch",
				txt: txt || "",
				company: this.filters.company || "",
			});
		},
		actionKind(row) {
			if (!this.context.can_reconcile) return "";
			if (row.status === "Pending Finalize") return "retry";
			if (row.status !== "Needs Review") return "";
			if (row.reservation_reference) return "review-retry";
			if (row.reason_code === "FAIL_OPEN_UNRESERVED") return "reconcile";
			return "";
		},
		async retry(row) {
			if (this.acting) return;
			this.acting = row.name;
			this.notice = "";
			try {
				const result = await callMethod("retailedge.coreedge_quota_review.retry_quota_operation", {
					operation_name: row.name,
				});
				this.notice = result.ok
					? "Quota finalization confirmed."
					: "The operation still needs attention. Review the latest reason.";
				await this.fetchData(this.pagination.page);
			} catch (error) {
				this.error = userError(error, "Quota retry failed.");
			} finally {
				this.acting = "";
			}
		},
		promptAction(row, action) {
			frappe.prompt(
				[{
					fieldname: "reason",
					fieldtype: "Small Text",
					label: __("Review reason"),
					reqd: 1,
					description: __("Explain why this quota operation is being retried or reconciled."),
				}],
				(values) => this.runReviewAction(row, action, values.reason),
				__("Quota review"),
				__("Continue")
			);
		},
		async runReviewAction(row, action, reason) {
			if (this.acting) return;
			this.acting = row.name;
			this.notice = "";
			this.error = "";
			const method = action === "reconcile"
				? "retailedge.coreedge_quota_review.reconcile_unreserved_quota_operation"
				: "retailedge.coreedge_quota_review.retry_quota_operation";
			try {
				const result = await callMethod(method, {
					operation_name: row.name,
					reason,
				});
				this.notice = result.ok
					? "Quota reconciliation finalized successfully."
					: "The operation remains in review. Check the updated reason before taking another action.";
				await this.fetchData(this.pagination.page);
			} catch (error) {
				this.error = userError(error, "Quota reconciliation failed.");
			} finally {
				this.acting = "";
			}
		},
		openSource(row) {
			if (!row.source_doctype || !row.source_name) return;
			frappe.set_route("Form", row.source_doctype, row.source_name);
		},
		goToPage(page) {
			const target = Math.min(
				Math.max(1, Number(page || 1)),
				Number(this.pagination.total_pages || 1)
			);
			this.fetchData(target);
		},
		statusClass(status) {
			return {
				"quota-status": true,
				"quota-status--review": status === "Needs Review",
				"quota-status--pending": status === "Pending Finalize",
				"quota-status--finalized": status === "Finalized",
			};
		},
		dateTime(value) {
			if (!value) return "—";
			try { return frappe.datetime.str_to_user(String(value)); } catch (_error) { return String(value); }
		},
		number(value) {
			return Number(value || 0).toLocaleString();
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return "/app/" + item.target;
			if (item.target_type === "Report") return "/app/query-report/" + encodeURIComponent(item.target);
			if (item.target_type === "DocType") {
				return "/app/" + String(item.target || "").toLowerCase().replace(/\s+/g, "-");
			}
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems
				.flatMap((group) => group.items || [])
				.find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
		},
	},
};
</script>

<style scoped>
.quota-review-shell { padding:22px; display:grid; gap:16px; }
.quota-review-header { display:flex; justify-content:space-between; gap:16px; align-items:flex-start; }
.quota-review-header h2 { margin:2px 0 6px; }
.quota-review-header p { margin:0; color:var(--edge-text-muted,#667085); max-width:780px; }
.quota-review-eyebrow { font-size:.75rem; font-weight:700; text-transform:uppercase; letter-spacing:.08em; color:var(--edge-text-muted,#667085); }
.quota-review-alert { padding:12px 14px; border:1px solid var(--edge-border,var(--border-color)); border-radius:10px; background:var(--edge-surface,var(--card-bg)); }
.quota-review-alert--danger { border-color:var(--red-300,#fca5a5); }
.quota-review-status { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:12px; }
.quota-review-status > div { padding:12px 14px; border:1px solid var(--edge-border,var(--border-color)); border-radius:10px; display:grid; gap:4px; }
.quota-review-status span { color:var(--edge-text-muted,#667085); }
.quota-review-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
.quota-summary-card { border:1px solid var(--edge-border,var(--border-color)); border-radius:12px; padding:14px; background:var(--edge-surface,var(--card-bg)); display:grid; gap:6px; }
.quota-summary-card span { color:var(--edge-text-muted,#667085); font-size:.8rem; }
.quota-summary-card strong { font-size:1.45rem; }
.quota-review-filters { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; align-items:end; }
.quota-input-field { display:grid; gap:6px; min-width:0; }
.quota-input-field > span { font-size:.78rem; font-weight:600; color:var(--edge-text-muted,#667085); }
.quota-input-field--search { grid-column:span 2; }
.quota-review-table-card { border:1px solid var(--edge-border,var(--border-color)); border-radius:12px; background:var(--edge-surface,var(--card-bg)); overflow:hidden; }
.quota-review-table-wrap { overflow:auto; }
.quota-review-table { width:100%; border-collapse:collapse; min-width:1200px; }
.quota-review-table th,.quota-review-table td { padding:11px 12px; border-bottom:1px solid var(--edge-border,var(--border-color)); text-align:left; vertical-align:top; }
.quota-review-table th { font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; color:var(--edge-text-muted,#667085); background:var(--edge-surface-subtle,var(--subtle-fg,#f8fafc)); }
.quota-review-table td { font-size:.86rem; }
.quota-review-table td small { display:block; margin-top:4px; color:var(--edge-text-muted,#667085); max-width:260px; white-space:normal; }
.quota-link { border:0; padding:0; background:transparent; color:var(--primary,#2563eb); cursor:pointer; font-weight:600; text-align:left; }
.quota-actions { display:flex; flex-wrap:wrap; gap:6px; min-width:190px; }
.quota-manual { font-size:.76rem; color:var(--edge-text-muted,#667085); align-self:center; }
.quota-status { display:inline-flex; padding:4px 8px; border-radius:999px; font-size:.75rem; font-weight:700; white-space:nowrap; }
.quota-status--review { background:rgba(220,38,38,.1); }
.quota-status--pending { background:rgba(217,119,6,.12); }
.quota-status--finalized { background:rgba(22,163,74,.1); }
.quota-review-empty { padding:36px 20px; display:grid; gap:6px; text-align:center; color:var(--edge-text-muted,#667085); }
.quota-review-pagination { display:flex; justify-content:space-between; align-items:center; gap:12px; color:var(--edge-text-muted,#667085); }
.quota-review-pagination > div { display:flex; align-items:center; gap:10px; }
.quota-review-fallback { margin:20px; padding:16px; border:1px solid var(--edge-border,#d9d9d9); border-radius:10px; display:grid; gap:6px; }
@media (max-width:1000px) {
	.quota-review-summary { grid-template-columns:repeat(2,minmax(0,1fr)); }
	.quota-review-filters { grid-template-columns:repeat(2,minmax(0,1fr)); }
	.quota-review-status { grid-template-columns:1fr; }
}
@media (max-width:640px) {
	.quota-review-shell { padding:14px; }
	.quota-review-header,.quota-review-pagination { flex-direction:column; align-items:stretch; }
	.quota-review-summary,.quota-review-filters { grid-template-columns:1fr; }
	.quota-input-field--search { grid-column:auto; }
}
</style>
