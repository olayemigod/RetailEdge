<template>
	<div v-if="!uiReady" class="pricing-fallback">
		<strong>Pricing & Promotions could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="retailedge"
		title="Pricing & Promotions"
		:tenantName="company"
		:branchName="branch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/pricing-promotions-control"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<div class="pricing-workspace">
			<section class="pricing-hero">
				<div>
					<span class="pricing-kicker">Commercial Control</span>
					<h2>Pricing & Promotions</h2>
					<p>{{ description }}</p>
				</div>
				<button
					v-if="activeArea?.can_create"
					type="button"
					class="edge-button edge-button--primary"
					@click="createRecord"
				>
					Create {{ singularLabel(activeArea.label) }}
				</button>
			</section>

			<div v-if="loadingWorkspace" class="pricing-state">Loading pricing setup…</div>
			<div v-else-if="workspaceError" class="pricing-state pricing-state--error">
				<strong>Unable to load Pricing & Promotions.</strong>
				<span>{{ workspaceError }}</span>
				<button type="button" class="edge-button edge-button--secondary" @click="loadWorkspace">Try again</button>
			</div>

			<template v-else>
				<nav class="pricing-tabs" role="tablist" aria-label="Pricing and promotions areas">
					<button
						v-for="area in areas"
						:key="area.key"
						type="button"
						class="pricing-tab"
						:class="{ active: area.key === activeKey }"
						role="tab"
						:aria-selected="area.key === activeKey ? 'true' : 'false'"
						@click="selectArea(area.key)"
					>
						{{ area.label }}
					</button>
				</nav>

				<section v-if="activeArea" class="pricing-panel">
					<div class="pricing-panel-heading">
						<div>
							<h3>{{ activeArea.label }}</h3>
							<p>{{ activeArea.description }}</p>
						</div>
						<div class="pricing-panel-actions">
							<button type="button" class="edge-button edge-button--secondary" @click="clearFilters">
								Clear filters
							</button>
							<button
								v-if="activeArea.can_create"
								type="button"
								class="edge-button edge-button--primary"
								@click="createRecord"
							>
								Create {{ singularLabel(activeArea.label) }}
							</button>
						</div>
					</div>

					<div class="pricing-filters">
						<EdgeInput
							v-model="search"
							label="Search"
							type="search"
							:placeholder="searchPlaceholder"
							@input="scheduleReload"
						/>
						<template v-for="filter in activeArea.filters || []" :key="filter.fieldname">
							<EdgeDropdown
								v-if="filter.type === 'boolean'"
								:modelValue="filterValues[filter.fieldname] || ''"
								:label="filter.label"
								:options="booleanOptions"
								@update:modelValue="setFilter(filter.fieldname, $event)"
							/>
							<EdgeInput
								v-else
								:modelValue="filterValues[filter.fieldname] || ''"
								:label="filter.label"
								:type="filter.type === 'date_from' || filter.type === 'date_to' ? 'date' : 'text'"
								@update:modelValue="setFilter(filter.fieldname, $event)"
							/>
						</template>
					</div>

					<div v-if="recordsError" class="pricing-inline-error" role="alert">{{ recordsError }}</div>
					<EdgeLoadingState v-if="loadingRecords && !rows.length" message="Loading records..." />
					<EdgeEmptyState
						v-else-if="!loadingRecords && !rows.length"
						title="No matching records"
						description="Adjust the filters or create a new record."
					/>

					<div v-else class="pricing-table-wrap">
						<table class="pricing-table">
							<thead>
								<tr>
									<th v-for="column in activeArea.columns" :key="column.fieldname" scope="col">
										<button type="button" class="pricing-sort" @click="setSort(column.fieldname)">
											<span>{{ column.label }}</span>
											<span v-if="sortBy === column.fieldname" aria-hidden="true">{{ sortOrder === "asc" ? "▲" : "▼" }}</span>
										</button>
									</th>
									<th scope="col" class="pricing-actions-column">Actions</th>
								</tr>
							</thead>
							<tbody>
								<tr v-for="row in rows" :key="row.name">
									<td
										v-for="column in activeArea.columns"
										:key="`${row.name}:${column.fieldname}`"
										:title="displayValue(row[column.fieldname], column.fieldname)"
									>
										{{ displayValue(row[column.fieldname], column.fieldname) }}
									</td>
									<td class="pricing-actions-column">
										<button type="button" class="edge-button edge-button--secondary pricing-edit" @click="editRecord(row)">
											{{ activeArea.can_write ? "Edit" : "View" }}
										</button>
									</td>
								</tr>
							</tbody>
						</table>
					</div>

					<div v-if="rows.length" class="pricing-footer">
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
		</div>
	</EdgeAppShell>
