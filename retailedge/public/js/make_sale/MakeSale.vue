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
					<span class="make-sale-kicker">Sale status</span>
					<p>{{ handoffNotice }}</p>
				</section>

				<UnfinishedSalesPanel
					v-if="!savedDocument && !editingSavedDraft"
					:drafts="unfinishedSales"
					:loading="unfinishedSalesLoading"
					:error="unfinishedSalesError"
					@refresh="refreshUnfinishedSales"
					@resume="resumeUnfinishedSale"
					@review="reviewUnfinishedSale"
				/>

				<section v-if="savedDocument && !editingSavedDraft" class="edge-panel saved-panel">
					<div>
						<span class="make-sale-kicker">{{ Number(savedDocument.docstatus || 0) === 1 ? "Submitted" : "Draft saved" }}</span>
						<h3>{{ savedDocument.name }}</h3>
						<p>{{ Number(savedDocument.docstatus || 0) === 1 ? "This sale has been submitted. Continue with the next customer action or start another sale." : "This sale is saved as a draft. Review it below, edit it if needed, or start another sale." }}</p>
					</div>
					<div class="make-sale-inline-actions">
						<button v-if="Number(savedDocument.docstatus || 0) === 0 && savedDocument.can_edit" type="button" class="edge-button" @click="beginSavedDraftEdit">Edit Sale</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('make-payment')" type="button" class="edge-button edge-button--primary" @click="runSavedNextAction('make-payment')">Record Payment</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('create-delivery-note')" type="button" class="edge-button" @click="runSavedNextAction('create-delivery-note')">Create Delivery Note</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1 && hasSavedNextAction('create-return-credit-note')" type="button" class="edge-button" @click="runSavedNextAction('create-return-credit-note')">Return / Credit Note</button>
						<button
							v-if="Number(savedDocument.docstatus || 0) === 1"
							type="button"
							class="edge-button edge-button--primary"
							:disabled="receiptPrinting"
							@click="printSavedReceipt"
						>
							{{ receiptPrinting ? "Printing..." : "Print Receipt" }}
						</button>
						<button v-if="Number(savedDocument.docstatus || 0) === 1" type="button" class="edge-button" @click="runSavedNextAction('output')">Print / Share</button>
						<button type="button" class="edge-button" @click="startAnother">Start Another Sale</button>
					</div>
				</section>

				<section
					v-if="savedDocument && !editingSavedDraft && Number(savedDocument.docstatus || 0) === 0"
					class="edge-panel make-sale-form"
					aria-label="Review and submit sale"
				>
					<div class="items-heading">
						<div>
							<span class="make-sale-kicker">Review & submit</span>
							<h3>Review {{ savedDocument.name }}</h3>
							<p>Confirm the saved sale below before submission. You can return to editing while it remains a draft.</p>
						</div>
						<span class="item-count">{{ savedDocument.workflow_readiness?.source === "frappe" ? "Approval required" : "Ready to submit" }}</span>
					</div>

					<SalesInvoiceSubmissionReview v-if="savedDocument.review_complete" :document="savedDocument" />

					<div v-if="workflowError" class="guided-invoice-error" role="alert">{{ workflowError }}</div>

					<div v-if="savedDocument.workflow_readiness?.source === 'frappe'" class="guided-invoice-warning" role="status">
						<strong>{{ savedDocument.workflow_readiness.workflow || "Approval Workflow" }}</strong>
						<div v-if="savedDocument.workflow_readiness.current_state">
							Current state: <strong>{{ savedDocument.workflow_readiness.current_state }}</strong>
						</div>
						<div>{{ savedDocument.workflow_readiness.message || "Use one of the permitted approval actions below." }}</div>
					</div>

					<div v-if="savedDocument.blockers?.length" class="guided-invoice-warning" role="status">
						<strong>Checks to resolve</strong>
						<ul>
							<li v-for="blocker in savedDocument.blockers" :key="blocker">{{ blocker }}</li>
						</ul>
					</div>

					<div class="make-sale-actions">
						<div>
							<strong>{{ savedDocument.workflow_readiness?.source === "frappe" ? "Approval controls this draft" : "Submit reviewed sale" }}</strong>
							<small v-if="savedDocument.workflow_readiness?.source === 'frappe'">
								Only approval actions currently available to you are shown.
							</small>
							<small v-else>
								Submission applies the normal Sales Invoice validation and posts the accounting{{ savedDocument.update_stock ? " and stock" : "" }} effects shown above.
							</small>
						</div>
						<div class="make-sale-inline-actions">
							<button type="button" class="edge-button" :disabled="workflowBusy" @click="refreshSavedDocumentPreview">
								{{ workflowBusy ? "Refreshing..." : "Refresh Review" }}
							</button>
							<button
								v-for="action in workflowActions"
								:key="action.action"
								type="button"
								class="edge-button edge-button--primary"
								:disabled="workflowBusy || !savedDocument.workflow_eligible"
								@click="applySavedWorkflow(action.action)"
							>
								{{ action.action }}
							</button>
							<button
								v-if="savedDocument.can_submit && savedDocument.workflow_readiness?.source !== 'frappe'"
								type="button"
								class="edge-button edge-button--primary"
								:disabled="workflowBusy || !savedDocument.review_complete"
								@click="confirmSavedDocumentSubmission"
							>
								{{ workflowBusy ? "Submitting..." : "Submit Reviewed Sale" }}
							</button>
							<button v-if="canUseNativeDesk" type="button" class="edge-button" :disabled="workflowBusy" @click="openAdvancedNative">
								Advanced: Open Sales Invoice
							</button>
						</div>
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

						<EdgeInput :modelValue="values.posting_date" id="make-sale-posting-date" label="Posting Date" type="date" required @update:modelValue="postingDateChanged" />

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
							:modelValue="values.price_list"
							label="Selling Price List"
							placeholder="Select assigned Price List"
							description="The effective default follows Settings → Price List Governance. When switching is allowed, choose from Price Lists assigned to you for this Branch."
							:required="Boolean(formContext.pricing?.selection_required)"
							:disabled="editingSavedDraft || Boolean(formContext.pricing?.locked) || !Boolean(formContext.pricing?.can_select)"
							:searcher="searchPriceList"
							:context="searchContext"
							@update:modelValue="setPriceList"
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

					<PartyBusinessContext
						partyType="Customer"
						:party="values.customer"
						:company="values.company"
						:branch="values.branch"
					/>

					<label class="guided-check-field">
						<input
							v-model="values.update_stock"
							type="checkbox"
							:true-value="1"
							:false-value="0"
							:disabled="editingSavedDraft || !canEditUpdateStock"
							@change="queueCommercialPreview()"
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

					<SalesCommercialTermsControls
						:values="values"
						:capabilities="commercialTermCapabilities"
						:preview="commercialPreview"
						:searcher="searchCommercialTerm"
						:disabled="saving || previewLoading"
						:openByDefault="editingSavedDraft"
						@change="updateCommercialTerms"
					/>

					<SalesCommercialSummary
						:preview="commercialPreview"
						:loading="previewLoading"
						:error="previewError"
					/>

					<p class="guided-invoice-hint">
						The effective Selling Price List follows Settings → Price List Governance. When switching is allowed, Branch-assigned alternatives can be chosen here.
						Changing the Price List automatically re-prices entered items, and the server validates pricing again when the draft is saved.
					</p>
					<p v-if="formContext.pricing?.allow_rate_change === false" class="guided-invoice-warning" role="status">
						Selling rate is read-only. {{ formContext.pricing?.rate_change_lock_reason || "Rate editing is disabled by the current pricing policy." }}
					</p>

					<label class="guided-field guided-field--wide">
						<span>Remarks</span>
						<textarea v-model="values.remarks" class="form-control" rows="4" placeholder="Optional note for this invoice"></textarea>
					</label>

					<div class="make-sale-actions">
						<div>
							<strong>{{ hasUnsavedChanges ? "Unsaved changes" : "Ready" }}</strong>
							<small v-if="hasUnsavedChanges">This browser session keeps a temporary recovery copy until the Sales Invoice draft is saved.</small>
							<small v-else>Complete the required fields, then save the Sales Invoice draft.</small>
						</div>
						<div class="make-sale-inline-actions">
							<button v-if="canUseNativeDesk" type="button" class="edge-button" :disabled="saving" @click="openAdvancedNative">Advanced: Open Sales Invoice</button>
							<button v-if="editingSavedDraft" type="button" class="edge-button" :disabled="saving" @click="cancelSavedDraftEdit">Cancel Edit</button>
							<button v-else type="button" class="edge-button" :disabled="saving" @click="resetForm">Reset</button>
							<button
								type="submit"
								class="edge-button edge-button--primary"
								:disabled="saving || loading || !transactionContextReady || commercialPreviewBlocked"
							>
								{{ saving ? "Saving..." : (editingSavedDraft ? "Update Draft" : (formContext.submit_label || "Save Draft")) }}
							</button>
						</div>
					</div>
				</form>
			</div>

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
				@saved="handlePaymentSaved"
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
import StandardDeliveryCompletionDialog from "../professional_selling/StandardDeliveryCompletionDialog.vue";
import SimplePaymentDialog from "../retailedge_business_hub/SimplePaymentDialog.vue";
import PartyBusinessContext from "../retailedge_business_hub/PartyBusinessContext.vue";
import SalesCommercialSummary from "../selling/SalesCommercialSummary.vue";
import SalesCommercialTermsControls from "../selling/SalesCommercialTermsControls.vue";
import SalesInvoiceSubmissionReview from "./SalesInvoiceSubmissionReview.vue";
import UnfinishedSalesPanel from "./UnfinishedSalesPanel.vue";
import {
	openRetailPrinterSetup,
	printRetailReceipt,
} from "../thermalReceiptPrinting";

