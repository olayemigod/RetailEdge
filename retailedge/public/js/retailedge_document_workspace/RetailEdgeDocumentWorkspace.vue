<template>
	<EdgeAppShell
		product="retailedge"
		title="RetailEdge"
		:tenant-name="identity.tenant_name || identity.company || ''"
		:branch-name="identity.branch || 'All permitted branches'"
		:user-name="userName"
		active-route="/app/retailedge-document-workspace"
		@navigate="openRoute"
		data-edge-product="retailedge"
	>
		<EdgePageLayout>
			<template #header>
				<EdgePageHeader
					eyebrow="Retail Setup"
					:title="pageTitle"
					:subtitle="pageSubtitle"
					:action-label="listMode && canCreate ? 'Add Branch Profile' : ''"
					@action="openNewDocument"
				/>
			</template>

			<template #filters>
				<EdgeFilterBar v-if="listMode" title="Find branch profiles">
					<div class="retailedge-document-filters">
						<label class="retailedge-document-filter">
							<span>Resource</span>
							<select v-model="resource" class="form-control" @change="changeResource">
								<option v-for="option in resourceOptions" :key="option.value" :value="option.value">
									{{ option.label }}
								</option>
							</select>
						</label>
						<label class="retailedge-document-filter retailedge-document-filter--search">
							<span>Search</span>
							<input
								v-model.trim="search"
								type="search"
								class="form-control"
								placeholder="Profile name, company, branch or POS Profile"
								@keyup.enter="applyFilters"
							/>
						</label>
						<template v-for="field in definition.filters || []" :key="field.fieldname">
							<label v-if="field.fieldtype === 'Check'" class="retailedge-document-filter">
								<span>{{ field.label }}</span>
								<select v-model="filters[field.fieldname]" class="form-control">
									<option value="">All</option>
									<option value="1">Yes</option>
									<option value="0">No</option>
								</select>
							</label>
							<EdgeLinkField
								v-else-if="field.fieldtype === 'Link'"
								:model-value="filters[field.fieldname] || ''"
								:label="field.label"
								:placeholder="`Filter by ${field.label}`"
								:searcher="(query) => filterLinkSearch(field, query)"
								@update:model-value="(value) => setFilter(field.fieldname, value)"
							/>
						</template>
					</div>
					<template #actions>
						<button type="button" class="edge-button edge-button--primary" :disabled="loading" @click="applyFilters">
							Apply
						</button>
						<button type="button" class="edge-button" :disabled="loading" @click="resetFilters">
							Reset
						</button>
					</template>
				</EdgeFilterBar>
			</template>

			<div class="retailedge-document-resource-bar">
				<label v-if="!listMode" class="retailedge-document-resource-select">
					<span>Resource</span>
					<select v-model="resource" class="form-control" :disabled="saving" @change="changeResource">
						<option v-for="option in resourceOptions" :key="option.value" :value="option.value">
							{{ option.label }}
						</option>
					</select>
				</label>
				<button type="button" class="edge-button" :disabled="loading || saving" @click="openNativeView">
					Open native Frappe view
				</button>
			</div>

			<EdgeLoadingState v-if="loading" message="Loading RetailEdge setup records…" :skeleton="true" />
			<EdgeErrorState
				v-else-if="error"
				title="RetailEdge setup workspace could not load"
				:message="error"
				action-label="Try again"
				@retry="reloadCurrentView"
			/>

			<template v-else-if="listMode">
				<section class="retailedge-document-summary" aria-label="Branch profile summary">
					<div><span>Total profiles</span><strong>{{ list.total || 0 }}</strong></div>
					<div><span>Current page</span><strong>{{ currentPage }} of {{ totalPages }}</strong></div>
					<div><span>Branch scope</span><strong>{{ identity.branch || 'Permitted branches' }}</strong></div>
				</section>

				<EdgeDataTable
					:columns="definition.columns || []"
					:rows="list.rows || []"
					:actions="rowActions"
					empty-title="No matching branch profiles"
					empty-description="Change the filters or add a Branch Profile if your role permits it."
					@row-click="openRow"
					@action="handleRowAction"
				>
					<template #footer>
						<span>Showing {{ firstVisible }}–{{ lastVisible }} of {{ list.total || 0 }}</span>
						<div class="retailedge-document-pagination">
							<button type="button" class="edge-button edge-button--compact" :disabled="!hasPrevious" @click="previousPage">Previous</button>
							<button type="button" class="edge-button edge-button--compact" :disabled="!hasNext" @click="nextPage">Next</button>
						</div>
					</template>
				</EdgeDataTable>
			</template>

			<template v-else-if="documentReady">
				<EdgeWorkflowBar
					:state="document.state || (document.is_new ? 'New' : 'Saved')"
					:docstatus="document.docstatus || 0"
					:dirty="dirty"
					:saving="saving"
					:can-save="canSave"
					:can-delete="false"
					:transitions="[]"
					:save-label="definition.is_single ? 'Save Settings' : 'Save Branch Profile'"
					@save="saveDocument"
					@back="backToList"
				/>

				<div v-if="definition.is_single" class="retailedge-settings-warning" role="note">
					<EdgeIcon name="shield" size="sm" />
					<span>These are site-wide controls. Account lookups use your active/default company because RetailEdge Settings currently has no company field.</span>
				</div>

				<EdgeSettingsLayout
					v-if="definition.is_single"
					:groups="settingsGroups"
					:active="settingsGroup"
					title="RetailEdge Settings"
					description="Configure operational controls in focused groups while retaining the native Frappe document as storage truth."
					@update:active="settingsGroup = $event"
				>
					<EdgeDocumentForm
						:schema="settingsVisibleSchema"
						:model-value="model"
						:errors="fieldErrors"
						:readonly="!canEdit"
						:link-searcher="linkSearch"
						:child-link-searcher="childLinkSearch"
						@update:model-value="onModelUpdate"
					/>
				</EdgeSettingsLayout>

				<EdgeDocumentForm
					v-else
					:schema="document.schema || { tabs: [] }"
					:model-value="model"
					:errors="fieldErrors"
					:readonly="!canEdit"
					:link-searcher="linkSearch"
					:child-link-searcher="childLinkSearch"
					@update:model-value="onModelUpdate"
				/>
			</template>

			<EdgeEmptyState
				v-else
				title="Setup document unavailable"
				description="Return to Branch Profiles or open the native Frappe view."
				action-label="Back to Branch Profiles"
				@action="backToList"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const API = Object.freeze({
	definition: "retailedge.document_workspace.get_resource_definition",
	list: "retailedge.document_workspace.get_document_list",
	document: "retailedge.document_workspace.get_document",
	save: "retailedge.document_workspace.save_document",
	link: "retailedge.document_workspace.get_link_options",
});

