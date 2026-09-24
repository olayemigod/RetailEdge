<template>
	<div v-if="!edgeUIValid" class="settings-fallback">
		<strong>Settings could not start.</strong>
		<span>Required interface components are unavailable. Refresh the page or contact your administrator.</span>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Settings"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/retail-settings"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retail-settings-page">
			<EdgePageHeader
				title="Settings"
				description="Configure operating controls, expenses, audit rules, banking safeguards and platform integrations."
			>
				<template #actions>
					<button type="button" class="edge-button" :disabled="loading || saving" @click="loadSettings">Refresh</button>
					<button type="button" class="edge-button edge-button--primary" :disabled="!canWrite || loading || saving || !dirty" @click="saveSettings">
						{{ saving ? "Saving..." : "Save Changes" }}
					</button>
				</template>
			</EdgePageHeader>

			<EdgeLoadingState v-if="loading && !loaded" message="Loading Settings..." :skeleton="true" />
			<EdgeErrorState v-else-if="error" title="Settings unavailable" :message="error" @retry="loadSettings" />

			<div v-else class="settings-workspace">
				<nav class="settings-tabs" role="tablist" aria-orientation="vertical" aria-label="Settings sections">
					<button
						v-for="group in groups"
						:key="group.key"
						type="button"
						class="settings-tab"
						:class="{ 'is-active': activeKey === group.key }"
						:aria-selected="activeKey === group.key ? 'true' : 'false'"
						role="tab"
						@click="activeKey = group.key"
					>
						{{ group.label }}
					</button>
				</nav>

				<section v-if="activeGroup" class="settings-group">
					<header class="settings-group-header">
						<div>
							<h2>{{ activeGroup.label }}</h2>
							<p>{{ activeGroup.description }}</p>
						</div>
						<span v-if="dirty" class="settings-unsaved">Unsaved changes</span>
					</header>

					<div class="settings-sections">
						<section v-for="section in activeGroup.sections" :key="section.label" class="edge-card settings-section">
							<div class="settings-section-heading">
								<h3>{{ section.label }}</h3>
							</div>
							<div class="settings-fields">
								<template v-for="field in section.fields" :key="field.fieldname">
									<div v-if="fieldVisible(field)" class="settings-field" :class="{ 'settings-field--wide': ['Small Text', 'RoleList'].includes(field.fieldtype) }">
										<label v-if="field.fieldtype === 'Check'" class="settings-check">
											<input
												type="checkbox"
												:checked="Boolean(values[field.fieldname])"
												:disabled="field.read_only || !canWrite"
												@change="setValue(field.fieldname, $event.target.checked ? 1 : 0)"
											/>
											<span>
												<strong>{{ field.label }}</strong>
												<small v-if="field.description">{{ field.description }}</small>
											</span>
										</label>

										<div v-else-if="field.fieldtype === 'RoleList'" class="role-list-field">
											<span class="settings-label">{{ field.label }}</span>
											<small v-if="field.description">{{ field.description }}</small>
											<div v-if="(values[field.fieldname] || []).length" class="role-chips">
												<span v-for="role in values[field.fieldname] || []" :key="role" class="role-chip">
													{{ role }}
													<button v-if="canWrite" type="button" aria-label="Remove role" @click="removeRole(field.fieldname, role)">×</button>
												</span>
											</div>
											<EdgeLinkField
												v-if="canWrite"
												:modelValue="roleDraft[field.fieldname] || ''"
												label="Add Role"
												placeholder="Search roles"
												:searcher="linkSearcher('Role')"
												@select="addRole(field.fieldname, $event)"
												@clear="roleDraft[field.fieldname] = ''"
											/>
										</div>

										<div v-else-if="field.read_only" class="settings-readonly">
											<span class="settings-label">{{ field.label }}</span>
											<strong>{{ values[field.fieldname] || "Not configured" }}</strong>
											<small v-if="field.description">{{ field.description }}</small>
										</div>

										<EdgeDropdown
											v-else-if="field.fieldtype === 'Select'"
											:modelValue="values[field.fieldname]"
											:options="field.options"
											:label="field.label"
											:disabled="!canWrite"
											@update:modelValue="setValue(field.fieldname, $event)"
										/>

										<EdgeLinkField
											v-else-if="field.fieldtype === 'Link'"
											:modelValue="values[field.fieldname] || ''"
											:label="field.label"
											:placeholder="'Search ' + field.label.toLowerCase()"
											:searcher="linkSearcher(field.link_doctype)"
											:disabled="!canWrite"
											@select="setValue(field.fieldname, $event.value || '')"
											@clear="setValue(field.fieldname, '')"
										/>

										<label v-else class="settings-input-wrap">
											<span>{{ field.label }}</span>
											<textarea
												v-if="field.fieldtype === 'Small Text'"
												:value="values[field.fieldname] || ''"
												class="edge-input"
												rows="3"
												:disabled="!canWrite"
												@input="setValue(field.fieldname, $event.target.value)"
											></textarea>
											<input
												v-else
												:value="values[field.fieldname] ?? ''"
												class="edge-input"
												:type="numericField(field) ? 'number' : 'text'"
												:step="field.fieldtype === 'Currency' ? '0.01' : '1'"
												:disabled="!canWrite"
												@input="setValue(field.fieldname, numericField(field) ? Number($event.target.value || 0) : $event.target.value)"
											/>
											<small v-if="field.description">{{ field.description }}</small>
										</label>
									</div>
								</template>
							</div>
						</section>
					</div>
				</section>

				<div v-if="saveError" class="settings-error">{{ saveError }}</div>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeDropdown", "EdgeLinkField"];
