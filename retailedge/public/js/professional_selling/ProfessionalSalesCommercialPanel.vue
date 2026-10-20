<template>
	<section class="professional-commercial-panel" aria-live="polite">
		<SalesCommercialTermsControls
			:values="values"
			:capabilities="commercialTermCapabilities"
			:preview="commercialPreview"
			:searcher="searchCommercialTerm"
			:disabled="disabled || previewLoading"
			:documentLabel="documentLabel"
			@change="updateCommercialTerms"
		/>

		<SalesCommercialSummary
			:preview="commercialPreview"
			:loading="previewLoading"
			:error="previewError"
			:documentLabel="documentLabel"
		/>

		<p v-if="values.shipping_rule" class="selling-form-hint">
			The selected delivery charge is applied when the draft is saved and is not included in this live discount/tax preview.
		</p>
	</section>
</template>

<script>
import { callMethod, errorMessage } from "../retailedge_business_hub/guidedEntryUtils";
import SalesCommercialSummary from "../selling/SalesCommercialSummary.vue";
import SalesCommercialTermsControls from "../selling/SalesCommercialTermsControls.vue";

const COMMERCIAL_PREVIEW_METHOD = "retailedge.sales_document_commercial_preview.get_sales_document_commercial_preview";
const COMMERCIAL_TERM_SEARCH_METHOD = "retailedge.sales_commercial_terms.search_sales_commercial_term_options";

export default {
	name: "ProfessionalSalesCommercialPanel",
	components: { SalesCommercialSummary, SalesCommercialTermsControls },
	props: {
		values: { type: Object, required: true },
		documentType: { type: String, required: true },
		documentLabel: { type: String, required: true },
		active: { type: Boolean, default: true },
		disabled: { type: Boolean, default: false },
		contextReady: { type: Boolean, default: true },
	},
	emits: ["change", "state"],
	data() {
		return {
			previewLoading: false,
			previewError: "",
			previewToken: 0,
			previewTimer: null,
			previewAppliedSignature: "",
			commercialPreview: null,
		};
	},
	computed: {
		populatedItemCount() {
			return (this.values.items || []).filter((row) => row?.item_code).length;
		},
		commercialPreviewRequired() {
			return Boolean(
				this.active
				&& this.contextReady
				&& this.values.company
				&& this.values.customer
				&& this.populatedItemCount
			);
		},
		commercialPreviewSignature() {
			return JSON.stringify({
				document_type: this.documentType,
				company: this.values.company || "",
				branch: this.values.branch || "",
				warehouse: this.values.warehouse || "",
				customer: this.values.customer || "",
				price_list: this.values.price_list || "",
				transaction_date: this.values.transaction_date || "",
				valid_till: this.values.valid_till || "",
				delivery_date: this.values.delivery_date || "",
				shipping_rule: this.values.shipping_rule || "",
				coupon_code: this.values.coupon_code || "",
				tax_category: this.values.tax_category || "",
				taxes_and_charges: this.values.taxes_and_charges || "",
				additional_discount_percentage: Number(this.values.additional_discount_percentage || 0),
				discount_amount: Number(this.values.discount_amount || 0),
				apply_discount_on: this.values.apply_discount_on || "Grand Total",
				items: (this.values.items || [])
					.filter((row) => row?.item_code)
					.map((row) => ({
						item_code: row.item_code,
						qty: Number(row.qty || 0),
						rate: row.rate === "" ? "" : Number(row.rate || 0),
						manual_discount_percentage: Number(row.manual_discount_percentage || 0),
						manual_discount_amount: Number(row.manual_discount_amount || 0),
					})),
			});
		},
		commercialPreviewBlocked() {
			if (!this.active) return false;
			if (!this.commercialPreviewRequired) return true;
			return Boolean(
				this.previewLoading
				|| this.previewError
				|| !this.commercialPreview
				|| this.previewAppliedSignature !== this.commercialPreviewSignature
			);
		},
		commercialTermCapabilities() {
			return this.commercialPreview?.commercial_term_capabilities || {};
		},
	},
	watch: {
		active(next) {
			this.invalidateCommercialPreview();
			if (next) this.queueCommercialPreview(0);
		},
		commercialPreviewSignature(next, previous) {
			if (next === previous || !this.active) return;
			this.invalidateCommercialPreview();
			this.queueCommercialPreview();
		},
		commercialPreviewBlocked() {
			this.publishState();
		},
		commercialPreview() {
			this.publishState();
		},
		previewError() {
			this.publishState();
		},
	},
	mounted() {
		this.publishState();
		if (this.active) this.queueCommercialPreview(0);
	},
	beforeUnmount() {
		if (this.previewTimer) window.clearTimeout(this.previewTimer);
		this.previewToken += 1;
	},
	methods: {
		publishState() {
			this.$emit("state", {
				blocked: this.commercialPreviewBlocked,
				loading: this.previewLoading,
				error: this.previewError,
				preview: this.commercialPreview,
				signature: this.previewAppliedSignature,
			});
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
			this.publishState();
		},
		queueCommercialPreview(delay = 180) {
			if (!this.commercialPreviewRequired) {
				this.publishState();
				return;
			}
			if (this.previewTimer) window.clearTimeout(this.previewTimer);
			this.previewLoading = true;
			this.publishState();
			this.previewTimer = window.setTimeout(() => {
				this.previewTimer = null;
				this.loadCommercialPreview();
			}, Math.max(0, Number(delay || 0)));
		},
		async loadCommercialPreview() {
			if (!this.commercialPreviewRequired) return;
			const token = ++this.previewToken;
			const signature = this.commercialPreviewSignature;
			this.previewLoading = true;
			this.previewError = "";
			this.publishState();
			try {
				const result = await callMethod(
					COMMERCIAL_PREVIEW_METHOD,
					{ document_type: this.documentType, values: this.values },
					"POST",
				);
				if (token !== this.previewToken || signature !== this.commercialPreviewSignature) return;
				this.commercialPreview = result || null;
				this.previewAppliedSignature = signature;
			} catch (error) {
				if (token !== this.previewToken || signature !== this.commercialPreviewSignature) return;
				this.commercialPreview = null;
				this.previewAppliedSignature = "";
				this.previewError = errorMessage(error, `Unable to calculate the current ${this.documentLabel.toLowerCase()}.`);
			} finally {
				if (token === this.previewToken) {
					this.previewLoading = false;
					this.publishState();
				}
			}
		},
		searchCommercialTerm(fieldname, query) {
			return callMethod(
				COMMERCIAL_TERM_SEARCH_METHOD,
				{
					fieldname,
					txt: query || "",
					values: this.values,
					document_type: this.documentType,
				},
				"GET",
			).then((rows) => Array.isArray(rows) ? rows : []);
		},
		updateCommercialTerms(patch) {
			this.$emit("change", patch || {});
		},
	},
};
</script>

<style scoped>
.professional-commercial-panel {
	display: grid;
	gap: 12px;
}
.selling-form-hint {
	margin: 0;
	color: var(--edge-text-muted, #667085);
	font-size: 0.84rem;
}
</style>
