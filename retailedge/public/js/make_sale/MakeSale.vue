<template>
	<EdgeAppShell
		product="retailedge"
		title="Make Sale"
		:tenantName="tenantName"
		:branchName="branchName"
		:userName="userName"
		:menuItems="menuItems"
		activeRoute="/app/make-sale"
		:hideNativeSidebar="true"
		@navigate="handleNavigation"
	>
		<EdgePageLayout class="retailedge-make-sale-page">
			<EdgePageHeader
				title="Make Sale"
				description="Use the full-page sale workspace for multi-item and longer invoices. Quick Sale remains available for short, fast transactions."
			/>

			<EdgeLoadingState v-if="loading && !loaded" message="Preparing Make Sale..." :skeleton="true" />
			<EdgeErrorState v-else-if="loadError" title="Make Sale unavailable" :message="loadError" @retry="loadPage" />

			<div v-else class="make-sale-content">
				<section v-if="recoveryCandidate" class="edge-panel recovery-panel" role="status">
					<div>
						<span class="make-sale-kicker">Unsaved work found</span>
						<strong>Restore the sale you were entering in this browser session?</strong>
						<small>{{ recoverySummary }}</small>
					</div>
					<div class="make-sale-inline-actions">
						<button type="button" class="edge-button edge-button--primary" @click="restoreRecovery">Restore</button>
						<button type="button" class="edge-button" @click="discardRecovery">Discard</button>
					</div>
				</section>

				<section v-if="handoffNotice" class="edge-panel handoff-panel">
					<span class="make-sale-kicker">Continued from Quick Sale</span>
					<p>{{ handoffNotice }}</p>
				</section>

				<section v-if="savedDocument && !editingSavedDraft" class="edge-panel saved-panel">
					<div>
						<span class="make-sale-kicker">{{ Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved" }}</span>
						<h3>{{ savedDocument.name }}</h3>
						<p>{{ Number(savedDocument.docstatus || 0) === 1 ? "ERPNext has submitted the Sales Invoice. Continue with the next valid customer workflow or start another sale." : "The ERPNext Sales Invoice draft now owns the saved work. You can complete it or start another sale." }}</p>
					</div>
					<div class="make-sale-inline-actions">
						<button v-if="Number(savedDocument.docstatus || 0) === 0" type="button" class="edge-button edge-button--primary" @click="beginSavedDraftEdit">Continue Editing on Page</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 0" type="button" class="edge-button" @click="openCompletion">Review / Complete</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('make-payment')" type="button" class="edge-button edge-button--primary" @click="runSavedNextAction('make-payment')">Record Payment</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('create-delivery-note')" type="button" class="edge-button" @click="runSavedNextAction('create-delivery-note')">Create Delivery Note</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1" type="button" class="edge-button" @click="runSavedNextAction('output')">Print / Share</button>
						<button type="button" class="edge-button" @click="startAnother">Start Another Sale</button>
					</div>
				</section>

				<form v-if="!savedDocument || editingSavedDraft" class="edge-panel make-sale-form" @submit.prevent="saveDraft">
					<div class="guided-invoice-context" aria-label="Invoice context">
						<div>
							<span>Company</span>
							<strong>{{ values.company || "Not set" }}</strong>
						</div>
						<div v-if="values.branch">
							<span>Branch</span>
							<strong>{{ values.branch }}</strong>
						</div>
						<div>
							<span>Selling Price List</span>
							<strong>{{ pricingLabel }}</strong>
							<small>{{ pricingSourceLabel }}</small>
						</div>
					</div>

					<div v-if="saveError" class="guided-invoice-error" role="alert">{{ saveError }}</div>
					<div v-else-if="stockContextMessage" class="guided-invoice-warning" role="status">{{ stockContextMessage }}</div>

					<div class="guided-invoice-grid">
						<EdgeLinkField
							:modelValue="values.customer"
							label="Customer"
							placeholder="Search customer"
							description="Only customers you can access are shown. Create a new Customer here when permitted."
							:required="true"
							:searcher="searchCustomer"
							:context="searchContext"
							:canCreate="!editingSavedDraft && canCreateCustomer"
							:creator="createCustomer"
							:disabled="editingSavedDraft"
							createLabel="Create Customer"
							@update:modelValue="setCustomer"
						/>

						<EdgeInput v-model="values.posting_date" id="make-sale-posting-date" label="Posting Date" type="date" required />

						<EdgeLinkField
							v-if="branchEnabled"
							:modelValue="values.branch"
							label="Branch"
							placeholder="Search branch"
							description="Only enabled Branch Setup entries for the active Company are shown."
							:searcher="searchBranch"
							:context="searchContext"
							:disabled="editingSavedDraft"
							@update:modelValue="setBranch"
						/>

						<EdgeLinkField
							:modelValue="values.warehouse"
							label="Stock Location"
							placeholder="Search stock location"
							description="Stock Locations are limited to the selected Company and enabled Branch Setup."
							:required="Boolean(values.update_stock)"
							:disabled="editingSavedDraft || (requiresBranchSelection && !values.branch)"
							:searcher="searchWarehouse"
							:context="searchContext"
							@update:modelValue="setWarehouse"
						/>
					</div>

					<label class="guided-check-field">
						<input
							v-model="values.update_stock"
							type="checkbox"
							:true-value="1"
							:false-value="0"
							:disabled="editingSavedDraft || !canEditUpdateStock"
						/>
						<span>
							<strong>Update Stock</strong>
							<small>{{ canEditUpdateStock ? "Post stock movement when the invoice is eventually submitted." : "Update Stock is required by the current sales settings for Make a Sale." }}</small>
						</span>
					</label>

					<div class="items-heading">
						<div>
							<span class="make-sale-kicker">Sale items</span>
							<h3>Products and services</h3>
							<p>This full-page workspace is intended for larger invoices; add as many valid lines as the transaction requires.</p>
						</div>
						<span class="item-count">{{ populatedItemCount }} item{{ populatedItemCount === 1 ? "" : "s" }}</span>
					</div>

					<EdgeChildTable
						:field="itemTableField"
						:rows="values.items"
						:columns="itemColumns"
						:addLabel="'Add Item'"
						:linkSearcher="searchLineLink"
						:linkCanCreate="canCreateItemLink"
						:linkCreator="createItemLink"
						:linkCreateLabel="itemCreateLabel"
						:newRowsFirst="true"
						@update:rows="updateItems"
					/>

					<p class="guided-invoice-hint">
						Rates use your assigned Price List or POS Profile where available, followed by ERPNext pricing rules and selling defaults.
						The server validates pricing again when the draft is saved.
					</p>

					<label class="guided-field guided-field--wide">
						<span>Remarks</span>
						<textarea v-model="values.remarks" class="form-control" rows="4" placeholder="Optional note for this invoice"></textarea>
					</label>

					<div class="make-sale-actions">
						<div>
							<strong>{{ hasUnsavedChanges ? "Unsaved changes" : "Ready" }}</strong>
							<small v-if="hasUnsavedChanges">This browser session keeps a temporary recovery copy until the ERPNext draft is saved.</small>
							<small v-else>Complete the required fields, then save the ERPNext draft.</small>
						</div>
						<div class="make-sale-inline-actions">
							<button v-if="canUseNativeDesk" type="button" class="edge-button" :disabled="saving" @click="openAdvancedNative">Advanced: ERPNext</button>
							<button v-if="editingSavedDraft" type="button" class="edge-button" :disabled="saving" @click="cancelSavedDraftEdit">Cancel Edit</button>
							<button v-else type="button" class="edge-button" :disabled="saving" @click="resetForm">Reset</button>
							<button
								type="submit"
								class="edge-button edge-button--primary"
								:disabled="saving || loading || !transactionContextReady"
							>
								{{ saving ? "Saving..." : (editingSavedDraft ? "Update Draft" : (formContext.submit_label || "Save Draft")) }}
							</button>
						</div>
					</div>
				</form>
			</div>

			<StandardSalesInvoiceCompletionDialog
				:open="completionOpen"
				:document="savedDocument"
				:canUseNativeDesk="canUseNativeDesk"
				:showNextActions="true"
				@close="completionOpen = false"
				@changed="handleCompletionChanged"
				@completed="handleCompletionCompleted"
				@next-action="handleCompletionNextAction"
			/>
			<StandardDeliveryCompletionDialog
				:open="deliveryCompletionOpen"
				:document="deliveryCompletionDocument"
				:canUseNativeDesk="canUseNativeDesk"
				@close="closeDeliveryCompletion"
				@changed="handleDeliveryCompletionChanged"
				@completed="handleDeliveryCompletionCompleted"
				@next-action="handleDeliveryNextAction"
			/>
			<SimplePaymentDialog
				:open="paymentOpen"
				intent="receive-customer-payment"
				:initialContext="paymentInitialContext"
				:nativeFallbackEnabled="canUseNativeDesk"
				@close="closePayment"
				@saved="closePayment"
			/>
		</EdgePageLayout>
	</EdgeAppShell>
</template>

<script>
import {
	callMethod,
	errorMessage,
	quickCreateCustomer,
	quickCreateItem,
	resolveBranchWarehouse,
} from "../retailedge_business_hub/guidedEntryUtils";
import StandardSalesInvoiceCompletionDialog from "../professional_selling/StandardSalesInvoiceCompletionDialog.vue";
import StandardDeliveryCompletionDialog from "../professional_selling/StandardDeliveryCompletionDialog.vue";
import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue";

const CONTEXT_METHOD = "retailedge.guided_sales_invoice.get_simple_sales_invoice_context";
const SEARCH_METHOD = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const PRICING_METHOD = "retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing";
const CREATE_METHOD = "retailedge.guided_sales_invoice.create_simple_sales_invoice_draft";
const UPDATE_METHOD = "retailedge.standard_sales_invoice_completion.update_standard_sales_invoice_draft";
const SHELL_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const CREATE_DELIVERY_METHOD = "retailedge.professional_delivery.create_delivery_note_from_sales_invoice";
const HANDOFF_PREFIX = "retailedge:make-sale:handoff:";
const RECOVERY_PREFIX = "retailedge:make-sale:recovery:";
const HANDOFF_MAX_AGE_MS = 10 * 60 * 1000;
const RECOVERY_MAX_AGE_MS = 12 * 60 * 60 * 1000;
const runtime = typeof window !== "undefined" && window.EdgeSuiteUI ? window.EdgeSuiteUI.components || window.EdgeSuiteUI : {};

function emptyValues() {
	return {
		company: "",
		branch: "",
		posting_date: "",
		warehouse: "",
		customer: "",
		update_stock: 1,
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

function sourceLabel(source) {
	return {
		user_default: "User default",
		user_permission: "User-assigned Price List",
		pos_profile: "Assigned POS Profile",
		party_default: "Customer default",
		erpnext_default: "ERPNext default",
		standard_price_list: "Standard Selling",
		item_fallback: "Item fallback",
	}[source] || "ERPNext pricing";
}

function cloneValues(values) {
	return JSON.parse(JSON.stringify(values || emptyValues()));
}

function cleanStoredPayload(raw, maxAge) {
	if (!raw) return null;
	try {
		const parsed = JSON.parse(raw);
		if (!parsed?.createdAt || Date.now() - Number(parsed.createdAt) > maxAge) return null;
		if (!parsed.values || typeof parsed.values !== "object") return null;
		return parsed;
	} catch (_error) {
		return null;
	}
}

export default {
	name: "RetailEdgeMakeSale",
	components: {
		EdgeAppShell: runtime.EdgeAppShell,
		EdgePageLayout: runtime.EdgePageLayout,
		EdgePageHeader: runtime.EdgePageHeader,
		EdgeLoadingState: runtime.EdgeLoadingState,
		EdgeErrorState: runtime.EdgeErrorState,
		EdgeLinkField: runtime.EdgeLinkField,
		EdgeInput: runtime.EdgeInput,
		EdgeChildTable: runtime.EdgeChildTable,
		StandardSalesInvoiceCompletionDialog,
		StandardDeliveryCompletionDialog,
		SimplePaymentDialog,
	},
	data() {
		return {
			loading: false,
			loaded: false,
			saving: false,
			loadError: "",
			saveError: "",
			formContext: {},
			values: emptyValues(),
			initialSnapshot: "",
			cascadeToken: 0,
			pricingTokens: {},
			pricingCache: new Map(),
			recoveryCandidate: null,
			handoffNotice: "",
			recoveryTimer: null,
			savedDocument: null,
			editingSavedDraft: false,
			completionOpen: false,
			deliveryCompletionOpen: false,
			deliveryCompletionDocument: null,
			paymentOpen: false,
			paymentInitialContext: {},
			tenantName: "",
			branchName: "",
			userName: "",
			menuItems: [],
			canUseNativeDesk: false,
			itemTableField: {
				label: "Items",
				description: "Use the full-page workspace for larger invoices and long item lists.",
			},
			itemColumns: [
				{ fieldname: "item_code", label: "Item", fieldtype: "Link", placeholder: "Search item" },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Selling Rate", fieldtype: "Currency", placeholder: "Auto price" },
			],
		};
	},
	computed: {
		branchEnabled() {
			return Boolean(this.formContext.capabilities?.branch_enabled);
		},
		requiresBranchSelection() {
			return Boolean(this.formContext.capabilities?.requires_branch_selection);
		},
		canEditUpdateStock() {
			return Boolean(this.formContext.capabilities?.can_edit_update_stock);
		},
		transactionContextReady() {
			if (!this.values.update_stock) return true;
			if (this.requiresBranchSelection && !this.values.branch) return false;
			return Boolean(this.values.warehouse);
		},
		stockContextMessage() {
			if (!this.values.update_stock) return "";
			if (this.requiresBranchSelection && !this.values.branch) return "Choose a Branch before selecting the Stock Location.";
			if (!this.values.warehouse) return "Choose a Stock Location before saving this stock-updating sale.";
			return "";
		},
		canCreateCustomer() {
			return Boolean(this.formContext.capabilities?.can_create_customer);
		},
		canCreateItem() {
			return Boolean(this.formContext.capabilities?.can_create_item);
		},
		pricingLabel() {
			return this.formContext.pricing?.price_list || "Item default";
		},
		pricingSourceLabel() {
			return sourceLabel(this.formContext.pricing?.source);
		},
		searchContext() {
			return {
				company: this.values.company,
				branch: this.values.branch,
				warehouse: this.values.warehouse,
				customer: this.values.customer,
			};
		},
		hasUnsavedChanges() {
			return Boolean(this.initialSnapshot && JSON.stringify(this.values) !== this.initialSnapshot);
		},
		populatedItemCount() {
			return (this.values.items || []).filter((row) => row?.item_code).length;
		},
		recoverySummary() {
			const values = this.recoveryCandidate?.values || {};
			const itemCount = (values.items || []).filter((row) => row?.item_code).length;
			const party = values.customer ? `Customer: ${values.customer}. ` : "";
			return `${party}${itemCount} item${itemCount === 1 ? "" : "s"} entered.`;
		},
	},
	watch: {
		values: {
			deep: true,
			handler() {
				if (!this.loaded || this.savedDocument) return;
				this.scheduleRecovery();
			},
		},
	},
	created() {
		this._onPageShow = () => {
			if (!this.loaded && !this.loading) this.loadPage();
		};
		this._beforeUnload = (event) => {
			if (!this.hasUnsavedChanges || this.saving || (this.savedDocument && !this.editingSavedDraft)) return;
			event.preventDefault();
			event.returnValue = "";
		};
	},
	mounted() {
		window.addEventListener("retailedge-make-sale-page-show", this._onPageShow);
		window.addEventListener("beforeunload", this._beforeUnload);
		this.loadPage();
	},
	beforeUnmount() {
		window.removeEventListener("retailedge-make-sale-page-show", this._onPageShow);
		window.removeEventListener("beforeunload", this._beforeUnload);
		if (this.recoveryTimer) window.clearTimeout(this.recoveryTimer);
	},
	methods: {
		async loadPage() {
			if (this.loading) return;
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			this.savedDocument = null;
			this.completionOpen = false;
			this.handoffNotice = "";
			this.pricingCache.clear();
			try {
				const [data, shell] = await Promise.all([
					callMethod(CONTEXT_METHOD),
					callMethod(SHELL_METHOD),
				]);
				this.formContext = data || {};
				this.applyShellContext(shell || {});
				this.applyFreshDefaults(data?.defaults || {});
				const usedHandoff = this.consumeHandoff();
				if (!usedHandoff) this.loadRecoveryCandidate();
				this.loaded = true;
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Make Sale.");
			} finally {
				this.loading = false;
			}
		},
		applyFreshDefaults(defaults) {
			this.values = {
				...emptyValues(),
				...(defaults || {}),
				items: (defaults?.items || emptyValues().items).map((row) => ({ ...row })),
			};
			if (!this.formContext.capabilities?.can_edit_update_stock) this.values.update_stock = 1;
			this.applyRatePermission();
			this.initialSnapshot = JSON.stringify(this.values);
		},
		applyRatePermission() {
			const readOnly = this.formContext.capabilities?.can_override_rate === false;
			this.itemColumns = this.itemColumns.map((column) =>
				column.fieldname === "rate" ? { ...column, read_only: readOnly ? 1 : 0 } : column
			);
		},
		applyShellContext(shell) {
			const context = shell.context || {};
			this.tenantName = context.company_label || context.company || "";
			this.branchName = context.branch || "";
			this.userName = context.user_name || "";
			this.canUseNativeDesk = Boolean(shell.access?.can_use_native_desk)
				&& shell.feature_flags?.native_document_fallback_enabled !== false;
			this.menuItems = (shell.navigation_groups || [])
				.map((group) => ({
					key: group.key,
					label: group.label,
					icon: group.icon || "layers",
					defaultCollapsed: group.key !== "sell",
					items: (group.items || [])
						.map((item) => ({
							label: item.label,
							description: item.description || "",
							icon: item.icon || "list",
							route: this.routeForTarget(item),
							source: item,
						}))
						.filter((item) => item.route),
				}))
				.filter((group) => group.items.length);
		},
		routeForTarget(item) {
			if (!item) return "";
			if (item.target_type === "URL") return item.target || "";
			if (item.target_type === "Page") return `/app/${item.target}`;
			if (["DocType", "Report"].includes(item.target_type) && !this.canUseNativeDesk) return "";
			if (item.target_type === "DocType") return `/app/${frappe.router.slug(item.target)}`;
			if (item.target_type === "Report") return `/app/query-report/${encodeURIComponent(item.target)}`;
			return "";
		},
		handleNavigation(route) {
			if (!route || route === "/app/make-sale") return;
			const navigate = () => {
				if (/^https?:\/\//i.test(route)) {
					window.location.assign(route);
					return;
				}
				const normalized = String(route).replace(/^\/app\//, "");
				frappe.set_route(...normalized.split("/").filter(Boolean));
			};
			if (!this.hasUnsavedChanges || this.savedDocument) {
				navigate();
				return;
			}
			frappe.confirm(
				"Leave Make Sale? Unsaved changes are kept temporarily in this browser session, but no ERPNext draft has been created yet.",
				navigate
			);
		},
		recoveryKey() {
			return `${RECOVERY_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`;
		},
		handoffKey() {
			return `${HANDOFF_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`;
		},
		consumeHandoff() {
			let raw = "";
			try {
				raw = window.sessionStorage.getItem(this.handoffKey()) || "";
				window.sessionStorage.removeItem(this.handoffKey());
			} catch (_error) {
				return false;
			}
			const payload = cleanStoredPayload(raw, HANDOFF_MAX_AGE_MS);
			if (!payload) return false;
			if (payload.values.company && this.values.company && payload.values.company !== this.values.company) {
				frappe.show_alert?.({ message: "Quick Sale data belongs to another Company and was not carried into Make Sale.", indicator: "orange" }, 7);
				return false;
			}
			this.values = {
				...this.values,
				...cloneValues(payload.values),
				items: (payload.values.items || this.values.items || []).map((row) => ({ ...row })),
			};
			if (!this.formContext.capabilities?.can_edit_update_stock) this.values.update_stock = 1;
			this.handoffNotice = "Your customer, context and item lines were carried into the full-page workspace.";
			return true;
		},
		loadRecoveryCandidate() {
			let raw = "";
			try {
				raw = window.sessionStorage.getItem(this.recoveryKey()) || "";
			} catch (_error) {
				return;
			}
			const payload = cleanStoredPayload(raw, RECOVERY_MAX_AGE_MS);
			if (!payload) {
				this.clearRecovery();
				return;
			}
			if (payload.values.company && this.values.company && payload.values.company !== this.values.company) return;
			this.recoveryCandidate = payload;
		},
		async restoreRecovery() {
			if (!this.recoveryCandidate?.values) return;
			const recovered = cloneValues(this.recoveryCandidate.values);
			this.values = {
				...this.values,
				...recovered,
				items: (recovered.items || []).map((row) => ({ ...row })),
			};
			if (!this.formContext.capabilities?.can_edit_update_stock) this.values.update_stock = 1;
			this.recoveryCandidate = null;
			this.saveError = "";
			try {
				if (this.values.company && (this.values.branch || this.values.warehouse)) {
					const resolved = await resolveBranchWarehouse({
						company: this.values.company,
						branch: this.values.branch || "",
						warehouse: this.values.warehouse || "",
						preference: "sales",
					});
					this.values.branch = resolved.branch || this.values.branch || "";
					this.values.warehouse = resolved.warehouse || this.values.warehouse || "";
				}
				this.handoffNotice = "Recovered unsaved Make Sale work and revalidated its current Branch / Stock Location access.";
			} catch (error) {
				this.values.branch = "";
				this.values.warehouse = "";
				this.saveError = errorMessage(error, "The recovered Branch or Stock Location is no longer available. Choose the current transaction context before saving.");
				this.handoffNotice = "Recovered line items, but the saved Branch / Stock Location was cleared because access could not be revalidated.";
			}
		},
		discardRecovery() {
			this.recoveryCandidate = null;
			this.clearRecovery();
		},
		scheduleRecovery() {
			if (this.recoveryTimer) window.clearTimeout(this.recoveryTimer);
			this.recoveryTimer = window.setTimeout(() => {
				if (!this.hasUnsavedChanges || this.savedDocument) {
					this.clearRecovery();
					return;
				}
				try {
					window.sessionStorage.setItem(this.recoveryKey(), JSON.stringify({
						createdAt: Date.now(),
						values: cloneValues(this.values),
					}));
				} catch (_error) {
					// Recovery is best-effort; server save remains authoritative.
				}
			}, 250);
		},
		clearRecovery() {
			try {
				window.sessionStorage.removeItem(this.recoveryKey());
			} catch (_error) {
				// Browser storage can be unavailable without blocking transaction entry.
			}
		},
		resetForm() {
			const reset = () => {
				this.recoveryCandidate = null;
				this.clearRecovery();
				this.applyFreshDefaults(this.formContext.defaults || {});
				this.saveError = "";
			};
			if (!this.hasUnsavedChanges) {
				reset();
				return;
			}
			frappe.confirm("Discard the unsaved Make Sale changes on this page?", reset);
		},
		async searchOptions(fieldname, query) {
			const results = await callMethod(SEARCH_METHOD, {
				fieldname,
				txt: query || "",
				values: {
					company: this.values.company,
					branch: this.values.branch,
					warehouse: this.values.warehouse,
					customer: this.values.customer,
				},
			});
			return Array.isArray(results) ? results : [];
		},
		searchCustomer(query) {
			return this.searchOptions("customer", query);
		},
		searchBranch(query) {
			return this.searchOptions("branch", query);
		},
		searchWarehouse(query) {
			return this.searchOptions("warehouse", query);
		},
		searchLineLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve([]);
			return this.searchOptions("item_code", query);
		},
		createCustomer(query) {
			return quickCreateCustomer(query);
		},
		canCreateItemLink(column) {
			return this.canCreateItem && column?.fieldname === "item_code";
		},
		createItemLink(column, query) {
			if (column?.fieldname !== "item_code") return Promise.resolve(null);
			return quickCreateItem(query);
		},
		itemCreateLabel(column) {
			return column?.fieldname === "item_code" ? "Create Item" : "Create new";
		},
		setCustomer(next) {
			const changed = Boolean(this.values.customer && this.values.customer !== next);
			this.values.customer = next || "";
			this.pricingCache.clear();
			if (changed) {
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "" }));
				this.refreshAllItemPricing();
			}
		},
		async setBranch(next) {
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			this.values.items = (this.values.items || []).map((row) => ({ ...row, rate: "" }));
			this.pricingCache.clear();
			if (!branch || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch,
					preference: "sales",
				});
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || branch;
				this.values.warehouse = resolved.warehouse || "";
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch stock location.");
			}
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			this.pricingCache.clear();
			if (!warehouse || !this.values.company) return;
			const token = ++this.cascadeToken;
			try {
				const resolved = await resolveBranchWarehouse({
					company: this.values.company,
					branch: this.values.branch,
					warehouse,
					preference: "sales",
				});
				if (token !== this.cascadeToken) return;
				this.values.branch = resolved.branch || this.values.branch;
				this.values.warehouse = resolved.warehouse || warehouse;
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) {
					this.values.warehouse = "";
					this.saveError = errorMessage(error, "Unable to use the selected Stock Location.");
				}
			}
		},
		updateItems(nextRows) {
			const previous = this.values.items || [];
			const changed = [];
			this.values.items = (nextRows || []).map((row, index) => {
				const prior = previous[index] || {};
				if (row.item_code && row.item_code !== prior.item_code) {
					changed.push(index);
					return { ...row, rate: "" };
				}
				return { ...row };
			});
			for (const index of changed) this.loadItemPricing(index);
		},
		pricingCacheKey(row) {
			return [
				this.values.company,
				this.values.branch,
				this.values.warehouse,
				this.values.customer,
				this.values.posting_date,
				row.item_code,
				row.qty || 1,
			].join("|");
		},
		async loadItemPricing(index) {
			const row = this.values.items[index];
			if (!row?.item_code || !this.values.customer) return;
			const key = this.pricingCacheKey(row);
			const token = `${row.item_code}:${Date.now()}:${Math.random()}`;
			this.pricingTokens[index] = token;
			try {
				let result = this.pricingCache.get(key);
				if (!result) {
					result = await callMethod(PRICING_METHOD, {
						item_code: row.item_code,
						values: {
							company: this.values.company,
							branch: this.values.branch,
							warehouse: this.values.warehouse,
							customer: this.values.customer,
							posting_date: this.values.posting_date,
							qty: row.qty || 1,
						},
					});
					this.pricingCache.set(key, result);
				}
				if (this.pricingTokens[index] !== token || this.values.items[index]?.item_code !== row.item_code) return;
				if (result?.rate !== null && result?.rate !== undefined) this.values.items[index] = { ...this.values.items[index], rate: result.rate };
				this.formContext.pricing = {
					...(this.formContext.pricing || {}),
					price_list: result?.price_list || this.formContext.pricing?.price_list || "",
					source: result?.source || this.formContext.pricing?.source || "item_fallback",
				};
			} catch (error) {
				if (this.pricingTokens[index] === token) this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
			}
		},
		refreshAllItemPricing() {
			if (!this.values.customer) return;
			this.values.items.forEach((row, index) => {
				if (!row.item_code) return;
				this.values.items[index] = { ...row, rate: "" };
				this.loadItemPricing(index);
			});
		},
		async saveDraft() {
			if (this.saving || this.loading || !this.transactionContextReady) return;
			this.saveError = "";
			this.saving = true;
			try {
				let result;
				if (this.savedDocument?.name && this.editingSavedDraft) {
					result = await callMethod(UPDATE_METHOD, {
						name: this.savedDocument.name,
						expected_modified: this.savedDocument.modified || "",
						values: {
							posting_date: this.values.posting_date,
							remarks: this.values.remarks || "",
							items: (this.values.items || []).filter((row) => row?.item_code).map((row) => ({
								item_code: row.item_code,
								qty: Number(row.qty || 0),
								rate: row.rate,
							})),
						},
					}, "POST");
					this.syncPageFromDraftPreview(result);
					this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
					this.initialSnapshot = JSON.stringify(this.values);
					this.editingSavedDraft = false;
					frappe.show_alert?.({ message: `Sales Invoice ${result.name} draft updated`, indicator: "green" });
					return;
				}
				result = await callMethod(CREATE_METHOD, { values: this.values });
				if (!result?.name) throw new Error("The Sales Invoice draft was not returned after saving.");
				this.clearRecovery();
				this.initialSnapshot = JSON.stringify(this.values);
				this.savedDocument = { ...result, doctype: result.doctype || "Sales Invoice" };
				this.completionOpen = true;
				frappe.show_alert?.({ message: `Sales Invoice ${result.name} saved as Draft`, indicator: "green" });
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Sales Invoice draft.");
			} finally {
				this.saving = false;
			}
		},
		beginSavedDraftEdit() {
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 0) return;
			this.editingSavedDraft = true;
			this.completionOpen = false;
			this.initialSnapshot = JSON.stringify(this.values);
		},
		cancelSavedDraftEdit() {
			const close = () => {
				try { this.values = JSON.parse(this.initialSnapshot || "{}"); } catch (_error) {}
				this.editingSavedDraft = false;
				this.saveError = "";
			};
			if (!this.hasUnsavedChanges) return close();
			frappe.confirm("Discard unsaved changes to this saved Sales Invoice draft?", close);
		},
		syncPageFromDraftPreview(result) {
			if (!result) return;
			if (result.posting_date) this.values.posting_date = result.posting_date;
			if (Object.prototype.hasOwnProperty.call(result, "remarks")) this.values.remarks = result.remarks || "";
			if (Array.isArray(result.editable_items)) {
				this.values.items = result.editable_items.map((row) => ({
					item_code: row.item_code || "",
					qty: row.qty,
					rate: row.rate,
				}));
			}
		},
		openCompletion() {
			if (this.savedDocument?.name) {
				this.editingSavedDraft = false;
				this.completionOpen = true;
			}
		},
		handleCompletionChanged(result) {
			if (!result?.name) return;
			this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
			if (Number(result.docstatus || 0) === 0) {
				this.syncPageFromDraftPreview(result);
				this.initialSnapshot = JSON.stringify(this.values);
			}
		},
		handleCompletionCompleted(result) {
			this.editingSavedDraft = false;
			if (result?.name) this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
		},
		hasSavedNextAction(action) {
			return (this.savedDocument?.next_actions || []).some((row) => row?.value === action);
		},
		runSavedNextAction(action) {
			if (!this.savedDocument?.name) return;
			this.handleCompletionNextAction({
				action,
				doctype: "Sales Invoice",
				name: this.savedDocument.name,
				customer: this.savedDocument.customer || this.values.customer || "",
			});
		},
		async handleCompletionNextAction(payload) {
			if (!payload?.action || !payload?.name) return;
			this.completionOpen = false;
			if (payload.action === "make-payment") {
				this.paymentInitialContext = {
					company: this.savedDocument?.company || this.values.company || "",
					branch: this.savedDocument?.branch || this.values.branch || "",
					party: payload.customer || this.savedDocument?.customer || this.values.customer || "",
					reference_name: payload.name,
				};
				this.paymentOpen = true;
				return;
			}
			if (payload.action === "create-delivery-note") {
				try {
					const result = await callMethod(CREATE_DELIVERY_METHOD, { sales_invoice: payload.name }, "POST");
					if (!result?.name) throw new Error("Delivery Note draft was not returned.");
					this.deliveryCompletionDocument = { doctype: "Delivery Note", name: result.name };
					if (Number(result.docstatus || 0) === 0) this.deliveryCompletionOpen = true;
					else this.openDocumentOutput("delivery-note", result.name, "view");
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to continue to Delivery Note.");
				}
				return;
			}
			if (payload.action === "output") this.openDocumentOutput("sales-invoice", payload.name, "share");
		},
		closePayment() {
			this.paymentOpen = false;
			this.paymentInitialContext = {};
		},
		closeDeliveryCompletion() {
			this.deliveryCompletionOpen = false;
			this.deliveryCompletionDocument = null;
		},
		handleDeliveryCompletionChanged() {},
		handleDeliveryCompletionCompleted() {},
		handleDeliveryNextAction(payload) {
			if (payload?.action === "output" && payload?.name) {
				this.closeDeliveryCompletion();
				this.openDocumentOutput("delivery-note", payload.name, "share");
			}
		},
		openDocumentOutput(document, name, mode = "share") {
			if (!document || !name) return;
			window.retailedgeDocumentOutputTarget = { document, name, mode };
			frappe.set_route("document-output-sharing");
		},
		async startAnother() {
			this.savedDocument = null;
			this.editingSavedDraft = false;
			this.recoveryCandidate = null;
			await this.loadPage();
		},
		openAdvancedNative() {
			if (!this.canUseNativeDesk) return;
			const navigate = () => frappe.new_doc("Sales Invoice");
			if (!this.hasUnsavedChanges) {
				navigate();
				return;
			}
			frappe.confirm(
				"Open the advanced ERPNext Sales Invoice form? Save this Make Sale draft first if you want the current page entries recorded in ERPNext.",
				navigate
			);
		},
	},
};
</script>