const CONTEXT_METHOD = "retailedge.guided_sales_invoice.get_simple_sales_invoice_context";
const SEARCH_METHOD = "retailedge.guided_sales_invoice.search_simple_sales_invoice_options";
const PRICING_METHOD = "retailedge.guided_sales_invoice.get_simple_sales_invoice_item_pricing";
const PRICE_CONTEXT_METHOD = "retailedge.guided_pricing.get_allowed_price_list_context";
const CREATE_METHOD = "retailedge.guided_sales_invoice.create_simple_sales_invoice_draft";
const COMMERCIAL_PREVIEW_METHOD = "retailedge.sales_commercial_preview.get_sales_invoice_commercial_preview";
const COMMERCIAL_TERM_CONTEXT_METHOD = "retailedge.sales_commercial_terms.get_sales_commercial_edit_context";
const COMMERCIAL_TERM_SEARCH_METHOD = "retailedge.sales_commercial_terms.search_sales_commercial_term_options";
const UPDATE_WITH_TERMS_METHOD = "retailedge.sales_commercial_draft_update.update_sales_invoice_draft_with_commercial_terms";
const PREVIEW_METHOD = "retailedge.sales_invoice_workbench.get_sales_invoice_submission_review";
const DRAFTS_METHOD = "retailedge.sales_invoice_workbench.get_resumable_sales_invoice_drafts";
const SUBMIT_METHOD = "retailedge.standard_sales_invoice_completion.submit_standard_sales_invoice";
const WORKFLOW_METHOD = "retailedge.standard_sales_invoice_completion.apply_standard_sales_invoice_workflow_action";
const SHELL_METHOD = "retailedge.master_experience.get_retailedge_business_hub_context";
const CREATE_DELIVERY_METHOD = "retailedge.professional_delivery.create_delivery_note_from_sales_invoice";
const CREATE_RETURN_METHOD = "retailedge.professional_sales_invoice.create_sales_return_credit_note_draft";
const SALES_ACTIONS_METHOD = "retailedge.professional_selling.get_professional_selling_record_actions";
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
		price_list: "",
		update_stock: 1,
		coupon_code: "",
		taxes_and_charges: "",
		additional_discount_percentage: 0,
		discount_amount: 0,
		apply_discount_on: "Grand Total",
		remarks: "",
		items: [{ item_code: "", qty: 1, rate: "" }],
	};
}

