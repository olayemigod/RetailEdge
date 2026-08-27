<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Operating Context could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>
	<EdgeAppShell
		v-else
		product="RetailEdge"
		title="Operating Context"
		:tenantName="current.company || tenantName"
		:branchName="current.branch || selectedBranch"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/operating-context"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-operating-context-page">
			<EdgePageHeader
				title="Operating Context"
				description="Choose the Company and Branch that should guide new RetailEdge work. Existing documents keep their saved accounting, branch and stock values."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error" :message="error" @retry="loadContext()" />

			<div v-else class="operating-context-layout">
				<section class="edge-panel operating-context-current">
					<div>
						<span class="operating-context-kicker">Current operating context</span>
						<h3>{{ currentLabel }}</h3>
						<p>New drafts and report defaults start from this context unless a valid explicit document value is already present.</p>
					</div>
					<EdgeStatusBadge :status="current.branch ? 'Active' : 'Warning'" />
				</section>

				<section class="edge-panel operating-context-form">
					<div class="operating-context-fields">
						<label class="edge-field">
							<span class="edge-field-label">Operating Company</span>
							<select v-model="selectedCompany" class="edge-input" :disabled="busy" @change="onCompanyChange">
								<option value="">Choose Company</option>
								<option v-for="company in companies" :key="company" :value="company">{{ company }}</option>
							</select>
						</label>
						<label class="edge-field">
							<span class="edge-field-label">Operating Branch</span>
							<select
								v-model="selectedBranch"
								class="edge-input"
								:disabled="busy || !selectedCompany"
								@change="onBranchChange"
							>
								<option value="">Choose Branch</option>
								<option v-for="branch in branches" :key="branch" :value="branch">{{ branch }}</option>
							</select>
						</label>
					</div>

					<div v-if="posRequired && selectedBranch" class="operating-context-pos">
						<div>
							<span class="operating-context-kicker">Required POS access</span>
							<strong>{{ posProfile || "POS Profile not ready" }}</strong>
							<small>{{ posMessage || "Your Branch Setup POS Profile is valid for this operating Branch." }}</small>
						</div>
						<EdgeStatusBadge :status="posReady ? 'Active' : 'Warning'" />
					</div>

					<div v-if="switchBlockers.length" class="operating-context-blockers">
						<div v-for="blocker in switchBlockers" :key="`${blocker.code}-${blocker.reference || ''}`" class="operating-context-warning">
							<strong>Finish current POS work before switching</strong>
							<span>{{ blocker.message || "Active POS work may prevent switching Branch." }}</span>
						</div>
					</div>

					<div class="operating-context-actions">
						<button
							type="button"
							class="edge-button edge-button--primary"
							:disabled="busy || !selectedCompany || !selectedBranch || (posRequired && !posReady)"
							@click="switchContext"
						>
							{{ busy ? "Updating…" : "Use Selected Branch" }}
						</button>
						<button type="button" class="edge-button edge-button--secondary" :disabled="busy" @click="restoreDefault">
							Restore Default
						</button>
					</div>
				</section>

				<section class="edge-panel operating-context-guidance">
					<h4>What changes when you switch?</h4>
					<ul>
						<li>New guided and full-form transactions may receive Branch Setup defaults for the selected Branch.</li>
						<li>Operational reports may start with the selected Company and Branch as editable defaults.</li>
						<li>Existing drafts and submitted documents keep their stored Company, Branch, Stock Location and accounting values.</li>
						<li>Users assigned to ERPNext POS Profiles must have a valid Branch Setup POS Profile for the selected Branch.</li>
						<li>An active POS shift or unsaved POS/cart/payment state can block switching until that work is completed.</li>
					</ul>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeStatusBadge"];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}, options = {}) {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			freeze: Boolean(options.freeze),
			freeze_message: options.freezeMessage || undefined,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