</template>

<script>
const CONTEXT_METHOD = "retailedge.pricing_promotions_workspace.get_pricing_promotions_workspace";
const RECORDS_METHOD = "retailedge.pricing_promotions_workspace.get_pricing_promotions_records";
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgeInput", "EdgeDropdown", "EdgeLoadingState", "EdgeEmptyState"];

function runtimeComponents() {
	const edgeUI = typeof window !== "undefined" ? window.EdgeSuiteUI || window.EdgeUI : null;
	return edgeUI?.components || edgeUI || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: reject,
		});
	});
}

function cleanError(error, fallback) {
	return window.retailedge?.userErrorMessage?.(error, fallback) || fallback;
}

function doctypeSlug(doctype) {
	return String(doctype || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");
}

export default {
	name: "PricingPromotionsWorkspace",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			uiReady: true,
			loadingWorkspace: true,
			workspaceError: "",
			loadingRecords: false,
			loadingMore: false,
			recordsError: "",
			description: "",
			company: "",
			branch: "",
			userName: "",
			areas: [],
			activeKey: "",
			rows: [],
			search: "",
			filterValues: {},
			hasMore: false,
			nextStart: 0,
			sortBy: "modified",
			sortOrder: "desc",
			requestToken: 0,
			searchTimer: null,
			menuItems: [],
			canUseNativeDesk: false,
			booleanOptions: [
				{ value: "", label: "All" },
				{ value: "Yes", label: "Yes" },
				{ value: "No", label: "No" },
			],
		};
	},
	computed: {
		activeArea() {
			return this.areas.find((area) => area.key === this.activeKey) || this.areas[0] || null;
		},
		searchPlaceholder() {
			return this.activeArea ? `Search ${this.activeArea.label.toLowerCase()}` : "Search";
		},
	},
	created() {
		const components = runtimeComponents();
		this.uiReady = REQUIRED_COMPONENTS.every((name) => Boolean(components[name]));
	},
	mounted() {
		if (this.uiReady) this.loadWorkspace();
	},
	beforeUnmount() {
		if (this.searchTimer) window.clearTimeout(this.searchTimer);
		this.requestToken += 1;
	},
	methods: {
		async loadWorkspace() {
			this.loadingWorkspace = true;
			this.workspaceError = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [workspace, navigation] = await Promise.all([
					callMethod(CONTEXT_METHOD),
					navigationPromise,
				]);
				this.description = workspace.description || "";
				this.company = workspace.company || navigation.context?.company || "";
				this.branch = workspace.branch || navigation.context?.branch || "";
				this.userName = workspace.user_name || navigation.context?.user_name || "";
				this.areas = Array.isArray(workspace.areas) ? workspace.areas : [];
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				if (!this.areas.some((area) => area.key === this.activeKey)) {
					this.activeKey = this.areas[0]?.key || "";
				}
				await this.reload();
			} catch (error) {
				this.workspaceError = cleanError(error, "Pricing & Promotions failed to load.");
			} finally {
				this.loadingWorkspace = false;
			}
		},
		selectArea(key) {
			if (key === this.activeKey) return;
			this.activeKey = key;
			this.search = "";
			this.filterValues = {};
			this.rows = [];
			this.hasMore = false;
			this.nextStart = 0;
			this.sortBy = "modified";
			this.sortOrder = "desc";
			this.reload();
		},
		setFilter(fieldname, value) {
			this.filterValues = { ...this.filterValues, [fieldname]: value || "" };
			this.scheduleReload();
		},
		clearFilters() {
			this.search = "";
			this.filterValues = {};
			this.reload();
		},
		setSort(fieldname) {
			if (!fieldname) return;
			if (this.sortBy === fieldname) {
				this.sortOrder = this.sortOrder === "asc" ? "desc" : "asc";
			} else {
				this.sortBy = fieldname;
				this.sortOrder = "asc";
			}
			this.reload();
		},
		scheduleReload() {
			if (this.searchTimer) window.clearTimeout(this.searchTimer);
			this.searchTimer = window.setTimeout(() => this.reload(), 280);
		},
		async reload() {
			if (!this.activeArea) return;
			const token = ++this.requestToken;
			this.loadingRecords = true;
			this.recordsError = "";
			try {
				const result = await this.fetchRecords(0);
				if (token !== this.requestToken) return;
				this.rows = Array.isArray(result.rows) ? result.rows : [];
				this.hasMore = Boolean(result.has_more);
				this.nextStart = Number(result.next_start || this.rows.length);
			} catch (error) {
				if (token !== this.requestToken) return;
				this.rows = [];
				this.hasMore = false;
				this.nextStart = 0;
				this.recordsError = cleanError(error, `Could not load ${this.activeArea.label}.`);
			} finally {
				if (token === this.requestToken) this.loadingRecords = false;
			}
		},
		async loadMore() {
			if (!this.activeArea || !this.hasMore || this.loadingMore) return;
			this.loadingMore = true;
			this.recordsError = "";
			try {
				const result = await this.fetchRecords(this.nextStart);
				const nextRows = Array.isArray(result.rows) ? result.rows : [];
				const existing = new Set(this.rows.map((row) => row.name));
				this.rows = [...this.rows, ...nextRows.filter((row) => !existing.has(row.name))];
				this.hasMore = Boolean(result.has_more);
				this.nextStart = Number(result.next_start || this.rows.length);
			} catch (error) {
				this.recordsError = cleanError(error, `Could not load more ${this.activeArea.label}.`);
			} finally {
				this.loadingMore = false;
			}
		},
		fetchRecords(start) {
			return callMethod(RECORDS_METHOD, {
				area: this.activeArea.key,
				search: String(this.search || "").trim(),
				filters: this.filterValues,
				start,
				page_length: 25,
				sort_by: this.sortBy,
				sort_order: this.sortOrder,
			});
		},
		createRecord() {
			if (!this.activeArea?.can_create) return;
			frappe.new_doc(this.activeArea.doctype);
		},
		editRecord(row) {
			if (!this.activeArea?.doctype || !row?.name) return;
			frappe.set_route("Form", this.activeArea.doctype, row.name);
		},
		singularLabel(label) {
			const values = {
				"Price Lists": "Price List",
				"Item Prices": "Item Price",
				"Pricing Rules": "Pricing Rule",
				"Promotional Schemes": "Promotional Scheme",
				"Coupon Codes": "Coupon Code",
				"Loyalty Programs": "Loyalty Program",
			};
			return values[label] || String(label || "Record").replace(/s$/, "");
		},
		displayValue(value, fieldname) {
			if (value === null || value === undefined || value === "") return "—";
			if (["enabled", "selling", "buying", "disable"].includes(fieldname)) return Number(value) ? "Yes" : "No";
			if (
				["modified", "valid_from", "valid_upto", "from_date", "to_date"].includes(fieldname)
				&& frappe.datetime?.str_to_user
			) {
				try {
					return frappe.datetime.str_to_user(String(value));
				} catch (_error) {
					return String(value);
				}
			}
			if (typeof value === "number") {
				return value.toLocaleString(undefined, { maximumFractionDigits: 4 });
			}
			return String(value);
		},
		mapNavigationGroups(groups) {
			return (groups || []).map((group) => ({
				...group,
				items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })),
			}));
		},
		routeForItem(item) {
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			if (item.target_type === "DocType") return `/app/${doctypeSlug(item.target)}`;
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
	},
};
</script>

