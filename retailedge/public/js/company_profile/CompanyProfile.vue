<template>
	<div v-if="!edgeUIValid" class="p-6 text-center">
		<strong>Company Profile could not start.</strong>
		<div>Missing EdgeSuite UI components: {{ missingComponents.join(", ") }}</div>
	</div>

	<EdgeAppShell
		v-else
		product="retailedge"
		title="RetailEdge"
		:tenantName="profile.label || profile.name"
		:branchName="operatingContext.branch || 'Company Profile'"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/company-profile"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-company-profile-page">
			<EdgePageHeader
				eyebrow="Administration"
				title="Company Profile"
				description="Maintain the business identity RetailEdge uses in the shell, reports and customer-facing output while ERPNext Company remains the source of truth."
			/>

			<EdgeLoadingState v-if="loading && !loaded" />
			<EdgeErrorState v-else-if="error && !loaded" :message="error" @retry="loadProfile" />

			<div v-else class="company-profile-layout">
				<section class="edge-panel company-profile-preview">
					<div class="company-profile-logo" :class="{ 'has-logo': Boolean(profile.logo) }">
						<img v-if="profile.logo" :src="profile.logo" :alt="profile.label || profile.name" />
						<EdgeIcon v-else name="building" size="lg" />
					</div>

					<div class="company-profile-preview-copy">
						<span class="company-profile-kicker">Operating company</span>
						<h2>{{ profile.company_name || profile.label || profile.name || "Company" }}</h2>
						<p>{{ profile.name }}</p>
						<div class="company-profile-summary">
							<span><small>Abbreviation</small><strong>{{ profile.abbr || "—" }}</strong></span>
							<span><small>Currency</small><strong>{{ profile.currency || "—" }}</strong></span>
							<span><small>Country</small><strong>{{ profile.country || "—" }}</strong></span>
							<span><small>Working Branch</small><strong>{{ operatingContext.branch || "Company-wide" }}</strong></span>
						</div>
					</div>

					<div v-if="canUploadLogo" class="company-profile-logo-actions">
						<button type="button" class="edge-button edge-button--primary" :disabled="savingLogo" @click="uploadLogo">
							{{ savingLogo ? "Updating..." : "Upload logo" }}
						</button>
						<button v-if="profile.logo" type="button" class="edge-button edge-button--secondary" :disabled="savingLogo" @click="removeLogo">
							Remove logo
						</button>
					</div>
				</section>

				<section class="edge-panel">
					<div class="company-profile-heading">
						<div>
							<p class="edge-eyebrow">Identity and tax profile</p>
							<h2>Company details</h2>
							<p>These are safe profile fields only. Currency, country, abbreviation and accounting defaults remain in Advanced ERPNext Company.</p>
						</div>
						<button type="button" class="edge-button edge-button--primary" :disabled="!canWrite || savingProfile" @click="saveProfile">
							{{ savingProfile ? "Saving..." : "Save Company profile" }}
						</button>
					</div>

					<div v-if="!canWrite" class="company-profile-readonly">
						Your current ERPNext permissions allow you to view this Company but not update its profile.
					</div>

					<div class="company-profile-form-grid">
						<label>
							<span>Company name</span>
							<input v-model.trim="profile.company_name" class="form-control" :disabled="!canWrite" />
						</label>
						<label>
							<span>Tax ID</span>
							<input v-model.trim="profile.tax_id" class="form-control" :disabled="!canWrite" />
						</label>
						<label>
							<span>Website</span>
							<input v-model.trim="profile.website" class="form-control" :disabled="!canWrite" placeholder="https://example.com" />
						</label>
						<label>
							<span>Date of establishment</span>
							<input v-model="profile.date_of_establishment" type="date" class="form-control" :disabled="!canWrite" />
						</label>
					</div>

					<p v-if="profileError" class="company-profile-error">{{ profileError }}</p>
				</section>

				<section class="edge-panel">
					<div class="company-profile-heading">
						<div>
							<p class="edge-eyebrow">Official contact location</p>
							<h2>Company address</h2>
							<p>RetailEdge reads and updates the Address linked to this ERPNext Company. It does not create a second Company record.</p>
						</div>
						<div class="company-profile-heading-actions">
							<button type="button" class="edge-button edge-button--primary" :disabled="!canManageAddress || savingAddress" @click="saveAddress">
								{{ savingAddress ? "Saving..." : "Save address" }}
							</button>
							<button v-if="address.name && canUseNativeDesk" type="button" class="edge-button edge-button--secondary" @click="openAddress">
								Open full Address
							</button>
						</div>
					</div>

					<div v-if="!canManageAddress" class="company-profile-readonly">
						Address editing requires the standard ERPNext Address create/write permission.
					</div>

					<div class="company-profile-form-grid">
						<label><span>Address title</span><input v-model.trim="address.address_title" class="form-control" :disabled="!canManageAddress" /></label>
						<label>
							<span>Address type</span>
							<select v-model="address.address_type" class="form-control" :disabled="!canManageAddress">
								<option>Office</option>
								<option>Billing</option>
								<option>Shipping</option>
								<option>Shop</option>
								<option>Other</option>
							</select>
						</label>
						<label class="company-profile-wide"><span>Address line 1</span><input v-model.trim="address.address_line1" class="form-control" :disabled="!canManageAddress" /></label>
						<label class="company-profile-wide"><span>Address line 2</span><input v-model.trim="address.address_line2" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>City / town</span><input v-model.trim="address.city" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>County / LGA</span><input v-model.trim="address.county" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>State / province</span><input v-model.trim="address.state" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>Country</span><input v-model.trim="address.country" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>Postal code</span><input v-model.trim="address.pincode" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>Phone</span><input v-model.trim="address.phone" class="form-control" :disabled="!canManageAddress" /></label>
						<label><span>Email</span><input v-model.trim="address.email_id" type="email" class="form-control" :disabled="!canManageAddress" /></label>
					</div>

					<p v-if="addressError" class="company-profile-error">{{ addressError }}</p>
				</section>

				<section class="edge-panel company-profile-advanced">
					<div>
						<p class="edge-eyebrow">Advanced ERPNext setup</p>
						<h2>Accounting and statutory Company configuration</h2>
						<p>Use the full ERPNext Company form for abbreviation, country, base currency, chart of accounts, default accounts, stock settings and other advanced configuration.</p>
					</div>
					<button v-if="canUseNativeDesk" type="button" class="edge-button edge-button--secondary" @click="openAdvanced">
						Advanced: Open Company in ERPNext
					</button>
					<span v-else class="company-profile-muted">Advanced ERPNext access is not enabled for this user.</span>
				</section>
			</div>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