const CONTEXT_METHOD = "retailedge.retailedge.page.retail_settings.retail_settings.get_settings_context";
const SAVE_METHOD = "retailedge.retailedge.page.retail_settings.retail_settings.save_settings";

function runtimeComponents() { return window.EdgeSuiteUI?.components || {}; }
function callMethod(method, args = {}) {
	return new Promise((resolve, reject) => frappe.call({ method, args, callback: (response) => resolve(response.message || {}), error: reject }));
}
function userError(error, fallback) { return window.retailedge?.userErrorMessage?.(error, fallback) || fallback; }

export default {
	name: "RetailSettings",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			saving: false,
			error: "",
			saveError: "",
			groups: [],
			values: {},
			roleDraft: {},
			activeKey: "",
			canWrite: false,
			dirty: false,
			menuItems: [],
			tenantName: "",
			branchName: "",
			userName: "",
			canUseNativeDesk: false,
		};
	},
	computed: {
		activeGroup() { return this.groups.find((group) => group.key === this.activeKey) || this.groups[0] || null; },
	},
	created() {
		const runtime = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !runtime[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.consumeRouteOptions();
	},
	mounted() {
		window.addEventListener("retailedge-settings-page-show", this._onPageShow);
		this.consumeRouteOptions();
		if (this.edgeUIValid) this.loadSettings();
	},
	beforeUnmount() { window.removeEventListener("retailedge-settings-page-show", this._onPageShow); },
	methods: {
		consumeRouteOptions() {
			const options = frappe.route_options || {};
			if (options.settings_section) this.activeKey = String(options.settings_section);
			frappe.route_options = null;
		},
		hydrate(groups) {
			this.groups = Array.isArray(groups) ? groups : [];
			const next = {};
			this.groups.forEach((group) => (group.sections || []).forEach((section) => (section.fields || []).forEach((field) => {
				next[field.fieldname] = field.fieldtype === "RoleList" ? [...(field.value || [])] : field.value;
			})));
			this.values = next;
			if (!this.activeKey || !this.groups.some((group) => group.key === this.activeKey)) this.activeKey = this.groups[0]?.key || "";
			this.dirty = false;
		},
		async loadSettings() {
			if (this.loading) return;
			this.loading = true; this.error = ""; this.saveError = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext({ force: true })
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [context, navigation] = await Promise.all([callMethod(CONTEXT_METHOD), navigationPromise]);
				this.hydrate(context.groups || []);
				this.canWrite = Boolean(context.can_write);
				this.tenantName = navigation.context?.company || "";
				this.branchName = navigation.context?.branch || "";
				this.userName = navigation.context?.user_name || frappe.session?.user || "";
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.loaded = true;
				this.consumeRouteOptions();
			} catch (error) { this.error = userError(error, "Unable to load Settings."); }
			finally { this.loading = false; }
		},
		async saveSettings() {
			if (!this.canWrite || this.saving || !this.dirty) return;
			this.saving = true; this.saveError = "";
			try {
				const result = await callMethod(SAVE_METHOD, { values: this.values });
				this.hydrate(result.groups || []);
				frappe.show_alert?.({ message: "Settings saved", indicator: "green" });
			} catch (error) { this.saveError = userError(error, "Settings could not be saved."); }
			finally { this.saving = false; }
		},
		setValue(fieldname, value) { this.values[fieldname] = value; this.dirty = true; },
		numericField(field) { return ["Int", "Currency", "Float", "Percent"].includes(field.fieldtype); },
		fieldVisible(field) {
			const rule = String(field.depends_on || "").trim();
			if (!rule) return true;
			if (!rule.startsWith("eval:")) return true;
			const dependencies = [...rule.matchAll(/doc\.([A-Za-z0-9_]+)/g)].map((match) => match[1]);
			if (!dependencies.length) return true;
			return dependencies.every((fieldname) => Boolean(this.values[fieldname]));
		},
		addRole(fieldname, option) {
			const role = String(option?.value || option?.label || "").trim();
			if (!role) return;
			const roles = [...(this.values[fieldname] || [])];
			if (!roles.includes(role)) roles.push(role);
			this.values[fieldname] = roles;
			this.roleDraft[fieldname] = "";
			this.dirty = true;
		},
		removeRole(fieldname, role) {
			this.values[fieldname] = (this.values[fieldname] || []).filter((item) => item !== role);
			this.dirty = true;
		},
		linkSearcher(doctype) {
			return async (txt) => {
				if (!doctype) return [];
				const response = await frappe.call({
					method: "frappe.desk.search.search_link",
					args: { doctype, txt: txt || "", page_length: 20 },
				});
				return (response.message || []).map((row) => ({
					value: row.value || row.name,
					label: row.label || row.value || row.name,
					description: row.description || "",
				}));
			};
		},
		mapNavigationGroups(groups) { return (groups || []).map((group) => ({ ...group, items: (group.items || []).map((item) => ({ ...item, route: this.routeForItem(item) })) })); },
		routeForItem(item) {
			if (item.target_type === "Page") return "/app/" + item.target;
			if (item.target_type === "Report") return "/app/query-report/" + encodeURIComponent(item.target);
			if (item.target_type === "DocType") return "/app/" + String(item.target || "").toLowerCase().replace(/\s+/g, "-");
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (item.target_type === "DocType") frappe.set_route("List", item.target);
			else if (item.target_type === "URL" && item.target) window.location.assign(item.target);
		},
	},
};
</script>

