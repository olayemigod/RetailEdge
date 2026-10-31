<template>
	<section class="onboarding-manager" aria-labelledby="retailedge-user-onboarding-title">
		<div class="onboarding-header">
			<div>
				<button type="button" class="edge-button edge-button--secondary edge-button--small" @click="$emit('back')">Back to Setup</button>
				<span class="onboarding-kicker">User access setup</span>
				<h2 id="retailedge-user-onboarding-title">User Onboarding</h2>
				<p>Set up a staff member's RetailEdge access, work location, and point-of-sale access.</p>
			</div>
			<EdgeStatusBadge v-if="result" :status="result.readiness?.ready ? 'Active' : 'Warning'" />
		</div>

		<EdgeLoadingState v-if="loading && !loaded" message="Preparing user onboarding..." />
		<div v-else-if="loadError" class="onboarding-error" role="alert">
			<strong>User onboarding could not start.</strong>
			<p>{{ loadError }}</p>
			<button type="button" class="edge-button edge-button--secondary" @click="loadContext">Try Again</button>
		</div>

		<div v-else class="onboarding-layout">
			<ol class="onboarding-steps" aria-label="Onboarding progress">
				<li v-for="item in steps" :key="item.number">
					<button
						type="button"
						class="onboarding-step"
						:class="{ 'is-current': step === item.number, 'is-complete': step > item.number }"
						:disabled="item.number > maxStep || saving"
						:aria-current="step === item.number ? 'step' : undefined"
						@click="goToStep(item.number)"
					>
						<span>{{ item.number }}</span>
						<strong>{{ item.label }}</strong>
					</button>
				</li>
			</ol>

			<div v-if="result" class="edge-panel onboarding-result" role="status" aria-live="polite">
				<div class="result-heading">
					<div>
						<span class="onboarding-kicker">Onboarding result</span>
						<h3>{{ result.readiness?.ready ? 'Ready to work' : 'Setup needs attention' }}</h3>
					</div>
					<EdgeStatusBadge :status="result.readiness?.ready ? 'Active' : 'Warning'" />
				</div>
				<p v-if="result.readiness?.message">{{ result.readiness.message }}</p>
				<p v-else>{{ result.user_name || result.user }} now has the selected RetailEdge access and Branch assignment.</p>
				<ul v-if="result.readiness?.reasons?.length" class="result-reasons">
					<li v-for="reason in result.readiness.reasons" :key="`${reason.code}-${reason.message}`">{{ reason.message }}</li>
				</ul>
				<p v-if="result.pos?.access === 'shared'" class="result-note">The Branch POS Profile remains shared. No user restriction was added.</p>
				<p v-if="result.welcome_email_error" class="result-note">{{ result.welcome_email_error }}</p>
				<div class="onboarding-actions">
					<button type="button" class="edge-button edge-button--primary" @click="resetWizard">Onboard Another User</button>
					<button type="button" class="edge-button edge-button--secondary" @click="openBranchAssignments">Branch Assignments</button>
				</div>
			</div>

			<div v-else class="edge-panel onboarding-stage">
				<div class="stage-heading">
					<span class="onboarding-kicker">Step {{ step }} of {{ steps.length }}</span>
					<h3>{{ currentStep.label }}</h3>
					<p>{{ currentStep.description }}</p>
				</div>

				<div v-if="step === 1" class="onboarding-form">
					<div class="choice-grid" role="group" aria-label="User type">
						<button type="button" class="choice-card" :class="{ 'is-selected': form.mode === 'existing' }" @click="setMode('existing')">
							<strong>Existing User</strong>
							<span>Set up RetailEdge for a staff member who already has an account.</span>
						</button>
						<button type="button" class="choice-card" :class="{ 'is-selected': form.mode === 'new' }" :disabled="!permissions.can_create_user" @click="setMode('new')">
							<strong>New User</strong>
							<span>Create a staff account, then complete their RetailEdge access.</span>
						</button>
					</div>

					<EdgeLinkField
						v-if="form.mode === 'existing'"
						:modelValue="form.user"
						label="User"
						placeholder="Search active staff accounts"
						:required="true"
						:searcher="searchUser"
						@update:modelValue="setExistingUser"
					/>
					<div v-else class="field-grid">
						<EdgeInput v-model="form.email" type="email" label="Email" placeholder="user@example.com" required autocomplete="email" />
						<EdgeInput v-model="form.first_name" label="First Name" required autocomplete="given-name" />
						<EdgeInput v-model="form.last_name" label="Last Name" autocomplete="family-name" />
						<EdgeCheckbox v-model="form.send_welcome_email" label="Send welcome email when ready" description="The invitation is sent only after the RetailEdge setup is complete." />
					</div>
					<div v-if="selectedUser.name" class="selection-summary">
						<strong>{{ selectedUser.full_name }}</strong>
						<span>{{ selectedUser.email }}</span>
						<span v-if="selectedUser.retailedge_roles?.length">Current RetailEdge access: {{ selectedUser.retailedge_roles.join(', ') }}</span>
						<span v-if="selectedUser.has_role_profiles">This account's access is managed by a Role Profile. Update that profile before changing RetailEdge access.</span>
					</div>
				</div>

				<div v-else-if="step === 2" class="onboarding-form">
					<EdgeDropdown
						:modelValue="form.role"
						:options="personas"
						label="RetailEdge Access"
						placeholder="Choose what this User will do"
						required
						@update:modelValue="setRole"
					/>
					<EdgeDropdown v-model="form.branch_role" :options="branchRoles" label="Branch Responsibility" placeholder="Choose responsibility" required />
					<div class="guidance-card">
						<strong>Business permissions are managed separately.</strong>
						<p>This wizard sets RetailEdge access and work location. It does not change Sales, Accounts, Stock or Purchasing permissions.</p>
					</div>
				</div>

				<div v-else-if="step === 3" class="onboarding-form">
					<div class="field-grid">
						<EdgeLinkField
							:modelValue="form.company"
							label="Company"
							placeholder="Choose Company"
							:required="true"
							:searcher="searchCompany"
							@update:modelValue="setCompany"
						/>
						<EdgeLinkField
							:modelValue="form.branch"
							label="Branch"
							placeholder="Choose configured Branch"
							:required="true"
							:disabled="!form.company"
							:searcher="searchBranch"
							@update:modelValue="setBranch"
						/>
						<EdgeInput v-model="form.effective_from" type="date" label="Access Starts" required />
						<EdgeCheckbox v-model="form.is_primary" label="Primary Branch" description="Use this Branch as the User's starting Branch for this Company." />
					</div>
					<div v-if="branchContextLoading" class="selection-summary">Checking Branch Setup...</div>
					<div v-else-if="form.branch && branchContext.configured" class="selection-summary">
						<strong>{{ form.branch }} is configured for {{ form.company }}.</strong>
						<span v-if="branchContext.default_pos_profile">Branch POS Profile: {{ branchContext.default_pos_profile }}</span>
						<span v-else>No default POS Profile is configured. That is allowed unless this User needs POS access.</span>
					</div>
					<div v-else-if="form.branch && branchContext.message" class="onboarding-error" role="alert">{{ branchContext.message }}</div>
				</div>

				<div v-else-if="step === 4" class="onboarding-form">
					<EdgeCheckbox
						v-model="form.requires_pos"
						label="This User will work at Point of Sale"
						description="Turn this on only when the User needs the Branch's POS Profile."
					/>
					<div v-if="!form.requires_pos" class="guidance-card">
						<strong>POS is not required.</strong>
						<p>No POS assignment will be created or changed for this User.</p>
					</div>
					<div v-else-if="branchContextLoading" class="selection-summary">Checking POS setup...</div>
					<div v-else-if="!branchContext.default_pos_profile" class="onboarding-error" role="alert">
						<strong>POS setup is incomplete.</strong>
						<p>Configure a default POS Profile in Branch Setup for {{ form.branch }} before completing POS onboarding.</p>
						<button type="button" class="edge-button edge-button--secondary" @click="openBranchSetup">Open Branch Setup</button>
					</div>
					<div v-else-if="!branchContext.pos_required_supported" class="onboarding-error" role="alert">
						<strong>POS Profile is not usable.</strong>
						<p>The Branch POS Profile is disabled or belongs to another Company.</p>
						<button type="button" class="edge-button edge-button--secondary" @click="openBranchSetup">Open Branch Setup</button>
					</div>
					<div v-else class="pos-summary">
						<div><span>POS Profile</span><strong>{{ branchContext.default_pos_profile }}</strong></div>
						<div><span>Access model</span><strong>{{ posAccessLabel }}</strong></div>
						<div v-if="branchContext.pos_access_mode === 'shared'" class="guidance-card edge-field--wide">
							<strong>Existing shared access will be preserved.</strong>
							<p>This POS Profile currently has no user restrictions. The wizard will not add the first restriction and accidentally remove access for other users.</p>
						</div>
						<div v-else-if="branchContext.pos_assigned" class="guidance-card edge-field--wide">
							<strong>This User is already assigned to the Branch POS Profile.</strong>
							<p>The existing POS Profile assignment will be kept.</p>
						</div>
					</div>
				</div>

				<div v-else class="onboarding-form">
					<div class="review-grid">
						<div><span>User</span><strong>{{ personLabel }}</strong></div>
						<div><span>RetailEdge Access</span><strong>{{ selectedPersona?.label || form.role }}</strong></div>
						<div><span>Company</span><strong>{{ form.company }}</strong></div>
						<div><span>Branch</span><strong>{{ form.branch }}</strong></div>
						<div><span>Branch Responsibility</span><strong>{{ form.branch_role }}</strong></div>
						<div><span>Point of Sale</span><strong>{{ form.requires_pos ? (branchContext.default_pos_profile || 'Required') : 'Not required' }}</strong></div>
					</div>
					<div class="guidance-card">
						<strong>Readiness is checked after setup.</strong>
						<p>RetailEdge will verify the User, role, Company, Branch, business permissions and any applicable POS setup before reporting the final status.</p>
					</div>
				</div>

				<div v-if="stageError" class="onboarding-error" role="alert">{{ stageError }}</div>

				<div class="onboarding-actions">
					<button v-if="step > 1" type="button" class="edge-button edge-button--secondary" :disabled="saving" @click="previousStep">Back</button>
					<span v-else></span>
					<button v-if="step < steps.length" type="button" class="edge-button edge-button--primary" :disabled="saving" @click="nextStep">Continue</button>
					<button v-else type="button" class="edge-button edge-button--primary" :disabled="saving" @click="completeOnboarding">{{ saving ? 'Completing...' : 'Complete Onboarding' }}</button>
				</div>
			</div>
		</div>
	</section>