export default {
	name: "RetailEdgeOperatingContext",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			busy: false,
			error: "",
			companies: [],
			branches: [],
			current: {},
			selectedCompany: "",
			selectedBranch: "",
			posRequired: false,
			posProfile: "",
			posReady: true,
			posMessage: "",
			switchBlockers: [],
			menuItems: [],
			tenantName: "",
			userName: "",
		};
	},
	computed: {
		currentLabel() {
			if (!this.current?.company) return "No operating context selected";
			return `${this.current.company}${this.current.branch ? ` · ${this.current.branch}` : ""}`;
		},
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadContext();
	},
	mounted() {
		window.addEventListener("retailedge-operating-context-page-show", this._onPageShow);
		if (this.edgeUIValid) {
			this.loadNavigation();
			this.loadContext();
		}
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-operating-context-page-show", this._onPageShow);
	},
	methods: {
		async loadNavigation() {
			try {
				const navigation = typeof window.retailedgeGetBusinessHubContext === "function"
					? await window.retailedgeGetBusinessHubContext()
					: await callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.tenantName = navigation.context?.company || "";
				this.userName = navigation.context?.user_name || "";
			} catch (error) {
				this.menuItems = [];
			}
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
			else if (item.target_type === "Report" || item.target_type === "DocType") window.open(route, "_blank", "noopener,noreferrer");
			else if (item.target_type === "URL" && item.target) window.open(item.target, "_blank", "noopener,noreferrer");
		},
		clientSwitchBlocker() {
			try {
				const guard = window.retailedgeOperatingContextGuard;
				if (guard && typeof guard.getBlocker === "function") return guard.getBlocker() || "";
			} catch (error) {
				return "The current transaction state could not be verified. Finish current work before switching Branch.";
			}
			return "";
		},
		showClientBlocker() {
			const message = this.clientSwitchBlocker();
			if (!message) return false;
			frappe.msgprint({ title: __("Finish current work before switching"), message, indicator: "orange" });
			return true;
		},
		invalidateContextCache() {
			window.__retailedgeBusinessHubContextCache = null;
			window.__retailedgeBusinessHubContextRequest = null;
			window.retailedgeInstallProductMenu?.({ force: true });
			document.dispatchEvent(new CustomEvent("retailedge-operating-context-changed"));
		},
		resetPosState(required = false) {
			this.posRequired = Boolean(required);
			this.posProfile = "";
			this.posReady = !this.posRequired;
			this.posMessage = "";
		},
		applyPosState(context = {}) {
			this.posRequired = Boolean(context.pos_required);
			this.posProfile = context.pos_profile || "";
			this.posReady = context.pos_ready !== false;
			this.posMessage = context.pos_message || "";
		},
		async loadContext(company = "") {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const data = await callMethod("retailedge.operating_context.get_allowed_operating_contexts", { company: company || "" });
				this.companies = Array.isArray(data.companies) ? data.companies : [];
				this.branches = Array.isArray(data.branches) ? data.branches : [];
				this.current = data.current || {};
				this.switchBlockers = Array.isArray(data.switch_blockers) ? data.switch_blockers : [];
				this.selectedCompany = company || data.current?.company || data.selected_company || "";
				const currentBranch = data.current?.company === this.selectedCompany ? data.current?.branch || "" : "";
				this.selectedBranch = this.branches.includes(currentBranch) ? currentBranch : "";
				if (this.selectedBranch) this.applyPosState(data.current || {});
				else this.resetPosState(Boolean(data.pos_required));
				this.loaded = true;
			} catch (error) {
				this.error = error?.message || error?.exc || __("The permitted Company and Branch options could not be loaded.");
			} finally {
				this.loading = false;
			}
		},
		async onCompanyChange() {
			this.selectedBranch = "";
			this.resetPosState(this.posRequired);
			await this.loadContext(this.selectedCompany);
		},
		async onBranchChange() {
			this.resetPosState(this.posRequired);
			if (!this.selectedCompany || !this.selectedBranch) return;
			try {
				const preview = await callMethod("retailedge.operating_context.preview_operating_context", {
					company: this.selectedCompany,
					branch: this.selectedBranch,
				});
				this.applyPosState(preview);
			} catch (error) {
				this.posReady = false;
				this.posMessage = error?.message || error?.exc || __("The selected Branch context could not be validated.");
			}
		},
		async switchContext() {
			if (!this.selectedCompany || !this.selectedBranch || (this.posRequired && !this.posReady) || this.showClientBlocker()) return;
			this.busy = true;
			try {
				await callMethod(
					"retailedge.operating_context.switch_operating_context",
					{ company: this.selectedCompany, branch: this.selectedBranch },
					{ freeze: true, freezeMessage: __("Updating operating branch...") },
				);
				this.invalidateContextCache();
				frappe.show_alert({ message: __("Operating branch updated."), indicator: "green" });
				await Promise.all([this.loadContext(), this.loadNavigation()]);
			} finally {
				this.busy = false;
			}
		},
		async restoreDefault() {
			if (this.showClientBlocker()) return;
			this.busy = true;
			try {
				await callMethod(
					"retailedge.operating_context.clear_operating_context",
					{},
					{ freeze: true, freezeMessage: __("Restoring default operating branch...") },
				);
				this.invalidateContextCache();
				frappe.show_alert({ message: __("Default operating branch restored."), indicator: "green" });
				await Promise.all([this.loadContext(), this.loadNavigation()]);
			} finally {
				this.busy = false;
			}
		},
	},
};
</script>

<style scoped>
.operating-context-layout { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.operating-context-current { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.operating-context-current h3 { margin: 0.2rem 0 0.35rem; }
.operating-context-current p { margin: 0; color: var(--text-muted); max-width: 52rem; }
.operating-context-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.operating-context-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.operating-context-pos { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-top: 1rem; padding: 0.85rem 1rem; border-radius: 0.6rem; border: 1px solid var(--edge-border-color, var(--border-color)); }
.operating-context-pos > div { display: grid; gap: 0.2rem; }
.operating-context-pos small { color: var(--text-muted); }
.operating-context-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1rem; }
.operating-context-blockers { display: grid; gap: 0.65rem; margin-top: 1rem; }
.operating-context-warning { display: grid; gap: 0.2rem; padding: 0.85rem 1rem; border-radius: 0.6rem; background: var(--orange-50, rgba(245, 158, 11, 0.1)); }
.operating-context-guidance h4 { margin-top: 0; }
.operating-context-guidance ul { margin-bottom: 0; padding-left: 1.15rem; }
.operating-context-guidance li + li { margin-top: 0.4rem; }
@media (max-width: 720px) { .operating-context-fields { grid-template-columns: 1fr; } .operating-context-current { flex-direction: column; } }
</style>