<style scoped>
.pricing-workspace { display:grid; gap:1rem; padding:1.25rem; min-width:0; }
.pricing-hero,.pricing-panel,.pricing-state {
	border:1px solid var(--edge-color-border,var(--border-color));
	border-radius:var(--edge-radius-lg,14px);
	background:var(--edge-color-surface,var(--card-bg,var(--fg-color)));
	padding:1.25rem;
}
.pricing-hero { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
.pricing-hero h2,.pricing-panel h3 { margin:.2rem 0 .35rem; color:var(--edge-color-ink-950,var(--heading-color,var(--text-color))); }
.pricing-hero p,.pricing-panel-heading p { margin:0; color:var(--edge-color-ink-500,var(--text-muted)); }
.pricing-kicker { font-size:.75rem; font-weight:700; letter-spacing:.04em; text-transform:uppercase; color:var(--edge-color-ink-500,var(--text-muted)); }
.pricing-tabs { display:flex; gap:.35rem; overflow-x:auto; border-bottom:1px solid var(--edge-color-border,var(--border-color)); padding:0 .25rem; }
.pricing-tab { appearance:none; border:0; border-bottom:2px solid transparent; background:transparent; color:var(--edge-color-ink-500,var(--text-muted)); padding:.75rem .9rem; font:inherit; font-weight:650; white-space:nowrap; cursor:pointer; }
.pricing-tab:hover { color:var(--edge-color-ink-950,var(--text-color)); background:var(--edge-color-surface-muted,var(--control-bg)); }
.pricing-tab.active { color:var(--edge-color-brand-700,var(--primary)); border-bottom-color:var(--edge-color-brand-600,var(--primary)); }
.pricing-panel { display:grid; gap:1rem; }
.pricing-panel-heading { display:flex; align-items:flex-start; justify-content:space-between; gap:1rem; }
.pricing-panel-actions { display:flex; flex-wrap:wrap; gap:.5rem; justify-content:flex-end; }
.pricing-filters { display:grid; grid-template-columns:repeat(auto-fit,minmax(12rem,1fr)); gap:.75rem; align-items:end; }
.pricing-table-wrap { width:100%; overflow:auto; border:1px solid var(--edge-color-border,var(--border-color)); border-radius:.75rem; }
.pricing-table { width:100%; min-width:60rem; border-collapse:collapse; table-layout:auto; }
.pricing-table th,.pricing-table td { padding:.75rem; border-bottom:1px solid var(--edge-color-border,var(--border-color)); text-align:left; white-space:nowrap; max-width:18rem; overflow:hidden; text-overflow:ellipsis; }
.pricing-table th { background:var(--edge-color-surface-muted,var(--control-bg)); color:var(--edge-color-ink-500,var(--text-muted)); font-size:.72rem; font-weight:700; letter-spacing:.035em; text-transform:uppercase; }
.pricing-sort { display:flex; align-items:center; gap:.35rem; width:100%; border:0; background:transparent; color:inherit; padding:0; font:inherit; font-weight:inherit; letter-spacing:inherit; text-transform:inherit; cursor:pointer; text-align:left; }
.pricing-table tbody tr:last-child td { border-bottom:0; }
.pricing-table tbody tr:hover { background:color-mix(in srgb,var(--edge-color-brand-50) 38%,transparent); }
.pricing-actions-column { width:8.75rem; text-align:right !important; }
.pricing-edit { width:100%; white-space:nowrap; }
.pricing-footer { display:flex; justify-content:space-between; align-items:center; gap:1rem; color:var(--edge-color-ink-500,var(--text-muted)); }
.pricing-inline-error,.pricing-state--error { color:var(--red-600,#b42318); }
.pricing-state { display:grid; gap:.75rem; justify-items:start; }
.pricing-fallback { display:grid; gap:.5rem; padding:1.5rem; }
@media (max-width:768px) {
	.pricing-workspace { padding:.75rem; }
	.pricing-hero,.pricing-panel-heading { flex-direction:column; align-items:stretch; }
	.pricing-panel-actions { justify-content:flex-start; }
	.pricing-table { min-width:48rem; }
}
</style>