</template>

<script>
const CONTEXT_METHOD = "retailedge.user_onboarding.get_user_onboarding_context";
const BRANCH_CONTEXT_METHOD = "retailedge.user_onboarding.get_user_onboarding_branch_context";
const SEARCH_METHOD = "retailedge.user_onboarding.search_user_onboarding_options";
const COMPLETE_METHOD = "retailedge.user_onboarding.complete_user_onboarding";

const REQUIRED_COMPONENTS = [
	"EdgeLinkField",
	"EdgeDropdown",
	"EdgeInput",
	"EdgeCheckbox",
	"EdgeStatusBadge",
	"EdgeLoadingState",
];

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => {
		frappe.call({
			method,
			args,
			type,
			callback: (response) => resolve(response.message || {}),
			error: (error) => reject(error),
		});
	});
}

function blankForm(mode = "existing") {
	return {
		mode: mode === "new" ? "new" : "existing",
		user: "",
		email: "",
		first_name: "",
		last_name: "",
		send_welcome_email: true,
		role: "",
		branch_role: "Other",
		company: "",
		branch: "",
		effective_from: frappe.datetime.get_today(),
		is_primary: true,
		requires_pos: false,
	};
}

export default {
	name: "RetailEdgeUserOnboardingManager",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	props: {
		initialMode: { type: String, default: "existing" },
	},
	emits: ["back"],
	data() {
		return {
			loading: false,
			loaded: false,
			loadError: "",
			stageError: "",
			saving: false,
			step: 1,
			maxStep: 1,
			personas: [],
			branchRoles: [],
			permissions: { can_create_user: false, can_create_assignment: false },
			selectedUser: {},
			branchContext: {},
			branchContextLoading: false,
			result: null,
			form: blankForm(this.initialMode),
			steps: [
				{ number: 1, label: "Person", description: "Choose an existing staff account or create a new one." },
				{ number: 2, label: "Access", description: "Choose the RetailEdge access and Branch responsibility for this User." },
				{ number: 3, label: "Location", description: "Assign the User to an enabled Company and Branch." },
				{ number: 4, label: "Point of Sale", description: "Confirm whether this User needs the Branch's POS Profile." },
				{ number: 5, label: "Review", description: "Review the setup before RetailEdge applies the changes." },
			],
		};
	},
	computed: {
		currentStep() { return this.steps.find((item) => item.number === this.step) || this.steps[0]; },
		selectedPersona() { return this.personas.find((item) => item.value === this.form.role) || null; },
		personLabel() {
			if (this.form.mode === "existing") return this.selectedUser.full_name || this.form.user || "—";
			return [this.form.first_name, this.form.last_name].filter(Boolean).join(" ") || this.form.email || "—";
		},
		posAccessLabel() {
			if (this.branchContext.pos_access_mode === "shared") return "Shared profile";
			if (this.branchContext.pos_assigned) return "Already assigned";
			return "User restricted";
		},
	},
	mounted() { this.loadContext(); },
	methods: {
		userError(error, fallback) {
			return window.retailedge?.userErrorMessage?.(error, fallback) || error?.message || fallback;
		},
		async loadContext(user = "") {
			this.loading = true;
			this.loadError = "";
			try {
				const context = await callMethod(CONTEXT_METHOD, { user });
				this.personas = Array.isArray(context.personas) ? context.personas : [];
				this.branchRoles = Array.isArray(context.branch_roles) ? context.branch_roles : [];
				this.permissions = context.permissions || this.permissions;
				if (user) this.selectedUser = context.selected_user || {};
				if (!this.form.effective_from) this.form.effective_from = context.today || frappe.datetime.get_today();
				this.loaded = true;
			} catch (error) {
				this.loadError = this.userError(error, "User onboarding could not load.");
			} finally {
				this.loading = false;
			}
		},
		setMode(mode) {
			if (mode === "new" && !this.permissions.can_create_user) return;
			const keepDate = this.form.effective_from || frappe.datetime.get_today();
			this.form = { ...blankForm(mode), effective_from: keepDate };
			this.selectedUser = {};
			this.branchContext = {};
			this.result = null;
			this.step = 1;
			this.maxStep = 1;
			this.stageError = "";
		},
		search(fieldname, query, values = {}) {
			return callMethod(SEARCH_METHOD, { fieldname, txt: query || "", values }).then((rows) => Array.isArray(rows) ? rows : []);
		},
		searchUser(query) { return this.search("user", query); },
		searchCompany(query) { return this.search("company", query); },
		searchBranch(query) { return this.search("branch", query, { company: this.form.company }); },
		async setExistingUser(value) {
			this.form.user = value || "";
			this.selectedUser = {};
			this.stageError = "";
			if (!this.form.user) return;
			try {
				await this.loadContext(this.form.user);
				const existingRoles = this.selectedUser.retailedge_roles || [];
				if (existingRoles.length === 1) this.setRole(existingRoles[0]);
			} catch (error) {
				this.stageError = this.userError(error, "Unable to review this User.");
			}
		},
		setRole(role) {
			this.form.role = role || "";
			const persona = this.personas.find((item) => item.value === this.form.role);
			if (persona) {
				this.form.branch_role = persona.branch_role || "Other";
				this.form.requires_pos = Boolean(persona.pos_default);
			}
		},
		setCompany(value) {
			const next = value || "";
			if (next === this.form.company) return;
			this.form.company = next;
			this.form.branch = "";
			this.branchContext = {};
		},
		async setBranch(value) {
			this.form.branch = value || "";
			this.branchContext = {};
			this.stageError = "";
			if (!this.form.company || !this.form.branch) return;
			await this.refreshBranchContext();
		},
		async refreshBranchContext() {
			if (!this.form.company || !this.form.branch) return;
			this.branchContextLoading = true;
			try {
				this.branchContext = await callMethod(BRANCH_CONTEXT_METHOD, {
					company: this.form.company,
					branch: this.form.branch,
					user: this.form.mode === "existing" ? this.form.user : "",
				});
			} catch (error) {
				this.branchContext = {};
				this.stageError = this.userError(error, "Unable to review this Branch setup.");
			} finally {
				this.branchContextLoading = false;
			}
		},
		validateStep(step) {
			this.stageError = "";
			if (step === 1) {
				if (this.form.mode === "existing" && !this.form.user) return "Choose an existing User.";
				if (this.form.mode === "new" && (!this.form.email || !this.form.first_name)) return "Enter the new User's email and first name.";
			}
			if (step === 2 && (!this.form.role || !this.form.branch_role)) return "Choose the User's RetailEdge access and Branch responsibility.";
			if (step === 3) {
				if (!this.form.company || !this.form.branch || !this.form.effective_from) return "Choose the Company, Branch and access start date.";
				if (!this.branchContext.configured) return this.branchContext.message || "Complete Branch Setup before continuing.";
			}
			if (step === 4 && this.form.requires_pos) {
				if (!this.branchContext.default_pos_profile) return "Configure a default POS Profile in Branch Setup before continuing.";
				if (!this.branchContext.pos_required_supported) return "The Branch POS Profile must be enabled and belong to the selected Company.";
			}
			return "";
		},
		async nextStep() {
			if (this.step === 3 || this.step === 4) await this.refreshBranchContext();
			const error = this.validateStep(this.step);
			if (error) { this.stageError = error; return; }
			this.step = Math.min(this.steps.length, this.step + 1);
			this.maxStep = Math.max(this.maxStep, this.step);
		},
		previousStep() { this.step = Math.max(1, this.step - 1); this.stageError = ""; },
		goToStep(target) {
			if (target < 1 || target > this.maxStep || this.saving) return;
			this.step = target;
			this.stageError = "";
		},
		async completeOnboarding() {
			const error = this.validateStep(4) || this.validateStep(3) || this.validateStep(2) || this.validateStep(1);
			if (error) { this.stageError = error; return; }
			this.saving = true;
			this.stageError = "";
			try {
				this.result = await callMethod(COMPLETE_METHOD, { payload: this.form }, "POST");
			} catch (requestError) {
				this.stageError = this.userError(requestError, "User onboarding could not be completed.");
			} finally {
				this.saving = false;
			}
		},
		resetWizard() {
			const mode = this.permissions.can_create_user ? this.initialMode : "existing";
			this.form = blankForm(mode);
			this.selectedUser = {};
			this.branchContext = {};
			this.result = null;
			this.step = 1;
			this.maxStep = 1;
			this.stageError = "";
		},
		openBranchAssignments() { frappe.set_route("branch-assignments"); },
		openBranchSetup() { frappe.set_route("branch-setup"); },
	},
};
</script>