<style scoped>
.make-sale-content,
.make-sale-form {
	display: grid;
	gap: 18px;
}
.make-sale-content {
	padding-bottom: 28px;
}
.make-sale-form,
.recovery-panel,
.handoff-panel,
.saved-panel {
	padding: 18px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #dfe3e8));
	border-radius: 12px;
	background: var(--edge-color-surface, #fff);
}
.recovery-panel,
.saved-panel {
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 18px;
}
.recovery-panel > div:first-child,
.saved-panel > div:first-child {
	display: grid;
	gap: 4px;
}
.recovery-panel small,
.saved-panel p,
.handoff-panel p,
.items-heading p,
.make-sale-actions small {
	margin: 0;
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.handoff-panel {
	display: grid;
	gap: 4px;
}
.make-sale-kicker {
	font-size: .72rem;
	font-weight: 700;
	text-transform: uppercase;
	letter-spacing: .07em;
	color: var(--edge-color-brand-600, #2563eb);
}
.guided-invoice-context {
	display: flex;
	flex-wrap: wrap;
	gap: 10px;
}
.guided-invoice-context > div {
	display: grid;
	gap: 2px;
	min-width: 180px;
	padding: 9px 12px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 8px;
	background: var(--edge-color-surface-muted, var(--edge-surface-muted, #f8fafc));
}
.guided-invoice-context span,
.guided-field > span {
	font-size: .78rem;
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.guided-invoice-context small {
	font-size: .72rem;
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.guided-invoice-grid {
	display: grid;
	grid-template-columns: repeat(2, minmax(0, 1fr));
	gap: 14px;
}
.guided-field {
	display: grid;
	gap: 6px;
}
.guided-field > span {
	font-weight: 600;
	color: var(--edge-color-ink-700, var(--edge-text, #344054));
}
.guided-field--wide {
	grid-column: 1 / -1;
}
.guided-check-field {
	display: flex;
	align-items: flex-start;
	gap: 10px;
	padding: 11px 12px;
	border: 1px solid var(--edge-color-border, var(--edge-border, #e5e7eb));
	border-radius: 8px;
}
.guided-check-field span {
	display: grid;
	gap: 2px;
}
.guided-check-field small,
.guided-invoice-hint {
	color: var(--edge-color-ink-500, var(--edge-text-muted, #667085));
}
.guided-invoice-hint {
	margin: -8px 0 0;
	font-size: .8rem;
}
.guided-invoice-warning,
.guided-invoice-error {
	padding: 10px 12px;
	border-radius: 8px;
}
.guided-invoice-warning {
	border: 1px solid var(--edge-color-warning, #f79009);
	background: var(--edge-color-warning-subtle, #fffaeb);
}
.guided-invoice-error {
	border: 1px solid var(--edge-color-danger, #d92d20);
	color: var(--edge-color-danger, #b42318);
	background: var(--edge-color-danger-subtle, #fef3f2);
}
.items-heading {
	display: flex;
	align-items: flex-end;
	justify-content: space-between;
	gap: 16px;
}
.items-heading h3 {
	margin: 3px 0 4px;
}
.item-count {
	white-space: nowrap;
	font-size: .8rem;
	font-weight: 700;
	padding: 6px 9px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 999px;
}
.make-sale-actions {
	position: sticky;
	bottom: 0;
	z-index: 5;
	display: flex;
	align-items: center;
	justify-content: space-between;
	gap: 16px;
	padding: 14px;
	border: 1px solid var(--edge-color-border, #dfe3e8);
	border-radius: 10px;
	background: color-mix(in srgb, var(--edge-color-surface, #fff) 94%, transparent);
	backdrop-filter: blur(8px);
}
.make-sale-actions > div:first-child {
	display: grid;
	gap: 2px;
}
.make-sale-inline-actions {
	display: flex;
	align-items: center;
	gap: 8px;
	flex-wrap: wrap;
	justify-content: flex-end;
}
:global(:root[data-edge-appearance="dark"]) .make-sale-form,
:global(:root[data-edge-appearance="dark"]) .recovery-panel,
:global(:root[data-edge-appearance="dark"]) .handoff-panel,
:global(:root[data-edge-appearance="dark"]) .saved-panel {
	background: var(--edge-color-surface);
	border-color: var(--edge-color-border);
}
@media (max-width: 760px) {
	.guided-invoice-grid {
		grid-template-columns: 1fr;
	}
	.recovery-panel,
	.saved-panel,
	.items-heading,
	.make-sale-actions {
		align-items: stretch;
		flex-direction: column;
	}
	.make-sale-inline-actions {
		justify-content: flex-start;
	}
}
</style>
