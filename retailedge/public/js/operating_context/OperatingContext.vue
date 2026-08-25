<template>
	<EdgePageLayout class="retailedge-operating-context-page">
		<EdgePageHeader
			title="Operating Context"
			description="Choose the Company and Branch that should guide new RetailEdge work. Existing documents keep their saved accounting, branch and stock values."
		/>

		<EdgeLoadingState v-if="loading && !loaded" message="Loading operating context…" />
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
						<select v-model="selectedBranch" class="edge-input" :disabled="busy || !selectedCompany">
							<option value="">Choose Branch</option>
							<option v-for="branch in branches" :key="branch" :value="branch">{{ branch }}</option>
						</select>
					</label>
				</div>

				<div v-if="switchBlockers.length" class="operating-context-blockers">
					<div v-for="blocker in switchBlockers" :key="`${blocker.code}-${blocker.reference || ''}`" class="operating-context-warning">
						<strong>Finish current POS work before switching</strong>
						<span>{{ blocker.message || 'Active POS work may prevent switching Branch.' }}</span>
					</div>
				</div>

				<div class="operating-context-actions">
					<button type="button" class="edge-button edge-button--primary" :disabled="busy || !selectedCompany || !selectedBranch" @click="switchContext">
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
					<li>An active POS shift or unsaved POS/cart/payment state can block switching until that work is completed.</li>
				</ul>
			</section>
		</div>
	</EdgePageLayout>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const edgeUI = window.EdgeSuiteUI || window.EdgeUI;
const EdgePageLayout = edgeUI?.getComponent?.("EdgePageLayout");
const EdgePageHeader = edgeUI?.getComponent?.("EdgePageHeader");
const EdgeLoadingState = edgeUI?.getComponent?.("EdgeLoadingState");
const EdgeErrorState = edgeUI?.getComponent?.("EdgeErrorState");
const EdgeStatusBadge = edgeUI?.getComponent?.("EdgeStatusBadge");

const loading = ref(false);
const loaded = ref(false);
const busy = ref(false);
const error = ref("");
const companies = ref([]);
const branches = ref([]);
const current = ref({});
const selectedCompany = ref("");
const selectedBranch = ref("");
const switchBlockers = ref([]);

const currentLabel = computed(() => {
	if (!current.value?.company) return "No operating context selected";
	return `${current.value.company}${current.value.branch ? ` · ${current.value.branch}` : ""}`;
});

function clientSwitchBlocker() {
	try {
		const guard = window.retailedgeOperatingContextGuard;
		if (guard && typeof guard.getBlocker === "function") return guard.getBlocker() || "";
	} catch (e) {
		return "The current transaction state could not be verified. Finish current work before switching Branch.";
	}
	return "";
}

function showClientBlocker() {
	const message = clientSwitchBlocker();
	if (!message) return false;
	frappe.msgprint({ title: __("Finish current work before switching"), message, indicator: "orange" });
	return true;
}

function invalidateContextCache() {
	window.__retailedgeBusinessHubContextCache = null;
	window.__retailedgeBusinessHubContextRequest = null;
	window.retailedgeInstallProductMenu?.({ force: true });
	document.dispatchEvent(new CustomEvent("retailedge-operating-context-changed"));
}

async function loadContext(company = "") {
	if (loading.value) return;
	loading.value = true;
	error.value = "";
	try {
		const response = await frappe.call({
			method: "retailedge.operating_context.get_allowed_operating_contexts",
			args: { company: company || "" },
		});
		const data = response?.message || {};
		companies.value = Array.isArray(data.companies) ? data.companies : [];
		branches.value = Array.isArray(data.branches) ? data.branches : [];
		current.value = data.current || {};
		switchBlockers.value = Array.isArray(data.switch_blockers) ? data.switch_blockers : [];
		selectedCompany.value = company || data.current?.company || data.selected_company || "";
		const currentBranch = data.current?.company === selectedCompany.value ? data.current?.branch || "" : "";
		selectedBranch.value = branches.value.includes(currentBranch) ? currentBranch : "";
		loaded.value = true;
	} catch (e) {
		error.value = e?.message || __("The permitted Company and Branch options could not be loaded.");
	} finally {
		loading.value = false;
	}
}

async function onCompanyChange() {
	selectedBranch.value = "";
	await loadContext(selectedCompany.value);
}

async function switchContext() {
	if (!selectedCompany.value || !selectedBranch.value || showClientBlocker()) return;
	busy.value = true;
	try {
		await frappe.call({
			method: "retailedge.operating_context.switch_operating_context",
			args: { company: selectedCompany.value, branch: selectedBranch.value },
			freeze: true,
			freeze_message: __("Updating operating branch..."),
		});
		invalidateContextCache();
		frappe.show_alert({ message: __("Operating branch updated."), indicator: "green" });
		await loadContext();
	} finally {
		busy.value = false;
	}
}

async function restoreDefault() {
	if (showClientBlocker()) return;
	busy.value = true;
	try {
		await frappe.call({
			method: "retailedge.operating_context.clear_operating_context",
			freeze: true,
			freeze_message: __("Restoring default operating branch..."),
		});
		invalidateContextCache();
		frappe.show_alert({ message: __("Default operating branch restored."), indicator: "green" });
		await loadContext();
	} finally {
		busy.value = false;
	}
}

function onPageShow() {
	loadContext();
}

onMounted(() => {
	window.addEventListener("retailedge-operating-context-page-show", onPageShow);
	loadContext();
});

onBeforeUnmount(() => {
	window.removeEventListener("retailedge-operating-context-page-show", onPageShow);
});
</script>

<style scoped>
.operating-context-layout { display: grid; gap: 1rem; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.operating-context-current { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.operating-context-current h3 { margin: 0.2rem 0 0.35rem; }
.operating-context-current p { margin: 0; color: var(--text-muted); max-width: 52rem; }
.operating-context-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.operating-context-fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 1rem; }
.operating-context-actions { display: flex; flex-wrap: wrap; gap: 0.75rem; margin-top: 1rem; }
.operating-context-blockers { display: grid; gap: 0.65rem; margin-top: 1rem; }
.operating-context-warning { display: grid; gap: 0.2rem; padding: 0.85rem 1rem; border-radius: 0.6rem; background: var(--orange-50, rgba(245, 158, 11, 0.1)); }
.operating-context-guidance h4 { margin-top: 0; }
.operating-context-guidance ul { margin-bottom: 0; padding-left: 1.15rem; }
.operating-context-guidance li + li { margin-top: 0.4rem; }
@media (max-width: 720px) { .operating-context-fields { grid-template-columns: 1fr; } .operating-context-current { flex-direction: column; } }
</style>