const REQUIRED_COMPONENTS = ["EdgeAppShell", "EdgePageLayout", "EdgePageHeader", "EdgeLoadingState", "EdgeErrorState", "EdgeIcon"];

const blankAddress = () => ({
	name: "",
	address_title: "",
	address_type: "Office",
	address_line1: "",
	address_line2: "",
	city: "",
	county: "",
	state: "",
	country: "",
	pincode: "",
	phone: "",
	email_id: "",
});

function runtimeComponents() {
	return window.EdgeSuiteUI?.components || {};
}

function callMethod(method, args = {}, type = "GET") {
	return new Promise((resolve, reject) => frappe.call({
		method,
		args,
		type,
		callback: (response) => resolve(response.message || {}),
		error: reject,
	}));
}

export default {
	name: "RetailEdgeCompanyProfile",
	components: Object.fromEntries(REQUIRED_COMPONENTS.map((name) => [name, runtimeComponents()[name]])),
	data() {
		return {
			edgeUIValid: true,
			missingComponents: [],
			loading: false,
			loaded: false,
			error: "",
			profileError: "",
			addressError: "",
			savingProfile: false,
			savingAddress: false,
			savingLogo: false,
			profile: {},
			address: blankAddress(),
			operatingContext: {},
			menuItems: [],
			userName: "",
			canUseNativeDesk: false,
			permissions: { can_write: false, can_upload_logo: false, can_manage_address: false },
		};
	},
	computed: {
		canWrite() { return Boolean(this.permissions?.can_write); },
		canUploadLogo() { return Boolean(this.permissions?.can_upload_logo); },
		canManageAddress() { return Boolean(this.permissions?.can_manage_address); },
	},
	created() {
		const components = runtimeComponents();
		this.missingComponents = REQUIRED_COMPONENTS.filter((name) => !components[name]);
		this.edgeUIValid = this.missingComponents.length === 0;
		this._onPageShow = () => this.loadProfile();
	},
	mounted() {
		window.addEventListener("retailedge-company-profile-page-show", this._onPageShow);
		if (this.edgeUIValid) this.loadProfile();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-company-profile-page-show", this._onPageShow);
	},
	methods: {
		applyProfileResponse(data = {}) {
			this.profile = { ...(data.profile || {}) };
			this.address = { ...blankAddress(), ...(data.address || {}) };
			this.operatingContext = data.operating_context || this.operatingContext || {};
			this.permissions = { ...this.permissions, ...(data.permissions || {}) };
			window.retailedgeSyncShellIdentity?.({
				tenant_name: this.profile.label || this.profile.company_name || this.profile.name || "",
				tenant_logo: this.profile.logo || "",
				active_company: this.profile.name || "",
				active_branch: this.operatingContext.branch || "",
				company_profile: this.profile,
			});
		},
		async loadProfile() {
			if (this.loading) return;
			this.loading = true;
			this.error = "";
			try {
				const navigationPromise = typeof window.retailedgeGetBusinessHubContext === "function"
					? window.retailedgeGetBusinessHubContext({ force: true })
					: callMethod("retailedge.master_experience.get_retailedge_business_hub_context");
				const [data, navigation] = await Promise.all([
					callMethod("retailedge.company_profile.get_company_profile"),
					navigationPromise,
				]);
				this.applyProfileResponse(data);
				this.menuItems = this.mapNavigationGroups(navigation.navigation_groups || []);
				this.userName = navigation.context?.user_name || "";
				this.canUseNativeDesk = Boolean(navigation.access?.can_use_native_desk);
				this.loaded = true;
			} catch (error) {
				this.error = error?.message || error?.exc || "Company Profile could not be loaded.";
			} finally {
				this.loading = false;
			}
		},
		async saveProfile() {
			if (!this.canWrite || !this.profile.name) return;
			this.savingProfile = true;
			this.profileError = "";
			try {
				const data = await callMethod("retailedge.company_profile.save_company_profile", {
					company: this.profile.name,
					profile: JSON.stringify(this.profile),
				}, "POST");
				this.applyProfileResponse(data);
				frappe.show_alert({ message: __("Company profile updated"), indicator: "green" });
			} catch (error) {
				this.profileError = error?.message || error?.exc || "Company profile could not be saved.";
			} finally {
				this.savingProfile = false;
			}
		},
		async saveAddress() {
			if (!this.canManageAddress || !this.profile.name) return;
			this.savingAddress = true;
			this.addressError = "";
			try {
				const data = await callMethod("retailedge.company_profile.save_company_address", {
					company: this.profile.name,
					address: JSON.stringify(this.address),
				}, "POST");
				this.applyProfileResponse(data);
				frappe.show_alert({ message: __("Company address updated"), indicator: "green" });
			} catch (error) {
				this.addressError = error?.message || error?.exc || "Company address could not be saved.";
			} finally {
				this.savingAddress = false;
			}
		},
		uploadLogo() {
			if (!this.canUploadLogo || !this.profile.name || !frappe.ui?.FileUploader) return;
			new frappe.ui.FileUploader({
				doctype: "Company",
				docname: this.profile.name,
				fieldname: "company_logo",
				allow_multiple: false,
				is_private: 0,
				restrictions: {
					allowed_file_types: ["image/*"],
					max_file_size: 2 * 1024 * 1024,
				},
				on_success: async (file) => {
					this.savingLogo = true;
					this.profileError = "";
					try {
						const data = await callMethod("retailedge.company_profile.set_company_logo", {
							company: this.profile.name,
							file_url: file.file_url,
						}, "POST");
						this.applyProfileResponse(data);
						frappe.show_alert({ message: __("Company logo updated"), indicator: "green" });
					} catch (error) {
						this.profileError = error?.message || error?.exc || "Company logo could not be updated.";
					} finally {
						this.savingLogo = false;
					}
				},
			});
		},
		async removeLogo() {
			if (!this.canUploadLogo || !this.profile.name) return;
			this.savingLogo = true;
			this.profileError = "";
			try {
				const data = await callMethod("retailedge.company_profile.set_company_logo", {
					company: this.profile.name,
					file_url: "",
				}, "POST");
				this.applyProfileResponse(data);
				frappe.show_alert({ message: __("Company logo removed"), indicator: "green" });
			} catch (error) {
				this.profileError = error?.message || error?.exc || "Company logo could not be removed.";
			} finally {
				this.savingLogo = false;
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
			return item.target || "";
		},
		handleNavigation(route) {
			const item = this.menuItems.flatMap((group) => group.items || []).find((candidate) => candidate.route === route);
			if (!item) return;
			if (item.target_type === "Page") frappe.set_route(item.target);
			else if (this.canUseNativeDesk && item.target_type === "Report") frappe.set_route("query-report", item.target);
			else if (this.canUseNativeDesk && item.target_type === "DocType") frappe.set_route("List", item.target);
		},
		openAddress() {
			if (this.canUseNativeDesk && this.address.name) frappe.set_route("Form", "Address", this.address.name);
		},
		openAdvanced() {
			if (!this.canUseNativeDesk || !this.profile.name) return;
			frappe.set_route("Form", "Company", this.profile.name);
		},
	},
};
</script>

<style scoped>
.company-profile-layout { display:grid; gap:1rem; }
.edge-panel { padding:1rem; border:1px solid var(--edge-color-border,var(--edge-border)); border-radius:.75rem; background:var(--edge-color-surface,var(--edge-surface)); color:var(--edge-color-ink-950,var(--edge-text)); }
.company-profile-preview { display:grid; grid-template-columns:auto minmax(0,1fr) auto; align-items:center; gap:1rem; }
.company-profile-logo { width:5rem; height:5rem; display:grid; place-items:center; border:1px solid var(--edge-color-border); border-radius:.85rem; background:var(--edge-color-brand-50); color:var(--edge-color-brand-700); overflow:hidden; }
.company-profile-logo img { width:100%; height:100%; object-fit:contain; background:var(--edge-color-surface); }
.company-profile-preview-copy { min-width:0; }
.company-profile-kicker,.company-profile-summary small,.company-profile-form-grid label > span { color:var(--edge-color-ink-500,var(--edge-text-muted)); font-size:.75rem; }
.company-profile-preview h2,.company-profile-heading h2,.company-profile-advanced h2 { margin:.15rem 0; font-size:1.2rem; }
.company-profile-preview p,.company-profile-heading p,.company-profile-advanced p { margin:.15rem 0 0; color:var(--edge-color-ink-500,var(--edge-text-muted)); }
.company-profile-summary { display:flex; flex-wrap:wrap; gap:.75rem 1.25rem; margin-top:.85rem; }
.company-profile-summary span { display:grid; gap:.1rem; }
.company-profile-summary strong { font-size:.82rem; font-weight:650; }
.company-profile-logo-actions,.company-profile-heading-actions { display:flex; flex-wrap:wrap; gap:.5rem; }
.company-profile-heading { display:flex; justify-content:space-between; align-items:flex-start; gap:1rem; margin-bottom:1rem; }
.company-profile-heading > div { min-width:0; }
.company-profile-form-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(13rem,1fr)); gap:.9rem; }
.company-profile-form-grid label { display:grid; gap:.35rem; min-width:0; }
.company-profile-wide { grid-column:1 / -1; }
.company-profile-readonly { margin-bottom:1rem; padding:.75rem .85rem; border:1px solid var(--edge-color-border); border-radius:.65rem; background:var(--edge-color-surface-muted); color:var(--edge-color-ink-700); font-size:.8rem; }
.company-profile-error { color:var(--edge-color-danger); margin:.75rem 0 0; font-size:.8rem; }
.company-profile-advanced { display:flex; justify-content:space-between; align-items:center; gap:1rem; }
.company-profile-muted { color:var(--edge-color-ink-500); font-size:.8rem; }
@media (max-width: 780px) {
	.company-profile-preview { grid-template-columns:auto minmax(0,1fr); }
	.company-profile-logo-actions { grid-column:1 / -1; }
	.company-profile-heading,.company-profile-advanced { align-items:stretch; flex-direction:column; }
}
</style>