<style scoped>
.onboarding-manager { display: grid; gap: 1rem; }
.onboarding-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; }
.onboarding-header > div { display: grid; gap: 0.35rem; }
.onboarding-header h2, .stage-heading h3, .result-heading h3 { margin: 0; }
.onboarding-header p, .stage-heading p, .guidance-card p, .onboarding-error p, .onboarding-result p { margin: 0; color: var(--text-muted); }
.onboarding-kicker { color: var(--text-muted); font-size: 0.8rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; }
.onboarding-layout { display: grid; grid-template-columns: minmax(11rem, 14rem) minmax(0, 1fr); gap: 1rem; align-items: start; }
.onboarding-steps { display: grid; gap: 0.45rem; margin: 0; padding: 0; list-style: none; position: sticky; top: 1rem; }
.onboarding-step { width: 100%; display: grid; grid-template-columns: 2rem 1fr; align-items: center; gap: 0.65rem; padding: 0.65rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.65rem; background: var(--edge-surface, var(--card-bg)); color: var(--text-color); text-align: left; }
.onboarding-step > span { display: inline-grid; place-items: center; width: 2rem; height: 2rem; border-radius: 50%; border: 1px solid var(--edge-border-color, var(--border-color)); }
.onboarding-step.is-current, .onboarding-step.is-complete { border-color: var(--primary, var(--blue-500)); }
.onboarding-step:disabled { opacity: 0.55; cursor: not-allowed; }
.edge-panel { padding: 1.25rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.75rem; background: var(--edge-surface, var(--card-bg)); }
.onboarding-stage, .onboarding-result { display: grid; gap: 1rem; }
.stage-heading { display: grid; gap: 0.3rem; }
.onboarding-form { display: grid; gap: 1rem; }
.choice-grid, .field-grid, .pos-summary, .review-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.85rem; }
.choice-card { display: grid; gap: 0.35rem; min-height: 6rem; padding: 1rem; text-align: left; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.65rem; background: var(--edge-surface, var(--card-bg)); color: var(--text-color); }
.choice-card span { color: var(--text-muted); }
.choice-card.is-selected { border-color: var(--primary, var(--blue-500)); box-shadow: 0 0 0 1px var(--primary, var(--blue-500)); }
.choice-card:disabled { opacity: 0.55; }
.selection-summary, .guidance-card, .onboarding-error { display: grid; gap: 0.3rem; padding: 0.85rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.65rem; background: var(--edge-surface, var(--control-bg)); }
.selection-summary span { color: var(--text-muted); }
.onboarding-error { border-color: var(--red-300, var(--edge-border-color, var(--border-color))); }
.pos-summary > div:not(.guidance-card), .review-grid > div { display: grid; gap: 0.2rem; padding: 0.8rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.6rem; }
.pos-summary span, .review-grid span { color: var(--text-muted); font-size: 0.8rem; }
.edge-field--wide { grid-column: 1 / -1; }
.result-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
.result-reasons { margin: 0; padding-left: 1.25rem; }
.result-note { padding: 0.75rem; border: 1px solid var(--edge-border-color, var(--border-color)); border-radius: 0.55rem; }
.onboarding-actions { display: flex; align-items: center; justify-content: space-between; gap: 0.75rem; flex-wrap: wrap; padding-top: 0.25rem; }
@media (max-width: 820px) { .onboarding-layout { grid-template-columns: 1fr; } .onboarding-steps { position: static; grid-template-columns: repeat(5, minmax(0, 1fr)); overflow-x: auto; } .onboarding-step { grid-template-columns: 1fr; min-width: 7rem; } }
@media (max-width: 640px) { .choice-grid, .field-grid, .pos-summary, .review-grid { grid-template-columns: 1fr; } .edge-field--wide { grid-column: auto; } .onboarding-header, .result-heading { flex-direction: column; } }
</style>