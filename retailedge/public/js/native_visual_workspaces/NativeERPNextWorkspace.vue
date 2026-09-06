<template>
	<div v-if="!edgeUIValid" class="native-workspace-fallback">
		<strong>{{ title || "RetailEdge control workspace" }} could not start.</strong>
		<span>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		:title="title"
		:tenantName="company"
		:branchName="branch"
		:userName="userName"
		:menuItems="menuItems"
		:activeRoute="activeRoute"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<div class="native-control-workspace">
			<section class="native-control-hero">
				<div>
					<div class="native-control-eyebrow">{{ eyebrow }}</div>
					<h2>{{ title }}</h2>
					<p>{{ description }}</p>
				</div>
				<div class="native-control-badges" aria-label="Workspace authority">
					<span>EdgeSuite workspace</span>
					<span>{{ sourceOfTruth }} source of truth</span>
					<span>Native lifecycle handoff</span>
				</div>
			</section>

			<div v-if="loading" class="native-control-state">Loading {{ title }}…</div>
			<div v-else-if="error" class="native-control-state native-control-error">
				<strong>Unable to load this workspace.</strong>
				<span>{{ error }}</span>
				<button class="edge-secondary-button" type="button" @click="loadWorkspace">Retry</button>
			</div>
			<template v-else>
				<section class="native-control-section">
					<div class="native-control-section-heading">
						<div>
							<h3>Work areas</h3>
							<p>Only ERPNext capabilities you are permitted to use are shown.</p>
						</div>
					</div>
					<div class="native-control-card-grid">
						<article v-for="source in sources" :key="`${source.kind}:${source.target}`" class="native-control-card">
							<div class="native-control-card-copy">
								<span class="native-control-kind">{{ kindLabel(source.kind) }}</span>
								<h4>{{ source.label }}</h4>
								<p>{{ source.description }}</p>
							</div>
							<div class="native-control-card-actions">
								<button class="edge-primary-button" type="button" @click="openSource(source)">
									{{ source.kind === "report" ? "Open report" : source.kind === "page" ? "Open workspace" : "Open records" }}
								</button>
								<button
									v-if="source.kind === 'doctype' && source.can_create"
									class="edge-secondary-button"
									type="button"
									@click="createSource(source)"
								>
									New
								</button>
							</div>
						</article>
					</div>
				</section>

				<section v-for="source in recordSources" :key="`recent:${source.target}`" class="native-control-section">
					<div class="native-control-section-heading">
						<div>
							<h3>{{ source.label }}</h3>
							<p>{{ source.preview_label }} permission-filtered ERPNext records. Open a row for the authoritative document.</p>
						</div>
						<button class="edge-secondary-button" type="button" @click="openSource(source)">View all</button>
					</div>
					<div v-if="source.rows.length" class="native-control-table-wrap">
						<table class="native-control-table">
							<thead>
								<tr>
									<th v-for="column in source.columns" :key="column.fieldname" scope="col">{{ column.label }}</th>
								</tr>
							</thead>
							<tbody>
								<tr
									v-for="row in source.rows"
									:key="row.name"
									tabindex="0"
									@click="openRow(source, row)"
									@keydown.enter="openRow(source, row)"
								>
									<td v-for="column in source.columns" :key="`${row.name}:${column.fieldname}`">
										{{ formatValue(row[column.fieldname], column.fieldname) }}
									</td>
								</tr>
							</tbody>
						</table>
					</div>
					<div v-else class="native-control-empty">No accessible {{ source.label.toLowerCase() }} found.</div>
				</section>

				<section class="native-control-note">
					<strong>Accounting and workflow safety</strong>
					<p>
						This EdgeSuite surface is read-only. Creation and changes continue through ERPNext's permitted native document and report workflows; RetailEdge does not create a second ledger, lifecycle, commission engine, or budget engine here.
					</p>
				</section>
			</template>
		</div>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function errorMessage(error, fallback) {
	return error?.message || error?.exc || error?.exception || fallback;
}