<style scoped>
.settings-workspace {
	display:grid;
	grid-template-columns:minmax(220px, 280px) minmax(0, 1fr);
	gap:1.25rem;
	align-items:start;
	min-width:0;
}
.settings-tabs {
	display:grid;
	gap:.35rem;
	position:sticky;
	top:1rem;
	max-height:calc(100vh - 2rem);
	overflow-y:auto;
	padding:.65rem;
	border:1px solid var(--edge-border, var(--border-color));
	border-radius:.8rem;
	background:var(--edge-surface, var(--card-bg));
	box-shadow:0 1px 2px rgba(16,24,40,.04);
}
.settings-tab {
	width:100%;
	border:1px solid transparent;
	border-radius:.6rem;
	background:transparent;
	color:var(--edge-text, var(--text-color));
	padding:.72rem .8rem;
	font-weight:600;
	text-align:left;
	line-height:1.3;
	cursor:pointer;
}
.settings-tab:hover {
	background:var(--edge-surface-soft, #f8fafc);
}
.settings-tab.is-active {
	border-color:var(--edge-primary, #0056a6);
	background:var(--edge-primary-subtle, #eef6ff);
	color:var(--edge-primary-strong, #003e73);
}
.settings-group { display:grid; gap:1rem; min-width:0; }
.settings-group-header { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; }
.settings-group-header h2 { margin:0 0 .3rem; }
.settings-group-header p { margin:0; color:var(--edge-text-muted, #667085); }
.settings-unsaved { flex:0 0 auto; border:1px solid var(--orange-300, #f7b955); border-radius:999px; padding:.25rem .65rem; font-size:.78rem; font-weight:600; }
.settings-sections { display:grid; gap:1rem; }
.settings-section { padding:1.2rem; }
.settings-section-heading { margin-bottom:1rem; padding-bottom:.7rem; border-bottom:1px solid var(--edge-border, var(--border-color)); }
.settings-section-heading h3 { margin:0; }
.settings-fields { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:1rem 1.25rem; align-items:start; }
.settings-field { min-width:0; }
.settings-field--wide { grid-column:1 / -1; }
.settings-check { display:flex; gap:.75rem; align-items:flex-start; padding:.85rem; border:1px solid var(--edge-border, var(--border-color)); border-radius:.65rem; background:var(--edge-surface, var(--card-bg)); }
.settings-check input { margin-top:.2rem; width:1.05rem; height:1.05rem; }
.settings-check span, .settings-readonly, .settings-input-wrap, .role-list-field { display:grid; gap:.3rem; }
.settings-check small, .settings-input-wrap small, .settings-readonly small, .role-list-field small { color:var(--edge-text-muted, #667085); line-height:1.45; }
.settings-label, .settings-input-wrap > span { font-weight:600; font-size:.82rem; }
.settings-readonly { padding:.8rem; border:1px solid var(--edge-border, var(--border-color)); border-radius:.65rem; }
.role-chips { display:flex; flex-wrap:wrap; gap:.4rem; margin:.3rem 0; }
.role-chip { display:inline-flex; align-items:center; gap:.35rem; padding:.3rem .55rem; border:1px solid var(--edge-border, var(--border-color)); border-radius:999px; background:var(--edge-surface-soft, #f8fafc); font-size:.82rem; }
.role-chip button { border:0; background:transparent; cursor:pointer; color:inherit; font-size:1rem; line-height:1; padding:0; }
.settings-error { grid-column:1 / -1; padding:.8rem 1rem; border:1px solid var(--edge-danger, #d92d20); border-radius:.6rem; background:var(--edge-danger-subtle, #fef3f2); color:var(--edge-danger, #b42318); }
.settings-fallback { margin:20px; padding:16px; border:1px solid var(--edge-border, #d9d9d9); border-radius:10px; display:grid; gap:6px; }
@media (max-width:980px) {
	.settings-workspace { grid-template-columns:1fr; }
	.settings-tabs { position:static; max-height:none; }
}
@media (max-width:760px) {
	.settings-fields { grid-template-columns:1fr; }
	.settings-field--wide { grid-column:auto; }
	.settings-group-header { flex-direction:column; }
}
</style>