function clone(value) {
	return JSON.parse(JSON.stringify(value ?? {}));
}

function errorMessage(error, fallback) {
	return error?.message || error?._server_messages || error?.exc_type || fallback || "The operation could not be completed.";
}

export default {
	name: "RetailEdgeDocumentWorkspace",
	data() {
		const route = new URLSearchParams(window.location.search || "");
		const requested = route.get("resource") || "branch-profiles";
		const roles = new Set(window.frappe?.boot?.user?.roles || window.frappe?.user_roles || []);
		const resourceOptions = [{ value: "branch-profiles", label: "Branch Profiles" }];
		if (window.frappe?.session?.user === "Administrator" || roles.has("System Manager")) {
			resourceOptions.push({ value: "settings", label: "RetailEdge Settings" });
		}
		return {
			resource: resourceOptions.some((option) => option.value === requested) ? requested : resourceOptions[0].value,
			resourceOptions,
			definition: { title: "RetailEdge Setup", singular: "Record", subtitle: "", columns: [], filters: [], permissions: {}, is_single: false },
			list: { rows: [], total: 0, start: 0, page_length: 25 },
			document: {},
			model: {},
			originalModel: "{}",
			fieldErrors: {},
			search: route.get("search") || "",
			filters: {},
			pageLength: 25,
			loading: true,
			saving: false,
			error: "",
			mode: route.get("name") || route.get("new") === "1" || requested === "settings" ? "form" : "list",
			settingsGroup: "",
		};
	},
	computed: {
		identity() {
			return window.frappe?.boot?.retailedge?.ui || {};
		},
		userName() {
			return this.identity.user?.full_name || window.frappe?.session?.user || "RetailEdge User";
		},
		listMode() {
			return this.mode === "list" && !this.definition.is_single;
		},
		documentReady() {
			return Boolean(this.document?.schema);
		},
		pageTitle() {
			if (this.listMode) return this.definition.title || "Branch Profiles";
			if (this.definition.is_single) return "RetailEdge Settings";
			if (this.document.is_new) return "Add Branch Profile";
			return this.document.title || this.document.name || "Branch Profile";
		},
		pageSubtitle() {
			if (this.listMode || this.definition.is_single) return this.definition.subtitle || "";
			return this.document.name ? `Branch Profile · ${this.document.name}` : this.definition.subtitle || "";
		},
		canCreate() {
			return Boolean(this.definition.permissions?.create);
		},
		canEdit() {
			if (this.document.is_new) return Boolean(this.definition.permissions?.create);
			return Boolean(this.document.permissions?.write && Number(this.document.docstatus || 0) === 0);
		},
		canSave() {
			return this.canEdit;
		},
		dirty() {
			return JSON.stringify(this.model || {}) !== this.originalModel;
		},
		rowActions() {
			return [{ key: "open", label: "Open", primary: true }];
		},
		currentPage() {
			return Math.floor((this.list.start || 0) / (this.list.page_length || this.pageLength)) + 1;
		},
		totalPages() {
			return Math.max(1, Math.ceil((this.list.total || 0) / (this.list.page_length || this.pageLength)));
		},
		firstVisible() {
			return this.list.total ? (this.list.start || 0) + 1 : 0;
		},
		lastVisible() {
			return Math.min((this.list.start || 0) + (this.list.rows || []).length, this.list.total || 0);
		},
		hasPrevious() {
			return (this.list.start || 0) > 0;
		},
		hasNext() {
			return (this.list.start || 0) + (this.list.rows || []).length < (this.list.total || 0);
		},
		settingsGroups() {
			return (this.document.schema?.tabs || []).map((tab) => ({
				key: tab.key,
				label: tab.label,
				description: tab.description || "",
				icon: this.settingsIcon(tab.key),
			}));
		},
		settingsVisibleSchema() {
			const tabs = this.document.schema?.tabs || [];
			const selected = tabs.find((tab) => tab.key === this.settingsGroup) || tabs[0];
			return { tabs: selected ? [selected] : [] };
		},
	},
	mounted() {
		this.loadDefinition();
	},
	methods: {
		async call(method, args = {}) {
			const response = await window.frappe.call(method, args);
			return response?.message;
		},
		confirmDiscard() {
			return !this.dirty || window.confirm("Discard unsaved changes?");
		},
		settingsIcon(key) {
			const value = String(key || "").toLowerCase();
			if (value.includes("bank")) return "wallet";
			if (value.includes("audit")) return "assessment";
			if (value.includes("expense")) return "report";
			if (value.includes("coreedge")) return "grid";
			return "settings";
		},
		async loadDefinition() {
			this.loading = true;
			this.error = "";
			try {
				this.definition = await this.call(API.definition, { resource: this.resource });
				this.filters = {};
				if (this.definition.is_single) {
					this.mode = "form";
					await this.loadDocument();
				} else if (this.mode === "form") {
					const route = new URLSearchParams(window.location.search || "");
					await this.loadDocument(route.get("name") || null, route.get("new") === "1");
				} else {
					await this.loadList(0);
				}
			} catch (error) {
				this.error = errorMessage(error, "RetailEdge setup definition could not load.");
			} finally {
				this.loading = false;
			}
		},
		async loadList(start = 0) {
			this.loading = true;
			this.error = "";
			try {
				this.list = await this.call(API.list, {
					resource: this.resource,
					search: this.search,
					filters: this.filters,
					start,
					page_length: this.pageLength,
				});
				this.mode = "list";
				this.syncRoute();
			} catch (error) {
				this.error = errorMessage(error, "Branch Profiles could not load.");
			} finally {
				this.loading = false;
			}
		},
		async loadDocument(name = null, isNew = false) {
			this.loading = true;
			this.error = "";
			try {
				this.document = await this.call(API.document, {
					resource: this.resource,
					name: isNew ? null : name,
				});
				this.model = clone(this.document.values || {});
				this.originalModel = JSON.stringify(this.model);
				this.fieldErrors = {};
				this.mode = "form";
				this.settingsGroup = this.document.schema?.tabs?.[0]?.key || "";
				this.syncRoute();
			} catch (error) {
				this.error = errorMessage(error, "The setup document could not load.");
			} finally {
				this.loading = false;
			}
		},
		async saveDocument() {
			if (!this.canSave || !this.dirty) return;
			this.saving = true;
			this.error = "";
			this.fieldErrors = {};
			try {
				this.document = await this.call(API.save, {
					resource: this.resource,
					values: this.model,
					name: this.document.is_new ? null : this.document.name,
					modified: this.document.modified || null,
				});
				this.model = clone(this.document.values || {});
				this.originalModel = JSON.stringify(this.model);
				this.mode = "form";
				this.syncRoute();
				window.frappe?.show_alert?.({ message: this.definition.is_single ? "RetailEdge Settings saved." : "Branch Profile saved.", indicator: "green" });
			} catch (error) {
				this.error = errorMessage(error, "The setup document could not be saved.");
			} finally {
				this.saving = false;
			}
		},
		onModelUpdate(values) {
			this.model = clone(values);
		},
		async linkSearch(field, query, values) {
			return (await this.call(API.link, {
				resource: this.resource,
				fieldname: field.fieldname,
				query,
				values,
				page_length: 20,
			})) || [];
		},
		async childLinkSearch(field, query, row) {
			return (await this.call(API.link, {
				resource: this.resource,
				fieldname: field.fieldname,
				query,
				values: this.model,
				child_doctype: field.parent || "RetailEdge Branch Profile User",
				page_length: 20,
				row,
			})) || [];
		},
		filterLinkSearch(field, query) {
			return this.call(API.link, {
				resource: this.resource,
				fieldname: field.fieldname,
				query,
				values: this.filters,
				page_length: 20,
			});
		},
		setFilter(fieldname, value) {
			this.filters[fieldname] = value || "";
			if (fieldname === "company") this.filters.branch = "";
		},
		applyFilters() {
			this.loadList(0);
		},
		resetFilters() {
			this.search = "";
			this.filters = {};
			this.loadList(0);
		},
		openRow(row) {
			if (row?.name) this.loadDocument(row.name, false);
		},
		handleRowAction({ row }) {
			this.openRow(row);
		},
		openNewDocument() {
			this.loadDocument(null, true);
		},
		previousPage() {
			this.loadList(Math.max(0, (this.list.start || 0) - this.pageLength));
		},
		nextPage() {
			this.loadList((this.list.start || 0) + this.pageLength);
		},
		async changeResource() {
			if (!this.confirmDiscard()) return;
			this.search = "";
			this.filters = {};
			this.mode = this.resource === "settings" ? "form" : "list";
			await this.loadDefinition();
		},
		backToList() {
			if (!this.confirmDiscard()) return;
			if (this.definition.is_single) {
				this.resource = "branch-profiles";
				this.mode = "list";
				this.loadDefinition();
				return;
			}
			this.loadList(0);
		},
		reloadCurrentView() {
			if (this.listMode) this.loadList(this.list.start || 0);
			else this.loadDocument(this.document.name || null, Boolean(this.document.is_new));
		},
		openNativeView() {
			if (this.definition.is_single) {
				window.frappe?.set_route?.("Form", this.definition.doctype, this.definition.doctype);
			} else if (this.document?.name && !this.listMode) {
				window.frappe?.set_route?.("Form", this.definition.doctype, this.document.name);
			} else {
				window.frappe?.set_route?.("List", this.definition.doctype);
			}
		},
		openRoute(route) {
			if (window.RetailEdgeUIBridge?.openRoute?.(route)) return;
			if (route) window.location.assign(route);
		},
		syncRoute() {
			const params = new URLSearchParams();
			params.set("resource", this.resource);
			if (!this.listMode) {
				if (this.document?.is_new) params.set("new", "1");
				else if (this.document?.name && !this.definition.is_single) params.set("name", this.document.name);
			}
			const next = `/app/retailedge-document-workspace?${params.toString()}`;
			window.history.replaceState({}, "", next);
		},
	},
};
</script>