export default {
	name: "NativeERPNextWorkspace",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	props: {
		workspaceKey: { type: String, required: true },
	},
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: true,
			error: "",
			title: "RetailEdge Control",
			eyebrow: "Operational Control",
			description: "",
			company: "",
			branch: "",
			userName: "",
			pageRoute: "",
			sourceOfTruth: "ERPNext",
			sources: [],
			menuItems: [],
		};
	},
	computed: {
		activeRoute() {
			return this.pageRoute ? `/app/${this.pageRoute}` : "";
		},
		recordSources() {
			return this.sources.filter((source) => source.kind === "doctype");
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
	},
	mounted() {
		this.loadWorkspace();
	},
	methods: {
		async loadWorkspace() {
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext()
					: callMethod("retailedge.edgesuite_ui.get_retailedge_business_hub_context");
				const [workspace, navigation] = await Promise.all([
					callMethod("retailedge.native_visual_workspaces.get_native_visual_workspace", { workspace: this.workspaceKey }),
					navigationPromise,
				]);
				this.title = workspace.title || this.title;
				this.eyebrow = workspace.eyebrow || this.eyebrow;
				this.description = workspace.description || "";
				this.company = workspace.company || "";
				this.branch = workspace.branch || "";
				this.userName = workspace.user_name || "";
				this.pageRoute = workspace.page_route || "";
				this.sourceOfTruth = workspace.source_of_truth || "ERPNext";
				this.sources = Array.isArray(workspace.sources) ? workspace.sources : [];
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
			} catch (error) {
				this.error = errorMessage(error, "Failed to load the RetailEdge control workspace.");
			} finally {
				this.loading = false;
			}
		},
		kindLabel(kind) {
			if (kind === "doctype") return "ERPNext records";
			if (kind === "report") return "ERPNext report";
			if (kind === "page") return "EdgeSuite workspace";
			return "Workspace";
		},
		openSource(source) {
			if (source.kind === "doctype") frappe.set_route("List", source.target);
			else if (source.kind === "report") frappe.set_route("query-report", source.target);
			else if (source.kind === "page") frappe.set_route(source.target);
		},
		createSource(source) {
			if (source.kind !== "doctype" || !source.can_create) return;
			frappe.new_doc(source.target);
		},
		openRow(source, row) {
			if (source.kind !== "doctype" || !row?.name) return;
			frappe.set_route("Form", source.target, row.name);
		},
		formatValue(value, fieldname) {
			if (value === null || value === undefined || value === "") return "—";
			if (fieldname === "modified" && frappe.datetime?.str_to_user) return frappe.datetime.str_to_user(value);
			if (value === 0) return "No";
			if (value === 1) return "Yes";
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
			if (item.target_type === "DocType") return `/app/${String(item.target || "").toLowerCase().replace(/\s+/g, "-")}`;
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
.native-control-workspace {
	display: grid;
	gap: 1.25rem;
	padding: 1.25rem;
}
.native-control-hero,
.native-control-section,
.native-control-note,
.native-control-state {
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius-lg, 12px);
	background: var(--card-bg, var(--fg-color));
	padding: 1.25rem;
}
.native-control-hero {
	display: flex;
	justify-content: space-between;
	gap: 1rem;
	align-items: flex-start;
}
.native-control-hero h2,
.native-control-section h3,
.native-control-card h4 {
	margin: 0;
	color: var(--heading-color, var(--text-color));
}
.native-control-hero p,
.native-control-section-heading p,
.native-control-card p,
.native-control-note p {
	margin: 0.35rem 0 0;
	color: var(--text-muted);
}
.native-control-eyebrow,
.native-control-kind {
	font-size: 0.75rem;
	font-weight: 600;
	letter-spacing: 0.04em;
	text-transform: uppercase;
	color: var(--text-muted);
}
.native-control-badges {
	display: flex;
	flex-wrap: wrap;
	gap: 0.4rem;
	justify-content: flex-end;
}
.native-control-badges span,
.native-control-kind {
	border: 1px solid var(--border-color);
	border-radius: 999px;
	padding: 0.3rem 0.55rem;
}
.native-control-card-grid {
	display: grid;
	grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
	gap: 0.85rem;
	margin-top: 1rem;
}
.native-control-card {
	display: flex;
	flex-direction: column;
	justify-content: space-between;
	gap: 1rem;
	min-height: 180px;
	border: 1px solid var(--border-color);
	border-radius: var(--border-radius, 8px);
	padding: 1rem;
	background: var(--fg-color);
}
.native-control-card-copy {
	display: grid;
	gap: 0.45rem;
}
.native-control-card-actions,
.native-control-section-heading {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 0.75rem;
}
.native-control-table-wrap {
	overflow-x: auto;
	margin-top: 1rem;
}
.native-control-table {
	width: 100%;
	border-collapse: collapse;
}
.native-control-table th,
.native-control-table td {
	padding: 0.7rem;
	border-bottom: 1px solid var(--border-color);
	text-align: left;
	white-space: nowrap;
}
.native-control-table tbody tr {
	cursor: pointer;
}
.native-control-table tbody tr:hover,
.native-control-table tbody tr:focus-within,
.native-control-table tbody tr:focus {
	background: var(--control-bg, var(--subtle-fg));
	outline: none;
}
.native-control-empty,
.native-control-state {
	color: var(--text-muted);
}
.native-control-state {
	display: grid;
	gap: 0.75rem;
	justify-items: start;
}
.native-workspace-fallback {
	display: grid;
	gap: 0.5rem;
	padding: 1.5rem;
}
@media (max-width: 768px) {
	.native-control-hero,
	.native-control-section-heading {
		flex-direction: column;
		align-items: stretch;
	}
	.native-control-badges {
		justify-content: flex-start;
	}
}
</style>