function sourceLabel(source) {
	return {
		branch_default: "Branch default",
		user_selected: "Selected Price List",
		branch_assignment: "Branch-assigned Price List",
		user_default: "User default",
		user_permission: "User-assigned Price List",
		pos_profile: "Assigned POS Profile",
		party_default: "Customer default",
		erpnext_default: "Default Selling Price List",
		standard_price_list: "Standard Selling",
		item_fallback: "Item fallback",
	}[source] || "Standard pricing";
}

function cloneValues(values) {
	return JSON.parse(JSON.stringify(values || emptyValues()));
}

function editableSnapshot(values) {
	const clean = cloneValues(values);
	clean.items = (clean.items || []).map((row) => {
		const copy = { ...row };
		delete copy.uom;
		delete copy.discount_percentage;
		delete copy.amount;
		return copy;
	});
	return JSON.stringify(clean);
}

function cleanStoredPayload(raw, maxAge) {
	if (!raw) return null;
	try {
		const parsed = JSON.parse(raw);
		if (!parsed?.createdAt || Date.now() - Number(parsed.createdAt) > maxAge) return null;
		const hasValues = parsed.values && typeof parsed.values === "object";
		const hasDocument = Boolean(String(parsed.document_name || "").trim());
		if (!hasValues && !hasDocument) return null;
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
		StandardDeliveryCompletionDialog,
		SimplePaymentDialog,
		PartyBusinessContext,
		SalesCommercialSummary,
		SalesCommercialTermsControls,
		SalesInvoiceSubmissionReview,
		UnfinishedSalesPanel,
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
			previewLoading: false,
			previewError: "",
			previewToken: 0,
			previewTimer: null,
			previewAppliedSignature: "",
			commercialPreview: null,
			savedCommercialTermCapabilities: null,
			recoveryCandidate: null,
			handoffNotice: "",
			recoveryTimer: null,
			savedDocument: null,
			editingSavedDraft: false,
			workflowBusy: false,
			workflowError: "",
			receiptPrinting: false,
			unfinishedSales: [],
			unfinishedSalesLoading: false,
			unfinishedSalesError: "",
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
				{ fieldname: "uom", label: "UOM", fieldtype: "Data", read_only: 1 },
				{ fieldname: "qty", label: "Qty", fieldtype: "Float", default: 1 },
				{ fieldname: "rate", label: "Selling Rate", fieldtype: "Currency", placeholder: "Auto price" },
				{ fieldname: "discount_percentage", label: "Discount %", fieldtype: "Float", read_only: 1 },
				{ fieldname: "amount", label: "Amount", fieldtype: "Currency", read_only: 1 },
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
		commercialTermCapabilities() {
			if (this.editingSavedDraft && this.savedCommercialTermCapabilities) return this.savedCommercialTermCapabilities;
			return this.commercialPreview?.commercial_term_capabilities
				|| this.formContext.capabilities?.commercial_terms
				|| {};
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
				price_list: this.values.price_list,
			};
		},
		hasUnsavedChanges() {
			return Boolean(this.initialSnapshot && editableSnapshot(this.values) !== this.initialSnapshot);
		},
		populatedItemCount() {
			return (this.values.items || []).filter((row) => row?.item_code).length;
		},
		workflowActions() {
			return this.savedDocument?.workflow_readiness?.available_actions || [];
		},
		recoverySummary() {
			const values = this.recoveryCandidate?.values || {};
			const itemCount = (values.items || []).filter((row) => row?.item_code).length;
			const party = values.customer ? `Customer: ${values.customer}. ` : "";
			return `${party}${itemCount} item${itemCount === 1 ? "" : "s"} entered.`;
		},
		commercialPreviewRequired() {
			return Boolean(this.values.customer && this.populatedItemCount && this.transactionContextReady);
		},
		commercialPreviewSignature() {
			return JSON.stringify({
				company: this.values.company || "",
				branch: this.values.branch || "",
				warehouse: this.values.warehouse || "",
				customer: this.values.customer || "",
				price_list: this.values.price_list || "",
				posting_date: this.values.posting_date || "",
				update_stock: Number(this.values.update_stock || 0),
				coupon_code: this.values.coupon_code || "",
				taxes_and_charges: this.values.taxes_and_charges || "",
				additional_discount_percentage: Number(this.values.additional_discount_percentage || 0),
				discount_amount: Number(this.values.discount_amount || 0),
				apply_discount_on: this.values.apply_discount_on || "Grand Total",
				items: (this.values.items || [])
					.filter((row) => row?.item_code)
					.map((row) => ({ item_code: row.item_code, qty: Number(row.qty || 0), rate: row.rate === "" ? "" : Number(row.rate || 0) })),
			});
		},
		commercialPreviewBlocked() {
			if (!this.commercialPreviewRequired) return false;
			return Boolean(
				this.previewLoading
				|| this.previewError
				|| !this.commercialPreview
				|| this.previewAppliedSignature !== this.commercialPreviewSignature
			);
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
			if (this.loading) return;
			const pendingHandoff = this.hasPendingHandoff();
			if (pendingHandoff) this.loaded = false;
			if (!this.loaded || pendingHandoff) this.loadPage();
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
		if (this.previewTimer) window.clearTimeout(this.previewTimer);
		this.previewToken += 1;
	},
	methods: {
		async loadPage() {
			if (this.loading) return;
			this.loading = true;
			this.loadError = "";
			this.saveError = "";
			this.savedDocument = null;
			this.savedCommercialTermCapabilities = null;
			this.recoveryCandidate = null;
			this.workflowError = "";
			this.handoffNotice = "";
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
			try {
				const [data, shell] = await Promise.all([
					callMethod(CONTEXT_METHOD),
					callMethod(SHELL_METHOD),
				]);
				this.formContext = data || {};
				this.applyShellContext(shell || {});
				this.applyFreshDefaults(data?.defaults || {});
				const usedHandoff = await this.consumeHandoff();
				if (!usedHandoff) {
					this.loadRecoveryCandidate();
					await this.refreshUnfinishedSales({ silent: true });
				}
				this.loaded = true;
			} catch (error) {
				this.loadError = errorMessage(error, "Unable to prepare Make Sale.");
			} finally {
				this.loading = false;
			}
		},
		async refreshUnfinishedSales({ silent = false } = {}) {
			if (this.unfinishedSalesLoading) return;
			this.unfinishedSalesLoading = true;
			if (!silent) this.unfinishedSalesError = "";
			try {
				const drafts = await callMethod(DRAFTS_METHOD, { limit: 12 }, "GET");
				this.unfinishedSales = Array.isArray(drafts) ? drafts : [];
				this.unfinishedSalesError = "";
			} catch (error) {
				this.unfinishedSales = [];
				this.unfinishedSalesError = errorMessage(error, "Unable to load unfinished sales.");
			} finally {
				this.unfinishedSalesLoading = false;
			}
		},
		async openUnfinishedSale(name, { edit = false } = {}) {
			const documentName = String(name || "").trim();
			if (!documentName || this.saving || this.workflowBusy) return;
			const openDraft = async () => {
				this.saveError = "";
				this.workflowError = "";
				try {
					const preview = await callMethod(PREVIEW_METHOD, { name: documentName, source_mode: "standard" }, "GET");
					if (Number(preview?.docstatus || 0) !== 0) {
						this.savedDocument = { ...preview, doctype: "Sales Invoice" };
						this.handoffNotice = `Sale ${documentName} is no longer a draft. Its current status is shown below.`;
						return;
					}
					if (preview?.is_return || preview?.source_mode === "sales_return") {
						this.saveError = "Return / Credit Note drafts use the governed return review instead of Make Sale.";
						return;
					}
					this.savedDocument = { ...preview, doctype: "Sales Invoice" };
					this.syncPageFromDraftPreview(preview);
					this.editingSavedDraft = false;
					this.savedCommercialTermCapabilities = null;
					this.recoveryCandidate = null;
					this.clearRecovery();
					this.initialSnapshot = editableSnapshot(this.values);
					this.handoffNotice = edit
						? `Resuming unfinished sale ${documentName}. Review the saved values before updating the draft.`
						: `Reviewing unfinished sale ${documentName}. Edit it if anything needs to change before submission.`;
					if (edit) await this.beginSavedDraftEdit();
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to open this unfinished sale.");
				}
			};
			if (this.hasUnsavedChanges && !this.savedDocument) {
				frappe.confirm(
					"Open this unfinished sale? The unsaved entries currently on Make Sale will be replaced.",
					openDraft,
				);
				return;
			}
			await openDraft();
		},
		resumeUnfinishedSale(name) {
			return this.openUnfinishedSale(name, { edit: true });
		},
		reviewUnfinishedSale(name) {
			return this.openUnfinishedSale(name, { edit: false });
		},
		applyFreshDefaults(defaults) {
			this.savedCommercialTermCapabilities = null;
			this.values = {
				...emptyValues(),
				...(defaults || {}),
				items: (defaults?.items || emptyValues().items).map((row) => ({ ...row })),
			};
			if (!this.formContext.capabilities?.can_edit_update_stock) this.values.update_stock = 1;
			this.applyRatePermission();
			this.invalidateCommercialPreview();
			this.initialSnapshot = editableSnapshot(this.values);
		},
		applyRatePermission(pricing = this.formContext.pricing || {}) {
			const readOnly = pricing?.allow_rate_change === false;
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
				"Leave Make Sale? Unsaved changes are kept temporarily in this browser session, but no Sales Invoice draft has been created yet.",
				navigate
			);
		},
		recoveryKey() {
			return `${RECOVERY_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`;
		},
		handoffKey() {
			return `${HANDOFF_PREFIX}${encodeURIComponent(frappe.session?.user || "Guest")}`;
		},
		hasPendingHandoff() {
			try {
				const raw = window.sessionStorage.getItem(this.handoffKey()) || "";
				return Boolean(cleanStoredPayload(raw, HANDOFF_MAX_AGE_MS));
			} catch (_error) {
				return false;
			}
		},
		async consumeHandoff() {
			let raw = "";
			try {
				raw = window.sessionStorage.getItem(this.handoffKey()) || "";
				window.sessionStorage.removeItem(this.handoffKey());
			} catch (_error) {
				return false;
			}
			const payload = cleanStoredPayload(raw, HANDOFF_MAX_AGE_MS);
			if (!payload) return false;
			if (payload.document_name) {
				return this.consumeSavedDraftHandoff(payload);
			}
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
				await this.revalidateCarriedPricing();
				this.queueCommercialPreview();
				this.handoffNotice = "Quick Sale data was carried into Make Sale and its current Branch, Stock Location and Price List access were revalidated.";
			} catch (error) {
				this.values.branch = "";
				this.values.warehouse = "";
				this.invalidateCommercialPreview();
				this.saveError = errorMessage(error, "The carried Branch or Stock Location is no longer available. Choose the current transaction context before saving.");
				this.handoffNotice = "Quick Sale line items were carried over, but the saved Branch / Stock Location was cleared because access could not be revalidated.";
			}
			return true;
		},
		async consumeSavedDraftHandoff(payload) {
			const name = String(payload?.document_name || "").trim();
			if (!name) return false;
			try {
				const preview = await callMethod(PREVIEW_METHOD, { name }, "GET");
				if (Number(preview?.docstatus || 0) !== 0) {
					this.savedDocument = { ...preview, doctype: "Sales Invoice" };
					this.handoffNotice = `Sales Invoice ${name} is no longer a draft. Review its current status instead of editing it.`;
					return true;
				}
				if (preview?.is_return || preview?.source_mode === "sales_return") {
					this.saveError = "Return / Credit Note drafts remain in the governed return review and are not edited through Make Sale.";
					return true;
				}
				this.savedDocument = { ...preview, doctype: "Sales Invoice" };
				this.syncPageFromDraftPreview(preview);
				this.editingSavedDraft = false;
				this.savedCommercialTermCapabilities = null;
				this.recoveryCandidate = null;
				this.clearRecovery();
				this.initialSnapshot = editableSnapshot(this.values);
				this.handoffNotice = `Sales Invoice ${name} was saved from Quick Sale. Review the sale below or edit it before submission.`;
				return true;
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to load the Sales Invoice draft on Make Sale.");
				return true;
			}
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
				await this.revalidateCarriedPricing();
				this.queueCommercialPreview();
				this.handoffNotice = "Recovered unsaved Make Sale work and revalidated its current Branch, Stock Location and Price List access.";
			} catch (error) {
				this.values.branch = "";
				this.values.warehouse = "";
				this.invalidateCommercialPreview();
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
				this.savedCommercialTermCapabilities = null;
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
					price_list: this.values.price_list,
					coupon_code: this.values.coupon_code,
					taxes_and_charges: this.values.taxes_and_charges,
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
		searchPriceList(query) {
			return this.searchOptions("price_list", query);
		},
		async searchCommercialTerm(fieldname, query) {
			if (this.editingSavedDraft && this.savedDocument?.name) {
				const results = await callMethod(COMMERCIAL_TERM_SEARCH_METHOD, {
					fieldname,
					txt: query || "",
					values: {
						document_name: this.savedDocument.name,
						company: this.values.company,
						customer: this.values.customer,
					},
				});
				return Array.isArray(results) ? results : [];
			}
			return this.searchOptions(fieldname, query);
		},
		updateCommercialTerms(patch) {
			this.values = { ...this.values, ...(patch || {}) };
			this.invalidateCommercialPreview();
			this.queueCommercialPreview(0);
		},
		async refreshPriceListContext({ preserveSelection = false } = {}) {
			if (!this.values.company) return;
			const selected = preserveSelection ? (this.values.price_list || "") : "";
			const pricing = await callMethod(PRICE_CONTEXT_METHOD, {
				mode: "selling",
				company: this.values.company,
				branch: this.values.branch || "",
				party: this.values.customer || "",
				selected_price_list: selected,
			});
			this.formContext.pricing = pricing || {};
			this.applyRatePermission(pricing || {});
			if (pricing?.locked || pricing?.price_list || !preserveSelection) this.values.price_list = pricing?.price_list || "";
		},
		async revalidateCarriedPricing() {
			const previous = this.values.price_list || "";
			try {
				await this.refreshPriceListContext({ preserveSelection: Boolean(previous) });
			} catch (_error) {
				await this.refreshPriceListContext();
			}
			if ((this.values.price_list || "") === previous) {
				this.queueCommercialPreview();
				return;
			}
			this.pricingCache.clear();
			this.values.items = (this.values.items || []).map((row) => row?.item_code ? { ...row, rate: "", uom: "", discount_percentage: "", amount: "" } : { ...row });
			this.refreshAllItemPricing();
		},
		async setPriceList(next) {
			if (this.formContext.pricing?.locked) return;
			this.values.price_list = next || "";
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
			try {
				await this.refreshPriceListContext({ preserveSelection: true });
				this.refreshAllItemPricing();
			} catch (error) {
				this.values.price_list = "";
				this.saveError = errorMessage(error, "Unable to use the selected Selling Price List.");
			}
		},
		postingDateChanged(next) {
			const value = next || "";
			if (this.values.posting_date === value) return;
			this.values.posting_date = value;
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
			this.refreshAllItemPricing();
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
			const value = next || "";
			const changed = this.values.customer !== value;
			this.values.customer = value;
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
			if (changed) {
				this.values.coupon_code = "";
				this.values.taxes_and_charges = "";
				this.values.items = this.values.items.map((row) => ({ ...row, rate: "", uom: "", discount_percentage: "", amount: "" }));
				this.refreshPriceListContext()
					.then(() => this.refreshAllItemPricing())
					.catch((error) => { this.saveError = errorMessage(error, "Unable to refresh Selling Price List."); });
			}
		},
		async setBranch(next) {
			const branch = next || "";
			this.values.branch = branch;
			this.values.warehouse = "";
			this.values.items = (this.values.items || []).map((row) => ({ ...row, rate: "", uom: "", discount_percentage: "", amount: "" }));
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
			if (!this.values.company) return;
			if (!branch) {
				try {
					await this.refreshPriceListContext();
					this.refreshAllItemPricing();
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to refresh Selling Price List.");
				}
				return;
			}
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
				await this.refreshPriceListContext();
				this.refreshAllItemPricing();
			} catch (error) {
				if (token === this.cascadeToken) this.saveError = errorMessage(error, "Unable to resolve the Branch stock location.");
			}
		},
		async setWarehouse(next) {
			const warehouse = next || "";
			this.values.warehouse = warehouse;
			this.pricingCache.clear();
			this.invalidateCommercialPreview();
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
			let rateOnlyChanged = false;
			this.values.items = (nextRows || []).map((row, index) => {
				const prior = previous[index] || {};
				const itemChanged = row.item_code !== prior.item_code;
				const quantityChanged = Number(row.qty || 1) !== Number(prior.qty || 1);
				const rateChanged = String(row.rate ?? "") !== String(prior.rate ?? "");
				if (row.item_code && (itemChanged || quantityChanged)) {
					changed.push(index);
					return { ...row, rate: "", uom: "", discount_percentage: "", amount: "" };
				}
				if (row.item_code && rateChanged) rateOnlyChanged = true;
				return { ...row };
			});
			this.invalidateCommercialPreview();
			for (const index of changed) this.loadItemPricing(index);
			if (!changed.length || rateOnlyChanged) this.queueCommercialPreview();
		},
		pricingCacheKey(row) {
			return [
				this.values.company,
				this.values.branch,
				this.values.warehouse,
				this.values.customer,
				this.values.price_list,
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
							price_list: this.values.price_list,
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
					...result,
					price_list: result?.price_list || this.formContext.pricing?.price_list || "",
					source: result?.source || this.formContext.pricing?.source || "item_fallback",
				};
				if (result?.price_list && (result?.locked || !this.values.price_list)) this.values.price_list = result.price_list;
				this.queueCommercialPreview();
			} catch (error) {
				if (this.pricingTokens[index] === token) {
					this.saveError = errorMessage(error, `Unable to price ${row.item_code}.`);
					this.invalidateCommercialPreview();
				}
			}
		},
		refreshAllItemPricing() {
			this.invalidateCommercialPreview();
			if (!this.values.customer) return;
			let pending = 0;
			this.values.items.forEach((row, index) => {
				if (!row.item_code) return;
				pending += 1;
				this.values.items[index] = { ...row, rate: "", uom: "", discount_percentage: "", amount: "" };
				this.loadItemPricing(index);
			});
			if (!pending) this.queueCommercialPreview();
		},
		invalidateCommercialPreview() {
			if (this.previewTimer) {
				window.clearTimeout(this.previewTimer);
				this.previewTimer = null;
			}
			this.previewToken += 1;
			this.previewLoading = false;
			this.previewError = "";
			this.previewAppliedSignature = "";
			this.commercialPreview = null;
		},
		queueCommercialPreview(delay = 120) {
			if (this.previewTimer) window.clearTimeout(this.previewTimer);
			this.previewAppliedSignature = "";
			this.previewError = "";
			if (!this.commercialPreviewRequired) {
				this.previewLoading = false;
				this.commercialPreview = null;
				return;
			}
			this.previewLoading = true;
			this.previewTimer = window.setTimeout(() => {
				this.previewTimer = null;
				this.refreshCommercialPreview();
			}, Math.max(0, Number(delay || 0)));
		},
		async refreshCommercialPreview() {
			if (!this.commercialPreviewRequired) {
				this.previewLoading = false;
				return;
			}
			const signature = this.commercialPreviewSignature;
			const token = ++this.previewToken;
			this.previewLoading = true;
			this.previewError = "";
			const args = { values: this.values };
			if (this.editingSavedDraft && this.savedDocument?.name) args.document_name = this.savedDocument.name;
			try {
				const result = await callMethod(COMMERCIAL_PREVIEW_METHOD, args, "POST");
				if (token !== this.previewToken || signature !== this.commercialPreviewSignature) return;
				this.commercialPreview = result || null;
				this.previewAppliedSignature = signature;
				this.applyCommercialPreviewItems(result?.items || []);
			} catch (error) {
				if (token !== this.previewToken) return;
				this.commercialPreview = null;
				this.previewAppliedSignature = "";
				this.previewError = errorMessage(error, "Check the Customer, items, pricing, discount or tax setup and try again.");
			} finally {
				if (token === this.previewToken) this.previewLoading = false;
			}
		},
		applyCommercialPreviewItems(items) {
			const rows = (items || []).filter((row) => !row?.is_free_item);
			let cursor = 0;
			this.values.items = (this.values.items || []).map((row) => {
				if (!row?.item_code) return { ...row };
				const previewRow = rows[cursor++] || {};
				return {
					...row,
					uom: previewRow.uom || "",
					discount_percentage: Number(previewRow.discount_percentage || 0),
					amount: Number(previewRow.amount || 0),
				};
			});
		},
		async saveDraft() {
			if (this.saving || this.loading || !this.transactionContextReady) return;
			if (this.commercialPreviewBlocked) {
				this.saveError = this.previewError || "Wait for the current invoice total to finish updating before saving.";
				this.queueCommercialPreview(0);
				return;
			}
			this.saveError = "";
			this.saving = true;
			try {
				let result;
				if (this.savedDocument?.name && this.editingSavedDraft) {
					result = await callMethod(UPDATE_WITH_TERMS_METHOD, {
						name: this.savedDocument.name,
						expected_modified: this.savedDocument.modified || "",
						values: {
							posting_date: this.values.posting_date,
							remarks: this.values.remarks || "",
							coupon_code: this.values.coupon_code || "",
							taxes_and_charges: this.values.taxes_and_charges || "",
							additional_discount_percentage: Number(this.values.additional_discount_percentage || 0),
							discount_amount: Number(this.values.discount_amount || 0),
							apply_discount_on: this.values.apply_discount_on || "Grand Total",
							items: (this.values.items || []).filter((row) => row?.item_code).map((row) => ({
								name: row.name || "",
								item_code: row.item_code,
								qty: Number(row.qty || 0),
								rate: row.rate,
							})),
						},
					}, "POST");
					this.syncPageFromDraftPreview(result);
					this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
					this.initialSnapshot = editableSnapshot(this.values);
					this.editingSavedDraft = false;
					this.savedCommercialTermCapabilities = null;
					this.invalidateCommercialPreview();
					await this.refreshSavedDocumentPreview({ silent: true });
					frappe.show_alert?.({ message: `Sales Invoice ${result.name} draft updated`, indicator: "green" });
					return;
				}
				result = await callMethod(CREATE_METHOD, { values: this.values });
				if (!result?.name) throw new Error("The Sales Invoice draft was not returned after saving.");
				this.clearRecovery();
				this.initialSnapshot = editableSnapshot(this.values);
				this.savedDocument = { ...result, doctype: result.doctype || "Sales Invoice" };
				this.invalidateCommercialPreview();
				await this.refreshSavedDocumentPreview({ silent: true });
				frappe.show_alert?.({ message: `Sales Invoice ${result.name} saved as Draft`, indicator: "green" });
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to save the Sales Invoice draft.");
			} finally {
				this.saving = false;
			}
		},
		async beginSavedDraftEdit() {
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 0 || this.saving) return;
			this.saveError = "";
			this.saving = true;
			try {
				const preview = await callMethod(PREVIEW_METHOD, { name: this.savedDocument.name }, "GET");
				this.savedDocument = { ...this.savedDocument, ...preview, doctype: "Sales Invoice" };
				if (!preview?.can_edit) {
					this.saveError = (preview?.blockers || [])[0] || "This Sales Invoice draft is no longer editable in the standard page.";
					return;
				}
				this.syncPageFromDraftPreview(preview);
				const commercialContext = await callMethod(
					COMMERCIAL_TERM_CONTEXT_METHOD,
					{ name: this.savedDocument.name },
					"GET"
				);
				this.applyCommercialTermContext(commercialContext);
				this.editingSavedDraft = true;
				this.initialSnapshot = editableSnapshot(this.values);
				this.queueCommercialPreview(0);
			} catch (error) {
				this.saveError = errorMessage(error, "Unable to reload this Sales Invoice draft for editing.");
			} finally {
				this.saving = false;
			}
		},
		applyCommercialTermContext(context) {
			if (!context) return;
			if (context.terms) this.values = { ...this.values, ...context.terms };
			this.savedCommercialTermCapabilities = context.capabilities || null;
		},
		cancelSavedDraftEdit() {
			const close = () => {
				try { this.values = JSON.parse(this.initialSnapshot || "{}"); } catch (_error) {}
				this.editingSavedDraft = false;
				this.savedCommercialTermCapabilities = null;
				this.invalidateCommercialPreview();
				this.saveError = "";
			};
			if (!this.hasUnsavedChanges) return close();
			frappe.confirm("Discard unsaved changes to this saved Sales Invoice draft?", close);
		},
		syncPageFromDraftPreview(result) {
			if (!result) return;
			if (result.company) this.values.company = result.company;
			if (Object.prototype.hasOwnProperty.call(result, "branch")) this.values.branch = result.branch || "";
			if (Object.prototype.hasOwnProperty.call(result, "customer")) this.values.customer = result.customer || "";
			if (Object.prototype.hasOwnProperty.call(result, "selling_price_list")) this.values.price_list = result.selling_price_list || "";
			if (Object.prototype.hasOwnProperty.call(result, "default_warehouse")) this.values.warehouse = result.default_warehouse || "";
			if (Object.prototype.hasOwnProperty.call(result, "update_stock")) this.values.update_stock = result.update_stock ? 1 : 0;
			if (result.posting_date) this.values.posting_date = result.posting_date;
			if (Object.prototype.hasOwnProperty.call(result, "remarks")) this.values.remarks = result.remarks || "";
			if (result.commercial_terms) this.values = { ...this.values, ...result.commercial_terms };
			if (result.commercial_term_capabilities) this.savedCommercialTermCapabilities = result.commercial_term_capabilities;
			if (result.pricing) {
				this.formContext = { ...this.formContext, pricing: { ...(this.formContext.pricing || {}), ...result.pricing } };
				this.applyRatePermission(result.pricing);
			}
			if (Array.isArray(result.editable_items)) {
				this.values.items = result.editable_items.map((row) => ({
					name: row.name || "",
					item_code: row.item_code || "",
					qty: row.qty,
					rate: row.rate,
				}));
			}
		},
		async refreshSavedDocumentPreview({ silent = false } = {}) {
			if (!this.savedDocument?.name || this.workflowBusy) return;
			this.workflowBusy = true;
			if (!silent) this.workflowError = "";
			try {
				const preview = await callMethod(PREVIEW_METHOD, { name: this.savedDocument.name, source_mode: "standard" }, "GET");
				this.savedDocument = { ...this.savedDocument, ...preview, doctype: "Sales Invoice" };
				if (Number(preview?.docstatus || 0) === 0) {
					this.syncPageFromDraftPreview(preview);
					if (!this.editingSavedDraft) this.initialSnapshot = editableSnapshot(this.values);
				}
			} catch (error) {
				this.workflowError = errorMessage(error, "Unable to refresh the sale review.");
			} finally {
				this.workflowBusy = false;
			}
		},
		async refreshSubmittedSalesDocumentState() {
			if (!this.savedDocument?.name) return;
			try {
				const [preview, resolved] = await Promise.all([
					callMethod(PREVIEW_METHOD, { name: this.savedDocument.name, source_mode: "standard" }, "GET"),
					callMethod(SALES_ACTIONS_METHOD, { document: "sales-invoice", name: this.savedDocument.name }, "GET"),
				]);
				this.savedDocument = {
					...this.savedDocument,
					...preview,
					doctype: "Sales Invoice",
					next_actions: resolved?.actions || [],
				};
			} catch (error) {
				this.workflowError = errorMessage(error, "Sales Invoice was completed, but its next actions could not be refreshed.");
			}
		},
		confirmSavedDocumentSubmission() {
			if (!this.savedDocument?.name || !this.savedDocument?.can_submit || !this.savedDocument?.review_complete || this.workflowBusy) return;
			const currency = String(this.savedDocument.currency || "NGN").trim() || "NGN";
			const amount = Number(this.savedDocument.rounded_total || 0) || Number(this.savedDocument.grand_total || 0);
			const formatted = `${currency} ${amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
			const effect = this.savedDocument.update_stock
				? "This will post the accounting and stock movements shown in the review."
				: "This will post the accounting entries shown in the review.";
			frappe.confirm(
				`Submit ${this.savedDocument.name} for ${formatted}? ${effect}`,
				() => this.submitSavedDocument(),
			);
		},
		async submitSavedDocument() {
			if (!this.savedDocument?.name || !this.savedDocument?.can_submit || !this.savedDocument?.review_complete || this.workflowBusy) return;
			this.workflowBusy = true;
			this.workflowError = "";
			try {
				const result = await callMethod(SUBMIT_METHOD, {
					name: this.savedDocument.name,
					expected_modified: this.savedDocument.modified || "",
					source_mode: "standard",
				}, "POST");
				this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
				this.editingSavedDraft = false;
				this.savedCommercialTermCapabilities = null;
				await this.refreshSubmittedSalesDocumentState();
				frappe.show_alert?.({ message: `Sales Invoice ${result.name || this.savedDocument.name} submitted`, indicator: "green" }, 7);
			} catch (error) {
				this.workflowError = errorMessage(error, "Unable to submit this Sales Invoice.");
			} finally {
				this.workflowBusy = false;
			}
		},
		async applySavedWorkflow(action) {
			if (!action || !this.savedDocument?.name || !this.savedDocument?.workflow_eligible || this.workflowBusy) return;
			this.workflowBusy = true;
			this.workflowError = "";
			try {
				const result = await callMethod(WORKFLOW_METHOD, {
					name: this.savedDocument.name,
					action,
					expected_modified: this.savedDocument.modified || "",
					expected_workflow_state: this.savedDocument.workflow_readiness?.current_state || "",
					source_mode: "standard",
				}, "POST");
				if (Number(result?.docstatus || 0) === 1) {
					this.savedDocument = { ...this.savedDocument, ...result, doctype: "Sales Invoice" };
					this.editingSavedDraft = false;
					this.savedCommercialTermCapabilities = null;
					await this.refreshSubmittedSalesDocumentState();
					frappe.show_alert?.({ message: `Sales Invoice ${result.name || this.savedDocument.name} submitted through Workflow`, indicator: "green" }, 7);
					return;
				}
				const preview = await callMethod(PREVIEW_METHOD, { name: this.savedDocument.name, source_mode: "standard" }, "GET");
				this.savedDocument = { ...this.savedDocument, ...preview, doctype: "Sales Invoice" };
				this.syncPageFromDraftPreview(preview);
				this.initialSnapshot = editableSnapshot(this.values);
			} catch (error) {
				this.workflowError = errorMessage(error, "Unable to apply this Sales Invoice workflow action.");
			} finally {
				this.workflowBusy = false;
			}
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
					this.deliveryCompletionOpen = true;
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to continue to Delivery Note.");
				}
				return;
			}
			if (payload.action === "create-return-credit-note") {
				try {
					const result = await callMethod(CREATE_RETURN_METHOD, { sales_invoice: payload.name }, "POST");
					if (!result?.name) throw new Error("Return / Credit Note draft was not returned.");
					window.retailedgeProfessionalSellingTarget = {
						doctype: "Sales Invoice",
						name: result.name,
						source_mode: "sales_return",
						user: frappe.session?.user || "Guest",
					};
					frappe.set_route("professional-selling");
				} catch (error) {
					this.saveError = errorMessage(error, "Unable to prepare the Return / Credit Note.");
				}
				return;
			}
			if (payload.action === "output") this.openDocumentOutput("sales-invoice", payload.name);
		},
		closePayment() {
			this.paymentOpen = false;
			this.paymentInitialContext = {};
		},
		async handlePaymentSaved() {
			this.closePayment();
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 1) return;
			try {
				const resolved = await callMethod(SALES_ACTIONS_METHOD, { document: "sales-invoice", name: this.savedDocument.name }, "GET");
				this.savedDocument = { ...this.savedDocument, next_actions: resolved?.actions || [] };
			} catch (error) {
				this.saveError = errorMessage(error, "Payment was posted, but Sales Invoice actions could not be refreshed.");
			}
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
				this.openDocumentOutput("delivery-note", payload.name);
			}
		},
		async printSavedReceipt() {
			if (!this.savedDocument?.name || Number(this.savedDocument.docstatus || 0) !== 1 || this.receiptPrinting) return;
			this.receiptPrinting = true;
			const printerContext = {
				company: this.savedDocument.company || this.values.company || this.tenantName || "",
				branch: this.savedDocument.branch || this.values.branch || this.branchName || "",
			};
			try {
				const result = await printRetailReceipt({
					document: "sales-invoice",
					name: this.savedDocument.name,
					...printerContext,
				});
				frappe.show_alert({
					message: `${result.copies || 1} receipt copy/copies printed.`,
					indicator: "green",
				});
			} catch (error) {
				const message = errorMessage(error, "Unable to print this Sales Invoice receipt.");
				const setupRequired = [
					"RETAIL_PRINTER_PROFILE_REQUIRED",
					"RETAIL_DIRECT_PRINTER_REQUIRED",
					"RETAIL_PRINTER_SETUP_REQUIRED",
				].includes(error?.code);
				if (setupRequired) {
					frappe.confirm(
						`${message} Open Devices & Printing now?`,
						() => openRetailPrinterSetup(printerContext),
					);
				} else {
					frappe.msgprint({
						title: "Receipt printing failed",
						message,
						indicator: "red",
					});
				}
			} finally {
				this.receiptPrinting = false;
			}
		},
		openDocumentOutput(document, name) {
			if (!document || !name) return;
			window.retailedge?.openDocumentOutputSharing?.(document, name);
		},
		async startAnother() {
			this.savedDocument = null;
			this.editingSavedDraft = false;
			this.savedCommercialTermCapabilities = null;
			this.recoveryCandidate = null;
			this.invalidateCommercialPreview();
			await this.loadPage();
		},
		openAdvancedNative() {
			if (!this.canUseNativeDesk) return;
			const navigate = () => this.savedDocument?.name
				? frappe.set_route("Form", "Sales Invoice", this.savedDocument.name)
				: frappe.new_doc("Sales Invoice");
			if (!this.hasUnsavedChanges) {
				navigate();
				return;
			}
			const message = this.savedDocument?.name
				? "Open the saved Sales Invoice in the advanced form? Unsaved page edits are not carried until you update the draft."
				: "Open the advanced Sales Invoice form? Save this Make Sale draft first if you want the current page entries recorded.";
			frappe.confirm(message, navigate);
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