<style scoped>
.retailedge-document-resource-bar {
	align-items: end;
	display: flex;
	flex-wrap: wrap;
	gap: 0.75rem;
	justify-content: flex-end;
	margin-bottom: 1rem;
}

.retailedge-document-resource-select {
	display: grid;
	gap: 0.25rem;
	min-width: 14rem;
}

.retailedge-document-resource-select span,
.retailedge-document-filter > span {
	color: var(--text-muted, #6b7d90);
	font-size: 0.72rem;
	font-weight: 700;
}

.retailedge-document-filters {
	display: grid;
	gap: 0.75rem;
	grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
	width: 100%;
}

.retailedge-document-filter {
	display: grid;
	gap: 0.3rem;
	min-width: 0;
}

.retailedge-document-filter--search {
	grid-column: span 2;
}

.retailedge-document-summary {
	display: grid;
	gap: 0.75rem;
	grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
	margin-bottom: 1rem;
}

.retailedge-document-summary > div {
	background: var(--card-bg, #fff);
	border: 1px solid var(--border-color, #dce5ef);
	border-radius: var(--edge-radius-md, 0.75rem);
	display: grid;
	gap: 0.2rem;
	padding: 0.8rem;
}

.retailedge-document-summary span {
	color: var(--text-muted, #6b7d90);
	font-size: 0.7rem;
}

.retailedge-document-summary strong {
	font-size: 1rem;
}

.retailedge-document-pagination {
	display: flex;
	gap: 0.5rem;
}

.retailedge-settings-warning {
	align-items: flex-start;
	background: var(--yellow-50, #fffaeb);
	border: 1px solid var(--yellow-200, #fedf89);
	border-radius: var(--edge-radius-md, 0.75rem);
	display: flex;
	gap: 0.5rem;
	margin-bottom: 1rem;
	padding: 0.75rem;
}

@media (max-width: 47.99rem) {
	.retailedge-document-filter--search {
		grid-column: auto;
	}
	.retailedge-document-resource-bar,
	.retailedge-document-pagination {
		align-items: stretch;
		flex-direction: column;
	}
	.retailedge-document-resource-select {
		width: 100%;
	}
}
</style>
